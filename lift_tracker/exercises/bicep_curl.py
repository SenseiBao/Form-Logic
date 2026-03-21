from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from lift_tracker.exercises.base import Exercise, ExerciseResult
from lift_tracker.geometry import angle_degrees
from lift_tracker.pose.landmarks import LandmarkFrame, PoseLandmark


class CurlPhase(Enum):
    UNKNOWN = auto()
    BOTTOM = auto()
    CONCENTRIC = auto()
    TOP = auto()
    ECCENTRIC = auto()


@dataclass
class BicepCurlConfig:
    extended_angle_min_deg: float = 150.0
    flexed_angle_max_deg: float = 55.0

    # --- STRICT REP COUNTER ---
    # The elbow MUST bend past this 90-degree mark for the rep to count
    min_flexion_for_rep_deg: float = 90.0

    min_vis: float = 0.20
    angle_ema_alpha: float = 0.35
    min_rep_interval_s: float = 0.8


class BicepCurlExercise(Exercise):
    id = "bicep_curl"

    def __init__(self, config: Optional[BicepCurlConfig] = None) -> None:
        self.cfg = config or BicepCurlConfig()
        self.reset()

    def reset(self) -> None:
        self._ema_angle: Optional[float] = None
        self._prev_t: Optional[float] = None
        self._prev_angle: Optional[float] = None
        self._phase = CurlPhase.UNKNOWN

        self._rep_count = 0
        self._last_rep_end_t = 0.0
        self._rep_cycle_start_t: Optional[float] = None

        # Live Rep Trackers
        self._current_max_conc_depth = 0.0
        self._current_max_ecc_depth = 0.0
        self._current_max_lean = 0.0

        # Strict angle tracker (resets to 999 every rep)
        self._current_min_angle = 999.0

        # Arrays for Averages
        self._rep_durations: List[float] = []
        self._rep_conc_depths: List[float] = []
        self._rep_ecc_depths: List[float] = []
        self._rep_max_leans: List[float] = []

    def _conc_depth_percent(self, elbow_angle_deg: float) -> float:
        ext = float(self.cfg.extended_angle_min_deg)
        flex = float(self.cfg.flexed_angle_max_deg)
        span = max(1e-6, ext - flex)
        return float(max(0.0, min(100.0, (ext - elbow_angle_deg) / span * 100.0)))

    def _ecc_depth_percent(self, elbow_angle_deg: float) -> float:
        ext = float(self.cfg.extended_angle_min_deg)
        flex = float(self.cfg.flexed_angle_max_deg)
        span = max(1e-6, ext - flex)
        return float(max(0.0, min(100.0, (elbow_angle_deg - flex) / span * 100.0)))

    def _torso_angle(self, lm: LandmarkFrame) -> Tuple[Optional[float], bool]:
        """Calculates back lean angle relative to a vertical line, auto-selecting the visible side."""
        pl = PoseLandmark

        vl = (float(lm.visibility[pl.LEFT_SHOULDER]) + float(lm.visibility[pl.LEFT_HIP])) / 2.0
        vr = (float(lm.visibility[pl.RIGHT_SHOULDER]) + float(lm.visibility[pl.RIGHT_HIP])) / 2.0

        if vl < self.cfg.min_vis and vr < self.cfg.min_vis:
            return None, False

        # Auto-Select the side facing the camera
        if vl >= vr:
            s, h = lm.xy[pl.LEFT_SHOULDER], lm.xy[pl.LEFT_HIP]
        else:
            s, h = lm.xy[pl.RIGHT_SHOULDER], lm.xy[pl.RIGHT_HIP]

        dx = s[0] - h[0]
        dy = s[1] - h[1]
        angle_rad = math.atan2(abs(dx), abs(dy))
        return float(math.degrees(angle_rad)), True

    def _elbow_angle(self, lm: LandmarkFrame) -> Tuple[Optional[float], bool]:
        """Calculates the angle of the elbow joint, auto-selecting the arm closest to the camera."""
        pl = PoseLandmark

        vl = (float(lm.visibility[pl.LEFT_SHOULDER]) + float(lm.visibility[pl.LEFT_ELBOW]) + float(lm.visibility[pl.LEFT_WRIST])) / 3.0
        vr = (float(lm.visibility[pl.RIGHT_SHOULDER]) + float(lm.visibility[pl.RIGHT_ELBOW]) + float(lm.visibility[pl.RIGHT_WRIST])) / 3.0

        if vl < self.cfg.min_vis and vr < self.cfg.min_vis:
            return None, False

        # SIDE-VIEW FIX: Stop blending, purely isolate the best arm!
        if vl >= vr:
            s, e, w = lm.xy[pl.LEFT_SHOULDER], lm.xy[pl.LEFT_ELBOW], lm.xy[pl.LEFT_WRIST]
        else:
            s, e, w = lm.xy[pl.RIGHT_SHOULDER], lm.xy[pl.RIGHT_ELBOW], lm.xy[pl.RIGHT_WRIST]

        a = angle_degrees(s, e, w)
        if math.isnan(a):
            return None, False
        return float(a), True

    def _update_phase(self, t: float, ang: float, dang_dt: float) -> None:
        ext = self.cfg.extended_angle_min_deg
        flex = self.cfg.flexed_angle_max_deg

        if self._phase in (CurlPhase.UNKNOWN, CurlPhase.BOTTOM):
            if ang >= ext - 15.0:
                self._phase = CurlPhase.BOTTOM
            elif ang < ext - 15.0 and dang_dt < -5.0:
                self._phase = CurlPhase.CONCENTRIC
                self._rep_cycle_start_t = t
                self._current_max_conc_depth = 0.0
                self._current_max_ecc_depth = 0.0
                self._current_max_lean = 0.0
                self._current_min_angle = ang

        elif self._phase == CurlPhase.CONCENTRIC:
            if ang <= flex + 15.0 and dang_dt > -5.0:
                self._phase = CurlPhase.TOP
            elif dang_dt > 15.0:
                self._phase = CurlPhase.ECCENTRIC

        elif self._phase == CurlPhase.TOP:
            if ang > flex + 15.0 and dang_dt > 5.0:
                self._phase = CurlPhase.ECCENTRIC

        elif self._phase == CurlPhase.ECCENTRIC:
            if ang >= ext - 20.0 and dang_dt < 5.0:
                self._phase = CurlPhase.BOTTOM
                # Check if the arm bent far enough to count!
                had_depth = self._current_min_angle <= self.cfg.min_flexion_for_rep_deg
                self._try_count_rep(t, had_depth)

            elif dang_dt < -15.0:
                had_depth = self._current_min_angle <= self.cfg.min_flexion_for_rep_deg
                self._try_count_rep(t, had_depth)

                self._phase = CurlPhase.CONCENTRIC
                self._rep_cycle_start_t = t
                self._current_max_conc_depth = 0.0
                self._current_max_ecc_depth = 0.0
                self._current_max_lean = 0.0
                self._current_min_angle = ang

    def _try_count_rep(self, t: float, had_depth: bool) -> None:
        if t - self._last_rep_end_t < self.cfg.min_rep_interval_s:
            return

        # Reject half-reps instantly
        if not had_depth:
            return

        self._rep_count += 1
        self._last_rep_end_t = t

        if self._rep_cycle_start_t is not None:
            self._rep_durations.append(max(0.0, t - self._rep_cycle_start_t))

        self._rep_conc_depths.append(self._current_max_conc_depth)
        self._rep_ecc_depths.append(self._current_max_ecc_depth)
        self._rep_max_leans.append(self._current_max_lean)

        self._rep_cycle_start_t = None

    def update(self, t: float, landmarks: LandmarkFrame) -> ExerciseResult:
        ang, ok = self._elbow_angle(landmarks)
        if not ok or ang is None:
            return ExerciseResult(self.id, False, {"visible": False}, {})

        if self._prev_t is None:
            self._prev_t = t
            self._prev_angle = ang

        dt = max(1e-6, t - self._prev_t)
        raw_dang = (ang - self._prev_angle) / dt
        self._prev_t = t
        self._prev_angle = ang

        a = self.cfg.angle_ema_alpha
        if self._ema_angle is None:
            self._ema_angle = ang
        else:
            self._ema_angle = a * ang + (1.0 - a) * self._ema_angle
        sm = float(self._ema_angle)

        self._update_phase(t, sm, raw_dang)

        conc_pct = self._conc_depth_percent(sm)
        ecc_pct = self._ecc_depth_percent(sm)
        torso_ang, torso_ok = self._torso_angle(landmarks)

        if self._rep_cycle_start_t is not None:
            # Track the deepest point the arm reaches during this active rep
            self._current_min_angle = min(self._current_min_angle, sm)

            self._current_max_conc_depth = max(self._current_max_conc_depth, conc_pct)
            self._current_max_ecc_depth = max(self._current_max_ecc_depth, ecc_pct)
            if torso_ok and torso_ang is not None:
                self._current_max_lean = max(self._current_max_lean, torso_ang)

        metrics: Dict[str, Any] = {
            "visible": True,
            "phase": self._phase.name,
            "rep_count": self._rep_count,
            "elbow_angle_deg": round(sm, 1),
            "conc_depth_percent": round(conc_pct, 1),
            "ecc_depth_percent": round(ecc_pct, 1),
        }

        if torso_ok and torso_ang is not None:
            metrics["torso_angle_deg"] = round(torso_ang, 1)

        if self._rep_cycle_start_t is not None:
            metrics["rep_speed_timer_s"] = round(max(0.0, t - self._rep_cycle_start_t), 2)

        if self._rep_durations:
            metrics["average_rep_duration_s"] = round(sum(self._rep_durations) / len(self._rep_durations), 2)
        if self._rep_conc_depths:
            metrics["average_conc_depth"] = round(sum(self._rep_conc_depths) / len(self._rep_conc_depths), 1)
        if self._rep_ecc_depths:
            metrics["average_ecc_depth"] = round(sum(self._rep_ecc_depths) / len(self._rep_ecc_depths), 1)
        if self._rep_max_leans:
            metrics["average_max_lean_deg"] = round(sum(self._rep_max_leans) / len(self._rep_max_leans), 1)

        return ExerciseResult(self.id, True, metrics, {})