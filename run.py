"""
run.py — AI Education OS 主入口

---------------------------------
用法：

  # 生成全书（从第1章开始）
  python run.py

  # 只生成第1-5章
  python run.py --start 1 --end 5

  # 从第6章继续（断点续跑）
  python run.py --start 6

  # 强制重新生成第1章
  python run.py --start 1 --end 1 --force

  # 指定 LLM 账号
  python run.py --start 1 --end 3 --account 2

  # 只生成单个章节（快速测试）
  python run.py --start 1 --end 1

环境要求：
  - Python 3.10+
  - pyyaml: pip install pyyaml
  - Playwright 浏览器（已在 engine/llm/ 中配置）
  - DeepSeek 和 ChatGPT 账号（在 engine/llm/accounts.json 中配置）
"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保 agents/ 可以 import engine/llm
ENGINE_PATH = Path(__file__).parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"  # chatgpt_bot / deepseek_bot 所在目录
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))
sys.path.insert(0, str(Path(__file__).parent))

from agents.chapter_pipeline import run_book


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Education OS — 书籍章节生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--start", type=int, default=1, help="起始章节号（默认：1）")
    parser.add_argument("--end", type=int, default=None, help="结束章节号（默认：全部）")
    parser.add_argument(
        "--researcher", default="deepseek",
        choices=["deepseek", "chatgpt"],
        help="Researcher Agent 使用的 LLM（默认：deepseek）"
    )
    parser.add_argument(
        "--writer", default="chatgpt",
        choices=["deepseek", "chatgpt"],
        help="Writer Agent 使用的 LLM（默认：chatgpt）"
    )
    parser.add_argument(
        "--reviewer", default="deepseek",
        choices=["deepseek", "chatgpt"],
        help="Reviewer Agent 使用的 LLM（默认：deepseek）"
    )
    parser.add_argument("--account", default="1", help="LLM 账号编号 1-6（默认：1）")
    parser.add_argument("--reviewer-account", default=None, help="DeepSeek Reviewer专用账号编号（默认同--account）")
    parser.add_argument("--force", action="store_true", help="强制重新生成（忽略已有文件）")
    parser.add_argument("--no-deploy", action="store_true",
                        help="生成后不自动部署到 StudyAthena（默认开启自动部署）")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Education OS -- 书籍生成系统")
    print("=" * 60)
    print(f"  章节范围: {args.start} -> {args.end or '全部'}")
    reviewer_acc = args.reviewer_account or args.account
    print(f"  Researcher: {args.researcher} (account={args.account})")
    print(f"  Writer:     {args.writer} (account={args.account})")
    print(f"  Reviewer:   {args.reviewer} (account={reviewer_acc})")
    print(f"  强制重跑:   {args.force}")
    print(f"  自动部署:   {'关闭' if args.no_deploy else '开启 (studyathena.com)'}")
    print("=" * 60)

    run_book(
        start_chapter=args.start,
        end_chapter=args.end,
        researcher_provider=args.researcher,
        writer_provider=args.writer,
        reviewer_provider=args.reviewer,
        account=args.account,
        reviewer_account=reviewer_acc,
        force_rerun=args.force,
        auto_deploy=not args.no_deploy,
    )


if __name__ == "__main__":
    main()
