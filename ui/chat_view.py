from __future__ import annotations

import json
import threading
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ui import theme
from ui.components import RoundedPanel
from ui.paths import API_CONFIG_JSON, HISTORY_JSON, WEIGHT_LOG_JSON
from ui.profile_store import load_profile, load_weight_log


# ── API key persistence ───────────────────────────────────────────────────────

def load_api_key() -> str:
    if not API_CONFIG_JSON.exists():
        return ""
    try:
        with open(API_CONFIG_JSON, "r", encoding="utf-8") as f:
            return json.load(f).get("openai_api_key", "")
    except Exception:
        return ""


def save_api_key(key: str) -> None:
    try:
        with open(API_CONFIG_JSON, "w", encoding="utf-8") as f:
            json.dump({"openai_api_key": key.strip()}, f)
    except OSError:
        pass


# ── Context builder ───────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    lines: List[str] = [
        "You are FormCoach, an AI fitness assistant embedded in the FormLogic workout tracker.",
        "You have full access to the user's data below. Give specific, data-driven advice.",
        "Be encouraging, concise, and reference actual numbers when relevant.",
        "",
    ]

    # Profile
    profile = load_profile()
    lines.append("=== USER PROFILE ===")
    if profile:
        lines.append(f"Name: {profile.first_name or 'Unknown'}")
        if profile.goal:
            from lift_tracker.profile import GOAL_CHOICES
            goal_label = str(profile.goal.value)
            for gl, ge in GOAL_CHOICES:
                if ge == profile.goal:
                    goal_label = gl
                    break
            lines.append(f"Goal: {goal_label}")
        if profile.height_cm:
            h_in = profile.height_cm / 2.54
            lines.append(f"Height: {int(h_in // 12)}'{int(h_in % 12)}\"")
        if profile.weight_kg:
            lines.append(f"Current weight: {profile.weight_kg * 2.20462:.1f} lbs")
    else:
        lines.append("No profile set up yet.")
    lines.append("")

    # Weight log
    weight_log = load_weight_log()
    lines.append("=== BODYWEIGHT HISTORY (most recent first) ===")
    if weight_log:
        sorted_log = sorted(weight_log, key=lambda e: e.get("timestamp", ""), reverse=True)
        for entry in sorted_log[:10]:
            ts = entry.get("timestamp", "")[:10]
            lbs = entry.get("weight_kg", 0.0) * 2.20462
            lines.append(f"  {ts}: {lbs:.1f} lbs")
    else:
        lines.append("  No weight entries logged yet.")
    lines.append("")

    # Workout history
    history: List[Dict[str, Any]] = []
    try:
        if HISTORY_JSON.exists():
            with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                history = json.load(f)
    except Exception:
        pass

    lines.append("=== RECENT WORKOUT SESSIONS (most recent first, up to 20) ===")
    if history:
        sorted_history = sorted(history, key=lambda e: e.get("timestamp", ""), reverse=True)
        for entry in sorted_history[:20]:
            ts = (entry.get("timestamp") or "")[:16]
            ex = entry.get("exercise_display") or entry.get("exercise", "?")
            metrics = entry.get("metrics") or {}
            reps = metrics.get("total_reps", "?")
            weight = entry.get("lift_weight_lbs")
            weight_str = f" @ {weight:.0f} lbs" if weight else " (bodyweight)"
            line = f"  [{ts}] {ex} — {reps} reps{weight_str}"

            # Append key form metrics where available
            details = []
            if "avg_depth_pct" in metrics:
                details.append(f"avg depth {metrics['avg_depth_pct']:.0f}%")
            if "avg_conc_depth_pct" in metrics:
                details.append(f"conc depth {metrics['avg_conc_depth_pct']:.0f}%")
            if "avg_ecc_depth_pct" in metrics:
                details.append(f"ecc depth {metrics['avg_ecc_depth_pct']:.0f}%")
            if "avg_rep_duration_s" in metrics:
                details.append(f"avg rep {metrics['avg_rep_duration_s']:.1f}s")
            if "head_clearance_pct" in metrics:
                details.append(f"head clearance {metrics['head_clearance_pct']:.0f}%")

            if weight and weight > 0:
                try:
                    epley = weight * (1 + int(reps) / 30)
                    details.append(f"est. 1RM {epley:.0f} lbs")
                except Exception:
                    pass

            if details:
                line += f"  [{', '.join(details)}]"
            lines.append(line)
    else:
        lines.append("  No sessions logged yet.")
    lines.append("")

    # All-time bests (for absolute reference only)
    lines.append("=== ALL-TIME BEST SESSION PER EXERCISE ===")
    bests: Dict[str, Any] = {}
    for entry in history:
        ex = entry.get("exercise", "")
        metrics = entry.get("metrics") or {}
        reps = int(metrics.get("total_reps") or 0)
        weight = entry.get("lift_weight_lbs") or 0.0
        if not reps:
            continue
        score = weight * (1 + reps / 30) if weight > 0 else float(reps)
        if ex not in bests or score > bests[ex]["score"]:
            bests[ex] = {"score": score, "reps": reps, "weight": weight, "timestamp": entry.get("timestamp", "")}

    ex_order = [("squat", "Squat"), ("bicep_curl", "Bicep Curl"), ("pullup", "Pull-up")]
    for ex_key, ex_label in ex_order:
        b = bests.get(ex_key)
        if b:
            w, r = b["weight"], b["reps"]
            ts = b["timestamp"][:10]
            if w > 0:
                lines.append(f"  {ex_label} [{ts}]: {w:.0f} lbs × {r} reps (est. 1RM {b['score']:.0f} lbs)")
            else:
                lines.append(f"  {ex_label} [{ts}]: {r} reps (bodyweight)")
        else:
            lines.append(f"  {ex_label}: no data")
    lines.append("")

    # Explicit trend comparison — the primary signal for recent progress
    lines.append("=== RECENT STRENGTH TREND (last 2 sessions per exercise — USE THIS for progress questions) ===")
    sessions_by_ex: Dict[str, List] = defaultdict(list)
    for entry in history:
        ex = entry.get("exercise", "")
        if ex:
            sessions_by_ex[ex].append(entry)

    for ex_key, ex_label in ex_order:
        sessions = sorted(sessions_by_ex.get(ex_key, []), key=lambda s: s.get("timestamp", ""))
        if len(sessions) < 2:
            count = len(sessions)
            lines.append(f"  {ex_label}: only {count} session(s) logged — no trend available yet.")
            continue

        prev, curr = sessions[-2], sessions[-1]

        def _score(s: Dict[str, Any]) -> Optional[float]:
            r = int((s.get("metrics") or {}).get("total_reps") or 0)
            if not r:
                return None
            w = s.get("lift_weight_lbs") or 0.0
            return w * (1 + r / 30) if w > 0 else float(r)

        def _desc(s: Dict[str, Any], score: float) -> str:
            r = int((s.get("metrics") or {}).get("total_reps") or 0)
            w = s.get("lift_weight_lbs") or 0.0
            ts = (s.get("timestamp") or "")[:10]
            if w > 0:
                return f"{ts}: {w:.0f} lbs × {r} reps (est. 1RM {score:.0f} lbs)"
            return f"{ts}: {r} reps bodyweight (score {score:.0f})"

        prev_score = _score(prev)
        curr_score = _score(curr)

        if prev_score is None or curr_score is None:
            lines.append(f"  {ex_label}: insufficient rep data in one of the last two sessions.")
            continue

        delta_pct = (curr_score - prev_score) / prev_score * 100.0
        if delta_pct >= 3.0:
            verdict = f"IMPROVED by {delta_pct:.1f}%"
        elif delta_pct <= -3.0:
            verdict = f"DECLINED by {abs(delta_pct):.1f}%"
        else:
            verdict = f"CONSISTENT ({delta_pct:+.1f}%)"

        lines.append(f"  {ex_label}:")
        lines.append(f"    Previous — {_desc(prev, prev_score)}")
        lines.append(f"    Latest   — {_desc(curr, curr_score)}")
        lines.append(f"    Verdict  — {verdict}")

    return "\n".join(lines)


# ── View ──────────────────────────────────────────────────────────────────────

_USER_TAG = "user_msg"
_BOT_TAG = "bot_msg"
_SENDER_TAG = "sender_label"
_THINKING_TAG = "thinking"
_ERROR_TAG = "error_msg"


class ChatView(tk.Frame):
    """AI coach chat interface backed by OpenAI."""

    def __init__(self, parent: tk.Misc, *, bg: str = theme.APP_SURFACE) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self._bg = bg
        self._messages: List[Dict[str, str]] = []  # {"role": ..., "content": ...}
        self._waiting = False

        self._build_ui()

    def _build_ui(self) -> None:
        # Title bar
        title_row = tk.Frame(self, bg=self._bg)
        title_row.pack(fill=tk.X, padx=28, pady=(16, 4))
        tk.Label(
            title_row,
            text="FormCoach",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=self._bg,
        ).pack(side=tk.LEFT)
        tk.Label(
            title_row,
            text="powered by ChatGPT",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=self._bg,
        ).pack(side=tk.LEFT, padx=(10, 0), pady=(4, 0))

        # Main area: API setup card OR chat area
        self._main = tk.Frame(self, bg=self._bg)
        self._main.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 0))

        api_key = load_api_key()
        if api_key:
            self._show_chat_ui()
        else:
            self._show_setup_ui()

    # ── API key setup ─────────────────────────────────────────────────────────

    def _show_setup_ui(self) -> None:
        for w in self._main.winfo_children():
            w.destroy()

        panel = RoundedPanel(
            self._main,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
        )
        panel.pack(fill=tk.BOTH, expand=True, pady=8)
        inner = tk.Frame(panel.body(), bg=theme.CARD_WHITE)
        inner.pack(expand=True, padx=40, pady=40)

        tk.Label(
            inner,
            text="Connect your OpenAI API key",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
        ).pack(pady=(0, 8))
        tk.Label(
            inner,
            text=(
                "FormCoach uses the ChatGPT API to answer questions about your\n"
                "workouts, weight, form, and goals. Your key is stored locally."
            ),
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            justify="center",
        ).pack(pady=(0, 20))

        self._key_var = tk.StringVar()
        key_entry = tk.Entry(
            inner,
            textvariable=self._key_var,
            font=theme.FONT_BODY,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
            show="•",
            width=40,
        )
        key_entry.pack(fill=tk.X, ipady=5, pady=(0, 6))

        self._setup_err = tk.Label(
            inner,
            text="",
            font=theme.FONT_SMALL,
            fg="#DC2626",
            bg=theme.CARD_WHITE,
        )
        self._setup_err.pack(pady=(0, 12))

        tk.Button(
            inner,
            text="Save & Start Chatting",
            font=theme.FONT_CTA,
            command=self._save_key,
            bg=theme.ACCENT_NAV_ACTIVE,
            fg="#FFFFFF",
            activebackground="#6D28D9",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=24,
            pady=10,
            cursor="hand2",
        ).pack()

        tk.Label(
            inner,
            text="You can find your key at platform.openai.com/api-keys",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
        ).pack(pady=(16, 0))

    def _save_key(self) -> None:
        key = (self._key_var.get() or "").strip()
        if not key.startswith("sk-"):
            self._setup_err.config(text="That doesn't look like a valid OpenAI key (should start with sk-).")
            return
        save_api_key(key)
        self._show_chat_ui()

    # ── Chat UI ───────────────────────────────────────────────────────────────

    def _show_chat_ui(self) -> None:
        for w in self._main.winfo_children():
            w.destroy()
        self._messages = []

        # Chat transcript
        transcript_panel = RoundedPanel(
            self._main,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
        )
        transcript_panel.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        transcript_body = transcript_panel.body()

        # Small "change key" button top-right
        key_btn = tk.Button(
            transcript_body,
            text="Change API key",
            font=theme.FONT_SMALL,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
            activeforeground=theme.ACCENT_NAV_ACTIVE,
            activebackground=theme.CARD_WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._show_setup_ui,
        )
        key_btn.pack(anchor="ne", padx=10, pady=(6, 0))

        self._text = tk.Text(
            transcript_body,
            font=theme.FONT_SMALL,
            bg=theme.CARD_WHITE,
            fg=theme.TEXT_PRIMARY,
            relief="flat",
            bd=0,
            wrap=tk.WORD,
            state=tk.DISABLED,
            cursor="arrow",
            padx=16,
            pady=8,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # Configure text tags
        self._text.tag_configure(
            _USER_TAG,
            foreground=theme.ACCENT_NAV_ACTIVE,
            lmargin1=20,
            lmargin2=20,
            spacing3=2,
        )
        self._text.tag_configure(
            _BOT_TAG,
            foreground=theme.TEXT_PRIMARY,
            lmargin1=20,
            lmargin2=20,
            spacing3=2,
        )
        self._text.tag_configure(
            _SENDER_TAG,
            font=("Helvetica", 9, "bold"),
            spacing1=10,
        )
        self._text.tag_configure(
            _THINKING_TAG,
            foreground=theme.TEXT_MUTED,
            font=("Helvetica", 9, "italic"),
            lmargin1=20,
            lmargin2=20,
            spacing1=8,
        )
        self._text.tag_configure(
            _ERROR_TAG,
            foreground="#DC2626",
            lmargin1=20,
            lmargin2=20,
            spacing1=8,
        )

        # Mousewheel on text widget
        self._text.bind("<MouseWheel>", lambda e: None)

        # Input area
        input_panel = RoundedPanel(
            self._main,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=255,
        )
        input_panel.pack(fill=tk.X, pady=(8, 8))
        input_body = input_panel.body()

        input_row = tk.Frame(input_body, bg=theme.CARD_WHITE)
        input_row.pack(fill=tk.X, padx=12, pady=10)

        self._input = tk.Text(
            input_row,
            font=theme.FONT_BODY,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=theme.CARD_BORDER,
            highlightcolor=theme.ACCENT_NAV_ACTIVE,
            height=2,
            wrap=tk.WORD,
        )
        self._input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self._input.bind("<Return>", self._on_enter_key)
        self._input.bind("<Shift-Return>", lambda e: None)  # allow newline with shift

        self._send_btn = tk.Button(
            input_row,
            text="Send",
            font=theme.FONT_CTA,
            command=self._send,
            bg=theme.ACCENT_NAV_ACTIVE,
            fg="#FFFFFF",
            activebackground="#6D28D9",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        )
        self._send_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Welcome message
        self._append_bot(
            "Hi! I'm FormCoach — your AI fitness assistant. "
            "Ask me anything about your workouts, weight progress, form, or goals. "
            "For example: *How is my pull-up progress?* or *What should I focus on to reach my goal?*"
        )

    # ── Message handling ──────────────────────────────────────────────────────

    def _on_enter_key(self, event: tk.Event) -> str:
        if event.state & 0x1:  # Shift held → allow newline
            return ""
        self._send()
        return "break"

    def _send(self) -> None:
        if self._waiting:
            return
        text = self._input.get("1.0", tk.END).strip()
        if not text:
            return
        self._input.delete("1.0", tk.END)

        self._append_user(text)
        self._messages.append({"role": "user", "content": text})
        self._set_waiting(True)
        self._append_thinking()

        api_key = load_api_key()
        messages_snapshot = [{"role": "system", "content": _build_system_prompt()}] + list(self._messages)

        thread = threading.Thread(
            target=self._api_thread,
            args=(api_key, messages_snapshot),
            daemon=True,
        )
        thread.start()

    def _api_thread(self, api_key: str, messages: List[Dict[str, str]]) -> None:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=600,
                temperature=0.7,
            )
            reply = response.choices[0].message.content or ""
            self.after(0, lambda: self._on_reply(reply))
        except Exception as exc:
            err = str(exc)
            # Surface the most useful part of common errors
            if "api_key" in err.lower() or "authentication" in err.lower() or "invalid" in err.lower():
                err = "Invalid API key. Go to 'Change API key' and enter a valid key from platform.openai.com."
            elif "quota" in err.lower() or "rate" in err.lower():
                err = "API quota or rate limit reached. Please check your OpenAI account."
            elif "network" in err.lower() or "connect" in err.lower() or "timeout" in err.lower():
                err = "Network error — check your internet connection and try again."
            self.after(0, lambda e=err: self._on_error(e))

    def _on_reply(self, text: str) -> None:
        self._remove_thinking()
        self._set_waiting(False)
        self._messages.append({"role": "assistant", "content": text})
        self._append_bot(text)

    def _on_error(self, message: str) -> None:
        self._remove_thinking()
        self._set_waiting(False)
        self._append_error(message)

    def _set_waiting(self, waiting: bool) -> None:
        self._waiting = waiting
        state = tk.DISABLED if waiting else tk.NORMAL
        self._send_btn.config(state=state)

    # ── Text widget helpers ───────────────────────────────────────────────────

    def _append_user(self, text: str) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, "You\n", (_SENDER_TAG, _USER_TAG))
        self._text.insert(tk.END, text + "\n", _USER_TAG)
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)

    def _append_bot(self, text: str) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, "FormCoach\n", (_SENDER_TAG, _BOT_TAG))
        # Render *italic* markers as plain text — good enough for simple formatting
        self._text.insert(tk.END, text.replace("*", "") + "\n", _BOT_TAG)
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)

    def _append_thinking(self) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, "FormCoach is thinking…\n", _THINKING_TAG)
        self._thinking_index = self._text.index(tk.END)
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)

    def _remove_thinking(self) -> None:
        self._text.config(state=tk.NORMAL)
        content = self._text.get("1.0", tk.END)
        marker = "FormCoach is thinking…\n"
        idx = content.rfind(marker)
        if idx >= 0:
            start = f"1.0 + {idx} chars"
            end = f"1.0 + {idx + len(marker)} chars"
            self._text.delete(start, end)
        self._text.config(state=tk.DISABLED)

    def _append_error(self, message: str) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, f"Error: {message}\n", _ERROR_TAG)
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)

    def refresh(self) -> None:
        """Called when tab is navigated to — no-op (chat history is preserved in-session)."""
        pass
