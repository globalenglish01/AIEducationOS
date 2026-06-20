"""
md_renderer.py
--------------
将 LLM 生成的纯 Markdown 渲染为 book.css 兼容的 HTML 片段。

支持的扩展语法（自定义 fenced blocks）：
  :::story            → <div class="story-box">
  :::skills           → <div class="skill-grid"> + <span class="skill-tag ...">
  :::q jr|md|sr|ex    → <div class="iq"> + <span class="q-lvl ...">
  :::milestone 标题   → <div class="milestone">
  :::next 第N章：标题 → <div class="next-teaser">
  :::answer           → <details><summary>点击展开参考答案</summary>

GitHub Alert 语法：
  > [!info] 标题    → <div class="callout callout-info">
  > [!warning]      → callout-warning
  > [!danger]       → callout-danger
  > [!tip]          → callout-tip
  > [!success]      → callout-success

章节 metabar（特殊 blockquote）：
  > 第X部分 · 第Y章 | ⏱ ... | ...  → <div class="ch-metabar">
"""
from __future__ import annotations

import html as _html_module
import re

try:
    import markdown as _md
    _HAS_MD = True
except ImportError:
    _HAS_MD = False

_PROVIDER_LABELS = {"chatgpt": "ChatGPT", "deepseek": "DeepSeek"}
_CALLOUT_ICONS   = {"info": "💡", "warning": "⚠️", "danger": "❌", "tip": "✅", "success": "🎉"}
_IQ_LABELS       = {"jr": "初级", "md": "中级", "sr": "高级", "ex": "大厂题"}


def render(content: str, provider: str = "chatgpt") -> str:
    """将纯 Markdown 内容渲染为 HTML 片段（不含 <html>/<body>）。"""
    content = _preprocess_fenced_divs(content)
    content = _preprocess_github_alerts(content)

    if _HAS_MD:
        html = _render_with_markdown(content)
    else:
        html = _render_fallback(content)

    html = _postprocess_metabar(html)
    html = _postprocess_code_blocks(html)
    html = _postprocess_mermaid(html)
    html = _postprocess_orphan_colons(html)

    label = _PROVIDER_LABELS.get(provider, provider)
    badge = f'<div class="provider-badge" data-provider="{provider}">由 {label} 生成</div>\n'
    return badge + html


# ── 预处理：:::type ... ::: → HTML ────────────────────────────────────────────

def _preprocess_fenced_divs(text: str) -> str:
    """将所有 :::type arg ... ::: 块转换为 HTML。代码块内的 ::: 原样保留。"""
    lines = text.split('\n')
    result: list[str] = []
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        # 追踪代码围栏，跳过其内部的 :::
        if not in_code and re.match(r'^```', line):
            in_code = True
            result.append(line)
            i += 1
            continue
        if in_code:
            result.append(line)
            if line.strip() == '```':
                in_code = False
            i += 1
            continue
        # 匹配自定义 fenced block 开始行（支持缩进，如 "   :::answer"）
        line_clean = line.strip().rstrip('\\').rstrip()  # 去掉前后空白和行尾 \
        m = re.match(r'^:::(\w+)(?:\s+(.+?))?$', line_clean)
        line = line_clean if m else line
        if m:
            ftype = m.group(1)
            farg  = (m.group(2) or '').strip()
            inner_lines: list[str] = []
            depth = 1
            i += 1
            while i < len(lines):
                ln = lines[i]
                if re.match(r'^\s*:::\w', ln):
                    depth += 1
                    inner_lines.append(ln)
                elif ln.strip() == ':::':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                    inner_lines.append(ln)
                else:
                    inner_lines.append(ln)
                i += 1
            inner = '\n'.join(inner_lines)
            result.append('')
            result.append(_render_fence(ftype, farg, inner))
            result.append('')
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


def _preprocess_github_alerts(text: str) -> str:
    """将 > [!type] title / > content 块转换为 callout HTML。"""
    lines = text.split('\n')
    result: list[str] = []
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if not in_code and re.match(r'^```', line):
            in_code = True
            result.append(line)
            i += 1
            continue
        if in_code:
            result.append(line)
            if line.strip() == '```':
                in_code = False
            i += 1
            continue
        m = re.match(r'^> \[!(\w+)\]\s*(.*)', line)
        if m:
            atype = m.group(1).lower()
            title = m.group(2).strip()
            content_lines: list[str] = []
            i += 1
            while i < len(lines) and re.match(r'^>', lines[i]):
                content_lines.append(re.sub(r'^>[ \t]?', '', lines[i]))
                i += 1
            content = '\n'.join(content_lines)
            result.append('')
            result.append(_render_callout(atype, title, content))
            result.append('')
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


# ── Fenced block 渲染器 ───────────────────────────────────────────────────────

def _inner_md(content: str) -> str:
    """将内部 Markdown 文本渲染为 HTML（用于块组件内部，不加 nl2br）。"""
    if not content.strip():
        return ''
    content = _preprocess_fenced_divs(content)
    content = _preprocess_github_alerts(content)
    if _HAS_MD:
        exts = _available_extensions(['extra', 'sane_lists'])
        return _md.markdown(content, extensions=exts, output_format='html')
    return _render_fallback(content)


def _render_fence(ftype: str, farg: str, inner: str) -> str:
    if ftype == 'story':
        return f'<div class="story-box">{_inner_md(inner)}</div>'

    if ftype == 'skills':
        return _render_skills(inner)

    if ftype == 'q':
        return _render_iq(farg or 'jr', _inner_md(inner))

    if ftype == 'milestone':
        return _render_milestone(farg, inner)

    if ftype == 'next':
        return _render_next_teaser(farg, _inner_md(inner))

    if ftype == 'answer':
        return (
            f'<details><summary>点击展开参考答案</summary>'
            f'<div class="answer-body">{_inner_md(inner)}</div>'
            f'</details>'
        )

    return f'<div class="custom-block custom-{ftype}">{_inner_md(inner)}</div>'


def _render_skills(inner: str) -> str:
    TYPE_MAP = [('🆕', 'new'), ('🔗', 'rel'), ('⬆️', 'adv'), ('⬆', 'adv')]
    tags: list[str] = []
    for line in inner.split('\n'):
        line = line.strip()
        if not line:
            continue
        stype = 'new'
        for emoji, cls in TYPE_MAP:
            if line.startswith(emoji):
                stype = cls
                line = line[len(emoji):].strip()
                break
        for skill in re.split(r'[,，]', line):
            skill = skill.strip()
            if skill:
                tags.append(f'<span class="skill-tag skill-{stype}">{skill}</span>')
    return f'<div class="skill-grid">{"".join(tags)}</div>'


def _render_iq(level: str, inner_html: str) -> str:
    label = _IQ_LABELS.get(level, level)
    return (
        f'<div class="iq">'
        f'<span class="q-lvl {level}">{label}</span>'
        f'{inner_html}'
        f'</div>'
    )


def _render_milestone(title: str, inner: str) -> str:
    items: list[str] = []
    for line in inner.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('✅'):
            items.append(f'<div class="milestone-item m-done">{line[1:].strip()}</div>')
        elif line.startswith('⬜'):
            items.append(f'<div class="milestone-item m-todo">{line[1:].strip()}</div>')
        else:
            items.append(f'<div class="milestone-item">{line}</div>')
    title_html = f'<div class="milestone-title">🎯 {title}</div>' if title else ''
    return f'<div class="milestone">{title_html}{"".join(items)}</div>'


def _render_next_teaser(title: str, inner_html: str) -> str:
    return (
        f'<div class="next-teaser">'
        f'<div class="next-teaser-label">下一章预告 →</div>'
        f'<div class="next-teaser-title">{title}</div>'
        f'<div class="next-teaser-hook">{inner_html}</div>'
        f'</div>'
    )


def _render_callout(atype: str, title: str, content: str) -> str:
    icon = _CALLOUT_ICONS.get(atype, 'ℹ️')
    title_html = f'<div class="callout-title">{icon} {title}</div>' if title else f'<div class="callout-title">{icon}</div>'
    body_html  = f'<div class="callout-body">{_inner_md(content)}</div>' if content.strip() else ''
    return f'<div class="callout callout-{atype}">{title_html}{body_html}</div>'


# ── Markdown 渲染 ─────────────────────────────────────────────────────────────

def _available_extensions(wanted: list[str]) -> list[str]:
    if not _HAS_MD:
        return []
    result = []
    for ext in wanted:
        try:
            _md.markdown('', extensions=[ext])
            result.append(ext)
        except Exception:
            pass
    return result or ['fenced_code', 'tables']


def _render_with_markdown(content: str) -> str:
    exts = _available_extensions(['extra', 'sane_lists', 'nl2br'])
    return _md.markdown(content, extensions=exts, output_format='html')


# ── Fallback 渲染（无 python-markdown 时）─────────────────────────────────────

def _render_fallback(content: str) -> str:
    lines = content.split('\n')
    out: list[str] = []
    in_fence = False
    fence_lang = ''
    fence_lines: list[str] = []

    for line in lines:
        if not in_fence and re.match(r'^```(\w*)', line):
            fence_lang = re.match(r'^```(\w*)', line).group(1) or 'text'
            in_fence = True
            fence_lines = []
            continue
        if in_fence:
            if line.strip() == '```':
                in_fence = False
                code = '\n'.join(fence_lines)
                out.append(
                    f'<pre><code class="language-{fence_lang}">'
                    f'{_html_module.escape(code)}</code></pre>'
                )
                fence_lines = []
            else:
                fence_lines.append(line)
            continue
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            out.append(f'<h{level}>{_inline(m.group(2))}</h{level}>')
            continue
        if re.match(r'^---+$', line.strip()):
            out.append('<hr>')
            continue
        if not line.strip():
            out.append('')
            continue
        if line.lstrip().startswith('<'):
            out.append(line)
            continue
        out.append(f'<p>{_inline(line)}</p>')

    return '\n'.join(out)


def _inline(text: str) -> str:
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{_html_module.escape(m.group(1))}</code>', text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


# ── 后处理 ────────────────────────────────────────────────────────────────────

def _postprocess_metabar(html: str) -> str:
    """将章节 metabar blockquote（第X部分 · 第Y章 | ...）转换为 ch-metabar div。"""
    return re.sub(
        r'<blockquote>\s*<p>(第[^<|]*·[^|<]*(?:\|[^<]*)+)</p>\s*</blockquote>',
        lambda m: f'<div class="ch-metabar"><div class="meta-badge">{m.group(1)}</div></div>',
        html,
    )


_CODE_RE = re.compile(
    r'<pre><code(?:\s+class="language-(?P<lang>[^"]+)")?>'
    r'(?P<body>.*?)'
    r'</code></pre>',
    re.DOTALL,
)


def _postprocess_code_blocks(html: str) -> str:
    """将 python-markdown 生成的 <pre><code class="language-xxx"> 转为 book.css 格式。"""
    def _replace(m: re.Match) -> str:
        lang = (m.group('lang') or '').strip()
        display_lang = lang if lang and lang not in ('text', 'txt', 'plain') else ''
        code_lang = lang or 'text'
        body = m.group('body')
        return (
            f'<pre>'
            f'<div class="code-hdr">'
            f'<span class="code-lang">{display_lang}</span>'
            f'<button class="copy-btn" onclick="copyCode(this)">复制</button>'
            f'</div>'
            f'<code class="language-{code_lang}">{body}</code>'
            f'</pre>'
        )
    return _CODE_RE.sub(_replace, html)


def _postprocess_mermaid(html: str) -> str:
    """将 mermaid 代码块转为 <pre class="mermaid">（mermaid.js 所需格式）。"""
    # 精确匹配 code-hdr 格式中的 mermaid 块，避免跨块匹配
    html = re.sub(
        r'<pre>'
        r'<div class="code-hdr">'
        r'<span class="code-lang">mermaid</span>'
        r'<button[^>]*>[^<]*</button>'
        r'</div>'
        r'<code class="language-mermaid">(.*?)</code>'
        r'</pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>',
        html, flags=re.DOTALL,
    )
    # fallback: python-markdown 直接生成的 <pre class="mermaid"><code>
    html = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>',
        html, flags=re.DOTALL,
    )
    return html


def _postprocess_orphan_colons(html: str) -> str:
    """清除渲染后 HTML 中孤立的 ::: 残留（未被 _preprocess_fenced_divs 匹配的闭合标签）。"""
    # <p>:::</p> 或 <p>   :::   </p>
    html = re.sub(r'<p>\s*:::\s*</p>', '', html)
    # :::</p>  :::</li>  :::</br> 等（::: 粘在闭合标签前）
    html = re.sub(r':::\s*(</(p|li|br|div|blockquote)>)', r'\1', html)
    # 单独成行的 ::: （换行包围）
    html = re.sub(r'\n\s*:::\s*\n', '\n', html)
    return html


# ── CLI 快速测试 ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print('用法：python md_renderer.py <file.md> [provider]')
        sys.exit(1)

    src  = Path(sys.argv[1])
    prov = sys.argv[2] if len(sys.argv) > 2 else 'chatgpt'
    result = render(src.read_text(encoding='utf-8'), prov)
    out = src.with_suffix('.rendered.html')
    out.write_text(result, encoding='utf-8')
    print(f'渲染完成：{out}')
