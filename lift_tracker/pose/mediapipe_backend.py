from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from lift_tracker.pose.landmarks import LandmarkFrame

_MODEL_URLS: dict[int, str] = {
    0: (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
    1: (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    ),
    2: (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
    ),
}


def _model_cache_path(model_complexity: int) -> Path:
    name = {0: "pose_landmarker_lite.task", 1: "pose_landmarker_full.task", 2: "pose_landmarker_heavy.task"}[
        model_complexity
    ]
    base = Path.home() / ".cache" / "form_logic" / "mediapipe_models"
    return base / name


def _ensure_pose_model(model_complexity: int) -> str:
    mc = min(max(model_complexity, 0), 2)
    path = _model_cache_path(mc)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = _MODEL_URLS[mc]
        tmp = path.with_suffix(path.suffix + ".download")
        try:
            urllib.request.urlretrieve(url, tmp)  # noqa: S310
            os.replace(tmp, path)
        except BaseException:
            if tmp.is_file():
                tmp.unlink(missing_ok=True)
            raise
    return str(path.resolve())


@dataclass
class MediaPipePoseConfig:
    model_complexity: int = 1
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    smooth_landmarks: bool = True


class MediaPipePoseBackend:
    """Pose via MediaPipe Tasks (Pose Landmarker); 33 landmarks, BlazePose topology."""

    def __init__(self, config: Optional[MediaPipePoseConfig] = None) -> None:
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as bo

        self._cfg = config or MediaPipePoseConfig()
        model_path = _ensure_pose_model(self._cfg.model_complexity)

        opts = vision.PoseLandmarkerOptions(
            base_options=bo.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=self._cfg.min_detection_confidence,
            min_pose_presence_confidence=self._cfg.min_detection_confidence,
            min_tracking_confidence=self._cfg.min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(opts)
        self._ts_ms = 0

    def close(self) -> None:
        self._landmarker.close()

    def process_bgr(self, frame_bgr: np.ndarray) -> Tuple[Optional[LandmarkFrame], Any]:
        """
        Returns (landmarks or None if no pose, raw_results for debugging).
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None, None

        from mediapipe.tasks.python.vision.core import image as mp_image

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_bgr.shape[:2]
        image = mp_image.Image(image_format=mp_image.ImageFormat.SRGB, data=rgb)

        self._ts_ms += 33
        res = self._landmarker.detect_for_video(image, self._ts_ms)

        if not res.pose_landmarks:
            return None, res

        lm = res.pose_landmarks[0]
        if len(lm) < 33:
            return None, res

        xy = np.zeros((33, 2), dtype=np.float32)
        vis = np.zeros(33, dtype=np.float32)
        for i in range(33):
            pt = lm[i]
            xy[i, 0] = (pt.x or 0.0) * w
            xy[i, 1] = (pt.y or 0.0) * h
            v = pt.visibility
            if v is None:
                v = pt.presence
            vis[i] = float(v or 0.0)
        return LandmarkFrame(xy=xy, visibility=vis), res
