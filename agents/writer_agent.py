"""
agents/writer_agent.py
----------------------
Writer Agent：将知识节点 + Researcher 素材合成完整的书籍章节（Markdown）。
使用 Browser LLM（ChatGPT 负责教学设计/叙事），不调用 Claude API。
"""
from __future__ import annotations

import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).parent.parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))

from engine.llm import create_llm
from agents.knowledge_loader import build_chapter_context

PROMPT_FILE = Path(__file__).parent / "prompts" / "writer.md"
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")


class WriterAgent:
    """
    接收知识节点 + Researcher 素材，输出完整 Markdown 章节。

    按 SPEC-002，Writer 使用 ChatGPT（教学设计/叙事能力更强）。

    用法：
        agent = WriterAgent(provider="chatgpt", account="1")
        chapter_md = agent.write(primary_node, research_data, chapter_num=1)
        agent.close()
    """

    def __init__(self, provider: str = "chatgpt", account: str = "1"):
        self.llm = create_llm(provider, account)

    def write(
        self,
        primary_node: dict,
        research_data: dict,
        chapter_num: int = 1,
        related_nodes: list[dict] | None = None,
        max_retries: int = 2,
    ) -> str:
        """
        生成章节 Markdown 内容。

        参数：
            primary_node: 主知识节点 YAML 数据
            research_data: ResearcherAgent 返回的素材字典
            chapter_num: 章节编号（用于生成标题前缀）
            related_nodes: 相关知识节点列表（可选）
        """
        context = build_chapter_context(primary_node, related_nodes)
        node_name = primary_node.get("name", "")
        node_id = primary_node.get("id", "")
        level = primary_node.get("level", "L1-L2")
        one_liner = primary_node.get("one_liner", "")

        # 将 research_data 序列化为可读文本
        import json
        research_text = json.dumps(research_data, ensure_ascii=False, indent=2)

        user_message = f"""请为第{chapter_num}章撰写完整内容。

章节信息：
- 章节编号：第{chapter_num}章
- 知识节点：{node_id} - {node_name}
- 层级标注：[{level}]
- 一句话精髓：{one_liner}

知识节点完整数据：
{context}

研究员素材（请充分利用以下内容）：
{research_text}

写作要求：
1. 严格按15个Part结构写完整章节
2. 在章节标题后标注 [{level}]
3. Part 1 必须使用研究员提供的认知冲突场景开头
4. Part 6 的Demo代码必须是完整可运行的Python代码
5. Part 7 使用研究员提供的真实案例
6. Part 9 使用研究员提供的面试题
7. 总字数目标：6000-8000字

直接输出 Markdown 格式的章节内容，不要有任何说明文字。"""

        last_output = ""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  [Writer] 正在撰写第{chapter_num}章 {node_id} [尝试 {attempt}/{max_retries}]...")
                # 使用多段发送避免 ChatGPT token 截断（超过 12000 字符自动分段）
                if hasattr(self.llm, "chat_multipart"):
                    response = self.llm.chat_multipart(SYSTEM_PROMPT, user_message)
                else:
                    response = self.llm.chat([
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ])
                if _validate_chapter(response):
                    response = _normalize_markdown(response)
                    print(f"  [Writer] 第{chapter_num}章撰写完成（{len(response)}字符）")
                    return response
                else:
                    last_output = response
                    missing = _find_missing_parts(response)
                    print(f"  [Writer] 章节结构不完整，缺少: {missing}，重试...")
                    user_message += f"\n\n[注意：上次输出缺少以下Part，请补充完整: {', '.join(missing)}]"
            except Exception as e:
                print(f"  [Writer] 写作出错（尝试{attempt}）: {e}")
                last_output = ""

        print(f"  [Writer] 警告：章节可能不完整，返回最后一次输出")
        return _normalize_markdown(last_output) if last_output else last_output

    def close(self):
        """章节结束：开启新对话，浏览器保持常驻。"""
        self.llm.close()

    def shutdown(self):
        """程序退出：真正关闭浏览器。"""
        if hasattr(self.llm, 'shutdown'):
            self.llm.shutdown()
        else:
            self.llm.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()


def _chinese_ratio(text: str) -> float:
    """计算文本中中文字符占非空白字符的比例。"""
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return 0.0
    return sum(1 for c in non_ws if '一' <= c <= '鿿') / len(non_ws)


MERMAID_VALID_FIRST = {
    'graph', 'flowchart', 'sequencediagram', 'classdiagram',
    'statediagram', 'erdiagram', 'gantt', 'pie', 'mindmap',
    'timeline', 'gitgraph', 'journey', 'quadrantchart',
}

BARE_LANG_NAMES = {'python', 'bash', 'shell', 'javascript', 'typescript',
                   'json', 'yaml', 'sql', 'mermaid'}


def _normalize_markdown(content: str) -> str:
    """
    完备的自愈型 Markdown 修复器：检测 AI 输出的所有已知格式错误并原地修复，
    不依赖重试。修复顺序很重要，不要随意调整。

    修复项：
    A. python/bash块中包含大量中文叙述 → 解包为普通段落
    B. 裸语言名（"Python\\n代码"）→ 包裹为正确代码块
    C. 未加语言标识的裸 ``` → 补为 ```python
    D. 不含 ## 前缀的 Part N：标题 → 补 ##
    E. ASCII 树形字符块 → 转为 mermaid flowchart/mindmap
    F. mermaid 块首词不合法 → 降级为普通段落
    G. 代码块未闭合 → 补关闭围栏
    """
    import re

    # ── A：解包错误包裹的中文叙事 python/bash 代码块 ─────────────────────────────
    def _maybe_unwrap_chinese(m: re.Match) -> str:
        body = m.group(2)
        if len(body) > 200 and _chinese_ratio(body) > 0.40:
            return "\n\n" + body.strip() + "\n\n"
        return m.group(0)

    content = re.sub(
        r"```(python|bash)[ \t]*\r?\n([\s\S]*?)```",
        _maybe_unwrap_chinese,
        content,
        flags=re.MULTILINE,
    )

    # ── B：把「Python\n代码」「Mermaid\n图表」格式包装成代码块 ──────────────────
    def _wrap_bare_code_blocks(text: str) -> str:
        lines = text.splitlines()
        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            next_nonblank = i + 1
            while next_nonblank < len(lines) and not lines[next_nonblank].strip():
                next_nonblank += 1
            if (stripped.lower() in BARE_LANG_NAMES
                    and (i == 0 or not lines[i-1].strip())
                    and next_nonblank < len(lines)
                    and not lines[next_nonblank].startswith('## ')):
                lang = stripped.lower()
                fence = 'mermaid' if lang == 'mermaid' else lang
                code_lines = []
                j = next_nonblank
                blank_count = 0
                while j < len(lines):
                    l = lines[j]
                    if l.startswith('## ') or l.startswith('### '):
                        break
                    if not l.strip():
                        blank_count += 1
                        if blank_count >= 2:
                            break
                        code_lines.append(l)
                    else:
                        blank_count = 0
                        code_lines.append(l)
                    j += 1
                while code_lines and not code_lines[-1].strip():
                    code_lines.pop()
                if code_lines:
                    out.append(f'```{fence}')
                    out.extend(code_lines)
                    out.append('```')
                    i = j
                    continue
            out.append(line)
            i += 1
        return '\n'.join(out)

    content = _wrap_bare_code_blocks(content)

    # ── C + D：逐行修复裸 ``` 和裸 Part 标题 ─────────────────────────────────
    lines = content.splitlines()
    result = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                in_code = False
                result.append(line)
            else:
                in_code = True
                # 裸 ``` 开启 → 补 python
                if line.strip() == "```":
                    result.append("```python")
                else:
                    result.append(line)
            continue

        if in_code:
            result.append(line)
            continue

        # "Part N..." 行 → 补 ## 前缀（多种格式）
        # 匹配行首的 Part N（支持 **Part N**、Part N：、Part N: 等）
        _stripped = line.strip()
        if not line.startswith('#') and re.match(r'^(?:\*\*)?Part\s*\d+[\s：:：*]', _stripped):
            # 去掉可能的 ** 包裹，补 ## 前缀
            _clean = re.sub(r'^\*\*|\*\*$', '', _stripped).strip()
            result.append("## " + _clean)
            continue

        result.append(line)

    normalized = "\n".join(result)

    # ── E：把代码块外的 ASCII 树形字符块转为 mermaid ─────────────────────────
    def _ascii_block_to_mermaid(block_text: str, is_mindmap: bool = False) -> str:
        blines = block_text.strip().splitlines()
        if not blines:
            return block_text
        if is_mindmap:
            mm = ["```mermaid", "mindmap"]
            first = "核心概念"
            for tl in blines:
                candidate = re.sub(r'[│├└─\s]+', '', tl).strip()
                if candidate:
                    first = candidate
                    break
            mm.append(f"  root(({first}))")
            for tl in blines[1:]:
                text = re.sub(r'[│├└─]+', '', tl).strip()
                if not text:
                    continue
                no_tree = re.sub(r'[│├└─]', ' ', tl)
                leading = len(no_tree) - len(no_tree.lstrip())
                level = (leading // 4) + 1
                mm.append("  " * level + text)
            mm.append("```")
        else:
            mm = ["```mermaid", "flowchart TD"]
            nodes: list[tuple[int, str]] = []
            for tl in blines:
                text = re.sub(r'[│├└─\s]+', '', tl).strip()
                if not text:
                    continue
                no_tree = re.sub(r'[│├└─]', ' ', tl)
                leading = len(no_tree) - len(no_tree.lstrip())
                level = leading // 4
                nodes.append((level, text))
            seen: dict[int, str] = {}
            for level, label in nodes:
                nid = "N" + str(len(seen))
                seen[level] = nid
                mm.append(f'  {nid}["{label}"]')
                if level > 0 and (level - 1) in seen:
                    mm.append(f'  {seen[level-1]} --> {nid}')
            mm.append("```")
        return "\n".join(mm)

    # 分段处理：只在代码块外替换 ASCII 树
    segments: list[tuple[bool, str]] = []
    code_re = re.compile(r'(```[\s\S]*?```)', re.MULTILINE)
    last = 0
    for cm in code_re.finditer(normalized):
        if cm.start() > last:
            segments.append((False, normalized[last:cm.start()]))
        segments.append((True, cm.group(0)))
        last = cm.end()
    if last < len(normalized):
        segments.append((False, normalized[last:]))

    ascii_tree_re = re.compile(
        r'((?:[^\n]*[│├└─┌┬┐┤┴┘╔╗╚╝╠╣╦╩╬═║]+[^\n]*\n){3,}[^\n]*[│├└─┌┬┐┤┴┘╔╗╚╝╠╣╦╩╬═║]+[^\n]*)',
        re.MULTILINE
    )

    out_parts = []
    for is_code, seg in segments:
        if is_code:
            out_parts.append(seg)
            continue
        def replace_ascii(m: re.Match, _seg=seg) -> str:
            ctx_before = _seg[:m.start()]
            in_part13 = bool(re.search(r'Part 13[：:]', ctx_before[-200:]))
            return "\n" + _ascii_block_to_mermaid(m.group(0), is_mindmap=in_part13) + "\n"
        seg = ascii_tree_re.sub(replace_ascii, seg)
        out_parts.append(seg)

    normalized = "".join(out_parts)

    # ── F：修复非法 mermaid 块（首词不是合法 mermaid 关键词）────────────────────
    def _fix_bad_mermaid(m: re.Match) -> str:
        body = m.group(1)
        stripped = body.strip()
        if not stripped:
            return m.group(0)
        first_word = stripped.split()[0].lower().rstrip('-')
        if first_word in MERMAID_VALID_FIRST:
            return m.group(0)
        # 非法：把整个 mermaid 块的内容降级为普通段落
        return '\n\n' + stripped + '\n\n'

    normalized = re.sub(
        r'```mermaid[ \t]*\r?\n([\s\S]*?)```',
        _fix_bad_mermaid,
        normalized,
    )

    # ── G：修复未闭合的代码块 ────────────────────────────────────────────────────
    # 重新扫描（F 步可能改变围栏结构）
    depth = 0
    for line in normalized.splitlines():
        s = line.strip()
        if s.startswith('```') and s != '```':
            depth += 1
        elif s == '```' and depth > 0:
            depth -= 1
    if depth > 0:
        normalized += '\n```\n' * depth

    return normalized


def _validate_chapter(content: str) -> bool:
    """验证章节是否包含所有必要的 Part。"""
    required_parts = [
        "Part 1", "Part 2", "Part 3", "Part 4", "Part 5",
        "Part 6", "Part 7", "Part 8", "Part 9", "Part 10",
        "Part 11", "Part 12", "Part 13", "Part 14", "Part 15",
    ]
    return all(part in content for part in required_parts)


def _find_missing_parts(content: str) -> list[str]:
    """找出缺失的 Part。"""
    required_parts = [
        "Part 1", "Part 2", "Part 3", "Part 4", "Part 5",
        "Part 6", "Part 7", "Part 8", "Part 9", "Part 10",
        "Part 11", "Part 12", "Part 13", "Part 14", "Part 15",
    ]
    return [p for p in required_parts if p not in content]


if __name__ == "__main__":
    import json
    from agents.knowledge_loader import load_node

    # 测试：用模拟的 research_data
    node = load_node("KN-C-000001")
    mock_research = {
        "cognitive_conflict": {
            "scenario": "你以为调高Temperature就能让LLM更聪明？",
            "wrong_assumption": "Temperature越高回答越好",
            "correct_understanding": "Temperature控制的是随机性，不是智力"
        },
        "life_analogy": "LLM像接龙游手：根据上文预测最可能的下一个字",
        "real_case": {
            "background": "某电商平台用GPT-4做商品描述生成",
            "problem": "Temperature=1.0时描述天马行空，包含不存在的功能",
            "solution": "调整为Temperature=0.3，增加Few-shot示例",
            "result": "描述准确率从60%提升到92%，人工审核成本降低70%"
        },
        "common_errors": [
            {
                "error": "把LLM当搜索引擎使用，直接问'最新的XXX是什么'",
                "consequence": "获得截止训练日期前的信息，被当成实时数据使用",
                "fix": "对时效性强的问题，结合RAG或搜索工具使用"
            }
        ],
        "interview_questions": [
            {"level": "L1", "question": "LLM和搜索引擎的本质区别是什么？", "key_points": "预测vs检索"},
            {"level": "L2", "question": "如何评估一个LLM是否适合某个生产场景？", "key_points": "Benchmark、成本、延迟、安全"},
            {"level": "L3", "question": "描述一个你用LLM解决复杂工程问题的完整案例", "key_points": "问题定义、方案选型、评估指标"}
        ],
        "memory_anchor": "LLM=超级接龙游手，预测下一个词，不知道真相只知道概率"
    }

    with WriterAgent(provider="chatgpt", account="1") as agent:
        chapter = agent.write(node, mock_research, chapter_num=1)
        output_path = Path("output") / "ch01_llm.md"
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(chapter, encoding="utf-8")
        print(f"章节已保存到 {output_path}")
