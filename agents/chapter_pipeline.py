"""
agents/chapter_pipeline.py
--------------------------
章节生成 Pipeline：Research → Write → Review → [Rewrite] → Save
实现 SPEC-002 中定义的 6 步并行策略（单章串行，多章可并行）。

Quality Gate：
  score >= 95 → 直接保存
  85 <= score < 95 → Writer 基于反馈改进后保存
  score < 85 → 重新 Research + Write（最多 MAX_REWRITES 次）
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ENGINE_PATH = Path(__file__).parent.parent / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
sys.path.insert(0, str(ENGINE_INNER))
sys.path.insert(0, str(ENGINE_PATH))

from agents.knowledge_loader import load_node, load_nodes_by_ids, list_all_nodes
from agents.researcher_agent import ResearcherAgent
from agents.writer_agent import WriterAgent, _normalize_markdown as _normalize_md, SYSTEM_PROMPT as WRITER_SYSTEM_PROMPT
from agents.reviewer_agent import ReviewerAgent

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "chapters"
STATE_DIR = Path(__file__).parent.parent / "output" / "state"

MAX_REWRITES = 3  # 最多重写次数


@dataclass
class ChapterResult:
    node_id: str
    node_name: str
    chapter_num: int
    status: str  # "success" | "failed" | "skipped"
    score: int = 0
    attempts: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class PipelineState:
    """持久化 Pipeline 运行状态，支持断点续跑。"""
    completed: dict[str, ChapterResult] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "completed": {
                k: v.__dict__ for k, v in self.completed.items()
            },
            "failed": self.failed,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        state = cls()
        for k, v in data.get("completed", {}).items():
            state.completed[k] = ChapterResult(**v)
        state.failed = data.get("failed", [])
        return state


def _load_chatgpt_account_ids() -> list[str]:
    """从 accounts.json 读取所有 ChatGPT 账号编号（"1","2",…）。"""
    accounts_file = Path(__file__).parent.parent / "engine" / "llm" / "accounts.json"
    try:
        import json as _j
        data = _j.loads(accounts_file.read_text(encoding="utf-8"))
        return [str(i + 1) for i in range(len(data.get("accounts", [])))]
    except Exception:
        return ["1", "2", "3", "4"]


class ChapterPipeline:
    """
    单章节生成 Pipeline。

    Writer（ChatGPT）浏览器全程常驻，每章只开新对话，不重启浏览器。
    Researcher / Reviewer（DeepSeek）因需要与 Playwright 串行，仍按需创建关闭。
    """

    def __init__(
        self,
        researcher_provider: str = "deepseek",
        writer_provider: str = "chatgpt",
        reviewer_provider: str = "deepseek",
        account: str = "1",
        reviewer_account: str | None = None,
    ):
        self._researcher_provider = researcher_provider
        self._writer_provider = writer_provider
        self._reviewer_provider = reviewer_provider
        self._account = account
        # reviewer 可单独指定账号（DeepSeek被封时换账号用）
        self._reviewer_account = reviewer_account if reviewer_account else account
        # ChatGPT 账号轮换列表（当前账号不可用时自动切换）
        all_ids = _load_chatgpt_account_ids()
        try:
            start = all_ids.index(account)
            self._chatgpt_accounts = all_ids[start:] + all_ids[:start]
        except ValueError:
            self._chatgpt_accounts = all_ids
        self._chatgpt_account_idx = 0
        # 三个 Agent 浏览器全部常驻（懒启动，首次使用时创建，章节间只开新对话不重启）
        self._writer: WriterAgent | None = None
        self._researcher: ResearcherAgent | None = None
        self._reviewer: ReviewerAgent | None = None
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _current_chatgpt_account(self) -> str:
        return self._chatgpt_accounts[self._chatgpt_account_idx % len(self._chatgpt_accounts)]

    def _rotate_chatgpt_account(self) -> str:
        """切换到下一个 ChatGPT 账号（关闭旧浏览器，启动新账号浏览器）。"""
        # 真正关闭当前账号浏览器
        if self._writer:
            self._writer.shutdown()
            self._writer = None
        self._chatgpt_account_idx += 1
        acc = self._current_chatgpt_account()
        print(f"  [账号切换] 切换到 ChatGPT 账号 {acc}")
        return acc

    def _get_writer(self) -> WriterAgent:
        """获取常驻 Writer 实例，不存在时创建，已存在时复用。"""
        if self._writer is None:
            acc = self._current_chatgpt_account()
            print(f"[Pipeline] 启动 Writer 浏览器 ({self._writer_provider}, 账号 {acc})...")
            self._writer = WriterAgent(provider=self._writer_provider, account=acc)
        return self._writer

    def _new_chapter_conversation(self) -> None:
        """每章开始前：在现有浏览器里开新对话（不重启 Chrome）。"""
        if self._writer:
            self._writer.close()  # close() = 新对话，不关浏览器

    def _get_researcher(self) -> ResearcherAgent:
        """获取常驻 Researcher 实例，不存在时创建，已存在时复用（浏览器不重启）。"""
        if self._researcher is None:
            print(f"[Pipeline] 启动 Researcher 浏览器 ({self._researcher_provider}, account={self._reviewer_account})...")
            self._researcher = ResearcherAgent(provider=self._researcher_provider, account=self._reviewer_account)
        return self._researcher

    def _get_reviewer(self) -> ReviewerAgent:
        """获取常驻 Reviewer 实例，不存在时创建，已存在时复用（浏览器不重启）。"""
        if self._reviewer is None:
            print(f"[Pipeline] 启动 Reviewer 浏览器 ({self._reviewer_provider}, account={self._reviewer_account})...")
            self._reviewer = ReviewerAgent(provider=self._reviewer_provider, account=self._reviewer_account)
        return self._reviewer

    def run_chapter(
        self,
        node_id: str,
        chapter_num: int,
        related_node_ids: list[str] | None = None,
        force_rerun: bool = False,
    ) -> ChapterResult:
        """
        运行单章节生成流程。
        每步 Agent 按需创建、用完立即关闭，避免 Playwright 多实例冲突。
        如果该章节已有输出文件且 force_rerun=False，则跳过。
        """
        start_time = time.time()
        output_path = OUTPUT_DIR / f"ch{chapter_num:02d}_{node_id}.md"

        # 检查是否已完成（断点续跑）
        if output_path.exists() and not force_rerun:
            print(f"[Pipeline] ch{chapter_num:02d} {node_id} 已存在，跳过")
            return ChapterResult(
                node_id=node_id,
                node_name=node_id,
                chapter_num=chapter_num,
                status="skipped",
                output_path=str(output_path),
            )

        # 加载知识节点
        try:
            primary_node = load_node(node_id)
        except FileNotFoundError as e:
            return ChapterResult(
                node_id=node_id, node_name=node_id, chapter_num=chapter_num,
                status="failed", error=str(e),
                duration_seconds=time.time() - start_time,
            )

        node_name = primary_node.get("name", node_id)
        related_nodes = load_nodes_by_ids(related_node_ids) if related_node_ids else []

        print(f"\n[Pipeline] ========== 第{chapter_num}章: {node_name} ({node_id}) ==========")

        # Research：优先复用 history 里已有的缓存，避免重复调用 DeepSeek
        history_raw_dir = OUTPUT_DIR.parent / "history" / f"ch{chapter_num:02d}_{node_id}" / "raw"
        cached_research = sorted(history_raw_dir.glob("*_researcher.json")) if history_raw_dir.exists() else []
        if cached_research:
            latest = cached_research[-1]
            try:
                research_data = json.loads(latest.read_text(encoding="utf-8"))
                print(f"  [Pipeline] 复用已有 Research 缓存: {latest.name}")
            except Exception:
                research_data = None
        else:
            research_data = None

        if research_data is None:
            researcher = self._get_researcher()
            try:
                research_data = researcher.research(primary_node, related_nodes)
                _save_raw(chapter_num, node_id, "researcher",
                          json.dumps(research_data, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"  [Pipeline] Research 失败: {e}")
                research_data = _fallback_research(primary_node)

        chapter_content = ""
        review_result: dict = {}

        for attempt in range(1, MAX_REWRITES + 1):
            print(f"[Pipeline] 尝试 {attempt}/{MAX_REWRITES}")

            # ── Step 2: Write / Revise（浏览器常驻，只开新对话；账号不可用时轮换）──
            # chapter_content 在循环外保留上一轮的内容（作为改进基础）
            new_content = ""  # 本轮新生成的内容
            for acc_try in range(len(self._chatgpt_accounts)):
                # 每次写作前开一个新对话（浏览器不重启）
                self._new_chapter_conversation()
                writer = self._get_writer()
                try:
                    if attempt == 1:
                        new_content = writer.write(
                            primary_node, research_data, chapter_num, related_nodes
                        )
                        if new_content:
                            _save_raw(chapter_num, node_id, "writer", new_content,
                                      attempt=attempt, inner_round=1)
                    else:
                        issues = review_result.get("critical_issues", [])
                        suggestions = review_result.get("improvement_suggestions", [])
                        rewrite_focus = review_result.get("rewrite_focus", "")
                        prev_score = review_result.get("total_score", 0)
                        cur_score = locals().get("score", 0)  # score 可能在第1次attempt时尚未赋值
                        # 第3次（最后一次）attempt，或分数比上一轮更低，从零重新写
                        if attempt == MAX_REWRITES or (prev_score > 0 and cur_score > 0 and cur_score < prev_score - 5):
                            print(f"  [Pipeline] 分数{cur_score}，从零重新撰写（不叠加旧内容）...")
                            new_content = writer.write(
                                primary_node, research_data, chapter_num, related_nodes
                            )
                            if new_content:
                                _save_raw(chapter_num, node_id, "writer", new_content,
                                          attempt=attempt, inner_round=1)
                            chapter_content = new_content or chapter_content
                            continue
                        print(f"  [Pipeline] 基于上一版本（{prev_score}分）和评审反馈修改...")
                        new_content = _apply_improvements(
                            writer, primary_node, research_data,
                            chapter_content,  # 上一轮的章节内容（非空）
                            chapter_num, related_nodes,
                            issues, suggestions, rewrite_focus,
                        )
                        if new_content:
                            _save_raw(chapter_num, node_id, "writer_improve", new_content,
                                      attempt=attempt, inner_round=1)
                except Exception as e:
                    err = str(e)
                    print(f"  [Pipeline] Write 失败（账号 {self._current_chatgpt_account()}）: {err[:120]}")
                    new_content = ""

                # 内容够长 → 成功，退出账号轮换循环
                if new_content and len(new_content.strip()) >= 2000:
                    chapter_content = new_content
                    break
                # 内容过短 → 账号可能被封/session 失效，切换账号（会关闭旧浏览器，开新浏览器）
                if acc_try < len(self._chatgpt_accounts) - 1:
                    print(f"  [Pipeline] 账号 {self._current_chatgpt_account()} 不可用，切换账号...")
                    self._rotate_chatgpt_account()

            # 所有账号都试过了还是不行
            if not chapter_content or len(chapter_content.strip()) < 2000:
                print(f"  [Pipeline] 所有账号均无法完成写作（attempt {attempt}），{'重试' if attempt < MAX_REWRITES else '放弃'}")
                if attempt == MAX_REWRITES:
                    return ChapterResult(
                        node_id=node_id, node_name=node_name, chapter_num=chapter_num,
                        status="failed", error="所有 ChatGPT 账号均无法完成写作", attempts=attempt,
                        duration_seconds=time.time() - start_time,
                    )
                continue

            # ── Step 3: Review（Reviewer 用独立子进程跑 DeepSeek，完全隔离 Playwright 状态）─────
            reviewer = ReviewerAgent(provider=self._reviewer_provider, account=self._reviewer_account)
            try:
                review_result = reviewer.review(chapter_content, node_name, chapter_num)
            except Exception as e:
                import traceback as _tb
                print(f"  [Pipeline] Review 失败，使用默认分数: {e}")
                _tb.print_exc()
                review_result = {"total_score": 80, "passed": False, "rewrite_required": False,
                                 "critical_issues": [], "improvement_suggestions": []}

            score = review_result.get("total_score", 0)
            print(f"  [Pipeline] 评审分数: {score}")
            _save_raw(chapter_num, node_id, "reviewer",
                      json.dumps(review_result, ensure_ascii=False, indent=2),
                      attempt=attempt, inner_round=1)

            # ── Step 4: Quality Gate ─────────────────────────────────────────
            inner_round = 1
            if score >= 85:
                # 85分以上：若还有改进空间，在同一浏览器同一对话内继续改进
                if score < 95 and attempt < MAX_REWRITES:
                    print(f"  [Pipeline] 分数 {score}，在当前对话内细化改进后保存...")
                    issues = review_result.get("critical_issues", [])
                    suggestions = review_result.get("improvement_suggestions", [])
                    # 改进在同一对话内进行，不开新对话
                    improved = _apply_improvements(
                        writer, primary_node, research_data,
                        chapter_content, chapter_num, related_nodes,
                        issues, suggestions, "",
                    )
                    chapter_content = improved
                    inner_round = 2

                _save_chapter(output_path, chapter_content, review_result, chapter_num, node_id,
                              attempt=attempt, inner_round=inner_round)
                return ChapterResult(
                    node_id=node_id, node_name=node_name, chapter_num=chapter_num,
                    status="success", score=score, attempts=attempt,
                    output_path=str(output_path),
                    duration_seconds=time.time() - start_time,
                )

            else:
                rewrite_focus = review_result.get("rewrite_focus", "")
                print(f"  [Pipeline] 分数 {score} < 85，基于当前版本和评审意见修改（attempt {attempt}）。重点: {rewrite_focus}")
                if attempt == MAX_REWRITES:
                    print(f"  [Pipeline] 已达最大重写次数，分数{score}<85，仅存 history，不写 chapters/")
                    _save_chapter(output_path, chapter_content, review_result, chapter_num, node_id,
                                  low_quality=True, attempt=attempt, inner_round=inner_round)
                    return ChapterResult(
                        node_id=node_id, node_name=node_name, chapter_num=chapter_num,
                        status="failed", score=score, attempts=attempt,
                        error=f"分数{score}<85，超过最大重写次数",
                        duration_seconds=time.time() - start_time,
                    )
                # 继续下一轮，下一轮会把 chapter_content + review_result 传给 _apply_improvements
                continue

        return ChapterResult(
            node_id=node_id, node_name=node_name, chapter_num=chapter_num,
            status="failed", error="超过最大重写次数仍未通过",
            duration_seconds=time.time() - start_time,
        )

    def close(self):
        """所有章节生成完毕后，真正关闭所有浏览器。"""
        for name, agent in [("Writer", self._writer), ("Researcher", self._researcher), ("Reviewer", self._reviewer)]:
            if agent:
                try:
                    agent.shutdown()
                except Exception:
                    pass
                print(f"[Pipeline] {name} 浏览器已关闭")
        self._writer = self._researcher = self._reviewer = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _save_raw(
    chapter_num: int,
    node_id: str,
    label: str,
    content: str,
    attempt: int = 1,
    inner_round: int = 1,
) -> None:
    """把LLM原始回复保存到 output/history/chXX_NODE/raw/ 目录，永不覆盖。"""
    history_dir = OUTPUT_DIR.parent / "history" / f"ch{chapter_num:02d}_{node_id}" / "raw"
    history_dir.mkdir(parents=True, exist_ok=True)
    existing = list(history_dir.glob(f"*_a{attempt}_r{inner_round}_{label}.*"))
    next_v = len(existing) + 1
    ext = "json" if label in ("researcher", "reviewer") else "txt"
    fname = f"v{next_v}_a{attempt}_r{inner_round}_{label}.{ext}"
    (history_dir / fname).write_text(content, encoding="utf-8")
    print(f"  [History] 原始回复已保存: raw/{fname}")


def _save_chapter(
    path: Path,
    content: str,
    review: dict,
    chapter_num: int,
    node_id: str,
    low_quality: bool = False,
    attempt: int = 1,
    inner_round: int = 1,
) -> None:
    """
    保存章节版本到 history/（每次都保存）。
    只有 low_quality=False 时才写入 output/chapters/（正式版本）。
    低质量版本只存 history，不污染 chapters 目录。
    """
    score = review.get("total_score", 0)
    status_tag = "⚠️ LOW_QUALITY" if low_quality else "✅ APPROVED"
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    header = f"""<!--
Chapter: {chapter_num:02d}
Node: {node_id}
Score: {score}
Status: {status_tag}
Attempt: {attempt}
Round: {inner_round}
Generated: {ts}
-->

"""
    full_content = header + content

    # ── 历史版本（每次都保存，永不覆盖，无论质量高低）
    history_dir = path.parent.parent / "history" / f"ch{chapter_num:02d}_{node_id}"
    history_dir.mkdir(parents=True, exist_ok=True)
    existing = list(history_dir.glob("v*.md"))
    next_v = len(existing) + 1
    hist_name = f"v{next_v}_attempt{attempt}_round{inner_round}_score{score}.md"
    (history_dir / hist_name).write_text(full_content, encoding="utf-8")
    print(f"  [Pipeline] 历史版本: history/ch{chapter_num:02d}_{node_id}/{hist_name}")

    # ── 主文件：低质量版本不写入 chapters/，避免污染
    if low_quality:
        print(f"  [Pipeline] ⚠️ 分数{score}<85，仅存 history，不写入 chapters/")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(full_content, encoding="utf-8")
    print(f"  [Pipeline] 章节已保存: {path}")


def _apply_improvements(
    writer: WriterAgent,
    primary_node: dict,
    research_data: dict,
    original_content: str,
    chapter_num: int,
    related_nodes: list[dict],
    issues: list[dict],
    suggestions: list[dict],
    rewrite_focus: str = "",
) -> str:
    """
    基于评审反馈在原文基础上修改章节。
    把原文内容 + 评审意见一起发给 Writer，要求针对性修改，保留原有例子和故事。
    如果改进版不完整（< 2000字），返回原始版本。
    在独立线程中运行，避免 Playwright asyncio loop 冲突。
    """
    import threading as _threading
    import json as _json

    node_name = primary_node.get("name", "")
    level = primary_node.get("level", "L1-L2")

    issues_text = "\n".join(
        f"- {iss.get('issue', iss)}" for iss in issues
    ) if issues else "无严重问题"
    suggestions_text = "\n".join(
        f"- {s.get('suggestion', s)}" for s in suggestions
    ) if suggestions else "无"

    focus_text = f"\n评审要求重点修改：{rewrite_focus}" if rewrite_focus else ""

    improve_message = f"""请为第{chapter_num}章【{node_name}】重新撰写完整内容，在原版本基础上修正评审问题。

章节信息：
- 章节编号：第{chapter_num}章
- 知识节点：{primary_node.get('id', '')} - {node_name}
- 层级标注：[{level}]{focus_text}

评审发现的问题（必须修正）：
{issues_text}

改进建议：
{suggestions_text}

原版本（参考，不要直接复制，需全面改进）：
{original_content}

写作要求：
1. 必须输出完整的 15 个 Part（## Part 1：...到 ## Part 15：...）
2. 总字数 6000-10000 字
3. **评审指出有问题的地方**必须改正；评审没有指出问题的地方可保留原风格
4. 确保 Part 6 有完整可运行的 Python 代码示例

直接输出修改后的完整 Markdown 章节内容，不要有任何说明文字。严禁只输出部分内容或说明改了什么。"""

    # Playwright page 对象只能在创建它的线程（主线程）里调用
    # 直接在主线程调用，但先清除 Reviewer 子线程可能遗留的 asyncio loop
    import asyncio as _asyncio
    try:
        _asyncio.set_event_loop(None)
    except Exception:
        pass

    try:
        if hasattr(writer.llm, "chat_multipart"):
            response = writer.llm.chat_multipart(WRITER_SYSTEM_PROMPT, improve_message)
        else:
            response = writer.llm.chat([
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": improve_message},
            ])
        if response.strip() and len(response.strip()) >= 2000:
            print(f"  [Pipeline] 改进版本 {len(response)} 字符，采用改进版")
            return _normalize_md(response)
        else:
            print(f"  [Pipeline] 改进版本过短（{len(response)} 字符），保留原始版本")
            return original_content
    except Exception as e:
        print(f"  [Pipeline] 改进写作失败: {e}，使用原版本")
        return original_content


def _fallback_research(primary_node: dict) -> dict:
    """当 Researcher 失败时，从知识节点直接构建基础素材。"""
    return {
        "_node_id": primary_node.get("id", ""),
        "_node_name": primary_node.get("name", ""),
        "_level": primary_node.get("level", ""),
        "cognitive_conflict": {
            "scenario": f"你以为你已经理解了{primary_node.get('name', '')}？",
            "wrong_assumption": "大多数工程师对此有的误解",
            "correct_understanding": primary_node.get("one_liner", ""),
        },
        "life_analogy": primary_node.get("mental_model", "")[:200] if primary_node.get("mental_model") else "",
        "real_case": {
            "background": "生产环境实际案例",
            "problem": primary_node.get("why", "")[:200] if primary_node.get("why") else "",
            "solution": "应用本章知识解决",
            "result": "显著提升了系统质量",
        },
        "common_errors": [
            {"error": ap.get("pattern", ""), "consequence": ap.get("consequence", ""), "fix": ""}
            for ap in (primary_node.get("anti_patterns") or [])[:2]
        ],
        "interview_questions": [
            {"level": "L1", "question": q, "key_points": ""}
            for q in (primary_node.get("interview_points") or [])[:3]
        ],
        "memory_anchor": primary_node.get("one_liner", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 批量运行入口
# ─────────────────────────────────────────────────────────────────────────────

# 书籍章节顺序表（node_id, chapter_num, related_node_ids）
BOOK_CHAPTERS = [
    # Batch 1: AI Basics
    ("KN-C-000001", 1,  ["KN-C-000002", "KN-C-000003"]),
    ("KN-C-000002", 2,  ["KN-C-000001", "KN-C-000003"]),
    ("KN-C-000003", 3,  ["KN-C-000001", "KN-C-000002"]),
    ("KN-C-000004", 4,  ["KN-C-000001"]),
    ("KN-C-000005", 5,  ["KN-C-000001"]),
    # Batch 2: Prompt
    ("KN-C-000010", 6,  ["KN-P-000001", "KN-P-000002"]),
    ("KN-P-000001", 7,  ["KN-C-000010"]),
    ("KN-P-000002", 8,  ["KN-C-000010", "KN-P-000003"]),
    ("KN-P-000003", 9,  ["KN-P-000002", "KN-P-000004"]),
    ("KN-P-000004", 10, ["KN-P-000003", "KN-C-000020"]),
    # Batch 3: Agent
    ("KN-C-000020", 11, ["KN-P-000004", "KN-C-000021", "KN-C-000022"]),
    ("KN-C-000021", 12, ["KN-C-000020", "KN-P-000004"]),
    ("KN-C-000022", 13, ["KN-C-000020"]),
    ("KN-C-000023", 14, ["KN-C-000020", "KN-C-000021"]),
    ("KN-C-000024", 15, ["KN-C-000020", "KN-C-000021"]),
    # Batch 4: RAG
    ("KN-C-000030", 16, ["KN-C-000031", "KN-C-000033"]),
    ("KN-C-000031", 17, ["KN-C-000030"]),
    ("KN-C-000032", 18, ["KN-C-000030", "KN-C-000033"]),
    ("KN-C-000033", 19, ["KN-C-000030", "KN-C-000031", "KN-C-000032"]),
    ("KN-C-000034", 20, ["KN-C-000033"]),
    ("KN-C-000035", 21, ["KN-C-000033", "KN-C-000034"]),
    # Batch 5: Workflow
    ("KN-C-000025", 22, ["KN-C-000026"]),
    ("KN-C-000026", 23, ["KN-C-000025", "KN-C-000027", "KN-C-000028"]),
    ("KN-C-000027", 24, ["KN-C-000026"]),
    ("KN-C-000028", 25, ["KN-C-000026", "KN-C-000027", "KN-C-000024"]),
    # Batch 6: Evaluation
    ("KN-C-000036", 26, ["KN-C-000037", "KN-C-000038"]),
    ("KN-C-000037", 27, ["KN-C-000033", "KN-C-000036"]),
    ("KN-C-000038", 28, ["KN-C-000036", "KN-C-000039"]),
    ("KN-C-000039", 29, ["KN-C-000036", "KN-C-000038"]),
    # Batch 7: Security
    ("KN-C-000040", 30, ["KN-C-000042", "KN-C-000041"]),
    ("KN-C-000041", 31, ["KN-C-000040", "KN-C-000022"]),
    ("KN-C-000042", 32, ["KN-C-000040", "KN-C-000041"]),
    ("KN-C-000043", 33, ["KN-C-000040", "KN-C-000042"]),
    # Batch 8: Observability
    ("KN-C-000044", 34, ["KN-C-000046", "KN-C-000047"]),
    ("KN-C-000046", 35, ["KN-C-000044", "KN-C-000047"]),
    ("KN-C-000047", 36, ["KN-C-000044", "KN-C-000046"]),
    # Batch 9: Advanced
    ("KN-C-000050", 37, ["KN-C-000033"]),
    ("KN-C-000051", 38, ["KN-C-000020"]),
    ("KN-C-000052", 39, ["KN-C-000042", "KN-C-000044"]),
    ("KN-C-000053", 40, ["KN-C-000052", "KN-C-000021"]),
    ("KN-C-000054", 41, ["KN-C-000033"]),
]


def _auto_deploy(node_id: str, chapter_num: int) -> None:
    """生成完一章后自动部署到 StudyAthena（静默失败，不中断 Pipeline）。"""
    try:
        # deployer.py 在项目根目录，需要加入路径
        deploy_root = Path(__file__).parent.parent
        import sys as _sys
        if str(deploy_root) not in _sys.path:
            _sys.path.insert(0, str(deploy_root))
        from deployer import deploy_chapter
        print(f"  [AutoDeploy] 自动部署第{chapter_num}章到 StudyAthena...")
        ok = deploy_chapter(node_id, chapter_num, do_deploy=True)
        if ok:
            print(f"  [AutoDeploy] ✅ 第{chapter_num}章已上线: studyathena.com/paths/ai-education-os")
        else:
            print(f"  [AutoDeploy] ⚠️  部署失败（可稍后手动部署）")
    except Exception as e:
        print(f"  [AutoDeploy] ⚠️  自动部署异常（不影响生成）: {e}")


def run_book(
    start_chapter: int = 1,
    end_chapter: int | None = None,
    researcher_provider: str = "deepseek",
    writer_provider: str = "chatgpt",
    reviewer_provider: str = "deepseek",
    account: str = "1",
    reviewer_account: str | None = None,
    force_rerun: bool = False,
    auto_deploy: bool = True,
) -> None:
    """
    批量生成书籍所有章节。
    支持断点续跑：已存在的章节文件默认跳过。
    auto_deploy=True 时，每章生成完后自动部署到 StudyAthena。
    """
    state_path = STATE_DIR / "pipeline_state.json"
    state = PipelineState.load(state_path)

    chapters_to_run = [
        (nid, cnum, related)
        for nid, cnum, related in BOOK_CHAPTERS
        if cnum >= start_chapter and (end_chapter is None or cnum <= end_chapter)
    ]

    print(f"\n[Pipeline] 开始生成书籍，共 {len(chapters_to_run)} 章")
    print(f"[Pipeline] 已完成: {len(state.completed)} 章，跳过已完成的章节")
    if auto_deploy:
        print(f"[Pipeline] 自动部署: 开启（每章生成后即时上线到 StudyAthena）")

    with ChapterPipeline(
        researcher_provider=researcher_provider,
        writer_provider=writer_provider,
        reviewer_provider=reviewer_provider,
        account=account,
        reviewer_account="4",  # LucyQQ (acc_5c9d64a2)，DeepSeek Reviewer专用
    ) as pipeline:
        for node_id, chapter_num, related_ids in chapters_to_run:
            if node_id in state.completed and not force_rerun:
                print(f"[Pipeline] 跳过 ch{chapter_num:02d} {node_id}（已在状态记录中）")
                continue

            result = pipeline.run_chapter(node_id, chapter_num, related_ids, force_rerun)

            if result.status in ("success", "skipped"):
                state.completed[node_id] = result
                # 生成成功后自动部署
                if auto_deploy and result.status == "success":
                    _auto_deploy(node_id, chapter_num)
            else:
                state.failed.append(node_id)
                print(f"[Pipeline] ❌ ch{chapter_num:02d} {node_id} 失败: {result.error}")

            state.save(state_path)
            print(f"[Pipeline] 进度: {len(state.completed)}/{len(BOOK_CHAPTERS)} 章完成\n")

    print(f"\n[Pipeline] ✅ 完成！成功: {len(state.completed)} 章，失败: {len(state.failed)} 章")
    if state.failed:
        print(f"[Pipeline] 失败列表: {state.failed}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Education OS 书籍生成 Pipeline")
    parser.add_argument("--start", type=int, default=1, help="起始章节号")
    parser.add_argument("--end", type=int, default=None, help="结束章节号")
    parser.add_argument("--researcher", default="deepseek", help="Researcher LLM provider")
    parser.add_argument("--writer", default="chatgpt", help="Writer LLM provider")
    parser.add_argument("--reviewer", default="deepseek", help="Reviewer LLM provider")
    parser.add_argument("--account", default="1", help="LLM 账号编号")
    parser.add_argument("--force", action="store_true", help="强制重新生成（忽略已有文件）")
    args = parser.parse_args()

    run_book(
        start_chapter=args.start,
        end_chapter=args.end,
        researcher_provider=args.researcher,
        writer_provider=args.writer,
        reviewer_provider=args.reviewer,
        account=args.account,
        force_rerun=args.force,
    )
