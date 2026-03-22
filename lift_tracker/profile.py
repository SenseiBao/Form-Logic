from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class TrainingGoal(str, Enum):
    BUILD_MUSCLE = "build_muscle"
    LOSE_WEIGHT = "lose_weight"
    INCREASE_STRENGTH = "increase_strength"
    GAIN_WEIGHT = "gain_weight"


# UI labels -> enum (onboarding / settings)
GOAL_CHOICES: Tuple[Tuple[str, TrainingGoal], ...] = (
    ("Muscle building", TrainingGoal.BUILD_MUSCLE),
    ("Build Strength", TrainingGoal.INCREASE_STRENGTH),
    ("Lose weight", TrainingGoal.LOSE_WEIGHT),
    ("Gain weight", TrainingGoal.GAIN_WEIGHT),
)


@dataclass
class UserProfile:
    """Collected for future prescription / thresholds; not used by raw pose math."""

    first_name: str = ""
    goal: Optional[TrainingGoal] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_name": self.first_name,
            "goal": self.goal.value if self.goal else None,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "UserProfile":
        g = d.get("goal")
        goal: Optional[TrainingGoal] = None
        if g:
            try:
                goal = TrainingGoal(g)
            except ValueError:
                goal = None
        return UserProfile(
            first_name=str(d.get("first_name") or "").strip(),
            goal=goal,
            height_cm=_opt_float(d.get("height_cm")),
            weight_kg=_opt_float(d.get("weight_kg")),
        )


def _opt_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def inches_to_cm(inches: Optional[float]) -> Optional[float]:
    if inches is None:
        return None
    return round(float(inches) * 2.54, 2)


def lbs_to_kg(lbs: Optional[float]) -> Optional[float]:
    if lbs is None:
        return None
    return round(float(lbs) * 0.45359237, 2)


def cm_to_inches(cm: Optional[float]) -> Optional[float]:
    if cm is None:
        return None
    return round(float(cm) / 2.54, 2)


def kg_to_lbs(kg: Optional[float]) -> Optional[float]:
    if kg is None:
        return None
    return round(float(kg) / 0.45359237, 2)
