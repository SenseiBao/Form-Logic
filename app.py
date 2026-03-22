from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from typing import Any, Dict, Optional

from PIL import ImageTk

from lift_tracker.exercises.bicep_curl import BicepCurlExercise
from lift_tracker.exercises.pullup import PullUpExercise
from lift_tracker.exercises.squat import SquatExercise
from lift_tracker.profile import UserProfile

from ui.components import BottomNav, TabId
from ui.dpi import apply_tk_scaling, enable_windows_dpi_awareness
from ui.history_view import HistoryView
from ui.home_view import HomeView
from ui.onboarding_dialog import OnboardingDialog
from ui.paths import HISTORY_JSON
from ui.profile_store import clear_profile_and_history, load_profile, needs_onboarding, save_profile
from ui.recording_window import RecordingSession
from ui.self_view import SelfView
from ui.settings_view import SettingsView
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

    def __init__(self, root: tk.Tk, *, first_name: str = "there") -> None:
        self.root = root
        root.title("Form-Logic Tracker")
        root.configure(bg=self.BG)
        root.minsize(960, 640)
        root.geometry("1000x720")

        self._grad_photo = None
        self._strip_h = 248
        self._grad_canvas = tk.Canvas(root, height=self._strip_h, highlightthickness=0, bd=0, bg=self.BG)
        self._grad_canvas.pack(fill=tk.X)
        self._grad_canvas.bind("<Configure>", self._paint_gradient_strip)
        self._last_grad_w = -1

        self._shell = tk.Frame(root, bg=self.BG, highlightthickness=0, bd=0)
        self._shell.pack(fill=tk.BOTH, expand=True)

        self._content = tk.Frame(self._shell, bg=self.BG, highlightthickness=0, bd=0)
        self._content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._home = HomeView(self._content, user_name=first_name, on_begin=self._on_begin, bg=self.BG)
        self._history = HistoryView(self._content, bg=self.BG)
        self._self = SelfView(self._content, bg=self.BG)
        self._settings = SettingsView(
            self._content,
            bg=self.BG,
            on_save=self._on_settings_save,
            on_reset=self._on_settings_reset,
        )

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
        style.configure(
            "Home.TCombobox",
            fieldbackground=theme.COMBO_FIELD_GREY,
            background=theme.COMBO_FIELD_GREY,
            foreground=theme.TEXT_PRIMARY,
            borderwidth=0,
            arrowcolor=theme.TEXT_MUTED,
            padding=(8, 4),
        )
        style.map(
            "Home.TCombobox",
            fieldbackground=[("readonly", theme.COMBO_FIELD_GREY), ("disabled", theme.COMBO_FIELD_GREY)],
            selectbackground=[("readonly", theme.COMBO_FIELD_GREY)],
            selectforeground=[("readonly", theme.TEXT_PRIMARY)],
        )

    def _paint_gradient_strip(self, event: tk.Event) -> None:
        w = max(2, event.width)
        if w == self._last_grad_w:
            return
        self._last_grad_w = w
        h = self._strip_h
        img = theme.header_banner_gradient(w, h)
        self._grad_photo = ImageTk.PhotoImage(img, master=self._grad_canvas)
        self._grad_canvas.delete("all")
        self._grad_canvas.create_image(0, 0, anchor="nw", image=self._grad_photo)
        self._grad_canvas.configure(height=h)

    def _show_tab(self, tab: TabId) -> None:
        self._home.pack_forget()
        self._history.pack_forget()
        self._self.pack_forget()
        self._settings.pack_forget()
        if tab == "home":
            self._home.pack(fill=tk.BOTH, expand=True)
        elif tab == "history":
            self._history.refresh()
            self._history.pack(fill=tk.BOTH, expand=True)
        elif tab == "self":
            self._self.pack(fill=tk.BOTH, expand=True)
        else:
            self._settings.refresh_from_profile()
            self._settings.pack(fill=tk.BOTH, expand=True)
        self._current_tab = tab

    def _on_tab(self, tab: TabId) -> None:
        self._show_tab(tab)

    def _on_settings_save(self, profile: UserProfile) -> None:
        save_profile(profile)
        self._home.set_first_name(profile.first_name)

    def _on_settings_reset(self) -> None:
        if not messagebox.askyesno(
            "Reset all data",
            "This will delete your workout history and profile, then ask you to set up again.\n\nContinue?",
            icon="warning",
            parent=self.root,
        ):
            return
        clear_profile_and_history()
        dlg = OnboardingDialog(self.root, on_saved=save_profile)
        if dlg.cancelled:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            return
        profile = load_profile()
        first = (profile.first_name if profile else "").strip() or "there"
        self._home.set_first_name(first)
        self._settings.refresh_from_profile()
        self._history.refresh()
        self._nav.set_active("home")

    def _on_begin(self, exercise_key: str, target_reps: int, lift_weight_lbs: Optional[float] = None) -> None:
        ex = make_exercise(exercise_key)
        display = EXERCISE_DISPLAY.get(exercise_key, exercise_key.upper())
        self._home.pack_forget()
        self._history.pack_forget()
        self._self.pack_forget()
        self._settings.pack_forget()
        self._nav.pack_forget()
        self._recording = RecordingSession(
            self._content,
            exercise_module=ex,
            exercise_display=display,
            target_reps=target_reps,
            lift_weight_lbs=lift_weight_lbs,
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
    enable_windows_dpi_awareness()
    root = tk.Tk()
    apply_tk_scaling(root)

    profile = load_profile()
    if needs_onboarding(profile):
        dlg = OnboardingDialog(root, on_saved=save_profile)
        if dlg.cancelled:
            try:
                root.destroy()
            except tk.TclError:
                pass
            return
        profile = load_profile()

    first = (profile.first_name if profile else "").strip() or "there"

    FormLogicApp(root, first_name=first)
    root.mainloop()


if __name__ == "__main__":
    main()
