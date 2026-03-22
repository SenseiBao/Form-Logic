from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from lift_tracker.profile import (
    GOAL_CHOICES,
    TrainingGoal,
    UserProfile,
    cm_to_inches,
    inches_to_cm,
    kg_to_lbs,
    lbs_to_kg,
)
from ui import theme
from ui.components import RoundedPanel
from ui.profile_store import load_profile


class SettingsView(tk.Frame):
    """Edit profile (imperial display); save or full reset + onboarding."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str = theme.APP_SURFACE,
        on_save: Callable[[UserProfile], None],
        on_reset: Callable[[], None],
    ) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self._on_save = on_save
        self._on_reset = on_reset

        tk.Label(
            self,
            text="Settings",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=bg,
        ).pack(anchor="w", padx=28, pady=(16, 8))

        card = RoundedPanel(
            self,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
        )
        card.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 16))

        inner = card.body()
        wrap = tk.Frame(inner, bg=theme.CARD_WHITE, highlightthickness=0, bd=0)
        wrap.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self._first_name_var = tk.StringVar()
        self._height_in = tk.StringVar()
        self._body_weight_lb = tk.StringVar()
        self._goal_label = tk.StringVar(value=GOAL_CHOICES[0][0])

        self._row_entry(wrap, "First name", self._first_name_var)
        self._row_entry(wrap, "Height (inches)", self._height_in)
        self._row_entry(wrap, "Weight (lbs)", self._body_weight_lb)

        tk.Label(wrap, text="Goal", font=theme.FONT_SUB, fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w").pack(
            fill=tk.X, pady=(12, 4)
        )
        self._goal_cb = ttk.Combobox(
            wrap,
            textvariable=self._goal_label,
            values=[x[0] for x in GOAL_CHOICES],
            state="readonly",
            font=theme.FONT_BODY,
            width=28,
            style="Home.TCombobox",
        )
        self._goal_cb.pack(fill=tk.X, pady=(0, 8))

        self._status = tk.Label(wrap, text="", font=theme.FONT_SMALL, fg=theme.ACCENT_NAV_ACTIVE, bg=theme.CARD_WHITE)
        self._status.pack(anchor="w", pady=(4, 0))

        self._err = tk.Label(wrap, text="", font=theme.FONT_SMALL, fg="#DC2626", bg=theme.CARD_WHITE)
        self._err.pack(anchor="w", pady=(2, 0))

        btn_row = tk.Frame(wrap, bg=theme.CARD_WHITE)
        btn_row.pack(fill=tk.X, pady=(20, 0))

        tk.Button(
            btn_row,
            text="Save changes",
            font=theme.FONT_CTA,
            command=self._submit_save,
            bg=theme.ACCENT_NAV_ACTIVE,
            fg="#FFFFFF",
            activebackground="#6D28D9",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_row,
            text="Reset all data…",
            font=theme.FONT_SUB,
            command=self._on_reset,
            bg="#FEE2E2",
            fg="#991B1B",
            activebackground="#FECACA",
            activeforeground="#7F1D1D",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        self.refresh_from_profile()

    def _row_entry(self, parent: tk.Frame, caption: str, var: tk.StringVar) -> None:
        tk.Label(parent, text=caption, font=theme.FONT_SUB, fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w").pack(
            fill=tk.X, pady=(10, 4)
        )
        e = tk.Entry(
            parent,
            textvariable=var,
            font=theme.FONT_BODY,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
        )
        e.pack(fill=tk.X, ipady=4)

    def refresh_from_profile(self) -> None:
        self._err.config(text="")
        self._status.config(text="")
        p = load_profile()
        if not p:
            self._first_name_var.set("")
            self._height_in.set("")
            self._body_weight_lb.set("")
            self._goal_label.set(GOAL_CHOICES[0][0])
            return
        self._first_name_var.set(p.first_name)
        hi = cm_to_inches(p.height_cm)
        wl = kg_to_lbs(p.weight_kg)
        self._height_in.set("" if hi is None else str(hi))
        self._body_weight_lb.set("" if wl is None else str(wl))
        label = GOAL_CHOICES[0][0]
        if p.goal:
            for gl, ge in GOAL_CHOICES:
                if ge == p.goal:
                    label = gl
                    break
        self._goal_label.set(label)

    def _submit_save(self) -> None:
        name = (self._first_name_var.get() or "").strip()
        if not name:
            self._err.config(text="Please enter your first name.")
            self._status.config(text="")
            return

        hi = self._parse_float(self._height_in.get())
        wl = self._parse_float(self._body_weight_lb.get())
        goal: Optional[TrainingGoal] = None
        glabel = self._goal_label.get()
        for gl, ge in GOAL_CHOICES:
            if gl == glabel:
                goal = ge
                break

        profile = UserProfile(
            first_name=name,
            height_cm=inches_to_cm(hi),
            weight_kg=lbs_to_kg(wl),
            goal=goal,
        )
        self._err.config(text="")
        self._status.config(text="Saved.")
        self._on_save(profile)

    @staticmethod
    def _parse_float(s: str) -> Optional[float]:
        s = (s or "").strip()
        if not s:
            return None
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None
