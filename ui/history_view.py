from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, DefaultDict, Dict, List, Optional

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


def entry_key(e: Dict[str, Any]) -> str:
    eid = e.get("id")
    if isinstance(eid, str) and eid.strip():
        return eid.strip()
    ts = e.get("timestamp", "")
    ex = e.get("exercise", "")
    return f"{ts}|{ex}"


def delete_history_entry(key: str) -> bool:
    hist = load_history()
    new = [e for e in hist if entry_key(e) != key]
    if len(new) == len(hist):
        return False
    try:
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(new, f, indent=4)
    except OSError:
        return False
    return True


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


# (label, exercise id or None for all)
_LIFT_FILTER_OPTIONS: List[tuple[str, Optional[str]]] = [
    ("All exercises", None),
    ("Squat", "squat"),
    ("Bicep curl", "bicep_curl"),
    ("Pull-up", "pullup"),
]


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
    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str = theme.APP_SURFACE,
        on_open_session: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self._on_open_session = on_open_session

        tk.Label(
            self,
            text="History",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=bg,
        ).pack(anchor="w", padx=28, pady=(16, 8))

        filter_row = tk.Frame(self, bg=bg, highlightthickness=0, bd=0)
        filter_row.pack(fill=tk.X, padx=28, pady=(0, 8))
        tk.Label(
            filter_row,
            text="Show:",
            font=theme.FONT_BODY,
            fg=theme.TEXT_MUTED,
            bg=bg,
        ).pack(side=tk.LEFT)
        self._lift_filter_label = tk.StringVar(value=_LIFT_FILTER_OPTIONS[0][0])
        self._filter_combo = ttk.Combobox(
            filter_row,
            textvariable=self._lift_filter_label,
            values=[x[0] for x in _LIFT_FILTER_OPTIONS],
            state="readonly",
            width=20,
        )
        self._filter_combo.pack(side=tk.LEFT, padx=(10, 0))
        self._filter_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

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
        sel = self._lift_filter_label.get()
        ex_key = next((k for lab, k in _LIFT_FILTER_OPTIONS if lab == sel), None)
        if ex_key is not None:
            entries = [e for e in entries if e.get("exercise") == ex_key]

        grouped = group_by_day(entries)
        if not grouped:
            empty_msg = (
                "No sessions for this lift yet."
                if ex_key is not None
                else "No workouts logged yet."
            )
            lbl = tk.Label(
                self._inner,
                text=empty_msg,
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

                left = tk.Frame(row, bg=theme.CARD_WHITE, highlightthickness=0, bd=0)
                left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                def _bind_open_summary(w: tk.Misc, s: Dict[str, Any] = sess) -> None:
                    if not self._on_open_session:
                        return
                    w.bind("<Button-1>", lambda _e, entry=s: self._on_open_session(entry))
                    w.configure(cursor="hand2")

                lbl_title = tk.Label(
                    left,
                    text=line,
                    font=theme.FONT_BODY,
                    fg=theme.TEXT_PRIMARY,
                    bg=theme.CARD_WHITE,
                    anchor="w",
                )
                lbl_title.pack(anchor="w", padx=8)
                _bind_open_summary(lbl_title)
                _bind_open_summary(left)
                if detail:
                    lbl_det = tk.Label(
                        left,
                        text=detail,
                        font=theme.FONT_SMALL,
                        fg=theme.TEXT_MUTED,
                        bg=theme.CARD_WHITE,
                        anchor="w",
                    )
                    lbl_det.pack(anchor="w", padx=8, pady=(2, 0))
                    _bind_open_summary(lbl_det)
                else:
                    tk.Frame(left, height=4, bg=theme.CARD_WHITE).pack()

                if self._on_open_session:
                    lbl_hint = tk.Label(
                        left,
                        text="Tap for session summary",
                        font=theme.FONT_SMALL,
                        fg=theme.ACCENT_NAV_ACTIVE,
                        bg=theme.CARD_WHITE,
                        anchor="w",
                    )
                    lbl_hint.pack(anchor="w", padx=8, pady=(2, 4))
                    _bind_open_summary(lbl_hint)

                ek = entry_key(sess)

                def _on_delete(k: str = ek) -> None:
                    if not messagebox.askyesno(
                        "Delete workout?",
                        "Remove this session from history? This cannot be undone.",
                        icon="warning",
                        parent=self.winfo_toplevel(),
                    ):
                        return
                    if delete_history_entry(k):
                        self.refresh()

                del_btn = tk.Label(
                    row,
                    text="Delete",
                    font=theme.FONT_SMALL,
                    fg=theme.ACCENT_NAV_ACTIVE,
                    bg=theme.CARD_WHITE,
                    cursor="hand2",
                )
                del_btn.pack(side=tk.RIGHT, padx=(4, 8), pady=4, anchor="ne")
                del_btn.bind("<Button-1>", lambda _e, fn=_on_delete: fn())

            tk.Frame(day_frame, height=8, bg=theme.CARD_WHITE).pack()
            day_rp.after_idle(day_rp.fit_hug)
