from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

from lift_tracker.pose.landmarks import LandmarkFrame, empty_landmark_frame


@dataclass
class MediaPipePoseConfig:
    model_complexity: int = 1
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    smooth_landmarks: bool = True


class MediaPipePoseBackend:
    """Thin wrapper around MediaPipe Pose (holistic 33 landmarks)."""

    def __init__(self, config: Optional[MediaPipePoseConfig] = None) -> None:
        self._cfg = config or MediaPipePoseConfig()
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=self._cfg.model_complexity,
            smooth_landmarks=self._cfg.smooth_landmarks,
            min_detection_confidence=self._cfg.min_detection_confidence,
            min_tracking_confidence=self._cfg.min_tracking_confidence,
        )

    def close(self) -> None:
        self._pose.close()

    def process_bgr(self, frame_bgr: np.ndarray) -> Tuple[Optional[LandmarkFrame], object]:
        """
        Returns (landmarks or None if no pose, raw_results for debugging).
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None, None
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self._pose.process(rgb)
        if not res.pose_landmarks:
            return None, res

        h, w = frame_bgr.shape[:2]
        lm = res.pose_landmarks.landmark
        xy = np.zeros((33, 2), dtype=np.float32)
        vis = np.zeros(33, dtype=np.float32)
        for i in range(33):
            xy[i, 0] = lm[i].x * w
            xy[i, 1] = lm[i].y * h
            vis[i] = lm[i].visibility
        return LandmarkFrame(xy=xy, visibility=vis), res
