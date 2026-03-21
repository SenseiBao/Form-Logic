"""Universal on-frame metrics HUD for all exercises."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def _put_lines(
    frame_bgr: np.ndarray,
    lines: List[str],
    origin: Tuple[int, int] = (12, 28),
    *,
    line_height: int = 22,
    font_scale: float = 0.55,
    text_color: Tuple[int, int, int] = (240, 240, 255),
    outline_color: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    x, y0 = origin
    for i, line in enumerate(lines):
        y = y0 + i * line_height
        cv2.putText(frame_bgr, line, (x, y), font, font_scale, outline_color, 3, cv2.LINE_AA)

        # Make the Cheap Rep Alert pop out in Red!
        if "Half Rep" in line:
            cv2.putText(frame_bgr, line, (x, y), font, font_scale, (0, 0, 255), 2, cv2.LINE_AA)
        elif "Good Rep" in line:
            cv2.putText(frame_bgr, line, (x, y), font, font_scale, (0, 255, 0), 2, cv2.LINE_AA)
        else:
            cv2.putText(frame_bgr, line, (x, y), font, font_scale, text_color, 1, cv2.LINE_AA)


def draw_squat_hud(frame_bgr: np.ndarray, metrics: Dict[str, Any]) -> None:
    """Draw exercise form summary on `frame_bgr` in place."""
    if not metrics.get("visible"):
        _put_lines(
            frame_bgr,
            ["No pose / low visibility"],
            origin=(12, 28),
        )
        return

    lines: List[str] = []

    # --- CHEAT ALERTS ---
    if "cheat_alert" in metrics:
        lines.append(f"STATUS: {metrics['cheat_alert']}")
        lines.append("") # Spacing

    # --- CORE METRICS ---
    if "rep_count" in metrics:
        lines.append(f"Reps: {metrics['rep_count']}")
    if "phase" in metrics:
        lines.append(f"Phase: {metrics['phase']}")

    # --- JOINT ANGLES & VECTORS ---
    if "knee_angle_deg" in metrics:
        lines.append(f"Hip-knee-ankle: {float(metrics['knee_angle_deg']):.1f} deg")
    if "elbow_angle_deg" in metrics:
        lines.append(f"Elbow Angle: {float(metrics['elbow_angle_deg']):.1f} deg")
    if "head_above_bar" in metrics:
        lines.append(f"Head Cleared Bar?: {metrics['head_above_bar']}")

    lines.append("") # Spacing

    # --- SQUAT DEPTH ---
    if "depth_percent" in metrics:
        lines.append(f"Current Depth: {float(metrics['depth_percent']):.0f}%")
    if "average_depth_percent" in metrics:
        lines.append(f"Avg Depth (per rep): {float(metrics['average_depth_percent']):.1f}%")

    # --- PULLUP / CURL DEPTH ---
    if "conc_depth_percent" in metrics:
        lines.append(f"Concentric Depth (Up): {float(metrics['conc_depth_percent']):.0f}%")
    if "ecc_depth_percent" in metrics:
        lines.append(f"Eccentric Depth (Down): {float(metrics['ecc_depth_percent']):.0f}%")
    if "average_conc_depth" in metrics:
        lines.append(f"Avg Conc Depth: {float(metrics['average_conc_depth']):.1f}%")
    if "average_ecc_depth" in metrics:
        lines.append(f"Avg Ecc Depth: {float(metrics['average_ecc_depth']):.1f}%")

    lines.append("") # Spacing

    # --- CHEAT DETECTOR / BACK LEAN ---
    if "torso_angle_deg" in metrics:
        lines.append(f"Current Back Lean: {float(metrics['torso_angle_deg']):.1f} deg (from vertical)")
    if "average_max_lean_deg" in metrics:
        lines.append(f"Avg Max Lean (per rep): {float(metrics['average_max_lean_deg']):.1f} deg")

    lines.append("") # Spacing

    # --- TIMERS ---
    if "rep_speed_timer_s" in metrics:
        lines.append(f"Current Rep Time: {float(metrics['rep_speed_timer_s']):.2f}s")
    if "average_rep_duration_s" in metrics:
        lines.append(f"Avg Rep Time: {float(metrics['average_rep_duration_s']):.2f}s")

    if not lines:
        return

    h = frame_bgr.shape[0]
    _put_lines(frame_bgr, lines, origin=(12, min(28, h - 10)))