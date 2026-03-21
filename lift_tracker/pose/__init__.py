from lift_tracker.pose.landmarks import LandmarkFrame, PoseLandmark

__all__ = [
    "LandmarkFrame",
    "PoseLandmark",
    "MediaPipePoseBackend",
    "MediaPipePoseConfig",
]


def __getattr__(name: str):
    if name in ("MediaPipePoseBackend", "MediaPipePoseConfig"):
        from lift_tracker.pose.mediapipe_backend import MediaPipePoseBackend, MediaPipePoseConfig

        return MediaPipePoseBackend if name == "MediaPipePoseBackend" else MediaPipePoseConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
