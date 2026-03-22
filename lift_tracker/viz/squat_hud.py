"""Styled on-frame metrics HUD matching the mockup."""

from __future__ import annotations

from typing import Any, Dict, Tuple

import cv2
import numpy as np


# ---------- helpers ----------

def _rounded_rect(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    radius: int,
    thickness: int = -1,
) -> None:
    x1, y1 = pt1
    x2, y2 = pt2
    r = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))

    if thickness < 0:
        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1)
        cv2.circle(img, (x1 + r, y1 + r), r, color, -1)
        cv2.circle(img, (x2 - r, y1 + r), r, color, -1)
        cv2.circle(img, (x1 + r, y2 - r), r, color, -1)
        cv2.circle(img, (x2 - r, y2 - r), r, color, -1)
    else:
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness)
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness)
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness)
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)


def _put_text(
    img: np.ndarray,
    text: str,
    org: Tuple[int, int],
    scale: float = 1.0,
    color: Tuple[int, int, int] = (20, 20, 20),
    thickness: int = 2,
    anchor: str = "left",
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = org

    if anchor == "center":
        x -= w // 2
    elif anchor == "right":
        x -= w

    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def _pill(
    img: np.ndarray,
    text: str,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    bg: Tuple[int, int, int] = (210, 210, 210),
    fg: Tuple[int, int, int] = (20, 20, 20),
    scale: float = 1.0,
    thickness: int = 2,
) -> None:
    _rounded_rect(img, pt1, pt2, bg, radius=(pt2[1] - pt1[1]) // 2, thickness=-1)
    cx = (pt1[0] + pt2[0]) // 2
    cy = (pt1[1] + pt2[1]) // 2 + 12
    _put_text(img, text, (cx, cy), scale=scale, color=fg, thickness=thickness, anchor="center")


def _fmt_percent(v: Any, decimals: int = 0) -> str:
    return f"{float(v):.{decimals}f}%"


def _fmt_seconds(v: Any, decimals: int = 2) -> str:
    return f"{float(v):.{decimals}f} s"


# ---------- main HUD ----------

def draw_squat_hud(frame_bgr: np.ndarray, metrics: Dict[str, Any]) -> None:
    """
    Draw a polished right-side metrics HUD similar to the provided mockup.
    The video remains visible underneath; this draws UI directly onto frame_bgr.
    """
    h, w = frame_bgr.shape[:2]

    # --- colors ---
    panel_bg = (245, 245, 245)
    pill_bg = (214, 214, 214)
    text_color = (20, 20, 20)

    # --- optional full-frame faded background for cleaner UI ---
    overlay = frame_bgr.copy()
    overlay[:] = panel_bg
    cv2.addWeighted(overlay, 0.88, frame_bgr, 0.12, 0, frame_bgr)

    # --- left preview panel placeholder / framing panel ---
    left_x1 = int(w * 0.05)
    left_y1 = int(h * 0.07)
    left_x2 = int(w * 0.61)
    left_y2 = int(h * 0.92)
    _rounded_rect(frame_bgr, (left_x1, left_y1), (left_x2, left_y2), (220, 220, 220), radius=28, thickness=-1)

    # --- right info area anchors ---
    rx = int(w * 0.65)
    top_y = int(h * 0.10)
    line_gap = 92

    # --- top row: date + time ---
    date_text = str(metrics.get("date", "March 21, 2026"))
    time_text = str(metrics.get("clock_time", "5:19:20"))

    _put_text(frame_bgr, date_text, (rx, top_y), scale=1.2, color=text_color, thickness=2)
    _put_text(frame_bgr, time_text, (w - 110, top_y), scale=1.2, color=text_color, thickness=2, anchor="right")

    # --- row 1: chosen exercise ---
    y = top_y + 80
    _put_text(frame_bgr, "Chosen Exercise", (rx, y), scale=1.15, color=text_color, thickness=2)
    _pill(
        frame_bgr,
        str(metrics.get("exercise", "SQUAT")).upper(),
        (w - 260, y - 40),
        (w - 85, y + 5),
        bg=pill_bg,
        fg=text_color,
        scale=1.0,
        thickness=2,
    )

    # --- row 2: reps to go ---
    y += line_gap
    reps_to_go = metrics.get("reps_to_go")
    if reps_to_go is None:
        if metrics.get("count_mode"):
            reps_to_go = "open"
        else:
            target_reps = metrics.get("target_reps", 0)
            rep_count = metrics.get("rep_count", 0)
            reps_to_go = max(0, int(target_reps) - int(rep_count)) if target_reps else 0

    rlabel = "Mode:" if metrics.get("count_mode") else "Reps to Go:"
    _put_text(frame_bgr, rlabel, (rx, y), scale=1.15, color=text_color, thickness=2)
    _pill(
        frame_bgr,
        str(reps_to_go),
        (w - 260, y - 40),
        (w - 85, y + 5),
        bg=pill_bg,
        fg=text_color,
        scale=1.1,
        thickness=2,
    )

    # --- row 3: avg duration ---
    y += line_gap
    avg_duration = metrics.get("average_rep_duration_s", 1.09)
    _put_text(frame_bgr, "Avg Duration:", (rx, y), scale=1.0, color=text_color, thickness=2)
    _put_text(
        frame_bgr,
        _fmt_seconds(avg_duration, 2),
        (w - 125, y),
        scale=1.0,
        color=text_color,
        thickness=2,
        anchor="right",
    )

    # --- mid title ---
    section_y = int(h * 0.53)
    _put_text(frame_bgr, "Avg Depths", (int(w * 0.80), section_y), scale=1.15, color=text_color, thickness=2, anchor="center")

    # --- concentric / eccentric values ---
    label_x = rx
    value_x = w - 110
    y1 = section_y + 90
    y2 = y1 + 72

    conc = metrics.get("average_conc_depth", metrics.get("conc_depth_percent", 67))
    ecc = metrics.get("average_ecc_depth", metrics.get("ecc_depth_percent", 75.9))

    conc_decimals = 0 if float(conc).is_integer() else 1
    ecc_decimals = 0 if float(ecc).is_integer() else 1

    _put_text(frame_bgr, "Concentric:", (label_x, y1), scale=1.05, color=text_color, thickness=2)
    _put_text(frame_bgr, _fmt_percent(conc, conc_decimals), (value_x, y1), scale=1.05, color=text_color, thickness=2, anchor="right")

    _put_text(frame_bgr, "Eccentric:", (label_x, y2), scale=1.05, color=text_color, thickness=2)
    _put_text(frame_bgr, _fmt_percent(ecc, ecc_decimals), (value_x, y2), scale=1.05, color=text_color, thickness=2, anchor="right")
