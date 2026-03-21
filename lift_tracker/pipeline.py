from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from lift_tracker.exercises.base import Exercise, ExerciseResult
from lift_tracker.pose.landmarks import LandmarkFrame, empty_landmark_frame
from lift_tracker.pose.mediapipe_backend import MediaPipePoseBackend, MediaPipePoseConfig
from lift_tracker.profile import UserProfile


@dataclass
class FramePacket:
    """Everything produced for one camera frame (UI-agnostic)."""

    t: float
    landmarks: Optional[LandmarkFrame]
    exercise: ExerciseResult


class TrackingPipeline:
    """
    Wires MediaPipe → active Exercise module. Swap `exercise` to add movements.
    """

    def __init__(
        self,
        exercise: Exercise,
        pose_config: Optional[MediaPipePoseConfig] = None,
        profile: Optional[UserProfile] = None,
    ) -> None:
        self.pose = MediaPipePoseBackend(pose_config)
        self.exercise = exercise
        self.profile = profile or UserProfile()

    def close(self) -> None:
        self.pose.close()

    def process_bgr(self, frame_bgr: Any) -> FramePacket:
        t = time.perf_counter()
        lm, _ = self.pose.process_bgr(frame_bgr)
        if lm is None:
            return FramePacket(
                t=t,
                landmarks=None,
                exercise=self.exercise.update(t, empty_landmark_frame()),
            )
        ex = self.exercise.update(t, lm)
        return FramePacket(t=t, landmarks=lm, exercise=ex)
