"""
AI Native System — 统一入口
=============================

用法：

  # 运行某本书（全部章节）
  python main.py run ai_native_bible

  # 从第5章开始续跑
  python main.py run ai_native_bible --from 5

  # 只运行某一章
  python main.py run ai_native_bible --chapter 3

  # 只运行某章的某个 Stage
  python main.py run ai_native_bible --chapter 3 --stage 2

  # 生成完后自动重建 JSON 并推送
  python main.py run ai_native_bible --then-build

  # 单独重建前端 JSON（不需要 LLM，纯文件处理）
  python main.py build ai_native_bible
  python main.py build all              # 重建所有书 + git push

  # 查看进度
  python main.py status ai_native_bible

  # 查看所有可用的书
  python main.py list

  # 添加新书注释
  python main.py glossary ai_native_bible

支持的书：books/ 目录下任何包含 config.json 的子目录。
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

# Windows cp932 环境下 print 中文会 UnicodeEncodeError → 进程崩溃
# 强制 stdout/stderr 使用 UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT       = Path(__file__).resolve().parent
BOOKS_DIR  = ROOT / "books"
OUTPUT_DIR = ROOT / "output"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine"))   # md_renderer, build_sections_json

# bot 文件（chatgpt_bot / deepseek_bot）运行时按需加载，路径由 engine/llm.py 管理


# ─────────────────────────────────────────────────────────────────────────────
# project_root：git 仓库根目录（输出文件路径的基准）
# ─────────────────────────────────────────────────────────────────────────────

def _find_project_root() -> Path:
    """找到 git 仓库根目录（从 ROOT 向上找 .git）。"""
    p = ROOT
    for _ in range(6):
        if (p / ".git").exists():
            return p
        p = p.parent
    return ROOT.parent.parent  # 最坏情况兜底


PROJECT_ROOT = _find_project_root()


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def list_books() -> list[str]:
    return [d.name for d in BOOKS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_") and (d / "config.json").exists()]


def load_config(book_id: str) -> dict:
    path = BOOKS_DIR / book_id / "config.json"
    if not path.exists():
        print(f"❌ 找不到 books/{book_id}/config.json")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def make_pipeline(book_id: str, llm):
    from engine.pipeline import Pipeline
    config  = load_config(book_id)
    prompts = BOOKS_DIR / book_id / "prompts"
    return Pipeline(book_id, config, prompts, OUTPUT_DIR, llm)


def _resolve_path(rel_or_abs: str) -> Path:
    """
    路径解析：
      - 绝对路径 → 直接用
      - 相对路径 → 相对于 PROJECT_ROOT
    """
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


# ─────────────────────────────────────────────────────────────────────────────
# Git 工具
# ─────────────────────────────────────────────────────────────────────────────

def _git(args_list: list[str], cwd: Path = PROJECT_ROOT) -> int:
    r = subprocess.run(["git"] + args_list, cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8")
    if r.stdout.strip():
        print(f"[git] {r.stdout.strip()}")
    if r.returncode != 0 and r.stderr.strip():
        print(f"[git] {r.stderr.strip()}")
    return r.returncode


def _git_commit(msg: str, *paths: str):
    for p in paths:
        _git(["add", p])
    rc = _git(["commit", "-m", msg])
    if rc == 0:
        _git(["push"])
    else:
        print("[git] 无变更或提交失败")


# ─────────────────────────────────────────────────────────────────────────────
# 命令：list
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list(_args):
    books = list_books()
    print(f"可用的书（共 {len(books)} 本）：")
    for b in books:
        cfg      = load_config(b)
        title    = cfg.get("book_title", b)
        stages   = len(cfg.get("stages", []))
        chapters = len(cfg.get("chapters", {}))
        print(f"  📚 {b:30s}  {chapters}章 × {stages}个Stage  —  {title}")


# ─────────────────────────────────────────────────────────────────────────────
# 命令：status
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args):
    from engine.progress import BookProgress
    config         = load_config(args.book)
    total_stages   = len(config.get("stages", []))
    total_chapters = len(config.get("chapters", {}))
    progress       = BookProgress(OUTPUT_DIR / args.book)
    print(f"\n📚 {config.get('book_title', args.book)}")
    print(f"   共 {total_chapters} 章 × {total_stages} 个 Stage\n")
    print(progress.summary(total_chapters, total_stages))
    done = sum(1 for ch in range(total_chapters)
               if progress.chapter_done(ch, total_stages))
    print(f"\n进度：{done}/{total_chapters} 章完成")


# ─────────────────────────────────────────────────────────────────────────────
# 命令：run
# ─────────────────────────────────────────────────────────────────────────────

def cmd_run(args):
    from engine.llm import create_llm

    config   = load_config(args.book)
    provider = args.provider or "deepseek"
    account  = args.account  or "1"

    print(f"[main] 启动 {provider} account={account}")
    llm = create_llm(provider, account=account)

    try:
        pipeline = make_pipeline(args.book, llm)

        if args.chapter is not None and args.stage is not None:
            ch_info = config["chapters"].get(str(args.chapter))
            if not ch_info:
                print(f"❌ 章节 {args.chapter} 不存在"); return
            stage_cfg = next((s for s in config["stages"] if s["id"] == args.stage), None)
            if not stage_cfg:
                print(f"❌ Stage {args.stage} 不存在"); return
            pipeline._run_stage(args.chapter, args.stage, ch_info)

        elif args.chapter is not None:
            pipeline.run_chapter(args.chapter)

        else:
            pipeline.run_all(from_chapter=args.from_chapter or 0)

    finally:
        llm.close()

    if getattr(args, "then_build", False):
        print(f"\n[main] --then-build: 开始重建 {args.book} 前端 JSON...")
        _do_build(args.book)

    _git_commit(
        f"feat: ai_native_system {args.book}",
        str(OUTPUT_DIR / args.book),
        str(ROOT),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 命令：build（重建前端 JSON，纯文件处理，无需 LLM）
# ─────────────────────────────────────────────────────────────────────────────

def _do_build(book_id: str) -> bool:
    import re
    from engine.md_renderer import render as md_render

    config = load_config(book_id)
    bcfg   = config.get("build")
    if not bcfg:
        print(f"[build] ⚠️  {book_id} 的 config.json 没有 build 配置，跳过")
        return False

    src_dir  = _resolve_path(bcfg["source_dir"])
    out_json = _resolve_path(bcfg["out_json"])
    mode     = bcfg.get("mode", "sections")
    title    = bcfg.get("frontend_title", config["book_title"])
    subtitle = bcfg.get("frontend_subtitle", "")
    provider = bcfg.get("provider", "deepseek")

    print(f"[build] 书: {book_id}  模式: {mode}")
    print(f"[build] 源目录: {src_dir}")
    print(f"[build] 输出:   {out_json}")

    if mode == "claude_single":
        PLACEHOLDER  = '<p class="text-slate-400 text-sm">本章正在生成中，请稍后刷新…</p>'
        chapter_info = config.get("chapters", {})
        chapters_out = []
        done_count   = 0

        for n in sorted(int(k) for k in chapter_info.keys()):
            spec     = chapter_info[str(n)]
            ch_title = spec.get("title", f"第{n}章")
            part     = spec.get("part", "序章" if n == 0 else f"第{n}章")

            html_file = src_dir / f"ch{n:02d}.html"
            md_file   = src_dir / f"ch{n:02d}.md"

            if html_file.exists():
                html  = html_file.read_text(encoding="utf-8").strip()
                html  = re.sub(r'<div class="provider-badge"[^>]*>.*?</div>\s*', '', html, flags=re.DOTALL)
                badge = '<div class="provider-badge" data-provider="claude">由 Claude 生成</div>\n'
                content, done = badge + html, True
            elif md_file.exists():
                raw  = md_file.read_text(encoding="utf-8").strip()
                raw  = re.sub(r'<!--\s*MEMORY_SUMMARY.*?-->', '', raw, flags=re.DOTALL).strip()
                if len(raw) < 500:
                    content, done = PLACEHOLDER, False
                else:
                    html  = md_render(raw, provider="claude")
                    html  = re.sub(r'<div class="provider-badge"[^>]*>.*?</div>\s*', '', html, flags=re.DOTALL)
                    badge = '<div class="provider-badge" data-provider="claude">由 Claude 生成</div>\n'
                    content, done = badge + html, True
            else:
                content, done = PLACEHOLDER, False

            if done:
                done_count += 1
            chapters_out.append({"n": n, "title": ch_title, "part": part,
                                  "done": done, "content": content})

        data = {"title": title, "subtitle": subtitle or f"共{len(chapters_out)}章",
                "chapters": chapters_out}
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[build] ✅ {out_json.name}  {done_count}/{len(chapters_out)} 章完成")
        return True

    elif mode == "sections":
        from engine.build_sections_json import build as bs_build
        cfg_file = BOOKS_DIR / book_id / "config.json"

        if not src_dir.exists():
            print(f"[build] ⚠️  源目录不存在: {src_dir}，跳过")
            return False

        n = bs_build(src_dir, out_json, title, cfg_file, provider=provider)
        if subtitle:
            data = json.loads(out_json.read_text(encoding="utf-8"))
            data["subtitle"] = subtitle
            out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[build] ✅ {out_json.name}  {n} 节完成")
        return True

    else:
        print(f"[build] ❌ 未知 mode: {mode}")
        return False


def cmd_build(args):
    books = list_books() if args.book == "all" else [args.book]
    built = []
    for b in books:
        ok = _do_build(b)
        if ok:
            built.append(b)

    if built:
        # 收集所有输出 JSON 路径
        out_paths = []
        for b in built:
            bcfg = load_config(b).get("build", {})
            if bcfg.get("out_json"):
                out_paths.append(str(_resolve_path(bcfg["out_json"])))
        names = "+".join(built)
        _git_commit(f"feat: rebuild frontend JSON ({names})", *out_paths)


# ─────────────────────────────────────────────────────────────────────────────
# 命令：glossary
# ─────────────────────────────────────────────────────────────────────────────

def _glossary_target_files(book_id: str, config: dict) -> list[tuple[int, Path]]:
    chapters = config.get("chapters", {})
    bcfg     = config.get("build", {})
    mode     = bcfg.get("mode", "")

    if mode == "claude_single":
        src_dir = _resolve_path(bcfg["source_dir"])
        result  = []
        for ch_num in sorted(int(k) for k in chapters.keys()):
            f = src_dir / f"ch{ch_num:02d}.md"
            if f.exists():
                result.append((ch_num, f))
        return result

    elif mode == "sections":
        src_dir = _resolve_path(bcfg["source_dir"])
        result  = []
        for ch_num in sorted(int(k) for k in chapters.keys()):
            # 处理该章所有存在的 section 文件 s1-s6
            for s in range(1, 7):
                f = src_dir / f"ch{ch_num:02d}_s{s}.md"
                if f.exists():
                    result.append((ch_num, f))
        return result

    else:
        out_dir = OUTPUT_DIR / book_id
        result  = []
        for ch_num in sorted(int(k) for k in chapters.keys()):
            for s in (5, 3, 2):
                f = out_dir / f"ch{ch_num:02d}_s{s}.md"
                if f.exists():
                    result.append((ch_num, f))
                    break
        return result


def _load_account_ids(provider: str) -> list[str]:
    """从 accounts.json 读取账号编号列表（"1","2",...）。"""
    import json as _json
    accounts_file = ROOT / "accounts.json"
    if not accounts_file.exists():
        return ["1", "2", "3", "4"]
    try:
        data = _json.loads(accounts_file.read_text(encoding="utf-8"))
        return [str(i + 1) for i in range(len(data.get("accounts", [])))]
    except Exception:
        return ["1", "2", "3", "4"]


def cmd_glossary(args):
    from engine.llm import create_llm
    from engine.prompt_renderer import render, load_named_template

    config   = load_config(args.book)
    provider = args.provider or "deepseek"
    prompts  = BOOKS_DIR / args.book / "prompts"

    try:
        template = load_named_template(prompts, "glossary")
    except FileNotFoundError:
        print(f"❌ 找不到 books/{args.book}/prompts/glossary.md")
        return

    MARKER    = "## 📖 本章名词解释（新人必读）"
    chapters  = config.get("chapters", {})
    bcfg      = config.get("build", {})
    mode      = bcfg.get("mode", "")
    all_files = _glossary_target_files(args.book, config)
    pending   = [(ch, f) for ch, f in all_files
                 if MARKER not in f.read_text(encoding="utf-8", errors="replace")]

    print(f"[glossary] 书: {args.book}  模式: {mode or '回退'}")
    print(f"[glossary] 源目录: {bcfg.get('source_dir', 'output/')}")
    print(f"[glossary] 总文件: {len(all_files)}  已完成: {len(all_files)-len(pending)}  待处理: {len(pending)}")

    if not pending:
        print("[glossary] 全部已完成 ✅")
        return

    # 账号轮换：从指定账号开始，额度耗尽时自动切换下一个
    all_accounts   = _load_account_ids(provider)
    start_acc      = args.account or "1"
    if start_acc in all_accounts:
        idx = all_accounts.index(start_acc)
        account_queue = all_accounts[idx:] + all_accounts[:idx]  # 从指定账号开始循环
    else:
        account_queue = all_accounts
    exhausted: set = set()   # 已耗尽额度的账号编号

    def _next_account(current: str) -> str | None:
        for acc in account_queue:
            if acc not in exhausted:
                return acc
        return None

    account = _next_account(start_acc) or start_acc
    print(f"[glossary] 使用账号: {account}（共 {len(account_queue)} 个可用）")

    # 像旧版 add_glossary.py 一样：一个 LLM 实例跑全程，只在切换账号时重建
    current_llm_account = None
    llm = None

    def _get_llm(acc):
        nonlocal llm, current_llm_account
        if llm is None or current_llm_account != acc:
            if llm is not None:
                try:
                    llm.close()
                except Exception:
                    pass
            llm = create_llm(provider, account=acc)
            current_llm_account = acc
        return llm

    done = 0
    try:
        for i, (ch_num, fpath) in enumerate(pending, 1):
            ch_info = chapters.get(str(ch_num), {})
            content = fpath.read_text(encoding="utf-8", errors="replace")
            # 从文件名提取 section 编号（ch00_s3.md → 3，ch00.md → None）
            import re as _re
            s_match = _re.search(r'_s(\d+)\.md$', fpath.name)
            section_num = int(s_match.group(1)) if s_match else None
            ctx = {
                "chapter":       ch_num,
                "section":       section_num or "",
                "chapter_title": ch_info.get("title", ""),
                "book_title":    config.get("book_title", args.book),
                "content":       "\n".join(content.splitlines()[:400]),
            }
            prompt = render(template, ctx)

            # 尝试当前账号，若额度耗尽则自动切换
            rate_limit_count = 0
            while True:
                if account is None:
                    print(f"\n[glossary] ❌ 所有账号额度已耗尽，停止（已完成 {done} 章）")
                    done = -done
                    break

                print(f"  [{i}/{len(pending)}] {fpath.name} (acc={account}) ...", end="", flush=True)
                try:
                    response = _get_llm(account).chat([{"role": "user", "content": prompt}])
                except Exception as e:
                    import traceback
                    print(f" ❌ {e}\n{traceback.format_exc()}")
                    # 浏览器可能崩溃，强制重建
                    try:
                        llm.close()
                    except Exception:
                        pass
                    llm = None
                    current_llm_account = None
                    response = ""

                if response == "RATE_LIMITED":
                    rate_limit_count += 1
                    if rate_limit_count >= 3:
                        print(f" ⚠️  账号 {account} 连续限速 {rate_limit_count} 次，切换下一个账号...")
                        exhausted.add(account)
                        account = _next_account(account)
                        rate_limit_count = 0
                        time.sleep(random.uniform(3, 8))
                        continue
                    wait = random.uniform(45, 90)
                    print(f" ⏳ 临时限速（第{rate_limit_count}次），等待 {wait:.0f}s 后重试...")
                    time.sleep(wait)
                    continue

                if response == "FREE_QUOTA_EXCEEDED":
                    print(f" ⚠️  账号 {account} 额度耗尽，切换下一个账号...")
                    exhausted.add(account)
                    account = _next_account(account)
                    time.sleep(2)
                    continue

                # 打印回复前100字（无论成功失败，方便调试）
                preview = response.replace("\n", " ")[:100] if response else "(空)"
                print(f"\n     [回复预览] {preview}")

                if MARKER in response and len(response) > 100:
                    start    = response.index(MARKER)
                    glossary = response[start:]
                    new_text = content.rstrip() + "\n\n" + glossary.strip() + "\n"
                    fpath.write_text(new_text, encoding="utf-8")
                    print(" ✅")
                    done += 1
                else:
                    print(f" ❌ 回复异常（未包含标记或内容过短，长度={len(response)}）")
                break  # 进入下一章

            if done < 0:
                done = -done
                break
            time.sleep(3)
    finally:
        if llm is not None:
            try:
                llm.close()
            except Exception:
                pass

    print(f"\n[glossary] 完成 {done}/{len(pending)}")

    if done > 0:
        src_path = str(_resolve_path(bcfg["source_dir"])) if bcfg.get("source_dir") else str(OUTPUT_DIR / args.book)
        _git_commit(f"feat: glossary {args.book} ({done}章注释)", src_path)
        print(f"\n[glossary] 自动重建前端 JSON...")
        _do_build(args.book)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Native System — 通用书籍生产流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="列出所有可用的书")

    p_status = sub.add_parser("status", help="查看进度")
    p_status.add_argument("book")

    p_run = sub.add_parser("run", help="运行书籍生产流水线")
    p_run.add_argument("book")
    p_run.add_argument("--from",       dest="from_chapter", type=int, default=0)
    p_run.add_argument("--chapter",    type=int, default=None)
    p_run.add_argument("--stage",      type=int, default=None)
    p_run.add_argument("--provider",   default="deepseek", choices=["deepseek", "chatgpt", "both"])
    p_run.add_argument("--account",    default="1")
    p_run.add_argument("--then-build", dest="then_build", action="store_true")

    p_build = sub.add_parser("build", help="重建前端 JSON（无需 LLM）")
    p_build.add_argument("book", help="书的 ID，或 all")

    p_gls = sub.add_parser("glossary", help="为已完成章节添加新人注释")
    p_gls.add_argument("book")
    p_gls.add_argument("--provider", default="deepseek")
    p_gls.add_argument("--account",  default="1")

    args = parser.parse_args()

    if   args.cmd == "list":     cmd_list(args)
    elif args.cmd == "status":   cmd_status(args)
    elif args.cmd == "run":      cmd_run(args)
    elif args.cmd == "build":    cmd_build(args)
    elif args.cmd == "glossary": cmd_glossary(args)
    else:                        parser.print_help()


if __name__ == "__main__":
    main()
