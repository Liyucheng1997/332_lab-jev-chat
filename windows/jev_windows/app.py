from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .capture import capture_chat
from .config import (
    AppConfig,
    delete_api_key,
    delete_deepseek_api_key,
    load_api_key,
    load_deepseek_api_key,
    save_api_key,
    save_deepseek_api_key,
)
from .deepseek_client import DeepSeekError, generate_suggestions
from .jev_api import judge
from .models import Analysis, Rect
from .safety import assert_safe_chat
from .windows_api import client_rect_on_screen, find_wechat_window
from .workflow import capture_without_overlay
from . import __version__


INTENT_LABELS = {
    "confirm_you_care": "确认你是否在乎",
    "vent_anger": "表达生气/受伤",
    "request_action": "要求具体行动",
    "seek_explanation": "寻求解释",
    "casual_chat": "轻松聊天",
    "close_topic": "结束话题",
}
ACTION_LABELS = {
    "check_history": "先查聊天记录",
    "apologize": "真诚道歉",
    "give_commitment": "给出具体承诺",
    "explain": "解释事实",
    "acknowledge": "先接住情绪",
    "say_less": "少说一点",
    "make_plan": "确定计划",
}
NEED_LABELS = {
    "apology": "道歉",
    "action": "行动",
    "explanation": "解释",
    "care": "被重视",
    "nothing": "无需追加",
}


class CalibrationOverlay(tk.Toplevel):
    def __init__(self, parent: tk.Misc, mode: str, on_done):
        super().__init__(parent)
        self.mode = mode
        self.on_done = on_done
        self.start: tuple[int, int] | None = None
        self.shape = None
        window = find_wechat_window()
        self.client = client_rect_on_screen(window.hwnd)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.30)
        self.geometry(
            f"{self.client.width}x{self.client.height}+{self.client.left}+{self.client.top}"
        )
        self.canvas = tk.Canvas(self, bg="#111827", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        instruction = "拖动框选聊天消息区域" if mode == "rect" else "点击微信输入框内部"
        self.canvas.create_text(
            self.client.width // 2,
            28,
            text=f"{instruction} · Esc 取消",
            fill="white",
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        self.bind("<Escape>", lambda _: self.destroy())
        self.focus_force()
        if mode == "rect":
            self.canvas.bind("<Button-1>", self._start_drag)
            self.canvas.bind("<B1-Motion>", self._drag)
            self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        else:
            self.canvas.bind("<Button-1>", self._pick_point)

    def _start_drag(self, event) -> None:
        self.start = (event.x, event.y)
        self.shape = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#38bdf8", width=4
        )

    def _drag(self, event) -> None:
        if self.start and self.shape:
            self.canvas.coords(self.shape, self.start[0], self.start[1], event.x, event.y)

    def _end_drag(self, event) -> None:
        if not self.start:
            return
        left, right = sorted((self.start[0], event.x))
        top, bottom = sorted((self.start[1], event.y))
        if right - left < 200 or bottom - top < 100:
            messagebox.showwarning("框选太小", "请框选完整的聊天消息区域。", parent=self)
            return
        self.on_done(Rect(left, top, right, bottom))
        self.destroy()

    def _pick_point(self, event) -> None:
        self.on_done((event.x, event.y))
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: "JevApp"):
        super().__init__(parent)
        self.parent_app = parent
        self.title("设置")
        self.geometry("560x470")
        self.transient(parent)
        self.grab_set()
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Jev / TypeSafe API 密钥").grid(row=0, column=0, padx=12, pady=(18, 6), sticky="w")
        self.key = ttk.Entry(self, show="•")
        self.key.grid(row=0, column=1, padx=12, pady=(18, 6), sticky="ew")
        key_status = "已保存密钥；留空保持不变" if load_api_key() else "尚未保存密钥"
        ttk.Label(self, text=key_status).grid(
            row=1, column=1, padx=12, sticky="w"
        )

        ttk.Label(self, text="DeepSeek API 密钥").grid(row=2, column=0, padx=12, pady=(18, 6), sticky="w")
        self.deepseek_key = ttk.Entry(self, show="•")
        self.deepseek_key.grid(row=2, column=1, padx=12, pady=(18, 6), sticky="ew")
        deepseek_status = "已保存密钥；留空保持不变" if load_deepseek_api_key() else "尚未配置；配置后生成建议回复"
        ttk.Label(self, text=deepseek_status).grid(row=3, column=1, padx=12, sticky="w")

        ttk.Label(self, text="DeepSeek 模型").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        self.deepseek_model = ttk.Entry(self)
        self.deepseek_model.insert(0, parent.settings.deepseek_model)
        self.deepseek_model.grid(row=4, column=1, padx=12, pady=10, sticky="ew")

        ttk.Label(self, text="关系说明").grid(row=5, column=0, padx=12, pady=6, sticky="nw")
        self.relationship = tk.Text(self, height=5, wrap="word")
        self.relationship.insert("1.0", parent.settings.relationship)
        self.relationship.grid(row=5, column=1, padx=12, pady=6, sticky="ew")

        ttk.Label(self, text="会话白名单").grid(row=6, column=0, padx=12, pady=6, sticky="w")
        self.whitelist = ttk.Entry(self)
        self.whitelist.insert(0, "，".join(parent.settings.allowed_titles))
        self.whitelist.grid(row=6, column=1, padx=12, pady=6, sticky="ew")
        ttk.Label(self, text="逗号分隔；留空允许所有会话").grid(row=7, column=1, padx=12, sticky="w")

        buttons = ttk.Frame(self)
        buttons.grid(row=8, column=0, columnspan=2, pady=20)
        ttk.Button(buttons, text="清除 Jev 密钥", command=self._clear_key).pack(side="left", padx=6)
        ttk.Button(buttons, text="清除 DeepSeek 密钥", command=self._clear_deepseek_key).pack(side="left", padx=6)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="left", padx=6)
        ttk.Button(buttons, text="保存", command=self._save).pack(side="left", padx=6)

    def _clear_key(self) -> None:
        if messagebox.askyesno("确认", "从 Windows 凭据管理器删除 Jev API 密钥？", parent=self):
            delete_api_key()
            self.parent_app.set_status("密钥已清除")

    def _clear_deepseek_key(self) -> None:
        if messagebox.askyesno("确认", "从 Windows 凭据管理器删除 DeepSeek API 密钥？", parent=self):
            delete_deepseek_api_key()
            self.parent_app.set_status("DeepSeek 密钥已清除")

    def _save(self) -> None:
        key = self.key.get().strip()
        if key:
            save_api_key(key)
        deepseek_key = self.deepseek_key.get().strip()
        if deepseek_key:
            save_deepseek_api_key(deepseek_key)
        settings = self.parent_app.settings
        settings.deepseek_model = self.deepseek_model.get().strip() or "deepseek-flash"
        settings.relationship = self.relationship.get("1.0", "end").strip()
        raw_titles = self.whitelist.get().replace("，", ",")
        settings.allowed_titles = [item.strip() for item in raw_titles.split(",") if item.strip()]
        settings.save()
        self.parent_app.set_status("设置已保存")
        self.destroy()


class JevApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = AppConfig.load()
        self.active_window = None
        self.is_analyzing = False
        self.title(f"Jev 微信助手 · Windows v{__version__}")
        self.geometry("500x760+40+60")
        self.minsize(450, 680)
        self.attributes("-topmost", True)
        self.configure(bg="#f8fafc")
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 11, "bold"))

        top = ttk.Frame(self, padding=16)
        top.pack(fill="x")
        ttk.Label(top, text="Jev 微信助手", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="设置", command=lambda: SettingsDialog(self)).pack(side="right")

        setup = ttk.LabelFrame(self, text="首次使用", padding=12)
        setup.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Button(setup, text="框选聊天区", command=self.calibrate_chat).pack(side="left", padx=4)

        self.analyze_button = ttk.Button(
            self, text="分析当前微信对话", style="Primary.TButton", command=self.analyze
        )
        self.analyze_button.pack(fill="x", padx=16, pady=8, ipady=7)

        self.status = tk.StringVar(value="请先设置 Jev API 密钥并框选聊天区")
        ttk.Label(self, textvariable=self.status, wraplength=430).pack(fill="x", padx=18, pady=4)

        self.summary = ttk.LabelFrame(self, text="Jev 判断", padding=12)
        self.summary.pack(fill="x", padx=16, pady=8)
        self.summary_text = tk.StringVar(value="尚未分析")
        ttk.Label(self.summary, textvariable=self.summary_text, wraplength=410, justify="left").pack(fill="x")

        self.preview = ttk.LabelFrame(self, text="识别到的最近消息", padding=10)
        self.preview.pack(fill="x", padx=16, pady=8)
        self.preview_text = tk.StringVar(value="—")
        ttk.Label(self.preview, textvariable=self.preview_text, wraplength=410, justify="left").pack(fill="x")

        self.suggestions = ttk.LabelFrame(self, text="DeepSeek 建议回复（仅供复制，不自动发送）", padding=10)
        self.suggestions.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self._show_suggestion_message("在设置中配置 DeepSeek API 密钥后生成建议回复")


    def set_status(self, text: str) -> None:
        self.status.set(text)

    def calibrate_chat(self) -> None:
        try:
            CalibrationOverlay(self, "rect", self._save_chat_rect)
        except Exception as exc:
            messagebox.showerror("无法校准", str(exc), parent=self)

    def _save_chat_rect(self, rect: Rect) -> None:
        self.settings.chat_rect = rect
        self.settings.save()
        self.set_status("聊天区已保存，可以开始分析")

    def analyze(self) -> None:
        if self.is_analyzing:
            return
        if self.settings.chat_rect is None:
            messagebox.showinfo("需要校准", "请先框选聊天消息区域。", parent=self)
            return
        key = load_api_key()
        if not key:
            messagebox.showinfo("需要密钥", "请在设置中保存 Jev / TypeSafe API 密钥。", parent=self)
            return
        self.is_analyzing = True
        self.analyze_button.configure(state="disabled")
        self.set_status("正在读取微信…截图时窗口会暂时隐藏，避免 OCR 读到助手自己")
        try:
            window = find_wechat_window()
            snapshot = capture_without_overlay(
                self._hide_for_capture,
                self._show_after_capture,
                lambda: capture_chat(window, self.settings.chat_rect),
            )
            assert_safe_chat(snapshot.raw_text)
            if self.settings.allowed_titles and not any(
                title in snapshot.title for title in self.settings.allowed_titles
            ):
                raise RuntimeError(f"当前会话“{snapshot.title}”不在白名单中。")
            self.active_window = window
            self._show_preview(snapshot)
        except Exception as exc:
            self._show_after_capture()
            self._show_error(str(exc))
            self._finish_analysis()
            return

        relationship = self.settings.relationship
        deepseek_key = load_deepseek_api_key()
        deepseek_model = self.settings.deepseek_model
        self._show_suggestion_message("等待 Jev 判断…" if deepseek_key else "未配置 DeepSeek API；本次只做 Jev 判断")
        self.set_status(f"已识别 {len(snapshot.messages)} 条消息，正在调用 Jev 判断…")
        threading.Thread(
            target=self._analyze_worker,
            args=(snapshot, key, relationship, deepseek_key, deepseek_model),
            daemon=True,
        ).start()

    def _hide_for_capture(self) -> None:
        self.withdraw()
        self.update_idletasks()

    def _show_after_capture(self) -> None:
        if self.state() == "withdrawn":
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)

    def _analyze_worker(
        self,
        snapshot,
        key: str,
        relationship: str,
        deepseek_key: str,
        deepseek_model: str,
    ) -> None:
        try:
            analysis = judge(snapshot, relationship, key)
            self.after(0, lambda: self._show_analysis(analysis))
            if not deepseek_key:
                self.after(0, lambda: self.set_status("Jev 判断完成；配置 DeepSeek API 后可生成建议回复"))
                return
            self.after(0, lambda: self.set_status("Jev 判断完成，正在让 DeepSeek 生成建议回复…"))
            try:
                replies = generate_suggestions(
                    snapshot,
                    relationship,
                    analysis,
                    deepseek_key,
                    deepseek_model,
                )
            except DeepSeekError as exc:
                message = str(exc)
                self.after(0, lambda message=message: self._show_suggestion_message(message))
                self.after(0, lambda message=message: self.set_status(f"Jev 判断完成；{message}"))
                return
            self.after(0, lambda: self._show_suggestions(replies))
            self.after(0, lambda: self.set_status("Jev 判断和 DeepSeek 建议回复已完成"))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda message=message: self._show_error(message))
        finally:
            self.after(0, self._finish_analysis)

    def _finish_analysis(self) -> None:
        self.is_analyzing = False
        self.analyze_button.configure(state="normal")

    def _show_preview(self, snapshot) -> None:
        lines = [
            f"{'我' if message.side == 'me' else '对方'}：{message.text}"
            for message in snapshot.messages[-5:]
        ]
        self.preview_text.set("\n".join(lines))

    def _show_analysis(self, analysis: Analysis) -> None:
        danger = "—" if analysis.danger_level is None else f"{analysis.danger_level:.1f}/9"
        reply_probability = "—" if analysis.should_reply_now is None else f"{analysis.should_reply_now * 100:.0f}%"
        resolved_probability = "—" if analysis.tension_resolved is None else f"{analysis.tension_resolved * 100:.0f}%"
        self.summary_text.set(
            f"真实意图：{INTENT_LABELS.get(analysis.true_intent, analysis.true_intent or '—')}\n"
            f"危险程度：{danger}\n"
            f"对方需要：{NEED_LABELS.get(analysis.need, analysis.need or '—')}\n"
            f"最佳动作：{ACTION_LABELS.get(analysis.best_action, analysis.best_action or '—')}\n"
            f"需要实质回复：{reply_probability}\n"
            f"紧张已化解：{resolved_probability}\n"
            f"耗时：{analysis.latency_ms} ms"
        )

    def _show_suggestion_message(self, text: str) -> None:
        for widget in self.suggestions.winfo_children():
            widget.destroy()
        ttk.Label(self.suggestions, text=text, wraplength=430, justify="left").pack(fill="x", pady=4)

    def _show_suggestions(self, replies: list[str]) -> None:
        for widget in self.suggestions.winfo_children():
            widget.destroy()
        for index, reply in enumerate(replies, start=1):
            row = ttk.Frame(self.suggestions)
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=f"{index}. {reply}", wraplength=360, justify="left").pack(
                side="left", fill="x", expand=True
            )
            ttk.Button(row, text="复制", command=lambda text=reply: self._copy_reply(text)).pack(
                side="right", padx=(8, 0)
            )

    def _copy_reply(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.set_status("建议回复已复制；请自行检查后粘贴发送")

    def _show_error(self, text: str) -> None:
        self.set_status(text)
        messagebox.showerror("Jev 微信助手", text, parent=self)


def main() -> None:
    JevApp().mainloop()


if __name__ == "__main__":
    main()
