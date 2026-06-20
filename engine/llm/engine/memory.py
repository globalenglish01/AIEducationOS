"""
engine/memory.py
----------------
书籍跨章节记忆管理。

每章完成后，用 LLM 从内容中提取关键记忆点（人物状态/术语/案例/金句），
注入到后续章节的 Prompt 中，保持故事和技术的跨章一致性。

数据存储：output/{book_id}/memory.md
格式：
  ## 第N章记忆
  （LLM 提取的结构化摘要）
  ---
"""
from __future__ import annotations

import re
from pathlib import Path


MAX_MEMORY_CHAPTERS = 3   # 注入 Prompt 时最多取最近 N 章记忆


class BookMemory:
    def __init__(self, book_output_dir: Path):
        self._file = book_output_dir / "memory.md"
        book_output_dir.mkdir(parents=True, exist_ok=True)

    def load(self, before_chapter: int | None = None) -> str:
        """加载记忆（可选：只取 before_chapter 之前的章节，最多 MAX_MEMORY_CHAPTERS 章）。"""
        if not self._file.exists():
            return ""
        text = self._file.read_text(encoding="utf-8")
        # 按章节切分
        chapters = re.split(r"(?=## 第\d+章记忆)", text)
        chapters = [c.strip() for c in chapters if c.strip()]

        if before_chapter is not None:
            chapters = [c for c in chapters if _chapter_num(c) < before_chapter]

        recent = chapters[-MAX_MEMORY_CHAPTERS:]
        return "\n\n".join(recent)

    def update(self, chapter: int, memory_text: str):
        """保存/覆盖某章的记忆。"""
        existing = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        # 删除该章旧记忆（如存在）
        pattern = rf"## 第{chapter}章记忆.*?(?=## 第\d+章记忆|\Z)"
        existing = re.sub(pattern, "", existing, flags=re.DOTALL).strip()
        new_block = f"## 第{chapter}章记忆\n\n{memory_text.strip()}\n\n---"
        self._file.write_text(existing + "\n\n" + new_block + "\n", encoding="utf-8")

    def extract_prompt(self, chapter: int, content: str, protagonist: str, book_title: str) -> str:
        """生成"从本章内容提取记忆"的 Prompt，供外部调用 llm.chat()。"""
        return f"""请从以下《{book_title}》第{chapter}章内容中提取结构化记忆，供后续章节保持一致性。

主角：{protagonist}

请提取并输出以下内容（200字以内）：
1. **主角状态**：{protagonist}本章的状态变化、情绪、重要决定
2. **关键术语**：本章引入的重要技术术语（3-5个）及其在书中的定义
3. **重要案例**：本章出现的具体公司/项目/代码案例（供后续章节引用）
4. **导师金句**：本章导师说的最重要一句话
5. **技术连续性**：下一章需要注意的技术前置条件

格式：直接输出结构化内容，不要加任何前置说明。

---

以下是章节内容：

{content[:6000]}
"""


def _chapter_num(block: str) -> int:
    m = re.search(r"## 第(\d+)章记忆", block)
    return int(m.group(1)) if m else -1
