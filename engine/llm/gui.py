"""
AI Native System — GUI 控制台
==============================
依赖: pip install customtkinter
启动: python gui.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT      = Path(__file__).resolve().parent
BOOKS_DIR = ROOT / "books"
OUT_DIR   = ROOT / "output"
MAIN_PY   = ROOT / "main.py"
PYTHON    = sys.executable

# 系统内账号文件（独立，不依赖外部）
_ACCOUNTS_FILE  = ROOT / "accounts.json"
# 登录助手脚本（系统内置，取代外部 chatgpt_agent/agent.py）
_LOGIN_HELPER   = ROOT / "engine" / "login_helper.py"
# 账号 session 存储目录
ACCOUNT_DIR = ROOT / "accounts"

sys.path.insert(0, str(ROOT))

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "green":  "#2ecc71",
    "red":    "#e74c3c",
    "yellow": "#f39c12",
    "muted":  "#7f8c8d",
    "blue":   "#3498db",
}

TOOLTIPS = {
    "provider": "LLM 提供商\n• deepseek — DeepSeek 网页（免费）\n• chatgpt  — ChatGPT 网页（免费）\n• both     — 两个窗口交替运行",
    "account":  "账号编号（1/2/3…）\n对应「账号管理」Tab 里的账号顺序\n如果你在浏览器里同时开了多个账号，\n填对应的序号以避免冲突",
    "from":     "从第 N 章开始跑（默认=0）\n用于续跑：已完成章节自动跳过\n也可以填章节号强制从该章重新开始",
    "chapter":  "只处理某一章（填章节编号）\n留空 = 处理全部章节\n配合 Stage 可以精确重跑某一步",
    "stage":    "只处理某章的某个 Stage（1~6）\n留空 = 运行该章全部 Stage\n必须同时填写「单章」才生效",
    "then_build": "生成完成后自动把 .md 转成前端 JSON\n并执行 git push，让网站立即更新",
}


# ─────────────────────────────────────────────────────────────────────────────
# 账号数据（系统内 accounts.json，独立存储）
# ─────────────────────────────────────────────────────────────────────────────

def _load_store() -> dict:
    if _ACCOUNTS_FILE.exists():
        try:
            return json.loads(_ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"accounts": []}


def _save_store(store: dict) -> None:
    _ACCOUNTS_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def acc_add(store: dict, name: str) -> dict:
    acc_id = f"acc_{uuid.uuid4().hex[:8]}"
    # storage_dir 放在系统内 accounts/ 子目录
    storage_dir = ACCOUNT_DIR / acc_id
    acc = {
        "id":          acc_id,
        "name":        name,
        "storage_dir": str(storage_dir),
        "logged_in":   False,
        "created_at":  datetime.now().isoformat(),
        "msgs_limit":  50,
    }
    store["accounts"].append(acc)
    _save_store(store)
    return acc


def acc_remove(store: dict, acc_id: str) -> None:
    store["accounts"] = [a for a in store["accounts"] if a["id"] != acc_id]
    _save_store(store)


def acc_rename(store: dict, acc_id: str, new_name: str) -> None:
    for a in store["accounts"]:
        if a["id"] == acc_id:
            a["name"] = new_name
            break
    _save_store(store)


def acc_is_logged_in(acc: dict, provider: str = "chatgpt") -> bool:
    if provider == "deepseek":
        p = Path(acc["storage_dir"] + "_deepseek") / "storage_state.json"
    else:
        p = Path(acc["storage_dir"]) / "storage_state.json"
    return p.exists()


def acc_display_names(store: dict) -> list[str]:
    """返回「序号: 名称」列表，用于下拉框"""
    accs = store.get("accounts", [])
    result = []
    for i, a in enumerate(accs, 1):
        cg = "✓" if acc_is_logged_in(a, "chatgpt")  else "·"
        ds = "✓" if acc_is_logged_in(a, "deepseek") else "·"
        result.append(f"{i}: {a['name']}  [C:{cg} D:{ds}]")
    if len(accs) > 1:
        result.append("auto: 轮换全部")
    return result or ["(无账号)"]


# ─────────────────────────────────────────────────────────────────────────────
# 书籍工具
# ─────────────────────────────────────────────────────────────────────────────

def list_books() -> list[tuple[str, str]]:
    result = []
    for d in sorted(BOOKS_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "config.json").exists():
            try:
                cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
                title = cfg.get("book_title", d.name)
            except Exception:
                title = d.name
            result.append((d.name, title))
    return result


def load_config(book_id: str) -> dict:
    return json.loads((BOOKS_DIR / book_id / "config.json").read_text(encoding="utf-8"))


def book_progress_summary(book_id: str) -> str:
    lines = []
    try:
        cfg = load_config(book_id)
        title       = cfg.get("book_title", book_id)
        chapters    = cfg.get("chapters", {})
        stages      = cfg.get("stages", [])
        bcfg        = cfg.get("build", {})
        mode        = bcfg.get("mode", "")
        src_dir_rel = bcfg.get("source_dir", "")
        out_json    = bcfg.get("out_json", "")

        lines.append(f"📚 {title}")
        lines.append(f"   ID: {book_id}  |  {len(chapters)}章 × {len(stages)}个Stage")
        lines.append(f"   模式: {mode or '未设置'}  |  Provider: {bcfg.get('provider','—')}")
        lines.append(f"   源目录: {src_dir_rel or '—'}")
        lines.append(f"   输出JSON: {out_json or '—'}")
        lines.append("")

        MARKER = "## 📖 本章名词解释（新人必读）"
        # 找 git 根（StudyAthena/），source_dir 相对于此
        _p = ROOT
        for _ in range(6):
            if (_p / ".git").exists():
                break
            _p = _p.parent
        project_root = _p

        lines.append("─" * 48)
        lines.append(f"{'章':>3}  {'标题':<28}  {'Stage':>6}  {'注释'}")
        lines.append("─" * 48)

        for n in sorted(int(k) for k in chapters.keys()):
            spec     = chapters[str(n)]
            ch_title = spec.get("title", "")[:26]

            out_book    = OUT_DIR / book_id
            done_stages = 0
            if out_book.exists():
                done_stages = sum(
                    1 for s in stages
                    if (out_book / f"ch{n:02d}_s{s['id']}.md").exists()
                )
            stage_str = f"{done_stages}/{len(stages)}" if stages else "—"

            glossary_done = "—"
            if src_dir_rel and mode == "claude_single":
                f = project_root / src_dir_rel / f"ch{n:02d}.md"
                if f.exists():
                    glossary_done = "✅" if MARKER in f.read_text(encoding="utf-8", errors="replace") else "待"
            elif src_dir_rel and mode == "sections":
                for s in (5, 3, 2):
                    f = project_root / src_dir_rel / f"ch{n:02d}_s{s}.md"
                    if f.exists():
                        glossary_done = "✅" if MARKER in f.read_text(encoding="utf-8", errors="replace") else "待"
                        break

            lines.append(f"  {n:>2}  {ch_title:<28}  {stage_str:>6}  {glossary_done}")

        if stages:
            lines.append("")
            lines.append("Stage 说明:")
            for s in stages:
                lines.append(f"  S{s['id']} {s['name']:<12}  provider={s.get('provider','—')}")

    except Exception as e:
        lines.append(f"读取进度失败: {e}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip 浮窗
# ─────────────────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text: str):
        self._widget  = widget
        self._text    = text
        self._tip     = None
        self._after   = None
        widget.bind("<Enter>", self._schedule_show)
        widget.bind("<Leave>", self._schedule_hide)

    def _schedule_show(self, _=None):
        if self._after:
            self._widget.after_cancel(self._after)
            self._after = None
        self._after = self._widget.after(400, self._show)

    def _show(self):
        self._after = None
        if self._tip:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() + 4
        y = self._widget.winfo_rooty()
        self._tip = tw = ctk.CTkToplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        ctk.CTkLabel(tw, text=self._text, justify="left",
                     font=("", 11), fg_color=("#f0f0f0","#2a2a2a"),
                     corner_radius=6, padx=10, pady=8).pack()
        # 鼠标移到 tooltip 自身上也能保持显示
        tw.bind("<Enter>", lambda _: self._cancel_hide())
        tw.bind("<Leave>", self._schedule_hide)
        # 最长 4 秒自动关闭
        self._widget.after(4000, self._hide)

    def _cancel_hide(self):
        if self._after:
            self._widget.after_cancel(self._after)
            self._after = None

    def _schedule_hide(self, _=None):
        if self._after:
            self._widget.after_cancel(self._after)
        self._after = self._widget.after(200, self._hide)

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
        self.title("AI Native System — 书籍生产控制台")
        self.geometry("1240x780")
        self.minsize(1000, 620)

        self._proc: subprocess.Popen | None = None
        self._log_queue: Queue = Queue()
        self._book_map: dict[str, str] = {}
        self._store: dict = _load_store()

        self._build_ui()
        self._refresh_books()
        self._refresh_account_dropdown()
        self._poll_log()

    # ── UI 骨架：Tab 切换 ──────────────────────────────────────────────────────

    def _build_ui(self):
        # 顶级 TabView
        self._tabview = ctk.CTkTabview(self, anchor="nw")
        self._tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self._tabview.add("📚 书籍生产")
        self._tabview.add("👥 账号管理")

        self._build_main_tab(self._tabview.tab("📚 书籍生产"))
        self._build_accounts_tab(self._tabview.tab("👥 账号管理"))

        # 底部状态栏（Tab 外）
        self._status_label = ctk.CTkLabel(
            self, text="就绪 | 鼠标悬停 ❓ 查看参数说明 | 账号管理在「👥 账号管理」Tab",
            anchor="w", fg_color=("#ddd","#333"), corner_radius=4
        )
        self._status_label.pack(fill="x", padx=8, pady=(0, 6))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1：书籍生产
    # ─────────────────────────────────────────────────────────────────────────

    def _build_main_tab(self, parent):
        # 左侧面板（可滚动，防止按钮被窗口高度截断）
        left_outer = ctk.CTkFrame(parent, width=320)
        left_outer.pack(side="left", fill="y", padx=(0, 6), pady=0)
        left_outer.pack_propagate(False)
        left = ctk.CTkScrollableFrame(left_outer, width=300, fg_color="transparent")
        left.pack(fill="both", expand=True)

        # 书籍列表
        ctk.CTkLabel(left, text="📚 书籍列表", font=("", 14, "bold")).pack(pady=(10, 2))
        ctk.CTkLabel(left, text="点击书名选择", font=("", 10), text_color="gray").pack()
        self._book_list = ctk.CTkScrollableFrame(left, height=120)
        self._book_list.pack(fill="x", padx=8, pady=(4, 0))

        # 分隔
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(left, text="▶ 运行参数", font=("", 13, "bold")).pack(pady=(0, 4))

        def lrow(label, widget_fn, tip_key=None):
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            lbl = ctk.CTkLabel(row, text=label, width=72, anchor="w", font=("", 12))
            lbl.pack(side="left")
            w = widget_fn(row)
            w.pack(side="left", expand=True, fill="x")
            if tip_key and tip_key in TOOLTIPS:
                Tooltip(lbl, TOOLTIPS[tip_key])
                Tooltip(w,   TOOLTIPS[tip_key])
            return w

        # provider
        self._provider_var = ctk.StringVar(value="deepseek")
        lrow("Provider ❓", lambda p: ctk.CTkOptionMenu(
            p, variable=self._provider_var,
            values=["deepseek", "chatgpt", "both"]), "provider")

        # account 下拉（联动账号管理）
        row_acc = ctk.CTkFrame(left, fg_color="transparent")
        row_acc.pack(fill="x", padx=8, pady=2)
        lbl_acc = ctk.CTkLabel(row_acc, text="账号 ❓", width=72, anchor="w", font=("", 12))
        lbl_acc.pack(side="left")
        Tooltip(lbl_acc, TOOLTIPS["account"])
        self._account_display_var = ctk.StringVar(value="1")
        self._account_menu = ctk.CTkOptionMenu(
            row_acc, variable=self._account_display_var,
            values=["(无账号)"], command=self._on_account_select)
        self._account_menu.pack(side="left", expand=True, fill="x")
        Tooltip(self._account_menu, TOOLTIPS["account"])
        self._account_num = "1"   # 实际传给 CLI 的数字或 auto

        # from chapter
        self._from_var = ctk.StringVar(value="0")
        lrow("从第N章 ❓", lambda p: ctk.CTkEntry(p, textvariable=self._from_var, width=50), "from")

        # chapter
        self._chapter_var = ctk.StringVar(value="")
        lrow("单章 ❓", lambda p: ctk.CTkEntry(
            p, textvariable=self._chapter_var, placeholder_text="空=全部", width=60), "chapter")

        # stage
        self._stage_var = ctk.StringVar(value="")
        lrow("Stage ❓", lambda p: ctk.CTkEntry(
            p, textvariable=self._stage_var, placeholder_text="空=全部", width=60), "stage")

        # then-build
        row6 = ctk.CTkFrame(left, fg_color="transparent")
        row6.pack(fill="x", padx=8, pady=(6, 0))
        self._then_build_var = ctk.BooleanVar(value=False)
        cb = ctk.CTkCheckBox(row6, text="完成后自动 Build JSON ❓",
                             variable=self._then_build_var)
        cb.pack(side="left")
        Tooltip(cb, TOOLTIPS["then_build"])

        # 命令预览
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(left, text="将执行的命令：", font=("", 10), text_color="gray").pack(anchor="w", padx=8)
        self._cmd_preview = ctk.CTkLabel(
            left, text="—", font=("Consolas", 10), anchor="w",
            wraplength=260, text_color=("#0070c0","#88ccff"))
        self._cmd_preview.pack(fill="x", padx=8, pady=(0, 4))

        for var in (self._provider_var, self._from_var,
                    self._chapter_var, self._stage_var, self._then_build_var):
            var.trace_add("write", lambda *_: self._update_cmd_preview())

        # 按钮区
        ctk.CTkFrame(left, height=1, fg_color="gray").pack(fill="x", padx=8, pady=(4, 6))

        def btn(text, color, cmd, tip=None):
            b = ctk.CTkButton(left, text=text, fg_color=color, command=cmd)
            b.pack(fill="x", pady=2, padx=6)
            if tip:
                Tooltip(b, tip)
            return b

        self._run_btn = btn("▶  开始运行（run）", "#1c7c3a", self._on_run,
                            tip="用浏览器 LLM 生成章节内容\n根据上方参数决定范围")
        btn("⏹  停止", "#8b1c1c", self._on_stop,
            tip="强制终止当前运行的进程")
        btn("🔨  重建前端 JSON（build）", "#5a3a8a", self._on_build,
            tip="把 progress/ 的 .md 转为前端 JSON\n不需要 LLM，自动 git push")
        btn("🌐  重建全部书 JSON", "#3a5a8a", self._on_build_all,
            tip="对所有书执行 build，一次更新全部前端 JSON")
        btn("📖  添加注释（glossary）", "#6a4a1a", self._on_glossary,
            tip="为每章末尾添加「新人必读」注释\n已注释章节自动跳过，支持断点续跑")
        btn("📊  刷新进度", "transparent", self._refresh_status)
        btn("🔄  刷新书列表", "transparent", self._refresh_books)

        # 右侧面板
        right = ctk.CTkFrame(parent)
        right.pack(side="left", fill="both", expand=True, pady=0)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="📊 进度 / 章节列表", font=("", 13, "bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="Stage列：output/下已完成数  注释列：glossary状态",
                     font=("", 10), text_color="gray").pack(side="left", padx=8)

        self._status_box = ctk.CTkTextbox(right, height=300, font=("Consolas", 11))
        self._status_box.pack(fill="x", pady=(2, 6))

        hdr2 = ctk.CTkFrame(right, fg_color="transparent")
        hdr2.pack(fill="x")
        ctk.CTkLabel(hdr2, text="📋 运行日志", font=("", 13, "bold")).pack(side="left")
        ctk.CTkButton(hdr2, text="🗑 清空", width=70, height=24,
                      fg_color="transparent", border_width=1,
                      command=self._clear_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(right, font=("Consolas", 11))
        self._log_box.pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2：账号管理
    # ─────────────────────────────────────────────────────────────────────────

    def _build_accounts_tab(self, parent):
        # 顶部工具栏
        toolbar = ctk.CTkFrame(parent, height=50)
        toolbar.pack(fill="x", pady=(0, 6))
        toolbar.pack_propagate(False)

        ctk.CTkLabel(toolbar, text="👥 账号管理",
                     font=("", 15, "bold")).pack(side="left", padx=16, pady=10)

        ctk.CTkButton(toolbar, text="+ 添加新账号", width=140,
                      fg_color=COLORS["green"], hover_color="#27ae60",
                      command=self._acc_add).pack(side="right", padx=12, pady=8)

        ctk.CTkButton(toolbar, text="🔄 刷新列表", width=100,
                      fg_color="transparent", border_width=1,
                      command=self._acc_refresh).pack(side="right", padx=4, pady=8)

        # 说明
        ctk.CTkLabel(
            parent,
            text=(
                "点击「🔑 登录」会打开浏览器，手动完成登录后状态自动保存，下次直接使用无需重登。\n"
                "C = ChatGPT  D = DeepSeek    ✓ = 已登录   · = 未登录\n"
                "主界面账号下拉框会自动读取这里的列表（格式：序号: 名称 [C:✓ D:·]）"
            ),
            wraplength=860, text_color=COLORS["muted"], font=("", 12), justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # 账号滚动列表
        self._acc_list_frame = ctk.CTkScrollableFrame(parent)
        self._acc_list_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # 日志（账号操作输出）
        ctk.CTkLabel(parent, text="📋 账号操作日志", font=("", 12, "bold")).pack(anchor="w", padx=8)
        self._acc_log_box = ctk.CTkTextbox(parent, height=120, font=("Consolas", 11))
        self._acc_log_box.pack(fill="x", padx=8, pady=(2, 6))

        self._acc_refresh()

    def _acc_log(self, msg: str):
        self._acc_log_box.configure(state="normal")
        self._acc_log_box.insert("end", msg + "\n")
        self._acc_log_box.see("end")
        self._acc_log_box.configure(state="disabled")

    def _acc_refresh(self):
        self._store = _load_store()
        for w in self._acc_list_frame.winfo_children():
            w.destroy()

        accounts = self._store.get("accounts", [])
        if not accounts:
            ctk.CTkLabel(self._acc_list_frame,
                         text="还没有账号，点击「+ 添加新账号」创建第一个。",
                         text_color=COLORS["muted"]).pack(pady=40)
            self._refresh_account_dropdown()
            return

        for i, acc in enumerate(accounts, 1):
            self._build_acc_card(acc, idx=i)

        self._refresh_account_dropdown()

    def _build_acc_card(self, acc: dict, idx: int):
        card = ctk.CTkFrame(self._acc_list_frame, corner_radius=8)
        card.pack(fill="x", padx=4, pady=5)

        cg_ok = acc_is_logged_in(acc, "chatgpt")
        ds_ok = acc_is_logged_in(acc, "deepseek")

        # 行1：编号 / 名称 / 登录状态 / 消息上限
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(row1, text=f"#{idx}", width=28,
                     font=("", 12), text_color=COLORS["muted"]).pack(side="left")
        ctk.CTkLabel(row1, text=acc["name"],
                     font=("", 14, "bold"), width=150, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(row1, text=f"ID: {acc['id']}",
                     text_color=COLORS["muted"], font=("Consolas", 10),
                     width=130, anchor="w").pack(side="left", padx=4)

        # ChatGPT 状态
        cg_color = COLORS["green"] if cg_ok else COLORS["muted"]
        ctk.CTkLabel(row1, text=f"C:{'✓' if cg_ok else '·'}",
                     text_color=cg_color, font=("", 13, "bold"), width=30).pack(side="left", padx=2)
        # DeepSeek 状态
        ds_color = COLORS["green"] if ds_ok else COLORS["muted"]
        ctk.CTkLabel(row1, text=f"D:{'✓' if ds_ok else '·'}",
                     text_color=ds_color, font=("", 13, "bold"), width=30).pack(side="left", padx=2)

        # 消息上限
        ctk.CTkLabel(row1, text="消息上限：",
                     text_color=COLORS["muted"], font=("", 11)).pack(side="right", padx=(0, 2))
        ml_entry = ctk.CTkEntry(row1, width=58, placeholder_text="0=不限")
        ml_entry.insert(0, str(acc.get("msgs_limit", 0) or 0))
        ml_entry.pack(side="right", padx=(0, 4))

        def _save_ml(_event=None, _a=acc, _e=ml_entry):
            try:
                limit = int(_e.get().strip() or 0)
            except ValueError:
                limit = 0
            for a in self._store.get("accounts", []):
                if a["id"] == _a["id"]:
                    a["msgs_limit"] = limit
                    break
            _save_store(self._store)

        ml_entry.bind("<FocusOut>", _save_ml)
        ml_entry.bind("<Return>",   _save_ml)

        # 行2：存储路径 + 操作按钮
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(row2, text=acc["storage_dir"],
                     text_color=COLORS["muted"], font=("Consolas", 9),
                     anchor="w").pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(row2, text="🔑 ChatGPT", width=100,
                      command=lambda a=acc: self._acc_login_chatgpt(a)
                      ).pack(side="right", padx=3)
        ctk.CTkButton(row2, text="🔑 DeepSeek", width=100,
                      fg_color="#1a5fa8", hover_color="#144d8a",
                      command=lambda a=acc: self._acc_login_deepseek(a)
                      ).pack(side="right", padx=3)
        ctk.CTkButton(row2, text="✏️ 改名", width=72,
                      fg_color="transparent", border_width=1,
                      command=lambda a=acc: self._acc_rename(a)
                      ).pack(side="right", padx=3)
        ctk.CTkButton(row2, text="🗑️ 删除", width=72,
                      fg_color=COLORS["red"], hover_color="#c0392b",
                      command=lambda a=acc: self._acc_delete(a)
                      ).pack(side="right", padx=3)

    # ── 账号操作 ──────────────────────────────────────────────────────────────

    def _acc_add(self):
        d = ctk.CTkInputDialog(text="输入新账号名称（如「账号5」）：", title="添加账号")
        name = d.get_input()
        if not name or not name.strip():
            return
        acc = acc_add(self._store, name.strip())
        self._acc_log(f"✅ 已添加账号「{acc['name']}」({acc['id']})\n   存储: {acc['storage_dir']}")
        self._acc_refresh()

    def _acc_rename(self, acc: dict):
        d = ctk.CTkInputDialog(text=f"为「{acc['name']}」输入新名称：", title="重命名账号")
        new_name = d.get_input()
        if not new_name or not new_name.strip():
            return
        acc_rename(self._store, acc["id"], new_name.strip())
        self._acc_log(f"✏️ 已重命名为「{new_name.strip()}」")
        self._acc_refresh()

    def _acc_delete(self, acc: dict):
        d = ctk.CTkInputDialog(
            text=f'确认删除「{acc["name"]}」？\n输入"确认"后删除：', title="删除账号")
        ans = d.get_input()
        if ans and ans.strip() == "确认":
            acc_remove(self._store, acc["id"])
            self._acc_log(f"🗑️ 已删除账号「{acc['name']}」")
            self._acc_refresh()

    def _acc_login_chatgpt(self, acc: dict):
        if not _LOGIN_HELPER.exists():
            self._acc_log(f"❌ 找不到 {_LOGIN_HELPER}")
            return
        storage_dir = Path(acc["storage_dir"])
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._acc_log(f"🔑 打开浏览器登录「{acc['name']}」（ChatGPT）...\n   登录完成后程序自动保存并关闭浏览器")
        cmd = [PYTHON, str(_LOGIN_HELPER), "chatgpt",
               "--storage-dir", str(storage_dir)]

        def _run():
            try:
                r = subprocess.run(cmd, cwd=str(_LOGIN_HELPER.parent),
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                if r.returncode == 0:
                    self._acc_log(f"✅ 「{acc['name']}」ChatGPT 登录成功，状态已保存")
                else:
                    self._acc_log(f"❌ 登录失败（返回码 {r.returncode}）\n{r.stderr[:400]}")
            except Exception as e:
                self._acc_log(f"❌ 启动失败：{e}")
            self.after(200, self._acc_refresh)

        threading.Thread(target=_run, daemon=True).start()

    def _acc_login_deepseek(self, acc: dict):
        storage_dir = Path(acc["storage_dir"])
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._acc_log(f"🔑 打开浏览器登录「{acc['name']}」（DeepSeek）...\n   请在弹出的浏览器里完成 Google 授权")

        cmd = [PYTHON, str(_LOGIN_HELPER), "deepseek",
               "--storage-dir", str(storage_dir)]

        def _run():
            try:
                r = subprocess.run(cmd, cwd=str(_LOGIN_HELPER.parent),
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=600)
                if r.returncode == 0:
                    self._acc_log(f"✅ 「{acc['name']}」DeepSeek 登录成功")
                else:
                    self._acc_log(f"❌ DeepSeek 登录失败\n{(r.stdout + r.stderr)[:400]}")
            except subprocess.TimeoutExpired:
                self._acc_log("❌ 登录超时（10分钟）")
            except Exception as e:
                self._acc_log(f"❌ 启动失败：{e}")
            self.after(200, self._acc_refresh)

        threading.Thread(target=_run, daemon=True).start()

    # ── 账号下拉刷新 ──────────────────────────────────────────────────────────

    def _refresh_account_dropdown(self):
        self._store = _load_store()
        names = acc_display_names(self._store)
        self._account_menu.configure(values=names)
        # 如果当前值不在列表里，重置到第一个
        cur = self._account_display_var.get()
        if cur not in names:
            self._account_display_var.set(names[0])
            self._account_num = "1"
        self._update_cmd_preview()

    def _on_account_select(self, value: str):
        # 解析「序号: 名称 [...」→ 取序号
        if value.startswith("auto"):
            self._account_num = "auto"
        else:
            try:
                self._account_num = value.split(":")[0].strip()
            except Exception:
                self._account_num = "1"
        self._update_cmd_preview()

    # ── 书列表 ────────────────────────────────────────────────────────────────

    def _refresh_books(self):
        for w in self._book_list.winfo_children():
            w.destroy()
        self._book_btns: dict[str, ctk.CTkButton] = {}
        self._selected_book: str | None = None
        self._book_map.clear()

        books = list_books()
        for book_id, title in books:
            self._book_map[book_id] = title
            display = f"{title}\n  [{book_id}]"
            btn = ctk.CTkButton(
                self._book_list, text=display, anchor="w",
                font=("", 12), height=44,
                fg_color="transparent", hover_color=("#3a6ea0","#1a4a7a"),
                command=lambda x=book_id: self._select_book(x)
            )
            btn.pack(fill="x", pady=1)
            self._book_btns[book_id] = btn

        if books:
            self._select_book(books[0][0])

    def _select_book(self, book_id: str):
        self._selected_book = book_id
        for b, btn in self._book_btns.items():
            btn.configure(fg_color=("#1f6aa5","#1f4f82") if b == book_id else "transparent")
        self._refresh_status()
        self._update_cmd_preview()

    # ── 命令预览 ──────────────────────────────────────────────────────────────

    def _update_cmd_preview(self, *_):
        if not getattr(self, "_selected_book", None):
            return
        book = self._selected_book
        acc  = getattr(self, "_account_num", "1")
        parts = ["python main.py run", book,
                 f"--provider {self._provider_var.get()}",
                 f"--account {acc}",
                 f"--from {self._from_var.get() or '0'}"]
        ch = self._chapter_var.get().strip()
        st = self._stage_var.get().strip()
        if ch:
            parts.append(f"--chapter {ch}")
        if st and ch:
            parts.append(f"--stage {st}")
        if self._then_build_var.get():
            parts.append("--then-build")
        self._cmd_preview.configure(text=" ".join(parts))

    # ── 进度刷新 ──────────────────────────────────────────────────────────────

    def _refresh_status(self):
        self._status_box.configure(state="normal")
        self._status_box.delete("1.0", "end")
        if not self._selected_book:
            self._status_box.insert("end", "请先在左侧选择一本书")
        else:
            self._status_box.insert("end", book_progress_summary(self._selected_book))
        self._status_box.configure(state="disabled")

    # ── 运行命令 ──────────────────────────────────────────────────────────────

    def _on_run(self):
        if not self._selected_book:
            self._log("❌ 请先选择一本书"); return
        if self._proc and self._proc.poll() is None:
            self._log("⚠️ 已有任务在运行，请先点「停止」"); return

        acc = getattr(self, "_account_num", "1")
        cmd = [PYTHON, str(MAIN_PY), "run", self._selected_book,
               "--provider", self._provider_var.get(),
               "--account",  acc,
               "--from",     self._from_var.get() or "0"]
        ch = self._chapter_var.get().strip()
        st = self._stage_var.get().strip()
        if ch:
            cmd += ["--chapter", ch]
        if st and ch:
            cmd += ["--stage", st]
        if self._then_build_var.get():
            cmd += ["--then-build"]

        self._log(f"\n{'='*60}\n▶ {' '.join(cmd[2:])}\n{'='*60}")
        self._status_label.configure(text=f"运行中: {self._selected_book}")
        self._run_btn.configure(state="disabled")
        self._start_proc(cmd)

    def _on_stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log("\n⏹ 用户停止任务")
        self._status_label.configure(text="已停止")
        self._run_btn.configure(state="normal")

    def _on_build(self):
        if not self._selected_book:
            self._log("❌ 请先选择一本书"); return
        if self._proc and self._proc.poll() is None:
            self._log("⚠️ 已有任务在运行"); return
        cmd = [PYTHON, str(MAIN_PY), "build", self._selected_book]
        self._log(f"\n▶ build {self._selected_book}")
        self._status_label.configure(text=f"构建中: {self._selected_book}")
        self._start_proc(cmd)

    def _on_build_all(self):
        if self._proc and self._proc.poll() is None:
            self._log("⚠️ 已有任务在运行"); return
        cmd = [PYTHON, str(MAIN_PY), "build", "all"]
        self._log("\n▶ build all")
        self._status_label.configure(text="构建全部...")
        self._start_proc(cmd)

    def _on_glossary(self):
        if not self._selected_book:
            self._log("❌ 请先选择一本书"); return
        if self._proc and self._proc.poll() is None:
            self._log("⚠️ 已有任务在运行"); return
        acc = getattr(self, "_account_num", "1")
        cmd = [PYTHON, str(MAIN_PY), "glossary", self._selected_book,
               "--provider", self._provider_var.get(),
               "--account",  acc]
        self._log(f"\n▶ glossary {self._selected_book}  provider={self._provider_var.get()}  account={acc}")
        self._start_proc(cmd)

    def _start_proc(self, cmd: list):
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1, cwd=str(ROOT)
        )
        threading.Thread(target=self._read_proc, daemon=True).start()

    def _read_proc(self):
        for line in self._proc.stdout:
            self._log_queue.put(line.rstrip())
        self._proc.wait()
        self._log_queue.put(f"\n{'='*60}\n✅ 进程结束，返回码: {self._proc.returncode}")
        self._log_queue.put("__DONE__")

    # ── 日志 ──────────────────────────────────────────────────────────────────

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
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._run_btn.configure(state="normal")
                    self._status_label.configure(text="完成 ✅")
                    self._refresh_status()
                else:
                    self._log(msg)
        except Empty:
            pass
        self.after(200, self._poll_log)


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
