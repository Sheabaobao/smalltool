"""
待办清单 — 独立小窗口版（不用浏览器）。
支持：时钟、可选截止日、完成（从待办消失并记入历史）、功德簿弹窗查看已完成记录、底部小花飘落动画。
运行：python todo_gui.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import tkinter as tk

DATA_FILE = Path(__file__).resolve().parent / "todos.json"


def load_todos() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError):
        return []


def save_todos(todos: list[dict]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


def ddl_from_text(s: str) -> str | None:
    """截止日改为自由文本；空字符串视为未填写。"""
    t = (s or "").strip()
    return t if t else None


class TodoApp:
    def __init__(self) -> None:
        self.todos: list[dict] = load_todos()
        self._normalize_todos()
        self._flower_job: str | None = None
        self._merit_win: tk.Toplevel | None = None
        self._merit_popup_lb: tk.Listbox | None = None

        self.root = tk.Tk()
        self.root.title("待办小游戏")
        self.root.geometry("440x640")
        self.root.minsize(400, 520)
        self.root.configure(bg="#e8f4fc")

        main = tk.Frame(self.root, bg="#e8f4fc", padx=14, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 先固定底部动画条，再让上方 body 占满剩余空间（避免 pack 顺序导致布局错位）
        self.anim_holder = tk.Frame(main, bg="#cfe8f6", height=118)
        self.anim_holder.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        self.anim_holder.pack_propagate(False)
        self.flower_canvas = tk.Canvas(
            self.anim_holder,
            height=96,
            highlightthickness=0,
            bg="#cfe8f6",
            bd=0,
        )
        self.flower_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        body = tk.Frame(main, bg="#e8f4fc")
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # —— 时钟 ⏰ ——
        clock_row = tk.Frame(body, bg="#e8f4fc")
        clock_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            clock_row,
            text="⏰",
            font=("Segoe UI Emoji", 16),
            bg="#e8f4fc",
        ).pack(side=tk.LEFT)
        self.time_lbl = tk.Label(
            clock_row,
            text="",
            font=("Consolas", 11),
            bg="#e8f4fc",
            fg="#1a5f7a",
        )
        self.time_lbl.pack(side=tk.RIGHT)
        self._tick_clock()

        tk.Label(
            body,
            text="我的待办小屋",
            font=("Microsoft YaHei UI", 18, "bold"),
            bg="#e8f4fc",
            fg="#1a5f7a",
        ).pack(pady=(0, 8))

        row = tk.Frame(body, bg="#e8f4fc")
        row.pack(fill=tk.X, pady=(0, 4))
        self.entry = tk.Entry(row, font=("Microsoft YaHei UI", 11))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.add_task())
        tk.Button(
            row,
            text="添加",
            font=("Microsoft YaHei UI", 10),
            bg="#57c5b6",
            fg="white",
            activebackground="#4ab3a5",
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=self.add_task,
        ).pack(side=tk.RIGHT)

        ddl_row = tk.Frame(body, bg="#e8f4fc")
        ddl_row.pack(fill=tk.X, pady=(0, 8))
        self.ddl_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ddl_row,
            text="本任务写截止说明",
            variable=self.ddl_var,
            font=("Microsoft YaHei UI", 9),
            bg="#e8f4fc",
            activebackground="#e8f4fc",
            selectcolor="#e8f4fc",
        ).pack(side=tk.LEFT)
        self.ddl_entry = tk.Entry(ddl_row, font=("Microsoft YaHei UI", 10), width=22)
        self.ddl_entry.pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            body,
            text="待办",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#e8f4fc",
            fg="#333",
        ).pack(anchor=tk.W)

        # 按钮必须排在列表之前 pack，否则列表 expand 会把按钮挤出窗口底部看不见
        act_btns = tk.Frame(body, bg="#e8f4fc")
        act_btns.pack(fill=tk.X, pady=(2, 6))
        tk.Button(
            act_btns,
            text="完成",
            font=("Microsoft YaHei UI", 10),
            bg="#ffc93c",
            fg="#333",
            activebackground="#f0b830",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            command=self.mark_complete,
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            act_btns,
            text="功德簿",
            font=("Microsoft YaHei UI", 10),
            bg="#e6c9a8",
            fg="#4a3728",
            activebackground="#d4b896",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            command=self.open_merit_book,
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            act_btns,
            text="截止日",
            font=("Microsoft YaHei UI", 10),
            bg="#a8d8ea",
            fg="#333",
            activebackground="#95c9dc",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            command=self.edit_ddl_selected_active,
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            act_btns,
            text="删除",
            font=("Microsoft YaHei UI", 10),
            bg="#ff6b6b",
            fg="white",
            activebackground="#ee5a5a",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            command=self.delete_active,
        ).pack(side=tk.LEFT)

        self.active_lb, self.active_scroll = self._make_listbox(body, visible_lines=10)

        self.refresh_active_list()

    def _make_listbox(self, parent: tk.Widget, visible_lines: int = 10) -> tuple[tk.Listbox, ttk.Scrollbar]:
        wrap = tk.Frame(parent, bg="white", highlightbackground="#b8d4e8", highlightthickness=2)
        wrap.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        sb = ttk.Scrollbar(wrap)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(
            wrap,
            font=("Microsoft YaHei UI", 10),
            selectmode=tk.SINGLE,
            activestyle="none",
            yscrollcommand=sb.set,
            borderwidth=0,
            highlightthickness=0,
            height=visible_lines,
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)
        return lb, sb

    def _normalize_todos(self) -> None:
        for t in self.todos:
            if "id" not in t:
                t["id"] = str(uuid.uuid4())
            t.setdefault("text", "")
            t.setdefault("done", False)
            if "ddl" in t and t["ddl"] == "":
                t["ddl"] = None

    def _tick_clock(self) -> None:
        self.time_lbl.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _pairs_active(self) -> list[tuple[int, dict]]:
        return [(i, t) for i, t in enumerate(self.todos) if not t.get("done", False)]

    def _pairs_merit(self) -> list[tuple[int, dict]]:
        return [(i, t) for i, t in enumerate(self.todos) if t.get("done", False)]

    def _merit_sorted_pairs(self) -> list[tuple[int, dict]]:
        pairs = self._pairs_merit()

        def sort_key(p: tuple[int, dict]) -> str:
            return p[1].get("completed_at") or ""

        return sorted(pairs, key=sort_key, reverse=True)

    def refresh_active_list(self) -> None:
        self.active_lb.delete(0, tk.END)
        for _, t in self._pairs_active():
            line = f"○  {t.get('text', '')}"
            ddl = t.get("ddl")
            if ddl:
                line += f"  | 截止 {ddl}"
            self.active_lb.insert(tk.END, line)

    def _fill_merit_listbox(self, lb: tk.Listbox) -> None:
        lb.delete(0, tk.END)
        for _, t in self._merit_sorted_pairs():
            line = f"✓  {t.get('text', '')}"
            ddl = t.get("ddl")
            if ddl:
                line += f"  | 截止 {ddl}"
            at = t.get("completed_at")
            if at:
                line += f"  · 完成于 {at}"
            lb.insert(tk.END, line)

    def _refresh_merit_popup_if_open(self) -> None:
        if self._merit_popup_lb is None or self._merit_win is None:
            return
        try:
            if self._merit_win.winfo_exists():
                self._fill_merit_listbox(self._merit_popup_lb)
        except tk.TclError:
            self._merit_win = None
            self._merit_popup_lb = None

    def _index_active_real(self) -> int | None:
        sel = self.active_lb.curselection()
        if not sel:
            return None
        pairs = self._pairs_active()
        pos = int(sel[0])
        if pos >= len(pairs):
            return None
        return pairs[pos][0]

    def _index_merit_popup_real(self, lb: tk.Listbox) -> int | None:
        sel = lb.curselection()
        if not sel:
            return None
        sorted_pairs = self._merit_sorted_pairs()
        pos = int(sel[0])
        if not sorted_pairs:
            return None
        if pos >= len(sorted_pairs):
            return None
        return sorted_pairs[pos][0]

    def add_task(self) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        ddl_val: str | None = None
        if self.ddl_var.get():
            ddl_val = ddl_from_text(self.ddl_entry.get())
            if ddl_val is None:
                messagebox.showerror(
                    "提示",
                    "已勾选「本任务写截止说明」时，请在框里写几个字；\n"
                    "不想写说明就取消勾选。",
                )
                return
        self.todos.append(
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "done": False,
                "ddl": ddl_val,
            }
        )
        save_todos(self.todos)
        self.entry.delete(0, tk.END)
        self.ddl_entry.delete(0, tk.END)
        self.ddl_var.set(False)
        self.refresh_active_list()

    def edit_ddl_selected_active(self) -> None:
        ri = self._index_active_real()
        if ri is None:
            messagebox.showinfo("提示", "请先在「待办」里点选一条。")
            return
        t = self.todos[ri]
        top = tk.Toplevel(self.root)
        top.title("截止日")
        top.configure(bg="#e8f4fc")
        top.transient(self.root)
        ent = tk.Entry(top, font=("Microsoft YaHei UI", 11), width=28)
        ent.pack(padx=12, pady=(14, 4))
        if t.get("ddl"):
            ent.insert(0, str(t["ddl"]))
        ent.focus_set()

        def ok() -> None:
            t["ddl"] = ddl_from_text(ent.get())
            save_todos(self.todos)
            self.refresh_active_list()
            top.destroy()

        tk.Button(
            top,
            text="确定",
            command=ok,
            bg="#57c5b6",
            fg="white",
            relief=tk.FLAT,
            padx=16,
            pady=4,
        ).pack(pady=(4, 12))
        ent.bind("<Return>", lambda e: ok())

    def mark_complete(self) -> None:
        ri = self._index_active_real()
        if ri is None:
            messagebox.showinfo("提示", "请先在「待办」里点选一条，再点「完成」。")
            return
        self.todos[ri]["done"] = True
        self.todos[ri]["completed_at"] = datetime.now().isoformat(timespec="seconds")
        save_todos(self.todos)
        self.refresh_active_list()
        self._refresh_merit_popup_if_open()
        self.play_flower_fall()

    def open_merit_book(self) -> None:
        if self._merit_win is not None:
            try:
                if self._merit_win.winfo_exists():
                    plb = self._merit_popup_lb
                    if plb is not None:
                        self._fill_merit_listbox(plb)
                    self._merit_win.lift()
                    self._merit_win.focus_force()
                    return
            except tk.TclError:
                pass
            self._merit_win = None
            self._merit_popup_lb = None

        win = tk.Toplevel(self.root)
        self._merit_win = win
        win.title("功德簿 · 已完成记录")
        win.configure(bg="#fdf8f0")
        win.geometry("460x420")
        win.minsize(360, 280)
        win.transient(self.root)

        tk.Label(
            win,
            text="功德簿",
            font=("Microsoft YaHei UI", 16, "bold"),
            bg="#fdf8f0",
            fg="#6b4f2f",
        ).pack(pady=(12, 8))

        wrap = tk.Frame(win, bg="white", highlightbackground="#d4c4b0", highlightthickness=2)
        wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        sb = ttk.Scrollbar(wrap)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(
            wrap,
            font=("Microsoft YaHei UI", 10),
            selectmode=tk.SINGLE,
            activestyle="none",
            yscrollcommand=sb.set,
            borderwidth=0,
            highlightthickness=0,
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)
        self._merit_popup_lb = lb

        def close_merit() -> None:
            self._merit_win = None
            self._merit_popup_lb = None
            win.destroy()

        def restore_one() -> None:
            ri = self._index_merit_popup_real(lb)
            if ri is None:
                messagebox.showinfo("提示", "请先选中一条已完成记录。")
                return
            if not self.todos[ri].get("done", False):
                return
            self.todos[ri]["done"] = False
            self.todos[ri].pop("completed_at", None)
            save_todos(self.todos)
            self.refresh_active_list()
            self._fill_merit_listbox(lb)

        def delete_one() -> None:
            ri = self._index_merit_popup_real(lb)
            if ri is None:
                messagebox.showinfo("提示", "请先选中一条记录。")
                return
            if not self.todos[ri].get("done", False):
                return
            if not messagebox.askyesno("确认", "从功德簿永久删除这条记录？"):
                return
            del self.todos[ri]
            save_todos(self.todos)
            self.refresh_active_list()
            self._fill_merit_listbox(lb)

        btn_row = tk.Frame(win, bg="#fdf8f0")
        btn_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        tk.Button(
            btn_row,
            text="撤回待办",
            font=("Microsoft YaHei UI", 10),
            bg="#c9e4de",
            fg="#333",
            activebackground="#b5d4cd",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            command=restore_one,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            btn_row,
            text="删除记录",
            font=("Microsoft YaHei UI", 10),
            bg="#e0e0e0",
            fg="#333",
            activebackground="#d0d0d0",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            command=delete_one,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            btn_row,
            text="关闭窗口",
            font=("Microsoft YaHei UI", 10),
            bg="#8d6e63",
            fg="white",
            activebackground="#795548",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            command=close_merit,
        ).pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", close_merit)
        self._fill_merit_listbox(lb)

    def delete_active(self) -> None:
        ri = self._index_active_real()
        if ri is None:
            messagebox.showinfo("提示", "请先在「待办」里点选一条。")
            return
        if not messagebox.askyesno("确认", "确定删除这条待办吗？"):
            return
        del self.todos[ri]
        save_todos(self.todos)
        self.refresh_active_list()

    def _spawn_flower_group(self, cv: tk.Canvas, cx: int, cy: int) -> None:
        tag = "flower_anim"
        cv.delete(tag)
        r = 8
        for dx, dy in ((0, -16), (13, -4), (8, 12), (-8, 12), (-13, -4)):
            cv.create_oval(
                cx + dx - r,
                cy + dy - r,
                cx + dx + r,
                cy + dy + r,
                fill="#f48fb1",
                outline="#ad1457",
                width=1,
                tags=tag,
            )
        cv.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#fff59d", outline="#f9a825", tags=tag)
        cv.create_text(
            cx,
            cy - 22,
            text="❀",
            font=("Segoe UI Emoji", 22),
            fill="#880e4f",
            tags=tag,
        )

    def play_flower_fall(self) -> None:
        if self._flower_job is not None:
            try:
                self.root.after_cancel(self._flower_job)
            except tk.TclError:
                pass
            self._flower_job = None

        cv = self.flower_canvas
        cv.delete("all")
        self.root.update_idletasks()

        cw = max(cv.winfo_width(), 320)
        ch = max(cv.winfo_height(), 72)
        cx = random.randint(28, max(29, cw - 28))
        cy = 16
        self._spawn_flower_group(cv, cx, cy)

        steps = 0
        max_steps = max(10, (ch - 24) // 10)

        def finish() -> None:
            try:
                cv.delete("all")
            except tk.TclError:
                pass
            self._flower_job = None

        def step() -> None:
            nonlocal steps
            try:
                cv.move("flower_anim", random.randint(-2, 2), 9)
            except tk.TclError:
                finish()
                return
            steps += 1
            if steps < max_steps:
                self._flower_job = self.root.after(36, step)
            else:
                finish()

        self._flower_job = self.root.after(40, step)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    TodoApp().run()
