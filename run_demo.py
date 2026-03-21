"""
Minimal webcam loop: prints tracking metrics to stdout (no GUI).

Usage (from repo root):
  pip install -r requirements.txt
  python run_demo.py

By default only prints JSON lines to stdout (no window). Use --preview to
open a camera window; press 'q' to quit.
"""

from __future__ import annotations

import argparse
import json
import sys

import cv2

from lift_tracker.exercises.squat import SquatExercise
from lift_tracker.pipeline import TrackingPipeline


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--no-preview", action="store_true", help="Do not open a preview window.")
    p.add_argument("--every", type=int, default=3, help="Print every N frames.")
    args = p.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Could not open camera.", file=sys.stderr)
        sys.exit(1)

    pipe = TrackingPipeline(SquatExercise())
    n = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            packet = pipe.process_bgr(frame)
            n += 1
            if n % max(1, args.every) == 0:
                line = {
                    "t": round(packet.t, 3),
                    "has_pose": packet.landmarks is not None,
                    **packet.exercise.as_dict(),
                }
                print(json.dumps(line), flush=True)

            if args.preview:
                cv2.imshow("lift_tracker (q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        pipe.close()
        if args.preview:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
