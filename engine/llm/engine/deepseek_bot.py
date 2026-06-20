"""
deepseek_bot.py
---------------
Playwright 自动化：操作 chat.deepseek.com 网页，接口与 chatgpt_bot.py 完全相同。

高层逻辑（write_section / run_chapter）全部复用 chatgpt_bot，只替换底层：
  - URL / 选择器
  - 账号存储目录
  - 错误检测词
  - 额度耗尽检测

选择器说明：
  DeepSeek 的 UI 使用 React 且类名经常随版本变化，这里以多备选 + fallback 方式
  覆盖常见情形。如 UI 更新后失效，请在浏览器 DevTools 找到对应元素更新下方常量。
"""
from __future__ import annotations

import os
import re
import sys
import time
import random
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BASE_DIR = Path(__file__).parent

# 记录最近一次成功导航到 DeepSeek 的时间（用于主动 session 续期）
_last_nav_time: float = 0.0

# ── 账号存储 ──────────────────────────────────────────────────────────────────
_env_dir = os.getenv("STUDYATHENA_ACCOUNTS_DIR")
if _env_dir:
    BOT_DIR = Path(_env_dir)
else:
    _appdata = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    BOT_DIR = _appdata / "StudyAthena" / "accounts"

BOT_DIR.mkdir(parents=True, exist_ok=True)


def _load_accounts_from_system() -> dict:
    """从系统内 accounts.json 读取账号列表，按顺序映射为数字 1,2,3…"""
    import json
    accounts_file = Path(__file__).resolve().parent.parent / "accounts.json"
    if not accounts_file.exists():
        return {}
    try:
        data = json.loads(accounts_file.read_text(encoding="utf-8"))
        accs = data.get("accounts", [])
        return {str(i + 1): acc["storage_dir"] for i, acc in enumerate(accs)}
    except Exception:
        return {}


_sys_accounts = _load_accounts_from_system()

def _ds_dir(v: str) -> str:
    """
    把 ChatGPT profile 路径转换为 DeepSeek profile 路径。
    - 旧式 account_chatgptN 路径 → 改为 account_deepseekN（隔离）
    - 新式 acc_XXXXXX 路径（accounts.json 自定义）→ 加 _deepseek 后缀
      理由：新式路径已登录 Google，可以自动 Google OAuth 重登 DeepSeek；
            ChatGPT cookie 与 DeepSeek cookie 域名完全不同，不会互相干扰。
    """
    if "account_chatgpt" in v:
        return v.replace("account_chatgpt", "account_deepseek")
    return v   # 新式路径直接复用，与旧版book_agent行为一致

ACCOUNTS = {
    k: _ds_dir(v)
    for k, v in (_sys_accounts or {
        "1": str(BOT_DIR / "account_chatgpt1"),
        "2": str(BOT_DIR / "account_chatgpt2"),
        "3": str(BOT_DIR / "account_chatgpt3"),
        "4": str(BOT_DIR / "account_chatgpt4"),
    }).items()
} or {
    "1": str(BOT_DIR / "account_deepseek1"),
    "2": str(BOT_DIR / "account_deepseek2"),
    "3": str(BOT_DIR / "account_deepseek3"),
    "4": str(BOT_DIR / "account_deepseek4"),
}

DEEPSEEK_URL = "https://chat.deepseek.com"
ERROR_SIGNAL  = "DEEPSEEK_ERROR"


class AccountNotLoggedIn(Exception):
    """账号从未登录或 session 彻底失效，应跳过该账号换下一个。"""


class BrowserRestartNeeded(Exception):
    """
    当 Google OAuth 自动重登失败时抛出，让上层调用方关闭并重开浏览器。
    相当于用户手动点击「停止 → 继续生成」的效果。
    """
    pass

# ── 参数（与 chatgpt_bot 保持一致） ──────────────────────────────────────────
MAX_CONTINUE_ROUNDS = 4
MAX_SEND_RETRIES    = 3
STABLE_SECS         = 30   # DeepSeek 思考模式有长停顿，放宽

# ── DOM 选择器（如 UI 更新后失效，在此修改） ──────────────────────────────────
_INPUT_SELECTORS = [
    # --- DeepSeek 最新 UI (2025-06) ---
    'textarea#chat-input',
    '#chat-input',
    'textarea[id*="chat"]',
    # contenteditable (新版用 prosemirror / lexical)
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"].ProseMirror',
    'div[contenteditable="true"]',
    # 通用 textarea fallback（通常是页面唯一 textarea）
    'textarea',
    # ARIA role
    '[role="textbox"]',
    # placeholder 文字匹配
    'textarea[placeholder*="消息"]',
    'textarea[placeholder*="Message"]',
    'textarea[placeholder*="问"]',
    '[placeholder*="消息"]',
    '[placeholder*="Message"]',
    # class 关键词
    '[class*="chatInput"] textarea',
    '[class*="chat-input"] textarea',
    '[class*="inputArea"] textarea',
    '[class*="input-area"] textarea',
]

_SEND_SELECTORS = [
    # DeepSeek 2025 新 UI：div[role=button] with ds-button--primary
    'div.ds-button--primary.ds-button--filled',
    'div.ds-button--primary',
    '[role="button"][class*="ds-button--primary"]',
    '[role="button"][class*="primary"]',
    # 旧版 / 通用
    'button[aria-label*="Send" i]',
    'button[aria-label*="发送"]',
    '[data-testid="send-button"]',
    'button.send-button',
    'button[type="submit"]',
    'button[class*="send"]',
    'button[class*="Send"]',
    'button[class*="submit"]',
    'form button:last-child',
    '[class*="inputAction"] button',
    '[class*="input-action"] button',
    '[class*="chatInput"] button:last-child',
    '[class*="chat-input"] button:last-child',
]

_STOP_SELECTORS = [
    'button[aria-label*="Stop" i]',
    'button[aria-label*="停止"]',
    '[data-testid="stop-button"]',
    'button.stop-button',
    'button:has-text("停止生成")',
    'button:has-text("Stop")',
]

_ANSWER_SELECTORS = [
    # DeepSeek 通常用 data-role 或类名标记 assistant 消息
    'div[data-role="assistant"]',
    'div[class*="assistant"][class*="message"]',
    'div[class*="message"][class*="bot"]',
    'div[class*="reply"]',
    # 最末一个 .prose（DeepSeek 用 TailwindCSS prose 渲染 Markdown）
    '.prose',
    # 兜底：查找最后一个含有长文本的 div
]

_QUOTA_PHRASES = [
    "您已达到免费额度",
    "You've reached your limit",
    "reached the usage limit",
    "usage limit",
    "请求频率",
    "访问频率",
]

# 临时限速（等待后重试，不算额度耗尽）
_RATE_LIMIT_PHRASES = [
    "rate limit",
    "too many requests",
    "请稍后再试",
    "稍后重试",
]

_ERROR_PHRASES = [
    "something went wrong",
    "出现了问题",
    "发生了错误",
    "无法完成",
    "服务出错",
    "网络错误",
    "请稍后重试",
    "请求失败",
    "generation error",
    "error generating",
    "服务器繁忙",
    "server busy",
    "系统繁忙",
    "服务繁忙",
]

_SERVER_BUSY_PHRASES = [
    "服务器繁忙",
    "server busy",
    "系统繁忙",
    "服务繁忙",
    "Server Busy",
]


# ── 浏览器操作 ────────────────────────────────────────────────────────────────

def _is_browser_closed_error(e: Exception) -> bool:
    """判断异常是否由浏览器/页面/context 已关闭引起（区别于普通网络错误）。"""
    msg = str(e).lower()
    return "closed" in msg and any(k in msg for k in ("page", "browser", "context", "target"))


_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
Object.defineProperty(navigator, 'plugins',    { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages',  { get: () => ['zh-CN','zh','en-US','en'] });
Object.defineProperty(navigator, 'platform',   { get: () => 'Win32' });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
""".strip()

# 真实 Chrome 131 UA（Windows）
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _is_logged_out(page) -> bool:
    """检测页面是否跳到了登录页。

    只用强信号判断，避免把聊天页面上的普通"登录"按钮误判为已登出：
    1. URL 明确指向登录/OAuth 页
    2. 页面存在输入框 → 一定已登录（优先 short-circuit）
    3. 页面存在 Google 登录专属文本
    """
    try:
        url = page.url or ""
        # URL 强信号（/sign_in 是 DeepSeek 最新的登录跳转路径）
        if ("/login" in url or "/sign_in" in url or "/signin" in url
                or "accounts.deepseek.com" in url or "accounts.google.com" in url):
            print(f"  [登出检测] URL 指向登录页: {url[:80]}")
            return True
        # 有输入框 → 肯定在聊天页面，已登录
        for sel in ('textarea', 'div[contenteditable="true"]', '[role="textbox"]'):
            try:
                if page.locator(sel).first.is_visible(timeout=300):
                    return False
            except Exception:
                pass
        # 无输入框时，再检查 Google 登录专属文本（比"登录"更精确）
        for sel in ('text=Continue with Google', 'text=使用 Google 登录',
                    'button:has-text("Continue with Google")'):
            try:
                if page.locator(sel).count() > 0:
                    print(f"  [登出检测] 发现 Google 登录按钮: {sel}")
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _has_captcha(page) -> bool:
    """检测页面是否出现了验证码（滑块 / reCAPTCHA / 人机验证）。"""
    try:
        sels = [
            'iframe[src*="captcha"]', 'iframe[src*="recaptcha"]',
            '[class*="captcha"]', '[id*="captcha"]',
            # 精确匹配：避免 DeepSeek 正常 UI（滚动条、进度条等）误触发
            '[class="verify"]', '[id="verify"]',
            '[class="slider-container"]', '[class="slider-btn"]',
            'text=人机验证', 'text=滑动验证',
            'text=CAPTCHA', 'text=请完成验证',
            # 宽泛文本匹配：只保留明确的验证提示，去掉 "验证码" 避免误匹配输入提示
        ]
        for sel in sels:
            try:
                if page.locator(sel).count() > 0:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _wait_for_captcha(page, timeout_secs: int = 300) -> bool:
    """检测到验证码后暂停，等用户手动完成验证。"""
    print("\n⚠️  检测到验证码！请在浏览器中完成人机验证...")
    print(f"  机器人将持续检测（最多等待 {timeout_secs // 60} 分钟）...")
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        time.sleep(3)
        try:
            if not _has_captcha(page):
                print("  ✅ 验证码已通过，继续运行")
                return True
        except Exception:
            pass
    print("  ❌ 等待验证码超时")
    return False


_GOOGLE_BTN_SELS = [
    'button:has-text("Continue with Google")',
    'button:has-text("使用 Google 登录")',
    'button:has-text("Google")',
    'a:has-text("Continue with Google")',
    'a:has-text("Google")',
    '[data-provider="google"]',
    '[class*="google"]',
    'text=Continue with Google',
]

_GOOGLE_ACCT_SELS = [
    'div[data-identifier]',        # Google 账号行（含邮箱）
    '[data-authuser="0"]',         # 第一个已登录账号
    'div[data-email]',
    '[data-gb-user]',
    'div[role="listitem"]:first-child',
    'li:first-child',
    'ul li:first-child a',
    'div.account:first-child',
]


def _auto_relogin_google(page) -> bool:
    """检测到登出后，利用浏览器已有 Google session 自动完成 OAuth 重登。

    同时支持：
    - Redirect 流：主页面直接跳到 Google 再跳回（更常见）
    - Popup 流：弹出 Google 账号选择窗口

    策略：点击 Google 按钮后，持续 90 秒轮询主页面是否恢复；
    期间若有 popup 出现则尝试点击账号，但不依赖 popup 是否出现。
    """
    print("  → 尝试自动重登（利用 Google 已有会话）...")
    try:
        page.goto(DEEPSEEK_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(4)

        if not _is_logged_out(page):
            _refresh_session(page)
            print("  ✅ 导航后 session 已恢复")
            return True

        # 找 Google 登录按钮
        btn_loc = None
        for sel in _GOOGLE_BTN_SELS:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=3_000):
                    btn_loc = loc.first
                    break
            except Exception:
                pass

        if btn_loc is None:
            print("  → 未找到 Google 登录按钮，跳过自动重登")
            return False

        ctx = getattr(page, "_sa_ctx", None)
        popup_ref: list = [None]

        def _on_new_page(new_page):
            if popup_ref[0] is None:
                popup_ref[0] = new_page

        if ctx:
            ctx.on("page", _on_new_page)

        try:
            btn_loc.click()
            print("  → 已点击 Google 按钮，等待 OAuth 完成（最多90秒）...")

            popup_handled = False
            deadline = time.time() + 90

            while time.time() < deadline:
                time.sleep(2)

                # 优先：主页面已恢复登录（redirect 流 或 popup 完成后）
                try:
                    url = page.url or ""
                    if "deepseek.com" in url and not _is_logged_out(page):
                        _refresh_session(page)
                        print("  ✅ 自动重登成功")
                        return True
                except Exception:
                    pass

                # 处理 popup（只需处理一次）
                if not popup_handled:
                    gp = popup_ref[0]
                    if gp is not None:
                        try:
                            if gp.is_closed():
                                popup_handled = True
                                continue
                            gp.wait_for_load_state("domcontentloaded", timeout=5_000)
                            # 尝试点击 Google 账号列表中的第一项
                            clicked = False
                            for asel in _GOOGLE_ACCT_SELS:
                                try:
                                    aloc = gp.locator(asel)
                                    if aloc.count() > 0 and aloc.first.is_visible(timeout=1_000):
                                        aloc.first.click()
                                        clicked = True
                                        popup_handled = True
                                        break
                                except Exception:
                                    pass
                            if not clicked:
                                # JS 兜底：找第一个含邮件地址文本的可见 div
                                try:
                                    sel_js = gp.evaluate("""() => {
                                        const els = [...document.querySelectorAll('[data-identifier],[data-authuser],li,div[role="listitem"]')];
                                        const el = els.find(e => e.offsetParent !== null);
                                        if (el) { if (el.id) return '#'+el.id; const c = el.className.trim().split(' ')[0]; return el.tagName.toLowerCase()+(c?'.'+c:''); }
                                        return null;
                                    }""")
                                    if sel_js:
                                        gp.locator(sel_js).first.click()
                                        popup_handled = True
                                except Exception:
                                    pass
                        except Exception as e:
                            print(f"  popup 处理失败: {e}")
                            popup_handled = True  # 不要反复重试

        finally:
            if ctx:
                try:
                    ctx.remove_listener("page", _on_new_page)
                except Exception:
                    pass

    except Exception as e:
        print(f"  自动重登异常：{e}")
    print("  → 自动重登超时或失败")
    return False


def _wait_for_manual_login(page, timeout_secs: int = 28800) -> bool:
    """自动重登失败后，轮询等待登录恢复（默认最多 8 小时）。

    每 5 分钟自动重试一次 Google OAuth 重登，
    期间若用户手动在浏览器登录也能立刻感知继续运行。
    """
    hours = timeout_secs // 3600
    print(f"\n{'='*60}")
    print(f"  ⚠️  DeepSeek 需要手动登录（自动 Google 重登失败）")
    print(f"  👉 请在弹出的浏览器窗口中：")
    print(f"     1. 点击「使用 Google 登录」按钮")
    print(f"     2. 选择 LucyQQ / LucyZhaoQQ 账号")
    print(f"     3. 完成后页面会自动跳转到 DeepSeek 聊天界面")
    print(f"  机器人检测到登录成功后自动继续（最多等 {hours} 小时）")
    print(f"{'='*60}\n")
    deadline = time.time() + timeout_secs
    last_auto_attempt = 0.0
    while time.time() < deadline:
        time.sleep(4)
        try:
            if not _is_logged_out(page):
                _refresh_session(page)
                print("  ✅ 检测到已登录，继续运行...")
                return True
        except Exception:
            pass
        # 每 5 分钟自动重试一次 Google OAuth
        if time.time() - last_auto_attempt >= 300:
            last_auto_attempt = time.time()
            try:
                print("  🔄 自动重试 Google 重登...")
                if _auto_relogin_google(page):
                    print("  ✅ Google 重登成功，继续运行...")
                    return True
            except Exception:
                pass
    print("  ❌ 等待手动登录超时（8小时），退出当前任务")
    return False


def _kill_chrome_using_profile(account_dir: str) -> None:
    """Kill Chrome processes using the given user-data-dir profile."""
    import subprocess as _sp
    # 先终止本模块跟踪的真实 Chrome 子进程
    proc = _chrome_procs.pop(account_dir, None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

    # 用 WMI 查找命令行包含 account_dir 的真实 Chrome 进程
    safe_dir = account_dir.replace("'", "''")
    ps_script_real = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{safe_dir}*' -and $_.Name -like 'chrome*' }} | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        result = _sp.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script_real],
            capture_output=True, text=True, timeout=15
        )
        killed = 0
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                try:
                    _sp.run(["taskkill", "/PID", line, "/F", "/T"],
                            capture_output=True, timeout=5)
                    killed += 1
                except Exception:
                    pass
        if killed:
            print(f"  [锁清理] 已终止 {killed} 个真实 Chrome 进程 (profile匹配)")
    except Exception as e:
        print(f"  [锁清理] 查找真实Chrome进程失败: {e}")

    # Kill ALL ms-playwright chromium processes (Playwright fallback路径)
    ps_script_pw = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -like '*ms-playwright*chrome*' } | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        result = _sp.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script_pw],
            capture_output=True, text=True, timeout=15
        )
        killed = 0
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                try:
                    _sp.run(["taskkill", "/PID", line, "/F"],
                            capture_output=True, timeout=5)
                    killed += 1
                except Exception:
                    pass
        if killed:
            print(f"  [锁清理] 已终止 {killed} 个 Playwright Chrome 进程")
    except Exception as e:
        print(f"  [锁清理] 查找Playwright进程失败: {e}")


def _clear_profile_locks(account_dir: str) -> None:
    """清理 Chrome profile 锁文件，防止启动时立即崩溃。"""
    import time as _time
    import subprocess as _sp
    _kill_chrome_using_profile(account_dir)
    _time.sleep(10)  # 等待 OS 释放文件句柄（真实Chrome需要更长时间，5秒不够）

    lock_paths = [
        os.path.join(account_dir, "lockfile"),
        os.path.join(account_dir, "SingletonLock"),
        os.path.join(account_dir, "SingletonCookie"),
        os.path.join(account_dir, "SingletonSocket"),
        os.path.join(account_dir, "Default", "LOCK"),
    ]
    for p in lock_paths:
        if not os.path.exists(p):
            continue
        removed = False
        # 尝试1：普通删除
        try:
            os.remove(p)
            print(f"  [锁清理] 已删除: {p}")
            removed = True
        except Exception:
            pass
        if removed:
            continue
        # 尝试2：cmd del /F
        try:
            _sp.run(["cmd", "/c", "del", "/F", "/Q", p],
                    capture_output=True, timeout=5)
            if not os.path.exists(p):
                print(f"  [锁清理] 强制删除(cmd): {p}")
                removed = True
        except Exception:
            pass
        if removed:
            continue
        # 尝试3：用 handle.exe 找占用进程并 kill，再删
        try:
            r = _sp.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 f"Get-Process | Where-Object {{$_.Modules.FileName -like '*{os.path.basename(p)}*'}} | ForEach-Object {{$_.Id}}"],
                capture_output=True, text=True, timeout=10
            )
            for pid_str in r.stdout.splitlines():
                pid_str = pid_str.strip()
                if pid_str.isdigit():
                    _sp.run(["taskkill", "/PID", pid_str, "/F"], capture_output=True, timeout=5)
            _time.sleep(1)
            os.remove(p)
            print(f"  [锁清理] kill占用进程后删除: {p}")
            removed = True
        except Exception:
            pass
        if not removed:
            print(f"  [锁清理] 无法删除，跳过: {p}")


_chrome_procs: dict = {}   # account_dir → subprocess.Popen


def _find_chrome_exe() -> str | None:
    """查找系统安装的真实 Chrome 可执行文件。"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _launch_ctx(p, account_dir: str):
    """启动浏览器并导航到 DeepSeek。
    优先使用真实 Chrome 子进程 + CDP（与 chatgpt_bot.py 完全一致）。
    Google OAuth 必须在真实 Chrome 中才能正常点击。
    """
    import socket
    import urllib.request
    import subprocess as _sp

    _clear_profile_locks(account_dir)
    chrome_exe = _find_chrome_exe()

    if chrome_exe:
        # ── 主策略：真实 Chrome 子进程 + CDP 接入 ─────────────────────────────
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        debug_port = s.getsockname()[1]
        s.close()

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={account_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-crash-restore-bubble",
            "--lang=zh-CN",
            DEEPSEEK_URL,
        ]
        print(f"  [浏览器] 真实 Chrome 启动 port={debug_port}")
        proc = _sp.Popen(cmd)
        _chrome_procs[account_dir] = proc

        # 等待调试端口就绪（最多 60 秒）
        port_ready = False
        for i in range(120):
            if proc.poll() is not None:
                raise RuntimeError("Chrome 进程提前退出，调试端口未就绪")
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{debug_port}/json/version", timeout=1
                )
                port_ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not port_ready:
            proc.terminate()
            raise RuntimeError("Chrome 调试端口 60 秒未就绪")

        # CDP 接入
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
        contexts = browser.contexts
        if contexts:
            ctx = contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        else:
            ctx = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
            page = ctx.new_page()
            page.goto(DEEPSEEK_URL, wait_until="domcontentloaded", timeout=30_000)

        page.add_init_script(_STEALTH_SCRIPT)
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        except ImportError:
            pass
        time.sleep(3)
        return ctx, page

    else:
        # ── Fallback：Playwright Chromium（Google OAuth 可能受限）──────────────
        print("  [浏览器] 未找到真实 Chrome，使用 Playwright Chromium")
        viewport = {
            "width":  1280 + random.randint(-80, 80),
            "height":  900 + random.randint(-40, 40),
        }
        for attempt in range(3):
            try:
                ctx = p.chromium.launch_persistent_context(
                    account_dir,
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                    user_agent=_USER_AGENT,
                    viewport=viewport,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  [浏览器启动] 第{attempt+1}次失败: {e!s:.120}，5秒后重试...")
                    _clear_profile_locks(account_dir)
                    time.sleep(5)
                else:
                    raise
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.add_init_script(_STEALTH_SCRIPT)
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        except ImportError:
            pass
        page.goto(DEEPSEEK_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(3)
        return ctx, page


def open_browser(p, account_dir: str):
    """打开浏览器（persistent context）并确保 DeepSeek session 有效。

    检测到登录页时自动关闭浏览器、重新打开，最多重试 MAX_REOPEN_ATTEMPTS 次。
    全部失败后等待用户手动登录（最多 8 小时）。
    """
    global _last_nav_time
    os.makedirs(account_dir, exist_ok=True)
    storage_file = os.path.join(account_dir, "storage_state.json")

    MAX_REOPEN_ATTEMPTS = 20   # 最多重开 20 次（间隔 30 秒 ≈ 最长等 10 分钟）
    REOPEN_DELAY       = 30    # 每次关闭后等待 30 秒再重开
    # 连续 cookie 注入后仍在登录页的次数上限；超过则判定账号未登录，快速跳过
    MAX_COOKIE_FAIL    = 3

    ctx, page = _launch_ctx(p, account_dir)
    cookie_fail_count = 0  # 连续 cookie 注入无效的次数

    for attempt in range(MAX_REOPEN_ATTEMPTS + 1):
        # ── 注入保存的 cookies（session-only cookie 需要手动注入）────────────
        if _is_logged_out(page) and os.path.exists(storage_file):
            print("  → 从 storage_state.json 恢复 session cookies...")
            try:
                import json as _json
                state = _json.loads(Path(storage_file).read_text(encoding="utf-8"))
                cookies = state.get("cookies", [])
                if cookies:
                    ctx.add_cookies(cookies)
                    page.reload(wait_until="domcontentloaded", timeout=20_000)
                    time.sleep(2)
                    print(f"  → 注入 {len(cookies)} 个 cookie，重新检测")
                    if _is_logged_out(page):
                        cookie_fail_count += 1
                        if cookie_fail_count >= MAX_COOKIE_FAIL:
                            print(f"  ❌ cookie 注入连续 {MAX_COOKIE_FAIL} 次无效，账号未登录，快速跳过")
                            try:
                                ctx.close()
                            except Exception:
                                pass
                            raise AccountNotLoggedIn(
                                f"账号未登录（cookie 无效）：{account_dir}"
                            )
                else:
                    # 无 cookie 可注入 → 账号从未登录
                    cookie_fail_count += 1
                    if cookie_fail_count >= MAX_COOKIE_FAIL:
                        print(f"  ❌ storage_state.json 无有效 cookie，账号未登录，快速跳过")
                        try:
                            ctx.close()
                        except Exception:
                            pass
                        raise AccountNotLoggedIn(
                            f"账号未登录（无 cookie）：{account_dir}"
                        )
            except AccountNotLoggedIn:
                raise
            except Exception as e:
                print(f"  → cookie 注入失败: {e}")

        # ── 已登录，直接结束 ─────────────────────────────────────────────────
        if not _is_logged_out(page):
            cookie_fail_count = 0  # 重置计数
            break

        # ── 尝试 Google OAuth 自动重登 ───────────────────────────────────────
        print(f"  DeepSeek 检测到登录页（第{attempt+1}次）")
        if _auto_relogin_google(page):
            print("  ✅ 自动重登成功")
            break

        # ── 自动重登失败：立刻进入手动登录等待（保留浏览器窗口）────────────
        # 不再循环关闭/重开浏览器（原有的20次重试会导致浏览器一直关闭，
        # 用户无法手动登录）。改为第一次失败就切换到手动等待模式。
        print("  → 自动重登失败，浏览器保持打开，请手动点击「使用 Google 登录」")
        if not _wait_for_manual_login(page):
            try:
                ctx.close()
            except Exception:
                pass
            raise RuntimeError(
                f"账号未登录：{account_dir}\n"
                "请先在浏览器中完成 DeepSeek 登录（点击 Google 按钮）。"
            )

    # 绑定元数据（每次重开 page 都需要重新绑定）
    page._sa_ctx           = ctx
    page._sa_storage_file  = storage_file
    page._sa_account_dir   = account_dir
    page._sa_playwright    = p

    # 保存当前 session（含 session-only cookies）
    try:
        ctx.storage_state(path=storage_file)
        print("  → session 已保存")
    except Exception:
        pass

    _last_nav_time = time.time()
    _wait_for_input(page)
    return ctx, ctx, page, _chrome_procs.get(account_dir)


def _proactive_keepalive(page, interval_secs: int = 2700) -> None:
    """每45分钟主动导航到 DeepSeek 一次，在 token 还未过期时续期 cookie。

    原理：DeepSeek session 约60分钟过期。每45分钟主动刷新，
    此时 Google token 还有效，直接导航即可完成续期，无需走 OAuth popup。
    只在 send_prompt 入口调用，不打断 wait_for_answer 的生成轮询。
    """
    global _last_nav_time
    now = time.time()
    if now - _last_nav_time < interval_secs:
        return

    print("  🔄 主动续期 session（距上次导航已超45分钟）...")
    try:
        page.goto(DEEPSEEK_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(3)
        if _is_logged_out(page):
            # 恰好踩到过期边界，走重登流程
            print("  ⚠️  session 刚好过期，尝试自动重登...")
            if not _auto_relogin_google(page):
                _wait_for_manual_login(page)
        _refresh_session(page)
        _wait_for_input(page)
        _last_nav_time = now
        print("  ✅ session 续期完成")
    except Exception as e:
        print(f"  keepalive 异常: {e}")


def _wait_for_input(page) -> None:
    """等待输入框出现（最多15秒总时长，逐选择器快速扫描）。"""
    deadline = time.time() + 15
    while time.time() < deadline:
        for sel in _INPUT_SELECTORS:
            try:
                if page.locator(sel).first.is_visible(timeout=200):
                    return
            except Exception:
                pass
        time.sleep(0.5)
    # 兜底：等页面基本加载完
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass


def _keepalive_ping(page) -> None:
    """在等待 DeepSeek 生成回复期间，发一个轻量 fetch 请求保持 session 活跃。
    不导航页面，不影响正在进行的生成。
    """
    try:
        page.evaluate("""async () => {
            try {
                await fetch('https://chat.deepseek.com/api/v0/users/current_user',
                    { method: 'GET', credentials: 'include' });
            } catch(e) {}
        }""")
    except Exception:
        pass


def login_account(account: str) -> None:
    account_dir = ACCOUNTS.get(account)
    if not account_dir:
        print(f"错误：账号 {account} 不存在（有效：{list(ACCOUNTS.keys())}）")
        return

    storage_file = os.path.join(account_dir, "storage_state.json")
    if os.path.exists(storage_file):
        print(f"账号 {account} 已有登录状态：{storage_file}")
        yn = input("重新登录？(y/N) ").strip().lower()
        if yn != "y":
            return
        os.remove(storage_file)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：pip install playwright && playwright install chromium")
        return

    with sync_playwright() as p:
        browser, ctx, page = open_browser(p, account_dir)
        print(f"✅ DeepSeek 账号 {account} 登录成功")
        browser.close()


# ── 拟人化辅助 ────────────────────────────────────────────────────────────────

def _jitter(base: float, pct: float = 0.35) -> float:
    """在 base 上叠加 ±pct 的随机抖动，模拟人类反应时间的自然波动。"""
    delta = base * pct
    return base + random.uniform(-delta, delta)


def _human_move(page, element) -> None:
    """移动鼠标：先移到元素附近，停顿，再移到元素中心，模拟人类操作轨迹。"""
    try:
        bb = element.bounding_box()
        if not bb:
            return
        cx = bb["x"] + bb["width"]  / 2
        cy = bb["y"] + bb["height"] / 2
        # 从当前位置随机偏移处移入
        page.mouse.move(cx + random.randint(-120, 120),
                        cy + random.randint(-60,  60))
        time.sleep(_jitter(0.12))
        page.mouse.move(cx + random.randint(-8, 8),
                        cy + random.randint(-4, 4))
        time.sleep(_jitter(0.08))
    except Exception:
        pass


# ── Prompt 发送 ───────────────────────────────────────────────────────────────

_PASTE_CHUNK = 2000

def _dismiss_dialogs(page) -> None:
    """关闭新账号首次登录时可能出现的引导弹窗/同意条款/cookie提示。"""
    dismiss_sels = [
        # 通用关闭/跳过按钮
        'button:has-text("跳过")', 'button:has-text("Skip")',
        'button:has-text("Close")', 'button:has-text("关闭")',
        'button:has-text("我知道了")', 'button:has-text("Got it")',
        'button:has-text("同意")', 'button:has-text("Accept")',
        'button:has-text("继续")', 'button:has-text("Continue")',
        'button:has-text("确定")', 'button:has-text("OK")',
        '[aria-label="Close"]', '[data-testid="close-button"]',
        # DeepSeek 特定
        'button:has-text("开始使用")', 'button:has-text("Get started")',
        '.modal button', '[role="dialog"] button',
    ]
    for sel in dismiss_sels:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=300):
                btn.first.click()
                time.sleep(0.5)
        except Exception:
            pass


def _find_input(page):
    """尝试所有选择器找输入框，最多等待 20 秒；失败时用 JS 自动扫描页面动态找。"""
    for attempt in range(4):
        _dismiss_dialogs(page)  # 每次重试前先清除可能的弹窗
        for sel in _INPUT_SELECTORS:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=300):
                    return loc.first
            except Exception as e:
                if _is_browser_closed_error(e):
                    raise BrowserRestartNeeded(f"_find_input: 浏览器/页面已关闭: {e}")
        if attempt < 3:
            time.sleep(2)

    # 所有硬编码选择器失败 → 用 JS 扫描页面，自动找第一个可见的输入元素
    return _find_input_by_js(page)


def _click_send(page) -> bool:
    """找发送按钮并点击，失败时用 JS 扫描输入框附近的最后一个可见按钮。"""
    for sel in _SEND_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=300):
                _human_move(page, btn.first)
                time.sleep(_jitter(0.20))
                btn.first.click()
                time.sleep(_jitter(1.2))
                return True
        except Exception:
            pass

    # 诊断：打印页面上所有可见 button/role=button 的信息
    try:
        btns_info = page.evaluate("""() => {
            return [...document.querySelectorAll('button, [role=button]')].filter(b => b.offsetParent !== null).map(b => ({
                tag: b.tagName,
                aria: b.getAttribute('aria-label') || '',
                cls: (b.className || '').toString().slice(0, 80),
                type: b.getAttribute('type') || '',
                text: (b.innerText || b.textContent || '').trim().slice(0, 30),
                disabled: b.hasAttribute('disabled') || b.getAttribute('aria-disabled') === 'true',
            }));
        }""")
        print(f"  [诊断] 页面可见按钮({len(btns_info)}个): {btns_info[:6]}")
    except Exception:
        pass

    # JS 兜底：找输入框的最近父容器里最后一个可见且未禁用的按钮
    try:
        clicked = page.evaluate("""() => {
            const inputs = [
                ...document.querySelectorAll('textarea'),
                ...document.querySelectorAll('[contenteditable="true"]'),
                ...document.querySelectorAll('[role="textbox"]'),
            ];
            for (const inp of inputs) {
                if (inp.offsetParent === null) continue;
                // 往上找最近的容器
                let parent = inp.parentElement;
                for (let i = 0; i < 6 && parent; i++, parent = parent.parentElement) {
                    const btns = [...parent.querySelectorAll('button')].filter(
                        b => b.offsetParent !== null && !b.disabled
                    );
                    if (btns.length > 0) {
                        btns[btns.length - 1].click();  // 最后一个按钮通常是发送
                        return true;
                    }
                }
            }
            return false;
        }""")
        if clicked:
            print("  [JS自动] 点击了发送按钮（建议加入 _SEND_SELECTORS）")
            time.sleep(_jitter(1.2))
            return True
    except Exception as e:
        print(f"  [JS发送] 失败: {e}")
    return False


def _find_input_by_js(page):
    """用 JS 动态扫描页面，找到可见输入框并返回 Playwright locator。"""
    try:
        result = page.evaluate("""() => {
            const candidates = [
                ...document.querySelectorAll('textarea'),
                ...document.querySelectorAll('[contenteditable="true"]'),
                ...document.querySelectorAll('[role="textbox"]'),
            ];
            for (const el of candidates) {
                if (el.offsetParent === null || el.disabled) continue;
                const info = {
                    tag: el.tagName.toLowerCase(),
                    id:  el.id || '',
                    ph:  el.getAttribute('placeholder') || '',
                    cls: (el.className || '').trim().split(/\\s+/)[0] || '',
                };
                // 打印诊断信息，方便日后更新硬编码列表
                console.log('[JS自动] 找到元素:', JSON.stringify(info));
                return info;
            }
            // 没找到：打印所有候选元素帮助调试
            const all = [...document.querySelectorAll('textarea,[contenteditable],[role="textbox"]')];
            return {debug: all.map(e => ({
                tag: e.tagName, id: e.id,
                cls: e.className.slice(0,60),
                ph:  e.getAttribute('placeholder') || '',
                vis: e.offsetParent !== null,
            }))};
        }""")

        if not result:
            print("  [JS诊断] 页面上没有找到任何输入元素")
            return None

        if "debug" in result:
            print(f"  [JS诊断] 所有候选元素（均不可见）: {result['debug']}")
            return None

        # 按优先级构造选择器
        tag = result.get("tag", "")
        el_id = result.get("id", "")
        ph  = result.get("ph", "")
        cls = result.get("cls", "")

        if el_id:
            sel = f"#{el_id}"
        elif ph:
            sel = f'{tag}[placeholder="{ph}"]' if tag else f'[placeholder="{ph}"]'
        elif cls:
            sel = f"{tag}.{cls}" if tag else f".{cls}"
        else:
            sel = tag or "textarea"

        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible(timeout=2_000):
            print(f"  [JS自动] 找到输入框: {sel}  (建议加入 _INPUT_SELECTORS)")
            return loc.first

        print(f"  [JS自动] 构造的选择器 {sel!r} 不可见")
    except Exception as e:
        if _is_browser_closed_error(e):
            raise BrowserRestartNeeded(f"_find_input_by_js: 浏览器/页面已关闭: {e}")
        print(f"  [JS自动] 扫描失败: {e}")
    return None


def send_prompt(page, text: str, new_conversation: bool = True) -> None:
    import pyperclip

    # 主动 session 续期（每45分钟导航一次，趁 token 还有效时刷新 cookie）
    _proactive_keepalive(page)

    # 验证码检测：出现时暂停等用户手动完成
    if _has_captcha(page):
        _wait_for_captcha(page)

    # 发送前先检查登录状态：登出后页面无输入框，会被误判为 UI 变化
    if _is_logged_out(page):
        print("  ⚠️  send_prompt：检测到已登出，尝试自动重登...")
        _stop_generation(page)   # 先停止正在生成的内容（如有）
        if _auto_relogin_google(page):
            print("  ✅ 自动重登成功，继续发送")
        else:
            print("  🔄 自动重登失败，触发浏览器重启（等效于手动停止→继续生成）")
            raise BrowserRestartNeeded("send_prompt: Google OAuth 重登失败")

    # 找输入框（带重试）
    box = _find_input(page)

    # 找不到但也没登出 → 可能是页面短暂刷新，再给一次机会
    if box is None and not _is_logged_out(page):
        print("  ⚠️  输入框消失但未登出，等10秒后再找一次...")
        time.sleep(10)
        box = _find_input(page)

    if box is None:
        raise RuntimeError("DeepSeek：找不到输入框，请检查选择器或重新登录")

    # 鼠标移入 → 点击 → 全选清空
    _human_move(page, box)
    time.sleep(_jitter(0.30))
    box.click()
    time.sleep(_jitter(0.45))
    page.keyboard.press("Control+A")
    time.sleep(_jitter(0.12))
    page.keyboard.press("Backspace")
    time.sleep(_jitter(0.35))

    # 分块粘贴（模拟人类逐段贴入长文本）
    # 用 chatgpt_bot 的全局剪贴板锁：--provider both 时两线程共用一个系统剪贴板
    from chatgpt_bot import _clipboard_lock
    chunks = [text[i:i+_PASTE_CHUNK] for i in range(0, len(text), _PASTE_CHUNK)]
    def _pyperclip_copy_retry(text, retries=8, delay=0.3):
        for i in range(retries):
            try:
                pyperclip.copy(text)
                return
            except Exception:
                if i < retries - 1:
                    time.sleep(delay)
        pyperclip.copy(text)  # final attempt, let it raise

    with _clipboard_lock:
        for chunk in chunks:
            _pyperclip_copy_retry(chunk)
            time.sleep(_jitter(0.15))
            page.keyboard.press("Control+V")
            time.sleep(_jitter(0.55))

    # 发送前停顿（等待 DeepSeek 启用发送按钮）
    time.sleep(_jitter(1.5))

    # 找发送按钮 → 最多重试3次（DeepSeek 输入后按钮需短暂延迟才激活）
    sent = False
    for _try in range(3):
        if _click_send(page):
            sent = True
            break
        time.sleep(1.0)

    if not sent:
        # 最后手段：Enter
        print("  ⚠️  未找到发送按钮，尝试 Enter 键")
        page.keyboard.press("Enter")
        time.sleep(_jitter(2.0))


# ── 回复提取 ──────────────────────────────────────────────────────────────────

def get_last_answer(page) -> str:
    """提取 DeepSeek 最后一条助手回复。"""
    result = page.evaluate("""() => {
        // 尝试 data-role="assistant"
        let els = document.querySelectorAll('div[data-role="assistant"]');
        if (!els.length) {
            // 备选：查找含 assistant/bot/reply 关键词的 div
            const candidates = Array.from(document.querySelectorAll('div[class]'))
                .filter(el => {
                    const c = el.className || '';
                    return (c.includes('assistant') || c.includes('bot-') || c.includes('reply'))
                        && !c.includes('input') && !c.includes('user');
                });
            els = candidates;
        }
        if (!els.length) {
            // 最终 fallback：最末一个 .prose 元素
            els = document.querySelectorAll('.prose');
        }
        if (!els.length) return '';

        const el = els[els.length - 1];
        const BLOCK = new Set(['div','p','pre','article','section','li',
                               'h1','h2','h3','h4','h5','h6',
                               'blockquote','tr','td','th','ul','ol']);
        function getText(node) {
            if (node.nodeType === 3) return node.nodeValue;
            if (node.nodeType !== 1) return '';
            const tag = node.tagName.toLowerCase();
            if (['script','style','button','svg'].includes(tag)) return '';
            if (tag === 'br') return '\\n';
            let s = '';
            for (const c of node.childNodes) s += getText(c);
            return BLOCK.has(tag) ? '\\n' + s + '\\n' : s;
        }
        return getText(el).replace(/\\n{3,}/g, '\\n\\n').trim();
    }""")
    if not result:
        return ""
    return _strip_markdown_fences(result)


def _get_answer_via_copy_button(page) -> str:
    """
    点击 DeepSeek 最后一条回复的「复制」按钮，返回剪贴板中的真正 Markdown。
    失败时返回空字符串（调用方应 fallback 到 DOM 文字提取）。
    """
    import pyperclip
    from chatgpt_bot import _clipboard_lock

    def _pyperclip_copy_retry2(text, retries=8, delay=0.3):
        for i in range(retries):
            try:
                pyperclip.copy(text)
                return
            except Exception:
                if i < retries - 1:
                    time.sleep(delay)

    with _clipboard_lock:
        try:
            _pyperclip_copy_retry2("__CLEAR__")
        except Exception:
            pass

        # 滚动到最后一条消息，然后 hover 触发操作栏
        # 优先用 ds-markdown 的直接父容器（DeepSeek 实际 DOM 结构）
        try:
            page.evaluate("""() => {
                // 先把页面滚到底
                window.scrollTo(0, document.body.scrollHeight);
                // 找最后一个 ds-markdown 的父元素，滚入视图
                const dsMds = Array.from(document.querySelectorAll('[class*="ds-markdown"]'));
                if (dsMds.length) {
                    const last = dsMds[dsMds.length - 1];
                    last.scrollIntoView({ block: 'end', behavior: 'instant' });
                }
            }""")
            time.sleep(0.5)
        except Exception:
            pass

        # hover 策略：从 ds-markdown 的父级逐层向上找消息容器
        hovered = False
        for hover_sel in [
            '[class*="ds-markdown"]',          # ds-markdown 本身
            'div[data-role="assistant"]',
            '[class*="assistant"]',
            '.prose',
            '[class*="message"]',
        ]:
            try:
                loc = page.locator(hover_sel).last
                if loc.count() > 0:
                    loc.scroll_into_view_if_needed()
                    loc.hover()
                    time.sleep(1.2)
                    hovered = True
                    break
            except Exception:
                pass

        if not hovered:
            # 最终 fallback：把鼠标移到页面中下部，触发按钮显现
            try:
                vp = page.viewport_size or {"width": 1280, "height": 800}
                page.mouse.move(vp["width"] // 2, int(vp["height"] * 0.75))
                time.sleep(1.0)
            except Exception:
                pass

        # 用 JS 找最后一条 assistant 消息旁的复制按钮
        pos = page.evaluate("""() => {
            function isCopyBtn(btn) {
                const text  = (btn.textContent   || '').trim().toLowerCase();
                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                const title = (btn.getAttribute('title')      || '').toLowerCase();
                const cls   = (btn.getAttribute('class')      || '').toLowerCase();
                return text.includes('复制') || text.includes('copy') ||
                       label.includes('复制') || label.includes('copy') ||
                       title.includes('复制') || title.includes('copy') ||
                       cls.includes('copy');
            }
            function visiblePos(btn) {
                const r = btn.getBoundingClientRect();
                if (r.width > 0 && r.height > 0)
                    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                return null;
            }

            // 找最后一条消息容器：优先 ds-markdown 的祖先（向上6层），再试其他选择器
            let container = null;
            const dsMds = Array.from(document.querySelectorAll('[class*="ds-markdown"]'));
            if (dsMds.length) {
                let el = dsMds[dsMds.length - 1];
                for (let i = 0; i < 6 && el && el !== document.body; i++) {
                    el = el.parentElement;
                    // 找到可能包含按钮的 wrapper（有多个子元素）
                    if (el && el.children.length >= 2) { container = el; break; }
                }
            }
            // 备用选择器
            if (!container) {
                for (const sel of ['div[data-role="assistant"]', '[class*="assistant-message"]', '.prose']) {
                    const els = document.querySelectorAll(sel);
                    if (els.length) { container = els[els.length - 1]; break; }
                }
            }

            if (container) {
                // 策略1: 容器内部（按钮在消息内/操作栏）
                const inner = Array.from(container.querySelectorAll('button')).filter(isCopyBtn);
                if (inner.length) {
                    const p = visiblePos(inner[inner.length - 1]);
                    if (p) return p;
                }
                // 策略2: 逐级向上（最多5层），找操作栏里的复制按钮
                let parent = container;
                for (let i = 0; i < 5; i++) {
                    parent = parent.parentElement;
                    if (!parent) break;
                    const siblings = Array.from(parent.querySelectorAll('button')).filter(isCopyBtn);
                    if (siblings.length) {
                        const p = visiblePos(siblings[siblings.length - 1]);
                        if (p) return p;
                    }
                }
            }

            // 策略3: 页面上所有可见的复制按钮，取垂直位置最靠下的（最后一条消息）
            const all = Array.from(document.querySelectorAll('button')).filter(isCopyBtn);
            if (all.length) {
                let best = null, bestY = -Infinity;
                for (const btn of all) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.y > bestY) {
                        bestY = r.y;
                        best = { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                    }
                }
                if (best) return best;
            }
            // 策略4: 调试——把所有按钮信息挂到 window.__debug_btns
            window.__debug_btns = Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.textContent.trim().slice(0,40),
                label: b.getAttribute('aria-label') || '',
                title: b.getAttribute('title') || '',
                cls: (b.getAttribute('class') || '').slice(0,80),
                visible: b.getBoundingClientRect().width > 0,
            }));
            return null;
        }""")

        # 复制按钮没找到时，打印调试信息帮助分析实际按钮结构
        if not pos:
            try:
                debug_btns = page.evaluate("window.__debug_btns || []")
                visible = [b for b in (debug_btns or []) if b.get('visible')]
                print(f"  [调试] 页面可见按钮({len(visible)}个):")
                for b in visible[:10]:
                    print(f"    text='{b['text']}' label='{b['label']}' title='{b['title']}' cls='{b['cls'][:50]}'")
            except Exception:
                pass

        if pos:
            try:
                page.mouse.click(pos["x"], pos["y"])
                time.sleep(1.5)
                result = pyperclip.paste()
                if result and result != "__CLEAR__" and len(result) > 50:
                    print(f"  ✅ 复制按钮成功（{len(result)} 字符 Markdown）")
                    return result
            except Exception as e:
                print(f"  ⚠️  点击复制按钮失败: {e}")

        print("  ⚠️  未找到 DeepSeek 复制按钮，回退到 DOM 文字提取")
        return ""


def _strip_markdown_fences(text: str) -> str:
    if '```' not in text:
        return text
    parts = []
    in_fence = False
    fence_content: list[str] = []
    outside_content: list[str] = []
    for line in text.splitlines():
        if not in_fence and line.strip().startswith('```'):
            in_fence = True
            chunk = '\n'.join(outside_content).strip()
            if chunk:
                parts.append(chunk)
            outside_content = []
            fence_content = []
        elif in_fence and line.strip() == '```':
            in_fence = False
            chunk = '\n'.join(fence_content).strip()
            if chunk:
                parts.append(chunk)
            fence_content = []
        elif in_fence:
            fence_content.append(line)
        else:
            outside_content.append(line)
    remaining = '\n'.join(fence_content if in_fence else outside_content).strip()
    if remaining:
        parts.append(remaining)
    return '\n'.join(parts).strip()


# ── 生成状态检测 ──────────────────────────────────────────────────────────────

def _is_generating(page) -> bool:
    for sel in _STOP_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=150):
                return True
        except Exception:
            pass
    return False


def _is_quota_exceeded(page) -> bool:
    """检测免费额度耗尽。只检查短提示框，避免误判回复内容。"""
    try:
        result = page.evaluate("""() => {
            const phrases = """ + str(_QUOTA_PHRASES).replace("'", '"') + """;
            const candidates = [
                ...document.querySelectorAll('[role="alert"], [class*="toast"], [class*="error"], [class*="modal"], [class*="dialog"], [class*="notice"], [class*="banner"]'),
            ];
            for (const el of candidates) {
                const t = (el.innerText || '').trim();
                if (t.length < 200 && phrases.some(p => t.toLowerCase().includes(p.toLowerCase()))) {
                    return true;
                }
            }
            return false;
        }""")
        return bool(result)
    except Exception:
        return False


def _is_rate_limited(page) -> bool:
    """检测临时限速（应等待重试，而非切换账号）。
    只检查输入框是否被禁用或页面有错误提示框，避免把回复内容里的词误判为限速。
    """
    try:
        # 只检查短文本的 toast/alert/banner，不检查整个 body（避免误判回复内容）
        result = page.evaluate("""() => {
            const phrases = """ + str(_RATE_LIMIT_PHRASES).replace("'", '"') + """;
            // 只检查可能是提示框的元素（短文本 < 100字符）
            const candidates = [
                ...document.querySelectorAll('[role="alert"], [class*="toast"], [class*="error"], [class*="tip"], [class*="notice"], [class*="banner"]'),
            ];
            for (const el of candidates) {
                const t = (el.innerText || '').trim();
                if (t.length < 100 && phrases.some(p => t.toLowerCase().includes(p.toLowerCase()))) {
                    return true;
                }
            }
            return false;
        }""")
        return bool(result)
    except Exception:
        return False


def _is_content_error(text: str) -> bool:
    if not text or len(text) > 400:
        return False
    tl = text.lower()
    return any(p.lower() in tl for p in _ERROR_PHRASES)


def _stop_generation(page) -> None:
    """如果 DeepSeek 正在生成，点击停止按钮。登出处理前调用，避免留下半截请求。"""
    if not _is_generating(page):
        return
    for sel in _STOP_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=1_000):
                btn.first.click()
                print("  → 已点击「停止生成」按钮")
                time.sleep(2)
                return
        except Exception:
            pass


_CONTINUE_GEN_SELS = [
    'button:has-text("继续生成")',
    'button:has-text("Continue generating")',
    'button:has-text("Continue")',
    '[data-testid*="continue-gen"]',
    'button[class*="continueGen"]',
]


def _try_continue_generation(page) -> bool:
    """重登后点击 DeepSeek 的「继续生成」按钮（如果存在）。返回 True 表示已点击。"""
    for sel in _CONTINUE_GEN_SELS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=3_000):
                btn.first.click()
                print(f"  → 点击了「继续生成」按钮 ({sel})")
                time.sleep(3)
                return True
        except Exception:
            pass
    return False


def _is_server_busy(page) -> bool:
    """检测页面是否出现「服务器繁忙」提示。
    只检查最后一条 AI 回复（短文本）或可见 toast，避免历史消息误判。
    """
    try:
        found = page.evaluate("""(phrases) => {
            // 策略1：只检查最后一条 AI 消息，且必须是短文本（真错误 ≤200 字）
            const msgSels = [
                '.ds-markdown', '[class*="markdown"]',
                '[class*="message-content"]', '[class*="chat-message"]',
                '[class*="reply-content"]', '[class*="response"]',
            ];
            for (const sel of msgSels) {
                const all = document.querySelectorAll(sel);
                if (!all.length) continue;
                const txt = (all[all.length - 1].innerText || '').trim();
                if (txt.length > 0 && txt.length <= 200 &&
                    phrases.some(p => txt.includes(p))) return true;
                break;
            }
            // 策略2：toast / 通知区域（不在对话历史内，且可见）
            const toastSels = [
                '[class*="toast"]', '[class*="snackbar"]', '[class*="notification"]',
                '[role="alert"]', '[class*="error-msg"]', '[class*="error-tip"]',
            ];
            for (const sel of toastSels) {
                for (const el of document.querySelectorAll(sel)) {
                    if (el.offsetParent === null) continue;
                    const txt = (el.innerText || '').trim();
                    if (txt.length <= 300 && phrases.some(p => txt.includes(p))) return true;
                }
            }
            return false;
        }""", _SERVER_BUSY_PHRASES)
        return bool(found)
    except Exception:
        pass
    return False


def _click_server_busy_retry(page) -> bool:
    """点击「服务器繁忙」错误提示旁边的「重试」按钮。"""
    # 先试标准重试选择器
    for sel in [
        'button:has-text("重试")',
        'button:has-text("Retry")',
        '[class*="retry" i] button',
        '[class*="error" i] button',
    ]:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=2_000):
                btn.first.click()
                print(f"  → 点击「重试」按钮 ({sel})")
                time.sleep(3)
                return True
        except Exception:
            pass
    # JS 兜底：找「服务器繁忙」文字附近的按钮
    try:
        clicked = page.evaluate("""(phrases) => {
            for (const phrase of phrases) {
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    if (!node.nodeValue.includes(phrase)) continue;
                    let el = node.parentElement;
                    for (let i = 0; i < 6 && el && el !== document.body; i++) {
                        const btns = [...el.querySelectorAll('button')]
                            .filter(b => b.offsetParent !== null && !b.disabled);
                        if (btns.length) { btns[btns.length - 1].click(); return true; }
                        el = el.parentElement;
                    }
                }
            }
            return false;
        }""", _SERVER_BUSY_PHRASES)
        if clicked:
            print("  → JS 点击了「重试」按钮")
            time.sleep(3)
            return True
    except Exception:
        pass
    return False


def _try_regenerate(page) -> bool:
    """点击 DeepSeek 的重试按钮。"""
    selectors = [
        'button:has-text("重试")',
        'button:has-text("Retry")',
        'button:has-text("重新生成")',
        'button:has-text("Regenerate")',
        '[data-testid*="retry"]',
        '[data-testid*="regenerate"]',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=1500):
                btn.first.click()
                time.sleep(3)
                return True
        except Exception:
            pass
    return False


# ── 等待回复完成 ──────────────────────────────────────────────────────────────

def wait_for_answer(page, timeout: int = 600, stable_secs: int = STABLE_SECS) -> str:
    """
    等待 DeepSeek 回复稳定。
    返回：回复文本 / 'FREE_QUOTA_EXCEEDED' / 'DEEPSEEK_ERROR'
    """
    last = ""
    start = time.time()
    stable_start = None
    regen_attempts = 0
    last_keepalive = time.time()
    KEEPALIVE_INTERVAL = 1200  # 每 20 分钟 ping 一次，防止 session 过期

    # 等待开始生成（最多60秒）
    for _ in range(30):
        if _is_generating(page) or get_last_answer(page):
            break
        time.sleep(2)

    while True:
        # 定期 keepalive：发一个轻量请求保持 DeepSeek session 活跃
        if time.time() - last_keepalive > KEEPALIVE_INTERVAL:
            _keepalive_ping(page)
            last_keepalive = time.time()

        # 服务器繁忙检测：自动点击重试按钮
        if _is_server_busy(page):
            print("  ⚠️  检测到「服务器繁忙」，自动点击重试...")
            if _click_server_busy_retry(page):
                last = ""
                stable_start = None
                time.sleep(5)
                continue
            print("  → 未找到重试按钮，10秒后重试...")
            time.sleep(10)
            continue

        if _is_rate_limited(page):
            return "RATE_LIMITED"

        if _is_quota_exceeded(page):
            return "FREE_QUOTA_EXCEEDED"

        if _has_captcha(page):
            if not _wait_for_captcha(page):
                return ERROR_SIGNAL

        # 检测运行时登出（Google OAuth 约 1 小时后到期）
        if _is_logged_out(page):
            print("\n⚠️  DeepSeek 检测到登出（Google OAuth 约 1 小时会过期）...")
            _stop_generation(page)   # 先停止当前生成，避免留下半截请求
            if _auto_relogin_google(page):
                time.sleep(3)
                # 尝试点击「继续生成」按钮（DeepSeek 有时保留了上次中断的对话）
                if _try_continue_generation(page):
                    print("  ✅ 重登后点击了「继续生成」，等待回复...")
                    last = ""
                    stable_start = None
                    time.sleep(5)
                    continue
                # 没有继续按钮，检查页面是否已有生成内容
                try:
                    existing = get_last_answer(page)
                except Exception:
                    existing = ""
                if existing and len(existing) > 300:
                    print(f"  ✅ 重登后发现已有内容（{len(existing)} 字），等待稳定...")
                    last = existing
                    stable_start = None
                    continue
                # 页面为空（新会话），需要重新发送 Prompt
                print("  🔄 重登后页面无内容，触发浏览器重启以重新发送 Prompt")
                raise BrowserRestartNeeded("wait_for_answer: 重登后无内容，需重发Prompt")
            # 自动重登失败 → 触发浏览器重启（上层捕获 BrowserRestartNeeded）
            print("  🔄 自动重登失败，触发浏览器重启（等效于手动停止→继续生成）")
            raise BrowserRestartNeeded("wait_for_answer: Google OAuth 重登失败")

        try:
            text = get_last_answer(page)
        except Exception as e:
            if _is_browser_closed_error(e):
                raise BrowserRestartNeeded(f"wait_for_answer: 浏览器/页面已关闭: {e}")
            raise
        is_error = _is_content_error(text)

        if is_error:
            err_hint = (text or "未知错误")[:80].strip()
            if regen_attempts < 3:
                regen_attempts += 1
                print(f"  ⚠️  DeepSeek 报错（{err_hint}），第{regen_attempts}次重试...")
                if _try_regenerate(page):
                    last = ""
                    stable_start = None
                    time.sleep(5)
                    continue
                time.sleep(10)
                continue
            print(f"  ❌ DeepSeek 持续报错（{err_hint}），放弃")
            return ERROR_SIGNAL

        if not text:
            time.sleep(2)
            continue

        if text == last:
            if stable_start is None:
                stable_start = time.time()
            elif time.time() - stable_start > stable_secs:
                if _is_generating(page):
                    stable_start = None
                else:
                    # 回复已稳定——立刻刷新 session cookie，防止 DeepSeek 轮换 token 后踢出
                    _refresh_session(page)
                    md = _get_answer_via_copy_button(page)
                    if md:
                        return md
                    md2 = _get_last_answer_html_md(page)
                    return md2 if md2 else text
        else:
            last = text
            stable_start = None

        if time.time() - start > timeout:
            _refresh_session(page)
            md = _get_answer_via_copy_button(page)
            if md:
                return md
            md2 = _get_last_answer_html_md(page)
            return md2 if md2 else last
        time.sleep(2)


def _get_last_answer_html_md(page) -> str:
    """innerHTML → markdownify 提取最后一条 assistant 回复，比 getText() 保留完整 markdown 格式。"""
    _DS_TOPS = """Array.from(document.querySelectorAll('[class*="ds-markdown"]')).filter(e=>{
        let p=e.parentElement;
        while(p&&p!==document.body){
            if((p.getAttribute('class')||'').includes('ds-markdown'))return false;
            p=p.parentElement;
        }
        return true;
    })"""
    try:
        html = page.evaluate(f"""() => {{
            const els = {_DS_TOPS};
            return els.length ? els[els.length - 1].innerHTML : null;
        }}""")
        if not html:
            return ""
        try:
            import markdownify
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup.find_all("button"):
                    tag.decompose()
                # 去掉 SVG（mermaid 渲染图）和 style，避免带入 CSS 垃圾
                for tag in soup.find_all("svg"):
                    tag.decompose()
                for tag in soup.find_all("style"):
                    tag.decompose()
                for tag in soup.find_all(True):
                    cls = " ".join(tag.get("class") or [])
                    if any(k in cls.lower() for k in ("code-header", "copy-btn", "code-copy", "code-action")):
                        tag.decompose()
                html = str(soup)
            except ImportError:
                pass
            md = markdownify.markdownify(html, heading_style="ATX", bullets="-",
                                         strip=["script", "style"]).strip()
            import re as _re
            md = _re.sub(r'\n[a-z]+\n\n复制\n\n下载\n', '\n', md)
            md = _re.sub(r'\n复制\n\n下载\n', '\n', md)
            # 去掉 mermaid tab 标签和残留 CSS
            md = _re.sub(r'\n(图表|代码|下载|全屏)\n', '\n', md)
            md = _re.sub(r'\n\.[a-z]{4,}\{[^\n]*', '', md)
            md = _re.sub(r'\n#mermaid-svg-\d+\{[^\n]*', '', md)
            md = _re.sub(r'\n{3,}', '\n\n', md)
            if len(md) > 50:
                print(f"  ✅ innerHTML→markdownify 提取（{len(md)} 字符）")
                return md
        except ImportError:
            pass
    except Exception:
        pass
    return ""


def _refresh_session(page) -> None:
    """把浏览器最新 cookie 保存回 storage_state.json，防止 token 轮换后被踢出。"""
    try:
        ctx  = getattr(page, "_sa_ctx",          None)
        path = getattr(page, "_sa_storage_file", None)
        if ctx and path:
            ctx.storage_state(path=path)
    except Exception:
        pass


# ── 新对话 ────────────────────────────────────────────────────────────────────

def new_conversation(page) -> None:
    """打开新对话（每次均完整导航到首页，顺带触发 Google OAuth token 刷新）。"""
    global _last_nav_time
    page.goto(DEEPSEEK_URL)
    time.sleep(2)
    _refresh_session(page)
    _wait_for_input(page)
    _last_nav_time = time.time()  # 导航成功，重置续期计时器


# ── 高层复用：write_section / run_chapter 由 chatgpt_bot 提供 ──────────────────

def write_section(page, chapter: int, section: int, cfg: dict,
                  skip_review: bool = False) -> str | None:
    from chatgpt_bot import write_section as _ws
    return _ws(page, chapter, section, cfg, skip_review=skip_review, bot=_this())


def run_chapter(chapter: int, cfg: dict, account: str = "1",
                sections=None, skip_review: bool = False):
    from chatgpt_bot import run_chapter as _rc
    return _rc(chapter, cfg, account=account, sections=sections,
               skip_review=skip_review, provider="deepseek")


def _this():
    import deepseek_bot
    return deepseek_bot


# ── 高层接口：单次对话（圣经流水线专用） ─────────────────────────────────────

def send_and_collect(
    prompt: str,
    account: str = "1",
    max_continues: int = 8,
    timeout_per_turn: int = 300,
    continue_signal: str = "继续",
) -> str:
    """
    打开 DeepSeek 浏览器 → 新建对话 → 发送 prompt → 收集完整回复（自动处理"继续"）。

    适用于圣经流水线的 Blueprint / Chapter Design / Writing 等大段输出任务。
    与 chatgpt_bot.send_and_collect 接口相同，方便在 bible_workflow.py 中统一调用。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：请安装 playwright：pip install playwright && playwright install chromium")
        return ""

    account_dir = ACCOUNTS.get(account, list(ACCOUNTS.values())[0])

    def _kill(proc):
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    with sync_playwright() as p:
        try:
            browser, ctx, page, chrome_proc = open_browser(p, account_dir)
        except Exception as e:
            print(f"❌ 打开 DeepSeek 浏览器失败：{e}")
            return ""

        try:
            new_conversation(page)
            time.sleep(2)

            print(f"  📤 发送提示词（{len(prompt):,} 字符）...")
            send_prompt(page, prompt)

            parts: list[str] = []
            for turn in range(max_continues + 1):
                print(f"  ⏳ 等待 DeepSeek 回复（turn {turn + 1}）...")
                answer = wait_for_answer(page, timeout=timeout_per_turn)

                if answer == ERROR_SIGNAL:
                    print(f"  ⚠️  DeepSeek 返回错误信号")
                    break

                parts.append(answer.strip())
                print(f"  ✅ Turn {turn + 1}：{len(answer):,} 字符")

                # 简单截断检测：回复末尾没有句号/结束标记视为截断
                last_char = answer.rstrip()[-1] if answer.rstrip() else ""
                if last_char not in "。.!！？?」』）)】\n" or turn == 0 and len(answer) > 1000:
                    pass  # 继续检查
                else:
                    break  # 看起来结束了

                if turn >= max_continues:
                    print(f"  ⚠️  已达最大「继续」次数（{max_continues}），停止")
                    break

                print(f"  ▶  自动发送「{continue_signal}」...")
                send_prompt(page, continue_signal)

            result = "\n\n".join(parts)
            return result

        except Exception as e:
            print(f"❌ send_and_collect 出错：{e}")
            return ""
        finally:
            try:
                browser.close()
            except Exception:
                pass
            _kill(chrome_proc)
