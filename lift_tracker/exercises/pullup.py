from lift_tracker.exercises.base import Exercise, ExerciseResult
from lift_tracker.pose.landmarks import LandmarkFrame

class PullUpExercise(Exercise):
    id = "pullup"

    def reset(self) -> None:
        pass

    def update(self, t: float, landmarks: LandmarkFrame) -> ExerciseResult:
        # Placeholder: Add your back-view shoulder/elbow math here later!
        metrics = {
            "visible": True,
            "phase": "WIP: Pull-up Mode",
            "rep_count": 0
        }
        return ExerciseResult(self.id, True, metrics, {})