from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from lift_tracker.exercises.base import Exercise, ExerciseResult
from lift_tracker.geometry import angle_degrees
from lift_tracker.pose.landmarks import LandmarkFrame, PoseLandmark


class PullUpPhase(Enum):
    UNKNOWN = auto()
    HANGING = auto()      # Dead hang at the bottom
    PULLING = auto()      # Concentric upward movement
    TOP = auto()          # Head has crossed the bar line
    LOWERING = auto()     # Eccentric downward movement


@dataclass
class PullUpConfig:
    extended_angle_min_deg: float = 145.0    # Angle of a proper dead-hang
    flexed_angle_max_deg: float = 60.0       # Angle of a deep pull

    # --- CHEAT DETECTOR THRESHOLDS ---
    min_extension_for_rep_deg: float = 135.0 # MUST go down this far before pulling to count

    min_vis: float = 0.20
    angle_ema_alpha: float = 0.35
    min_rep_interval_s: float = 1.0


class PullUpExercise(Exercise):
    id = "pullup"

    def __init__(self, config: Optional[PullUpConfig] = None) -> None:
        self.cfg = config or PullUpConfig()
        self.reset()

    def reset(self) -> None:
        self._ema_angle: Optional[float] = None
        self._prev_t: Optional[float] = None
        self._prev_angle: Optional[float] = None
        self._phase = PullUpPhase.UNKNOWN

        self._rep_count = 0
        self._last_rep_end_t = 0.0
        self._rep_cycle_start_t: Optional[float] = None

        # Cheat Detectors
        self._valid_start = True
        self._rep_counted_this_cycle = False
        self._current_max_extension = 180.0 # Assumes you start fully extended
        self._cheat_alert = "Ready"

        # Live Rep Trackers
        self._current_max_conc_depth = 0.0

        # Arrays for Averages
        self._rep_durations: List[float] = []
        self._rep_conc_depths: List[float] = []
        self._rep_ecc_depths: List[float] = []

    def _depth_percent(self, elbow_angle_deg: float, is_eccentric: bool) -> float:
        """Calculates how far the user is into the pull or the hang."""
        ext = float(self.cfg.extended_angle_min_deg)
        flex = float(self.cfg.flexed_angle_max_deg)
        span = max(1e-6, ext - flex)

        if is_eccentric:
            return float(max(0.0, min(100.0, (elbow_angle_deg - flex) / span * 100.0)))
        else:
            return float(max(0.0, min(100.0, (ext - elbow_angle_deg) / span * 100.0)))

    def _head_and_bar(self, lm: LandmarkFrame) -> Tuple[Optional[float], Optional[float]]:
        """Calculates the Y-coordinates of the head vs the invisible line between the hands."""
        pl = PoseLandmark
        if not lm.confident([pl.LEFT_WRIST, pl.RIGHT_WRIST, pl.NOSE], self.cfg.min_vis):
            return None, None

        # Create the invisible bar line by averaging the height of both wrists
        bar_y = (lm.xy[pl.LEFT_WRIST][1] + lm.xy[pl.RIGHT_WRIST][1]) / 2.0

        # Track the head (Using the nose as the center of mass for the head)
        head_y = lm.xy[pl.NOSE][1]

        return head_y, bar_y

    def _elbow_angle(self, lm: LandmarkFrame) -> Tuple[Optional[float], bool]:
        """Averages the angle of both elbows to get a stable rear-view metric."""
        pl = PoseLandmark

        vl = (float(lm.visibility[pl.LEFT_SHOULDER]) + float(lm.visibility[pl.LEFT_ELBOW]) + float(lm.visibility[pl.LEFT_WRIST])) / 3.0
        vr = (float(lm.visibility[pl.RIGHT_SHOULDER]) + float(lm.visibility[pl.RIGHT_ELBOW]) + float(lm.visibility[pl.RIGHT_WRIST])) / 3.0

        angles = []
        if vl >= self.cfg.min_vis:
            angles.append(angle_degrees(lm.xy[pl.LEFT_SHOULDER], lm.xy[pl.LEFT_ELBOW], lm.xy[pl.LEFT_WRIST]))
        if vr >= self.cfg.min_vis:
            angles.append(angle_degrees(lm.xy[pl.RIGHT_SHOULDER], lm.xy[pl.RIGHT_ELBOW], lm.xy[pl.RIGHT_WRIST]))

        if not angles:
            return None, False

        avg_angle = sum(angles) / len(angles)
        return float(avg_angle), True

    def _update_phase(self, t: float, ang: float, dang_dt: float, head_y: Optional[float], bar_y: Optional[float]) -> None:
        ext = self.cfg.extended_angle_min_deg

        if self._phase in (PullUpPhase.UNKNOWN, PullUpPhase.HANGING):
            if ang >= ext - 15.0:
                self._phase = PullUpPhase.HANGING
                self._current_max_extension = max(self._current_max_extension, ang)
            elif ang < ext - 15.0 and dang_dt < -5.0:
                self._phase = PullUpPhase.PULLING
                self._rep_cycle_start_t = t
                self._rep_counted_this_cycle = False
                self._current_max_conc_depth = 0.0

                # If they started pulling from a hang, it's a valid start
                self._valid_start = True
                self._cheat_alert = "Tracking..."

        elif self._phase == PullUpPhase.PULLING:
            # Check if head went above the bar! (Y is inverted in pixels, so smaller Y means higher)
            if head_y is not None and bar_y is not None and head_y < bar_y:
                self._phase = PullUpPhase.TOP
                if not self._rep_counted_this_cycle:
                    self._try_count_rep(t)
            elif dang_dt > 15.0:  # Gave up pulling
                self._phase = PullUpPhase.LOWERING
                self._current_max_extension = ang

        elif self._phase == PullUpPhase.TOP:
            # Check if they dropped below the bar
            if (head_y is not None and bar_y is not None and head_y > bar_y + 0.02) or dang_dt > 5.0:
                self._phase = PullUpPhase.LOWERING
                self._current_max_extension = ang

        elif self._phase == PullUpPhase.LOWERING:
            self._current_max_extension = max(self._current_max_extension, ang)

            if ang >= ext - 15.0:  # Reached full hang
                self._phase = PullUpPhase.HANGING
            elif dang_dt < -15.0:  # Started pulling back up early (Half-Rep!)
                self._phase = PullUpPhase.PULLING
                self._rep_cycle_start_t = t
                self._rep_counted_this_cycle = False
                self._current_max_conc_depth = 0.0

                # CHEAT DETECTOR: Did they drop far enough before starting this new pull?
                if self._current_max_extension >= self.cfg.min_extension_for_rep_deg:
                    self._valid_start = True
                    self._cheat_alert = "Tracking..."
                else:
                    self._valid_start = False
                    self._cheat_alert = "Half Rep: Didn't start from dead hang!"

    def _try_count_rep(self, t: float) -> None:
        if t - self._last_rep_end_t < self.cfg.min_rep_interval_s:
            return

        self._rep_counted_this_cycle = True

        # CHEAT DETECTOR 2: Didn't go all the way down prior to this pull
        if not self._valid_start:
            self._cheat_alert = "Half Rep: Didn't start from dead hang!"
            return

        # Good Rep!
        self._cheat_alert = "Good Rep!"
        self._rep_count += 1
        self._last_rep_end_t = t

        if self._rep_cycle_start_t is not None:
            self._rep_durations.append(max(0.0, t - self._rep_cycle_start_t))

        self._rep_conc_depths.append(self._current_max_conc_depth)

        # The eccentric depth for this rep is based on how far down they went BEFORE pulling
        ecc_pct = self._depth_percent(self._current_max_extension, is_eccentric=True)
        self._rep_ecc_depths.append(ecc_pct)

    def update(self, t: float, landmarks: LandmarkFrame) -> ExerciseResult:
        ang, ok = self._elbow_angle(landmarks)
        head_y, bar_y = self._head_and_bar(landmarks)

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

        self._update_phase(t, sm, raw_dang, head_y, bar_y)

        conc_pct = self._depth_percent(sm, is_eccentric=False)
        ecc_pct = self._depth_percent(sm, is_eccentric=True)

        if self._phase in (PullUpPhase.PULLING, PullUpPhase.TOP):
            self._current_max_conc_depth = max(self._current_max_conc_depth, conc_pct)

        metrics: Dict[str, Any] = {
            "visible": True,
            "phase": self._phase.name,
            "rep_count": self._rep_count,
            "elbow_angle_deg": round(sm, 1),
            "conc_depth_percent": round(conc_pct, 1),
            "ecc_depth_percent": round(ecc_pct, 1),
            "cheat_alert": self._cheat_alert
        }

        if head_y is not None and bar_y is not None:
            metrics["head_above_bar"] = "YES!" if head_y < bar_y else "No"

        if self._rep_cycle_start_t is not None:
            metrics["rep_speed_timer_s"] = round(max(0.0, t - self._rep_cycle_start_t), 2)

        if self._rep_durations:
            metrics["average_rep_duration_s"] = round(sum(self._rep_durations) / len(self._rep_durations), 2)
        if self._rep_conc_depths:
            metrics["average_conc_depth"] = round(sum(self._rep_conc_depths) / len(self._rep_conc_depths), 1)
        if self._rep_ecc_depths:
            metrics["average_ecc_depth"] = round(sum(self._rep_ecc_depths) / len(self._rep_ecc_depths), 1)

        return ExerciseResult(self.id, True, metrics, {})