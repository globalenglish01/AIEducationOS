"""
build_aios_bible.py
===================
把 output/chapters/ 里已生成的 MD 文件打包成
D:/My/StudyAthena/frontend/public/data/aios-bible.json

格式与 claude-bible.json 完全一致：
{
  "title": "...",
  "subtitle": "...",
  "chapters": [
    { "n": 1, "title": "...", "part": "...", "done": true, "content": "<html>" },
    ...
  ]
}

用法：
    python build_aios_bible.py          # 构建并写入
    python build_aios_bible.py --dry    # 只打印，不写文件
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CHAPTERS_DIR = ROOT / "output" / "chapters"
OUT_PATH = Path("D:/My/StudyAthena/frontend/public/data/aios-bible.json")

# ── 章节元数据（编号→节点→标题→所属 Part）──────────────────────────────────
# part 分组与 ai-education-os 路线的九大模块对应
CHAPTER_META: list[dict] = [
    # Part 1: LLM 基础
    {"n": 1,  "node": "KN-C-000001", "part": "第一部分：LLM 基础"},
    {"n": 2,  "node": "KN-C-000002", "part": "第一部分：LLM 基础"},
    {"n": 3,  "node": "KN-C-000003", "part": "第一部分：LLM 基础"},
    {"n": 4,  "node": "KN-C-000004", "part": "第一部分：LLM 基础"},
    {"n": 5,  "node": "KN-C-000005", "part": "第一部分：LLM 基础"},
    # Part 2: Prompt Engineering
    {"n": 6,  "node": "KN-C-000010", "part": "第二部分：Prompt Engineering"},
    {"n": 7,  "node": "KN-P-000001", "part": "第二部分：Prompt Engineering"},
    {"n": 8,  "node": "KN-P-000002", "part": "第二部分：Prompt Engineering"},
    {"n": 9,  "node": "KN-P-000003", "part": "第二部分：Prompt Engineering"},
    {"n": 10, "node": "KN-P-000004", "part": "第二部分：Prompt Engineering"},
    # Part 3: Agent
    {"n": 11, "node": "KN-C-000020", "part": "第三部分：Agent 架构"},
    {"n": 12, "node": "KN-C-000021", "part": "第三部分：Agent 架构"},
    {"n": 13, "node": "KN-C-000022", "part": "第三部分：Agent 架构"},
    {"n": 14, "node": "KN-C-000023", "part": "第三部分：Agent 架构"},
    {"n": 15, "node": "KN-C-000024", "part": "第三部分：Agent 架构"},
    # Part 4: RAG
    {"n": 16, "node": "KN-C-000030", "part": "第四部分：RAG 与知识检索"},
    {"n": 17, "node": "KN-C-000031", "part": "第四部分：RAG 与知识检索"},
    {"n": 18, "node": "KN-C-000032", "part": "第四部分：RAG 与知识检索"},
    {"n": 19, "node": "KN-C-000033", "part": "第四部分：RAG 与知识检索"},
    {"n": 20, "node": "KN-C-000034", "part": "第四部分：RAG 与知识检索"},
    {"n": 21, "node": "KN-C-000035", "part": "第四部分：RAG 与知识检索"},
    # Part 5: Workflow
    {"n": 22, "node": "KN-C-000025", "part": "第五部分：Workflow 与状态机"},
    {"n": 23, "node": "KN-C-000026", "part": "第五部分：Workflow 与状态机"},
    {"n": 24, "node": "KN-C-000027", "part": "第五部分：Workflow 与状态机"},
    {"n": 25, "node": "KN-C-000028", "part": "第五部分：Workflow 与状态机"},
    # Part 6: Evaluation
    {"n": 26, "node": "KN-C-000036", "part": "第六部分：Evaluation 与测试"},
    {"n": 27, "node": "KN-C-000037", "part": "第六部分：Evaluation 与测试"},
    {"n": 28, "node": "KN-C-000038", "part": "第六部分：Evaluation 与测试"},
    {"n": 29, "node": "KN-C-000039", "part": "第六部分：Evaluation 与测试"},
    # Part 7: Security
    {"n": 30, "node": "KN-C-000040", "part": "第七部分：安全与防护"},
    {"n": 31, "node": "KN-C-000041", "part": "第七部分：安全与防护"},
    {"n": 32, "node": "KN-C-000042", "part": "第七部分：安全与防护"},
    {"n": 33, "node": "KN-C-000043", "part": "第七部分：安全与防护"},
    # Part 8: Observability
    {"n": 34, "node": "KN-C-000044", "part": "第八部分：可观测性"},
    {"n": 35, "node": "KN-C-000046", "part": "第八部分：可观测性"},
    {"n": 36, "node": "KN-C-000047", "part": "第八部分：可观测性"},
    # Part 9: Advanced
    {"n": 37, "node": "KN-C-000050", "part": "第九部分：高级专题"},
    {"n": 38, "node": "KN-C-000051", "part": "第九部分：高级专题"},
    {"n": 39, "node": "KN-C-000052", "part": "第九部分：高级专题"},
    {"n": 40, "node": "KN-C-000053", "part": "第九部分：高级专题"},
    {"n": 41, "node": "KN-C-000054", "part": "第九部分：高级专题"},
]


# ── MD → HTML ────────────────────────────────────────────────────────────────

def _is_real_mermaid(content: str) -> bool:
    """
    Return True if the content looks like real mermaid diagram syntax.
    Real mermaid starts with one of the known diagram-type keywords.
    """
    MERMAID_KEYWORDS = {
        "graph", "flowchart", "sequencediagram", "classdiagram",
        "statediagram", "erdiagram", "gantt", "pie", "mindmap",
        "timeline", "gitgraph", "journey", "quadrantchart",
        "requirementdiagram", "c4context",
    }
    first_word = content.strip().split()[0].lower().rstrip("-") if content.strip() else ""
    # also handle "stateDiagram-v2" etc.
    return first_word in MERMAID_KEYWORDS


def _unwrap_chinese_code_blocks(md_text: str) -> str:
    """
    Pre-processing step: detect ```python or ```bash blocks whose content is
    mostly Chinese narrative text (Chinese char ratio > 30% AND block length
    > 200 chars) and unwrap them to plain paragraphs.
    """
    def _chinese_ratio(text: str) -> float:
        non_ws = [c for c in text if not c.isspace()]
        if not non_ws:
            return 0.0
        chinese = [c for c in non_ws if '一' <= c <= '鿿']
        return len(chinese) / len(non_ws)

    def _maybe_unwrap(m: re.Match) -> str:
        lang = m.group(1).lower()   # "python" or "bash"
        body = m.group(2)
        if len(body) > 200 and _chinese_ratio(body) > 0.30:
            # Drop the fences, keep the content as plain text
            return "\n\n" + body.strip() + "\n\n"
        return m.group(0)  # leave unchanged

    return re.sub(
        r"```(python|bash)[ \t]*\r?\n([\s\S]*?)```",
        _maybe_unwrap,
        md_text,
        flags=re.MULTILINE,
    )


def _md_to_html(md_text: str) -> str:
    """
    把 Markdown 转成 HTML，渲染效果与 ChatGPT/DeepSeek 对话界面一致：
    - ## 标题正确渲染
    - ```python 代码块保留格式
    - 表格正常显示
    - mermaid 图表用 <div class="mermaid"> 包裹
    - 不使用 nl2br（避免段落内每行都变成 <br>）
    """
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension

    # 预处理：把错误的中文叙事从 python/bash 代码块中解包
    md_text = _unwrap_chinese_code_blocks(md_text)

    # 预处理：把 mermaid 代码块临时替换成占位符（防止被 markdown 解析器破坏）
    mermaid_blocks: list[str] = []
    def extract_mermaid(m: re.Match) -> str:
        idx = len(mermaid_blocks)
        mermaid_blocks.append(m.group(1).strip())
        return f"\n\nMERMAID_PLACEHOLDER_{idx}\n\n"

    md_text = re.sub(
        r"```mermaid[ \t]*\r?\n([\s\S]*?)```",
        extract_mermaid,
        md_text,
        flags=re.MULTILINE,
    )

    html = markdown.markdown(
        md_text,
        extensions=[
            FencedCodeExtension(),
            TableExtension(),
            "sane_lists",
        ],
        output_format="html",
    )

    # 还原 mermaid 块
    # Validate each block: if it doesn't look like real mermaid, render as <pre><code>
    def _render_mermaid_or_pre(code: str) -> str:
        if _is_real_mermaid(code):
            return f'<div class="mermaid">{code}</div>'
        # Not real mermaid — render as a plain code block with code-hdr style
        import html as html_mod
        escaped = html_mod.escape(code)
        return (
            '<pre>'
            '<div class="code-hdr">'
            '<span class="code-lang">mermaid</span>'
            '<button class="copy-btn" onclick="copyCode(this)">复制</button>'
            '</div>'
            f'<code class="language-mermaid">{escaped}</code>'
            '</pre>'
        )

    for i, code in enumerate(mermaid_blocks):
        placeholder = f"MERMAID_PLACEHOLDER_{i}"
        rendered = _render_mermaid_or_pre(code)
        html = html.replace(
            f"<p>{placeholder}</p>",
            rendered,
        )
        html = html.replace(
            placeholder,
            rendered,
        )

    # 给代码块加语言标签 + 复制按钮（与 book.css .code-hdr 配套）
    def _add_code_header(m: re.Match) -> str:
        cls = m.group(1)  # e.g. "language-python"
        lang = cls.replace("language-", "") if cls else "code"
        code_content = m.group(2)
        return (
            f'<pre>'
            f'<div class="code-hdr">'
            f'<span class="code-lang">{lang}</span>'
            f'<button class="copy-btn" onclick="copyCode(this)">复制</button>'
            f'</div>'
            f'<code class="{cls}">{code_content}</code>'
            f'</pre>'
        )

    html = re.sub(
        r'<pre><code class="([^"]*)">([\s\S]*?)</code></pre>',
        _add_code_header,
        html,
    )
    # 处理没有语言标注的裸代码块
    html = re.sub(
        r'<pre><code>([\s\S]*?)</code></pre>',
        lambda m: (
            '<pre>'
            '<div class="code-hdr">'
            '<span class="code-lang">code</span>'
            '<button class="copy-btn" onclick="copyCode(this)">复制</button>'
            '</div>'
            f'<code>{m.group(1)}</code>'
            '</pre>'
        ),
        html,
    )

    return html


def _strip_comment(md: str) -> tuple[str, dict]:
    """去掉 HTML 注释头，返回 (纯 md, 元数据字典)。"""
    meta: dict = {}
    m = re.match(r"<!--([\s\S]*?)-->", md)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip()
        md = md[m.end():].strip()
    return md, meta


def _extract_title(md: str) -> str:
    """提取章节标题——优先匹配 # 第N章 H1，跳过HTML注释块。"""
    # 优先：在整个文件里找 # 第N章 H1（不限前20行，因为可能前面有注释）
    m = re.search(r"^#\s+(第\d+章.+)$", md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # 回退：前20行第一个标题
    in_comment = False
    for line in md.splitlines()[:40]:
        s = line.strip()
        if s.startswith("<!--"):
            in_comment = True
        if in_comment:
            if "-->" in s:
                in_comment = False
            continue
        if re.match(r"^第\d+章[：:\s]", s):
            return s
        m2 = re.match(r"^#\s+(.+)$", s)
        if m2:
            return m2.group(1).strip()
    return ""


def build_chapter_html(md_path: Path, chapter_n: int) -> tuple[str, str, bool]:
    """
    把单个 MD 文件转成 (title, html_content, done)。
    done=False 表示文件不存在或内容为空（显示"生成中"标记）。
    """
    if not md_path.exists():
        return f"第 {chapter_n} 章", "", False

    raw = md_path.read_text(encoding="utf-8")
    md, meta = _strip_comment(raw)

    # 空文件检测
    if len(md.strip()) < 200:
        return f"第 {chapter_n} 章", "", False

    title = _extract_title(md) or f"第 {chapter_n} 章"

    # provider badge（固定为 AI Pipeline）
    badge = '<div class="provider-badge" data-provider="aios">由 AI Pipeline 生成</div>\n'

    html_body = _md_to_html(md)
    return title, badge + html_body, True


# ── 主构建逻辑 ────────────────────────────────────────────────────────────────

def build(dry_run: bool = False) -> None:
    chapters = []
    done_count = 0

    for meta in CHAPTER_META:
        n = meta["n"]
        node = meta["node"]
        part = meta["part"]
        md_path = CHAPTERS_DIR / f"ch{n:02d}_{node}.md"

        print(f"  ch{n:02d} {node} ... ", end="", flush=True)
        title, html, done = build_chapter_html(md_path, n)
        status = "✅" if done else "⏳ (未生成)"
        print(f"{status}  {title[:40]}")
        if done:
            done_count += 1

        chapters.append({
            "n": n,
            "title": title,
            "part": part,
            "done": done,
            "content": html,
        })

    data = {
        "title": "AI Education OS · AI工程师完全手册",
        "subtitle": f"共 41 章，已完成 {done_count} 章 · 持续生成更新中",
        "chapters": chapters,
    }

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    print(f"\n[Build] 总计 {len(chapters)} 章，{done_count} 章已完成")
    print(f"[Build] JSON 大小: {len(json_str) // 1024} KB")

    if dry_run:
        print("[Build] --dry 模式，不写入文件")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json_str, encoding="utf-8")
    print(f"[Build] ✅ 已写入: {OUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建 aios-bible.json")
    parser.add_argument("--dry", action="store_true", help="只打印，不写文件")
    args = parser.parse_args()
    build(dry_run=args.dry)
