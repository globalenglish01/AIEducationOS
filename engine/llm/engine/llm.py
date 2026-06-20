"""
engine/llm.py
-------------
LLM 接口层。使用系统内置的 engine/llm_provider.py。
bot 文件（chatgpt_bot / deepseek_bot）已内置在 engine/，无需外部路径。

用法：
    from engine.llm import create_llm
    llm = create_llm("deepseek", account="1")
    answer = llm.chat([{"role": "user", "content": "你好"}])
    llm.close()
"""
from __future__ import annotations

from engine.llm_provider import BaseLLM, LLMResponse, create_llm  # noqa: F401

__all__ = ["BaseLLM", "LLMResponse", "create_llm"]
