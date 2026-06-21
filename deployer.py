"""
deployer.py — AI Education OS 章节部署器
==========================================
把 output/chapters/ch{N:02d}_{node_id}.md 转成 StudyAthena lesson JSON，
写入 D:/My/StudyAthena/content/lessons/aios-{slug}.json，
然后只重启 backend（content 变化无需重编译前端）。

用法：
    # 部署单章
    python deployer.py --chapter 1

    # 部署所有已生成的章节
    python deployer.py --all

    # 只转换，不 SSH 部署（本地调试）
    python deployer.py --all --no-deploy
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
CHAPTERS_DIR = ROOT / "output" / "chapters"
STATE_FILE = ROOT / "output" / "state" / "pipeline_state.json"

# StudyAthena content 目录
STUDYATHENA_ROOT = Path("D:/My/StudyAthena")
LESSONS_DIR = STUDYATHENA_ROOT / "content" / "lessons"
DEPLOY_SCRIPT = STUDYATHENA_ROOT / "scripts" / "local-deploy.ps1"

# 章节 → slug 映射（与 BOOK_CHAPTERS 保持一致）
CHAPTER_SLUGS: dict[str, str] = {
    "KN-C-000001": "aios-llm",
    "KN-C-000002": "aios-token",
    "KN-C-000003": "aios-context-window",
    "KN-C-000004": "aios-temperature",
    "KN-C-000005": "aios-hallucination",
    "KN-C-000010": "aios-prompt-engineering",
    "KN-P-000001": "aios-few-shot",
    "KN-P-000002": "aios-chain-of-thought",
    "KN-P-000003": "aios-prompt-chaining",
    "KN-P-000004": "aios-react",
    "KN-C-000020": "aios-agent",
    "KN-C-000021": "aios-agent-loop",
    "KN-C-000022": "aios-tool-use",
    "KN-C-000023": "aios-planning",
    "KN-C-000024": "aios-human-in-the-loop",
    "KN-C-000030": "aios-embedding",
    "KN-C-000031": "aios-vector-db",
    "KN-C-000032": "aios-chunking",
    "KN-C-000033": "aios-rag",
    "KN-C-000034": "aios-reranking",
    "KN-C-000035": "aios-hybrid-search",
    "KN-C-000025": "aios-state-machine",
    "KN-C-000026": "aios-langgraph",
    "KN-C-000027": "aios-checkpoint",
    "KN-C-000028": "aios-interrupt",
    "KN-C-000036": "aios-llm-as-judge",
    "KN-C-000037": "aios-ragas",
    "KN-C-000038": "aios-eval-dataset",
    "KN-C-000039": "aios-regression-testing",
    "KN-C-000040": "aios-prompt-injection",
    "KN-C-000041": "aios-agent-privilege-escalation",
    "KN-C-000042": "aios-guardrails",
    "KN-C-000043": "aios-tool-injection",
    "KN-C-000044": "aios-tracing",
    "KN-C-000046": "aios-llm-observability",
    "KN-C-000047": "aios-structured-logging",
    "KN-C-000050": "aios-graph-rag",
    "KN-C-000051": "aios-a2a-protocol",
    "KN-C-000052": "aios-fcars",
    "KN-C-000053": "aios-chaos-engineering",
    "KN-C-000054": "aios-fine-tuning",
    # Batch 10: MCP
    "KN-C-000060": "aios-mcp",
    "KN-C-000061": "aios-tool-schema-design",
    "KN-C-000062": "aios-tool-path-sandbox",
    "KN-C-000063": "aios-tool-injection",
    "KN-C-000064": "aios-mcp-server-client",
    # Batch 11: Memory
    "KN-C-000065": "aios-short-term-memory",
    "KN-C-000066": "aios-long-term-memory",
    "KN-C-000067": "aios-context-compression",
    "KN-C-000068": "aios-memory-isolation",
    # Batch 12: Cost Optimization
    "KN-C-000069": "aios-token-budget",
    "KN-C-000070": "aios-semantic-cache",
    "KN-C-000071": "aios-model-routing",
    "KN-C-000072": "aios-context-pruning",
    # Batch 13: Deployment
    "KN-C-000073": "aios-graceful-degradation",
    "KN-C-000074": "aios-multi-tenancy",
    "KN-C-000075": "aios-fine-tuning-deployment",
    "KN-C-000076": "aios-ollama",
    "KN-C-000077": "aios-chaos-engineering-deployment",
    # Batch 14: Governance
    "KN-C-000078": "aios-fcars-framework",
    "KN-C-000079": "aios-ai-compliance",
    "KN-C-000080": "aios-ai-fairness",
    # Batch 15: Patterns
    "KN-P-000005": "aios-react-pattern",
    "KN-P-000006": "aios-supervisor-worker",
    "KN-P-000007": "aios-pipeline-pattern",
    "KN-P-000008": "aios-semantic-cache-pattern",
    "KN-P-000009": "aios-model-routing-pattern",
    # Batch 16: Frameworks
    "KN-F-000001": "aios-langchain",
    "KN-F-000002": "aios-langgraph",
    "KN-F-000003": "aios-autogen",
    "KN-F-000004": "aios-crewai",
    "KN-F-000005": "aios-openai-agents-sdk",
    # Batch 17: Tools
    "KN-T-000001": "aios-vllm",
    "KN-T-000002": "aios-vector-database",
    "KN-T-000003": "aios-browser-automation",
    # Batch 18: Architectures
    "KN-A-000001": "aios-agent-harness",
    "KN-A-000002": "aios-ai-testing-pyramid",
    # Batch 19: Anti-patterns & Protocol
    "KN-X-000001": "aios-god-agent",
    "KN-X-000002": "aios-idor",
    "KN-R-000001": "aios-a2a-protocol-spec",
    # Batch 20: Practices
    "KN-B-000001": "aios-prompt-version-control",
    "KN-B-000002": "aios-max-iteration-guard",
    "KN-B-000003": "aios-pii-detection",
    "KN-B-000004": "aios-jwt-auth",
    "KN-B-000005": "aios-secret-management",
    # Batch 21: Case Studies
    "KN-S-000001": "aios-case-cursor-ai",
    "KN-S-000002": "aios-case-perplexity",
    "KN-S-000003": "aios-case-customer-service",
    "KN-S-000004": "aios-case-code-review",
    "KN-S-000005": "aios-case-multi-tenant-saas",
    # Batch 22: Exercises
    "KN-E-000001": "aios-ex-rag-qa",
    "KN-E-000002": "aios-ex-react-agent",
    "KN-E-000003": "aios-ex-supervisor-worker",
    "KN-E-000004": "aios-ex-security-hardening",
    "KN-E-000005": "aios-ex-production-harness",
}

# 章节编号 → node_id 映射
CHAPTER_NUM_TO_NODE: dict[int, str] = {
    1: "KN-C-000001", 2: "KN-C-000002", 3: "KN-C-000003",
    4: "KN-C-000004", 5: "KN-C-000005", 6: "KN-C-000010",
    7: "KN-P-000001", 8: "KN-P-000002", 9: "KN-P-000003",
    10: "KN-P-000004", 11: "KN-C-000020", 12: "KN-C-000021",
    13: "KN-C-000022", 14: "KN-C-000023", 15: "KN-C-000024",
    16: "KN-C-000030", 17: "KN-C-000031", 18: "KN-C-000032",
    19: "KN-C-000033", 20: "KN-C-000034", 21: "KN-C-000035",
    22: "KN-C-000025", 23: "KN-C-000026", 24: "KN-C-000027",
    25: "KN-C-000028", 26: "KN-C-000036", 27: "KN-C-000037",
    28: "KN-C-000038", 29: "KN-C-000039", 30: "KN-C-000040",
    31: "KN-C-000041", 32: "KN-C-000042", 33: "KN-C-000043",
    34: "KN-C-000044", 35: "KN-C-000046", 36: "KN-C-000047",
    37: "KN-C-000050", 38: "KN-C-000051", 39: "KN-C-000052",
    40: "KN-C-000053", 41: "KN-C-000054",
    # Batch 10-22: new nodes ch42-ch95
    42: "KN-C-000060", 43: "KN-C-000061", 44: "KN-C-000062", 45: "KN-C-000063", 46: "KN-C-000064",
    47: "KN-C-000065", 48: "KN-C-000066", 49: "KN-C-000067", 50: "KN-C-000068",
    51: "KN-C-000069", 52: "KN-C-000070", 53: "KN-C-000071", 54: "KN-C-000072",
    55: "KN-C-000073", 56: "KN-C-000074", 57: "KN-C-000075", 58: "KN-C-000076", 59: "KN-C-000077",
    60: "KN-C-000078", 61: "KN-C-000079", 62: "KN-C-000080",
    63: "KN-P-000005", 64: "KN-P-000006", 65: "KN-P-000007", 66: "KN-P-000008", 67: "KN-P-000009",
    68: "KN-F-000001", 69: "KN-F-000002", 70: "KN-F-000003", 71: "KN-F-000004", 72: "KN-F-000005",
    73: "KN-T-000001", 74: "KN-T-000002", 75: "KN-T-000003",
    76: "KN-A-000001", 77: "KN-A-000002",
    78: "KN-X-000001", 79: "KN-X-000002", 80: "KN-R-000001",
    81: "KN-B-000001", 82: "KN-B-000002", 83: "KN-B-000003", 84: "KN-B-000004", 85: "KN-B-000005",
    86: "KN-S-000001", 87: "KN-S-000002", 88: "KN-S-000003", 89: "KN-S-000004", 90: "KN-S-000005",
    91: "KN-E-000001", 92: "KN-E-000002", 93: "KN-E-000003", 94: "KN-E-000004", 95: "KN-E-000005",
}


# ─────────────────────────────────────────────────────────────────────────────
# MD → Lesson JSON 转换
# ─────────────────────────────────────────────────────────────────────────────

def _strip_html_comment(md: str) -> str:
    """去掉文件头部的 <!-- ... --> 元数据注释。"""
    return re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL).strip()


def _ascii_tree_to_mermaid(block: str) -> str:
    """
    把 ASCII 树形图（│ ├─ └─）转换为 mermaid mindmap。
    block 是已经提取出来的树形图文本。
    """
    lines = block.strip().splitlines()
    if not lines:
        return block

    result = ["```mermaid", "mindmap"]

    # 第一行：根节点（没有树形前缀）
    first = lines[0].strip()
    if first:
        result.append(f"  root(({first}))")

    for line in lines[1:]:
        raw = line
        # 去掉树字符后的文本
        text = re.sub(r"[│├└─]+", "", raw).strip()
        if not text:
            continue
        # 计算缩进层级：
        # "├─ 子节点" → leading 0  → level 1
        # "│   ├─ 孙节点" → leading 4 → level 2
        # "│   │   └─ 曾孙" → leading 8 → level 3
        # 去掉树形字符后统计前导空格
        no_tree = re.sub(r"[│├└─]", " ", raw)
        leading = len(no_tree) - len(no_tree.lstrip())
        # 每4个空格为一个层级（├─ 本身 2字符 + 空格 = 4）
        level = (leading // 4) + 1
        result.append("  " * level + text)

    result.append("```")
    return "\n".join(result)


def _postprocess_markdown(md: str) -> str:
    """
    对 AI 生成的 Markdown 做后处理：
    把 Part 13（思维导图）里的 ASCII 树形图替换为 mermaid mindmap。
    """
    # 用字符串定位，不用正则，避免全角冒号/换行歧义
    p13_markers = ["Part 13：", "Part 13:", "## Part 13"]
    p14_markers = ["Part 14：", "Part 14:", "## Part 14"]

    p13_start = -1
    for marker in p13_markers:
        idx = md.find(marker)
        if idx != -1:
            p13_start = idx
            break
    if p13_start == -1:
        return md

    p14_start = len(md)
    for marker in p14_markers:
        idx = md.find(marker, p13_start + 1)
        if idx != -1 and idx < p14_start:
            p14_start = idx

    block = md[p13_start:p14_start]

    # 已经有 mermaid，不处理
    if "```mermaid" in block:
        return md

    # 没有 ASCII 树字符，不处理
    if not re.search(r"[│├└─]", block):
        return md

    # 把整个 Part 13 块里的 ASCII 树替换为 mermaid
    # 提取树块（从第一行非 Part 13 标题行开始到结束）
    header_end = block.index("\n") + 1
    header = block[:header_end]
    tree_content = block[header_end:].strip()

    mermaid_block = _ascii_tree_to_mermaid(tree_content)
    new_block = header + "\n" + mermaid_block + "\n\n"

    return md[:p13_start] + new_block + md[p14_start:]


def _extract_title(md: str) -> str:
    """从章节第一行标题提取标题（支持多种格式）。"""
    # 只看前20行，避免误匹配代码块内容
    first_lines = md.splitlines()[:20]
    for line in first_lines:
        line = line.strip()
        # 格式1：第N章：标题 [L0-L1] 或 第N章 标题
        if re.match(r"^第\d+章[：:\s]", line):
            return line
        # 格式2：# 第N章...
        m = re.match(r"^#+\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return "AI Education OS"


def _split_parts(md: str) -> dict[str, str]:
    """
    把章节内容按 Part 分割成字典。
    支持多种格式：
      - 「Part N：标题」（行首，无 ## 前缀）
      - 「## Part N：标题」（有 ## 前缀）
    """
    parts: dict[str, str] = {}
    # 统一匹配：行首可选 ## ，后跟 Part N
    pattern = re.compile(
        r"^(?:##\s+)?(Part \d+[：:：][^\n]*)",
        re.MULTILINE
    )
    matches = list(pattern.finditer(md))
    for i, m in enumerate(matches):
        key = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        content = md[start:end].strip()
        parts[key] = content
    return parts


def md_to_lesson_json(md_path: Path, node_id: str, chapter_num: int) -> dict:
    """
    把 Markdown 章节文件转成 StudyAthena lesson JSON 格式。

    lesson JSON 结构：
    {
      "slug": "aios-llm",
      "title": "Ch01 · LLM（大语言模型）",
      "domain": "ai-os",
      "prereqs": [],
      "stages": {
        "why":          { "markdown": "..." },
        "intuition":    { "markdown": "..." },
        "structure":    { "markdown": "..." },
        "formalization":{ "markdown": "..." },
        "reconstruction": { "questions": [...] }
      },
      "takeaways": ["...", "..."],
      "gated": false
    }
    """
    raw = md_path.read_text(encoding="utf-8")
    md = _strip_html_comment(raw)
    md = _postprocess_markdown(md)  # ASCII 图 → mermaid
    title = _extract_title(md)
    slug = CHAPTER_SLUGS.get(node_id, f"aios-ch{chapter_num:02d}")
    parts = _split_parts(md)

    # 把 15 Part 映射到 stages（前4个 Part 是核心叙事，后面归入 formalization）
    def get_part(*keys: str) -> str:
        for k in keys:
            for pk, pv in parts.items():
                if k.lower() in pk.lower():
                    return pv
        return ""

    why_md = get_part("Part 1", "为什么") or get_part("why")
    intuition_md = (
        get_part("Part 2", "学习路径") + "\n\n" +
        get_part("Part 3", "生活", "类比", "案例")
    ).strip()
    structure_md = (
        get_part("Part 4", "AI映射", "技术全景") + "\n\n" +
        get_part("Part 5", "技术解释", "核心")
    ).strip()

    # Part 6-14 合并到 formalization
    deep_parts = []
    for pk, pv in parts.items():
        m = re.match(r"Part (\d+)", pk)
        if m and int(m.group(1)) >= 6:
            deep_parts.append(f"## {pk}\n\n{pv}")
    formalization_md = "\n\n---\n\n".join(deep_parts)

    # 从 Part 9（面试题）提取 reconstruction questions
    interview_md = get_part("Part 9", "面试")
    questions = _extract_interview_questions(interview_md)

    # takeaways 从 Part 11（必须记住）或 Part 15（总结）
    takeaways_md = get_part("Part 11", "必须记住") or get_part("Part 15", "总结")
    takeaways = _extract_takeaways(takeaways_md)

    lesson = {
        "slug": slug,
        "title": title,
        "domain": "ai-os",
        "prereqs": [],
        "stages": {
            "why": {"markdown": why_md or md[:2000]},
            "intuition": {"markdown": intuition_md or ""},
            "structure": {"markdown": structure_md or ""},
            "formalization": {"markdown": formalization_md or ""},
            "reconstruction": {"questions": questions},
        },
        "takeaways": takeaways,
        "gated": False,
        "_source": {
            "node_id": node_id,
            "chapter_num": chapter_num,
            "source_file": md_path.name,
        },
    }
    return lesson


def _extract_interview_questions(md: str) -> list[dict]:
    """从面试题部分提取问题列表。"""
    if not md:
        return []
    questions = []
    # 匹配「**Q: ...** A: ...」或「**问题N：...**」或「- Q：...」格式
    patterns = [
        r"\*\*(?:Q\d*[：:]\s*|问题\d*[：:]\s*)(.+?)\*\*(?:\n+(?:A[：:]\s*)?(.+?))?(?=\n\*\*|\Z)",
        r"[-•]\s*\*\*(.+?)\*\*(?:\n+(.+?))?(?=\n[-•]|\Z)",
        r"\d+\.\s*\*\*(.+?)\*\*(?:\n+(.+?))?(?=\n\d+\.|\Z)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, md, re.DOTALL):
            q_text = m.group(1).strip()
            a_text = (m.group(2) or "").strip()[:500]
            if q_text and len(q_text) > 5:
                questions.append({
                    "type": "understanding",
                    "prompt": q_text,
                    "rubric": a_text or "请结合本章内容作答。",
                })
        if questions:
            break

    # 如果正则没抓到，回退：把整块面试题 MD 作为一道大题
    if not questions and md.strip():
        questions = [{
            "type": "understanding",
            "prompt": "请总结本章的核心面试考点，并说明如何在面试中回答。",
            "rubric": md[:1000],
        }]
    return questions[:10]  # 最多10题


def _extract_takeaways(md: str) -> list[str]:
    """从必须记住/总结部分提取要点列表。"""
    if not md:
        return []
    items = []
    for line in md.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")):
            text = line[2:].strip()
            if text:
                items.append(text)
        elif re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^\d+\.\s+", "", line).strip()
            if text:
                items.append(text)
    return items[:10]


# ─────────────────────────────────────────────────────────────────────────────
# 部署逻辑
# ─────────────────────────────────────────────────────────────────────────────

def convert_chapter(node_id: str, chapter_num: int) -> Path | None:
    """把单章 MD 转成 lesson JSON，写入 StudyAthena/content/lessons/。"""
    md_path = CHAPTERS_DIR / f"ch{chapter_num:02d}_{node_id}.md"
    if not md_path.exists():
        print(f"  [Deploy] ❌ 章节文件不存在: {md_path.name}")
        return None

    # 检查文件是否有实际内容（排除只有注释头的空文件）
    raw = md_path.read_text(encoding="utf-8")
    content_without_comment = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()
    if len(content_without_comment) < 500:
        print(f"  [Deploy] ⚠️  章节内容过短（{len(content_without_comment)}字符），跳过: {md_path.name}")
        return None

    slug = CHAPTER_SLUGS.get(node_id, f"aios-ch{chapter_num:02d}")
    out_path = LESSONS_DIR / f"{slug}.json"

    lesson = md_to_lesson_json(md_path, node_id, chapter_num)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [Deploy] ✅ 已写入: {out_path.name}  ({len(content_without_comment)}字符)")
    return out_path


def deploy_backend(log_fn=None) -> bool:
    """
    部署流程：
    1. git add content/ → commit → push（本地 StudyAthena 仓库）
    2. SSH EC2 → git pull → docker compose restart backend

    content/ 已通过 bind mount 挂载到容器，git pull 后 restart 即刻生效，
    无需重建镜像。
    """
    def log(msg: str):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    ssh_host = "ec2-ollama"
    remote_dir = "/opt/studyathena"

    # ── Step 1: git add + commit + push ──────────────────────────────────────
    log("  [Deploy] git add content/ ...")
    r = subprocess.run(
        ["git", "add", "content/"],
        cwd=str(STUDYATHENA_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        log(f"  [Deploy] ❌ git add 失败:\n{r.stderr[:300]}")
        return False

    # 检查是否有实际变更需要提交
    status = subprocess.run(
        ["git", "status", "--porcelain", "content/"],
        cwd=str(STUDYATHENA_ROOT),
        capture_output=True, text=True, encoding="utf-8",
    )
    if not status.stdout.strip():
        log("  [Deploy] ℹ️  content/ 无变更，无需提交")
    else:
        log("  [Deploy] git commit ...")
        r = subprocess.run(
            ["git", "commit", "-m", "chore: auto-deploy AI Education OS lesson content"],
            cwd=str(STUDYATHENA_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            log(f"  [Deploy] ❌ git commit 失败:\n{r.stderr[:300]}")
            return False

        log("  [Deploy] git push origin main ...")
        r = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(STUDYATHENA_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
        if r.returncode != 0:
            log(f"  [Deploy] ❌ git push 失败:\n{r.stderr[:300]}")
            return False
        log("  [Deploy] ✅ 代码已推送到 GitHub")

    # ── Step 2: 重建 aios-bible.json 并 docker cp 进 volume ──────────────────
    bible_src = STUDYATHENA_ROOT / "frontend" / "public" / "data" / "aios-bible.json"
    aios_root = Path(__file__).resolve().parent
    try:
        import importlib.util as _ilu, sys as _sys
        spec = _ilu.spec_from_file_location("build_aios_bible", aios_root / "build_aios_bible.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(dry_run=False)
        log("  [Deploy] ✅ aios-bible.json 已重建")
    except Exception as e:
        log(f"  [Deploy] ⚠️  aios-bible.json 重建失败（跳过）: {e}")

    # ── Step 3: EC2 git pull + docker cp aios-bible.json + restart backend ──
    log(f"  [Deploy] SSH {ssh_host}: git pull + cp aios-bible.json + restart backend ...")
    remote_cmd = (
        f"cd {remote_dir} && git pull --ff-only origin main "
        f"&& docker cp {remote_dir}/frontend/public/data/aios-bible.json "
        f"studyathena-frontend:/app/public/data/aios-bible.json "
        f"&& docker compose restart backend"
    )
    try:
        r = subprocess.run(
            ["ssh", ssh_host, remote_cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90,
        )
        if r.returncode != 0:
            log(f"  [Deploy] ❌ EC2 操作失败:\n{r.stderr[:300]}")
            return False
        log("  [Deploy] ✅ EC2 已更新，新章节已上线！")
        return True
    except subprocess.TimeoutExpired:
        log("  [Deploy] ❌ SSH 超时")
        return False


def deploy_chapter(node_id: str, chapter_num: int, do_deploy: bool = True,
                   log_fn=None) -> bool:
    """
    完整的单章部署流程：
    1. 转换 MD → lesson JSON
    2. （可选）rsync content + 重启 backend
    """
    def log(msg):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    log(f"\n[Deploy] 部署第{chapter_num}章 {node_id} ...")
    out = convert_chapter(node_id, chapter_num)
    if out is None:
        return False

    if do_deploy:
        return deploy_backend(log_fn=log_fn)
    return True


def deploy_all(do_deploy: bool = True, log_fn=None) -> tuple[int, int]:
    """
    部署所有已生成的章节。
    返回 (成功数, 失败数)。
    """
    def log(msg):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    converted = 0
    failed = 0

    log(f"\n[Deploy] 扫描已生成章节...")
    for chapter_num, node_id in CHAPTER_NUM_TO_NODE.items():
        md_path = CHAPTERS_DIR / f"ch{chapter_num:02d}_{node_id}.md"
        if not md_path.exists():
            continue
        out = convert_chapter(node_id, chapter_num)
        if out:
            converted += 1
        else:
            failed += 1

    log(f"[Deploy] 转换完成: {converted} 章成功, {failed} 章跳过/失败")

    if converted > 0 and do_deploy:
        log("[Deploy] 开始 git push + 重启 backend...")
        ok = deploy_backend(log_fn=log_fn)
        if not ok:
            failed += 1

    return converted, failed


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Education OS — 章节部署器")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chapter", type=int, help="部署指定章节号（1-41）")
    group.add_argument("--all", action="store_true", help="部署所有已生成章节")
    parser.add_argument("--no-deploy", action="store_true",
                        help="只转换 JSON，不 SSH 部署（本地调试）")
    args = parser.parse_args()

    do_deploy = not args.no_deploy

    if args.chapter:
        node_id = CHAPTER_NUM_TO_NODE.get(args.chapter)
        if not node_id:
            print(f"❌ 无效章节号: {args.chapter}（有效范围 1-41）")
            sys.exit(1)
        ok = deploy_chapter(node_id, args.chapter, do_deploy=do_deploy)
        sys.exit(0 if ok else 1)
    else:
        ok_count, fail_count = deploy_all(do_deploy=do_deploy)
        print(f"\n✅ 完成：{ok_count} 章已部署，{fail_count} 章失败")
        sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
