import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import time
import json
import os
from datetime import datetime

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
        self.root.geometry("450x300")
        self.root.configure(padx=20, pady=20)

        title = tk.Label(root, text="Form-Logic", font=("Helvetica", 24, "bold"))
        title.pack(pady=(0, 10))

        tk.Label(root, text="Select an Exercise:", font=("Helvetica", 12)).pack()

        self.exercise_var = tk.StringVar()
        self.dropdown = ttk.Combobox(
            root,
            textvariable=self.exercise_var,
            values=["Squat (Side Profile)", "Bicep Curl (Side Profile)", "Pull-up (Back Profile)"],
            state="readonly",
            width=30,
            font=("Helvetica", 12)
        )
        self.dropdown.current(0)
        self.dropdown.pack(pady=10)

        self.start_btn = ttk.Button(root, text="Start Workout", command=self.start_tracker)
        self.start_btn.pack(pady=10)

        # New History Button for later!
        self.history_btn = ttk.Button(root, text="View History", command=self.view_history_stub)
        self.history_btn.pack(pady=5)

    def start_tracker(self):
        selection = self.exercise_var.get()
        if "Squat" in selection: active_exercise = SquatExercise()
        elif "Bicep Curl" in selection: active_exercise = BicepCurlExercise()
        elif "Pull-up" in selection: active_exercise = PullUpExercise()
        else: return
        self.run_webcam_loop(active_exercise)

    def run_webcam_loop(self, exercise_module):
        self.root.withdraw()
        cap = cv2.VideoCapture(0)
        pipe = TrackingPipeline(exercise_module)

        # 5-second countdown
        start_time = time.time()
        while True:
            ok, frame = cap.read()
            if not ok: break
            remaining = int(5 - (time.time() - start_time)) + 1
            if remaining <= 0: break
            display = frame.copy()
            h, w, _ = display.shape
            cv2.putText(display, str(remaining), (w//2-50, h//2+50), cv2.FONT_HERSHEY_SIMPLEX, 5, (255, 255, 255), 10, cv2.LINE_AA)
            cv2.imshow("Form-Logic (Press 'Q' to Exit)", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cap.release(); cv2.destroyAllWindows(); self.root.deiconify(); return

        # Active Tracking
        try:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok: break
                packet = pipe.process_bgr(frame)
                display = frame.copy()
                if packet.landmarks is not None: draw_pose_skeleton(display, packet.landmarks)
                draw_squat_hud(display, packet.exercise.metrics)
                cv2.imshow("Form-Logic (Press 'Q' to Exit)", display)
                if cv2.waitKey(1) & 0xFF == ord("q"): break
        finally:
            # --- NEW LOGGING LOGIC ---
            summary = exercise_module.get_summary()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "exercise": exercise_module.id,
                "metrics": summary
            }
            self.save_log(log_entry)

            cap.release()
            pipe.close()
            cv2.destroyAllWindows()
            self.root.deiconify()

            # Show summary window
            self.show_summary_window(log_entry)

    def save_log(self, entry):
        filename = "history.json"
        history = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    history = json.load(f)
            except: pass
        history.append(entry)
        with open(filename, 'w') as f:
            json.dump(history, f, indent=4)

    def show_summary_window(self, log):
        summary_win = tk.Toplevel(self.root)
        summary_win.title("Workout Summary")
        summary_win.geometry("400x400")

        tk.Label(summary_win, text="Session Summary", font=("Helvetica", 16, "bold")).pack(pady=10)
        tk.Label(summary_win, text=f"Time: {log['timestamp']}", font=("Helvetica", 10)).pack()
        tk.Label(summary_win, text=f"Exercise: {log['exercise'].capitalize()}", font=("Helvetica", 12, "bold")).pack(pady=5)

        metrics_frame = tk.Frame(summary_win)
        metrics_frame.pack(pady=10, padx=20, fill="both")

        for key, value in log['metrics'].items():
            readable_key = key.replace("_", " ").capitalize()
            label_text = f"{readable_key}: {value}"
            tk.Label(metrics_frame, text=label_text, font=("Helvetica", 11)).pack(anchor="w")

        ttk.Button(summary_win, text="Close", command=summary_win.destroy).pack(pady=20)

    def view_history_stub(self):
        messagebox.showinfo("Coming Soon", "You can view the raw 'history.json' file in your project folder now. Full history UI coming in the next update!")

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    app = FormLogicUI(root)
    root.mainloop()