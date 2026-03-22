from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Tuple

from ui import theme
from ui.components import PillButton, RoundedPanel


ExerciseChoice = Tuple[str, str]  # (display, internal key)


class HomeView(tk.Frame):
    """Home tab: greeting and workout card layout."""

    EXERCISES: List[ExerciseChoice] = [
        ("Squat", "squat"),
        ("Bicep Curl", "bicep_curl"),
        ("Pull-up", "pullup"),
    ]

    def __init__(
        self,
        parent: tk.Misc,
        *,
        user_name: str = "Andrew",
        on_begin: Callable[[str, int], None],
        bg: str = theme.APP_SURFACE,
    ) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self.user_name = user_name
        self._on_begin = on_begin

        self.exercise_var = tk.StringVar(value=self.EXERCISES[0][0])
        self.reps_var = tk.StringVar(value="4")

        header = tk.Frame(self, bg=bg, highlightthickness=0, bd=0)
        header.pack(fill=tk.X, padx=28, pady=(20, 8))

        self._date_lbl = tk.Label(header, font=theme.FONT_SUB, fg=theme.TEXT_PRIMARY, bg=bg, anchor="w")
        self._date_lbl.pack(anchor="w")
        self._greet_lbl = tk.Label(header, font=theme.FONT_TITLE, fg=theme.TEXT_PRIMARY, bg=bg, anchor="w")
        self._greet_lbl.pack(anchor="w", pady=(4, 0))
        tk.Label(
            header,
            text="Today's a great day to get moving.",
            font=theme.FONT_SMALL,
            fg=theme.ACCENT_PURPLE,
            bg=bg,
            anchor="w",
        ).pack(anchor="w", pady=(8, 0))

        self._refresh_greeting()

        body = tk.Frame(self, bg=bg, highlightthickness=0, bd=0)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

        body.grid_columnconfigure(0, weight=1, uniform="col")
        body.grid_columnconfigure(1, weight=1, uniform="col")
        body.grid_rowconfigure(0, weight=1)

        glass = dict(radius=theme.CORNER_RADIUS_LG, fill_rgb=(255, 255, 255), fill_alpha=theme.GLASS_FILL_RGBA[3])
        left_card = RoundedPanel(body, **glass)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=4)
        right_col = tk.Frame(body, bg=bg, highlightthickness=0, bd=0)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=4)
        right_col.grid_rowconfigure(1, weight=1)

        today_card = RoundedPanel(right_col, **glass)
        today_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        stats_card = RoundedPanel(right_col, **glass)
        stats_card.grid(row=1, column=0, sticky="nsew")

        self._build_workout_card(left_card.body())
        self._build_today_card(today_card.body())
        self._build_stats_placeholder(stats_card.body())

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
        ).pack(pady=(24, 16))

        ttk.Combobox(
            f,
            textvariable=self.exercise_var,
            values=[x[0] for x in self.EXERCISES],
            state="readonly",
            font=theme.FONT_BODY,
            width=22,
        ).pack(pady=8, padx=32)

        ttk.Combobox(
            f,
            textvariable=self.reps_var,
            values=[str(i) for i in range(1, 21)],
            state="readonly",
            font=theme.FONT_BODY,
            width=22,
        ).pack(pady=8, padx=32)

        wrap = tk.Frame(f, bg=theme.CARD_WHITE)
        wrap.pack(pady=(20, 32))
        begin = PillButton(
            wrap,
            "Begin",
            self._handle_begin,
            width=160,
            height=48,
            fill=theme.CARD_WHITE,
            text_color=theme.TEXT_PRIMARY,
            font=theme.FONT_CTA,
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
        tk.Label(
            f,
            text="Focus on controlled tempo and full range of motion. "
            "Side profile works best for squats and curls; back to camera for pull-ups.",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 20))

    def _build_stats_placeholder(self, f: tk.Frame) -> None:
        tk.Label(
            f,
            text="Your stats",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w", padx=20, pady=(16, 8))
        tk.Label(
            f,
            text="Recovery and workout rings will live here soon.",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 24))

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
        self._on_begin(key, n)
