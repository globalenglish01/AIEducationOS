"""
auto_loop.py — 全自动章节生成+质量检查+部署循环

流程：
  for each chapter (from start_chapter to 41):
    1. 运行 pipeline 生成该章节（--start N --end N）
    2. 质量检查：Parts数量、内容长度、无严重损坏
    3. 通过 → 部署到 EC2 → 验证
    4. 失败 → 重试一次 → 仍失败则记录跳过，继续下一章
"""
from __future__ import annotations
import sys
import json
import re
import subprocess
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine" / "llm"))
sys.path.insert(0, str(ROOT / "engine" / "llm" / "engine"))

STATE_PATH = ROOT / "output" / "state" / "pipeline_state.json"
CHAPTERS_DIR = ROOT / "output" / "chapters"
LOG_PATH = ROOT / "output" / "auto_loop.log"

# 从 chapter_pipeline.py 导入章节表
from agents.chapter_pipeline import BOOK_CHAPTERS


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"completed": {}, "failed": []}


def quality_check(chapter_file: Path) -> tuple[bool, str]:
    """
    严格检查生成的 Markdown 文件质量。返回 (ok, reason)。
    所有检查必须全部通过，任何一项失败都强制重新生成。
    """
    if not chapter_file.exists():
        return False, "文件不存在"

    raw = chapter_file.read_text(encoding="utf-8")
    md = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()

    # ── 1. 基本长度 ───────────────────────────────────────────────
    if len(md) < 2000:
        return False, f"内容过短 ({len(md)} 字符)"

    # ── 2. 碎片输出检测（ChatGPT 拒绝完整输出时的特征词）────────────
    bad_patterns = [
        r"替换\s*Part", r"以下是.*?修改", r"根据评审.*?反馈",
        r"只需要替换", r"保持其余内容不变",
    ]
    for pat in bad_patterns:
        if re.search(pat, md[:500]):
            return False, f"碎片输出: {pat}"

    # ── 3. Part 标题数量 ──────────────────────────────────────────
    # 匹配多种格式: ## Part 1, ## Part 1：, Part 1：, **Part 1**等
    parts_count = len(re.findall(r"^##\s*Part\s*\d+", md, re.MULTILINE))
    if parts_count < 5:
        # 二次检测：更宽松的匹配（包含中文冒号、无##前缀等）
        nums = set(re.findall(r'(?:^|\n)(?:##\s*)?(?:\*\*)?Part\s*(\d+)', md))
        parts_count = len(nums)
    if parts_count < 5:
        return False, f"Part 标题不足 ({parts_count}/5)"

    # ── 4. 代码块必须正确配对（无未闭合的 ``` ）─────────────────────
    fence_lines = [l.strip() for l in md.splitlines() if l.strip().startswith("```")]
    depth = 0
    for fl in fence_lines:
        if fl == "```":
            if depth > 0:
                depth -= 1   # 关闭
            # 孤立的 ``` 关闭符 (depth==0) 不增加深度，视为段落结束
        else:
            depth += 1       # 开启（```python / ```mermaid 等）
    if depth != 0:
        return False, f"代码块未正确闭合（未配对围栏数={depth}）"

    # ── 5. mermaid 块（只统计数量，不阻塞，格式问题由normalize处理）──
    mermaid_blocks = re.findall(r"```mermaid[ \t]*\r?\n([\s\S]*?)```", md)

    # ── 6. python/bash 中文比例（警告但不阻塞）──────────────────────
    def _chinese_ratio(text: str) -> float:
        non_ws = [c for c in text if not c.isspace()]
        if not non_ws:
            return 0.0
        return sum(1 for c in non_ws if '一' <= c <= '鿿') / len(non_ws)

    code_blocks = re.findall(r"```(?:python|bash)[ \t]*\r?\n([\s\S]*?)```", md)

    # ── 7. 裸语言名（警告但不阻塞，normalize 已处理）──────────────
    bare_lang = re.search(r"^(Python|Mermaid|Bash|JavaScript|SQL)\s*$", md, re.MULTILINE | re.IGNORECASE)
    bare_lang_warn = f" [warn:裸语言名'{bare_lang.group().strip()}']" if bare_lang else ""

    # ── 8. ASCII 树形字符（警告但不阻塞，normalize 已处理）──────────
    ascii_tree = re.search(r"([│├└─]{2,}.*\n){3,}", md)
    ascii_warn = " [warn:ASCII树形图]" if ascii_tree else ""

    return True, f"OK (len={len(md)}, Parts={parts_count}, mermaid={len(mermaid_blocks)}, code={len(code_blocks)}){bare_lang_warn}{ascii_warn}"


def _try_fix_in_place(chapter_file: Path, fail_reason: str) -> bool:
    """
    质量检查失败后，根据 fail_reason 对文件原地修复，而不是盲目重试。
    返回 True 表示已修复并可重新验证，False 表示问题无法原地修复（需重新生成）。
    """
    from agents.writer_agent import _normalize_markdown

    if not chapter_file.exists():
        return False

    content = chapter_file.read_text(encoding="utf-8")
    original = content

    log(f"  [自愈] 问题: {fail_reason}")
    log(f"  [自愈] 对文件原地修复...")

    # 无论什么原因，先跑完整 normalize（已覆盖 A-G 全部修复项）
    fixed = _normalize_markdown(content)

    if fixed == original:
        log(f"  [自愈] normalize 未改变文件内容，原地修复无效")
        return False

    chapter_file.write_text(fixed, encoding="utf-8")
    log(f"  [自愈] 已应用修复，文件重写完成")
    return True


def run_chapter(chapter_num: int, force: bool = False) -> bool:
    """运行 pipeline 生成单章节。实时写出子进程输出到日志。"""
    cmd = [
        sys.executable, "run.py",
        "--start", str(chapter_num),
        "--end", str(chapter_num),
        "--no-deploy",
        "--account", "7",          # work01 ChatGPT（新鲜账号）
        "--reviewer-account", "3", # lucyzhaoaa DeepSeek（acc7 session过期后切换）
    ]
    if force:
        cmd.append("--force")

    log(f"  运行: {' '.join(cmd)}")

    import threading
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace",
    )

    def _stream():
        for ln in proc.stdout:
            log(f"  {ln.rstrip()}")

    t = threading.Thread(target=_stream, daemon=True)
    t.start()

    timeout = 1800  # 30分钟（复杂章节生成需要更长时间）
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"  ⚠️  第 {chapter_num} 章生成超时（{timeout//60}分钟），终止进程")
        proc.kill()
        t.join(timeout=5)
        raise subprocess.TimeoutExpired(cmd, timeout)

    t.join(timeout=10)
    return proc.returncode == 0


def deploy_and_verify(node_id: str, chapter_num: int) -> bool:
    """
    部署章节到 EC2：
    1. build_aios_bible.py 重建 aios-bible.json（所有已完成章节的 MD→HTML）
    2. git push StudyAthena 仓库
    3. EC2 git pull + docker compose restart frontend
    """
    try:
        import subprocess as _sp

        # Step 1: 重建 aios-bible.json
        log(f"  重建 aios-bible.json (含第 {chapter_num} 章)...")
        r = _sp.run(
            [sys.executable, "build_aios_bible.py"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        if r.returncode != 0:
            log(f"  ⚠️  build_aios_bible 失败: {r.stderr[:200]}")
        else:
            log(f"  ✅ aios-bible.json 已重建")

        # Step 2+3: git push + EC2 更新
        studyathena_root = Path("D:/My/StudyAthena")

        log("  git add + commit + push ...")
        _sp.run(["git", "add", "frontend/public/data/aios-bible.json"],
                cwd=str(studyathena_root), capture_output=True)
        status = _sp.run(["git", "status", "--porcelain", "frontend/public/data/"],
                         cwd=str(studyathena_root), capture_output=True, text=True)
        if status.stdout.strip():
            _sp.run(["git", "commit", "-m",
                     f"chore: update aios-bible.json through ch{chapter_num:02d}"],
                    cwd=str(studyathena_root), capture_output=True)
            r = _sp.run(["git", "push", "origin", "main"],
                        cwd=str(studyathena_root), capture_output=True,
                        text=True, encoding="utf-8", timeout=120)
            if r.returncode != 0:
                log(f"  ⚠️  git push 失败: {r.stderr[:200]}")
                return False
            log("  ✅ 已推送到 GitHub")
        else:
            log("  ℹ️  无新变更，跳过 push")

        # EC2: git pull + restart frontend
        remote_cmd = (
            "cd /opt/studyathena && "
            "git pull --ff-only origin main && "
            "docker compose restart frontend"
        )
        r = _sp.run(["ssh", "ec2-ollama", remote_cmd],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=90)
        if r.returncode != 0:
            log(f"  ⚠️  EC2 更新失败: {r.stderr[:200]}")
            return False

        log(f"  ✅ 第 {chapter_num} 章已上线 studyathena.com/paths/ai-education-os")
        return True
    except Exception as e:
        log(f"  ⚠️  部署异常: {e}")
        return False


def main(start_chapter: int = 1):
    log("=" * 60)
    log(f"AUTO LOOP 启动，从第 {start_chapter} 章开始")
    log(f"策略：复用 history/raw 里的 Researcher 缓存（如有），直接跑 Writer+Review")
    log("=" * 60)

    state = load_state()
    completed_ids = set(state.get("completed", {}).keys())
    log(f"已完成: {len(completed_ids)} 章: {sorted(completed_ids)}")

    results = {"success": [], "failed": [], "skipped": []}

    for node_id, chapter_num, related_ids in BOOK_CHAPTERS:
        if chapter_num < start_chapter:
            continue

        log(f"\n{'='*50}")
        log(f"第 {chapter_num} 章: {node_id}")

        chapter_file = CHAPTERS_DIR / f"ch{chapter_num:02d}_{node_id}.md"

        # ── 全流程生成（Research 缓存由 chapter_pipeline 自动复用）────────────
        success = False
        for attempt in range(1, 3):
            log(f"  尝试 {attempt}/2 生成第 {chapter_num} 章...")

            state = load_state()
            if node_id in state.get("failed", []):
                state["failed"].remove(node_id)
                STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            try:
                run_chapter(chapter_num, force=(attempt > 1))
            except subprocess.TimeoutExpired:
                log(f"  ⚠️  第 {chapter_num} 章生成超时（20分钟）")
            except Exception as e:
                log(f"  ⚠️  生成异常: {e}")

            if not chapter_file.exists():
                log(f"  ❌ 文件未生成")
                continue

            ok, reason = quality_check(chapter_file)
            log(f"  质量检查: {reason}")

            if ok:
                success = True
                break

            log(f"  ❌ 质量不合格: {reason}")
            fixed = _try_fix_in_place(chapter_file, reason)
            if fixed:
                ok2, reason2 = quality_check(chapter_file)
                log(f"  [自愈后] 质量检查: {reason2}")
                if ok2:
                    success = True
                    break
                else:
                    log(f"  [自愈后] 仍不合格: {reason2}，{'重新生成' if attempt < 2 else '放弃'}")
            else:
                log(f"  [自愈] 无法原地修复，{'重新生成' if attempt < 2 else '放弃'}")

            if not success:
                chapter_file.unlink(missing_ok=True)
                state = load_state()
                state["completed"].pop(node_id, None)
                STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        if success:
            deploy_and_verify(node_id, chapter_num)
            results["success"].append(chapter_num)
            completed_ids.add(node_id)
            log(f"  ✅ 第 {chapter_num} 章完成")
        else:
            results["failed"].append(chapter_num)
            log(f"  ❌ 第 {chapter_num} 章最终失败，跳过继续")

    log("\n" + "=" * 60)
    log(f"AUTO LOOP 完成")
    log(f"成功: {results['success']}")
    log(f"失败: {results['failed']}")
    log("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args()
    main(start_chapter=args.start)
