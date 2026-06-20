"""
AI Education OS — 可视化控制台
================================
依赖: pip install customtkinter pyyaml
启动: python gui.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
ENGINE_PATH = ROOT / "engine" / "llm"
ENGINE_INNER = ENGINE_PATH / "engine"
for p in (str(ENGINE_INNER), str(ENGINE_PATH), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

PYTHON = sys.executable
OUTPUT_DIR = ROOT / "output" / "chapters"
STATE_FILE = ROOT / "output" / "state" / "pipeline_state.json"
KNOWLEDGE_DIR = ROOT / "knowledge"

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "green":  "#2ecc71",
    "red":    "#e74c3c",
    "yellow": "#f39c12",
    "muted":  "#7f8c8d",
    "blue":   "#3498db",
    "purple": "#9b59b6",
}

# 章节映射表（与 chapter_pipeline.py 保持一致）
BOOK_CHAPTERS = [
    ("KN-C-000001", 1,  "LLM (Large Language Model)"),
    ("KN-C-000002", 2,  "Token & Tokenization"),
    ("KN-C-000003", 3,  "Context Window"),
    ("KN-C-000004", 4,  "Temperature & Sampling"),
    ("KN-C-000005", 5,  "Hallucination"),
    ("KN-C-000010", 6,  "Prompt Engineering"),
    ("KN-P-000001", 7,  "Few-Shot Prompting"),
    ("KN-P-000002", 8,  "Chain-of-Thought"),
    ("KN-P-000003", 9,  "Prompt Chaining"),
    ("KN-P-000004", 10, "ReAct"),
    ("KN-C-000020", 11, "Agent"),
    ("KN-C-000021", 12, "Agent Loop"),
    ("KN-C-000022", 13, "Tool Use"),
    ("KN-C-000023", 14, "Planning"),
    ("KN-C-000024", 15, "Human-in-the-Loop"),
    ("KN-C-000030", 16, "Embedding"),
    ("KN-C-000031", 17, "Vector DB"),
    ("KN-C-000032", 18, "Chunking"),
    ("KN-C-000033", 19, "RAG"),
    ("KN-C-000034", 20, "Reranking"),
    ("KN-C-000035", 21, "Hybrid Search"),
    ("KN-C-000025", 22, "State Machine"),
    ("KN-C-000026", 23, "LangGraph"),
    ("KN-C-000027", 24, "Checkpoint"),
    ("KN-C-000028", 25, "Interrupt & Resume"),
    ("KN-C-000036", 26, "LLM-as-Judge"),
    ("KN-C-000037", 27, "RAGAS"),
    ("KN-C-000038", 28, "Eval Dataset"),
    ("KN-C-000039", 29, "Regression Testing"),
    ("KN-C-000040", 30, "Prompt Injection"),
    ("KN-C-000041", 31, "Agent Privilege Escalation"),
    ("KN-C-000042", 32, "Guardrails"),
    ("KN-C-000043", 33, "Tool Injection"),
    ("KN-C-000044", 34, "Tracing"),
    ("KN-C-000046", 35, "LLM Observability"),
    ("KN-C-000047", 36, "Structured Logging"),
    ("KN-C-000050", 37, "GraphRAG"),
    ("KN-C-000051", 38, "A2A Protocol"),
    ("KN-C-000052", 39, "FCARS"),
    ("KN-C-000053", 40, "Chaos Engineering"),
    ("KN-C-000054", 41, "Fine-Tuning"),
]

BATCH_LABELS = {
    (1, 5):   "📘 Batch 1 · AI 基础",
    (6, 10):  "💬 Batch 2 · Prompt",
    (11, 15): "🤖 Batch 3 · Agent",
    (16, 21): "🔍 Batch 4 · RAG",
    (22, 25): "🔄 Batch 5 · Workflow",
    (26, 29): "📊 Batch 6 · Evaluation",
    (30, 33): "🔒 Batch 7 · Security",
    (34, 36): "👁 Batch 8 · Observability",
    (37, 41): "🚀 Batch 9 · Advanced",
}


def _batch_label(ch: int) -> str:
    for (s, e), label in BATCH_LABELS.items():
        if s <= ch <= e:
            return label
    return ""


def _load_pipeline_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed": {}, "failed": []}


def _load_knowledge_nodes() -> list[dict]:
    """扫描 knowledge/ 目录，加载所有 YAML 节点。"""
    try:
        import yaml
    except ImportError:
        return []
    nodes = []
    if not KNOWLEDGE_DIR.exists():
        return nodes
    for f in sorted(KNOWLEDGE_DIR.rglob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data and isinstance(data, dict):
                data["_file"] = str(f.relative_to(ROOT))
                nodes.append(data)
        except Exception:
            pass
    return nodes


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip
# ─────────────────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text: str):
        self._w = widget
        self._text = text
        self._tip = None
        self._after = None
        widget.bind("<Enter>", self._sched_show)
        widget.bind("<Leave>", self._sched_hide)

    def _sched_show(self, _=None):
        if self._after:
            self._w.after_cancel(self._after)
        self._after = self._w.after(400, self._show)

    def _show(self):
        self._after = None
        if self._tip:
            return
        x = self._w.winfo_rootx() + self._w.winfo_width() + 4
        y = self._w.winfo_rooty()
        self._tip = tw = ctk.CTkToplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        ctk.CTkLabel(tw, text=self._text, justify="left",
                     font=("", 11), fg_color=("#f0f0f0", "#2a2a2a"),
                     corner_radius=6, padx=10, pady=8).pack()
        self._w.after(4000, self._hide)

    def _sched_hide(self, _=None):
        if self._after:
            self._w.after_cancel(self._after)
        self._after = self._w.after(200, self._hide)

    def _hide(self):
        self._after = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ─────────────────────────────────────────────────────────────────────────────
# 主窗口
# ─────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Education OS — 书籍生成控制台")
        self.geometry("1280x820")
        self.minsize(1024, 640)

        self._proc: subprocess.Popen | None = None
        self._log_queue: Queue = Queue()
        self._nodes: list[dict] = []
        self._selected_node: dict | None = None

        self._build_ui()
        self._poll_log()
        self._refresh_pipeline_status()

        # 后台加载知识节点（避免启动卡顿）
        threading.Thread(target=self._bg_load_nodes, daemon=True).start()

    # ── UI 骨架 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._tabview = ctk.CTkTabview(self, anchor="nw")
        self._tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self._tabview.add("▶ 生成控制")
        self._tabview.add("📊 Pipeline 状态")
        self._tabview.add("📖 章节查看")
        self._tabview.add("🗂 知识节点")
        self._tabview.add("🚀 部署")

        self._build_gen_tab(self._tabview.tab("▶ 生成控制"))
        self._build_status_tab(self._tabview.tab("📊 Pipeline 状态"))
        self._build_viewer_tab(self._tabview.tab("📖 章节查看"))
        self._build_nodes_tab(self._tabview.tab("🗂 知识节点"))
        self._build_deploy_tab(self._tabview.tab("🚀 部署"))

        self._status_bar = ctk.CTkLabel(
            self, text="就绪", anchor="w",
            fg_color=("#ddd", "#333"), corner_radius=4
        )
        self._status_bar.pack(fill="x", padx=8, pady=(0, 6))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1：生成控制
    # ─────────────────────────────────────────────────────────────────────────

    def _build_gen_tab(self, parent):
        # 左侧参数面板
        left_outer = ctk.CTkFrame(parent, width=300)
        left_outer.pack(side="left", fill="y", padx=(0, 6))
        left_outer.pack_propagate(False)
        left = ctk.CTkScrollableFrame(left_outer, fg_color="transparent")
        left.pack(fill="both", expand=True)

        ctk.CTkLabel(left, text="⚙️ 生成参数", font=("", 14, "bold")).pack(pady=(10, 6))

        def row(label, widget_fn, tip=""):
            r = ctk.CTkFrame(left, fg_color="transparent")
            r.pack(fill="x", padx=8, pady=3)
            lbl = ctk.CTkLabel(r, text=label, width=90, anchor="w", font=("", 12))
            lbl.pack(side="left")
            w = widget_fn(r)
            w.pack(side="left", expand=True, fill="x")
            if tip:
                Tooltip(lbl, tip)
                Tooltip(w, tip)
            return w

        # 章节范围
        self._start_var = ctk.StringVar(value="1")
        self._end_var = ctk.StringVar(value="")
        row("起始章节", lambda p: ctk.CTkEntry(p, textvariable=self._start_var, width=60),
            "从第几章开始生成（默认 1）")
        row("结束章节", lambda p: ctk.CTkEntry(
            p, textvariable=self._end_var, placeholder_text="空=全部", width=60),
            "到第几章结束（空=生成全部）")

        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=6)

        # LLM Provider
        self._researcher_var = ctk.StringVar(value="deepseek")
        self._writer_var = ctk.StringVar(value="chatgpt")
        self._reviewer_var = ctk.StringVar(value="deepseek")
        self._account_var = ctk.StringVar(value="1")

        row("Researcher", lambda p: ctk.CTkOptionMenu(
            p, variable=self._researcher_var, values=["deepseek", "chatgpt"]),
            "Researcher Agent 使用的 LLM\n推荐 DeepSeek（技术分析能力强）")
        row("Writer", lambda p: ctk.CTkOptionMenu(
            p, variable=self._writer_var, values=["chatgpt", "deepseek"]),
            "Writer Agent 使用的 LLM\n推荐 ChatGPT（叙事/教学设计更好）")
        row("Reviewer", lambda p: ctk.CTkOptionMenu(
            p, variable=self._reviewer_var, values=["deepseek", "chatgpt"]),
            "Reviewer Agent 使用的 LLM\n推荐 DeepSeek（技术准确性评审）")
        row("账号编号", lambda p: ctk.CTkEntry(p, textvariable=self._account_var, width=60),
            "LLM 账号编号（1-6）\n对应 engine/llm/accounts.json")

        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=6)

        # 选项
        self._force_var = ctk.BooleanVar(value=False)
        r_force = ctk.CTkFrame(left, fg_color="transparent")
        r_force.pack(fill="x", padx=8, pady=3)
        cb = ctk.CTkCheckBox(r_force, text="强制重新生成（忽略已有文件）",
                             variable=self._force_var)
        cb.pack(side="left")
        Tooltip(cb, "勾选后，已生成的章节也会重新生成\n用于强制刷新某个章节")

        # 命令预览
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(left, text="将执行：", font=("", 10), text_color="gray").pack(anchor="w", padx=8)
        self._cmd_label = ctk.CTkLabel(
            left, text="—", font=("Consolas", 10), anchor="w",
            wraplength=260, text_color=("#0070c0", "#88ccff"))
        self._cmd_label.pack(fill="x", padx=8, pady=(0, 6))

        for v in (self._start_var, self._end_var, self._researcher_var,
                  self._writer_var, self._reviewer_var, self._account_var, self._force_var):
            v.trace_add("write", lambda *_: self._update_cmd_preview())
        self._update_cmd_preview()

        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=4)

        def btn(text, color, cmd, tip=""):
            b = ctk.CTkButton(left, text=text, fg_color=color, command=cmd)
            b.pack(fill="x", pady=3, padx=6)
            if tip:
                Tooltip(b, tip)
            return b

        self._run_btn = btn("▶  开始生成", "#1c7c3a", self._on_run,
                            "启动章节生成 Pipeline\n将打开浏览器并自动操作 LLM")
        btn("⏹  停止", "#8b1c1c", self._on_stop, "终止当前运行")
        btn("🔄  刷新状态", "transparent", self._refresh_pipeline_status)

        # 右侧日志
        right = ctk.CTkFrame(parent)
        right.pack(side="left", fill="both", expand=True)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="📋 运行日志", font=("", 13, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🗑 清空", width=70, height=24,
                      fg_color="transparent", border_width=1,
                      command=self._clear_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(right, font=("Consolas", 11))
        self._log_box.pack(fill="both", expand=True, pady=(4, 0))

    def _update_cmd_preview(self, *_):
        parts = [f"python run.py",
                 f"--start {self._start_var.get() or 1}"]
        end = self._end_var.get().strip()
        if end:
            parts.append(f"--end {end}")
        parts += [
            f"--researcher {self._researcher_var.get()}",
            f"--writer {self._writer_var.get()}",
            f"--reviewer {self._reviewer_var.get()}",
            f"--account {self._account_var.get() or 1}",
        ]
        if self._force_var.get():
            parts.append("--force")
        self._cmd_label.configure(text=" ".join(parts))

    def _on_run(self):
        if self._proc and self._proc.poll() is None:
            self._log("⚠️ 已有任务在运行，请先停止"); return

        cmd = [PYTHON, str(ROOT / "run.py"),
               "--start", self._start_var.get() or "1",
               "--researcher", self._researcher_var.get(),
               "--writer", self._writer_var.get(),
               "--reviewer", self._reviewer_var.get(),
               "--account", self._account_var.get() or "1"]
        end = self._end_var.get().strip()
        if end:
            cmd += ["--end", end]
        if self._force_var.get():
            cmd.append("--force")

        self._log(f"\n{'='*60}\n▶ {' '.join(cmd[2:])}\n{'='*60}")
        self._run_btn.configure(state="disabled")
        self._status_bar.configure(text="生成中…")
        self._start_proc(cmd)

    def _on_stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log("\n⏹ 已停止")
        self._run_btn.configure(state="normal")
        self._status_bar.configure(text="已停止")

    def _start_proc(self, cmd: list):
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1, cwd=str(ROOT)
        )
        threading.Thread(target=self._read_proc, daemon=True).start()

    def _read_proc(self):
        for line in self._proc.stdout:
            self._log_queue.put(("log", line.rstrip()))
        self._proc.wait()
        self._log_queue.put(("log", f"\n{'='*60}\n✅ 进程结束，返回码: {self._proc.returncode}"))
        self._log_queue.put(("done", None))

    def _log(self, msg: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _poll_log(self):
        try:
            while True:
                kind, msg = self._log_queue.get_nowait()
                if kind == "log":
                    self._log(msg)
                elif kind == "done":
                    self._run_btn.configure(state="normal")
                    self._status_bar.configure(text="完成 ✅")
                    self._refresh_pipeline_status()
                    self._refresh_chapter_list()
        except Empty:
            pass
        self.after(200, self._poll_log)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2：Pipeline 状态
    # ─────────────────────────────────────────────────────────────────────────

    def _build_status_tab(self, parent):
        toolbar = ctk.CTkFrame(parent, height=44)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        ctk.CTkLabel(toolbar, text="📊 Pipeline 状态",
                     font=("", 14, "bold")).pack(side="left", padx=12, pady=10)
        ctk.CTkButton(toolbar, text="🔄 刷新", width=80, height=28,
                      command=self._refresh_pipeline_status).pack(side="right", padx=10, pady=8)

        # 进度汇总
        self._progress_label = ctk.CTkLabel(
            parent, text="加载中…", font=("", 13),
            fg_color=("#e8f4e8", "#1a3a1a"), corner_radius=6)
        self._progress_label.pack(fill="x", padx=8, pady=6)

        # 章节状态表
        hdr_row = ctk.CTkFrame(parent, fg_color=("#c0c0c0", "#222"))
        hdr_row.pack(fill="x", padx=8)
        for text, w in [("章", 40), ("知识节点 ID", 150), ("章节名称", 220),
                        ("批次", 160), ("状态", 80), ("分数", 60), ("输出文件", 220)]:
            ctk.CTkLabel(hdr_row, text=text, width=w, font=("", 11, "bold"),
                         anchor="w").pack(side="left", padx=4, pady=4)

        self._status_scroll = ctk.CTkScrollableFrame(parent)
        self._status_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _refresh_pipeline_status(self):
        # 清空旧行
        for w in self._status_scroll.winfo_children():
            w.destroy()

        state = _load_pipeline_state()
        completed = state.get("completed", {})
        failed_list = state.get("failed", [])

        done_count = len(completed)
        fail_count = len(failed_list)
        total = len(BOOK_CHAPTERS)

        # 进度标签
        self._progress_label.configure(
            text=f"✅ 已完成 {done_count} / {total} 章    "
                 f"❌ 失败 {fail_count} 章    "
                 f"⏳ 待处理 {total - done_count - fail_count} 章"
        )

        for node_id, ch_num, ch_name in BOOK_CHAPTERS:
            result = completed.get(node_id)
            is_failed = node_id in failed_list
            out_file = OUTPUT_DIR / f"ch{ch_num:02d}_{node_id}.md"
            file_exists = out_file.exists()

            if result:
                status_text = "✅ 完成"
                status_color = COLORS["green"]
                score_text = str(result.get("score", 0)) if isinstance(result, dict) else "—"
                out_text = f"ch{ch_num:02d}_{node_id}.md" if file_exists else "文件缺失"
            elif is_failed:
                status_text = "❌ 失败"
                status_color = COLORS["red"]
                score_text = "—"
                out_text = "—"
            elif file_exists:
                status_text = "📄 有文件"
                status_color = COLORS["yellow"]
                score_text = "—"
                out_text = f"ch{ch_num:02d}_{node_id}.md"
            else:
                status_text = "⏳ 待处理"
                status_color = COLORS["muted"]
                score_text = "—"
                out_text = "—"

            row_frame = ctk.CTkFrame(self._status_scroll,
                                     fg_color="transparent")
            row_frame.pack(fill="x", pady=1)

            batch = _batch_label(ch_num)
            items = [
                (str(ch_num), 40),
                (node_id, 150),
                (ch_name[:28], 220),
                (batch, 160),
            ]
            for text, w in items:
                ctk.CTkLabel(row_frame, text=text, width=w, anchor="w",
                             font=("", 11)).pack(side="left", padx=4)

            ctk.CTkLabel(row_frame, text=status_text, width=80, anchor="w",
                         font=("", 11, "bold"),
                         text_color=status_color).pack(side="left", padx=4)
            ctk.CTkLabel(row_frame, text=score_text, width=60,
                         anchor="w", font=("", 11)).pack(side="left", padx=4)

            if file_exists:
                btn = ctk.CTkButton(
                    row_frame, text=out_text, width=220, height=22,
                    fg_color="transparent", border_width=1,
                    font=("Consolas", 10), anchor="w",
                    command=lambda n=node_id, c=ch_num: self._open_chapter_in_viewer(n, c)
                )
                btn.pack(side="left", padx=4)
            else:
                ctk.CTkLabel(row_frame, text=out_text, width=220,
                             anchor="w", font=("", 11),
                             text_color=COLORS["muted"]).pack(side="left", padx=4)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 3：章节查看
    # ─────────────────────────────────────────────────────────────────────────

    def _build_viewer_tab(self, parent):
        # 左侧文件列表
        left = ctk.CTkFrame(parent, width=260)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="📚 已生成章节", font=("", 13, "bold")).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(hdr, text="🔄", width=36, height=28,
                      command=self._refresh_chapter_list).pack(side="right", padx=6, pady=6)

        self._chapter_list_frame = ctk.CTkScrollableFrame(left)
        self._chapter_list_frame.pack(fill="both", expand=True)

        # 右侧内容
        right = ctk.CTkFrame(parent)
        right.pack(side="left", fill="both", expand=True)

        ch_hdr = ctk.CTkFrame(right, fg_color="transparent")
        ch_hdr.pack(fill="x")
        self._viewer_title = ctk.CTkLabel(
            ch_hdr, text="← 选择左侧章节查看内容",
            font=("", 13, "bold"), anchor="w")
        self._viewer_title.pack(side="left", padx=8, pady=8)

        self._viewer_box = ctk.CTkTextbox(right, font=("Consolas", 11), wrap="word")
        self._viewer_box.pack(fill="both", expand=True, padx=0, pady=0)

        self._refresh_chapter_list()

    def _refresh_chapter_list(self):
        for w in self._chapter_list_frame.winfo_children():
            w.destroy()

        if not OUTPUT_DIR.exists():
            ctk.CTkLabel(self._chapter_list_frame,
                         text="还没有生成任何章节", text_color=COLORS["muted"]).pack(pady=20)
            return

        files = sorted(OUTPUT_DIR.glob("ch*.md"))
        if not files:
            ctk.CTkLabel(self._chapter_list_frame,
                         text="还没有生成任何章节", text_color=COLORS["muted"]).pack(pady=20)
            return

        for f in files:
            name = f.stem
            btn = ctk.CTkButton(
                self._chapter_list_frame, text=name, anchor="w",
                fg_color="transparent", hover_color=("#3a6ea0", "#1a4a7a"),
                font=("Consolas", 11), height=32,
                command=lambda fp=f: self._load_chapter(fp)
            )
            btn.pack(fill="x", pady=1, padx=2)

    def _load_chapter(self, filepath: Path):
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            content = f"读取失败: {e}"
        self._viewer_title.configure(text=filepath.name)
        self._viewer_box.configure(state="normal")
        self._viewer_box.delete("1.0", "end")
        self._viewer_box.insert("end", content)
        self._viewer_box.configure(state="disabled")
        self._tabview.set("📖 章节查看")

    def _open_chapter_in_viewer(self, node_id: str, ch_num: int):
        fp = OUTPUT_DIR / f"ch{ch_num:02d}_{node_id}.md"
        if fp.exists():
            self._load_chapter(fp)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 4：知识节点
    # ─────────────────────────────────────────────────────────────────────────

    def _build_nodes_tab(self, parent):
        # 左侧节点列表
        left = ctk.CTkFrame(parent, width=300)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="🗂 知识节点库",
                     font=("", 13, "bold")).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(hdr, text="🔄", width=36, height=28,
                      command=lambda: threading.Thread(
                          target=self._bg_load_nodes, daemon=True).start()
                      ).pack(side="right", padx=6, pady=6)

        # 搜索框
        self._node_search_var = ctk.StringVar()
        search = ctk.CTkEntry(left, placeholder_text="搜索节点 ID / 名称…",
                              textvariable=self._node_search_var)
        search.pack(fill="x", padx=8, pady=(0, 4))
        self._node_search_var.trace_add("write", lambda *_: self._filter_nodes())

        self._node_count_label = ctk.CTkLabel(
            left, text="加载中…", font=("", 10), text_color=COLORS["muted"])
        self._node_count_label.pack(anchor="w", padx=8)

        self._node_list_frame = ctk.CTkScrollableFrame(left)
        self._node_list_frame.pack(fill="both", expand=True)

        # 右侧详情
        right = ctk.CTkFrame(parent)
        right.pack(side="left", fill="both", expand=True)

        node_hdr = ctk.CTkFrame(right, fg_color="transparent")
        node_hdr.pack(fill="x")
        self._node_title = ctk.CTkLabel(
            node_hdr, text="← 选择左侧节点查看详情",
            font=("", 13, "bold"), anchor="w")
        self._node_title.pack(side="left", padx=8, pady=8)
        self._node_file_label = ctk.CTkLabel(
            node_hdr, text="", font=("Consolas", 10),
            text_color=COLORS["muted"], anchor="w")
        self._node_file_label.pack(side="left", padx=4)

        self._node_detail_box = ctk.CTkTextbox(right, font=("Consolas", 11), wrap="word")
        self._node_detail_box.pack(fill="both", expand=True)

    def _bg_load_nodes(self):
        nodes = _load_knowledge_nodes()
        self._nodes = nodes
        self.after(0, self._render_node_list, nodes)

    def _render_node_list(self, nodes: list[dict]):
        for w in self._node_list_frame.winfo_children():
            w.destroy()
        self._node_count_label.configure(text=f"共 {len(nodes)} 个节点")
        for node in nodes:
            node_id = node.get("id", "?")
            name = node.get("name", node_id)[:30]
            level = node.get("level", "")
            btn = ctk.CTkButton(
                self._node_list_frame,
                text=f"{node_id}\n{name}  [{level}]",
                anchor="w", fg_color="transparent",
                hover_color=("#3a6ea0", "#1a4a7a"),
                font=("", 11), height=42,
                command=lambda n=node: self._show_node(n)
            )
            btn.pack(fill="x", pady=1, padx=2)

    def _filter_nodes(self):
        q = self._node_search_var.get().lower().strip()
        filtered = [n for n in self._nodes
                    if q in n.get("id", "").lower() or q in n.get("name", "").lower()]
        self._render_node_list(filtered)

    def _show_node(self, node: dict):
        try:
            import yaml
            text = yaml.dump(node, allow_unicode=True, default_flow_style=False, sort_keys=False)
        except Exception:
            text = json.dumps(node, ensure_ascii=False, indent=2)

        node_id = node.get("id", "?")
        name = node.get("name", "")
        self._node_title.configure(text=f"{node_id}  {name}")
        self._node_file_label.configure(text=node.get("_file", ""))
        self._node_detail_box.configure(state="normal")
        self._node_detail_box.delete("1.0", "end")
        self._node_detail_box.insert("end", text)
        self._node_detail_box.configure(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 5：部署到 StudyAthena
    # ─────────────────────────────────────────────────────────────────────────

    def _build_deploy_tab(self, parent):
        # 顶部说明
        info = ctk.CTkFrame(parent, fg_color=("#e8f4ff", "#0f2a40"), corner_radius=8)
        info.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            info,
            text=(
                "🌐  studyathena.com/paths  →  AI Education OS · AI工程师完全手册\n"
                "生成完一章 → 点「部署」→ 30秒内上线。支持单章部署和全量部署。"
            ),
            font=("", 12), justify="left", anchor="w",
            text_color=("#1a5fa8", "#88ccff"),
        ).pack(padx=12, pady=8, anchor="w")

        # 左侧控制面板
        pane = ctk.CTkFrame(parent)
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        left = ctk.CTkFrame(pane, width=300)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="🚀 部署控制", font=("", 14, "bold")).pack(pady=(12, 6))

        # 单章部署
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(left, text="单章部署", font=("", 12, "bold")).pack(anchor="w", padx=12)

        ch_row = ctk.CTkFrame(left, fg_color="transparent")
        ch_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(ch_row, text="章节号 (1-41):", width=100, anchor="w").pack(side="left")
        self._deploy_ch_var = ctk.StringVar(value="1")
        ctk.CTkEntry(ch_row, textvariable=self._deploy_ch_var, width=60).pack(side="left")

        self._deploy_only_convert_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            left, text="仅转换 JSON（不 SSH 部署）",
            variable=self._deploy_only_convert_var
        ).pack(anchor="w", padx=12, pady=2)

        ctk.CTkButton(
            left, text="▶  部署单章", fg_color=COLORS["blue"],
            command=self._on_deploy_single
        ).pack(fill="x", padx=8, pady=4)

        # 全量部署
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(left, text="全量部署", font=("", 12, "bold")).pack(anchor="w", padx=12)
        ctk.CTkLabel(
            left, text="将所有已生成章节一次性部署",
            font=("", 10), text_color=COLORS["muted"]
        ).pack(anchor="w", padx=12)

        ctk.CTkButton(
            left, text="🌐  部署全部章节", fg_color=COLORS["green"],
            command=self._on_deploy_all
        ).pack(fill="x", padx=8, pady=4)

        ctk.CTkButton(
            left, text="📋  仅转换全部（不部署）", fg_color="transparent",
            border_width=1, command=self._on_convert_all
        ).pack(fill="x", padx=8, pady=2)

        # 章节状态摘要
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(
            left, text="🔄  刷新部署状态", fg_color="transparent",
            border_width=1, command=self._refresh_deploy_status
        ).pack(fill="x", padx=8, pady=2)

        self._deploy_summary_label = ctk.CTkLabel(
            left, text="", font=("", 11), justify="left",
            anchor="w", wraplength=260
        )
        self._deploy_summary_label.pack(padx=12, pady=4, anchor="w")

        # 右侧日志
        right = ctk.CTkFrame(pane)
        right.pack(side="left", fill="both", expand=True)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="📋 部署日志", font=("", 13, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🗑 清空", width=70, height=24,
                      fg_color="transparent", border_width=1,
                      command=self._clear_deploy_log).pack(side="right")

        self._deploy_log_box = ctk.CTkTextbox(right, font=("Consolas", 11))
        self._deploy_log_box.pack(fill="both", expand=True, pady=(4, 0))

        self._refresh_deploy_status()

    def _deploy_log(self, msg: str):
        self._deploy_log_box.configure(state="normal")
        self._deploy_log_box.insert("end", msg + "\n")
        self._deploy_log_box.see("end")
        self._deploy_log_box.configure(state="disabled")

    def _clear_deploy_log(self):
        self._deploy_log_box.configure(state="normal")
        self._deploy_log_box.delete("1.0", "end")
        self._deploy_log_box.configure(state="disabled")

    def _refresh_deploy_status(self):
        from deployer import CHAPTERS_DIR, LESSONS_DIR, CHAPTER_NUM_TO_NODE, CHAPTER_SLUGS
        generated = sum(
            1 for nid, ch in CHAPTER_NUM_TO_NODE.items()
            if (CHAPTERS_DIR / f"ch{int(ch):02d}_{nid}.md").exists()
        )
        deployed = sum(
            1 for nid in CHAPTER_NUM_TO_NODE
            if (LESSONS_DIR / f"{CHAPTER_SLUGS.get(nid, 'x')}.json").exists()
        )
        self._deploy_summary_label.configure(
            text=f"已生成: {generated} / 41 章\n已部署: {deployed} / 41 章"
        )

    def _on_deploy_single(self):
        try:
            ch_num = int(self._deploy_ch_var.get().strip())
        except ValueError:
            self._deploy_log("❌ 请输入有效章节号（1-41）")
            return
        do_deploy = not self._deploy_only_convert_var.get()
        self._deploy_log(f"\n{'='*50}\n▶ 部署第{ch_num}章  deploy={do_deploy}\n{'='*50}")
        self._status_bar.configure(text=f"部署第{ch_num}章...")

        def _run():
            from deployer import deploy_chapter, CHAPTER_NUM_TO_NODE
            node_id = CHAPTER_NUM_TO_NODE.get(ch_num)
            if not node_id:
                self.after(0, self._deploy_log, f"❌ 无效章节号: {ch_num}")
                return
            ok = deploy_chapter(node_id, ch_num, do_deploy=do_deploy,
                                log_fn=lambda m: self.after(0, self._deploy_log, m))
            self.after(0, self._deploy_log,
                       f"\n{'='*50}\n{'✅ 部署完成' if ok else '❌ 部署失败'}\n{'='*50}")
            self.after(0, self._status_bar.configure,
                       {"text": "部署完成 ✅" if ok else "部署失败 ❌"})
            self.after(0, self._refresh_deploy_status)

        threading.Thread(target=_run, daemon=True).start()

    def _on_deploy_all(self):
        self._deploy_log(f"\n{'='*50}\n🌐 全量部署所有已生成章节...\n{'='*50}")
        self._status_bar.configure(text="全量部署中...")

        def _run():
            from deployer import deploy_all
            ok, fail = deploy_all(do_deploy=True,
                                  log_fn=lambda m: self.after(0, self._deploy_log, m))
            self.after(0, self._deploy_log,
                       f"\n{'='*50}\n✅ 完成: {ok}章成功, {fail}章失败\n{'='*50}")
            self.after(0, self._status_bar.configure,
                       {"text": f"全量部署完成 ✅ {ok}章"})
            self.after(0, self._refresh_deploy_status)

        threading.Thread(target=_run, daemon=True).start()

    def _on_convert_all(self):
        self._deploy_log(f"\n{'='*50}\n📋 转换全部章节（不部署）...\n{'='*50}")

        def _run():
            from deployer import deploy_all
            ok, fail = deploy_all(do_deploy=False,
                                  log_fn=lambda m: self.after(0, self._deploy_log, m))
            self.after(0, self._deploy_log,
                       f"\n{'='*50}\n✅ 转换完成: {ok}章成功, {fail}章跳过\n{'='*50}")
            self.after(0, self._refresh_deploy_status)

        threading.Thread(target=_run, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # 公共
    # ─────────────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status_bar.configure(text=msg)


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
