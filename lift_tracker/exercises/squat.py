from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Literal, Optional, Tuple

from lift_tracker.exercises.base import Exercise, ExerciseResult, blend_visibility
from lift_tracker.geometry import angle_degrees
from lift_tracker.pose.landmarks import LandmarkFrame, PoseLandmark


class SquatPhase(Enum):
    UNKNOWN = auto()
    STANDING = auto()
    ECCENTRIC = auto()
    BOTTOM = auto()
    CONCENTRIC = auto()


class _ConcentricSubphase(Enum):
    NONE = auto()
    BOTTOM_HALF = auto()
    TOP_HALF = auto()


@dataclass
class SquatConfig:
    standing_angle_min_deg: float = 145.0
    bottom_angle_max_deg: float = 100.0
    # Extra knee-angle slack so slightly shallow squats still count (enables “go deeper” feedback).
    count_depth_lenience_deg: float = 18.0
    min_vis: float = 0.20
    require_depth: bool = True
    depth_slack_deg: float = 15.0
    min_knee_flexion_for_rep_deg: float = 35.0

    min_rep_eccentric_duration_s: float = 0.0
    min_rep_concentric_duration_s: float = 0.0
    knee_vy_ema_alpha: float = 0.25
    knee_vy_px_s_threshold: float = 9999.0

    dsm_down_threshold_deg_s: float = -8.0
    dsm_up_threshold_deg_s: float = 8.0

    angle_ema_alpha: float = 0.35
    min_rep_interval_s: float = 0.95
    leg_selection: Literal["side_profile", "blend"] = "side_profile"
    imbalance_ratio: float = 1.45
    min_mean_speed_deg_s: float = 25.0


class SquatExercise(Exercise):
    id = "squat"

    def __init__(self, config: Optional[SquatConfig] = None) -> None:
        self.cfg = config or SquatConfig()
        self.reset()

    def reset(self) -> None:
        self._ema_angle: Optional[float] = None
        self._prev_t: Optional[float] = None
        self._prev_angle: Optional[float] = None
        self._phase = SquatPhase.UNKNOWN
        self._conc_sub = _ConcentricSubphase.NONE
        self._rep_count = 0
        self._last_rep_end_t = 0.0
        self._descent_start_t: Optional[float] = None
        self._bottom_t: Optional[float] = None
        self._bottom_angle: Optional[float] = None
        self._eccentric_duration_s: Optional[float] = None
        self._concentric_duration_s: Optional[float] = None
        self._last_rep_speeds: Optional[Tuple[float, float, float, float]] = None
        self._ch_start_t: Optional[float] = None
        self._concentric_start_t: Optional[float] = None
        self._ch_split_t: Optional[float] = None
        self._ch_end_t: Optional[float] = None
        self._sum_speed_bottom: float = 0.0
        self._sum_speed_top: float = 0.0
        self._n_bottom: int = 0
        self._n_top: int = 0
        self._mid_angle: Optional[float] = None
        self._hist_bottom_slow: List[float] = []
        self._hist_top_slow: List[float] = []
        self._hist_window = 5
        self._prev_smo = None
        self._eccentric_start_angle = None
        self._last_rep_eccentric_mean_deg_s = None
        self._last_rep_concentric_mean_deg_s = None
        self._last_rep_duration_s: Optional[float] = None
        self._rep_cycle_start_t: Optional[float] = None

        # Arrays to hold the exact metrics per completed rep
        self._rep_durations: List[float] = []
        self._rep_depths: List[float] = []
        self._rep_ideal_depth: List[bool] = []

        # --- NEW TRACKERS FOR BACK ANGLE ---
        self._current_rep_max_lean: float = 0.0
        self._rep_max_leans: List[float] = []

    def _depth_percent(self, knee_angle_deg: float) -> float:
        stand = float(self.cfg.standing_angle_min_deg)
        deep = float(self.cfg.bottom_angle_max_deg)
        span = max(1e-6, stand - deep)
        return float(max(0.0, min(100.0, (stand - knee_angle_deg) / span * 100.0)))

    def _torso_angle(self, lm: LandmarkFrame) -> Tuple[Optional[float], bool]:
        """Calculates the back lean angle relative to a perfectly vertical line."""
        pl = PoseLandmark
        idx = [
            pl.LEFT_SHOULDER, pl.LEFT_HIP,
            pl.RIGHT_SHOULDER, pl.RIGHT_HIP,
        ]
        if not lm.confident(idx, self.cfg.min_vis):
            return None, False

        ls, rs = lm.xy[pl.LEFT_SHOULDER], lm.xy[pl.RIGHT_SHOULDER]
        lh, rh = lm.xy[pl.LEFT_HIP], lm.xy[pl.RIGHT_HIP]

        shoulder, vs = blend_visibility(ls, rs, float(lm.visibility[pl.LEFT_SHOULDER]), float(lm.visibility[pl.RIGHT_SHOULDER]))
        hip, vh = blend_visibility(lh, rh, float(lm.visibility[pl.LEFT_HIP]), float(lm.visibility[pl.RIGHT_HIP]))
        vis_ok = (vs + vh) / 2.0 >= self.cfg.min_vis

        # Vector from hip to shoulder
        dx = shoulder[0] - hip[0]
        dy = shoulder[1] - hip[1]

        # Calculate angle relative to the vertical Y-axis
        # 0 degrees = perfectly upright
        angle_rad = math.atan2(abs(dx), abs(dy))
        return float(math.degrees(angle_rad)), vis_ok

    def _knee_angle(self, lm: LandmarkFrame) -> Tuple[Optional[float], bool]:
        pl = PoseLandmark
        idx = [
            pl.LEFT_HIP, pl.LEFT_KNEE, pl.LEFT_ANKLE,
            pl.RIGHT_HIP, pl.RIGHT_KNEE, pl.RIGHT_ANKLE,
        ]
        if not lm.confident(idx, self.cfg.min_vis):
            return None, False

        lh, lk, la = lm.xy[pl.LEFT_HIP], lm.xy[pl.LEFT_KNEE], lm.xy[pl.LEFT_ANKLE]
        rh, rk, ra = lm.xy[pl.RIGHT_HIP], lm.xy[pl.RIGHT_KNEE], lm.xy[pl.RIGHT_ANKLE]

        hip, _ = blend_visibility(lh, rh, float(lm.visibility[pl.LEFT_HIP]), float(lm.visibility[pl.RIGHT_HIP]))
        knee, vk = blend_visibility(lk, rk, float(lm.visibility[pl.LEFT_KNEE]), float(lm.visibility[pl.RIGHT_KNEE]))
        ank, va = blend_visibility(la, ra, float(lm.visibility[pl.LEFT_ANKLE]), float(lm.visibility[pl.RIGHT_ANKLE]))
        vis_ok = (vk + va) / 2.0 >= self.cfg.min_vis

        a = angle_degrees(hip, knee, ank)
        if math.isnan(a):
            return None, False
        return float(a), vis_ok

    def _update_phase(self, t: float, ang: float, dang_dt: float) -> None:
        stand = self.cfg.standing_angle_min_deg
        deep = self.cfg.bottom_angle_max_deg

        if self._phase in (SquatPhase.UNKNOWN, SquatPhase.STANDING):
            if ang >= stand - 3.0:
                self._phase = SquatPhase.STANDING
            elif ang < stand - 5.0 and dang_dt < -5.0:
                self._phase = SquatPhase.ECCENTRIC
                if self._descent_start_t is None:
                    self._descent_start_t = t
                    self._eccentric_start_angle = ang
                self._rep_cycle_start_t = t
                self._current_rep_max_lean = 0.0  # Reset max lean tracker at the start of rep
        elif self._phase == SquatPhase.ECCENTRIC:
            if ang <= deep + 16.0 and abs(dang_dt) < 40.0:
                self._phase = SquatPhase.BOTTOM
                self._bottom_t = t
                self._bottom_angle = ang
                if self._descent_start_t is not None:
                    self._eccentric_duration_s = max(0.0, t - self._descent_start_t)
            elif ang >= stand - 5.0 and dang_dt > 8.0:
                self._phase = SquatPhase.STANDING
                self._clear_rep_timers()
        elif self._phase == SquatPhase.BOTTOM:
            if ang > deep + 12.0 and dang_dt > 5.0:
                self._phase = SquatPhase.CONCENTRIC
                ba = self._bottom_angle if self._bottom_angle is not None else ang
                self._begin_concentric(t, float(ba))
        elif self._phase == SquatPhase.CONCENTRIC:
            if ang >= stand - 4.0:
                lim = self.cfg.bottom_angle_max_deg + 15.0 + self.cfg.count_depth_lenience_deg
                had_depth = self._bottom_angle is not None and self._bottom_angle <= lim
                ba = self._bottom_angle
                self._phase = SquatPhase.STANDING
                self._finish_concentric(t, ang)
                self._try_count_rep(t, had_depth, ba)
            elif ang < deep + 10.0 and dang_dt < -5.0:
                self._phase = SquatPhase.ECCENTRIC
                self._abort_concentric()
                self._descent_start_t = t
                self._eccentric_start_angle = ang

    def _clear_rep_timers(self) -> None:
        self._descent_start_t = None
        self._bottom_t = None
        self._bottom_angle = None
        self._eccentric_duration_s = None
        self._concentric_duration_s = None
        self._eccentric_start_angle = None
        self._rep_cycle_start_t = None
        self._abort_concentric()

    def _begin_concentric(self, t: float, bottom_angle: float) -> None:
        self._conc_sub = _ConcentricSubphase.BOTTOM_HALF
        self._ch_start_t = t
        self._concentric_start_t = t
        self._ch_split_t = None
        self._ch_end_t = None
        top_ref = float(self.cfg.standing_angle_min_deg)
        self._mid_angle = (bottom_angle + top_ref) / 2.0
        self._sum_speed_bottom = 0.0
        self._sum_speed_top = 0.0
        self._n_bottom = 0
        self._n_top = 0

    def _abort_concentric(self) -> None:
        self._conc_sub = _ConcentricSubphase.NONE
        self._ch_start_t = None
        self._concentric_start_t = None
        self._ch_split_t = None
        self._ch_end_t = None
        self._mid_angle = None

    def _finish_concentric(self, t: float, final_angle: float) -> None:
        if self._rep_cycle_start_t is not None:
            self._last_rep_duration_s = max(0.0, t - self._rep_cycle_start_t)

        start = self._concentric_start_t if self._concentric_start_t is not None else self._bottom_t
        if start is not None:
            self._concentric_duration_s = max(0.0, t - start)

        if self._ch_start_t is not None:
            self._ch_end_t = t

        v_b = self._sum_speed_bottom / self._n_bottom if self._n_bottom else 0.0
        v_t = self._sum_speed_top / self._n_top if self._n_top else 0.0
        e = self._eccentric_duration_s
        c = self._concentric_duration_s
        self._last_rep_speeds = (e or 0.0, c or 0.0, v_b, v_t)
        ea = self._eccentric_start_angle
        ba = self._bottom_angle

        self._last_rep_eccentric_mean_deg_s = None
        self._last_rep_concentric_mean_deg_s = None

        if ea is not None and ba is not None and e and e > 1e-6:
            self._last_rep_eccentric_mean_deg_s = max(0.0, (ea - ba) / e)
        if ba is not None and c and c > 1e-6:
            self._last_rep_concentric_mean_deg_s = max(0.0, (final_angle - ba) / c)

        self._update_fatigue_history(v_b, v_t)
        self._abort_concentric()
        self._descent_start_t = None
        self._bottom_t = None
        self._bottom_angle = None
        self._eccentric_start_angle = None
        self._rep_cycle_start_t = None

    def _update_fatigue_history(self, v_bottom_half: float, v_top_half: float) -> None:
        eps = 1e-3
        self._hist_bottom_slow.append(1.0 / max(v_bottom_half, eps))
        self._hist_top_slow.append(1.0 / max(v_top_half, eps))
        if len(self._hist_bottom_slow) > self._hist_window:
            self._hist_bottom_slow.pop(0)
            self._hist_top_slow.pop(0)

    def get_summary(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "total_reps": self._rep_count,
            "avg_rep_duration_s": round(sum(self._rep_durations) / len(self._rep_durations), 2) if self._rep_durations else 0,
            "avg_depth_pct": round(sum(self._rep_depths) / len(self._rep_depths), 1) if self._rep_depths else 0,
            "avg_max_lean_deg": round(sum(self._rep_max_leans) / len(self._rep_max_leans), 1) if self._rep_max_leans else 0,
        }
        if self._rep_ideal_depth:
            deep = sum(1 for x in self._rep_ideal_depth if x)
            out["pct_reps_deep_enough"] = round(100.0 * deep / len(self._rep_ideal_depth), 1)
        return out

    def _try_count_rep(self, t: float, had_depth: bool, bottom_angle: Optional[float] = None) -> None:
        if t - self._last_rep_end_t < self.cfg.min_rep_interval_s:
            return
        if self.cfg.require_depth and not had_depth:
            return

        self._rep_count += 1
        self._last_rep_end_t = t

        if getattr(self, "_last_rep_duration_s", None) is not None:
            self._rep_durations.append(self._last_rep_duration_s)

        if bottom_angle is not None:
            self._rep_depths.append(self._depth_percent(bottom_angle))
            ideal = bottom_angle <= self.cfg.bottom_angle_max_deg + 10.0
            self._rep_ideal_depth.append(ideal)
        else:
            self._rep_ideal_depth.append(False)

        # Save the maximum lean of this completed rep
        if getattr(self, "_current_rep_max_lean", None) is not None and self._current_rep_max_lean > 0.0:
            self._rep_max_leans.append(self._current_rep_max_lean)

    def _track_concentric_halves(self, t: float, ang: float, dang_dt: float) -> None:
        if self._phase != SquatPhase.CONCENTRIC or self._conc_sub == _ConcentricSubphase.NONE:
            return
        if self._mid_angle is None or self._bottom_angle is None:
            return

        ext_speed = max(0.0, dang_dt)
        if self._conc_sub == _ConcentricSubphase.BOTTOM_HALF:
            if ang >= self._mid_angle:
                self._conc_sub = _ConcentricSubphase.TOP_HALF
                self._ch_split_t = t
            else:
                if ext_speed >= self.cfg.min_mean_speed_deg_s * 0.05:
                    self._sum_speed_bottom += ext_speed
                    self._n_bottom += 1
        elif self._conc_sub == _ConcentricSubphase.TOP_HALF:
            if ext_speed >= self.cfg.min_mean_speed_deg_s * 0.05:
                self._sum_speed_top += ext_speed
                self._n_top += 1

    def _fatigue_hints(self) -> Tuple[Optional[str], Optional[str], dict]:
        if self._last_rep_speeds is None:
            return None, None, {}
        _, _, v_b, v_t = self._last_rep_speeds
        dbg = {
            "concentric_mean_speed_bottom_half_deg_s": round(v_b, 2),
            "concentric_mean_speed_top_half_deg_s": round(v_t, 2),
        }
        if v_b < self.cfg.min_mean_speed_deg_s and v_t < self.cfg.min_mean_speed_deg_s:
            return None, None, dbg
        r = self.cfg.imbalance_ratio
        if v_b * r < v_t:
            return (
                "bottom_half_concentric_slower",
                "Often associated with needing more posterior chain / hip extension strength — this is a rough heuristic, not a diagnosis.",
                dbg,
            )
        if v_t * r < v_b:
            return (
                "top_half_concentric_slower",
                "Often associated with needing more knee extension strength — this is a rough heuristic, not a diagnosis.",
                dbg,
            )
        return None, None, dbg

    def update(self, t: float, landmarks: LandmarkFrame) -> ExerciseResult:
        ang, ok = self._knee_angle(landmarks)
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

        if self._prev_smo is None:
            self._prev_smo = sm
        dsm = (sm - self._prev_smo) / dt
        self._prev_smo = sm

        if self._phase == SquatPhase.CONCENTRIC:
            self._track_concentric_halves(t, sm, dsm)
        self._update_phase(t, sm, raw_dang)

        # --- NEW BACK ANGLE LOGIC ---
        torso_ang, torso_ok = self._torso_angle(landmarks)
        if torso_ok and torso_ang is not None:
            # Continuously search for the highest forward lean while actively moving
            if self._phase in (SquatPhase.ECCENTRIC, SquatPhase.BOTTOM, SquatPhase.CONCENTRIC):
                self._current_rep_max_lean = max(self._current_rep_max_lean, torso_ang)


        hint_key, hint_text, dbg = self._fatigue_hints()
        dp_instant = self._depth_percent(sm)

        metrics: Dict[str, Any] = {
            "knee_angle_deg": round(sm, 2),
            "depth_percent": round(dp_instant, 1),
            "phase": self._phase.name,
            "rep_count": self._rep_count,
            "visible": True,
        }

        # Timer for the current live rep
        if self._rep_cycle_start_t is not None and self._phase in (
            SquatPhase.ECCENTRIC, SquatPhase.BOTTOM, SquatPhase.CONCENTRIC,
        ):
            elapsed = max(0.0, t - self._rep_cycle_start_t)
            metrics["rep_speed_timer_s"] = round(elapsed, 2)
            metrics["live_rep_duration_s"] = round(elapsed, 2)

        # Averages calculated from the per-rep arrays
        if self._rep_durations:
            avg_rep = round(sum(self._rep_durations) / len(self._rep_durations), 2)
            metrics["average_rep_duration_s"] = avg_rep

        if self._rep_depths:
            metrics["average_depth_percent"] = round(sum(self._rep_depths) / len(self._rep_depths), 1)

        # Output Back Angle data
        if torso_ok and torso_ang is not None:
            metrics["torso_angle_deg"] = round(torso_ang, 1)
        if self._rep_max_leans:
            metrics["average_max_lean_deg"] = round(sum(self._rep_max_leans) / len(self._rep_max_leans), 1)

        if self._last_rep_speeds is not None:
            _, _, vb, vt = self._last_rep_speeds
            metrics.update({
                "last_rep_mean_knee_extension_speed_bottom_half_deg_s": round(vb, 2),
                "last_rep_mean_knee_extension_speed_top_half_deg_s": round(vt, 2),
            })

        metrics.update(dbg)

        hints = {}
        if hint_key:
            hints["fatigue_balance"] = {"code": hint_key, "detail": hint_text}

        return ExerciseResult(self.id, True, metrics, hints)