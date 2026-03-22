from __future__ import annotations

from typing import Any, Callable, Dict, List

import tkinter as tk

from lift_tracker.form_feedback import form_suggestions_for_set

from ui import theme
from ui.components import RoundedPanel, ScrollableFrame


def _format_stats_line(m: Dict[str, Any]) -> str:
    parts: List[str] = []
    if "total_reps" in m:
        parts.append(f"reps {m['total_reps']}")
    if "avg_rep_duration_s" in m:
        parts.append(f"avg {m['avg_rep_duration_s']} s")
    if "avg_depth_pct" in m:
        parts.append(f"depth {m['avg_depth_pct']}%")
    if "avg_conc_depth_pct" in m:
        parts.append(f"conc {m['avg_conc_depth_pct']}%")
    if "avg_ecc_depth_pct" in m:
        parts.append(f"ecc {m['avg_ecc_depth_pct']}%")
    return " · ".join(parts) if parts else ""


def _exercise_title(log_entry: Dict[str, Any]) -> str:
    disp = log_entry.get("exercise_display")
    if isinstance(disp, str) and disp.strip():
        return disp.strip()
    ex = str(log_entry.get("exercise", "?"))
    return ex.replace("_", " ").title()


class SessionSummaryView(tk.Frame):
    """Full main-area session summary (stats + form coaching)."""

    def __init__(self, parent: tk.Misc, *, bg: str = theme.APP_SURFACE) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self._on_done: Callable[[], None] = lambda: None

    def present(self, log_entry: Dict[str, Any], *, on_done: Callable[[], None]) -> None:
        self._on_done = on_done
        for w in self.winfo_children():
            w.destroy()

        pad = self._bg
        outer = tk.Frame(self, bg=pad, highlightthickness=0, bd=0)
        outer.pack(fill=tk.BOTH, expand=True, padx=28, pady=(8, 16))

        tk.Label(
            outer,
            text="Session summary",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=pad,
        ).pack(anchor="w", pady=(0, 4))

        ts = str(log_entry.get("timestamp", ""))
        title = _exercise_title(log_entry)
        sub = f"{title}" + (f" · {ts}" if ts else "")
        tk.Label(
            outer,
            text=sub,
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=pad,
            wraplength=860,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 16))

        card = RoundedPanel(
            outer,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=theme.GLASS_FILL_RGBA[3],
            expand_fill=True,
        )
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        body = card.body()

        inner_pad = theme.CARD_WHITE
        block = tk.Frame(body, bg=inner_pad, highlightthickness=0, bd=0)
        block.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        lw = log_entry.get("lift_weight_lbs")
        if lw is not None:
            try:
                wv = float(lw)
                wtxt = f"{int(wv)} lb" if wv == int(wv) else f"{wv:g} lb"
                tk.Label(
                    block,
                    text=f"Weight: {wtxt}",
                    font=theme.FONT_BODY,
                    fg=theme.TEXT_PRIMARY,
                    bg=inner_pad,
                ).pack(anchor="w", pady=(0, 12))
            except (TypeError, ValueError):
                pass

        metrics = log_entry.get("metrics") if isinstance(log_entry.get("metrics"), dict) else {}
        stat_line = _format_stats_line(metrics)
        tk.Label(
            block,
            text="Stats",
            font=theme.FONT_SUB,
            fg=theme.TEXT_PRIMARY,
            bg=inner_pad,
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            block,
            text=stat_line if stat_line else "No metrics captured.",
            font=theme.FONT_BODY,
            fg=theme.TEXT_PRIMARY,
            bg=inner_pad,
            wraplength=820,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 16))

        ex_id = str(log_entry.get("exercise", ""))
        tips: List[str] = form_suggestions_for_set(ex_id, metrics)

        tk.Label(
            block,
            text="Form coaching",
            font=theme.FONT_SUB,
            fg=theme.TEXT_PRIMARY,
            bg=inner_pad,
        ).pack(anchor="w", pady=(0, 6))

        scroll = ScrollableFrame(block, bg=inner_pad)
        scroll.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        s_inner = scroll.body()

        def _wheel(e: tk.Event) -> str | None:
            return scroll.on_mousewheel(e)

        cav = getattr(scroll, "_canvas", None)
        if cav is not None:
            cav.bind("<MouseWheel>", _wheel)
            cav.bind("<Button-4>", _wheel)
            cav.bind("<Button-5>", _wheel)

        wrap = 800
        if not tips:
            tk.Label(
                s_inner,
                text="No major form flags for this set — solid work.",
                font=theme.FONT_BODY,
                fg=theme.TEXT_MUTED,
                bg=inner_pad,
                wraplength=wrap,
                justify=tk.LEFT,
            ).pack(anchor="w", padx=2, pady=4)
        else:
            for i, line in enumerate(tips):
                tk.Label(
                    s_inner,
                    text=f"• {line}",
                    font=theme.FONT_BODY,
                    fg=theme.TEXT_PRIMARY,
                    bg=inner_pad,
                    wraplength=wrap,
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(anchor="w", padx=2, pady=(0, 10 if i < len(tips) - 1 else 4))

        btn_row = tk.Frame(outer, bg=pad, highlightthickness=0, bd=0)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            btn_row,
            text="Done",
            font=theme.FONT_BODY,
            command=self._finish,
            relief=tk.FLAT,
            bg=theme.CARD_WHITE,
            fg=theme.TEXT_PRIMARY,
            padx=28,
            pady=10,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=theme.CARD_BORDER,
        ).pack(side=tk.RIGHT)

    def _finish(self) -> None:
        self.pack_forget()
        cb = self._on_done
        self._on_done = lambda: None
        cb()
