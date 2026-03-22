from __future__ import annotations

import queue
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

from lift_tracker.pipeline import TrackingPipeline
from lift_tracker.pose.skeleton import draw_pose_skeleton

from ui import theme
from ui.components import RoundedPanel, ScrollableFrame

TRACKING_CALLOUT: Dict[str, str] = {
    "squat": "For optimal tracking, stand sideways to the camera so your profile is visible.",
    "bicep_curl": "For optimal tracking, stand sideways to the camera so your profile is visible.",
    "pullup": "For optimal tracking, face away from the camera so your back is clearly visible.",
}

LogCallback = Callable[[Dict[str, Any]], None]

_WARMUP_READS = 15
_WARMUP_DISCARD = 5


def open_capture() -> Tuple[Optional[cv2.VideoCapture], str]:
    """
    Open the first working webcam. On macOS, prefer AVFoundation.
    Returns (capture, "") on success, or (None, reason) on failure.
    """
    indices = (0, 1, 2)
    last_err = "Could not open any camera index (0–2)."
    avf = getattr(cv2, "CAP_AVFOUNDATION", None)

    for idx in indices:
        if sys.platform == "darwin" and avf is not None:
            cap = cv2.VideoCapture(idx, avf)
        else:
            cap = cv2.VideoCapture(idx)

        if not cap.isOpened():
            cap.release()
            last_err = f"Index {idx}: isOpened() is false."
            continue

        got_frame = False
        for _ in range(_WARMUP_READS):
            ok, frame = cap.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                got_frame = True
                break
            time.sleep(0.05)

        if not got_frame:
            cap.release()
            last_err = f"Index {idx}: opened but no frames."
            continue

        for _ in range(_WARMUP_DISCARD):
            cap.read()

        return cap, ""

    return None, last_err


def _synthetic_error_bgr(message: str, tw: int, th: int) -> np.ndarray:
    """BGR placeholder for camera failures at preview size (tw x th)."""
    tw = max(160, int(tw))
    th = max(120, int(th))
    img = np.full((th, tw, 3), 220, dtype=np.uint8)
    ref = 480.0
    scale = max(0.35, min(1.15, min(tw, th) / ref))
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.55 * scale
    thickness = max(1, min(3, int(round(2 * scale))))
    line_step = int(max(22, 34 * scale))
    y = int(th * 0.22)
    margin = int(max(16, 32 * scale))
    for line in message.split("\n"):
        if not line.strip():
            y += line_step // 2
            continue
        cv2.putText(
            img,
            line[:70],
            (margin, y),
            font,
            fs,
            (35, 35, 35),
            thickness,
            cv2.LINE_AA,
        )
        y += line_step
    return img


def _cover_bgr(frame_bgr: np.ndarray, tw: int, th: int) -> np.ndarray:
    """Uniform scale to cover (tw, th), then center-crop. No letterbox bars."""
    tw = max(1, int(tw))
    th = max(1, int(th))
    h, w = frame_bgr.shape[:2]
    if w < 1 or h < 1:
        return np.full((th, tw, 3), 220, dtype=np.uint8)
    scale = max(tw / w, th / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    x0 = (nw - tw) // 2
    y0 = (nh - th) // 2
    x0 = max(0, min(x0, nw - tw))
    y0 = max(0, min(y0, nh - th))
    return resized[y0 : y0 + th, x0 : x0 + tw].copy()


def _depth_pair(metrics: Dict[str, Any]) -> Tuple[str, str]:
    """Return (concentric %, eccentric %) display strings."""
    if "average_conc_depth" in metrics and "average_ecc_depth" in metrics:
        c, e = metrics["average_conc_depth"], metrics["average_ecc_depth"]
        return f"{float(c):.1f}%", f"{float(e):.1f}%"
    if "conc_depth_percent" in metrics and "ecc_depth_percent" in metrics:
        c, e = metrics["conc_depth_percent"], metrics["ecc_depth_percent"]
        cd = 0 if float(c).is_integer() else 1
        ed = 0 if float(e).is_integer() else 1
        return f"{float(c):.{cd}f}%", f"{float(e):.{ed}f}%"
    if "average_depth_percent" in metrics:
        v = metrics["average_depth_percent"]
        s = f"{float(v):.1f}%"
        return s, s
    if "depth_percent" in metrics:
        v = metrics["depth_percent"]
        s = f"{float(v):.1f}%"
        return s, s
    return "—", "—"


def _fmt_num(v: Any, decimals: int = 1) -> str:
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


class RecordingSession(tk.Frame):
    """Embedded recording UI (replaces separate Toplevel)."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        exercise_module: Any,
        exercise_display: str,
        target_reps: Optional[int],
        on_finished: LogCallback,
        lift_weight_lbs: Optional[float] = None,
        min_w: int = 960,
        min_h: int = 620,
    ) -> None:
        super().__init__(parent, bg=theme.METRICS_PANEL, highlightthickness=0, bd=0)

        self._exercise_module = exercise_module
        self._exercise_display = exercise_display.upper()
        self._count_mode = target_reps is None
        self._target_reps: Optional[int] = None if self._count_mode else max(1, int(target_reps))
        self._lift_weight_lbs = lift_weight_lbs
        self._on_finished = on_finished

        self._root = self.winfo_toplevel()
        self._saved_title = self._root.title()
        self._saved_minsize = (self._root.minsize()[0], self._root.minsize()[1])
        self._root.title("Form-Logic — Workout")
        self._root.minsize(min_w, min_h)
        self._root.protocol("WM_DELETE_WINDOW", self._finish)

        self._stop = threading.Event()
        self._frame_q: queue.Queue[Tuple[np.ndarray, Dict[str, Any]]] = queue.Queue(maxsize=1)
        self._thread: Optional[threading.Thread] = None
        self._last_metrics: Dict[str, Any] = {}
        self._metrics_carry: Dict[str, Any] = {}

        self._photo: Optional[ImageTk.PhotoImage] = None
        self._finishing_target: bool = False
        self._completion_after_id: Optional[Any] = None
        self._completion_secs: int = 0

        self._preview_lock = threading.Lock()
        self._preview_tw: int = 640
        self._preview_th: int = 480

        self._build_ui()
        self._root.bind("<KeyPress-q>", self._on_key_finish)
        self._root.bind("<KeyPress-Q>", self._on_key_finish)
        self.update_idletasks()
        try:
            self._root.lift()
            self._root.focus_force()
        except tk.TclError:
            pass

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self.after(16, self._poll_queue)
        self._tick_clock()

    def _on_key_finish(self, _e: tk.Event) -> None:
        self._finish()

    def _on_video_lbl_configure(self, event: tk.Event) -> None:
        w, h = int(event.width), int(event.height)
        if w < 2 or h < 2:
            return
        with self._preview_lock:
            if abs(w - self._preview_tw) < 3 and abs(h - self._preview_th) < 3:
                return
            self._preview_tw, self._preview_th = w, h

    def _preview_dimensions(self) -> Tuple[int, int]:
        with self._preview_lock:
            return max(2, self._preview_tw), max(2, self._preview_th)

    def _cancel_completion_timer(self) -> None:
        if self._completion_after_id is not None:
            try:
                self.after_cancel(self._completion_after_id)
            except tk.TclError:
                pass
            self._completion_after_id = None
        self._finishing_target = False
        try:
            self._lbl_completion.config(text="")
        except tk.TclError:
            pass

    def _start_completion_countdown(self) -> None:
        if self._finishing_target or getattr(self, "_session_closed", False):
            return
        self._finishing_target = True
        self._completion_secs = 3
        try:
            self._lbl_completion.config(text="Target reps complete — stopping in 3…")
        except tk.TclError:
            pass
        self._completion_after_id = self.after(1000, self._tick_completion)

    def _tick_completion(self) -> None:
        self._completion_after_id = None
        if not self.winfo_exists() or getattr(self, "_session_closed", False):
            return
        self._completion_secs -= 1
        if self._completion_secs <= 0:
            try:
                self._lbl_completion.config(text="")
            except tk.TclError:
                pass
            self._finish()
            return
        try:
            self._lbl_completion.config(
                text=f"Target reps complete — stopping in {self._completion_secs}…"
            )
        except tk.TclError:
            pass
        self._completion_after_id = self.after(1000, self._tick_completion)

    def _maybe_start_completion(self, rep_count: int) -> None:
        if self._finishing_target or getattr(self, "_session_closed", False):
            return
        if self._count_mode or self._target_reps is None:
            return
        if rep_count < self._target_reps:
            return
        if "rep_count" not in self._metrics_carry:
            return
        self._start_completion_countdown()

    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg=theme.METRICS_PANEL, highlightthickness=0, bd=0)
        outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        outer.grid_columnconfigure(0, weight=62, uniform="rec")
        outer.grid_columnconfigure(1, weight=38, uniform="rec")
        outer.grid_rowconfigure(0, weight=1)

        left = tk.Frame(outer, bg=theme.METRICS_PANEL, highlightthickness=0, bd=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        left_panel = RoundedPanel(
            left,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=theme.VIDEO_CARD_RGB,
            fill_alpha=255,
            outline_rgb=theme.CARD_OUTLINE_RGB,
        )
        left_panel.pack(fill=tk.BOTH, expand=True)
        self._video_wrap = left_panel.body()

        callout = tk.Frame(
            self._video_wrap,
            bg=theme.CARD_WHITE,
            highlightthickness=1,
            highlightbackground="#E4E9EF",
            bd=0,
        )
        callout.place(relx=0.5, y=12, anchor="n")
        eid_hint = getattr(self._exercise_module, "id", "") or ""
        hint_text = TRACKING_CALLOUT.get(eid_hint, TRACKING_CALLOUT["squat"])
        self._callout_lbl = tk.Label(
            callout,
            text=hint_text,
            font=theme.FONT_SMALL,
            fg=theme.TEXT_PRIMARY,
            bg=theme.CARD_WHITE,
            padx=14,
            pady=6,
            wraplength=320,
            justify="center",
        )
        self._callout_lbl.pack()

        self._video_lbl = tk.Label(self._video_wrap, bg=theme.VIDEO_CARD_BG, highlightthickness=0, bd=0)
        self._video_lbl.pack(fill=tk.BOTH, expand=True)
        self._video_lbl.bind("<Configure>", self._on_video_lbl_configure)

        right = tk.Frame(outer, bg=theme.METRICS_PANEL, highlightthickness=0, bd=0)
        right.grid(row=0, column=1, sticky="nsew")

        right_panel = RoundedPanel(
            right,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=theme.METRICS_CARD_RGB,
            fill_alpha=255,
            outline_rgb=theme.CARD_OUTLINE_RGB,
        )
        right_panel.pack(fill=tk.BOTH, expand=True)
        panel = right_panel.body()
        panel.grid_columnconfigure(0, weight=1)

        stop_row = tk.Frame(panel, bg=theme.METRICS_CARD_BG)
        stop_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        tk.Button(
            stop_row,
            text="Stop workout",
            font=theme.FONT_SUB,
            command=self._finish,
            padx=12,
            pady=10,
            bg=theme.CARD_WHITE,
            activebackground=theme.PILL_GREY,
            fg=theme.TEXT_PRIMARY,
            activeforeground=theme.TEXT_PRIMARY,
            highlightbackground=theme.CARD_BORDER,
            highlightthickness=1,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(fill=tk.X)

        self._lbl_completion = tk.Label(
            panel,
            text="",
            font=theme.FONT_SMALL,
            fg="#B45309",
            bg=theme.METRICS_CARD_BG,
        )
        self._lbl_completion.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        head = tk.Frame(panel, bg=theme.METRICS_CARD_BG)
        head.grid(row=2, column=0, sticky="new", padx=16, pady=(0, 4))
        self._date_hdr = tk.Label(
            head,
            text="",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.METRICS_CARD_BG,
            anchor="w",
        )
        self._date_hdr.pack(side=tk.LEFT)
        self._clock_lbl = tk.Label(
            head,
            text="",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.METRICS_CARD_BG,
            anchor="e",
        )
        self._clock_lbl.pack(side=tk.RIGHT)

        scroll = ScrollableFrame(panel, bg=theme.METRICS_CARD_BG)
        scroll.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 8))
        panel.grid_rowconfigure(3, weight=1)

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            scroll._canvas.bind(seq, scroll.on_mousewheel)  # type: ignore[attr-defined]

        body = scroll.body()

        self._lbl_exercise = tk.Label(body, text="", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w")
        self._lbl_exercise.pack(fill=tk.X, pady=4)
        self._pill_ex = tk.Label(body, text="", font=theme.FONT_BODY, bg=theme.PILL_GREY, padx=12, pady=6, anchor="w")
        self._pill_ex.pack(fill=tk.X, pady=(0, 12))

        self._lbl_reps = tk.Label(body, text="", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w")
        self._lbl_reps.pack(fill=tk.X, pady=4)
        self._pill_reps = tk.Label(body, text="", font=theme.FONT_BODY, bg=theme.PILL_GREY, padx=12, pady=6, anchor="w")
        self._pill_reps.pack(fill=tk.X, pady=(0, 12))
        if self._count_mode:
            self._lbl_reps.config(text="Mode:")
            self._pill_reps.config(text="Rep counter (no target)")
        else:
            self._lbl_reps.config(text="Reps left:")
            self._pill_reps.config(text=str(self._target_reps))

        row_dur = tk.Frame(body, bg=theme.METRICS_CARD_BG)
        row_dur.pack(fill=tk.X, pady=4)
        tk.Label(row_dur, text="Avg Duration:", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
        self._lbl_avg_dur = tk.Label(row_dur, text="—", font=theme.FONT_BODY, fg=theme.TEXT_MUTED, bg=theme.METRICS_CARD_BG, anchor="e")
        self._lbl_avg_dur.pack(side=tk.RIGHT)

        tk.Label(
            body,
            text="Avg Depths",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.METRICS_CARD_BG,
        ).pack(pady=(20, 8))

        row_c = tk.Frame(body, bg=theme.METRICS_CARD_BG)
        row_c.pack(fill=tk.X, pady=4)
        tk.Label(row_c, text="Concentric:", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
        self._lbl_conc = tk.Label(row_c, text="—", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="e")
        self._lbl_conc.pack(side=tk.RIGHT)

        row_e = tk.Frame(body, bg=theme.METRICS_CARD_BG)
        row_e.pack(fill=tk.X, pady=4)
        tk.Label(row_e, text="Eccentric:", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
        self._lbl_ecc = tk.Label(row_e, text="—", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="e")
        self._lbl_ecc.pack(side=tk.RIGHT)

        tk.Label(
            body,
            text="Details",
            font=theme.FONT_HEADING,
            fg=theme.TEXT_PRIMARY,
            bg=theme.METRICS_CARD_BG,
        ).pack(pady=(18, 8))

        row_rc = tk.Frame(body, bg=theme.METRICS_CARD_BG)
        row_rc.pack(fill=tk.X, pady=3)
        tk.Label(row_rc, text="Reps completed:", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
        self._lbl_reps_done = tk.Label(row_rc, text="0", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="e")
        self._lbl_reps_done.pack(side=tk.RIGHT)

        row_ph = tk.Frame(body, bg=theme.METRICS_CARD_BG)
        row_ph.pack(fill=tk.X, pady=3)
        tk.Label(row_ph, text="Phase:", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
        self._lbl_phase = tk.Label(row_ph, text="—", font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="e")
        self._lbl_phase.pack(side=tk.RIGHT)

        eid = getattr(self._exercise_module, "id", "") or ""

        def add_detail_row(left_text: str) -> tk.Label:
            row = tk.Frame(body, bg=theme.METRICS_CARD_BG)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=left_text, font=theme.FONT_BODY, bg=theme.METRICS_CARD_BG, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="—", font=theme.FONT_SMALL, fg=theme.TEXT_MUTED, bg=theme.METRICS_CARD_BG, anchor="e")
            val.pack(side=tk.RIGHT)
            return val

        self._lbl_d1 = self._lbl_d2 = self._lbl_d3 = self._lbl_d4 = self._lbl_d5 = None
        if eid == "squat":
            self._lbl_d1 = add_detail_row("Knee angle:")
            self._lbl_d2 = add_detail_row("Depth:")
            self._lbl_d3 = add_detail_row("Avg depth (session):")
            self._lbl_d4 = add_detail_row("Torso lean:")
            self._lbl_d5 = add_detail_row("Avg max lean:")
        elif eid == "bicep_curl":
            self._lbl_d1 = add_detail_row("Elbow angle:")
            self._lbl_d2 = add_detail_row("Torso lean:")
            self._lbl_d3 = add_detail_row("Avg max lean:")
            self._lbl_d4 = None
            self._lbl_d5 = None
        elif eid == "pullup":
            self._lbl_d1 = add_detail_row("Elbow angle:")
            self._lbl_d2 = add_detail_row("Head above bar:")
            self._lbl_d3 = add_detail_row("Status:")
            self._lbl_d4 = None
            self._lbl_d5 = None

        self._date_hdr.config(text=datetime.now().strftime("%B %d, %Y"))
        self._lbl_exercise.config(text="Exercise:")
        self._pill_ex.config(text=self._exercise_display)

    def _tick_clock(self) -> None:
        if not self.winfo_exists():
            return
        self._clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _clear_detail_value_labels(self) -> None:
        for lbl in (self._lbl_d1, self._lbl_d2, self._lbl_d3, self._lbl_d4, self._lbl_d5):
            if lbl is not None:
                lbl.config(text="—", fg=theme.TEXT_MUTED)

    def _merge_into_carry(self, m: Dict[str, Any]) -> None:
        """Merge frame metrics; preserve session keys when pose-only payload is {visible: False}."""
        if set(m.keys()) == {"visible"}:
            self._metrics_carry["visible"] = bool(m["visible"])
            return
        self._metrics_carry.update(m)

    def _apply_metrics(self, m: Dict[str, Any]) -> None:
        self._last_metrics = dict(m)
        self._merge_into_carry(m)
        carry = self._metrics_carry
        visible = bool(m.get("visible", True))

        rep_count = int(carry.get("rep_count", 0))
        if self._count_mode:
            self._pill_reps.config(text="Rep counter (no target)")
        elif self._target_reps is not None:
            left = max(0, self._target_reps - rep_count)
            self._pill_reps.config(text=str(left))

        avg = carry.get("average_rep_duration_s")
        if avg is not None:
            self._lbl_avg_dur.config(text=f"{float(avg):.2f} s", fg=theme.TEXT_PRIMARY)
        else:
            live = m.get("live_rep_duration_s")
            if live is None:
                live = m.get("rep_speed_timer_s")
            if live is not None:
                self._lbl_avg_dur.config(text=f"{float(live):.2f} s", fg=theme.TEXT_PRIMARY)
            else:
                self._lbl_avg_dur.config(text="—", fg=theme.TEXT_MUTED)

        c_str, e_str = _depth_pair(carry)
        self._lbl_conc.config(text=c_str)
        self._lbl_ecc.config(text=e_str)

        self._lbl_reps_done.config(text=str(rep_count), fg=theme.TEXT_PRIMARY)

        eid = getattr(self._exercise_module, "id", "") or ""

        def _deg_from(src: Dict[str, Any], key: str) -> str:
            v = src.get(key)
            return f"{_fmt_num(v)} deg" if v is not None else "—"

        def _pct_from(src: Dict[str, Any], key: str, decimals: int = 1) -> str:
            v = src.get(key)
            return f"{_fmt_num(v, decimals)}%" if v is not None else "—"

        if not visible:
            self._lbl_phase.config(text="Pose lost", fg=theme.TEXT_MUTED)
            if eid == "squat":
                if self._lbl_d1 is not None:
                    self._lbl_d1.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d2 is not None:
                    self._lbl_d2.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d3 is not None:
                    self._lbl_d3.config(text=_pct_from(carry, "average_depth_percent"), fg=theme.TEXT_PRIMARY)
                if self._lbl_d4 is not None:
                    self._lbl_d4.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d5 is not None:
                    aml = carry.get("average_max_lean_deg")
                    self._lbl_d5.config(
                        text=_deg_from(carry, "average_max_lean_deg") if aml is not None else "—",
                        fg=theme.TEXT_PRIMARY,
                    )
            elif eid == "bicep_curl":
                if self._lbl_d1 is not None:
                    self._lbl_d1.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d2 is not None:
                    self._lbl_d2.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d3 is not None:
                    aml = carry.get("average_max_lean_deg")
                    self._lbl_d3.config(
                        text=_deg_from(carry, "average_max_lean_deg") if aml is not None else "—",
                        fg=theme.TEXT_PRIMARY,
                    )
            elif eid == "pullup":
                if self._lbl_d1 is not None:
                    self._lbl_d1.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d2 is not None:
                    self._lbl_d2.config(text="—", fg=theme.TEXT_MUTED)
                if self._lbl_d3 is not None:
                    st = carry.get("cheat_alert")
                    self._lbl_d3.config(text=str(st) if st is not None else "—", fg=theme.TEXT_PRIMARY)
            self._maybe_start_completion(rep_count)
            return

        ph = m.get("phase")
        self._lbl_phase.config(
            text=str(ph).replace("_", " ").title() if ph is not None else "—",
            fg=theme.TEXT_PRIMARY,
        )

        if eid == "squat":
            if self._lbl_d1 is not None:
                self._lbl_d1.config(text=_deg_from(m, "knee_angle_deg"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d2 is not None:
                self._lbl_d2.config(text=_pct_from(m, "depth_percent"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d3 is not None:
                self._lbl_d3.config(text=_pct_from(carry, "average_depth_percent"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d4 is not None:
                self._lbl_d4.config(text=_deg_from(m, "torso_angle_deg"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d5 is not None:
                aml = carry.get("average_max_lean_deg")
                self._lbl_d5.config(
                    text=_deg_from(carry, "average_max_lean_deg") if aml is not None else "—",
                    fg=theme.TEXT_PRIMARY,
                )
        elif eid == "bicep_curl":
            if self._lbl_d1 is not None:
                self._lbl_d1.config(text=_deg_from(m, "elbow_angle_deg"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d2 is not None:
                self._lbl_d2.config(text=_deg_from(m, "torso_angle_deg"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d3 is not None:
                aml = carry.get("average_max_lean_deg")
                self._lbl_d3.config(
                    text=_deg_from(carry, "average_max_lean_deg") if aml is not None else "—",
                    fg=theme.TEXT_PRIMARY,
                )
        elif eid == "pullup":
            if self._lbl_d1 is not None:
                self._lbl_d1.config(text=_deg_from(m, "elbow_angle_deg"), fg=theme.TEXT_PRIMARY)
            if self._lbl_d2 is not None:
                pct = m.get("head_clearance_pct")
                if pct is not None:
                    self._lbl_d2.config(text=f"{_fmt_num(pct)}%", fg=theme.TEXT_PRIMARY)
                else:
                    hab = m.get("head_above_bar")
                    self._lbl_d2.config(text=str(hab) if hab is not None else "—", fg=theme.TEXT_PRIMARY)
            if self._lbl_d3 is not None:
                st = m.get("cheat_alert")
                self._lbl_d3.config(text=str(st) if st is not None else "—", fg=theme.TEXT_PRIMARY)

        self._maybe_start_completion(rep_count)

    def _poll_queue(self) -> None:
        if not self.winfo_exists():
            return
        try:
            item = self._frame_q.get_nowait()
        except queue.Empty:
            self.after(16, self._poll_queue)
            return
        rgb, metrics = item
        self._apply_metrics(metrics)
        try:
            if rgb.dtype != np.uint8:
                rgb = np.clip(rgb, 0, 255).astype(np.uint8)
            if rgb.ndim != 3 or rgb.shape[2] != 3:
                raise ValueError(f"expected HxWx3 uint8 RGB, got shape={getattr(rgb, 'shape', None)} dtype={rgb.dtype}")
            img = Image.fromarray(rgb, mode="RGB")
            self._photo = ImageTk.PhotoImage(image=img, master=self)
            self._video_lbl.configure(image=self._photo, text="")
        except Exception:
            traceback.print_exc()
            try:
                self._video_lbl.configure(image="", text="Preview error — see terminal")
            except tk.TclError:
                pass
        self.after(16, self._poll_queue)

    def _capture_loop(self) -> None:
        cap, cam_err = open_capture()
        ex = self._exercise_module
        pipe = TrackingPipeline(ex)

        try:
            if cap is None:
                print(f"Form-Logic: camera failed: {cam_err}", file=sys.stderr)
                msg = (
                    "Camera unavailable.\n"
                    "Allow camera access in System Settings (Privacy),\n"
                    "or close other apps using the camera."
                )
                err_metrics: Dict[str, Any] = {
                    "target_reps": 0 if self._count_mode else self._target_reps,
                    "count_mode": self._count_mode,
                    "exercise": self._exercise_display,
                    "visible": False,
                }
                while not self._stop.is_set():
                    tw, th = self._preview_dimensions()
                    self._push_frame(_synthetic_error_bgr(msg, tw, th), err_metrics, passthrough=True)
                    time.sleep(0.15)
                return

            start_time = time.time()
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                remaining = int(5 - (time.time() - start_time)) + 1
                if remaining <= 0:
                    break
                display = frame.copy()
                h, w, _ = display.shape
                cv2.putText(
                    display,
                    str(remaining),
                    (w // 2 - 50, h // 2 + 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    5,
                    (255, 255, 255),
                    10,
                    cv2.LINE_AA,
                )
                self._push_frame(
                    display,
                    {
                        "target_reps": 0 if self._count_mode else self._target_reps,
                        "count_mode": self._count_mode,
                        "exercise": self._exercise_display,
                        "visible": True,
                    },
                )
                time.sleep(0.03)

            while not self._stop.is_set() and cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                packet = pipe.process_bgr(frame)
                display = frame.copy()
                if packet.landmarks is not None:
                    draw_pose_skeleton(display, packet.landmarks)
                m = dict(packet.exercise.metrics)
                m["target_reps"] = 0 if self._count_mode else self._target_reps
                m["count_mode"] = self._count_mode
                m["exercise"] = self._exercise_display
                self._push_frame(display, m)
                time.sleep(0.001)
        finally:
            if cap is not None:
                cap.release()
            pipe.close()

    def _push_frame(
        self,
        display_bgr: np.ndarray,
        metrics: Optional[Dict[str, Any]] = None,
        *,
        passthrough: bool = False,
    ) -> None:
        with self._preview_lock:
            tw, th = self._preview_tw, self._preview_th
        tw = max(2, tw)
        th = max(2, th)
        if passthrough:
            boxed = display_bgr
            if boxed.shape[0] != th or boxed.shape[1] != tw:
                boxed = cv2.resize(boxed, (tw, th), interpolation=cv2.INTER_AREA)
        else:
            boxed = _cover_bgr(display_bgr, tw, th)
        rgb = cv2.cvtColor(boxed, cv2.COLOR_BGR2RGB)
        m: Dict[str, Any]
        if metrics is not None:
            m = dict(metrics)
            m.setdefault("target_reps", 0 if self._count_mode else self._target_reps)
            m.setdefault("count_mode", self._count_mode)
            m.setdefault("exercise", self._exercise_display)
        else:
            m = {
                "target_reps": 0 if self._count_mode else self._target_reps,
                "count_mode": self._count_mode,
                "exercise": self._exercise_display,
                "visible": True,
            }
        try:
            self._frame_q.put_nowait((rgb, m))
        except queue.Full:
            try:
                self._frame_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_q.put_nowait((rgb, m))
            except queue.Full:
                pass

    def _restore_root_chrome(self) -> None:
        try:
            self._root.title(self._saved_title)
            w, h = self._saved_minsize
            self._root.minsize(w, h)
            self._root.protocol("WM_DELETE_WINDOW", self._root.destroy)
            for seq in ("<KeyPress-q>", "<KeyPress-Q>"):
                self._root.unbind(seq)
        except tk.TclError:
            pass

    def _finish(self) -> None:
        if getattr(self, "_session_closed", False):
            return
        self._cancel_completion_timer()
        self._session_closed = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)

        summary = self._exercise_module.get_summary()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "exercise": self._exercise_module.id,
            "exercise_display": self._exercise_display,
            "metrics": summary,
        }
        if self._lift_weight_lbs is not None:
            log_entry["lift_weight_lbs"] = float(self._lift_weight_lbs)
        log_entry["count_mode"] = self._count_mode
        log_entry["target_reps"] = None if self._count_mode else self._target_reps
        self._restore_root_chrome()
        self._on_finished(log_entry)

        try:
            self.destroy()
        except tk.TclError:
            pass


RecordingWindow = RecordingSession
