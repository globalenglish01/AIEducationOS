"""
engine/login_helper.py
----------------------
命令行工具：打开 Playwright 浏览器，供用户手动登录并保存 session。
GUI 通过 subprocess 调用此脚本，无需依赖外部 chatgpt_agent/。

用法：
    python login_helper.py chatgpt --storage-dir <path>
    python login_helper.py deepseek --storage-dir <path>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def login_chatgpt(storage_dir: str) -> None:
    storage_path = Path(storage_dir)
    storage_path.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：pip install playwright && playwright install chromium")
        sys.exit(1)

    import chatgpt_bot as bot

    bot.ACCOUNTS["_login_"] = str(storage_path)
    with sync_playwright() as p:
        browser, ctx, page, _proc = bot.open_browser(p, str(storage_path))
        print(f"✅ ChatGPT 登录成功，session 已保存到：{storage_path}")
        browser.close()
        if _proc:
            try:
                _proc.terminate()
            except Exception:
                pass


def login_deepseek(storage_dir: str) -> None:
    """打开真实 Chrome，等用户手动完成 DeepSeek 登录，检测到成功后保存 session。"""
    import subprocess, socket, time, urllib.request
    storage_path = Path(storage_dir)
    storage_path.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：pip install playwright && playwright install chromium")
        sys.exit(1)

    import deepseek_bot as ds

    # 清除旧锁文件
    ds._clear_profile_locks(str(storage_path))

    # 找 Chrome
    chrome_exe = ds._find_chrome_exe()
    if not chrome_exe:
        print("❌ 未找到 Chrome，请先安装 Google Chrome")
        sys.exit(1)

    # 启动 Chrome
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={storage_path}",
        "--no-first-run", "--no-default-browser-check",
        "https://chat.deepseek.com/",
    ])

    # 等调试端口就绪
    for _ in range(60):
        if proc.poll() is not None:
            print("❌ Chrome 提前退出"); sys.exit(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        contexts = browser.contexts
        ctx = contexts[0] if contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("⏳ 等待登录完成（最多10分钟）...")
        deadline = time.time() + 600
        logged_in = False
        while time.time() < deadline:
            try:
                url = page.url
                if "sign_in" not in url and "chat.deepseek.com" in url:
                    # 等页面稳定
                    time.sleep(3)
                    logged_in = True
                    break
            except Exception:
                pass
            time.sleep(2)

        if logged_in:
            try:
                ctx.storage_state(path=str(storage_path / "storage_state.json"))
                print(f"✅ DeepSeek 登录成功，session 已保存到：{storage_path}")
            except Exception as e:
                print(f"⚠️  session 保存失败：{e}")
        else:
            print("❌ 登录超时（10分钟未完成）")
            sys.exit(1)

        try:
            ctx.close()
        except Exception:
            pass

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="账号登录助手")
    parser.add_argument("provider", choices=["chatgpt", "deepseek"], help="登录目标")
    parser.add_argument("--storage-dir", required=True, help="session 存储目录")
    args = parser.parse_args()

    sys.path.insert(0, str(BASE_DIR))

    if args.provider == "chatgpt":
        login_chatgpt(args.storage_dir)
    else:
        login_deepseek(args.storage_dir)
