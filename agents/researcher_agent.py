"""
agents/researcher_agent.py
--------------------------
Researcher Agent：为每个章节收集认知冲突、生活类比、真实案例、面试题等素材。
使用 Browser LLM（DeepSeek/ChatGPT），不调用 Claude API。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 将 engine/llm 加入路径
ENGINE_PATH = Path(__file__).parent.parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))

from engine.llm import create_llm
from agents.knowledge_loader import build_chapter_context, load_nodes_by_ids

PROMPT_FILE = Path(__file__).parent / "prompts" / "researcher.md"
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")


class ResearcherAgent:
    """
    给定一个主知识节点（和可选的相关节点），生成章节素材。

    用法：
        agent = ResearcherAgent(provider="deepseek", account="1")
        result = agent.research(primary_node, related_nodes=[...])
        agent.close()
    """

    def __init__(self, provider: str = "deepseek", account: str = "1"):
        self.llm = create_llm(provider, account)
        self._provider = provider

    def research(
        self,
        primary_node: dict,
        related_nodes: list[dict] | None = None,
        max_retries: int = 3,
    ) -> dict:
        """
        执行研究任务，返回结构化素材字典。
        如果 LLM 返回非合法 JSON，自动重试（最多 max_retries 次）。
        """
        context = build_chapter_context(primary_node, related_nodes)
        node_name = primary_node.get("name", "")
        node_id = primary_node.get("id", "")
        level = primary_node.get("level", "")

        user_message = f"""请为以下知识节点收集章节素材：

节点信息：
{context}

要求：
- 这是一本面向{level}层级工程师的书籍
- 认知冲突要贴近中国AI工程师的真实工作场景
- 真实案例要有具体数字（如"从3秒降到200ms"）
- 面试题要是真实面试中的问题，不是教科书式提问

请严格按JSON格式输出，不要有任何额外文字。"""

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  [Researcher] 正在研究 {node_id} ({node_name}) [尝试 {attempt}/{max_retries}]...")
                response = self.llm.chat([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ])
                result = _parse_json_response(response)
                result["_node_id"] = node_id
                result["_node_name"] = node_name
                result["_level"] = level
                print(f"  [Researcher] {node_id} 素材收集完成")
                return result
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                print(f"  [Researcher] JSON解析失败（尝试{attempt}）: {e}")
                if attempt < max_retries:
                    # 提示重新输出
                    user_message += "\n\n[注意：上次输出的JSON格式有误，请严格按JSON格式重新输出，不要包含代码块标记以外的任何内容]"

        raise RuntimeError(
            f"Researcher Agent 在 {max_retries} 次尝试后仍无法获取有效JSON: {last_error}"
        )

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
    """从 LLM 响应中提取 JSON 内容（处理 ```json ... ``` 包裹的情况）。"""
    text = text.strip()

    # 尝试直接解析
    if text.startswith("{"):
        return json.loads(text)

    # 提取 ```json ... ``` 块
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # 尝试找第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError(f"无法从响应中提取JSON，响应前200字符: {text[:200]}")


if __name__ == "__main__":
    # 快速测试：研究 LLM 节点
    from agents.knowledge_loader import load_node

    node = load_node("KN-C-000001")
    with ResearcherAgent(provider="deepseek", account="1") as agent:
        result = agent.research(node)
        print(json.dumps(result, ensure_ascii=False, indent=2))
