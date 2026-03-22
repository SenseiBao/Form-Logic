from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

from PIL import ImageTk

from lift_tracker.exercises.bicep_curl import BicepCurlExercise
from lift_tracker.exercises.pullup import PullUpExercise
from lift_tracker.exercises.squat import SquatExercise

from ui.components import BottomNav, TabId
from ui.history_view import HistoryView
from ui.home_view import HomeView
from ui.paths import HISTORY_JSON
from ui.recording_window import RecordingSession
from ui.self_view import SelfView
from ui import theme


EXERCISE_DISPLAY = {
    "squat": "SQUAT",
    "bicep_curl": "BICEP CURL",
    "pullup": "PULL-UP",
}


def make_exercise(key: str):
    if key == "squat":
        return SquatExercise()
    if key == "bicep_curl":
        return BicepCurlExercise()
    if key == "pullup":
        return PullUpExercise()
    return SquatExercise()


def save_log(entry: Dict[str, Any]) -> None:
    history: list = []
    if HISTORY_JSON.exists():
        try:
            with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []
    if not isinstance(history, list):
        history = []
    history.append(entry)
    try:
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
    except OSError:
        pass


class FormLogicApp:
    BG = theme.APP_SURFACE

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Form-Logic Tracker")
        root.configure(bg=self.BG)
        root.minsize(960, 640)
        root.geometry("1000x720")

        self._grad_photo = None
        self._strip_h = 132
        self._grad_canvas = tk.Canvas(root, height=self._strip_h, highlightthickness=0, bd=0, bg=self.BG)
        self._grad_canvas.pack(fill=tk.X)
        self._grad_canvas.bind("<Configure>", self._paint_gradient_strip)
        self._last_grad_w = -1

        self._shell = tk.Frame(root, bg=self.BG, highlightthickness=0, bd=0)
        self._shell.pack(fill=tk.BOTH, expand=True)

        self._content = tk.Frame(self._shell, bg=self.BG, highlightthickness=0, bd=0)
        self._content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._home = HomeView(self._content, on_begin=self._on_begin, bg=self.BG)
        self._history = HistoryView(self._content, bg=self.BG)
        self._self = SelfView(self._content, bg=self.BG)

        self._nav = BottomNav(self._shell, self._on_tab, bg=theme.NAV_DOCK_BG)
        self._nav.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 20))

        self._current_tab: TabId = "home"
        self._recording: Optional[RecordingSession] = None
        self._show_tab("home")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=theme.CARD_WHITE,
            foreground=theme.TEXT_PRIMARY,
            borderwidth=0,
            relief="flat",
        )

    def _paint_gradient_strip(self, event: tk.Event) -> None:
        w = max(2, event.width)
        if w == self._last_grad_w:
            return
        self._last_grad_w = w
        h = self._strip_h
        img = theme.diagonal_gradient_rgba(w, h)
        self._grad_photo = ImageTk.PhotoImage(img, master=self._grad_canvas)
        self._grad_canvas.delete("all")
        self._grad_canvas.create_image(0, 0, anchor="nw", image=self._grad_photo)
        self._grad_canvas.configure(height=h)

    def _show_tab(self, tab: TabId) -> None:
        self._home.pack_forget()
        self._history.pack_forget()
        self._self.pack_forget()
        if tab == "home":
            self._home.pack(fill=tk.BOTH, expand=True)
        elif tab == "history":
            self._history.refresh()
            self._history.pack(fill=tk.BOTH, expand=True)
        else:
            self._self.pack(fill=tk.BOTH, expand=True)
        self._current_tab = tab

    def _on_tab(self, tab: TabId) -> None:
        self._show_tab(tab)

    def _on_begin(self, exercise_key: str, target_reps: int) -> None:
        ex = make_exercise(exercise_key)
        display = EXERCISE_DISPLAY.get(exercise_key, exercise_key.upper())
        self._home.pack_forget()
        self._history.pack_forget()
        self._self.pack_forget()
        self._nav.pack_forget()
        self._recording = RecordingSession(
            self._content,
            exercise_module=ex,
            exercise_display=display,
            target_reps=target_reps,
            on_finished=self._on_session_finished,
        )
        self._recording.pack(fill=tk.BOTH, expand=True)

    def _on_session_finished(self, log_entry: Dict[str, Any]) -> None:
        save_log(log_entry)
        self._recording = None
        self._nav.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 20))
        self._show_tab("home")
        self._history.refresh()


def main() -> None:
    root = tk.Tk()
    FormLogicApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
