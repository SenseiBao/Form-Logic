import tkinter as tk
from tkinter import ttk
import cv2
import time

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
        self.root.withdraw()

        cap = cv2.VideoCapture(0)
        pipe = TrackingPipeline(exercise_module)

        # --- 5 SECOND COUNTDOWN LOGIC ---
        start_time = time.time()
        countdown_duration = 5

        while True:
            ok, frame = cap.read()
            if not ok: break

            elapsed = time.time() - start_time
            remaining = int(countdown_duration - elapsed) + 1

            if remaining <= 0:
                break

            display = frame.copy()
            h, w, _ = display.shape

            # Draw big centered text
            text = str(remaining)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 5
            thickness = 10
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]

            text_x = (w - text_size[0]) // 2
            text_y = (h + text_size[1]) // 2

            # Outline for visibility
            cv2.putText(display, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 5, cv2.LINE_AA)
            # Actual White Text
            cv2.putText(display, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

            cv2.imshow("Form-Logic (Press 'Q' to Exit)", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cap.release()
                cv2.destroyAllWindows()
                self.root.deiconify()
                return

        # --- ACTIVE TRACKING LOOP ---
        try:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break

                packet = pipe.process_bgr(frame)
                display = frame.copy()

                if packet.landmarks is not None:
                    draw_pose_skeleton(display, packet.landmarks)

                draw_squat_hud(display, packet.exercise.metrics)

                cv2.imshow("Form-Logic (Press 'Q' to Exit)", display)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            pipe.close()
            cv2.destroyAllWindows()
            self.root.deiconify()

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    app = FormLogicUI(root)
    root.mainloop()