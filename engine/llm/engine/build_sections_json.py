"""
engine/build_sections_json.py
------------------------------
把 progress/ 下的 chNN_s*.md 按节展开成前端 JSON。
作为库使用，由 main.py 的 _do_build 调用，不直接运行。

主要接口：
  build(input_dir, out_file, title, cfg_file, provider) -> int
  build_merged(ds_dir, gpt_dir, out_file, title, cfg_file) -> int
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

from md_renderer import render as md_render



# ── 内容处理 ──────────────────────────────────────────────────────────────────

def _extract_title(content: str, ch_num: int, s_num: int) -> str:
    """从 MD 或 HTML 内容中提取可读的标题。"""
    # 优先匹配"第N章："开头的行（不需要 # 前缀，bible S5 常用此格式；要求有冒号避免匹配元说明碎片）
    for line in content.split("\n")[:5]:
        stripped = line.strip()
        if re.match(r'^第\d+章[：:]', stripped) and len(stripped) > 5:
            return stripped[:80]
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("####"):
            candidate = stripped.lstrip("#").strip()
            if candidate and not re.match(r'^[./\\]|^\d+\.|^```', candidate):
                return candidate
    h_match = re.search(r'<h[123][^>]*>(.*?)</h[123]>', content, re.DOTALL)
    if h_match:
        return re.sub(r'<[^>]+>', '', h_match.group(1)).strip()
    return f"第{ch_num}章 第{s_num}节"


def _is_html_content(content: str) -> bool:
    """判断内容是否已经是渲染后的 HTML（而非 Markdown）。"""
    first = next((l.strip() for l in content.split("\n") if l.strip()), "")
    return first.startswith("<")


def _render(content: str, provider: str = "deepseek") -> str:
    """将内容渲染为 HTML。已是 HTML 则直接加 badge；否则经过 md_renderer。"""
    if _is_html_content(content):
        from md_renderer import _postprocess_mermaid  # noqa: local import OK (same package)
        badge = f'<div class="provider-badge" data-provider="{provider}">由 {provider.capitalize()} 生成</div>\n'
        return badge + _postprocess_mermaid(content)
    return md_render(content, provider=provider)


# ── 核心构建逻辑 ──────────────────────────────────────────────────────────────

_MIN_S5_LEN = 3000  # S5 清洗后的最小有效长度（真实章节内容 >= 8500字，格式模板碎片 < 1500字）


def _strip_meta_preamble(content: str) -> str:
    """
    去掉 ChatGPT S5 文件开头的元说明（'无法修订/当前输入...'等）。
    从第一个 # 标题行或第N章标题行开始保留实际内容。
    若找不到则返回空字符串（调用方应降级到 S2/S3）。
    """
    lines = content.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#"):
            return "\n".join(lines[i:]).strip()
        # 第N章：Title 格式（要求有冒号，避免误匹配"第5章后半部分..."等元说明碎片）
        if re.match(r"^第\d+章[：:]", s):
            return "\n".join(lines[i:]).strip()
    return ""


def _collect_files(input_dir: Path) -> dict[tuple[int,int], Path]:
    """返回 {(ch_num, s_num): Path} 映射，仅包含 ch*_s*.md 文件。"""
    result: dict[tuple[int,int], Path] = {}
    for f in input_dir.glob("ch*_s*.md"):
        m = re.match(r"ch(\d+)_s(\d+)\.md$", f.name)
        if m:
            result[(int(m.group(1)), int(m.group(2)))] = f
    return result


def build_merged(ds_dir: Path, gpt_dir: Path, out_file: Path, title: str,
                 cfg_file: Path) -> int:
    """
    合并 deepseek（s1-s4）和 chatgpt（s5-s6）目录，优先展示最佳版本：
      1. 优先用 S5（ChatGPT 修订版），清洗掉元说明前缀后，每章一条目
      2. S5 不存在或清洗后内容太短（< _MIN_S5_LEN），降级到 S2+S3（DeepSeek 初稿）
      3. S1/S4/S6 始终跳过（施工图/审稿/评分报告，内部文档）
    """
    cfg          = json.loads(cfg_file.read_text(encoding="utf-8"))
    chapter_info = cfg.get("chapters", {})

    ds_files  = _collect_files(ds_dir)  if ds_dir.exists()  else {}
    gpt_files = _collect_files(gpt_dir) if gpt_dir.exists() else {}

    all_ch_nums = sorted(set(ch for ch, _ in list(ds_files.keys()) + list(gpt_files.keys())))

    chapters = []
    n = 0

    for ch_num in all_ch_nums:
        ch_cfg   = chapter_info.get(str(ch_num), {})
        ch_title = ch_cfg.get("title", f"第{ch_num}章")
        part     = "序章" if ch_num == 0 else f"第{ch_num}章：{ch_title}"

        # ── 尝试 S5（ChatGPT 修订版）────────────────────────────────────────
        s5_file = gpt_files.get((ch_num, 5))
        if s5_file:
            raw     = s5_file.read_text(encoding="utf-8").strip()
            cleaned = _strip_meta_preamble(raw)
            if len(cleaned) >= _MIN_S5_LEN:
                title_s = _extract_title(cleaned, ch_num, 5)
                chapters.append({
                    "n":       n,
                    "title":   title_s,
                    "part":    part,
                    "done":    True,
                    "content": _render(cleaned, provider="chatgpt"),
                })
                n += 1
                continue  # S5 已用，不再添加 S2/S3

        # ── 降级到 S2 + S3（DeepSeek 初稿），合并为一个章节条目 ──────────────
        combined_html_parts = []
        combined_title = None
        combined_provider = "deepseek"
        for s_num in (2, 3):
            md_file = ds_files.get((ch_num, s_num)) or gpt_files.get((ch_num, s_num))
            if not md_file:
                continue
            provider = "chatgpt" if (ch_num, s_num) in gpt_files else "deepseek"
            # 优先使用预渲染的 .html 文件（格式更完整）
            html_file = md_file.with_suffix(".html")
            if html_file.exists():
                from md_renderer import _postprocess_mermaid
                html_content = html_file.read_text(encoding="utf-8").strip()
                # 去掉 html 文件里已有的 provider-badge（build 时会重新加）
                html_content = re.sub(r'<div class="provider-badge"[^>]*>.*?</div>\s*', '', html_content, flags=re.DOTALL)
                html_content = _postprocess_mermaid(html_content)
                combined_html_parts.append(html_content)
            else:
                raw = md_file.read_text(encoding="utf-8").strip()
                combined_html_parts.append(_render(raw, provider=provider))
            if combined_title is None:
                raw_for_title = md_file.read_text(encoding="utf-8").strip()
                combined_title = _extract_title(raw_for_title, ch_num, s_num)
            if provider == "chatgpt":
                combined_provider = "chatgpt"

        if combined_html_parts:
            badge = f'<div class="provider-badge" data-provider="{combined_provider}">由 {combined_provider.capitalize()} 生成</div>\n'
            merged_html = badge + '\n<hr class="section-divider">\n'.join(combined_html_parts)
            chapters.append({
                "n":       n,
                "title":   combined_title or f"第{ch_num}章",
                "part":    part,
                "done":    True,
                "content": merged_html,
            })
            n += 1

    out = {
        "title":    title,
        "subtitle": f"章节版 · {n} 节已完成 · 持续更新中",
        "chapters": chapters,
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return n


def build(input_dir: Path, out_file: Path, title: str, cfg_file: Path,
          provider: str = "deepseek") -> int:
    """
    扫描 input_dir 下的 ch*_s*.md 文件，渲染后写入 out_file。
    返回生成的节数。
    """
    cfg          = json.loads(cfg_file.read_text(encoding="utf-8"))
    chapter_info = cfg.get("chapters", {})

    md_files = sorted(
        input_dir.glob("ch*_s*.md"),
        key=lambda f: (
            int(re.search(r"ch(\d+)_s(\d+)\.md$", f.name).group(1)),
            int(re.search(r"ch(\d+)_s(\d+)\.md$", f.name).group(2)),
        )
    )

    chapters = []
    n = 0

    for md_file in md_files:
        m = re.match(r"ch(\d+)_s(\d+)\.md$", md_file.name)
        if not m:
            continue

        ch_num  = int(m.group(1))
        s_num   = int(m.group(2))
        content = md_file.read_text(encoding="utf-8").strip()
        title_s = _extract_title(content, ch_num, s_num)

        ch_cfg    = chapter_info.get(str(ch_num), {})
        ch_title  = ch_cfg.get("title", f"第{ch_num}章")
        # 优先使用 chapters.json 里的 part 字段（面试宝典按 Part1/Part2 分组），
        # 否则按章节编号自动生成
        if "part" in ch_cfg and ch_cfg["part"] not in ("序章", ""):
            part = ch_cfg["part"] if ch_num != 0 else "序章"
        else:
            part = "序章" if ch_num == 0 else f"第{ch_num}章：{ch_title}"
        content_html = _render(content, provider=provider)

        chapters.append({
            "n":       n,
            "title":   title_s,
            "part":    part,
            "done":    True,
            "content": content_html,
        })
        n += 1

    out = {
        "title":    title,
        "subtitle": f"章节版 · {n} 节已完成 · 持续更新中",
        "chapters": chapters,
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return n


# CLI 入口已移除，此模块作为库使用（由 main.py 的 _do_build 调用）
# 入口：main.py build <book_id>
