"""Desktop typing practice window."""

from __future__ import annotations

import ctypes
import json
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import books
from dropfiles import install_drop
from engine import Session
from icons import IconSet
from product import APP_NAME, APP_VERSION, log_path, progress_path
from texts import build_passage, choose, read_text_file, split_segments

BG = "#1a1b26"
FG = "#c0caf5"
MUTED = "#565f89"
DONE = "#e6e8ee"
PENDING = "#4c5472"
CURRENT_FG = "#ffffff"
ERROR = "#f7768e"
SKIP = "#32364a"
BUTTON = "#24283b"
ACCENT = "#7aa2f7"
ACCENT_FG = "#1a1b26"
COVERS = (
    "#5c4d8a",
    "#2f5d62",
    "#8a4a3c",
    "#3d5a80",
    "#6d4c3b",
    "#3e5c49",
    "#7a3e5c",
    "#3a4a6b",
    "#6a5a32",
    "#4e3d5c",
)
PROGRESS_PATH = progress_path()
FRAME_RATES = (30, 60, 120, 240)


def _enable_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        return


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("980x760")
        self.root.minsize(760, 680)
        self.root.configure(bg=BG)
        self.font_ui = ("Microsoft YaHei UI", 11)
        self.font_passage = ("Microsoft YaHei UI", 26)
        self.font_pinyin = ("Consolas", 18)
        self.font_context = ("Microsoft YaHei UI", 14)
        self.font_stats = ("Microsoft YaHei UI", 11)
        self.check_punct = tk.BooleanVar(value=True)
        self.show_pinyin = tk.BooleanVar(value=False)
        self.stats_var = tk.StringVar()
        self.segment_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self._note = ""
        self.imported: list[str] | None = None
        self.import_pos = 0
        self._dialog_open = False
        self._last_score: tuple[float, float, int, str] | None = None
        self._source_kind = "builtin"
        self._source_path: str | None = None
        self._source_text: str | None = None
        self._book_id: str | None = None
        self._library_open = False
        self._library_flash_id: str | None = None
        self._shelf_cols = 0
        self._drop_hook: list = []
        self.icons = IconSet()
        self._menu_open = False
        self._lyric_job = None
        self._lyric_animating = False
        self._fps = 60
        self._bg = BG
        self._fg = FG
        self._done = DONE
        self._muted = MUTED
        self._pending = PENDING
        self._surface = BUTTON
        self._settings_open = False
        self._buttons = []
        self._build()
        if not self._restore():
            self._load_builtin("en")
        self._apply_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Map>", self._on_first_map, add="+")
        self.root.bind_all("<Key>", self.on_key)
        self.root.bind_all("<ButtonRelease-1>", self._refocus_later)
        self.root.bind_all("<MouseWheel>", self._library_wheel)
        self._drop_ready = install_drop(self.root, self._add_paths, self._drop_hook)
        self.root.after(200, self._tick)
        self.root.focus_set()

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        self.header = header
        header.pack(side="top", fill="x", padx=24, pady=(12, 0))
        self.shelf_button = tk.Button(
            header,
            text="资料库",
            command=self._show_library,
            font=self.font_ui,
            bg=BG,
            fg=MUTED,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        self.shelf_button._icon_name = "books"
        self.shelf_button.pack(side="left")
        self.menu_button = tk.Button(
            header,
            text="",
            command=self._toggle_menu,
            font=self.font_ui,
            bg=BG,
            fg=MUTED,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        self.menu_button._icon_name = "dots-three"
        self.menu_button.pack(side="right")
        self.add_button = tk.Button(
            header,
            text="加入",
            command=self._pick_books,
            font=self.font_ui,
            bg=BG,
            fg=MUTED,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        self.add_button._icon_name = "plus"
        self._place_label = tk.Label(
            header,
            textvariable=self.segment_var,
            font=self.font_stats,
            bg=BG,
            fg=MUTED,
        )
        self._place_label.pack(side="right", padx=(0, 8))

        self.menu = tk.Frame(self.root, bg=BG)
        actions = tk.Frame(self.menu, bg=BG)
        actions.pack(fill="x")
        self.english_button = self._button(actions, "英文", self.use_english, "text-aa")
        self.chinese_button = self._button(actions, "中文拼音", self.use_chinese, "translate")
        self.english_button.pack(side="left", padx=(0, 8))
        self.chinese_button.pack(side="left", padx=(0, 18))
        for label, command, icon in (
            ("换一篇", self.next_piece, "arrow-clockwise"),
            ("重来", self.restart, "arrow-counter-clockwise"),
            ("资料库", self._show_library, "books"),
            ("粘贴文本", self.paste_text, "clipboard-text"),
            ("设置", self._open_settings, "gear"),
        ):
            self._button(actions, label, command, icon).pack(side="left", padx=(0, 8))

        bottom = tk.Frame(self.root, bg=BG)
        self.bottom = bottom
        bottom.pack(side="bottom", fill="x", padx=24, pady=(0, 14))
        self._hint_label = tk.Label(
            bottom,
            text="请使用英文输入法",
            font=self.font_stats,
            bg=BG,
            fg=MUTED,
        )
        self._hint_label.pack(side="bottom")
        self._status_label = tk.Label(
            bottom,
            textvariable=self.status_var,
            font=self.font_stats,
            bg=BG,
            fg=ACCENT,
        )
        self._status_label.pack(side="bottom", pady=(0, 2))
        self._stats_label = tk.Label(
            bottom,
            textvariable=self.stats_var,
            font=self.font_stats,
            bg=BG,
            fg=MUTED,
        )
        self._stats_label.pack(side="bottom", pady=(0, 4))

        self.stage = tk.Frame(self.root, bg=BG)
        self.stage.pack(fill="both", expand=True)
        center = tk.Frame(self.stage, bg=BG)
        center.place(relx=0, rely=0, relwidth=1, relheight=1)
        center.bind("<Configure>", self._wrap_context)
        self.fade_canvas = tk.Canvas(center, bg=BG, highlightthickness=0, bd=0)
        self.fade_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._fade_large = self.fade_canvas.create_text(
            0,
            0,
            text="",
            anchor="center",
            font=self.font_passage,
            fill=DONE,
            state="hidden",
            justify="center",
        )
        self._fade_small = self.fade_canvas.create_text(
            0,
            0,
            text="",
            anchor="center",
            font=self.font_context,
            fill=BG,
            state="hidden",
            justify="center",
        )
        self._fade_image = self.fade_canvas.create_image(0, 0, anchor="center", state="hidden")
        self._in_image = self.fade_canvas.create_image(0, 0, anchor="center", state="hidden")
        self._fade_photo = None
        self._in_photo = None
        self._fade_src = None
        self._in_src = None
        self._fade_scaled_size = None
        self._in_scaled_size = None
        self._timer_open = False
        self.prev_label = tk.Label(
            center,
            text="",
            font=self.font_context,
            bg=BG,
            fg=MUTED,
            justify="center",
            wraplength=720,
        )
        self.next_label = tk.Label(
            center,
            text="",
            font=self.font_context,
            bg=BG,
            fg=MUTED,
            justify="center",
            wraplength=720,
        )

        self.text = tk.Text(
            center,
            height=1,
            wrap="word",
            font=self.font_passage,
            bg=BG,
            fg=PENDING,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="arrow",
            takefocus=0,
            insertwidth=0,
        )
        self.text.tag_configure("body", justify="center")
        self.text.tag_configure("done", foreground=DONE)
        self.text.tag_configure("pending", foreground=PENDING)
        self.text.tag_configure(
            "current",
            foreground=CURRENT_FG,
            background="",
            underline=True,
            underlinefg=ACCENT,
        )
        self.text.tag_configure(
            "error",
            foreground=ERROR,
            background="",
            underline=True,
            underlinefg=ERROR,
        )
        self.text.tag_configure("skipped", foreground=SKIP)
        self.text.bind("<FocusIn>", lambda _event: self.root.focus_set())
        self.text.bind("<<Paste>>", lambda _event: "break")

        self.leave_label = tk.Label(
            center,
            text="",
            font=self.font_context,
            bg=BG,
            fg=MUTED,
            justify="center",
            wraplength=720,
        )
        self.rise_label = tk.Label(
            center,
            text="",
            font=self.font_passage,
            bg=BG,
            fg=DONE,
            justify="center",
            wraplength=720,
        )
        self.rise_small = tk.Label(
            center,
            text="",
            font=self.font_context,
            bg=BG,
            fg=BG,
            justify="center",
            wraplength=720,
        )
        self.pinyin_row = tk.Frame(center, bg=BG)
        self.pinyin_typed = tk.Label(
            self.pinyin_row,
            text=" ",
            font=self.font_pinyin,
            bg=BG,
            fg=DONE,
        )
        self.pinyin_typed.pack(side="left")
        self.pinyin_rest = tk.Label(
            self.pinyin_row,
            text="",
            font=self.font_pinyin,
            bg=BG,
            fg=MUTED,
        )
        self.pinyin_rest.pack(side="left")
        self._build_library()
        self._build_settings()

    def _build_library(self) -> None:
        self.library_note = tk.StringVar()
        self.library_frame = tk.Frame(self.root, bg=BG)
        head = tk.Frame(self.library_frame, bg=BG)
        head.pack(fill="x", padx=48, pady=(28, 0))
        self.library_title = tk.Label(
            head,
            text="资料库",
            font=("Microsoft YaHei UI", 26),
            bg=BG,
            fg=FG,
            anchor="w",
        )
        self.library_title.pack(side="left")
        self.continue_button = tk.Button(
            head,
            text="继续练习",
            command=self._hide_library,
            font=self.font_ui,
            bg=BG,
            fg=FG,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        self.continue_button._icon_name = "book-open"
        self.continue_button.pack(side="right")
        self.library_meta = tk.Label(
            self.library_frame,
            text="",
            font=self.font_stats,
            bg=BG,
            fg=MUTED,
            anchor="w",
        )
        self.library_meta.pack(fill="x", padx=48, pady=(6, 0))
        self.library_status = tk.Label(
            self.library_frame,
            textvariable=self.library_note,
            font=self.font_stats,
            bg=BG,
            fg=ACCENT,
            anchor="w",
        )
        self.library_status.pack(fill="x", padx=48, pady=(4, 0))
        self.shelf_canvas = tk.Canvas(self.library_frame, bg=BG, highlightthickness=0, bd=0)
        self.shelf_canvas.pack(fill="both", expand=True, padx=34, pady=(8, 18))
        self.shelf_inner = tk.Frame(self.shelf_canvas, bg=BG)
        self._shelf_window = self.shelf_canvas.create_window((0, 0), window=self.shelf_inner, anchor="nw")
        self.shelf_canvas.bind("<Configure>", self._on_shelf_configure)
        self.shelf_inner.bind("<Configure>", self._sync_shelf_scroll)

    def _build_settings(self) -> None:
        self._settings_return = "practice"
        self.settings_frame = tk.Frame(self.root, bg=BG)
        head = tk.Frame(self.settings_frame, bg=BG)
        head.pack(fill="x", padx=48, pady=(18, 0))
        self.settings_title = tk.Label(
            head,
            text="设置",
            font=("Microsoft YaHei UI", 26),
            bg=BG,
            fg=FG,
            anchor="w",
        )
        self.settings_title.pack(side="left")
        self.settings_done = tk.Button(
            head,
            text="完成",
            command=self._close_settings,
            font=self.font_ui,
            bg=BG,
            fg=FG,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        self.settings_done._icon_name = "check"
        self.settings_done.pack(side="right")
        self.settings_meta = tk.Label(
            self.settings_frame,
            text=f"{APP_NAME} {APP_VERSION}  ·  进度和日志只保存在这台电脑上",
            font=self.font_stats,
            bg=BG,
            fg=MUTED,
            anchor="w",
        )
        self.settings_meta.pack(fill="x", padx=48, pady=(6, 0))
        self.settings_canvas = tk.Canvas(self.settings_frame, bg=BG, highlightthickness=0, bd=0)
        self.settings_canvas.pack(fill="both", expand=True, padx=48, pady=(4, 12))
        self.settings_body = tk.Frame(self.settings_canvas, bg=BG)
        self._settings_window = self.settings_canvas.create_window((0, 0), window=self.settings_body, anchor="nw")
        self.settings_canvas.bind("<Configure>", self._on_settings_configure)
        self.settings_body.bind("<Configure>", self._sync_settings_scroll)

    def _button(self, parent: tk.Widget, label: str, command, icon: str | None = None) -> tk.Button:
        button = tk.Button(
            parent,
            text=label,
            command=command,
            font=self.font_ui,
            bg=BUTTON,
            fg=FG,
            activebackground=ACCENT,
            activeforeground=ACCENT_FG,
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        if icon:
            button._icon_name = icon
        self._buttons.append(button)
        return button

    def _icon_size(self) -> int:
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
        except tk.TclError:
            dpi = 96
        return max(20, round(18 * dpi / 96))

    def _apply_icon(self, widget: tk.Widget, color: str) -> None:
        name = getattr(widget, "_icon_name", None)
        if not name:
            return
        photo = self.icons.photo(self.root, name, self._icon_size(), color)
        if photo is None:
            return
        widget._icon_ref = photo
        widget.configure(image=photo, compound="left")

    def _refresh_icons(self) -> None:
        self._apply_icon(self.menu_button, self._muted)
        for button in (self.shelf_button, self.add_button, self.continue_button, self.settings_done):
            self._apply_icon(button, self._fg)
        for button in self._buttons:
            self._apply_icon(button, self._fg)
        mark = self.icons.photo(self.root, "keyboard", self._icon_size() + 10, self._fg)
        if mark is not None:
            self._window_icon = mark
            self.root.iconphoto(True, mark)

    def _refocus_later(self, _event=None) -> None:
        if not self._dialog_open:
            self.root.after(10, self.root.focus_set)

    def _open_settings(self) -> None:
        self._show_settings()

    def _show_settings(self) -> None:
        if self._settings_open:
            return
        if self._lyric_animating:
            self._cancel_lyric(snap=True)
        self._set_menu(False)
        self._settings_return = "library" if self._library_open else "practice"
        if self._library_open:
            self._library_open = False
            self.library_note.set("")
            if self.add_button.winfo_manager():
                self.add_button.pack_forget()
            if self.library_frame.winfo_manager():
                self.library_frame.pack_forget()
        if self.stage.winfo_manager():
            self.stage.pack_forget()
        if self.bottom.winfo_manager():
            self.bottom.pack_forget()
        self._settings_open = True
        if not self.settings_frame.winfo_manager():
            self.settings_frame.pack(fill="both", expand=True)
        self.segment_var.set("")
        self._render_settings()
        self.root.focus_set()

    def _close_settings(self) -> None:
        if not self._settings_open:
            return
        back = self._settings_return
        self._settings_open = False
        if self.settings_frame.winfo_manager():
            self.settings_frame.pack_forget()
        if back == "library":
            self._show_library()
            return
        if not self.bottom.winfo_manager():
            self.bottom.pack(side="bottom", fill="x", padx=24, pady=(0, 14))
        if not self.stage.winfo_manager():
            self.stage.pack(fill="both", expand=True)
        self.refresh()
        self.root.focus_set()

    def _render_settings(self) -> None:
        for child in self.settings_body.winfo_children():
            child.destroy()
        practice = self._settings_section(self.settings_body, "练习", first=True)
        self._settings_switch_row(
            practice,
            "核对标点",
            "打开时，逗号和句号也要打",
            bool(self.check_punct.get()),
            True,
            self._set_punctuation,
        )
        self._settings_hairline(practice)
        chinese = self.passage.mode == "zh"
        self._settings_switch_row(
            practice,
            "显示拼音",
            "当前汉字下面写出还没打完的拼音" if chinese else "只在中文练习里可用",
            bool(self.show_pinyin.get()),
            chinese,
            self._set_pinyin,
        )
        motion = self._settings_section(
            self.settings_body,
            "动画",
            "数字越大，句子上滑时越顺。不改变要打的内容。",
        )
        self._settings_fps_row(motion)
        appearance = self._settings_section(self.settings_body, "外观")
        self._settings_color_row(appearance, "背景", self._bg, "bg")
        self._settings_hairline(appearance)
        self._settings_color_row(appearance, "字体颜色", self._fg, "fg")
        reset = self._settings_section(self.settings_body, "")
        self._settings_action_row(reset, "恢复默认", self._restore_defaults)

    def _settings_section(self, parent: tk.Frame, title: str, footer: str = "", first: bool = False) -> tk.Frame:
        block = tk.Frame(parent, bg=self._bg)
        block.pack(fill="x", pady=(2 if first else 16, 0))
        if title:
            tk.Label(
                block,
                text=title,
                font=self.font_stats,
                bg=self._bg,
                fg=self._muted,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 6))
        inner = self._settings_card(block)
        if footer:
            tk.Label(
                block,
                text=footer,
                font=self.font_stats,
                bg=self._bg,
                fg=self._muted,
                anchor="w",
                justify="left",
                wraplength=640,
            ).pack(fill="x", padx=16, pady=(6, 0))
        return inner

    def _settings_card(self, parent: tk.Frame) -> tk.Frame:
        shell = tk.Frame(parent, bg=self._bg)
        shell.pack(fill="x")
        canvas = tk.Canvas(shell, bg=self._bg, highlightthickness=0, bd=0, height=48)
        canvas._cover = True
        canvas.pack(fill="x")
        inner = tk.Frame(canvas, bg=self._surface)
        window = canvas.create_window((12, 12), window=inner, anchor="nw")

        def sync(_event: tk.Event | None = None) -> None:
            inner.update_idletasks()
            width = max(shell.winfo_width(), 280)
            height = max(inner.winfo_reqheight() + 24, 52)
            if getattr(canvas, "_laid", None) == (width, height, self._surface):
                return
            canvas._laid = (width, height, self._surface)
            canvas.configure(width=width, height=height, bg=self._bg)
            canvas.coords(window, 12, 12)
            canvas.itemconfigure(window, width=width - 24)
            canvas.delete("card")
            canvas.create_polygon(
                _round_points(1, 1, width - 1, height - 1, 12),
                smooth=True,
                fill=self._surface,
                outline="",
                tags="card",
            )
            canvas.tag_lower("card")

        inner.bind("<Configure>", sync)
        shell.bind("<Configure>", sync)
        canvas._sync = sync
        return inner

    def _settings_hairline(self, parent: tk.Frame) -> None:
        line = tk.Frame(parent, bg=_mix_color(self._surface, self._fg, 0.16), height=1)
        line.pack_propagate(False)
        line.pack(fill="x", padx=(16, 12))

    def _settings_switch_row(
        self,
        parent: tk.Frame,
        title: str,
        hint: str,
        value: bool,
        enabled: bool,
        command,
    ) -> None:
        row = tk.Frame(parent, bg=self._surface)
        row.pack(fill="x")
        switch = self._settings_switch(row, value, enabled, command)
        switch.pack(side="right", padx=(8, 14), pady=12)
        text = tk.Frame(row, bg=self._surface)
        text.pack(side="left", fill="x", expand=True, padx=(16, 8), pady=10)
        tk.Label(
            text,
            text=title,
            font=self.font_ui,
            bg=self._surface,
            fg=self._fg if enabled else self._muted,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            text,
            text=hint,
            font=self.font_stats,
            bg=self._surface,
            fg=self._muted,
            anchor="w",
        ).pack(anchor="w")

    def _settings_switch(self, parent: tk.Frame, value: bool, enabled: bool, command) -> tk.Canvas:
        width, height = 50, 30
        canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=self._surface,
            cursor="hand2" if enabled else "arrow",
        )
        canvas._cover = True
        state = {"on": bool(value), "job": None}

        def draw(progress: float) -> None:
            canvas.delete("all")
            if enabled:
                off = _mix_color(self._fg, self._bg, 0.62)
                track = _mix_color(off, ACCENT, progress)
                knob = "#ffffff"
            else:
                track = _mix_color(self._surface, self._fg, 0.2)
                knob = _mix_color("#ffffff", self._surface, 0.4)
            canvas.create_oval(1, 1, width - 1, height - 1, fill=track, outline="")
            knob_d = height - 6
            x = 3 + progress * (width - knob_d - 6)
            canvas.create_oval(x, 3, x + knob_d, 3 + knob_d, fill=knob, outline="")

        def animate(start: float, end: float) -> None:
            if state["job"] is not None:
                canvas.after_cancel(state["job"])
            frames = 7

            def step(index: int) -> None:
                amount = index / frames
                eased = amount * amount * (3 - 2 * amount)
                draw(start + (end - start) * eased)
                if index < frames:
                    state["job"] = canvas.after(16, lambda: step(index + 1))
                else:
                    state["job"] = None

            step(0)

        def toggle(_event: tk.Event | None = None) -> None:
            if not enabled:
                return
            state["on"] = not state["on"]
            animate(0.0 if state["on"] else 1.0, 1.0 if state["on"] else 0.0)
            command(state["on"])

        canvas.bind("<Button-1>", toggle)
        draw(1.0 if state["on"] else 0.0)
        return canvas

    def _settings_fps_row(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent, bg=self._surface)
        row.pack(fill="x")
        segment = self._settings_segments(row)
        segment.pack(side="right", padx=(8, 14), pady=12)
        tk.Label(
            row,
            text="帧率",
            font=self.font_ui,
            bg=self._surface,
            fg=self._fg,
            anchor="w",
        ).pack(side="left", padx=(16, 8), pady=14)

    def _settings_segments(self, parent: tk.Frame) -> tk.Canvas:
        values = FRAME_RATES
        seg_w = 58
        height = 30
        width = seg_w * len(values)
        canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=self._surface,
            cursor="hand2",
        )
        canvas._cover = True

        def draw() -> None:
            canvas.delete("all")
            track = _mix_color(self._surface, self._bg, 0.55)
            canvas.create_polygon(_round_points(0, 0, width, height, 9), smooth=True, fill=track, outline="")
            for index, value in enumerate(values):
                x = index * seg_w
                selected = value == self._fps
                if selected:
                    canvas.create_polygon(
                        _round_points(x + 2, 2, x + seg_w - 2, height - 2, 7),
                        smooth=True,
                        fill=self._bg,
                        outline="",
                    )
                canvas.create_text(
                    x + seg_w / 2,
                    height / 2,
                    text=str(value),
                    fill=self._fg if selected else self._muted,
                    font=self.font_ui,
                )

        def pick(event: tk.Event) -> None:
            index = min(len(values) - 1, max(0, int(event.x) // seg_w))
            chosen = values[index]
            if chosen == self._fps:
                return
            self._fps = chosen
            draw()
            self._save_progress()

        canvas.bind("<Button-1>", pick)
        draw()
        return canvas

    def _settings_color_row(self, parent: tk.Frame, title: str, color: str, kind: str) -> None:
        row = tk.Frame(parent, bg=self._surface, cursor="hand2")
        row.pack(fill="x")
        swatch = tk.Canvas(
            row,
            width=28,
            height=28,
            highlightthickness=0,
            bd=0,
            bg=self._surface,
            cursor="hand2",
        )
        swatch._cover = True
        swatch.pack(side="right", padx=(8, 14), pady=12)
        swatch.create_oval(1, 1, 27, 27, fill=color, outline=_mix_color(color, self._fg, 0.28))
        value = tk.Label(
            row,
            text=color,
            font=("Consolas", 11),
            bg=self._surface,
            fg=self._muted,
            cursor="hand2",
        )
        value.pack(side="right")
        name = tk.Label(
            row,
            text=title,
            font=self.font_ui,
            bg=self._surface,
            fg=self._fg,
            cursor="hand2",
        )
        name.pack(side="left", padx=(16, 8), pady=14)

        def pick(_event: tk.Event | None = None, target: str = kind) -> None:
            self._pick_page_color(target)

        for widget in (row, swatch, value, name):
            widget.bind("<Button-1>", pick)

    def _settings_action_row(self, parent: tk.Frame, title: str, command) -> None:
        row = tk.Frame(parent, bg=self._surface, cursor="hand2")
        row.pack(fill="x")
        label = tk.Label(
            row,
            text=title,
            font=self.font_ui,
            bg=self._surface,
            fg=ACCENT,
            cursor="hand2",
            pady=12,
        )
        label.pack()
        row.bind("<Button-1>", lambda _event: command())
        label.bind("<Button-1>", lambda _event: command())

    def _set_punctuation(self, enabled: bool) -> None:
        self.check_punct.set(enabled)
        self._save_progress()
        if hasattr(self, "passage"):
            self.restart()

    def _set_pinyin(self, enabled: bool) -> None:
        self.show_pinyin.set(enabled)
        self._save_progress()

    def _pick_page_color(self, kind: str) -> None:
        current = self._bg if kind == "bg" else self._fg
        self._dialog_open = True
        try:
            chosen = colorchooser.askcolor(
                color=current,
                parent=self.root,
                title="背景" if kind == "bg" else "字体颜色",
            )
        finally:
            self._dialog_open = False
        self.root.focus_set()
        if not chosen or not chosen[1]:
            return
        parsed = _normalize_hex(chosen[1])
        if parsed is None:
            return
        if kind == "bg":
            self._bg = parsed
        else:
            self._fg = parsed
        self._apply_theme()
        self._save_progress()

    def _restore_defaults(self) -> None:
        punct_changed = not bool(self.check_punct.get())
        self._bg = BG
        self._fg = FG
        self.check_punct.set(True)
        self.show_pinyin.set(False)
        self._fps = 60
        self._apply_theme()
        self._save_progress()
        if punct_changed and hasattr(self, "passage"):
            self.restart()

    def _on_settings_configure(self, event: tk.Event) -> None:
        self.settings_canvas.itemconfigure(self._settings_window, width=event.width)

    def _sync_settings_scroll(self, _event: tk.Event | None = None) -> None:
        box = self.settings_canvas.bbox("all")
        if box is not None:
            self.settings_canvas.configure(scrollregion=box)

    def _apply_theme(self) -> None:
        light = _luminance(self._bg) >= 150
        self._surface = _mix_color(self._bg, "#000000" if light else "#ffffff", 0.14)
        self._muted = _mix_color(self._fg, self._bg, 0.62)
        self._pending = _mix_color(self._fg, self._bg, 0.45)
        self._done = self._fg
        self._paint_tree(self.root)
        self.text.configure(bg=self._bg, fg=self._pending, insertbackground=self._fg)
        self.text.tag_configure("done", foreground=self._done)
        self.text.tag_configure("pending", foreground=self._pending)
        self.text.tag_configure("current", foreground=self._fg, background="", underlinefg=self._fg)
        self.text.tag_configure("error", foreground=ERROR, background="", underlinefg=ERROR)
        self.fade_canvas.configure(bg=self._bg)
        for label in (self.prev_label, self.next_label, self.leave_label):
            label.configure(bg=self._bg, fg=self._muted)
        self.rise_label.configure(bg=self._bg, fg=self._done)
        self.rise_small.configure(bg=self._bg, fg=self._bg)
        self.pinyin_row.configure(bg=self._bg)
        self.pinyin_typed.configure(bg=self._bg, fg=self._done)
        self.pinyin_rest.configure(bg=self._bg, fg=self._muted)
        self._hint_label.configure(bg=self._bg, fg=self._muted)
        self._stats_label.configure(bg=self._bg, fg=self._muted)
        self._status_label.configure(bg=self._bg, fg=self._fg)
        self._place_label.configure(bg=self._bg, fg=self._muted)
        self.menu_button.configure(bg=self._bg, fg=self._muted, activebackground=self._bg, activeforeground=self._fg)
        for button in (self.shelf_button, self.add_button, self.continue_button, self.settings_done):
            button.configure(bg=self._bg, fg=self._fg, activebackground=self._bg, activeforeground=self._fg)
        self.library_title.configure(bg=self._bg, fg=self._fg)
        self.library_meta.configure(bg=self._bg, fg=self._muted)
        self.library_status.configure(bg=self._bg, fg=self._fg)
        self.shelf_canvas.configure(bg=self._bg)
        self.shelf_inner.configure(bg=self._bg)
        self.settings_title.configure(bg=self._bg, fg=self._fg)
        self.settings_meta.configure(bg=self._bg, fg=self._muted)
        self.settings_canvas.configure(bg=self._bg)
        self.settings_body.configure(bg=self._bg)
        self._refresh_icons()
        if self._settings_open:
            self._render_settings()
        if self._library_open:
            self._render_shelf()
        if hasattr(self, "passage"):
            self.refresh()

    def _paint_tree(self, widget: tk.Widget) -> None:
        if getattr(widget, "_cover", False):
            return
        kind = widget.winfo_class()
        if kind in ("Frame", "Canvas", "Tk", "Toplevel"):
            widget.configure(bg=self._bg)
        elif kind == "Label":
            widget.configure(bg=self._bg)
        elif kind == "Button":
            widget.configure(bg=self._surface, fg=self._fg, activebackground=self._surface, activeforeground=self._fg)
        elif kind == "Checkbutton":
            widget.configure(bg=self._bg, fg=self._fg, activebackground=self._bg, selectcolor=self._surface)
        for child in widget.winfo_children():
            self._paint_tree(child)

    def _set_fps(self, fps: int) -> None:
        if fps not in FRAME_RATES:
            return
        self._fps = fps
        self._save_progress()

    def _frame_delay(self) -> int:
        return max(1, round(1000 / self._fps))

    def _on_close(self) -> None:
        self._cancel_lyric()
        self._save_progress()
        self.root.destroy()

    def _restore(self) -> bool:
        data = _read_progress()
        if data is None:
            return False
        mode = data.get("mode") if data.get("mode") in ("en", "zh") else "en"
        self.check_punct.set(bool(data.get("check_punctuation", True)))
        if data.get("fps") in FRAME_RATES:
            self._fps = int(data["fps"])
        bg = _normalize_hex(str(data.get("bg") or ""))
        fg = _normalize_hex(str(data.get("fg") or ""))
        if bg:
            self._bg = bg
        if fg:
            self._fg = fg
        kind = data.get("kind")
        if kind == "file":
            path = str(data.get("path") or "")
            book_id = str(data.get("book_id") or "")
            if book_id and books.get_book(book_id) is not None:
                path = str(books.book_file(book_id))
            else:
                book_id = ""
            try:
                content = read_text_file(path)
            except OSError:
                self._note = "找不到上次的文件，已从内置短句开始"
                self._load_builtin(mode)
                return True
            if not book_id and path:
                try:
                    adopted, _created = books.add_file(path)
                except (OSError, ValueError):
                    adopted = None
                if adopted is not None:
                    book_id = adopted.id
                    path = str(books.book_file(book_id))
            if not self.load_imported(
                content,
                index=_as_index(data.get("index")),
                path=path,
                book_id=book_id or None,
            ):
                self._note = "找不到上次的文件，已从内置短句开始"
                self._load_builtin(mode)
            return True
        if kind == "paste":
            text = str(data.get("text") or "")
            if self.load_imported(text, index=_as_index(data.get("index"))):
                return True
            self._note = "找不到上次的文件，已从内置短句开始"
            self._load_builtin(mode)
            return True
        if kind == "builtin":
            sentence = str(data.get("sentence") or "").strip()
            if not sentence:
                return False
            self.imported = None
            self.start_text(sentence, mode)
            return True
        return False

    def _save_progress(self) -> None:
        if not hasattr(self, "passage"):
            return
        payload: dict = {
            "kind": self._source_kind,
            "index": self.import_pos if self.imported is not None else 0,
            "mode": self.passage.mode,
            "sentence": self.passage.text,
            "check_punctuation": bool(self.check_punct.get()),
            "fps": self._fps,
            "bg": self._bg,
            "fg": self._fg,
        }
        if self._book_id:
            payload["book_id"] = self._book_id
        if self._source_kind == "file" and self._source_path:
            payload["path"] = self._source_path
        elif self._source_kind == "paste":
            payload["text"] = self._source_text or ""
        try:
            PROGRESS_PATH.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            return
        if self._book_id and self.imported is not None:
            try:
                books.update_progress(
                    self._book_id,
                    self.import_pos,
                    len(self.imported),
                    False,
                )
            except OSError:
                return

    def _load_builtin(self, mode: str) -> None:
        avoid = None
        if hasattr(self, "passage") and self.passage.mode == mode:
            avoid = self.passage.text
        self.imported = None
        self.start_text(choose(mode, avoid), mode)

    def use_english(self) -> None:
        self._switch_mode("en")

    def use_chinese(self) -> None:
        self._switch_mode("zh")

    def _switch_mode(self, mode: str) -> None:
        if self.imported is None and self.passage.mode == mode:
            return
        self._note = ""
        self._last_score = None
        self.imported = None
        self.start_text(choose(mode), mode)
        if self._library_open:
            self._hide_library()

    def next_piece(self) -> None:
        self._capture_score()
        if self.imported is not None and self.import_pos + 1 < len(self.imported):
            old_prev = self._neighbor(-1)
            old_current = self.passage.text
            self.import_pos += 1
            self._note = ""
            self.start_text(self.imported[self.import_pos])
            self._scroll_lyrics(old_prev, old_current)
            return
        if self.imported is not None:
            mode = self.passage.mode
            if self._book_id:
                book = books.get_book(self._book_id)
                title = book.title if book is not None else "这本书"
                books.mark_finished(self._book_id)
                self._book_id = None
                self.imported = None
                self._note = ""
                self.start_text(choose(mode), mode)
                self._show_library(f"已读完《{title}》")
                return
            self.imported = None
            self._note = "已练完导入文本，回到内置短句"
            self.start_text(choose(mode), mode)
            return
        self._note = ""
        self._load_builtin(self.passage.mode)

    def restart(self) -> None:
        self._note = ""
        self._last_score = None
        self.session = Session(self.passage, self.check_punct.get())
        self._save_progress()
        self.refresh()

    def start_text(self, text: str, mode: str | None = None) -> None:
        self.passage = build_passage(text, mode)
        self.session = Session(self.passage, self.check_punct.get())
        if self.imported is None:
            self._book_id = None
            self._source_kind = "builtin"
            self._source_path = None
            self._source_text = None
        self._save_progress()
        self.refresh()

    def load_imported(
        self,
        text: str,
        index: int = 0,
        path: str | None = None,
        book_id: str | None = None,
    ) -> bool:
        segments = split_segments(text)
        if not segments:
            self._note = "没有可练习的文本"
            self.refresh()
            return False
        self._last_score = None
        self.imported = segments
        self.import_pos = max(0, min(index, len(segments) - 1))
        self._book_id = book_id
        if path:
            self._source_kind = "file"
            self._source_path = str(Path(path).resolve())
            self._source_text = None
        else:
            self._source_kind = "paste"
            self._source_path = None
            self._source_text = text
        self._note = ""
        self.start_text(segments[self.import_pos])
        return True

    def import_file(self) -> None:
        self._show_library()

    def _pick_books(self) -> None:
        self._dialog_open = True
        try:
            chosen = filedialog.askopenfilenames(
                parent=self.root,
                title="加入资料库",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            )
        finally:
            self._dialog_open = False
        self.root.focus_set()
        if chosen:
            self._add_paths(list(chosen))

    def _add_paths(self, paths: list[str]) -> None:
        added: list[books.Book] = []
        existing: list[books.Book] = []
        skipped = 0
        failed = 0
        for raw in paths:
            file = Path(raw)
            if not file.is_file() or file.suffix.lower() != ".txt":
                skipped += 1
                continue
            try:
                book, created = books.add_file(str(file))
            except ValueError:
                failed += 1
                continue
            except OSError:
                failed += 1
                continue
            if created:
                added.append(book)
            else:
                existing.append(book)
        if added:
            self._library_flash_id = added[0].id
        parts: list[str] = []
        if len(added) == 1:
            parts.append(f"已加入《{added[0].title}》")
        elif added:
            parts.append(f"已加入 {len(added)} 本")
        if existing and not added:
            if len(existing) == 1:
                parts.append(f"《{existing[0].title}》已经在资料库里")
            else:
                parts.append("这些文本已经在资料库里")
        elif existing:
            parts.append(f"{len(existing)} 本已经在资料库里")
        if skipped and not added:
            parts.append("只能加入 txt 文本")
        elif skipped:
            parts.append(f"跳过 {skipped} 个不是 txt 的文件")
        if failed and not added:
            parts.append("没有可练习的文本")
        note = "，".join(parts)
        self._show_library(note or None)

    def paste_text(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            text = ""
        if not str(text).strip():
            self._note = "剪贴板是空的"
            self.refresh()
            return
        self.load_imported(str(text))
        if self._library_open:
            self._hide_library()

    def _show_library(self, note: str | None = None) -> None:
        if self._settings_open:
            self._settings_open = False
            if self.settings_frame.winfo_manager():
                self.settings_frame.pack_forget()
        if self._lyric_animating:
            self._cancel_lyric(snap=True)
        self._save_progress()
        self._set_menu(False)
        if note is not None:
            self.library_note.set(note)
        if note is None:
            self._library_flash_id = None
        self._library_open = True
        if self.stage.winfo_manager():
            self.stage.pack_forget()
        if self.bottom.winfo_manager():
            self.bottom.pack_forget()
        if not self.library_frame.winfo_manager():
            self.library_frame.pack(fill="both", expand=True)
        if not self.add_button.winfo_manager():
            self.add_button.pack(side="right", after=self.menu_button)
        self.segment_var.set("")
        self.root.update_idletasks()
        width = self.shelf_canvas.winfo_width()
        self._shelf_cols = max(1, width // 176) if width > 1 else 4
        self._render_shelf()
        self.root.focus_set()

    def _hide_library(self) -> None:
        if not self._library_open:
            return
        self._library_open = False
        self.library_note.set("")
        if self.add_button.winfo_manager():
            self.add_button.pack_forget()
        if self.library_frame.winfo_manager():
            self.library_frame.pack_forget()
        if not self.bottom.winfo_manager():
            self.bottom.pack(side="bottom", fill="x", padx=24, pady=(0, 14))
        if not self.stage.winfo_manager():
            self.stage.pack(fill="both", expand=True)
        self.refresh()
        self.root.focus_set()

    def _library_wheel(self, event: tk.Event) -> None:
        if self._settings_open:
            self.settings_canvas.yview_scroll(int(-event.delta / 120), "units")
            return
        if not self._library_open:
            return
        self.shelf_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_shelf_configure(self, event: tk.Event) -> None:
        self.shelf_canvas.itemconfigure(self._shelf_window, width=event.width)
        if not self._library_open:
            return
        cols = max(1, event.width // 176)
        if cols != self._shelf_cols:
            self._shelf_cols = cols
            self._render_shelf()

    def _sync_shelf_scroll(self, _event: tk.Event | None = None) -> None:
        box = self.shelf_canvas.bbox("all")
        if box is not None:
            self.shelf_canvas.configure(scrollregion=box)

    def _render_shelf(self) -> None:
        for child in self.shelf_inner.winfo_children():
            child.destroy()
        found = books.list_books()
        if found:
            self.library_meta.configure(text=f"{len(found)} 本  ·  把 txt 拖进窗口，或点「加入」")
        else:
            self.library_meta.configure(text="把 txt 拖进窗口，文件会留在资料库里")
        if not found:
            self._render_empty_shelf()
            return
        cols = max(1, self._shelf_cols)
        for index, book in enumerate(found):
            self._render_book(book, index % cols, index // cols)

    def _render_empty_shelf(self) -> None:
        box = tk.Frame(self.shelf_inner, bg=self._bg)
        box.pack(pady=(64, 0))
        tk.Label(
            box,
            text="把 txt 拖到这里",
            font=("Microsoft YaHei UI", 20),
            bg=self._bg,
            fg=self._fg,
        ).pack()
        tk.Label(
            box,
            text="加入之后会留在资料库里。点封面就能从上次的句子接着练。",
            font=self.font_stats,
            bg=self._bg,
            fg=self._muted,
            pady=8,
        ).pack()
        pick = tk.Button(
            box,
            text="选取文件",
            command=self._pick_books,
            font=self.font_ui,
            bg=self._surface,
            fg=self._fg,
            activebackground=self._surface,
            activeforeground=self._fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
        )
        pick._icon_name = "file-plus"
        self._apply_icon(pick, self._fg)
        pick.pack(pady=(8, 0))

    def _render_book(self, book: books.Book, column: int, row: int) -> None:
        cell = tk.Frame(self.shelf_inner, bg=self._bg, width=156)
        cell.grid(row=row, column=column, padx=16, pady=14, sticky="n")
        cover = tk.Canvas(
            cell,
            width=132,
            height=196,
            bg=self._bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        cover._cover = True
        cover.pack()
        self._draw_cover(cover, book)
        title = tk.Label(
            cell,
            text=book.title,
            font=self.font_ui,
            bg=self._bg,
            fg=self._fg,
            wraplength=136,
            justify="center",
            cursor="hand2",
        )
        title.pack(fill="x", pady=(2, 0))
        caption = self._book_caption(book)
        cap = None
        if caption:
            cap = tk.Label(
                cell,
                text=caption,
                font=self.font_stats,
                bg=self._bg,
                fg=self._muted,
                cursor="hand2",
            )
            cap.pack()
        targets = [cell, cover, title]
        if cap is not None:
            targets.append(cap)
        for target in targets:
            target.bind("<Button-1>", lambda _event, book_id=book.id: self._open_book(book_id))
            target.bind("<Button-3>", lambda event, book_id=book.id: self._book_menu(event, book_id))

    def _book_caption(self, book: books.Book) -> str:
        if book.finished:
            return "读完"
        if book.opened and book.segments:
            return f"{min(book.index + 1, book.segments)} / {book.segments}"
        return ""

    def _draw_cover(self, canvas: tk.Canvas, book: books.Book) -> None:
        canvas.delete("all")
        color = COVERS[sum(ord(char) for char in book.id) % len(COVERS)]
        spine = _mix_color(color, "#000000", 0.28)
        shadow = _mix_color(self._bg, "#000000", 0.35)
        marked = self._library_flash_id or self._book_id
        selected = book.id == marked
        canvas.create_polygon(_round_points(14, 12, 126, 186, 8), smooth=True, fill=shadow, outline="")
        canvas.create_polygon(_round_points(8, 6, 118, 178, 8), smooth=True, fill=color, outline="")
        canvas.create_rectangle(8, 14, 18, 170, fill=spine, outline="")
        canvas.create_text(
            68,
            86,
            text=_cover_lines(book.title),
            fill="#f7f4ef",
            font=("Microsoft YaHei UI", 15),
            justify="center",
        )
        if book.finished or book.opened:
            ratio = 1.0 if book.finished else (book.index + 1) / max(book.segments, 1)
            canvas.create_rectangle(24, 162, 108, 165, fill=_mix_color(color, "#000000", 0.35), outline="")
            canvas.create_rectangle(24, 162, 24 + max(4, int(84 * ratio)), 165, fill="#f7f4ef", outline="")
        if selected:
            canvas.create_polygon(_round_points(4, 2, 122, 182, 10), smooth=True, outline=ACCENT, width=2, fill="")

    def _open_book(self, book_id: str) -> None:
        book = books.get_book(book_id)
        if book is None:
            self.library_note.set("这本书已经不在资料库里")
            self._render_shelf()
            return
        try:
            text = books.read_text(book_id)
        except OSError:
            self.library_note.set("这本书的文件读不出来")
            return
        index = 0 if book.finished else book.index
        self._library_flash_id = None
        self._hide_library()
        self.load_imported(text, index=index, path=str(books.book_file(book_id)), book_id=book_id)

    def _book_menu(self, event: tk.Event, book_id: str) -> None:
        book = books.get_book(book_id)
        if book is None:
            return
        menu = tk.Menu(self.root, tearoff=0)
        self._book_popup = menu
        open_icon = self.icons.photo(self.root, "book-open", self._icon_size(), self._fg)
        remove_icon = self.icons.photo(self.root, "trash", self._icon_size(), self._fg)
        menu.add_command(label="打开", image=open_icon, compound="left", command=lambda: self._open_book(book_id))
        menu.add_command(label="从资料库移除", image=remove_icon, compound="left", command=lambda: self._remove_book(book))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _remove_book(self, book: books.Book) -> None:
        self._dialog_open = True
        try:
            agreed = messagebox.askyesno(
                "从资料库移除",
                f"移除《{book.title}》？这本书的练习进度会一起删掉。",
                parent=self.root,
            )
        finally:
            self._dialog_open = False
        self.root.focus_set()
        if not agreed:
            return
        books.remove_book(book.id)
        if self._book_id == book.id:
            mode = self.passage.mode if hasattr(self, "passage") else "en"
            self._book_id = None
            self.imported = None
            self._last_score = None
            self.start_text(choose(mode), mode)
        if self._library_flash_id == book.id:
            self._library_flash_id = None
        self.library_note.set(f"已移除《{book.title}》")
        self._render_shelf()

    def _toggle_menu(self) -> None:
        self._set_menu(not self._menu_open)

    def _set_menu(self, open_menu: bool) -> None:
        self._menu_open = open_menu
        if open_menu:
            before = self.stage
            if not before.winfo_manager():
                before = self.library_frame if self.library_frame.winfo_manager() else self.settings_frame
            if before.winfo_manager():
                self.menu.pack(side="top", fill="x", padx=24, pady=(8, 0), before=before)
            else:
                self.menu.pack(side="top", fill="x", padx=24, pady=(8, 0))
            return
        if self.menu.winfo_manager():
            self.menu.pack_forget()

    def _wrap_context(self, event: tk.Event) -> None:
        width = max(event.width - 8, 200)
        for label in (
            self.prev_label,
            self.next_label,
            self.leave_label,
            self.rise_label,
            self.rise_small,
        ):
            label.configure(wraplength=width)

    def _neighbor(self, offset: int) -> str:
        if self.imported is None:
            return ""
        index = self.import_pos + offset
        if index < 0 or index >= len(self.imported):
            return ""
        return self.imported[index]

    def _place_text(self) -> str:
        if self.imported is None:
            return ""
        position = f"{self.import_pos + 1} / {len(self.imported)}"
        if self._book_id:
            book = books.get_book(self._book_id)
            if book is not None:
                return f"{book.title} · {position}"
        if self._source_kind == "file" and self._source_path:
            return f"{Path(self._source_path).stem} · {position}"
        return position

    def on_key(self, event: tk.Event) -> str | None:
        if self._dialog_open:
            return None
        if self._settings_open:
            if event.keysym == "Escape":
                self._close_settings()
            return "break"
        if self._library_open:
            if event.keysym == "Escape":
                self._hide_library()
            return "break"
        if event.state & 0x4 or event.state & 0x20000:
            return None
        typing_key = event.keysym == "BackSpace" or bool(event.char and ord(event.char) >= 32)
        if typing_key and self._lyric_animating:
            self._cancel_lyric(snap=True)
        if self._menu_open and typing_key:
            self._set_menu(False)
        if event.keysym == "BackSpace":
            self._note = ""
            self.session.backspace()
            self.refresh()
            return "break"
        char = event.char
        if not char or ord(char) < 32:
            return None
        self._note = ""
        was_finished = self.session.finished
        for piece in char:
            self.session.press(piece)
        if not was_finished and self.session.finished:
            self.next_piece()
        else:
            self.refresh()
        return "break"

    def _tick(self) -> None:
        if self.session.started_at is not None and not self.session.finished:
            self._show_stats()
        self.root.after(200, self._tick)

    def refresh(self) -> None:
        self._show_passage()
        self._show_context()
        self._show_pinyin()
        self._show_stats()
        self._show_chrome()
        self._place_pinyin_under_current()

    def _begin_fine_timer(self) -> None:
        if sys.platform != "win32" or self._timer_open:
            return
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
            self._timer_open = True
        except (AttributeError, OSError):
            self._timer_open = False

    def _end_fine_timer(self) -> None:
        if not self._timer_open:
            return
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except (AttributeError, OSError):
            pass
        self._timer_open = False

    def _fitted_text_height(self, text: str) -> int:
        saved_lines = int(self.text.cget("height"))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        measured = self._fit_text_height()
        self._show_passage()
        self.text.configure(height=saved_lines)
        self.text.update_idletasks()
        return measured

    def _settle_lyrics(self) -> None:
        side = getattr(self, "_scroll_side", None)
        if side is None:
            self._show_context()
            return
        self._show_passage()
        self._place_lyric(self.text, 0)
        self._place_neighbor(self.prev_label, self._neighbor(-1), -side)
        self._place_neighbor(self.next_label, self._neighbor(1), side)

    def _line_px(self, text: str, font: tuple) -> int:
        self.rise_label.configure(text=text, font=font)
        self.rise_label.update_idletasks()
        return max(1, self.rise_label.winfo_reqheight())

    def _hide_fade_image(self) -> None:
        for name in ("_fade_image", "_in_image"):
            item = getattr(self, name)
            try:
                self.fade_canvas.itemconfigure(item, image="", state="hidden")
            except tk.TclError:
                replacement = self.fade_canvas.create_image(
                    0, 0, anchor="center", state="hidden"
                )
                setattr(self, name, replacement)
        self._fade_photo = None
        self._in_photo = None
        self._fade_src = None
        self._in_src = None
        self._fade_scaled_size = None
        self._in_scaled_size = None

    def _show_shrink_frame(self, scale: float, y: int, incoming: bool = False) -> None:
        from PIL import Image, ImageTk

        src = self._in_src if incoming else self._fade_src
        size_name = "_in_scaled_size" if incoming else "_fade_scaled_size"
        photo_name = "_in_photo" if incoming else "_fade_photo"
        item = self._in_image if incoming else self._fade_image
        width = max(1, round(src.width * scale))
        height = max(1, round(src.height * scale))
        if (width, height) != getattr(self, size_name):
            resized = src.resize((width, height), Image.Resampling.BILINEAR)
            photo = ImageTk.PhotoImage(resized)
            setattr(self, photo_name, photo)
            setattr(self, size_name, (width, height))
            self.fade_canvas.itemconfigure(item, image=photo, state="normal")
        x = max(self.fade_canvas.winfo_width(), 1) / 2
        origin = max(self.fade_canvas.winfo_height(), 1) / 2 + y
        self.fade_canvas.coords(item, x, origin)

    def _move_fade(self, large_y: int, small_y: int) -> None:
        x = max(self.fade_canvas.winfo_width(), 1) / 2
        origin = max(self.fade_canvas.winfo_height(), 1) / 2
        self.fade_canvas.coords(self._fade_large, x, origin + large_y)
        self.fade_canvas.coords(self._fade_small, x, origin + small_y)

    def _place_lyric(self, widget: tk.Widget, y: int) -> None:
        widget.place(relx=0.5, rely=0.5, anchor="center", y=y, relwidth=0.9)

    def _on_first_map(self, event: tk.Event) -> None:
        if event.widget is not self.root or self._lyric_animating:
            return
        self.root.after_idle(self._relayout_visible)

    def _relayout_visible(self) -> None:
        if self._lyric_animating:
            return
        if self._library_open or self._settings_open:
            return
        self.refresh()

    def _fit_text_height(self) -> int:
        self.text.update_idletasks()
        if self.text.winfo_width() < 80:
            if int(self.text.cget("height")) != 1:
                self.text.configure(height=1)
            return max(self.text.winfo_reqheight(), 1)
        lines = 1
        while lines < 8:
            if int(self.text.cget("height")) != lines:
                self.text.configure(height=lines)
            self.text.update_idletasks()
            if self.text.dlineinfo("end-1c"):
                break
            lines += 1
        return max(self.text.winfo_reqheight(), 1)

    def _show_context(self) -> None:
        if self._lyric_animating:
            return
        self.text.configure(font=self.font_passage)
        self._layout_rest()

    def _layout_rest(self) -> None:
        text_h = self._fit_text_height()
        side = self._side_offset(text_h)
        self._place_lyric(self.text, 0)
        self._place_neighbor(self.prev_label, self._neighbor(-1), -side)
        self._place_neighbor(self.next_label, self._neighbor(1), side)

    def _side_offset(self, text_h: int) -> int:
        return text_h // 2 + 80

    def _place_neighbor(self, label: tk.Label, text: str, y: int) -> None:
        label.configure(text=text, font=self.font_context, fg=self._muted)
        if text:
            self._place_lyric(label, y)
            return
        if label.winfo_manager():
            label.place_forget()

    def _scroll_lyrics(self, old_prev: str, old_current: str) -> None:
        self._cancel_lyric()
        self.text.configure(font=self.font_passage)
        text_h = self._fit_text_height()
        self._scroll_side = self._side_offset(text_h)
        side = self._scroll_side
        self.leave_label.configure(text=old_prev, fg=self._muted, font=self.font_context)
        if self.rise_label.winfo_manager():
            self.rise_label.place_forget()
        if self.rise_small.winfo_manager():
            self.rise_small.place_forget()
        self._fade_width = max(int(self.fade_canvas.winfo_width() * 0.9), 200)
        self._fade_size = self.font_passage[1]
        self._in_fade_size = self.font_context[1]
        self._fade_src = None
        self._in_src = None
        self._hide_fade_image()
        self.fade_canvas.itemconfigure(
            self._fade_large,
            text=old_current,
            font=self.font_passage,
            fill=self._done,
            width=self._fade_width,
            state="normal",
        )
        self.fade_canvas.itemconfigure(
            self._fade_small,
            text=self.passage.text,
            font=self.font_context,
            fill=self._pending,
            width=self._fade_width,
            state="normal",
        )
        self._move_fade(0, side)
        self._begin_fine_timer()
        if self.prev_label.winfo_manager():
            self.prev_label.place_forget()
        if self.pinyin_row.winfo_manager():
            self.pinyin_row.place_forget()
        if old_prev:
            self._place_lyric(self.leave_label, -side)
        elif self.leave_label.winfo_manager():
            self.leave_label.place_forget()
        if self.text.winfo_manager():
            self.text.place_forget()
        if self.next_label.cget("text"):
            self._place_lyric(self.next_label, side * 2)
        self._lyric_animating = True
        self._lyric_started = time.perf_counter()
        self._lyric_job = self.root.after(self._frame_delay(), self._lyric_step)

    def _lyric_step(self) -> None:
        duration = 0.52
        elapsed = time.perf_counter() - self._lyric_started
        t = min(1.0, elapsed / duration)
        eased = t * t * (3 - 2 * t)
        side = self._scroll_side
        if self.leave_label.cget("text"):
            self.leave_label.place_configure(y=int(-side * (1 + eased)))
        y = int(-side * eased)
        incoming_y = int(side * (1 - eased))
        large_size = self.font_passage[1]
        small_size = self.font_context[1]
        out_size = max(small_size, round(large_size + (small_size - large_size) * eased))
        in_size = max(small_size, round(small_size + (large_size - small_size) * eased))
        if out_size != self._fade_size:
            self._fade_size = out_size
            self.fade_canvas.itemconfigure(
                self._fade_large,
                font=(self.font_passage[0], out_size),
            )
        if in_size != self._in_fade_size:
            self._in_fade_size = in_size
            self.fade_canvas.itemconfigure(
                self._fade_small,
                font=(self.font_context[0], in_size),
            )
        self.fade_canvas.itemconfigure(
            self._fade_large, fill=_mix_color(self._done, self._muted, eased)
        )
        self._move_fade(y, incoming_y)
        if self.text.winfo_manager():
            self.text.place_configure(y=int(side * (1 - eased)))
        if self.next_label.cget("text"):
            self.next_label.place_configure(y=int(side * (2 - eased)))
        if t >= 1:
            self._cancel_lyric(snap=True)
            self._place_pinyin_under_current()
            return
        self._lyric_job = self.root.after(self._frame_delay(), self._lyric_step)

    def _cancel_lyric(self, snap: bool = False) -> None:
        if self._lyric_job is not None:
            self.root.after_cancel(self._lyric_job)
            self._lyric_job = None
        self._lyric_animating = False
        if self.leave_label.winfo_manager():
            self.leave_label.place_forget()
        if self.rise_label.winfo_manager():
            self.rise_label.place_forget()
        if self.rise_small.winfo_manager():
            self.rise_small.place_forget()
        self.fade_canvas.itemconfigure(self._fade_large, state="hidden")
        self.fade_canvas.itemconfigure(self._fade_small, state="hidden")
        self._hide_fade_image()
        self._end_fine_timer()
        self.text.configure(font=self.font_passage)
        if snap:
            self._settle_lyrics()

    def _show_chrome(self) -> None:
        mode = self.passage.mode
        self._paint_mode(self.english_button, mode == "en")
        self._paint_mode(self.chinese_button, mode == "zh")
        if self._library_open or self._settings_open:
            self.segment_var.set("")
        else:
            self.segment_var.set(self._place_text())
        if self._note:
            self.status_var.set(self._note)
        elif self.session.finished:
            self.status_var.set("完成")
        else:
            self.status_var.set("")

    def _paint_mode(self, button: tk.Button, selected: bool) -> None:
        button.configure(
            bg=ACCENT if selected else self._surface,
            fg=ACCENT_FG if selected else self._fg,
        )
        self._apply_icon(button, ACCENT_FG if selected else self._fg)

    def _show_passage(self) -> None:
        shown = "".join(unit.display for unit in self.passage.units)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", shown)
        self.text.tag_add("body", "1.0", "end")
        for index, unit in enumerate(self.passage.units):
            start = f"1.0+{index}c"
            end = f"1.0+{index + 1}c"
            self.text.tag_add(self._tag_for(index, unit.kind), start, end)
        if self.session.index < len(self.passage.units):
            self.text.see(f"1.0+{self.session.index}c")

    def _tag_for(self, index: int, kind: str) -> str:
        if kind == "punct" and not self.session.check_punctuation:
            return "skipped"
        if index < self.session.index:
            return "done"
        if index == self.session.index:
            return "error" if self.session.error else "current"
        return "pending"

    def _show_pinyin(self) -> None:
        unit = self.session.current_unit()
        if self.session.error and self.session.wrong and unit is not None:
            expected = ""
            if len(self.session.typed) < len(unit.keys):
                expected = _key_name(unit.keys[len(self.session.typed)])
            self.pinyin_typed.configure(
                text=f"按了 {_key_name(self.session.wrong)}，应为 {expected}",
                fg=ERROR,
            )
            self.pinyin_rest.configure(text="")
            self._place_pinyin_under_current()
            return
        typed = ""
        rest = ""
        typed_color = DONE
        rest_color = MUTED
        if unit is not None and unit.kind == "punct" and unit.display != unit.keys:
            typed = self.session.typed
            rest = unit.keys[len(self.session.typed) :]
            if self.session.error and typed:
                typed_color = ERROR
            else:
                typed_color = ACCENT
            rest_color = ACCENT
            if not typed:
                typed = rest
                rest = ""
        elif (
            self.passage.mode == "zh"
            and unit is not None
            and unit.kind == "hanzi"
        ):
            typed = self.session.typed
            if self.show_pinyin.get():
                rest = unit.keys[len(self.session.typed) :]
            if self.session.error and typed:
                typed_color = ERROR
        self.pinyin_typed.configure(
            text=typed if typed else " ",
            fg=typed_color,
        )
        self.pinyin_rest.configure(text=rest, fg=rest_color)
        self._place_pinyin_under_current()

    def _place_pinyin_under_current(self) -> None:
        typed = (self.pinyin_typed.cget("text") or "").strip()
        rest = (self.pinyin_rest.cget("text") or "").strip()
        if not typed and not rest:
            if self.pinyin_row.winfo_manager():
                self.pinyin_row.place_forget()
            return
        self.text.update_idletasks()
        bbox = None
        if self.session.index < len(self.passage.units):
            bbox = self.text.bbox(f"1.0+{self.session.index}c")
        parent = self.text.master
        if bbox is None or parent.winfo_width() < 2 or parent.winfo_height() < 2:
            if self.pinyin_row.winfo_manager():
                self.pinyin_row.place_forget()
            return
        text_y = int(float(self.text.place_info().get("y") or 0))
        text_left = parent.winfo_width() / 2 - self.text.winfo_width() / 2
        text_top = parent.winfo_height() / 2 + text_y - self.text.winfo_height() / 2
        x = text_left + bbox[0] + bbox[2] / 2
        y = text_top + bbox[1] + bbox[3] + 4
        self.pinyin_row.place_forget()
        self.pinyin_row.place(x=int(x), y=int(y), anchor="n")

    def _capture_score(self) -> None:
        if not hasattr(self, "session") or self.session.started_at is None:
            return
        self._last_score = (
            self.session.speed(),
            self.session.accuracy,
            self.session.errors,
            self.passage.mode,
        )

    def _show_stats(self) -> None:
        if self.session.started_at is None and self._last_score is not None:
            value, accuracy, errors, mode = self._last_score
            self._write_stats(value, accuracy, errors, mode, previous=True)
            return
        elapsed = 0.0
        if self.session.started_at is not None:
            end = (
                self.session.finished_at
                if self.session.finished and self.session.finished_at is not None
                else time.perf_counter()
            )
            elapsed = end - self.session.started_at
        value = self.session.speed()
        if not self.session.finished and 0 < elapsed < 0.5:
            value = 0.0
        self._write_stats(
            value,
            self.session.accuracy,
            self.session.errors,
            self.passage.mode,
            previous=False,
        )

    def _write_stats(
        self,
        value: float,
        accuracy: float,
        errors: int,
        mode: str,
        previous: bool,
    ) -> None:
        if mode == "en":
            speed = f"{round(value)} WPM"
        else:
            speed = f"{round(value)} 字/分钟"
        line = f"{speed} · {round(accuracy)}% · 错误 {errors}"
        if previous:
            line = f"上一句 {line}"
        self.stats_var.set(line)


def _read_progress() -> dict | None:
    try:
        data = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _shrink_scales(
    root: tk.Tk, render_px: int, passage_font: tuple, context_font: tuple
) -> tuple[float, float]:
    from tkinter import font as tkfont

    try:
        from PIL import ImageFont

        ink = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", render_px).getlength("字")
    except (ImportError, OSError):
        ink = float(render_px)
    if ink <= 0:
        ink = float(render_px)
    passage = tkfont.Font(root, font=passage_font).measure("字")
    context = tkfont.Font(root, font=context_font).measure("字")
    return passage / ink, context / ink


def _luminance(color: str) -> float:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return (red * 299 + green * 587 + blue * 114) / 1000


def _normalize_hex(value: str) -> str | None:
    text = value.strip().lower()
    if not text:
        return None
    if not text.startswith("#"):
        text = "#" + text
    if len(text) == 4:
        text = "#" + "".join(char * 2 for char in text[1:])
    if len(text) != 7:
        return None
    try:
        int(text[1:], 16)
    except ValueError:
        return None
    return text


def _font_px(root: tk.Tk, spec: tuple) -> int:
    from tkinter import font as tkfont

    font = tkfont.Font(root, font=spec)
    size = int(font.cget("size"))
    if size < 0:
        return abs(size)
    return max(1, round(abs(size) * root.winfo_fpixels("1i") / 72))


def _render_shrink_image(text: str, max_width: int, render_px: int, passage_px: int):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", render_px)
    except OSError:
        return None
    lines: list[str] = []
    current = ""
    limit = max(max_width * render_px / passage_px, 40)
    for char in text:
        trial = current + char
        if current and font.getlength(trial) > limit:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    if not lines:
        return None
    probe = font.getbbox("字")
    line_height = probe[3] - probe[1] + 12
    width = max(int(font.getlength(line)) for line in lines) + 8
    image = Image.new("RGB", (width, line_height * len(lines)), (26, 27, 38))
    draw = ImageDraw.Draw(image)
    y = 0
    for line in lines:
        draw.text((4, y), line, font=font, fill=(230, 232, 238))
        y += line_height
    return image


def _round_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


def _cover_lines(title: str) -> str:
    text = title.strip() or "未命名"
    lines = []
    rest = text
    while rest and len(lines) < 4:
        lines.append(rest[:6])
        rest = rest[6:]
    if rest and lines:
        lines[-1] = lines[-1][:5] + "…"
    return "\n".join(lines)


def _mix_color(start: str, end: str, amount: float) -> str:
    def channel(index: int) -> int:
        left = int(start[index : index + 2], 16)
        right = int(end[index : index + 2], 16)
        return int(left + (right - left) * amount)

    return f"#{channel(1):02x}{channel(3):02x}{channel(5):02x}"


def _key_name(char: str) -> str:
    if char == " ":
        return "空格"
    return char


def _as_index(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def main() -> None:
    _enable_dpi()
    _configure_logging()
    root = tk.Tk()
    root.report_callback_exception = _report_error
    try:
        App(root)
    except Exception:
        _report_error(*sys.exc_info())
        root.destroy()
        return
    root.mainloop()


def _configure_logging() -> None:
    import logging

    logging.basicConfig(
        filename=log_path(),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def _report_error(exc_type, exc, tb) -> None:
    import logging
    import traceback

    if exc_type is None:
        return
    logging.error("".join(traceback.format_exception(exc_type, exc, tb)))
    try:
        from tkinter import messagebox

        messagebox.showerror(APP_NAME, "出现了一个问题。详情已写入日志，练习可以继续或重新打开。")
    except tk.TclError:
        return


if __name__ == "__main__":
    main()
