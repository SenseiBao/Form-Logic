from __future__ import annotations

import json
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from lift_tracker.profile import GOAL_CHOICES, TrainingGoal, UserProfile
from ui import theme
from ui.components import RoundedPanel, ScrollableFrame
from ui.paths import HISTORY_JSON
from ui.profile_store import delete_weight_entry, load_profile, load_weight_log, log_weight, save_profile


_EXERCISE_LABELS: Dict[str, str] = {
    "squat": "Squat",
    "bicep_curl": "Bicep Curl",
    "pullup": "Pull-up",
}


# ── Epley helpers ─────────────────────────────────────────────────────────────

def _epley_1rm(weight_lbs: float, reps: int) -> float:
    return weight_lbs * (1.0 + reps / 30.0)


def _session_score(session: Dict[str, Any]) -> Optional[float]:
    """Return Epley 1RM if weighted, raw reps if bodyweight, or None."""
    reps = (session.get("metrics") or {}).get("total_reps", 0)
    if not reps:
        return None
    weight = session.get("lift_weight_lbs") or 0.0
    if weight > 0:
        return _epley_1rm(weight, int(reps))
    return float(reps)


def _fmt_session(session: Dict[str, Any], score: float) -> str:
    metrics = session.get("metrics") or {}
    reps = int(metrics.get("total_reps", 0))
    weight = session.get("lift_weight_lbs") or 0.0
    ts = (session.get("timestamp") or "")[:10]
    if weight > 0:
        return f"{ts}  ·  {weight:.0f} lbs × {reps} reps  (est. 1RM {score:.0f} lbs)"
    return f"{ts}  ·  {reps} reps (bodyweight)  →  score {score:.0f}"


# ── Bodyweight feedback ───────────────────────────────────────────────────────

def _weight_feedback(entries: List[Dict[str, Any]], goal: Optional[TrainingGoal]) -> List[str]:
    if len(entries) < 2:
        return ["Log your weight regularly to track trends over time."]

    entries = sorted(entries, key=lambda e: e.get("timestamp", ""))
    first_kg = entries[0].get("weight_kg", 0.0)
    last_kg = entries[-1].get("weight_kg", 0.0)

    try:
        first_dt = datetime.strptime(entries[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
        last_dt = datetime.strptime(entries[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError):
        return []

    days = max(1, (last_dt - first_dt).days)
    delta_lbs = (last_kg - first_kg) * 2.20462
    rate = delta_lbs / (days / 7.0)  # lbs per week

    if goal == TrainingGoal.BUILD_MUSCLE:
        if rate > 1.0:
            return [
                f"You're gaining ~{rate:.1f} lbs/week — faster than optimal for lean muscle gain. "
                "Gaining too quickly often means excess fat accumulation. "
                "Aim for 0.25–0.5 lbs/week by trimming your caloric surplus slightly."
            ]
        if rate >= 0.25:
            return [
                f"You're gaining {rate:.1f} lbs/week — a healthy rate for lean muscle building. "
                "This pace minimises fat gain while supporting consistent growth. Keep it up!"
            ]
        if rate >= 0:
            return [
                f"Weight is relatively stable ({rate:+.2f} lbs/week). "
                "For muscle growth, a slight caloric surplus that drives 0.25–0.5 lbs/week of gain "
                "provides the extra energy needed to build tissue."
            ]
        return [
            f"Your weight is trending down ({rate:.2f} lbs/week). "
            "Building muscle in a caloric deficit is very difficult past the beginner stage. "
            "Try increasing daily intake by 200–300 calories."
        ]

    if goal == TrainingGoal.INCREASE_STRENGTH:
        if rate > 1.0:
            return [
                f"You're gaining {rate:.1f} lbs/week — potentially faster than ideal for a strength focus. "
                "A slight surplus is helpful, but slow gain (0.25–0.5 lbs/week) keeps body composition "
                "optimal for performance."
            ]
        if rate >= 0:
            return [
                f"Weight is {rate:+.2f} lbs/week — solid for strength development. "
                "A slight surplus ensures your muscles have the fuel to grow stronger."
            ]
        return [
            f"Your weight is trending down ({rate:.2f} lbs/week). "
            "Strength progresses best with adequate calories. Consider a small surplus."
        ]

    if goal == TrainingGoal.LOSE_WEIGHT:
        if rate < -2.0:
            return [
                f"You're losing {abs(rate):.1f} lbs/week — quite aggressive. "
                "Sustainable fat loss is 0.5–1 lb/week. Losing too quickly can reduce muscle mass "
                "and strength. Consider easing the deficit slightly."
            ]
        if rate <= -0.5:
            return [
                f"You're losing {abs(rate):.1f} lbs/week — solid, sustainable progress! "
                "Keep the deficit and maintain strength training to preserve muscle."
            ]
        if rate < 0:
            return [
                f"You're losing {abs(rate):.2f} lbs/week — steady progress. "
                "To accelerate slightly, consider increasing daily activity or trimming 100–200 calories."
            ]
        return [
            f"Weight is up {rate:.1f} lbs/week. "
            "For your weight-loss goal, review your caloric intake and ensure you're in a consistent deficit."
        ]

    if goal == TrainingGoal.GAIN_WEIGHT:
        if rate >= 0.5:
            return [f"You're gaining {rate:.1f} lbs/week — great progress toward your weight-gain goal!"]
        if rate >= 0:
            return [
                f"You're gaining {rate:.1f} lbs/week. "
                "To speed things up, try adding 300–500 calories per day through calorie-dense foods "
                "like nuts, oats, rice, and lean proteins."
            ]
        return [
            f"Your weight is trending down ({rate:.2f} lbs/week). "
            "To gain weight you need to consistently eat more than you burn. "
            "Add calorie-dense foods: nuts, oats, rice, lean meats, and whole milk."
        ]

    # No goal set
    return [
        f"Weight change: {rate:+.2f} lbs/week over the tracked period. "
        "Set a goal in Settings to receive personalised bodyweight feedback."
    ]


# ── Lift progress ─────────────────────────────────────────────────────────────

def _compute_lift_progress(history: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    sessions_by_ex: Dict[str, List] = defaultdict(list)
    for entry in history:
        ex = entry.get("exercise", "")
        if ex:
            sessions_by_ex[ex].append(entry)

    results: Dict[str, Optional[Dict[str, Any]]] = {}
    for ex_key in _EXERCISE_LABELS:
        sessions = sorted(sessions_by_ex.get(ex_key, []), key=lambda s: s.get("timestamp", ""))
        if len(sessions) < 2:
            results[ex_key] = None
            continue
        prev, curr = sessions[-2], sessions[-1]
        prev_score = _session_score(prev)
        curr_score = _session_score(curr)
        if prev_score is None or curr_score is None:
            results[ex_key] = None
            continue
        delta_pct = (curr_score - prev_score) / prev_score * 100.0 if prev_score else 0.0
        results[ex_key] = {
            "prev": prev,
            "curr": curr,
            "prev_score": prev_score,
            "curr_score": curr_score,
            "delta_pct": delta_pct,
        }
    return results


def _decline_tips(goal: Optional[TrainingGoal]) -> str:
    base = "Try prioritising 8 hours of sleep and at least 0.8 g of protein per lb of bodyweight."
    if goal == TrainingGoal.LOSE_WEIGHT:
        return base + " Be careful not to cut calories too aggressively — a steep deficit can erode strength."
    if goal == TrainingGoal.GAIN_WEIGHT:
        return base
    return base + " Eating in a slight caloric surplus also fuels strength gains."


# ── View ──────────────────────────────────────────────────────────────────────

class SelfView(tk.Frame):
    """Profile overview, bodyweight tracking, and lift progress tab."""

    def __init__(self, parent: tk.Misc, *, bg: str = theme.APP_SURFACE) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self._weight_expanded = False
        self._weight_tip_labels: List[tk.Label] = []
        self._toggle_btn: Optional[tk.Button] = None
        self._weight_container: Optional[tk.Frame] = None

        tk.Label(
            self,
            text="Self",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=bg,
        ).pack(anchor="w", padx=28, pady=(16, 8))

        scroll = ScrollableFrame(self, bg=bg)
        scroll.pack(fill=tk.BOTH, expand=True)
        self._outer = scroll.body()

        self._build_profile_card()
        self._build_progress_card()

    def refresh(self) -> None:
        for w in self._outer.winfo_children():
            w.destroy()
        self._weight_expanded = False
        self._weight_tip_labels = []
        self._toggle_btn = None
        self._weight_container = None
        self._build_profile_card()
        self._build_progress_card()

    # ── Profile card ──────────────────────────────────────────────────────────

    def _build_profile_card(self) -> None:
        panel = RoundedPanel(
            self._outer,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
            expand_fill=False,
        )
        self._profile_panel = panel
        panel.pack(fill=tk.X, padx=24, pady=(8, 0))
        wrap = tk.Frame(panel.body(), bg=theme.CARD_WHITE)
        wrap.pack(fill=tk.X, padx=20, pady=16)

        tk.Label(
            wrap,
            text="Your Profile",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w", pady=(0, 8))
        tk.Frame(wrap, bg=theme.CARD_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        profile = load_profile()
        if profile:
            self._profile_rows(wrap, profile)
        else:
            tk.Label(
                wrap,
                text="No profile found. Go to Settings to set up your profile.",
                font=theme.FONT_SMALL,
                fg=theme.TEXT_MUTED,
                bg=theme.CARD_WHITE,
            ).pack(anchor="w")

        tk.Frame(wrap, bg=theme.CARD_BORDER, height=1).pack(fill=tk.X, pady=(12, 0))

        self._toggle_btn = tk.Button(
            wrap,
            text="Track Bodyweight Changes  ▼",
            font=theme.FONT_SUB,
            fg=theme.ACCENT_NAV_ACTIVE,
            bg=theme.CARD_WHITE,
            activeforeground="#6D28D9",
            activebackground=theme.CARD_WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            anchor="w",
            command=self._toggle_weight_history,
        )
        self._toggle_btn.pack(fill=tk.X, pady=(8, 0))

        self._weight_container = tk.Frame(wrap, bg=theme.CARD_WHITE)
        panel.after_idle(panel.fit_hug)

    def _profile_rows(self, parent: tk.Frame, profile: UserProfile) -> None:
        def _row(label: str, value: str) -> None:
            f = tk.Frame(parent, bg=theme.CARD_WHITE)
            f.pack(fill=tk.X, pady=3)
            tk.Label(f, text=label, font=theme.FONT_SUB, fg=theme.TEXT_MUTED,
                     bg=theme.CARD_WHITE, width=10, anchor="w").pack(side=tk.LEFT)
            tk.Label(f, text=value, font=theme.FONT_BODY, fg=theme.TEXT_PRIMARY,
                     bg=theme.CARD_WHITE, anchor="w").pack(side=tk.LEFT)

        _row("Name", profile.first_name or "—")
        if profile.height_cm:
            h_in = profile.height_cm / 2.54
            _row("Height", f"{int(h_in // 12)}'{int(h_in % 12)}\"")
        if profile.weight_kg:
            _row("Weight", f"{profile.weight_kg * 2.20462:.1f} lbs")
        goal_label = "—"
        if profile.goal:
            for gl, ge in GOAL_CHOICES:
                if ge == profile.goal:
                    goal_label = gl
                    break
        _row("Goal", goal_label)

    # ── Bodyweight toggle ─────────────────────────────────────────────────────

    def _toggle_weight_history(self) -> None:
        self._weight_expanded = not self._weight_expanded
        if self._weight_expanded:
            assert self._toggle_btn and self._weight_container
            self._toggle_btn.config(text="Track Bodyweight Changes  ▲")
            self._weight_container.pack(fill=tk.X, pady=(8, 0))
            self._populate_weight_history(self._weight_container)
        else:
            assert self._toggle_btn and self._weight_container
            self._toggle_btn.config(text="Track Bodyweight Changes  ▼")
            self._weight_container.pack_forget()
            for w in self._weight_container.winfo_children():
                w.destroy()
            self._weight_tip_labels = []
        self._profile_panel.after_idle(self._profile_panel.fit_hug)

    def _repopulate_weight(self) -> None:
        """Refresh the weight history section after a new entry is logged."""
        if self._weight_container is None:
            return
        for w in self._weight_container.winfo_children():
            w.destroy()
        self._weight_tip_labels = []
        self._populate_weight_history(self._weight_container)
        self._profile_panel.after_idle(self._profile_panel.fit_hug)

    def _populate_weight_history(self, parent: tk.Frame) -> None:
        entries = load_weight_log()
        profile = load_profile()
        goal = profile.goal if profile else None

        # Quick-log row
        log_row = tk.Frame(parent, bg=theme.CARD_WHITE)
        log_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            log_row, text="Weight (lbs):",
            font=theme.FONT_SMALL, fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w",
        ).pack(side=tk.LEFT)
        wt_var = tk.StringVar()
        if profile and profile.weight_kg is not None:
            from lift_tracker.profile import kg_to_lbs
            cur = kg_to_lbs(profile.weight_kg)
            if cur is not None:
                wt_var.set(str(cur))
        tk.Entry(
            log_row, textvariable=wt_var, font=theme.FONT_SMALL,
            width=7, relief="solid", bd=1,
            highlightthickness=1, highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
        ).pack(side=tk.LEFT, padx=(6, 10), ipady=2)

        tk.Label(
            log_row, text="Date:",
            font=theme.FONT_SMALL, fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w",
        ).pack(side=tk.LEFT)
        date_var = tk.StringVar(value=datetime.now().strftime("%m/%d/%Y"))
        tk.Entry(
            log_row, textvariable=date_var, font=theme.FONT_SMALL,
            width=10, relief="solid", bd=1,
            highlightthickness=1, highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
        ).pack(side=tk.LEFT, padx=(6, 10), ipady=2)

        log_err = tk.Label(
            parent, text="", font=("Helvetica", 10), fg="#DC2626",
            bg=theme.CARD_WHITE, anchor="w",
        )
        log_err.pack(fill=tk.X)

        def _do_log() -> None:
            log_err.config(text="")
            s = wt_var.get().strip()
            if not s:
                return
            try:
                lbs = float(s.replace(",", "."))
            except ValueError:
                log_err.config(text="Enter a valid weight number.")
                return

            ds = date_var.get().strip()
            ts: Optional[str] = None
            if ds:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
                    try:
                        dt = datetime.strptime(ds, fmt)
                        ts = dt.strftime("%Y-%m-%d") + " 12:00:00"
                        break
                    except ValueError:
                        continue
                if ts is None:
                    log_err.config(text="Invalid date. Use MM/DD/YYYY.")
                    return

            from lift_tracker.profile import lbs_to_kg
            kg = lbs_to_kg(lbs)
            if kg is not None and kg > 0:
                log_weight(kg, timestamp=ts)
                p = load_profile()
                if p is not None:
                    p.weight_kg = kg
                    save_profile(p)
                self._repopulate_weight()

        log_lbl = tk.Label(
            log_row, text="Log", font=theme.FONT_SMALL,
            fg=theme.ACCENT_NAV_ACTIVE, bg=theme.CARD_WHITE,
            cursor="hand2", padx=6,
        )
        log_lbl.pack(side=tk.LEFT)
        log_lbl.bind("<Button-1>", lambda _e: _do_log())
        log_lbl.bind("<Enter>", lambda _e: log_lbl.config(fg="#6D28D9"))
        log_lbl.bind("<Leave>", lambda _e: log_lbl.config(fg=theme.ACCENT_NAV_ACTIVE))

        if not entries:
            lbl = tk.Label(
                parent,
                text="No weight entries yet — use the field above to start logging.",
                font=theme.FONT_SMALL,
                fg=theme.TEXT_MUTED,
                bg=theme.CARD_WHITE,
                wraplength=440,
                justify="left",
            )
            lbl.pack(anchor="w", pady=4)
            self._weight_tip_labels.append(lbl)
            return

        has_chart = self._has_chart_data(entries)

        # Two-column row: table on left, chart on right
        columns = tk.Frame(parent, bg=theme.CARD_WHITE)
        columns.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        left = tk.Frame(columns, bg=theme.CARD_WHITE)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=not has_chart)

        # Header row
        hdr = tk.Frame(left, bg=theme.CARD_WHITE)
        hdr.pack(fill=tk.X, pady=(0, 2))
        tk.Label(hdr, text="Date", font=theme.FONT_SUB, fg=theme.TEXT_MUTED,
                 bg=theme.CARD_WHITE, width=14, anchor="w").pack(side=tk.LEFT)
        tk.Label(hdr, text="Weight", font=theme.FONT_SUB, fg=theme.TEXT_MUTED,
                 bg=theme.CARD_WHITE, anchor="w").pack(side=tk.LEFT)

        indexed = list(enumerate(entries))
        indexed.sort(key=lambda t: t[1].get("timestamp", ""), reverse=True)
        for orig_idx, entry in indexed[:10]:
            ts_str = entry.get("timestamp", "")
            try:
                date_str = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y")
            except Exception:
                date_str = ts_str[:10]
            weight_lbs = entry.get("weight_kg", 0.0) * 2.20462
            row = tk.Frame(left, bg=theme.CARD_WHITE)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=date_str, font=theme.FONT_SMALL, fg=theme.TEXT_PRIMARY,
                     bg=theme.CARD_WHITE, width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{weight_lbs:.1f} lbs", font=theme.FONT_SMALL,
                     fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w").pack(side=tk.LEFT)

            def _del(idx: int = orig_idx) -> None:
                delete_weight_entry(idx)
                self._repopulate_weight()

            tk.Label(
                row, text="✕", font=("Helvetica", 10), fg="#DC2626",
                bg=theme.CARD_WHITE, cursor="hand2",
            ).pack(side=tk.RIGHT, padx=(8, 0))
            row.winfo_children()[-1].bind("<Button-1>", lambda _e, f=_del: f())

        if has_chart:
            sep = tk.Frame(columns, bg=theme.CARD_BORDER, width=1)
            sep.pack(side=tk.LEFT, fill=tk.Y, padx=(12, 12))
            right = tk.Frame(columns, bg=theme.CARD_WHITE)
            right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._build_weight_chart(right, entries)

        tips = _weight_feedback(entries, goal)
        if tips:
            tk.Frame(parent, bg=theme.CARD_BORDER, height=1).pack(fill=tk.X, pady=(10, 6))
            for tip in tips:
                row_f = tk.Frame(parent, bg=theme.CARD_WHITE)
                row_f.pack(fill=tk.X, pady=(0, 6))
                tk.Label(row_f, text="•", font=theme.FONT_SMALL, fg=theme.ACCENT_PURPLE,
                         bg=theme.CARD_WHITE).pack(side=tk.LEFT, padx=(0, 6), anchor="nw")
                lbl = tk.Label(
                    row_f,
                    text=tip,
                    font=theme.FONT_SMALL,
                    fg=theme.TEXT_PRIMARY,
                    bg=theme.CARD_WHITE,
                    justify="left",
                    anchor="nw",
                )
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="nw")
                self._weight_tip_labels.append(lbl)

        _last_parent_w: list = [0]

        def _sync_tip_wrap(_evt: object = None) -> None:
            try:
                pw = max(1, parent.winfo_width())
            except tk.TclError:
                return
            if pw == _last_parent_w[0]:
                return
            _last_parent_w[0] = pw
            wrap = max(200, pw - 40)
            for tl in self._weight_tip_labels:
                try:
                    tl.configure(wraplength=wrap)
                except tk.TclError:
                    pass

        parent.bind("<Configure>", _sync_tip_wrap)
        parent.after_idle(lambda: _sync_tip_wrap(None))

    # ── Weight chart ──────────────────────────────────────────────────────────

    @staticmethod
    def _has_chart_data(entries: List[Dict[str, Any]]) -> bool:
        days = {e.get("timestamp", "")[:10] for e in entries}
        return len(days) >= 2

    def _build_weight_chart(
        self, parent: tk.Frame, entries: List[Dict[str, Any]]
    ) -> None:
        sorted_ents = sorted(entries, key=lambda e: e.get("timestamp", ""))

        by_day: Dict[str, float] = {}
        for e in sorted_ents:
            day = e.get("timestamp", "")[:10]
            kg = e.get("weight_kg", 0.0)
            by_day[day] = kg * 2.20462

        days = sorted(by_day.keys())
        weights = [by_day[d] for d in days]
        if len(days) < 2:
            return

        CHART_H = 190
        PAD_L, PAD_R, PAD_T, PAD_B = 44, 12, 24, 28
        FILL_COLOR = "#EDE9FE"
        LINE_COLOR = theme.ACCENT_PURPLE
        DOT_R = 3.5

        tk.Label(
            parent, text="Weight Trend", font=theme.FONT_SUB,
            fg=theme.TEXT_PRIMARY, bg=theme.CARD_WHITE, anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        canvas = tk.Canvas(
            parent, height=CHART_H, bg=theme.CARD_WHITE,
            highlightthickness=0, bd=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        min_w = min(weights) - 1
        max_w = max(weights) + 1
        if max_w <= min_w:
            max_w = min_w + 2
        w_range = max_w - min_w

        def _draw(_evt: object = None) -> None:
            canvas.delete("all")
            cw = max(120, canvas.winfo_width())
            ch = max(80, canvas.winfo_height())
            plot_w = cw - PAD_L - PAD_R
            plot_h = ch - PAD_T - PAD_B

            def _px(i: int, w: float) -> tuple:
                x = PAD_L + (i / max(1, len(days) - 1)) * plot_w
                y = PAD_T + (1.0 - (w - min_w) / w_range) * plot_h
                return x, y

            n_grid = 4
            for gi in range(n_grid + 1):
                gy = PAD_T + gi * plot_h / n_grid
                gw = min_w + (1 - gi / n_grid) * w_range
                canvas.create_line(
                    PAD_L, gy, cw - PAD_R, gy,
                    fill=theme.CARD_BORDER, dash=(2, 4),
                )
                canvas.create_text(
                    PAD_L - 6, gy, text=f"{gw:.0f}",
                    anchor="e", font=("Helvetica", 9), fill=theme.TEXT_MUTED,
                )

            pts = [_px(i, w) for i, w in enumerate(weights)]

            poly_coords: list = []
            for p in pts:
                poly_coords.extend(p)
            poly_coords.extend([pts[-1][0], PAD_T + plot_h])
            poly_coords.extend([pts[0][0], PAD_T + plot_h])
            canvas.create_polygon(poly_coords, fill=FILL_COLOR, outline="")

            line_coords: list = []
            for p in pts:
                line_coords.extend(p)
            canvas.create_line(
                *line_coords, fill=LINE_COLOR, width=2, smooth=True, capstyle="round",
            )

            for x, y in pts:
                canvas.create_oval(
                    x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R,
                    fill=LINE_COLOR, outline=theme.CARD_WHITE, width=1.5,
                )

            max_labels = min(5, len(days))
            step = max(1, (len(days) - 1) // (max_labels - 1)) if max_labels > 1 else 1
            label_indices = list(range(0, len(days), step))
            if (len(days) - 1) not in label_indices:
                label_indices.append(len(days) - 1)
            for i in label_indices:
                x, _ = _px(i, weights[i])
                try:
                    dl = datetime.strptime(days[i], "%Y-%m-%d").strftime("%b %d")
                except ValueError:
                    dl = days[i]
                canvas.create_text(
                    x, ch - 4, text=dl, anchor="s",
                    font=("Helvetica", 9), fill=theme.TEXT_MUTED,
                )

        _last_size: list = [(0, 0)]

        def _on_cfg(_evt: object = None) -> None:
            sz = (canvas.winfo_width(), canvas.winfo_height())
            if sz == _last_size[0]:
                return
            _last_size[0] = sz
            _draw()

        canvas.bind("<Configure>", _on_cfg)
        canvas.after_idle(_draw)

    # ── Lift progress card ────────────────────────────────────────────────────

    def _build_progress_card(self) -> None:
        # expand_fill=False: hug content height. expand_fill=True clips the inner frame to a short canvas
        # when this card lives inside ScrollableFrame (fill=X only), hiding rows like "Bicep Curl".
        panel = RoundedPanel(
            self._outer,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
            expand_fill=False,
        )
        panel.pack(fill=tk.X, padx=24, pady=(12, 16))
        wrap = tk.Frame(panel.body(), bg=theme.CARD_WHITE)
        wrap.pack(fill=tk.X, padx=20, pady=16)

        tk.Label(
            wrap,
            text="Lift Progress",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w", pady=(0, 8))
        tk.Frame(wrap, bg=theme.CARD_BORDER, height=1).pack(fill=tk.X, pady=(0, 12))

        profile = load_profile()
        goal = profile.goal if profile else None

        history: List[Dict[str, Any]] = []
        try:
            if HISTORY_JSON.exists():
                with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                    history = json.load(f)
        except Exception:
            pass

        progress = _compute_lift_progress(history)
        any_data = any(v is not None for v in progress.values())

        for ex_key, ex_label in _EXERCISE_LABELS.items():
            self._render_exercise_row(wrap, ex_label, progress.get(ex_key), goal)

        if not any_data:
            tk.Label(
                wrap,
                text="Complete at least 2 sessions of an exercise to see progress comparisons here.",
                font=theme.FONT_SMALL,
                fg=theme.TEXT_MUTED,
                bg=theme.CARD_WHITE,
                wraplength=440,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))

        panel.after_idle(panel.fit_hug)

    def _render_exercise_row(
        self,
        parent: tk.Frame,
        label: str,
        data: Optional[Dict[str, Any]],
        goal: Optional[TrainingGoal],
    ) -> None:
        frame = tk.Frame(parent, bg=theme.CARD_WHITE)
        frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            frame,
            text=label,
            font=theme.FONT_SUB,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(anchor="w")

        if data is None:
            tk.Label(
                frame,
                text="Not enough sessions yet.",
                font=theme.FONT_SMALL,
                fg=theme.TEXT_MUTED,
                bg=theme.CARD_WHITE,
            ).pack(anchor="w", padx=(12, 0))
            return

        delta_pct = data["delta_pct"]
        prev_score = data["prev_score"]
        curr_score = data["curr_score"]

        if delta_pct >= 3.0:
            detail_bg, arrow, arrow_color = "#F0FDF4", "↑", "#16A34A"
            msg = f"+{delta_pct:.1f}% — You're clearly getting stronger. Keep it up!"
            msg_color = "#16A34A"
        elif delta_pct <= -3.0:
            detail_bg, arrow, arrow_color = "#FFF1F2", "↓", "#DC2626"
            tips = _decline_tips(goal)
            msg = f"{delta_pct:.1f}% — Strength appears to have dipped. {tips}"
            msg_color = "#DC2626"
        else:
            detail_bg, arrow, arrow_color = "#F9FAFB", "→", theme.TEXT_MUTED
            msg = f"{delta_pct:+.1f}% — Performance is consistent."
            msg_color = theme.TEXT_MUTED

        box = tk.Frame(
            frame,
            bg=detail_bg,
            highlightthickness=1,
            highlightbackground="#DDD6FE",
            bd=0,
        )
        box.pack(fill=tk.X, padx=(12, 0), pady=(4, 0))

        lbl_prev = tk.Label(
            box,
            text=_fmt_session(data["prev"], prev_score),
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=detail_bg,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_prev.pack(anchor="w", padx=10, pady=(8, 2))

        lbl_curr = tk.Label(
            box,
            text=_fmt_session(data["curr"], curr_score),
            font=theme.FONT_SMALL,
            fg=theme.TEXT_PRIMARY,
            bg=detail_bg,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_curr.pack(anchor="w", padx=10, pady=(2, 4))

        msg_row = tk.Frame(box, bg=detail_bg)
        msg_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Label(
            msg_row,
            text=arrow,
            font=("Helvetica", 13, "bold"),
            fg=arrow_color,
            bg=detail_bg,
        ).pack(side=tk.LEFT, padx=(0, 6), anchor="nw")
        lbl_msg = tk.Label(
            msg_row,
            text=msg,
            font=theme.FONT_SMALL,
            fg=msg_color,
            bg=detail_bg,
            justify=tk.LEFT,
            anchor="nw",
        )
        lbl_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="nw")

        _last_w = [0]

        def _sync_wrap(_evt: object = None) -> None:
            try:
                bw = max(1, int(box.winfo_width()))
            except tk.TclError:
                return
            if bw == _last_w[0]:
                return
            _last_w[0] = bw
            inner_w = max(200, bw - 24)
            lbl_prev.configure(wraplength=inner_w)
            lbl_curr.configure(wraplength=inner_w)
            lbl_msg.configure(wraplength=max(160, inner_w - 28))

        box.bind("<Configure>", _sync_wrap)
        box.after_idle(lambda: _sync_wrap(None))
