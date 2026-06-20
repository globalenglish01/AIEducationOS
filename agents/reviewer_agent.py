"""
agents/reviewer_agent.py
------------------------
Chief Reviewer Agent：对 Writer Agent 生成的章节进行质量评审。
评分 >= 95 直接通过；< 95 返回改进建议；< 85 要求重写。
使用 Browser LLM（DeepSeek，技术准确性评审能力强）。

关键设计：review() 通过独立子进程运行 DeepSeek Playwright，
完全隔离进程内 Playwright 全局状态，避免污染 Writer 所在进程的 ChatGPT Playwright。
"""
from __future__ import annotations

import json
import re
import sys
import subprocess
import tempfile
import time
from pathlib import Path

ENGINE_PATH = Path(__file__).parent.parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))

PROMPT_FILE = Path(__file__).parent / "prompts" / "reviewer.md"
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")

PASS_THRESHOLD = 95
REWRITE_THRESHOLD = 85

# 子进程 runner 脚本（独立进程运行 DeepSeek，结果写到临时 JSON 文件）
_RUNNER_SCRIPT = """
import sys, json, os
sys.path.insert(0, sys.argv[1])  # ENGINE_INNER
sys.path.insert(0, sys.argv[2])  # ENGINE_PATH
out_path = sys.argv[3]
provider = sys.argv[4]
account = sys.argv[5]
msgs_path = sys.argv[6]

from engine.llm import create_llm
msgs = json.loads(open(msgs_path, encoding="utf-8").read())
llm = create_llm(provider, account)
try:
    resp = llm.chat(msgs)
    result = {"ok": True, "response": resp}
except Exception as e:
    result = {"ok": False, "error": str(e)}
finally:
    try:
        llm.shutdown()
    except Exception:
        pass

open(out_path, "w", encoding="utf-8").write(json.dumps(result, ensure_ascii=False))
"""


class ReviewerAgent:
    """
    对章节内容进行质量评审，返回评审结果。
    每次 review() 启动独立子进程运行 DeepSeek，避免 Playwright 进程级状态污染 Writer。
    """

    def __init__(self, provider: str = "deepseek", account: str = "1"):
        self._provider = provider
        self._account = account

    def review(
        self,
        chapter_content: str,
        node_name: str = "",
        chapter_num: int = 1,
        max_retries: int = 3,
    ) -> dict:
        user_message = f"""请评审第{chapter_num}章（{node_name}）的内容：

---章节内容开始---
{chapter_content}
---章节内容结束---

评审要点：
1. 检查15个Part是否全部存在且内容充实
2. 验证代码示例是否可以真实运行（语法是否正确）
3. 评估认知冲突是否真实有效
4. 检查技术描述是否准确（如有明显错误请指出）
5. 评估面试题质量（是否是真实面试会问的）

请严格按JSON格式输出评审结果，不要有任何额外文字。"""

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  [Reviewer] 正在评审第{chapter_num}章 [{node_name}] [尝试 {attempt}/{max_retries}]...")
                response = self._run_in_subprocess(user_message, attempt)
                result = _parse_json_response(response)

                result.setdefault("total_score", 0)
                result.setdefault("passed", result["total_score"] >= PASS_THRESHOLD)
                result.setdefault("rewrite_required", result["total_score"] < REWRITE_THRESHOLD)
                result.setdefault("critical_issues", [])
                result.setdefault("improvement_suggestions", [])
                result.setdefault("passed_aspects", [])
                result.setdefault("rewrite_focus", None)

                score = result["total_score"]
                status = "通过" if result["passed"] else ("需重写" if result["rewrite_required"] else "需改进")
                print(f"  [Reviewer] 评审完成：{score}分 → {status}")
                return result

            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                print(f"  [Reviewer] JSON解析失败（尝试{attempt}）: {e}")
                if attempt < max_retries:
                    user_message += "\n\n[注意：请严格按JSON格式输出，不要有任何额外文字或代码块标记]"
            except Exception as e:
                last_error = e
                print(f"  [Reviewer] 子进程评审失败（尝试{attempt}）: {e}")
                if attempt < max_retries:
                    time.sleep(5)

        raise RuntimeError(f"Reviewer Agent 在 {max_retries} 次尝试后仍无法获取有效评审: {last_error}")

    def _run_in_subprocess(self, user_message: str, attempt: int) -> str:
        """在独立子进程中运行 DeepSeek，返回 LLM 响应文本。"""
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            runner_path = tmpdir / "reviewer_runner.py"
            msgs_path = tmpdir / "msgs.json"
            out_path = tmpdir / "result.json"

            runner_path.write_text(_RUNNER_SCRIPT, encoding="utf-8")
            msgs_path.write_text(json.dumps(msgs, ensure_ascii=False), encoding="utf-8")

            cmd = [
                sys.executable,
                str(runner_path),
                str(ENGINE_INNER),
                str(ENGINE_PATH),
                str(out_path),
                self._provider,
                self._account,
                str(msgs_path),
            ]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            )

            def _stream():
                for ln in proc.stdout:
                    print(f"    [Reviewer-proc] {ln.rstrip()}", flush=True)

            import threading
            t = threading.Thread(target=_stream, daemon=True)
            t.start()

            try:
                proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                proc.kill()
                t.join(timeout=5)
                raise RuntimeError("Reviewer 子进程超时（600秒）")

            t.join(timeout=5)

            if not out_path.exists():
                raise RuntimeError(f"Reviewer 子进程未生成输出文件（returncode={proc.returncode}）")

            result_data = json.loads(out_path.read_text(encoding="utf-8"))
            if not result_data.get("ok"):
                raise RuntimeError(f"Reviewer 子进程异常: {result_data.get('error')}")

            return result_data["response"]

    def close(self):
        pass

    def shutdown(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _parse_json_response(text: str) -> dict:
    """从 LLM 响应中提取 JSON 内容。"""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError(f"无法从响应中提取JSON: {text[:200]}")


if __name__ == "__main__":
    sample_chapter = """# 第1章 LLM：一个超级接龙游手 [L0-L1]

## Part 1: 为什么要学这个？
很多人以为LLM是一个知识库...

## Part 2: 学习路径定位
L0 → L1 → L2...

## Part 3: 用生活理解它
LLM就像接龙游戏...
"""
    with ReviewerAgent(provider="deepseek", account="1") as agent:
        result = agent.review(sample_chapter, node_name="LLM", chapter_num=1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
