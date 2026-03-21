"""MediaPipe Pose landmark indices (33-landmark topology)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Optional

import numpy as np


class PoseLandmark(IntEnum):
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass(frozen=True)
class LandmarkFrame:
    """Pixel-space landmarks + visibility (0–1)."""

    xy: np.ndarray  # shape (33, 2) float32
    visibility: np.ndarray  # shape (33,) float32

    def confident(self, indices: Iterable[int], min_vis: float = 0.5) -> bool:
        idx = list(indices)
        if not idx:
            return False
        return bool(np.all(self.visibility[idx] >= min_vis))


def empty_landmark_frame() -> LandmarkFrame:
    z = np.zeros((33, 2), dtype=np.float32)
    v = np.zeros(33, dtype=np.float32)
    return LandmarkFrame(xy=z, visibility=v)
