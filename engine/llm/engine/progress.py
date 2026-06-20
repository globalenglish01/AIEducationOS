"""
engine/progress.py
------------------
断点续跑：记录每本书每章每 Stage 的完成状态。

数据结构（output/{book_id}/progress.json）：
{
  "0": {"stages": {"1": "done", "2": "done", ...}, "word_count": 0},
  "1": {"stages": {"1": "pending", ...}},
  ...
}
"""
from __future__ import annotations

import json
from pathlib import Path


class BookProgress:
    def __init__(self, book_output_dir: Path):
        self._file = book_output_dir / "progress.json"
        book_output_dir.mkdir(parents=True, exist_ok=True)
        self._data: dict = json.loads(self._file.read_text(encoding="utf-8")) if self._file.exists() else {}

    def _save(self):
        self._file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_done(self, chapter: int, stage: int) -> bool:
        return self._data.get(str(chapter), {}).get("stages", {}).get(str(stage)) == "done"

    def set_done(self, chapter: int, stage: int):
        ch = self._data.setdefault(str(chapter), {"stages": {}, "word_count": 0})
        ch["stages"][str(stage)] = "done"
        self._save()

    def set_word_count(self, chapter: int, count: int):
        self._data.setdefault(str(chapter), {"stages": {}, "word_count": 0})["word_count"] = count
        self._save()

    def chapter_done(self, chapter: int, total_stages: int) -> bool:
        stages = self._data.get(str(chapter), {}).get("stages", {})
        return all(stages.get(str(s)) == "done" for s in range(1, total_stages + 1))

    def pending_chapters(self, total_chapters: int, total_stages: int) -> list[int]:
        return [ch for ch in range(total_chapters) if not self.chapter_done(ch, total_stages)]

    def summary(self, total_chapters: int, total_stages: int) -> str:
        lines = []
        for ch in range(total_chapters):
            stages = self._data.get(str(ch), {}).get("stages", {})
            done = sum(1 for s in range(1, total_stages + 1) if stages.get(str(s)) == "done")
            mark = "✅" if done == total_stages else f"[{done}/{total_stages}]"
            lines.append(f"  ch{ch:02d}: {mark}")
        return "\n".join(lines)
