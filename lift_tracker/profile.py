from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrainingGoal(str, Enum):
    BUILD_MUSCLE = "build_muscle"
    LOSE_WEIGHT = "lose_weight"
    INCREASE_STRENGTH = "increase_strength"
    GAIN_WEIGHT = "gain_weight"


@dataclass
class UserProfile:
    """Collected for future prescription / thresholds; not used by raw pose math."""

    goal: Optional[TrainingGoal] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
