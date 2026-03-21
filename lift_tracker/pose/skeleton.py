"""Draw BlazePose 33-landmark skeleton on a BGR image (pixel coordinates)."""

from __future__ import annotations

import cv2
import numpy as np

from lift_tracker.pose.landmarks import LandmarkFrame

# Same topology as legacy MediaPipe `pose_connections.POSE_CONNECTIONS`.
POSE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (24, 26),
    (25, 27),
    (26, 28),
    (27, 29),
    (28, 30),
    (29, 31),
    (30, 32),
    (27, 31),
    (28, 32),
)


def draw_pose_skeleton(
    frame_bgr: np.ndarray,
    lm: LandmarkFrame,
    *,
    min_visibility: float = 0.25,
    line_color: tuple[int, int, int] = (0, 255, 128),
    line_thickness: int = 2,
    joint_color: tuple[int, int, int] = (0, 220, 255),
    joint_radius_face: int = 3,
    joint_radius_body: int = 5,
) -> None:
    """Draw bones and joint dots on `frame_bgr` in place."""
    xy = lm.xy
    vis = lm.visibility
    h, w = frame_bgr.shape[:2]

    def pt(i: int) -> tuple[int, int]:
        x = int(np.clip(xy[i, 0], 0, w - 1))
        y = int(np.clip(xy[i, 1], 0, h - 1))
        return x, y

    for a, b in POSE_CONNECTIONS:
        if vis[a] < min_visibility or vis[b] < min_visibility:
            continue
        cv2.line(frame_bgr, pt(a), pt(b), line_color, line_thickness, lineType=cv2.LINE_AA)

    for i in range(33):
        if vis[i] < min_visibility:
            continue
        r = joint_radius_face if i <= 10 else joint_radius_body
        cv2.circle(frame_bgr, pt(i), r, joint_color, -1, lineType=cv2.LINE_AA)
        cv2.circle(frame_bgr, pt(i), r, (40, 40, 40), 1, lineType=cv2.LINE_AA)
