"""
engine/pipeline.py
------------------
通用书籍生产流水线核心引擎。

流程（对每一章，顺序执行每个 Stage）：
  1. 跳过已完成的 Stage（断点续跑）
  2. 加载书籍记忆（前几章摘要）
  3. 加载前序 Stage 内容（供上下文参考）
  4. 渲染提示词模板 → 完整 Prompt
  5. 调用 LLM（DeepSeek/ChatGPT）
  6. 保存结果到文件
  7. 最后一个 Stage 完成后：提取并更新书籍记忆

全部逻辑与书籍内容无关。书与书的区别只在 config + prompts 目录。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from engine.llm import BaseLLM
from engine.progress import BookProgress
from engine.memory import BookMemory
from engine.prompt_renderer import render, load_template, load_named_template


class Pipeline:
    def __init__(
        self,
        book_id: str,
        config: dict,
        prompts_dir: Path,
        output_dir: Path,
        llm: BaseLLM,
    ):
        self.book_id = book_id
        self.config = config
        self.prompts_dir = prompts_dir
        self.llm = llm

        self.output_dir = output_dir / book_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.progress = BookProgress(self.output_dir)
        self.memory = BookMemory(self.output_dir)

        # 从 config 读取基础信息
        self.book_title: str = config.get("book_title", book_id)
        self.protagonist: str = config.get("protagonist", "主角")
        self.chapters: dict = config.get("chapters", {})
        self.stages: list[dict] = config.get("stages", [])  # [{id, name, provider}]
        self.total_stages = len(self.stages)

    # ──────────────────────────────────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────────────────────────────────

    def run_all(self, from_chapter: int = 0):
        """顺序处理所有章节。"""
        chapter_ids = sorted(int(k) for k in self.chapters.keys())
        pending = [ch for ch in chapter_ids if ch >= from_chapter
                   and not self.progress.chapter_done(ch, self.total_stages)]
        total = len(pending)
        print(f"[{self.book_id}] 共 {total} 章待处理（总 {len(chapter_ids)} 章）")
        for i, ch in enumerate(pending, 1):
            print(f"\n{'='*60}")
            print(f"[{self.book_id}] 第 {ch} 章 ({i}/{total}): {self.chapters[str(ch)].get('title','')}")
            print(f"{'='*60}")
            self.run_chapter(ch)

    def run_chapter(self, chapter: int):
        """处理单章的所有 Stage。"""
        ch_info = self.chapters.get(str(chapter))
        if ch_info is None:
            print(f"  ⚠️  章节 {chapter} 不在 config 中，跳过")
            return

        for stage_cfg in self.stages:
            stage_id = stage_cfg["id"]
            stage_name = stage_cfg.get("name", f"Stage {stage_id}")

            if self.progress.is_done(chapter, stage_id):
                print(f"  ⏭  Stage {stage_id} ({stage_name})：已完成，跳过")
                continue

            print(f"  ▶  Stage {stage_id} ({stage_name})...", end="", flush=True)
            try:
                result = self._run_stage(chapter, stage_id, ch_info)
                if result:
                    self._save_stage(chapter, stage_id, result)
                    self.progress.set_done(chapter, stage_id)
                    print(f" ✅ ({len(result)} chars)")
                else:
                    print(f" ❌ LLM 返回空内容")
            except KeyboardInterrupt:
                print("\n[Pipeline] 用户中断")
                raise
            except Exception as e:
                print(f" ❌ 异常: {e}")
                time.sleep(5)
                continue

            time.sleep(2)  # 避免速率限制

        # 章节全部 Stage 完成后提取记忆
        if self.progress.chapter_done(chapter, self.total_stages):
            self._extract_memory(chapter)

    # ──────────────────────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────────────────────

    def _run_stage(self, chapter: int, stage_id: int, ch_info: dict) -> str:
        """渲染 Prompt → 调用 LLM → 返回结果文本。"""
        template = load_template(self.prompts_dir, stage_id)

        # 构造渲染上下文
        context = self._build_context(chapter, stage_id, ch_info)
        prompt = render(template, context)

        return self.llm.chat([{"role": "user", "content": prompt}])

    def _build_context(self, chapter: int, stage_id: int, ch_info: dict) -> dict[str, Any]:
        """构造提示词渲染所需的全部变量。"""
        # 前序 Stage 内容
        prev_stages = {}
        for s in range(1, stage_id):
            content = self._load_stage(chapter, s)
            if content:
                # Stage 内容按位置截断（越早的 stage 给越少上下文）
                max_chars = self._prev_stage_max_chars(stage_id, s)
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n\n...[内容已截断]..."
                prev_stages[f"prev_stage_{s}"] = content

        # 书籍记忆
        memory_text = self.memory.load(before_chapter=chapter)

        # book_spec（规范文件，如果存在）
        spec_text = ""
        spec_file = self.prompts_dir.parent / "book_spec.md"
        if spec_file.exists():
            spec_text = spec_file.read_text(encoding="utf-8")

        ctx: dict[str, Any] = {
            "chapter": chapter,
            "chapter_title": ch_info.get("title", ""),
            "book_title": self.book_title,
            "protagonist": self.protagonist,
            "memory": memory_text,
            "book_spec": spec_text,
            "ch_info": ch_info,
            **prev_stages,
            # ch_info 的所有字段也直接展开（方便模板里用 {{part}}、{{maturity}} 等）
            **{k: v for k, v in ch_info.items() if isinstance(v, (str, int, float))},
        }
        # 列表字段转逗号字符串
        for k, v in ch_info.items():
            if isinstance(v, list):
                ctx[k] = "、".join(str(i) for i in v)

        return ctx

    def _prev_stage_max_chars(self, current_stage: int, prev_stage: int) -> int:
        """根据 stage 关系决定截断长度（越近越长）。"""
        distance = current_stage - prev_stage
        if distance == 1:
            return 8000
        elif distance == 2:
            return 4000
        else:
            return 800

    def _save_stage(self, chapter: int, stage_id: int, content: str):
        path = self.output_dir / f"ch{chapter:02d}_s{stage_id}.md"
        path.write_text(content, encoding="utf-8")

    def _load_stage(self, chapter: int, stage_id: int) -> str:
        path = self.output_dir / f"ch{chapter:02d}_s{stage_id}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _extract_memory(self, chapter: int):
        """章节完成后，用 LLM 提取跨章记忆并保存。"""
        # 取最后一个有实质内容的 Stage（通常是最终稿）
        content = ""
        for s in range(self.total_stages, 0, -1):
            content = self._load_stage(chapter, s)
            if len(content) > 200:
                break
        if not content:
            return

        # 尝试加载专用 memory_extract 模板，否则用 memory.py 默认 Prompt
        try:
            template = load_named_template(self.prompts_dir, "memory_extract")
            ctx = {
                "chapter": chapter,
                "chapter_title": self.chapters[str(chapter)].get("title", ""),
                "book_title": self.book_title,
                "protagonist": self.protagonist,
                "content": content[:6000],
            }
            prompt = render(template, ctx)
        except FileNotFoundError:
            prompt = self.memory.extract_prompt(chapter, content, self.protagonist, self.book_title)

        print(f"  📝 提取第 {chapter} 章记忆...", end="", flush=True)
        try:
            memory_text = self.llm.chat([{"role": "user", "content": prompt}])
            self.memory.update(chapter, memory_text)
            print(f" ✅")
        except Exception as e:
            print(f" ⚠️  记忆提取失败（{e}），跳过")
