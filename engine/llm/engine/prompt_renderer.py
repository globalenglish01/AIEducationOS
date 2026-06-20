"""
engine/prompt_renderer.py
--------------------------
提示词模板渲染器。

模板文件是普通 Markdown，支持以下占位符：
  {{chapter}}          章节号（整数）
  {{chapter_title}}    章节标题
  {{book_title}}       书名
  {{protagonist}}      主角名
  {{memory}}           前几章记忆（由 BookMemory 提供）
  {{prev_stage_N}}     第 N 个 Stage 的内容摘要
  {{ch_info.xxx}}      章节配置字段（如 ch_info.part、ch_info.maturity）
  {{book_spec}}        书籍规范全文
  {{任意key}}          config 里的任意字段

渲染优先级：直接传入 context dict 的值 > config 字段 > 空字符串
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def render(template: str, context: dict[str, Any]) -> str:
    """把 {{key}} 占位符替换为 context 中对应的值。"""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        # 支持嵌套 key：ch_info.maturity → context["ch_info"]["maturity"]
        parts = key.split(".")
        val = context
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, "")
            else:
                val = ""
                break
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([^}]+)\}\}", replacer, template)


def load_template(prompts_dir: Path, stage: int | str) -> str:
    """加载 prompts/ 目录下的 stage 模板文件。

    文件名约定：s1.md、s2.md ... 或 glossary.md 等自定义名。
    """
    path = prompts_dir / f"s{stage}.md"
    if not path.exists():
        raise FileNotFoundError(f"提示词模板不存在: {path}")
    return path.read_text(encoding="utf-8")


def load_named_template(prompts_dir: Path, name: str) -> str:
    """加载具名模板（如 glossary.md、memory_extract.md）。"""
    path = prompts_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"提示词模板不存在: {path}")
    return path.read_text(encoding="utf-8")
