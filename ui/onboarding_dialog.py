from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from PIL import ImageTk

from lift_tracker.profile import GOAL_CHOICES, TrainingGoal, UserProfile, inches_to_cm, lbs_to_kg
from ui import theme


class OnboardingDialog:
    """First-run modal: resizable, scrollable form over full-window gradient (imperial → stored metric)."""

    _FORM_BG = "#5B21B6"

    def __init__(self, parent: tk.Tk, *, on_saved: Callable[[UserProfile], None]) -> None:
        self._parent = parent
        self._on_saved = on_saved
        self._result: Optional[UserProfile] = None
        self.cancelled = False  # True if user closed with X without completing
        self._grad_photo: Optional[ImageTk.PhotoImage] = None
        self._last_grad_size: tuple[int, int] = (0, 0)

        self._top = tk.Toplevel(parent)
        self._top.title("Welcome to FormLogic")
        self._top.transient(parent)
        self._top.grab_set()
        self._top.resizable(True, True)
        self._top.minsize(560, 580)
        self._top.geometry("680x780")

        root = tk.Frame(self._top, highlightthickness=0, bd=0)
        root.pack(fill=tk.BOTH, expand=True)

        self._bg_canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_canvas.bind("<Configure>", self._on_bg_configure)

        # Card + scroll sits above the gradient (same stacking order: packed/placed later = on top)
        self._card = tk.Frame(root, bg=self._FORM_BG, highlightthickness=0, bd=0)
        self._card.place(relx=0.5, rely=0.04, relwidth=0.92, relheight=0.92, anchor="n")

        self._scroll_canvas = tk.Canvas(
            self._card,
            highlightthickness=0,
            bd=0,
            bg=self._FORM_BG,
        )
        self._sb = tk.Scrollbar(self._card, orient=tk.VERTICAL, command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=self._sb.set)

        self._inner = tk.Frame(self._scroll_canvas, bg=self._FORM_BG, highlightthickness=0, bd=0)
        self._inner_win = self._scroll_canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=16)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 12), pady=16)

        self._bind_mousewheel(self._scroll_canvas)
        self._bind_mousewheel(self._inner)
        self._bind_mousewheel(self._card)

        self._name = tk.StringVar()
        self._height_in = tk.StringVar()
        self._weight_lb = tk.StringVar()
        self._goal_label = tk.StringVar(value=GOAL_CHOICES[0][0])

        style = ttk.Style(self._top)
        style.theme_use("clam")
        style.configure(
            "Onboard.TCombobox",
            fieldbackground=theme.CARD_WHITE,
            background=theme.CARD_WHITE,
            foreground=theme.TEXT_PRIMARY,
            arrowcolor=self._FORM_BG,
        )
        style.map(
            "Onboard.TCombobox",
            fieldbackground=[("readonly", theme.CARD_WHITE)],
            selectbackground=[("readonly", theme.CARD_WHITE)],
            selectforeground=[("readonly", theme.TEXT_PRIMARY)],
        )

        self._build_header(self._inner)
        self._build_form(self._inner)

        self._scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)
        self._inner.bind("<Configure>", self._on_inner_configure)

        self._top.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        self._top.update_idletasks()
        self._center_on_parent(parent)
        parent.wait_window(self._top)

    def _bind_mousewheel(self, widget: tk.Misc) -> None:
        def on_wheel(event: tk.Event) -> str | None:
            if self._scroll_canvas.winfo_height() <= 1:
                return None
            if hasattr(event, "delta") and event.delta:
                self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                self._scroll_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self._scroll_canvas.yview_scroll(1, "units")
            return "break"

        widget.bind("<MouseWheel>", on_wheel, add=True)
        widget.bind("<Button-4>", on_wheel, add=True)
        widget.bind("<Button-5>", on_wheel, add=True)

    def _build_header(self, parent: tk.Frame) -> None:
        self._hdr_title = tk.Label(
            parent,
            text="Welcome to FormLogic!",
            font=("Helvetica", 22, "bold"),
            fg="#FFFFFF",
            bg=self._FORM_BG,
            wraplength=400,
            justify="center",
        )
        self._hdr_title.pack(fill=tk.X, pady=(8, 6), padx=8)
        self._hdr_sub = tk.Label(
            parent,
            text="A few details to personalize your sessions.",
            font=("Helvetica", 12),
            fg="#E9D5FF",
            bg=self._FORM_BG,
            wraplength=400,
            justify="center",
        )
        self._hdr_sub.pack(fill=tk.X, pady=(0, 16), padx=8)

    def _build_form(self, parent: tk.Frame) -> None:
        self._field_block(
            parent,
            "Name",
            tk.Entry(parent, textvariable=self._name, font=theme.FONT_BODY),
            caption_pady=(2, 6),
        )
        self._field_block(parent, "Height (inches)", tk.Entry(parent, textvariable=self._height_in, font=theme.FONT_BODY))
        self._field_block(parent, "Weight (lbs)", tk.Entry(parent, textvariable=self._weight_lb, font=theme.FONT_BODY))

        tk.Label(parent, text="Goal", font=theme.FONT_SUB, fg="#F5F3FF", bg=self._FORM_BG, anchor="w").pack(
            fill=tk.X, pady=(14, 6), padx=4
        )
        cb_wrap = tk.Frame(parent, bg=theme.CARD_WHITE, highlightthickness=1, highlightbackground="#DDD6FE")
        cb_wrap.pack(fill=tk.X, padx=4)
        cb = ttk.Combobox(
            cb_wrap,
            textvariable=self._goal_label,
            values=[x[0] for x in GOAL_CHOICES],
            state="readonly",
            font=theme.FONT_BODY,
            style="Onboard.TCombobox",
        )
        cb.pack(fill=tk.X, padx=6, pady=8)

        self._err = tk.Label(
            parent,
            text="",
            font=theme.FONT_SMALL,
            fg="#FECACA",
            bg=self._FORM_BG,
            anchor="w",
            justify="left",
            wraplength=400,
        )
        self._err.pack(fill=tk.X, pady=(14, 4), padx=4)

        btn = tk.Button(
            parent,
            text="Continue",
            font=theme.FONT_CTA,
            command=self._submit,
            bg="#FFFFFF",
            fg=self._FORM_BG,
            activebackground="#F5F3FF",
            activeforeground=self._FORM_BG,
            relief="flat",
            padx=28,
            pady=12,
            cursor="hand2",
        )
        btn.pack(anchor="center", pady=(18, 28))

    def _field_block(
        self,
        parent: tk.Frame,
        caption: str,
        widget: tk.Widget,
        *,
        caption_pady: tuple[int, int] = (10, 6),
    ) -> None:
        tk.Label(parent, text=caption, font=theme.FONT_SUB, fg="#F5F3FF", bg=self._FORM_BG, anchor="w").pack(
            fill=tk.X, pady=caption_pady, padx=4
        )
        box = tk.Frame(parent, bg=theme.CARD_WHITE, highlightthickness=1, highlightbackground="#DDD6FE")
        box.pack(fill=tk.X, padx=4)
        if isinstance(widget, tk.Entry):
            widget.configure(
                relief="flat",
                bd=10,
                bg=theme.CARD_WHITE,
                fg=theme.TEXT_PRIMARY,
                insertbackground=theme.TEXT_PRIMARY,
                highlightthickness=0,
            )
        widget.pack(fill=tk.X, padx=4, pady=4)

    def _on_bg_configure(self, event: tk.Event) -> None:
        if event.widget is not self._bg_canvas:
            return
        w, h = max(2, event.width), max(2, event.height)
        if (w, h) == self._last_grad_size:
            return
        self._last_grad_size = (w, h)
        img = theme.header_banner_gradient(w, h)
        self._grad_photo = ImageTk.PhotoImage(img, master=self._bg_canvas)
        self._bg_canvas.delete("bg")
        self._bg_canvas.create_image(0, 0, anchor="nw", image=self._grad_photo, tags="bg")

    def _on_scroll_canvas_configure(self, event: tk.Event) -> None:
        w = max(1, event.width)
        self._scroll_canvas.itemconfig(self._inner_win, width=w)
        wrap = max(180, w - 32)
        if hasattr(self, "_err"):
            self._err.config(wraplength=wrap)
        self._hdr_title.config(wraplength=wrap)
        self._hdr_sub.config(wraplength=wrap)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _center_on_parent(self, parent: tk.Tk) -> None:
        self._top.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self._top.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self._top.winfo_height()) // 2
        self._top.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _on_close_attempt(self) -> None:
        """Close without saving — user chose to exit setup (caller should quit app if needed)."""
        self.cancelled = True
        try:
            self._top.grab_release()
        except tk.TclError:
            pass
        try:
            self._top.destroy()
        except tk.TclError:
            pass

    def _submit(self) -> None:
        name = (self._name.get() or "").strip()
        if not name:
            self._err.config(text="Please enter your first name.")
            return

        hi = self._parse_float(self._height_in.get())
        wl = self._parse_float(self._weight_lb.get())
        height_cm = inches_to_cm(hi)
        weight_kg = lbs_to_kg(wl)

        goal: Optional[TrainingGoal] = None
        label = self._goal_label.get()
        for gl, ge in GOAL_CHOICES:
            if gl == label:
                goal = ge
                break

        profile = UserProfile(first_name=name, height_cm=height_cm, weight_kg=weight_kg, goal=goal)
        self._result = profile
        self._top.grab_release()
        self._top.destroy()
        self._on_saved(profile)

    @staticmethod
    def _parse_float(s: str) -> Optional[float]:
        s = (s or "").strip()
        if not s:
            return None
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None
