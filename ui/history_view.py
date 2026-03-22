from __future__ import annotations

import json
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, Dict, List

from ui import theme
from ui.components import RoundedPanel, ScrollableFrame
from ui.paths import HISTORY_JSON


def load_history() -> List[Dict[str, Any]]:
    if not HISTORY_JSON.exists():
        return []
    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def group_by_day(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_day: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        ts = e.get("timestamp", "")
        if not isinstance(ts, str) or len(ts) < 10:
            continue
        day_key = ts[:10]
        try:
            datetime.strptime(day_key, "%Y-%m-%d")
        except ValueError:
            continue
        by_day[day_key].append(e)
    ordered = sorted(by_day.keys(), reverse=True)
    return {d: by_day[d] for d in ordered}


def _fmt_metrics(m: Dict[str, Any]) -> str:
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


class HistoryView(tk.Frame):
    def __init__(self, parent: tk.Misc, *, bg: str = theme.APP_SURFACE) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg

        tk.Label(
            self,
            text="History",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=bg,
        ).pack(anchor="w", padx=28, pady=(16, 8))

        self._scroll = ScrollableFrame(self, bg=bg)
        self._scroll.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._scroll._canvas.bind(seq, self._on_wheel)  # type: ignore[attr-defined]

        self._inner = self._scroll.body()
        self._rows: List[tk.Misc] = []

    def _on_wheel(self, event: tk.Event) -> str | None:
        return self._scroll.on_mousewheel(event)

    def refresh(self) -> None:
        for w in self._rows:
            w.destroy()
        self._rows.clear()

        entries = load_history()
        grouped = group_by_day(entries)
        if not grouped:
            lbl = tk.Label(
                self._inner,
                text="No workouts logged yet.",
                font=theme.FONT_BODY,
                fg=theme.TEXT_MUTED,
                bg=self._bg,
            )
            lbl.pack(anchor="w", pady=24)
            self._rows.append(lbl)
            return

        for day_key, sessions in grouped.items():
            try:
                dt = datetime.strptime(day_key, "%Y-%m-%d")
                day_title = dt.strftime("%A, %B %d, %Y")
            except ValueError:
                day_title = day_key

            day_rp = RoundedPanel(
                self._inner,
                radius=theme.CORNER_RADIUS_LG,
                fill_rgb=(255, 255, 255),
                fill_alpha=theme.GLASS_FILL_RGBA[3],
                expand_fill=False,
            )
            day_rp.pack(fill=tk.X, pady=(0, 14))
            self._rows.append(day_rp)
            day_frame = day_rp.body()

            tk.Label(
                day_frame,
                text=day_title,
                font=theme.FONT_HEADING,
                fg=theme.TEXT_PRIMARY,
                bg=theme.CARD_WHITE,
            ).pack(anchor="w", padx=16, pady=(12, 8))

            for sess in sessions:
                ex = str(sess.get("exercise", "?"))
                ts_full = str(sess.get("timestamp", ""))
                time_part = ts_full[11:] if len(ts_full) > 11 else ts_full
                metrics = sess.get("metrics") if isinstance(sess.get("metrics"), dict) else {}
                line = f"{time_part} — {ex.replace('_', ' ').title()}"
                lw = sess.get("lift_weight_lbs")
                if lw is not None:
                    try:
                        wv = float(lw)
                        if wv == int(wv):
                            line += f" · {int(wv)} lb"
                        else:
                            line += f" · {wv:g} lb"
                    except (TypeError, ValueError):
                        pass
                detail = _fmt_metrics(metrics)

                row = tk.Frame(day_frame, bg=theme.CARD_WHITE, highlightthickness=0, bd=0)
                row.pack(fill=tk.X, padx=12, pady=(0, 8))

                tk.Label(
                    row,
                    text=line,
                    font=theme.FONT_BODY,
                    fg=theme.TEXT_PRIMARY,
                    bg=theme.CARD_WHITE,
                    anchor="w",
                ).pack(anchor="w", padx=8)
                if detail:
                    tk.Label(
                        row,
                        text=detail,
                        font=theme.FONT_SMALL,
                        fg=theme.TEXT_MUTED,
                        bg=theme.CARD_WHITE,
                        anchor="w",
                    ).pack(anchor="w", padx=8, pady=(2, 8))
                else:
                    tk.Frame(row, height=8, bg=theme.CARD_WHITE).pack()

            tk.Frame(day_frame, height=8, bg=theme.CARD_WHITE).pack()
            day_rp.after_idle(day_rp.fit_hug)
