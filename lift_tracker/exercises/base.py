from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from lift_tracker.pose.landmarks import LandmarkFrame


@dataclass
class ExerciseResult:
    """Stable dict-friendly payload for UI or logging."""

    exercise_id: str
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    hints: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "ok": self.ok,
            "metrics": self.metrics,
            "hints": self.hints,
        }


class Exercise(ABC):
    """One exercise module; stateful across frames."""

    id: str = "base"

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, t: float, landmarks: LandmarkFrame) -> ExerciseResult:
        """t = monotonic seconds (e.g. time.perf_counter())."""
        raise NotImplementedError


def blend_visibility(
    left: np.ndarray,
    right: np.ndarray,
    vl: float,
    vr: float,
) -> tuple[np.ndarray, float]:
    if vl < 0.35 and vr < 0.35:
        return (left + right) / 2.0, (vl + vr) / 2.0
    if vl >= vr:
        return left, vl
    return right, vr
