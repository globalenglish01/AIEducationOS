"""
agents/reviewer_agent.py
------------------------
Chief Reviewer Agent：对 Writer Agent 生成的章节进行质量评审。
评分 >= 95 直接通过；< 95 返回改进建议；< 85 要求重写。
使用 Browser LLM（DeepSeek，技术准确性评审能力强）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).parent.parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))

from engine.llm import create_llm

PROMPT_FILE = Path(__file__).parent / "prompts" / "reviewer.md"
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")

PASS_THRESHOLD = 95
REWRITE_THRESHOLD = 85


class ReviewerAgent:
    """
    对章节内容进行质量评审，返回评审结果。

    用法：
        agent = ReviewerAgent(provider="deepseek", account="1")
        result = agent.review(chapter_content, node_name="LLM", chapter_num=1)
        if result["passed"]:
            print("章节通过审核")
        else:
            print("需要改进:", result["critical_issues"])
        agent.close()
    """

    def __init__(self, provider: str = "deepseek", account: str = "1"):
        self.llm = create_llm(provider, account)

    def review(
        self,
        chapter_content: str,
        node_name: str = "",
        chapter_num: int = 1,
        max_retries: int = 3,
    ) -> dict:
        """
        评审章节内容，返回评审结果字典。

        返回字典结构：
        {
            "total_score": int,
            "passed": bool,
            "dimension_scores": {...},
            "critical_issues": [...],
            "improvement_suggestions": [...],
            "passed_aspects": [...],
            "rewrite_required": bool,
            "rewrite_focus": str | None,
        }
        """
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

        import threading as _threading
        import asyncio as _asyncio
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  [Reviewer] 正在评审第{chapter_num}章 [{node_name}] [尝试 {attempt}/{max_retries}]...")
                # 始终在独立线程中运行 chat()，并在该线程内清除 asyncio loop，
                # 避免 Playwright sync API 与 asyncio loop 冲突
                _result = [None, None]
                _msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user_message}]
                def _run(msgs=_msgs, llm=self.llm):
                    try:
                        # 显式清除当前线程的 asyncio loop，让 Playwright 在纯净环境运行
                        try:
                            _asyncio.set_event_loop(None)
                        except Exception:
                            pass
                        _result[0] = llm.chat(msgs)
                    except Exception as e:
                        _result[1] = e
                t = _threading.Thread(target=_run, daemon=True)
                t.start()
                t.join(timeout=600)
                if _result[1]:
                    raise _result[1]
                response = _result[0] or ""
                result = _parse_json_response(response)

                # 确保必要字段存在
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

        raise RuntimeError(f"Reviewer Agent 在 {max_retries} 次尝试后仍无法获取有效评审: {last_error}")

    def close(self):
        self.llm.close()

    def shutdown(self):
        if hasattr(self.llm, "shutdown"):
            self.llm.shutdown()

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
    # 快速测试（用一段示例章节内容）
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
