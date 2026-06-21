"""
chatgpt_bot.py
--------------
Playwright 自动化：发送写书 Prompt 到 ChatGPT，收集长文本回复。

与 lesson_builder_bot.py 的区别：
  - 输出是 HTML 长文本，不是 JSON 数组
  - 需要检测截断并自动追问"继续"
  - 每个 Section 可能需要多轮对话才能完成

v2 新增：
  - Review → Revise 循环（write_section 完成后自动审查+修订）
  - 章节完成后自动提取章节记忆（在关闭浏览器之前）
  - skip_review=True 可跳过以上两步（快速模式）
"""
from __future__ import annotations

import os
import re
import sys
import time
import random
import threading
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BASE_DIR = Path(__file__).parent


class SessionExpired(RuntimeError):
    """账号 session 已过期（ChatGPT 显示登录页），task_runner 捕获后自动切换到下一个账号。"""


# ── 剪贴板互斥锁（--provider both 时两线程共用一个系统剪贴板，必须串行） ──────
_clipboard_lock = threading.Lock()

# ChatGPT 账号存储目录
# 优先使用环境变量 STUDYATHENA_ACCOUNTS_DIR（GUI 打包版会设置这个）
# 否则用 AppData\Roaming\StudyAthena\accounts（所有 Windows 电脑都有 AppData）
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
ACCOUNTS = _sys_accounts or {
    "1": str(BOT_DIR / "account_chatgpt1"),
    "2": str(BOT_DIR / "account_chatgpt2"),
    "3": str(BOT_DIR / "account_chatgpt3"),
    "4": str(BOT_DIR / "account_chatgpt4"),
}
CHATGPT_URL = "https://chatgpt.com"


def login_account(account: str) -> None:
    """打开浏览器，手动登录指定账号并保存 storage_state。"""
    account_dir = ACCOUNTS.get(account)
    if not account_dir:
        print(f"错误：账号 {account} 不存在（有效：{list(ACCOUNTS.keys())}）")
        return

    storage_file = os.path.join(account_dir, "storage_state.json")
    if os.path.exists(storage_file):
        print(f"账号 {account} 已有登录状态：{storage_file}")
        yn = input("重新登录？(y/N) ").strip().lower()
        if yn != "y":
            print("跳过")
            return
        os.remove(storage_file)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：pip install playwright && playwright install chromium")
        return

    with sync_playwright() as p:
        browser, ctx, page, _proc = open_browser(p, account_dir)
        print(f"✅ 账号 {account} 登录成功，已保存登录状态")
        browser.close()
        if _proc:
            try: _proc.terminate()
            except Exception: pass

# 每个 Section 的最少字数（HTML 去标签后）
MIN_SECTION_CHARS = {
    1: 1500,
    2: 2000,
    3: 2500,
    4: 1800,
    5: 3000,
    6: 1800,
}

MAX_CONTINUE_ROUNDS = 4   # 最多追问几轮"继续"
MAX_SEND_RETRIES    = 3   # ChatGPT 报错时最多重新发 Prompt 几次
STABLE_SECS         = 5   # 回复稳定多少秒认为完成

# ── 输入框选择器：兼容 ChatGPT 2024-2026 多个 UI 版本 ──────────────────────────
# 2024-2025: id="prompt-textarea"（div contenteditable）
# 2026: id 可能变更，但 data-testid / role / ProseMirror class 更稳定
_INPUT_SEL = (
    "#prompt-textarea, "
    "[data-testid='prompt-textarea'], "
    "div[contenteditable='true'][role='textbox'], "
    "div.ProseMirror[contenteditable='true'], "
    "textarea#prompt-textarea, "
    "div#prompt-textarea"
)


# ── Playwright 浏览器操作 ─────────────────────────────────────────────────────

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
Object.defineProperty(navigator, 'plugins',    { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages',  { get: () => ['zh-CN','zh','en-US','en'] });
Object.defineProperty(navigator, 'platform',   { get: () => 'Win32' });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
""".strip()

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _jitter(base: float, pct: float = 0.35) -> float:
    delta = base * pct
    return base + random.uniform(-delta, delta)


def _human_move(page, element) -> None:
    try:
        bb = element.bounding_box()
        if not bb:
            return
        cx = bb["x"] + bb["width"]  / 2
        cy = bb["y"] + bb["height"] / 2
        page.mouse.move(cx + random.randint(-120, 120),
                        cy + random.randint(-60,  60))
        time.sleep(_jitter(0.12))
        page.mouse.move(cx + random.randint(-8, 8),
                        cy + random.randint(-4, 4))
        time.sleep(_jitter(0.08))
    except Exception:
        pass


def _suppress_crash_restore(account_dir: str) -> None:
    """修改 Chrome Preferences，使 Chrome 认为上次正常退出，避免弹出「浏览器没有正确关闭」提示。"""
    prefs_file = os.path.join(account_dir, "Default", "Preferences")
    if not os.path.exists(prefs_file):
        return
    try:
        import json as _json
        with open(prefs_file, "r", encoding="utf-8") as f:
            prefs = _json.load(f)
        profile = prefs.setdefault("profile", {})
        profile["exit_type"] = "Normal"
        profile["exited_cleanly"] = True
        with open(prefs_file, "w", encoding="utf-8") as f:
            _json.dump(prefs, f, ensure_ascii=False)
    except Exception as e:
        print(f"  [prefs] 修改 Chrome Preferences 失败（{e}），已跳过")


def _clear_chatgpt_locks(account_dir: str) -> None:
    """清理 Chrome profile 锁文件，并 kill 占用该 profile 的 Chrome 进程。"""
    import subprocess as _sp
    # kill：Playwright 内置 chromium 进程 OR 使用该 account_dir 的真实 Chrome 进程
    safe_dir = account_dir.replace("'", "''")  # PowerShell 单引号转义；反斜杠无需转义（-like 不把 \ 当特殊字符）
    ps_script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "    $_.CommandLine -like '*ms-playwright*chrome*' -or "
        f"   ($_.CommandLine -like '*chrome*' -and $_.CommandLine -like '*{safe_dir}*')"
        " } | ForEach-Object { $_.ProcessId }"
    )
    try:
        result = _sp.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                try:
                    _sp.run(["taskkill", "/PID", line, "/F"], capture_output=True, timeout=5)
                except Exception:
                    pass
    except Exception:
        pass
    time.sleep(1)
    for lock in [
        os.path.join(account_dir, "lockfile"),
        os.path.join(account_dir, "SingletonLock"),
        os.path.join(account_dir, "Default", "LOCK"),
    ]:
        if os.path.exists(lock):
            try:
                os.remove(lock)
            except Exception:
                pass


def _find_chrome_exe() -> str | None:
    """查找系统安装的真实 Chrome 可执行文件。"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",  # Edge 作为 fallback
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def open_browser(p, account_dir: str):
    """打开 ChatGPT 浏览器。
    策略：先以子进程启动真实 Chrome（无任何 Playwright/自动化标志），
    等待 CF Turnstile 在干净浏览器中自然通过，再通过 CDP 接入 Playwright。
    CF 的 JS 挑战只在页面加载时运行一次；Playwright 接入后不会触发重新挑战。
    返回 (browser, ctx, page)。
    """
    import json as _json
    import socket
    import urllib.request
    import subprocess as _sp

    storage_file = os.path.join(account_dir, "storage_state.json")
    os.makedirs(account_dir, exist_ok=True)
    _clear_chatgpt_locks(account_dir)
    _suppress_crash_restore(account_dir)   # 防止 Chrome 弹出"没有正确关闭"提示

    viewport = {"width": 1280 + random.randint(-80, 80), "height": 900 + random.randint(-40, 40)}
    chrome_exe = _find_chrome_exe()

    if not chrome_exe:
        # ── Fallback: Playwright Chromium（没有真实 Chrome 时）─────────────────
        print("  [浏览器] 未找到 Chrome，使用 Playwright Chromium（可能被 CF 拦截）")
        ctx = p.chromium.launch_persistent_context(
            account_dir,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
            ignore_default_args=["--enable-automation", "--no-sandbox"],
            user_agent=_USER_AGENT,
            viewport=viewport,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.add_init_script(_STEALTH_SCRIPT)
        page._sa_account_dir = account_dir
        page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30_000)
        _wait_for_input(page)
        try:
            ctx.storage_state(path=storage_file)
        except Exception:
            pass
        return ctx, ctx, page, None

    # ── 主策略：子进程 Chrome → 等待 CF → CDP 接入 ───────────────────────────
    # 寻找空闲调试端口
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    debug_port = s.getsockname()[1]
    s.close()

    chrome_cmd = [
        chrome_exe,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={account_dir}",
        f"--window-size={viewport['width']},{viewport['height']}",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-crash-restore-bubble",
        "--lang=zh-CN",
        CHATGPT_URL,  # 直接打开 chatgpt.com（使用 profile 里已有的 session cookies）
    ]
    print(f"  [浏览器] 子进程启动真实 Chrome (port={debug_port})")
    proc = _sp.Popen(chrome_cmd)

    # 等待调试端口就绪（最多 60 秒）
    port_ready = False
    for i in range(120):
        # 检查 Chrome 进程是否提前退出
        ret = proc.poll()
        if ret is not None:
            raise RuntimeError(f"Chrome 进程提前退出（returncode={ret}），调试端口未就绪")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/version", timeout=1)
            port_ready = True
            break
        except Exception:
            if i % 10 == 0:
                print(f"  [浏览器] 等待 Chrome 端口就绪... ({i//2}s)")
            time.sleep(0.5)
    if not port_ready:
        proc.terminate()
        raise RuntimeError("Chrome 调试端口未就绪（启动超时 60s）")

    # ── 通过调试 API（非 CDP）监控 CF 通过状态 ────────────────────────────────
    # Chrome 以无自动化标志启动，CF 的 JS 挑战应在真实浏览器中自然通过
    print("  [CF] 等待 CF 在干净 Chrome 中自然通过（不使用 Playwright CDP）...")
    print("  [CF] 如有验证框出现，请在浏览器窗口手动点击")
    cf_deadline = time.time() + 600  # 最多等 10 分钟
    last_report = time.time()
    cf_passed = False

    while time.time() < cf_deadline:
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{debug_port}/json", timeout=2
            )
            tabs = _json.loads(resp.read().decode())
            for tab in tabs:
                tab_url = tab.get("url", "")
                tab_title = tab.get("title", "")
                _cf_kws = ("请稍候", "Just a moment", "Checking your browser",
                           "しばらくお待ちください",  # 日文
                           "잠시만 기다려",            # 韩文
                           "Por favor espere",          # 西班牙文
                           "Veuillez patienter",        # 法文
                           "Bitte warten",              # 德文
                           )
                _login_url_kws  = ("/auth/login", "/auth/", "sign_in", "openai.com/")
                _login_ttl_kws  = ("Log in", "Sign in", "登录", "Login")
                _is_login_url   = any(kw in tab_url   for kw in _login_url_kws)
                _is_login_title = any(kw in tab_title for kw in _login_ttl_kws)
                if "chatgpt.com" in tab_url and (_is_login_url or _is_login_title):
                    # 账号 session 已过期，直接抛异常，跳过手动登录等待
                    raise SessionExpired(
                        f"账号 session 已过期，请在「账号管理」中重新登录（URL: {tab_url[:60]}）"
                    )
                if (
                    "chatgpt.com" in tab_url
                    and not any(kw in tab_title for kw in _cf_kws)
                    and not _is_login_url
                    and not _is_login_title
                    and tab_title.strip()
                ):
                    cf_passed = True
                    print(f"  ✅ [CF] 挑战已通过（title='{tab_title[:50]}'）")
                    break
        except Exception:
            pass

        if cf_passed:
            break

        if time.time() - last_report > 30:
            rem = int(cf_deadline - time.time())
            print(f"  [CF] 仍在等待...剩余 {rem}s；如有验证框请点击")
            last_report = time.time()
        time.sleep(3)

    if not cf_passed:
        print("  ⚠️  CF 等待超时（10分钟），尝试继续连接...")

    # ── CF 已通过，现在才接入 Playwright CDP ──────────────────────────────────
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
    contexts = browser.contexts
    if contexts:
        ctx = contexts[0]
        pages_list = ctx.pages
        page = pages_list[0] if pages_list else ctx.new_page()
    else:
        ctx = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
        page = ctx.new_page()
        page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30_000)

    # 对后续导航注入 stealth（当前页面已加载完毕，init_script 对其无效但对新页有效）
    page.add_init_script(_STEALTH_SCRIPT)
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except ImportError:
        pass

    # 限制所有 page 操作（evaluate/wait_for_selector 等）的默认超时为 20 秒
    # 防止 page.evaluate() 无限阻塞（CDP 断开或页面冻结时）
    page.set_default_timeout(20_000)

    page._sa_account_dir = account_dir

    # 等待输入框（CF 已过，chatgpt.com 应该直接就绪）
    try:
        page.wait_for_selector(_INPUT_SEL, timeout=20_000)
        print("  ✅ ChatGPT 输入框就绪")
    except Exception:
        _wait_for_input(page)

    # 保存 session（Chrome 的 cookies 同步到 storage_state.json 供下次使用）
    try:
        ctx.storage_state(path=storage_file)
    except Exception:
        pass

    return browser, ctx, page, proc


def _detect_captcha(page) -> bool:
    """检测页面上是否存在 CAPTCHA / 人机验证挑战。"""
    try:
        found = page.evaluate("""() => {
            // Cloudflare Turnstile / Challenge
            if (document.querySelector('iframe[src*="challenges.cloudflare.com"]')) return true;
            if (document.querySelector('#challenge-running, #challenge-stage, #cf-challenge-running')) return true;
            if (document.querySelector('[class*="cf-challenge"]')) return true;
            // OpenAI / generic robot verification
            const bodyText = document.body ? document.body.innerText.toLowerCase() : '';
            const captchaKeywords = [
                'verify you are human', 'prove you are not a robot',
                '证明您不是机器人', '证明你不是机器人', '验证您是人类',
                'i am not a robot', 'robot verification',
                'captcha', 'cloudflare',
            ];
            for (const kw of captchaKeywords) {
                if (bodyText.includes(kw)) return true;
            }
            // Checkbox that says "I'm not a robot"
            if (document.querySelector('input[type="checkbox"][id*="robot"]')) return true;
            if (document.querySelector('.recaptcha-checkbox')) return true;
            return false;
        }""")
        return bool(found)
    except Exception:
        return False


def _wait_for_captcha_solve(page, max_wait: int = 300) -> bool:
    """
    提示用户手动完成 CAPTCHA，等待直到输入框出现。
    返回 True 表示成功恢复，False 表示超时。
    """
    print("\n  ⚠️  检测到人机验证 (CAPTCHA)！")
    print("  ─────────────────────────────────────────────────")
    print("  请在打开的浏览器窗口中完成验证（勾选「我不是机器人」或按要求操作）")
    print("  注意：如果验证后仍反复弹出，尝试刷新页面或重新打开浏览器")
    print(f"  程序将等待最多 {max_wait // 60} 分钟...")
    print("  ─────────────────────────────────────────────────")

    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            page.wait_for_selector(_INPUT_SEL, timeout=5_000)
            print("  ✅ CAPTCHA 已完成，继续运行")
            # 保存新 session
            account_dir = getattr(page, "_sa_account_dir", None)
            if account_dir:
                storage_file = os.path.join(account_dir, "storage_state.json")
                try:
                    page.context.storage_state(path=storage_file)
                    print("  ✅ 新 session 已保存")
                except Exception:
                    pass
            return True
        except Exception:
            pass
        remaining = int(deadline - time.time())
        if remaining % 30 == 0 and remaining > 0:
            print(f"  [CAPTCHA] 还在等待验证完成…剩余 {remaining}s")
        time.sleep(3)
    print("  ❌ CAPTCHA 等待超时，程序将跳过本次任务")
    return False


def _wait_for_input(page):
    """等待 ChatGPT 输入框出现，自动检测登录页/CAPTCHA 并等待用户处理（最多5分钟）。"""
    # 快速尝试：已登录时输入框很快出现
    try:
        page.wait_for_selector(_INPUT_SEL, timeout=15_000)
        return
    except Exception:
        pass

    # ── Cloudflare "请稍候…" 挑战检测（自动等待 CF JS 挑战完成）────────────────
    # CF 挑战通常 3-10 秒后自动完成，URL 里带有 __cf_chl_rt_tk 参数
    try:
        cf_url = page.url or ""
        cf_title = page.evaluate("() => document.title") or ""
    except Exception:
        cf_url = cf_title = ""
    _is_cf = ("__cf_chl" in cf_url
               or any(kw in cf_title for kw in ("请稍候", "Just a moment", "Checking your browser")))
    if _is_cf:
        print(f"\n  ⚠️  检测到 Cloudflare 挑战页！")
        print(f"  ─────────────────────────────────────────────────────────────")
        print(f"  请查看已打开的浏览器窗口。")
        print(f"  CF 正在自动验证（3-10秒通常自动通过）；")
        print(f"  若 10 秒内未跳转，请手动点击「验证您是人类」复选框。")
        print(f"  程序将等待最多 8 分钟，验证通过后自动继续。")
        print(f"  ─────────────────────────────────────────────────────────────")
        cf_deadline = time.time() + 480  # 8分钟
        last_report = time.time()
        while time.time() < cf_deadline:
            time.sleep(3)
            still_cf = True
            try:
                cur_url = page.url or ""
                cur_title = page.evaluate("() => document.title") or ""
                still_cf = ("__cf_chl" in cur_url
                             or any(kw in cur_title for kw in ("请稍候", "Just a moment", "Checking your browser")))
            except Exception as _ex:
                if "Target crashed" in str(_ex) or "Target closed" in str(_ex):
                    raise RuntimeError(f"ChatGPT 浏览器已崩溃，请重启: {_ex}")
                # 页面在导航中 → 暂时未知，继续等待
                still_cf = True
            if not still_cf:
                print(f"  ✅ [Cloudflare] CF 挑战已通过，继续...")
                break
            if time.time() - last_report > 30:
                rem = int(cf_deadline - time.time())
                print(f"  [Cloudflare] 仍在等待挑战通过，剩余 {rem}s...")
                last_report = time.time()
        # CF 过后先等输入框（快速路径）
        try:
            page.wait_for_selector(_INPUT_SEL, timeout=10_000)
            return
        except Exception:
            pass
        # 若输入框未出现，可能仍有 CAPTCHA checkbox 需要手动点击
        if _detect_captcha(page):
            if not _wait_for_captcha_solve(page, max_wait=300):
                raise RuntimeError("ChatGPT CAPTCHA 验证超时，请手动完成后重启")
            return

    # 检测 CAPTCHA（优先于登录页检测，因为 CAPTCHA 也在 chatgpt.com 域名下）
    if _detect_captcha(page):
        if not _wait_for_captcha_solve(page, max_wait=300):
            raise RuntimeError("ChatGPT CAPTCHA 验证超时，请手动完成后重启")
        return

    # 检测是否跳到了登录/验证页
    url = ""
    try:
        url = page.url or ""
    except Exception:
        pass

    # 打印当前URL和页面摘要，帮助诊断卡住原因
    print(f"  [诊断] 页面URL: {url[:80]}")
    try:
        dom_summary = page.evaluate(
            "() => {"
            "  var title = document.title || '';"
            "  var inputs = document.querySelectorAll('input,textarea').length;"
            "  var ce = document.querySelectorAll('[contenteditable]').length;"
            "  var roles = Array.from(document.querySelectorAll('[role]')).map(function(e){return e.getAttribute('role');}).join(',').slice(0,80);"
            "  var ids = Array.from(document.querySelectorAll('[id]')).filter(function(e){return e.id && e.id.length<40;}).map(function(e){return e.id;}).join(',').slice(0,120);"
            "  return 'title=' + title.slice(0,40) + ' inputs=' + inputs + ' ce=' + ce + ' roles=' + roles + ' ids=' + ids;"
            "}"
        )
        print(f"  [诊断] {dom_summary}")
    except Exception as _e:
        print(f"  [诊断] DOM评估失败: {_e}")

    is_login_page = any(kw in url for kw in ("login", "auth", "account", "signin", "openai.com/"))
    if not is_login_page:
        # 不是登录页，可能是慢加载，再等 90 秒，期间持续检测 CAPTCHA
        deadline = time.time() + 90
        check_n = 0
        while time.time() < deadline:
            try:
                page.wait_for_selector(_INPUT_SEL, timeout=8_000)
                return
            except Exception as _e:
                if "Target crashed" in str(_e) or "Target closed" in str(_e):
                    raise RuntimeError(f"ChatGPT 浏览器已崩溃: {_e}")
            check_n += 1
            if check_n % 3 == 0:
                try:
                    cur_url = page.url or ""
                    print(f"  [等待输入框] {int(time.time()-deadline+90)}s, url={cur_url[:60]}")
                except Exception:
                    pass
            if _detect_captcha(page):
                if not _wait_for_captcha_solve(page, max_wait=300):
                    raise RuntimeError("ChatGPT CAPTCHA 验证超时")
                return
        raise RuntimeError("ChatGPT 输入框未出现（等待超时）")

    # 是登录页 ─ session 已过期，立即抛出异常让 task_runner 切换到下一个账号
    print(f"\n  ⚠️  ChatGPT session 已过期（{url[:60]}）")
    print("  ↪ 请在「👥 账号管理」中点击对应账号的「🔑 登录」重新登录后再运行任务。")
    raise SessionExpired(
        f"账号 session 已过期，请重新登录（URL: {url[:60]}）"
    )


_PASTE_CHUNK = 2500   # 每次粘贴的最大字符数，防止 ChatGPT 自动转为文件附件

def _remove_file_attachments(page) -> bool:
    """检测并移除 ChatGPT 自动转换的文件附件，返回 True 表示发现并处理了附件。"""
    found = False
    for sel in [
        'button[aria-label="Remove file"]',
        'button[aria-label="Remove attachment"]',
        '[data-testid*="remove"][data-testid*="file"]',
        '[data-testid*="remove"][data-testid*="attach"]',
        'button[class*="remove"]:near([class*="attachment"])',
    ]:
        try:
            btns = page.locator(sel)
            if btns.count() > 0:
                print(f"  ⚠️  检测到文件附件（ChatGPT 自动转换），正在移除...")
                for i in range(btns.count()):
                    btns.nth(i).click()
                    time.sleep(0.5)
                found = True
                time.sleep(1)
        except Exception:
            pass
    return found


def _dismiss_blocking_modals(page) -> bool:
    """检测并关闭阻挡输入的弹窗（rate-limit / upgrade 等）。
    返回 True 表示检测到并尝试关闭了弹窗。"""
    modal_selectors = [
        '[data-testid="modal-conversation-history-rate-limit"]',
        '#modal-conversation-history-rate-limit',
        '[role="dialog"]',
    ]
    found = False
    for sel in modal_selectors:
        try:
            if page.locator(sel).count() > 0:
                found = True
                print(f"  ⚠️  检测到阻挡弹窗: {sel}，尝试关闭...")
                # 尝试点击弹窗内的关闭/OK/确认按钮
                for btn_sel in [
                    f'{sel} button[aria-label="Close"]',
                    f'{sel} button[aria-label="关闭"]',
                    f'{sel} button:has-text("OK")',
                    f'{sel} button:has-text("确定")',
                    f'{sel} button:has-text("Close")',
                    f'{sel} button:has-text("关闭")',
                    f'{sel} button:has-text("Got it")',
                    f'{sel} button:has-text("知道了")',
                    f'{sel} button:last-child',
                ]:
                    try:
                        btn = page.locator(btn_sel)
                        if btn.count() > 0:
                            btn.first.click(timeout=3_000)
                            time.sleep(0.5)
                            print(f"    ✅ 已点击关闭按钮: {btn_sel}")
                            break
                    except Exception:
                        pass
                else:
                    # 按 Escape 关闭
                    page.keyboard.press("Escape")
                    time.sleep(0.5)
                    print("    ✅ 已按 Escape 关闭弹窗")
                break
        except Exception:
            pass
    return found


def _new_conversation(page) -> None:
    """导航到 ChatGPT 首页，开一个干净的新对话，等待输入框出现。
    每次发 prompt 前调用，防止旧对话状态（太长 / 报错 / 加载中）干扰。
    遇到 CAPTCHA 时提示用户手动完成后继续。
    """
    try:
        current = page.url or ""
    except Exception:
        current = ""

    def _goto_chatgpt():
        try:
            page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            err_str = str(e)
            if "Timeout" in err_str and "chatgpt.com" in (page.url or ""):
                print("  ⚠️  page.goto 超时但已在 chatgpt.com，继续...")
            elif any(kw in err_str.lower() for kw in ("closed", "target", "context")):
                # CDP 连接断开（真实 Chrome 子进程重新加载时常见），直接 raise 给上层重试
                raise RuntimeError(f"CDP 连接断开（page.goto）：{err_str[:120]}")
            else:
                raise

    # 已经在 chatgpt.com 且输入框可能就绪，先快速检查一次——避免不必要的 goto
    # 这对 CDP 子进程模式尤其重要：open_browser 完成后 page 已就绪，再 goto 会断连
    if "chatgpt.com" in current:
        try:
            page.wait_for_selector(_INPUT_SEL, timeout=8_000)
            return
        except Exception:
            pass  # 输入框未出现，继续走完整流程

    # 只要不是刚打开的首页就重新导航
    if current.rstrip("/") not in ("https://chatgpt.com", "https://chat.openai.com"):
        _goto_chatgpt()
        time.sleep(1)

    # 等待输入框，期间检测 CAPTCHA
    for attempt in range(3):
        try:
            page.wait_for_selector(_INPUT_SEL, timeout=15_000)
            return
        except Exception:
            pass

        if _detect_captcha(page):
            if not _wait_for_captcha_solve(page, max_wait=300):
                raise RuntimeError("ChatGPT CAPTCHA 验证超时，无法发送 Prompt")
            return

        # 不是 CAPTCHA：重新导航后再试
        if attempt < 2:
            print(f"  ⚠️  输入框未出现（第{attempt+1}次），重新导航...")
            _goto_chatgpt()
            time.sleep(2)

    raise RuntimeError("ChatGPT 输入框未出现（导航3次均失败）")


def send_prompt(page, text: str, new_conversation: bool = True):
    import pyperclip

    if new_conversation:
        # 首次发送前导航到新对话，避免旧对话状态干扰（会话过长/错误/加载中）
        _new_conversation(page)

    box = page.locator(_INPUT_SEL).first
    box.wait_for(state="visible", timeout=30_000)

    # 关闭可能弹出的 rate-limit / upgrade 弹窗
    _dismiss_blocking_modals(page)
    time.sleep(_jitter(0.20))

    # 鼠标移入 → 点击 → 全选清空
    _human_move(page, box)
    time.sleep(_jitter(0.30))
    box.click()
    time.sleep(_jitter(0.45))
    page.keyboard.press("Control+A")
    time.sleep(_jitter(0.12))
    page.keyboard.press("Backspace")
    time.sleep(_jitter(0.35))

    # 分块粘贴（防止 ChatGPT 把长文本自动转为文件附件）
    # 用互斥锁保护剪贴板：--provider both 时 ChatGPT/DeepSeek 两线程共用一个系统剪贴板
    chunks = [text[i:i+_PASTE_CHUNK] for i in range(0, len(text), _PASTE_CHUNK)]
    with _clipboard_lock:
        for chunk in chunks:
            pyperclip.copy(chunk)
            time.sleep(_jitter(0.15))
            page.keyboard.press("Control+V")
            time.sleep(_jitter(0.60))

    time.sleep(_jitter(1.0))

    # 检测并移除可能生成的文件附件
    _remove_file_attachments(page)
    time.sleep(_jitter(0.50))

    # 优先点击发送按钮（比 Enter 键更可靠，避免多行内容时 Enter 插入换行）
    _send_selectors = [
        'button[data-testid="send-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label="发送提示"]',
        'button[aria-label="Send message"]',
        'button[aria-label="发送消息"]',
        '[data-testid="send-button"]',
    ]
    sent = False
    for sel in _send_selectors:
        try:
            btn = page.locator(sel)
            if btn.count() > 0:
                btn.first.wait_for(state="visible", timeout=4_000)
                _human_move(page, btn.first)
                time.sleep(_jitter(0.20))
                btn.first.click()
                sent = True
                time.sleep(_jitter(1.2))
                break
        except Exception:
            pass

    if not sent:
        page.keyboard.press("Enter")
        time.sleep(_jitter(2.0))
        # 再次确认是否发出（Enter 可能只是插入换行）
        try:
            current = box.inner_text(timeout=3_000) if box else ""
            if current and current.strip():
                for sel in _send_selectors:
                    try:
                        btn = page.locator(sel)
                        if btn.count() > 0:
                            btn.first.wait_for(state="visible", timeout=3_000)
                            btn.first.click()
                            time.sleep(1)
                            break
                    except Exception:
                        pass
        except Exception:
            pass

    # ── 确认消息已提交：等待输入框变空 / 新用户消息出现 ─────────────────────
    def _box_is_empty() -> bool:
        """检查输入框是否已清空（兼容 textarea 和 contenteditable div）。"""
        try:
            # textarea
            val = box.input_value(timeout=500)
            return not val or not val.strip()
        except Exception:
            pass
        try:
            # contenteditable div
            txt = box.inner_text(timeout=500)
            return not txt or not txt.strip()
        except Exception:
            pass
        return True  # 异常时假设已清空

    for _ in range(8):
        if _box_is_empty():
            break
        time.sleep(1)
    else:
        # 输入框仍有内容，强制 Enter 再试一次
        try:
            page.keyboard.press("Enter")
            time.sleep(2)
        except Exception:
            pass


def _strip_markdown_fences(text: str) -> str:
    """
    把 ChatGPT 有时加的 ```html ... ``` 包裹剥掉，只保留 HTML 内容。

    场景：ChatGPT 把一部分内容放在代码块里，另一部分放在代码块外，
    导致提取到的文本混有 ```html / ``` 标记行。
    处理策略：把所有 ``` 代码块的内容提取出来，与代码块外的 HTML 合并。
    """
    # 如果没有代码块标记，直接返回
    if '```' not in text:
        return text

    parts = []
    in_fence = False
    fence_content: list[str] = []
    outside_content: list[str] = []

    for line in text.splitlines():
        if not in_fence and line.strip().startswith('```'):
            in_fence = True
            # 把代码块外已积累的内容存入 parts
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

    # 处理末尾未闭合的代码块 / 普通内容
    remaining = '\n'.join(fence_content if in_fence else outside_content).strip()
    if remaining:
        parts.append(remaining)

    return '\n'.join(parts).strip()


def get_assistant_msg_count(page) -> int:
    """返回页面上当前 assistant 消息数量，用于判断新回复是否已出现。"""
    try:
        return page.evaluate("""() =>
            document.querySelectorAll('[data-message-author-role="assistant"]').length
        """) or 0
    except Exception:
        return 0


def get_last_answer(page) -> str:
    """
    提取最后一条 ChatGPT 消息内容，保留 <pre> 里的换行符。
    支持多种 ChatGPT UI 版本（选择器随版本变化）。
    注意：此函数用于生成过程中的进度检测（判断是否稳定/截断），
    最终内容通过 _get_answer_via_copy_button 获取真正的 Markdown。
    """
    result = page.evaluate(r"""() => {
        const BLOCK = new Set(['div','p','pre','article','section','li',
                               'h1','h2','h3','h4','h5','h6',
                               'blockquote','tr','td','th','ul','ol']);
        function getText(node) {
            if (node.nodeType === 3) return node.nodeValue;
            if (node.nodeType !== 1) return '';
            const tag = node.tagName.toLowerCase();
            if (['script','style','button','svg'].includes(tag)) return '';
            if (tag === 'br') return '\n';
            // pre 块：保留原始文本（含代码）
            if (tag === 'pre') return '\n' + node.textContent + '\n';
            let s = '';
            for (const c of node.childNodes) s += getText(c);
            return BLOCK.has(tag) ? '\n' + s + '\n' : s;
        }

        let els = document.querySelectorAll('[data-message-author-role="assistant"]');
        if (!els.length)
            els = document.querySelectorAll('.agent-turn .markdown, .message.from-assistant .markdown');
        if (!els.length)
            els = document.querySelectorAll('.markdown.prose, .prose');
        if (!els.length) {
            const articles = document.querySelectorAll('article[data-testid^="conversation-turn"]');
            if (articles.length >= 2) {
                const asst = Array.from(articles).filter((_, i) => i % 2 === 1);
                if (asst.length) els = [asst[asst.length - 1]];
            }
        }
        if (!els.length) return '';
        const el = els[els.length - 1];
        return getText(el).replace(/\n{3,}/g, '\n\n').trim();
    }""")
    return result or ""


def _get_answer_via_copy_button(page) -> str:
    """
    点击 ChatGPT 最后一条回复的「Copy」按钮，返回剪贴板中的真正 Markdown。
    用 JS .click() 直接触发，不依赖鼠标 hover（按钮 DOM 存在即可点击）。
    失败时返回空字符串。
    """
    import pyperclip
    import time as _t

    try:
        _pyperclip_copy_retry("__CLEAR__")
    except Exception:
        pass

    # 找文字最长的 assistant 消息，用 JS 直接点击其复制按钮
    # 策略：优先 data-testid="copy-turn-action-button"，再 aria-label 含 copy
    JS_CLICK_COPY = """() => {
        // 找文字最长的 assistant 消息（跳过短 ack）
        const msgs = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
        if (!msgs.length) return {ok: false, reason: 'no assistant messages'};

        let bestMsg = msgs[msgs.length - 1];
        let bestLen = (bestMsg.textContent || '').length;
        for (const m of msgs) {
            const l = (m.textContent || '').length;
            if (l > bestLen) { bestLen = l; bestMsg = m; }
        }

        // 向上找包含它的 turn 容器（任意祖先）
        function findCopyBtn(root) {
            // testid 优先
            const byId = root.querySelector('[data-testid="copy-turn-action-button"]');
            if (byId) return byId;
            // aria-label 含 copy
            const btns = Array.from(root.querySelectorAll('button'));
            return btns.find(b => (b.getAttribute('aria-label') || '').toLowerCase().includes('copy')) || null;
        }

        // 从消息本身向上最多遍历 8 层祖先找按钮
        let node = bestMsg;
        for (let i = 0; i < 8; i++) {
            if (!node || !node.parentElement) break;
            node = node.parentElement;
            const btn = findCopyBtn(node);
            if (btn) {
                btn.click();
                return {ok: true, btnText: btn.getAttribute('aria-label') || btn.getAttribute('data-testid') || ''};
            }
        }

        // 降级：全页面所有 copy 按钮，点最后一个
        const allCopy = Array.from(document.querySelectorAll('[data-testid="copy-turn-action-button"]'));
        if (allCopy.length) {
            allCopy[allCopy.length - 1].click();
            return {ok: true, btnText: 'fallback-testid'};
        }
        const byLabel = Array.from(document.querySelectorAll('button')).filter(b =>
            (b.getAttribute('aria-label') || '').toLowerCase().includes('copy'));
        if (byLabel.length) {
            byLabel[byLabel.length - 1].click();
            return {ok: true, btnText: 'fallback-label'};
        }

        return {ok: false, reason: `no copy btn found, msgs=${msgs.length}, bestLen=${bestLen}`};
    }"""

    # 最多尝试 3 次（等待生成完成后按钮才可点击）
    for attempt in range(3):
        try:
            res = page.evaluate(JS_CLICK_COPY)
            if res and res.get('ok'):
                _t.sleep(1.5)  # 等剪贴板写入
                clip = pyperclip.paste()
                if clip and clip != "__CLEAR__" and len(clip) > 50:
                    print(f"  ✅ ChatGPT 复制按钮成功（{len(clip)} 字符 Markdown，btn={res.get('btnText')}）")
                    return clip
                # 剪贴板内容不对，等一下再试
                _t.sleep(1.0)
            else:
                reason = res.get('reason', '?') if res else '?'
                if attempt == 2:
                    print(f"  ⚠️  JS click 找不到复制按钮: {reason}")
                _t.sleep(2.0)
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠️  JS click 异常: {e}")
            _t.sleep(1.0)

    print("  ❌ 复制按钮 3 次尝试均失败")
    return ""


def _ask_markdown_in_codeblock(page) -> str:
    """
    复制按钮失败时的备用方案：
    发一条追问让 ChatGPT 把刚才的回复放入 ```markdown 代码块，
    然后从 <pre><code> DOM 直接提取（代码块内容不被渲染，保留原始格式）。
    失败返回空字符串。
    """
    import time as _t
    FALLBACK_PROMPT = (
        "现在请做一件事：将你刚才输出的章节内容，**原封不动**地放入下面格式的代码块中再输出一次。\n\n"
        "要求：\n"
        "1. 代码块用 ```markdown 开头，``` 结尾\n"
        "2. 代码块内是你刚才回复的**完整原文**，一个字也不能改、不能省略\n"
        "3. 代码块外面不要有任何其他文字\n\n"
        "格式示例：\n"
        "```markdown\n"
        "## Part 1：...\n"
        "（你的完整章节原文）\n"
        "## Part 15：...\n"
        "```\n\n"
        "现在请输出："
    )
    try:
        send_prompt(page, FALLBACK_PROMPT, new_conversation=False)
        _t.sleep(2)
        # 等回复稳定（最多 120s）
        deadline = _t.time() + 120
        last = ""
        stable_start = None
        while _t.time() < deadline:
            try:
                text = get_last_answer(page)
            except Exception:
                break
            if text == last:
                if stable_start is None:
                    stable_start = _t.time()
                elif _t.time() - stable_start > STABLE_SECS:
                    break
            else:
                last = text
                stable_start = None
            if _is_generating(page) or _is_thinking(page):
                stable_start = None
            _t.sleep(2)

        # 从最后一条 assistant 回复里找 ```markdown ... ``` 代码块
        result = page.evaluate(r"""() => {
            const els = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (!els.length) return '';
            const last = els[els.length - 1];
            const pres = last.querySelectorAll('pre code, pre');
            for (const pre of pres) {
                const t = pre.textContent || '';
                if (t.length > 200) return t;
            }
            return '';
        }""")
        if result and len(result) > 200:
            print(f"  📋 代码块备用方案成功（{len(result)} 字符）")
            return result.strip()
    except Exception as e:
        print(f"  ⚠️  代码块备用方案失败: {e}")
    return ""


# ── ChatGPT 错误检测 ──────────────────────────────────────────────────────────

# 短文本关键词（回复内容 < 400 字时检测，避免误判正文）
_ERROR_PHRASES = [
    # 英语
    "something went wrong",
    "went wrong",
    "there was an error",
    "error generating",
    "please try again",
    "try again later",
    "couldn't complete",
    "cannot complete",
    "network error",
    "stream error",
    # 中文
    "出现了问题",
    "发生了错误",
    "无法完成",
    "请稍后重试",
    "服务出错",
    "网络错误",
    "生成出错",
    # 日语（ChatGPT 日语界面的常见错误提示）
    "エラーが発生しました",        # "发生了错误"（通用，覆盖所有 ～エラーが発生しました）
    "もう一度試してください",      # "请再试一次"
    "しばらくしてからもう一度",    # "过一会儿再试"
    "接続に問題が",               # "连接有问题"
    "ネットワーク エラー",        # "网络错误"
    "再試行",                     # "重试"（单独出现时可能是错误按钮旁的提示）
]

# ChatGPT 错误 UI 的 CSS 选择器（只保留精确的，避免误命中通知/免责声明）
_ERROR_SELECTORS = [
    '[data-testid="conversation-error-message"]',   # ChatGPT 明确的错误容器
    '[data-testid*="error-message"]',
    '[data-testid="regenerate-button"]~div',        # 重试按钮附近的错误说明
    '[role="alert"]:not([aria-live])',              # 真正的 alert（排除 polite 提示）
]

# 已知的"假错误"文本片段（免责声明、提示、版权等）——命中即跳过
_FALSE_POSITIVE_PHRASES = [
    "必ずしも正しいとは限りません",   # 日语免责声明
    "can make mistakes",              # 英语免责声明
    "check important information",
    "verify important",
    "not always correct",
    "may not always be accurate",
    "always double-check",
    "ご確認",                         # 日语"请确认"
    "重要な情報は確認",
    "ChatGPT可能会犯错",              # 中文免责
    "内容可能不准确",
    "help.openai.com",
    "openai.com/policies",
]


def _check_page_error(page) -> str | None:
    """
    检查页面上是否有 ChatGPT 真实错误元素（精确匹配，排除免责声明等误报）。
    返回错误文本（供日志记录），或 None（无错误）。
    """
    for sel in _ERROR_SELECTORS:
        try:
            els = page.locator(sel)
            if els.count() > 0 and els.first.is_visible(timeout=1000):
                txt = els.first.inner_text(timeout=2000).strip()
                if not txt or len(txt) > 600:
                    continue
                # 排除已知的免责声明/通知文本
                tl = txt.lower()
                if any(fp.lower() in tl for fp in _FALSE_POSITIVE_PHRASES):
                    continue
                return txt
        except Exception:
            pass
    return None


def _is_content_error(text: str) -> bool:
    """
    把回复文本本身当错误信息的二次检测：
    仅对短文本（< 400 字）做关键词匹配，先排除已知免责声明，再匹配错误词。
    """
    if not text or len(text) > 400:
        return False
    tl = text.lower()
    # 先排除：是免责声明/提示，不是错误
    if any(fp.lower() in tl for fp in _FALSE_POSITIVE_PHRASES):
        return False
    return any(p.lower() in tl for p in _ERROR_PHRASES)


def _try_regenerate(page) -> bool:
    """
    尝试点击 ChatGPT 的「重试/Regenerate」按钮。成功返回 True。
    覆盖英语 / 中文简繁 / 日语界面的各种按钮文字。
    """
    selectors = [
        # ── data-testid（最精确）──────────────────────────────────────────────
        '[data-testid="regenerate-button"]',
        '[data-testid*="regenerate"]',
        '[data-testid*="retry"]',
        # ── aria-label（各语言）──────────────────────────────────────────────
        'button[aria-label="Regenerate"]',
        'button[aria-label="Regenerate response"]',
        'button[aria-label="重试"]',
        'button[aria-label="重試"]',
        'button[aria-label="再生成"]',
        'button[aria-label="再試行"]',
        # ── 按钮文字（各语言）────────────────────────────────────────────────
        'button:has-text("Regenerate")',
        'button:has-text("Try again")',
        'button:has-text("Retry")',
        'button:has-text("重试")',
        'button:has-text("重試")',
        'button:has-text("再生成")',
        'button:has-text("再試行")',
        'button:has-text("もう一度試す")',
        'button:has-text("送信し直す")',
        # ── 兜底：最后一条助手消息附近的所有按钮 ─────────────────────────────
        'div[data-message-author-role="assistant"]:last-of-type button',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel)
            cnt = btn.count()
            if cnt == 0:
                continue
            for i in range(min(cnt, 3)):
                try:
                    if btn.nth(i).is_visible(timeout=1500):
                        btn.nth(i).click()
                        time.sleep(3)
                        return True
                except Exception:
                    pass
        except Exception:
            pass
    return False


def _is_generating(page) -> bool:
    """ChatGPT 流式输出过程中，页面上存在「停止生成」按钮（■）或流式光标。"""
    for sel in [
        'button[data-testid="stop-button"]',
        'button[data-testid*="stop"]',
        'button[data-testid*="stop-generating"]',
        'button[data-testid="composer-speech-button"]~button',  # 2025+ layout
        'button[aria-label="Stop generating"]',
        'button[aria-label="Stop streaming"]',
        'button[aria-label="Stop"]',
        'button[aria-label="停止生成"]',
        'button[aria-label="停止"]',
        'button[aria-label="생성 중지"]',
        'button[aria-label="生成を停止"]',
        'button[aria-label*="stop" i]',
        'button[aria-label*="Stop" i]',
        # 2025+ ChatGPT uses a square icon button during generation
        'button svg[data-icon="stop"]',
        '[data-state="generating"]',
        '[data-streaming="true"]',
    ]:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=300):
                return True
        except Exception:
            pass
    # Also check via JS for streaming cursor (blinking underscore or similar)
    try:
        found = page.evaluate("""() => {
            // ChatGPT 2025+: streaming message has data-message-id and is incomplete
            const streamingEl = document.querySelector(
                '[data-message-author-role="assistant"][data-message-id]:not([data-message-id=""])'
            );
            if (streamingEl) {
                // Check if there's an active blinking/streaming cursor
                // 注意：排除 cursor-default/cursor-pointer 等 Tailwind CSS 鼠标样式类（误判）
                const cursor = streamingEl.querySelector(
                    '.cursor, .cursor-blink, [class*="blink"], [class="result-streaming"], [class*=" streaming"], [class^="streaming"]'
                );
                if (cursor && cursor.offsetParent !== null) return true;
            }
            // Check for square stop icon button: svg must contain ONLY a single <rect>
            // (the stop/square icon has no path/circle, just one rect)
            // Note: do NOT use 'any rect in svg' — that matches nearly all icon buttons (false positive)
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.offsetParent === null) continue;
                const svg = btn.querySelector('svg');
                if (!svg) continue;
                const children = svg.querySelectorAll('*');
                if (children.length === 1 && children[0].tagName.toLowerCase() === 'rect') return true;
            }
            return false;
        }""")
        if found:
            return True
    except Exception:
        pass
    return False


def _is_thinking(page) -> bool:
    """ChatGPT「思考中」阶段（转圈圈，尚未开始输出文字）。"""
    # JS 扫描：任何可见的加载/动画指示器
    try:
        found = page.evaluate("""() => {
            const keywords = ['loading','thinking','spinner','pulse','blink','dots','cursor'];
            const sels = [
                '[data-testid*="thinking"]','[data-testid*="loading"]',
                '[class*="loading"]','[class*="thinking"]','[class*="spinner"]',
                '[class*="pulse"]','[class*="blink"]','[class*="dots"]',
                'span.animate-pulse', 'div.animate-pulse',
                'svg[class*="spin"]', '[class*="generating"]',
            ];
            for (const sel of sels) {
                try {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) return true;
                } catch(e) {}
            }
            return false;
        }""")
        if found:
            return True
    except Exception:
        pass
    return False


def _try_continue_generating(page) -> bool:
    """
    检测并点击"生成を続ける"/"Continue generating"按钮。
    返回 True 表示已点击（需继续等待后续生成）。
    """
    selectors = [
        'button:has-text("生成を続ける")',
        'button:has-text("Continue generating")',
        'button:has-text("继续生成")',
        'button:has-text("繼續生成")',
        '[data-testid="continue-generating-button"]',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible(timeout=1000):
                btn.first.click()
                print("  ▶ 点击「生成を続ける」，等待继续生成...")
                time.sleep(3)
                return True
        except Exception:
            pass
    return False


def wait_for_answer(page, timeout: int = 300, stable_secs: int = STABLE_SECS,
                    ack_only: bool = False, min_msg_count: int = 0) -> str:
    """
    等待 ChatGPT 回复稳定。
    返回值：回复文本 / 'FREE_QUOTA_EXCEEDED' / 'CHATGPT_ERROR'
    ack_only=True：只等短确认回复（多段发送中间段），不尝试复制按钮/代码块追问。
    min_msg_count：等待页面 assistant 消息数 >= 此值才开始稳定计时（防止拿到旧消息）。
                   传入发送前的消息数+1，确保新回复已出现。
    """
    last = ""
    start = time.time()
    last_text_change = time.time()   # 上次 text 发生变化的时刻（用于检测卡死）
    stable_start = None
    regen_attempts = 0       # 本轮已点「重试」次数
    _STUCK_GENERATING_SECS = 240  # generating=True 但4分钟内 text 没变化 → 认为卡死

    while True:
        # ── 页面已关闭则直接退出 ───────────────────────────────────────────────
        try:
            current_url = page.url or ""
        except Exception:
            print("  ⚠️  页面已关闭，退出等待")
            return "CHATGPT_ERROR"
        # Session 过期时会跳到登录页
        if any(kw in current_url for kw in ("login", "auth/", "signin", "openai.com/")):
            print(f"  ⚠️  页面跳到登录页（{current_url[:60]}），session 已过期")
            return "CHATGPT_ERROR"

        # ── 额度耗尽 / 限速 ──────────────────────────────────────────────────
        try:
            # 永久性额度耗尽 → FREE_QUOTA_EXCEEDED（切换账号）
            hard_quota_texts = [
                "您已达到免费额度", "You've reached your limit",
                "You've reached the usage limit", "You've hit your limit",
                "You can send", "messages every",
                "GPT-4o is at capacity", "reached capacity", "at capacity",
                "Upgrade to continue", "Upgrade to Plus",
                "达到了上限", "发送了太多消息",
                "history rate limit",
                "访问太多", "限制访问", "晚些时候再",
            ]
            # 临时限速 → RATE_LIMITED（等待后重试，不切换账号）
            soft_rate_texts = [
                "rate limit", "Rate limit",
                "too many requests", "Too many requests",
                "Try again in", "请稍后再试",
            ]
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            for phrase in soft_rate_texts:
                if phrase.lower() in body_text.lower():
                    print(f"  ⚠️  检测到临时限速：'{phrase}'")
                    return "RATE_LIMITED"
            for phrase in hard_quota_texts:
                if phrase.lower() in body_text.lower():
                    print(f"  ⚠️  检测到额度耗尽：'{phrase}'")
                    return "FREE_QUOTA_EXCEEDED"
        except Exception:
            return "CHATGPT_ERROR"

        # ── 检测页面上的错误 UI 元素（红色框、alert 等）────────────────────────
        try:
            page_err = _check_page_error(page)
            text = get_last_answer(page)
        except Exception:
            return "CHATGPT_ERROR"

        # 两路错误信号：DOM 错误元素 OR 回复文本本身是错误提示
        is_error = bool(page_err) or _is_content_error(text)

        if is_error:
            err_hint = (page_err or text or "未知错误")[:80].strip()
            if regen_attempts < 3:
                regen_attempts += 1
                print(f"  ⚠️  ChatGPT 报错（{err_hint}），"
                      f"第{regen_attempts}次尝试重试按钮...")
                if _try_regenerate(page):
                    last = ""
                    stable_start = None
                    time.sleep(5)
                    continue
                # 点不到按钮时，稍等后再循环（等 ChatGPT 自行恢复）
                time.sleep(10)
                continue
            print(f"  ❌ ChatGPT 持续报错（{err_hint}），放弃")
            return "CHATGPT_ERROR"

        if not text:
            elapsed = time.time() - start
            thinking   = _is_thinking(page)
            generating = _is_generating(page)

            # 思考中或生成中 → 继续等，不计入稳定计时
            if thinking or generating:
                # 卡死检测：generating=True 但 text 长期为空（ChatGPT 转圈圈但不输出）
                stuck_secs = time.time() - last_text_change
                if stuck_secs > _STUCK_GENERATING_SECS:
                    print(f"  ⚠️  ChatGPT 已转圈 {int(stuck_secs)}s 但无任何输出，判定卡死")
                    return "CHATGPT_ERROR"
                if int(elapsed) % 30 == 0 and elapsed > 5:
                    print(f"  [等待] {int(elapsed)}s，思考中={thinking}，生成中={generating}，"
                          f"无输出已 {int(stuck_secs)}s")
                time.sleep(2)
                continue

            # mid-session CAPTCHA 检测（每 20 秒检查一次）
            if int(elapsed) % 20 == 0 and elapsed > 10:
                if _detect_captcha(page):
                    print(f"  ⚠️  等待回复中检测到 CAPTCHA，暂停等用户完成验证...")
                    if not _wait_for_captcha_solve(page, max_wait=300):
                        return "CHATGPT_ERROR"
                    # 验证完成后重新发送当前 prompt（调用方已有重试机制）
                    return "CHATGPT_ERROR"

            # 每30秒打印一次诊断
            if int(elapsed) % 30 == 0 and elapsed > 5:
                url = ""
                try:
                    url = page.url or ""
                except Exception:
                    pass
                print(f"  [诊断] 等待{int(elapsed)}s，无输出也无生成指示，url={url[:60]}")
                # 检测弹窗
                for modal_sel in [
                    'text=Upgrade to Plus', 'text=升级到 Plus',
                    "text=You've reached your limit", 'text=您已达到',
                    'text=Network error', 'text=网络错误',
                    '[role="dialog"]', '.modal',
                ]:
                    try:
                        if page.locator(modal_sel).count() > 0:
                            print(f"  [诊断] 检测到弹窗: {modal_sel}")
                    except Exception:
                        pass
                # DOM 诊断：报告页面有多少 article/message 元素
                try:
                    dom_info = page.evaluate("""() => {
                        const arts = document.querySelectorAll('article[data-testid^="conversation-turn"]').length;
                        const msgs = document.querySelectorAll('[data-message-author-role]').length;
                        const asst = document.querySelectorAll('[data-message-author-role="assistant"]').length;
                        const prose = document.querySelectorAll('.markdown,.prose').length;
                        return `turns=${arts} msgs=${msgs} asst=${asst} prose=${prose}`;
                    }""")
                    print(f"  [DOM] {dom_info}")
                except Exception:
                    pass

            # 既无思考/生成指示也无文本 → 120s 快速判定无响应（避免等满 300s）
            if elapsed > 120:
                print(f"  ⚠️  {int(elapsed)}s 既无思考/生成指示也无文本，判定无响应，快速重试")
                return "CHATGPT_ERROR"
            if elapsed > timeout:
                print("  ⚠️  等待 ChatGPT 回复超时（未收到任何输出），可能选择器失效")
                return "CHATGPT_ERROR"
            time.sleep(2)
            continue

        # ── 等待新消息出现且生成完毕（防止拿到旧ack或生成中内容）────────────
        if min_msg_count > 0:
            try:
                cur_count = get_assistant_msg_count(page)
                if cur_count < min_msg_count:
                    elapsed = time.time() - start
                    if elapsed > timeout:
                        print(f"  [等待新消息] 超时（{int(elapsed)}s），ChatGPT 未响应，返回空")
                        return "CHATGPT_ERROR"
                    if int(elapsed) % 30 == 0 and elapsed > 5:
                        print(f"  [等待新消息] 当前{cur_count}条，需{min_msg_count}条，已等{int(elapsed)}s")
                    time.sleep(2)
                    continue
                # 消息数已满足，但若还在生成则重置稳定计时
                if _is_generating(page) or _is_thinking(page):
                    stable_start = None
                    time.sleep(2)
                    continue
            except Exception:
                pass

        # ── 正常稳定检测 ──────────────────────────────────────────────────────
        if text == last:
            if stable_start is None:
                stable_start = time.time()
            elif time.time() - stable_start > stable_secs:
                # 优先：仍在思考或生成 → 重置计时继续等
                if _is_thinking(page) or _is_generating(page):
                    stable_start = None
                # 次之：有「生成を続ける」按钮 → 点击后继续等
                elif _try_continue_generating(page):
                    stable_start = None
                else:
                    # ack_only模式（多段发送中间段）：直接返回，不需要Markdown格式
                    if ack_only:
                        return text
                    # 正式内容：用复制按钮取真正的 Markdown
                    clip = _get_answer_via_copy_button(page)
                    if clip:
                        return clip
                    # 复制按钮失败：返回 CHATGPT_ERROR 让 pipeline 重试
                    print("  ❌ 复制按钮失败，无法获取原始 Markdown，触发重试")
                    return "CHATGPT_ERROR"
        else:
            last = text
            last_text_change = time.time()   # text 有变化，重置卡死计时
            stable_start = None

        if time.time() - start > timeout:
            if ack_only:
                return last
            clip = _get_answer_via_copy_button(page)
            if clip:
                return clip
            print("  ❌ 超时且复制按钮失败，触发重试")
            return "CHATGPT_ERROR"
        time.sleep(2)


# ── 截断检测 ──────────────────────────────────────────────────────────────────

def strip_html_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def char_count(html: str) -> int:
    text = re.sub(r"\s+", "", strip_html_tags(html))
    return len(text)


def is_truncated(content: str, section: int) -> bool:
    """
    判断 Markdown 输出是否被截断：
      1. 字数不足最低要求
      2. 代码围栏（``` ）或自定义块（:::）未闭合
      3. Section 5：四个难度分区 + 至少10个 :::q 块
      4. Section 6：必须含 :::milestone 和 :::next
    """
    text_len  = char_count(content)
    min_chars = MIN_SECTION_CHARS.get(section, 1500)

    if text_len < min_chars:
        return True

    # 字数超过上限则视为完整（防止因 ::: 格式差异导致无限追问）
    MAX_SECTION_CHARS = {1: 8000, 2: 10000, 3: 15000, 4: 15000, 5: 12000, 6: 10000}
    if text_len > MAX_SECTION_CHARS.get(section, 10000):
        return False

    # 检测未闭合的代码围栏
    fence_depth = 0
    for line in content.split('\n'):
        if re.match(r'^```\w', line):
            fence_depth += 1
        elif line.strip() == '```' and fence_depth > 0:
            fence_depth -= 1
    if fence_depth > 0:
        return True

    # Section 5：:::q 块不需要显式 ::: 关闭（每个新 :::q 隐式关闭上一个），
    # 因此直接用内容特异检查，通过后 return False，跳过通用 ::: 平衡检查。
    if section == 5:
        for hdr in ["初级题", "中级题", "高级题", "大厂系统设计"]:
            if hdr not in content:
                return True
        q_count = len(re.findall(r'^:::q\s', content, re.MULTILINE))
        if q_count < 10:
            # 兼容未加 :::q 标签的格式（如 Q1. Q2. ... 编号式）
            q_count = len(re.findall(r'(?m)^Q\d+[\.、]', content))
        if q_count < 10:
            return True
        return False

    # 检测未闭合的自定义 fenced block（:::）——非 section 5
    custom_open  = len(re.findall(r'^:::\w', content, re.MULTILINE))
    custom_close = len(re.findall(r'^:::$',  content, re.MULTILINE))
    if custom_open > custom_close:
        return True

    # Section 6：必须含里程碑 + 下章预告（兼容无 ::: 标签的纯文本格式）
    if section == 6:
        has_milestone = (':::milestone' in content or '里程碑' in content
                         or 'milestone' in content.lower() or '你已经完成' in content)
        if not has_milestone:
            return True
        has_next = (':::next' in content or '下章预告' in content
                    or '下一章' in content or '第' in content and '章' in content and ('预告' in content or '我们将' in content))
        if not has_next:
            return True

    return False


# ── Section 写作流程 ──────────────────────────────────────────────────────────

def write_section(
    page,
    chapter: int,
    section: int,
    cfg: dict,
    skip_review: bool = False,
    bot=None,
) -> str | None:
    """
    向 LLM（ChatGPT 或 DeepSeek）发送 Section 写作 Prompt，收集完整输出。

    bot: 实现 send_prompt / wait_for_answer 的 bot 模块；None → 使用 chatgpt_bot 自身。

    Returns:
        完整 HTML 字符串；
        ("PARTIAL", html) 元组（字数不足时）；
        "FREE_QUOTA_EXCEEDED" 字符串；
        None（失败）。
    """
    import chatgpt_bot as _self
    if bot is None:
        bot = _self

    from prompt_builder import build_prompt
    from progress import SECTION_NAMES

    error_signal = getattr(bot, "ERROR_SIGNAL", "CHATGPT_ERROR")
    prompt = build_prompt(chapter, section, cfg)

    # ── prompt_log：自定义提示词检查 ──────────────────────────────────────────
    _pl_book = cfg.get("_book", "ai_native")
    try:
        import progress as _pg_mod
        _pl_prov = _pg_mod.get_provider()
    except Exception:
        _pl_prov = "chatgpt"
    _pl_start = time.time()
    try:
        from prompt_log import get_custom_prompt as _get_custom
        _custom_p = _get_custom(_pl_book, _pl_prov, chapter, section)
        if _custom_p:
            print(f"  ✏  使用自定义提示词（{len(_custom_p):,} 字符）")
            prompt = _custom_p
    except Exception:
        pass
    # ─────────────────────────────────────────────────────────────────────────

    label = f"第{chapter}章 Section{section} ({SECTION_NAMES[section][:15]}...)"

    def _send_safe(p=prompt) -> bool:
        """发送 Prompt，输入框找不到时等待15秒重试一次，仍失败返回 False。"""
        for attempt in range(2):
            try:
                bot.send_prompt(page, p)
                return True
            except RuntimeError as e:
                print(f"  ⚠️  send_prompt 失败（{e}），等待15秒后重试...")
                time.sleep(15)
        return False

    print(f"\n  发送 Prompt ({len(prompt)} 字符)...")
    if not _send_safe():
        print(f"  ❌ {label}：输入框一直找不到，触发浏览器重启")
        return "NEED_RESTART"

    print(f"  等待回复 [{label}]...")
    answer = bot.wait_for_answer(page)

    # ── 服务端错误：重发 Prompt 重试 ─────────────────────────────────────────
    for send_retry in range(MAX_SEND_RETRIES):
        if answer != error_signal:
            break
        wait_t = random.randint(20, 40)
        print(f"  ⚠️  服务错误，{wait_t}秒后第{send_retry+1}次重发 Prompt...")
        time.sleep(wait_t)
        if not _send_safe():
            break
        answer = bot.wait_for_answer(page)

    if answer == error_signal:
        print(f"  ❌ {label}：持续报错，跳过本节")
        return None

    if answer == "FREE_QUOTA_EXCEEDED":
        return "FREE_QUOTA_EXCEEDED"
    if not answer.strip():
        print(f"  ❌ {label}：回复为空")
        return None

    all_parts = [answer]
    rounds = 0

    # 自动追问"继续"直到完整
    while is_truncated("\n".join(all_parts), section) and rounds < MAX_CONTINUE_ROUNDS:
        rounds += 1
        combined = "\n".join(all_parts)
        current_chars = char_count(combined)
        print(f"  ⚠️  输出不完整（{current_chars} 字），第{rounds}次追问继续...")
        time.sleep(random.randint(5, 10))

        # 携带已输出内容末尾 600 字作为上下文，避免每次开新对话后 ChatGPT 不知道从哪继续
        _tail = combined[-600:] if len(combined) > 600 else combined
        _continue_prompt = (
            "请继续输出，从以下内容断点之后接续（不重复已有内容，直到本Section完整结束）：\n\n"
            "---（以下是已输出的最后部分）---\n"
            f"{_tail}\n"
            "---（请从这里之后继续输出，保持格式一致）---\n"
        )
        bot.send_prompt(page, _continue_prompt, new_conversation=False)
        cont = bot.wait_for_answer(page)

        if cont == "FREE_QUOTA_EXCEEDED":
            return "FREE_QUOTA_EXCEEDED"
        if cont == error_signal:
            print(f"  ⚠️  追问时报错，停止继续追问")
            break
        if not cont.strip() or cont == answer:
            print(f"  ⚠️  没有继续输出，停止追问")
            break
        all_parts.append(cont)
        answer = cont

    full_html = "\n".join(all_parts)

    if is_truncated(full_html, section):
        print(f"  ⚠️  {label}：可能仍不完整（{char_count(full_html)} 字），标记为 partial")
        try:
            from prompt_log import save_run as _pl_save
            _pl_save(_pl_book, _pl_prov, chapter, section, prompt, full_html,
                     "partial", time.time() - _pl_start, SECTION_NAMES.get(section, ""))
        except Exception:
            pass
        return ("PARTIAL", full_html)

    # ── 生成完立刻抢剪贴板（Review 之前）────────────────────────────────────────
    # 比 wait_for_answer 内部的调用更晚，UI 已完全稳定，copy 按钮成功率更高
    _fn = getattr(bot, "_get_answer_via_copy_button", None)
    if _fn:
        clip = _fn(page)
        if clip:
            print(f"  📋 生成完成后剪贴板抢先保存（{len(clip):,} 字）")
            full_html = clip

    # ── Review → Revise ───────────────────────────────────────────────────────
    if not skip_review:
        from book_memory import review_section as _review, revise_section as _revise
        from progress import SECTION_NAMES as _SN
        rev = _review(page, chapter, section, full_html, _SN[section], bot=bot)
        if not rev["passed"]:
            revised = _revise(page, full_html, rev["issues"], bot=bot)
            # R1思考模式下final answer可能很短，防止用短结果覆盖完整初稿
            min_len = max(1500, len(full_html) // 4)
            if revised and len(revised) >= min_len:
                full_html = revised
                # ── 修订完成后再抢一次剪贴板，覆盖初稿 ──────────────────────
                if _fn:
                    clip2 = _fn(page)
                    if clip2 and len(clip2) >= min_len:
                        print(f"  📋 修订后剪贴板覆盖（{len(clip2):,} 字）")
                        full_html = clip2
                print(f"  ✅ Section {section} 修订完成")
            elif revised:
                print(f"  ⚠️ Section {section} 修订结果过短（{len(revised)} 字 < {min_len}），保留初稿")

    print(f"  ✅ {label}：完成（{char_count(full_html):,} 字）")
    try:
        from prompt_log import save_run as _pl_save
        _pl_save(_pl_book, _pl_prov, chapter, section, prompt, full_html,
                 "success", time.time() - _pl_start, SECTION_NAMES.get(section, ""))
    except Exception:
        pass
    return full_html


# ── 章节写作主流程 ────────────────────────────────────────────────────────────

def run_chapter(
    chapter: int,
    cfg: dict,
    account: str = "1",
    sections: list[int] | None = None,
    skip_review: bool = False,
    provider: str = "chatgpt",
) -> None:
    """
    写一章的所有（或指定的）Section，完成后自动注入书文件并提取章节记忆。

    skip_review=True 时跳过 Review/Revise 和记忆提取（快速模式）。
    """
    from progress import (
        save_section_content, save_section_md, render_section,
        set_section_status,
        get_pending_sections, SECTION_NAMES,
        assemble_chapter_html, count_words, set_injected,
    )
    if provider == "deepseek":
        import deepseek_bot as bot
    else:
        import chatgpt_bot as bot

    # 切换 progress / chapter 输出目录到对应 provider 子目录
    import progress as _prog
    import chapter_builder as _cb
    _prog.set_provider(provider)
    _cb.set_provider(provider)

    ch_info = cfg["chapters"][str(chapter)]
    account_dir = bot.ACCOUNTS.get(account, list(bot.ACCOUNTS.values())[0])

    if sections is None:
        sections = get_pending_sections(chapter)
        if not sections:
            print(f"✅ 第{chapter}章所有 Section 均已完成")
            return

    mode_label = "[快速模式，跳过Review]" if skip_review else "[Review模式]"
    print(f"\n开始写第{chapter}章：{ch_info['title']}  {mode_label}")
    print(f"计划写 Section：{sections}")

    try:
        import pyperclip  # noqa
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：请安装依赖：pip install playwright pyperclip")
        print("playwright install chromium")
        return

    # 导入 deepseek 专用异常（仅 deepseek provider 需要）
    _BrowserRestartNeeded = None
    _AccountNotLoggedIn   = None
    if provider == "deepseek":
        try:
            from deepseek_bot import BrowserRestartNeeded as _BrowserRestartNeeded
            from deepseek_bot import AccountNotLoggedIn   as _AccountNotLoggedIn
        except ImportError:
            pass

    # ── 账号未登录时直接返回 QUOTA_EXCEEDED，让外层切换到下一个账号 ──────────
    if _AccountNotLoggedIn:
        try:
            pass  # 仅在 with 块内捕获，见下方
        except Exception:
            pass

    with sync_playwright() as p:
        try:
            browser, ctx, page, chrome_proc = bot.open_browser(p, account_dir)
        except Exception as e:
            if isinstance(e, SessionExpired):
                print(f"  ⏭  账号 {account} session 已过期，跳过（视为额度耗尽）")
                return "QUOTA_EXCEEDED"
            if _AccountNotLoggedIn and isinstance(e, _AccountNotLoggedIn):
                print(f"  ⏭  账号 {account} 未登录，跳过（视为额度耗尽）")
                return "QUOTA_EXCEEDED"
            raise

        def _kill_chrome_proc(proc):
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        def _reopen_browser():
            """关闭当前浏览器，重开一个干净的 persistent context。
            等效于用户手动「停止 → 继续生成」。"""
            nonlocal ctx, page, chrome_proc
            print("  🔄 关闭浏览器，重新启动（等效手动停止→继续生成）...")
            try:
                ctx.close()
            except Exception:
                pass
            _kill_chrome_proc(chrome_proc)
            _, new_ctx, new_page, new_proc = bot.open_browser(p, account_dir)
            ctx        = new_ctx
            page       = new_page
            chrome_proc = new_proc
            print("  ✅ 浏览器已重开，session 恢复")

        for section in sections:
            print(f"\n{'─'*50}")
            print(f"  Section {section}：{SECTION_NAMES[section]}")
            print(f"{'─'*50}")

            try:
                result = write_section(page, chapter, section, cfg, skip_review=skip_review, bot=bot)
            except Exception as e:
                if _BrowserRestartNeeded and isinstance(e, _BrowserRestartNeeded):
                    print(f"  ⚠️  BrowserRestartNeeded: {e}")
                    _reopen_browser()
                    try:
                        result = write_section(page, chapter, section, cfg, skip_review=skip_review, bot=bot)
                    except Exception as e2:
                        print(f"  ❌ 重启后仍失败: {e2}")
                        result = None
                else:
                    raise

            if result == "FREE_QUOTA_EXCEEDED":
                print(f"  账号 {account} 额度耗尽，停止。")
                ctx.close()
                _kill_chrome_proc(chrome_proc)
                return "QUOTA_EXCEEDED"

            if result == "NEED_RESTART":
                # 先尝试重新导航（保留 session），导航失败则真正重启浏览器
                print("  🔄 重新导航到 DeepSeek（保留 session，不关浏览器）...")
                nav_ok = False
                try:
                    from deepseek_bot import DEEPSEEK_URL as _DS_URL
                    page.goto(_DS_URL, wait_until="domcontentloaded", timeout=30_000)
                    time.sleep(3)
                    nav_ok = True
                except Exception as e:
                    print(f"  导航失败（{e}），改为重启浏览器...")
                    _reopen_browser()
                if nav_ok:
                    result = write_section(page, chapter, section, cfg, skip_review=skip_review, bot=bot)
                    if result in ("NEED_RESTART", None):
                        print(f"  ❌ Section {section} 导航后仍失败，改为重启浏览器...")
                        _reopen_browser()
                        result = write_section(page, chapter, section, cfg, skip_review=skip_review, bot=bot)
                else:
                    result = write_section(page, chapter, section, cfg, skip_review=skip_review, bot=bot)
                if result in ("NEED_RESTART", None):
                    print(f"  ❌ Section {section} 重启后仍失败，跳过")
                    continue
                if result == "FREE_QUOTA_EXCEEDED":
                    ctx.close()
                    _kill_chrome_proc(chrome_proc)
                    return "QUOTA_EXCEEDED"

            if result is None:
                print(f"  ❌ Section {section} 写作失败，跳过")
                continue

            if isinstance(result, tuple) and result[0] == "PARTIAL":
                raw = result[1]
                md_path = save_section_md(chapter, section, raw)
                render_section(chapter, section, provider)
                set_section_status(chapter, section, "partial")
                print(f"  ⚠️  Section {section} 保存为 partial：{md_path}")
            else:
                raw = result
                md_path = save_section_md(chapter, section, raw)
                render_section(chapter, section, provider)
                set_section_status(chapter, section, "done")
                print(f"  💾 已保存：{md_path}")

            if provider == "deepseek":
                sleep_t = random.randint(30, 60)
                print(f"  休息 {sleep_t} 秒（DeepSeek 降频）...")
            else:
                sleep_t = random.randint(5, 10)
                print(f"  休息 {sleep_t} 秒...")
            time.sleep(sleep_t)

        # ── 全部完成：生成独立章节 HTML + 提取章节记忆（在关闭浏览器之前）──────
        still_pending = get_pending_sections(chapter)
        if not still_pending:
            print(f"\n第{chapter}章全部 Section 完成！正在生成独立章节文件...")
            full_html = assemble_chapter_html(chapter)
            if full_html:
                from chapter_builder import write_chapter_html
                ch_path = write_chapter_html(chapter, full_html, cfg)
                wc = count_words(full_html)
                set_injected(chapter, wc)
                print(f"✅ 第{chapter}章已生成：{ch_path}（{wc:,} 字）")

                # 无论是否 skip_review，都提取章节记忆（保证后续章节上下文连贯）
                from book_memory import extract_chapter_memory, update_book_memory
                memory_text = extract_chapter_memory(page, chapter, full_html, bot=bot)
                if memory_text:
                    update_book_memory(chapter, memory_text)
            browser.close()
            _kill_chrome_proc(chrome_proc)
            return "DONE"
        else:
            print(f"\n第{chapter}章还有未完成的 Section：{still_pending}")
            print(f"继续运行：python book_agent.py write {chapter}")
            browser.close()
            _kill_chrome_proc(chrome_proc)
            return "PARTIAL"


# ── 高层接口：单次对话（圣经流水线专用） ─────────────────────────────────────

def send_and_collect(
    prompt: str,
    account: str = "1",
    max_continues: int = 8,
    timeout_per_turn: int = 300,
    continue_signal: str = "继续",
) -> str:
    """
    打开浏览器 → 新建对话 → 发送 prompt → 收集完整回复（自动处理"继续"）。

    适用于圣经流水线的 Blueprint / Chapter Design / Writing 等大段输出任务。

    Returns:
        完整回复文本（纯文本，已去除 HTML 标签）
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
            print(f"❌ 打开浏览器失败：{e}")
            return ""

        try:
            _new_conversation(page)
            time.sleep(2)

            print(f"  📤 发送提示词（{len(prompt):,} 字符）...")
            send_prompt(page, prompt)

            parts: list[str] = []
            for turn in range(max_continues + 1):
                print(f"  ⏳ 等待回复（turn {turn + 1}）...")
                answer = wait_for_answer(page, timeout=timeout_per_turn)

                if answer in ("FREE_QUOTA_EXCEEDED", CHATGPT_URL, "CHATGPT_ERROR"):
                    print(f"  ⚠️  收到错误信号：{answer}")
                    break

                # 去除 HTML 标签（如果是 HTML 输出）
                clean = strip_html_tags(answer) if answer.startswith("<") else answer
                parts.append(clean.strip())
                print(f"  ✅ Turn {turn + 1}：{len(clean):,} 字符")

                # 检测是否需要继续
                if not is_truncated(answer, section=0):
                    break
                if turn >= max_continues:
                    print(f"  ⚠️  已达最大「继续」次数（{max_continues}），停止")
                    break

                print(f"  ▶  自动发送「{continue_signal}」...")
                send_prompt(page, continue_signal, new_conversation=False)

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
