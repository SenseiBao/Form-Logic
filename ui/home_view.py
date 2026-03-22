from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Tuple

from ui import theme
from ui.components import GradientPillButton, RoundedPanel


ExerciseChoice = Tuple[str, str]  # (display, internal key)


class HomeView(tk.Frame):
    """Home tab: greeting strip, lavender body, glass cards (mockup-aligned)."""

    EXERCISES: List[ExerciseChoice] = [
        ("Squat", "squat"),
        ("Bicep Curl", "bicep_curl"),
        ("Pull-up", "pullup"),
    ]

    def __init__(
        self,
        parent: tk.Misc,
        *,
        user_name: str = "there",
        on_begin: Callable[[str, int, Optional[float]], None],
        bg: str = theme.APP_SURFACE,
    ) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self.user_name = user_name
        self._on_begin = on_begin

        self.exercise_var = tk.StringVar(value=self.EXERCISES[0][0])
        self.reps_var = tk.StringVar(value="4")
        self.lift_weight_var = tk.StringVar(value="")

        greet_strip = tk.Frame(self, bg=theme.HOME_GREETING_BG, highlightthickness=0, bd=0)
        greet_strip.pack(fill=tk.X)

        header = tk.Frame(greet_strip, bg=theme.HOME_GREETING_BG, highlightthickness=0, bd=0)
        header.pack(fill=tk.X, padx=32, pady=(20, 16))

        self._date_lbl = tk.Label(
            header,
            font=theme.FONT_DATE,
            fg=theme.TEXT_MUTED,
            bg=theme.HOME_GREETING_BG,
            anchor="w",
        )
        self._date_lbl.pack(anchor="w")
        self._greet_lbl = tk.Label(
            header,
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=theme.HOME_GREETING_BG,
            anchor="w",
        )
        self._greet_lbl.pack(anchor="w", pady=(6, 0))
        tk.Label(
            header,
            text="Today's a great day to get moving.",
            font=theme.FONT_SMALL,
            fg=theme.ACCENT_PURPLE,
            bg=theme.HOME_GREETING_BG,
            anchor="w",
        ).pack(anchor="w", pady=(8, 0))

        self._refresh_greeting()

        body = tk.Frame(self, bg=bg, highlightthickness=0, bd=0)
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=(12, 16))
        self.bind("<Configure>", self._on_home_configure)

        body.grid_columnconfigure(0, weight=1, uniform="col")
        body.grid_columnconfigure(1, weight=1, uniform="col")
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        glass = dict(radius=theme.CORNER_RADIUS_LG, fill_rgb=(255, 255, 255), fill_alpha=255)
        left_card = RoundedPanel(body, **glass)
        left_card.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10), pady=2)

        today_card = RoundedPanel(body, **glass)
        today_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(2, 6))
        stats_card = RoundedPanel(body, **glass)
        stats_card.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(6, 2))

        self._build_workout_card(left_card.body())
        self._build_today_card(today_card.body())
        self._build_stats_placeholder(stats_card.body())

    def _on_home_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        w = event.width
        if w < 100:
            return
        col = max(180, (w - 120) // 2)
        wrap = max(160, col - 48)
        if hasattr(self, "_today_body"):
            self._today_body.config(wraplength=wrap)
        if hasattr(self, "_stats_body"):
            self._stats_body.config(wraplength=wrap)

    def set_first_name(self, name: str) -> None:
        self.user_name = name.strip() or "there"
        self._refresh_greeting()

    def _refresh_greeting(self) -> None:
        from datetime import datetime

        now = datetime.now()
        self._date_lbl.config(text=now.strftime("%A, %B %d, %Y"))
        hour = now.hour
        if hour < 12:
            greet = "Good Morning"
        elif hour < 17:
            greet = "Good Afternoon"
        else:
            greet = "Good Evening"
        self._greet_lbl.config(text=f"{greet}, {self.user_name}!")

    def _build_workout_card(self, f: tk.Frame) -> None:
        tk.Label(
            f,
            text="Start A New Workout",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
            anchor="center",
        ).pack(pady=(22, 18), fill=tk.X)

        combo_kw = dict(
            state="readonly",
            font=theme.FONT_BODY,
            width=24,
            style="Home.TCombobox",
        )
        ttk.Combobox(f, textvariable=self.exercise_var, values=[x[0] for x in self.EXERCISES], **combo_kw).pack(
            pady=5, padx=36, fill=tk.X
        )
        ttk.Combobox(
            f,
            textvariable=self.reps_var,
            values=[str(i) for i in range(1, 21)],
            **combo_kw,
        ).pack(pady=5, padx=36, fill=tk.X)

        tk.Label(
            f,
            text="Load (lbs)",
            font=theme.FONT_SUB,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
            anchor="w",
        ).pack(anchor="w", padx=36, pady=(10, 4))
        tk.Label(
            f,
            text="Optional — barbell, dumbbells, kettlebell, etc.",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            anchor="w",
        ).pack(anchor="w", padx=36, pady=(0, 4))
        tk.Entry(
            f,
            textvariable=self.lift_weight_var,
            font=theme.FONT_BODY,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
        ).pack(pady=2, padx=36, fill=tk.X, ipady=4)

        wrap = tk.Frame(f, bg=theme.CARD_WHITE)
        wrap.pack(pady=(16, 22))
        begin = GradientPillButton(
            wrap,
            "Begin",
            self._handle_begin,
            width=200,
            height=54,
            canvas_bg=theme.CARD_WHITE,
        )
        begin.pack()

    def _build_today_card(self, f: tk.Frame) -> None:
        tk.Label(
            f,
            text="Today's Exercise",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w", padx=20, pady=(16, 8))
        self._today_body = tk.Label(
            f,
            text="Focus on controlled tempo and full range of motion. "
            "Side profile works best for squats and curls; back to camera for pull-ups.",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            wraplength=360,
            justify="left",
        )
        self._today_body.pack(anchor="w", padx=20, pady=(0, 16))

    def _build_stats_placeholder(self, f: tk.Frame) -> None:
        tk.Label(
            f,
            text="Your stats",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w", padx=20, pady=(16, 8))
        self._stats_body = tk.Label(
            f,
            text="Recovery and workout rings will live here soon.",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            wraplength=360,
            justify="left",
        )
        self._stats_body.pack(anchor="w", padx=20, pady=(0, 18))

    def _handle_begin(self) -> None:
        key = "squat"
        for disp, k in self.EXERCISES:
            if disp == self.exercise_var.get():
                key = k
                break
        try:
            n = int(self.reps_var.get())
        except ValueError:
            n = 4
        lift = self._parse_optional_lbs(self.lift_weight_var.get())
        self._on_begin(key, n, lift)

    @staticmethod
    def _parse_optional_lbs(s: str) -> Optional[float]:
        s = (s or "").strip()
        if not s:
            return None
        try:
            v = float(s.replace(",", "."))
            return round(v, 2) if v >= 0 else None
        except ValueError:
            return None
