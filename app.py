import tkinter as tk
from tkinter import ttk
import cv2

from lift_tracker.exercises.squat import SquatExercise
from lift_tracker.exercises.bicep_curl import BicepCurlExercise
from lift_tracker.exercises.pullup import PullUpExercise
from lift_tracker.pipeline import TrackingPipeline
from lift_tracker.pose.skeleton import draw_pose_skeleton
from lift_tracker.viz.squat_hud import draw_squat_hud

class FormLogicUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Form-Logic Tracker")
        self.root.geometry("450x250")
        self.root.configure(padx=20, pady=20)

        # Main Title
        title = tk.Label(root, text="Form-Logic", font=("Helvetica", 20, "bold"))
        title.pack(pady=(0, 10))

        # Dropdown Label
        tk.Label(root, text="Select an Exercise:", font=("Helvetica", 12)).pack()

        # Exercise Dropdown
        self.exercise_var = tk.StringVar()
        self.dropdown = ttk.Combobox(
            root,
            textvariable=self.exercise_var,
            values=["Squat (Side Profile)", "Bicep Curl (Side Profile)", "Pull-up (Back Profile)"],
            state="readonly",
            width=30,
            font=("Helvetica", 12)
        )
        self.dropdown.current(0)  # Default to Squat
        self.dropdown.pack(pady=10)

        # Start Button
        self.start_btn = ttk.Button(root, text="Start Tracker", command=self.start_tracker)
        self.start_btn.pack(pady=20)

    def start_tracker(self):
        selection = self.exercise_var.get()

        # Map the dropdown choice to the correct math module
        if "Squat" in selection:
            active_exercise = SquatExercise()
        elif "Bicep Curl" in selection:
            active_exercise = BicepCurlExercise()
        elif "Pull-up" in selection:
            active_exercise = PullUpExercise()
        else:
            return

        self.run_webcam_loop(active_exercise)

    def run_webcam_loop(self, exercise_module):
        # Hide the UI window while the camera is active
        self.root.withdraw()

        cap = cv2.VideoCapture(0)
        pipe = TrackingPipeline(exercise_module)

        try:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break

                # Run the math on the frame
                packet = pipe.process_bgr(frame)
                display = frame.copy()

                # Draw the skeleton
                if packet.landmarks is not None:
                    draw_pose_skeleton(display, packet.landmarks)

                # Draw the HUD overlay
                draw_squat_hud(display, packet.exercise.metrics)

                # Show the window
                cv2.imshow("Form-Logic (Press 'Q' to Exit)", display)

                # Break the loop if the user presses 'q'
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            pipe.close()
            cv2.destroyAllWindows()

            # Bring the UI menu back!
            self.root.deiconify()

# THIS is the block that actually starts the app!
if __name__ == "__main__":
    root = tk.Tk()

    style = ttk.Style()
    style.theme_use('clam')

    app = FormLogicUI(root)
    root.mainloop()