# FormLogic

**Real-time AI-powered workout form tracker and personal fitness coach — no wearables, no gym membership, just your webcam.**

FormLogic uses computer vision and pose estimation to watch you exercise, count your reps, measure your range of motion, and coach you on your form after every session. It also tracks your strength progress and bodyweight over time, and includes an AI chat coach powered by ChatGPT that has full access to your fitness data.

---

## Features

### Real-time Form Tracking
- Tracks **Squats**, **Bicep Curls**, and **Pull-ups** via your webcam using [MediaPipe](https://mediapipe.dev/) pose landmarks.
- Counts reps automatically using a phase-state machine (eccentric → bottom → concentric) with lenient thresholds so imperfect reps still count — and generate coaching feedback.
- Measures key metrics per exercise in real time:
  - **Squat**: knee angle depth %, torso lean
  - **Bicep Curl**: concentric/eccentric depth %, torso sway, rep duration
  - **Pull-up**: eccentric extension, head clearance percentage above the bar

### Post-Session Coaching
- After each session, the app generates a written summary with specific form tips (e.g. "You're not reaching a full dead hang — lower until your elbows are nearly straight before each pull" or "Average torso lean was high — keep your chest tall and elbows fixed").
- Tips are deduplicated and shown on the **Home** tab under **Today's Feedback**.

### Workout History
- Every saved session is logged to `history.json` with timestamps, rep counts, weights, and all form metrics.
- The **History** tab lists all past sessions; clicking any opens its full session summary.

### Strength Progress (Self Tab)
- Compares your **last two sessions** of each exercise using the [Epley Formula](https://en.wikipedia.org/wiki/One-repetition_maximum) (1RM = weight × (1 + reps ÷ 30)).
- Displays a colour-coded trend: green ↑ (improved), grey → (consistent), red ↓ (declined), with percentage delta.
- For bodyweight exercises (pull-ups with no added weight), rep count is used as the comparison score.

### Bodyweight Tracking (Self Tab)
- Every time you save a new weight in Settings, the date and value are logged to `weight_log.json`.
- The **Track Bodyweight Changes** button expands to show a history table and personalised feedback based on your goal:
  - **Muscle Building / Strength**: praises 0.25–0.5 lbs/week gain; warns above 1 lb/week as likely excess fat.
  - **Lose Weight**: celebrates 0.5–1 lb/week loss; warns against aggressive deficit (>2 lbs/week).
  - **Gain Weight**: encourages consistent gain with actionable calorie tips.

### Your Stats (Home Tab)
- Shows your all-time best session for each exercise, calculated via the Epley formula.
- Displays as "245 lbs × 8 reps · est. 1RM 311 lbs" or "17 reps (bodyweight)" for unweighted sets.

### FormCoach — AI Chat (Chat Tab)
- A ChatGPT-powered assistant with full context of your fitness data.
- Every conversation includes your profile, bodyweight history, all recent sessions with metrics and estimated 1RMs, and an explicit strength trend verdict (IMPROVED / DECLINED / CONSISTENT) for each exercise.
- Ask things like *"How is my weight loss goal going?"*, *"Compare my last two squat sessions"*, or *"What should I focus on this week?"*
- Requires an OpenAI API key (stored locally in `api_config.json`, never committed).

### Rep Counter Mode
- In addition to a fixed target rep count, you can select **Rep Counter** mode — the session records indefinitely until you stop it manually.

---

## Supported Exercises

| Exercise | Tracked Metrics |
|---|---|
| Squat | Knee angle depth %, torso lean, rep speed, % reps parallel or below |
| Bicep Curl | Concentric depth %, eccentric extension %, torso sway, rep duration |
| Pull-up | Eccentric extension %, head clearance % above bar, % reps with full dead hang |

---

## Requirements

- **Python 3.11 or 3.12**
- A **webcam** accessible at index 0 (or specify `--camera N`)
- An **OpenAI API key** for the FormCoach chat feature (optional — the rest of the app works without it)

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Form-Logic.git
cd Form-Logic
```

### 2. Create a virtual environment and install dependencies

**Windows (PowerShell) — recommended:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_venv.ps1
```

This script creates `.venv`, upgrades pip, and installs all dependencies from `requirements.txt` with a clean MediaPipe wheel.

**Manual (any platform):**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install openai   # required for the FormCoach chat tab
```

### 3. Run the full application

```bash
python app.py
```

On first launch the app will open an onboarding screen asking for your name, height, weight, and training goal. This data is stored locally in `profile.json`.

### 4. (Optional) Headless demo mode

A minimal webcam loop that prints tracking metrics as JSON to stdout — useful for testing the pose pipeline without the GUI:

```bash
python run_demo.py              # JSON output only
python run_demo.py --preview    # opens a window with skeleton + squat overlay
python run_demo.py --camera 1   # use a different camera index
```

---

## Project Structure

```
Form-Logic/
├── app.py                        # Main entry point — wires all views together
├── run_demo.py                   # Headless pose-tracking demo
├── requirements.txt
├── scripts/
│   └── setup_venv.ps1            # One-click venv setup (Windows)
├── lift_tracker/
│   ├── exercises/
│   │   ├── base.py               # Abstract Exercise base class
│   │   ├── squat.py              # Squat rep detection + form metrics
│   │   ├── bicep_curl.py         # Bicep curl rep detection + form metrics
│   │   └── pullup.py             # Pull-up rep detection + form metrics
│   ├── pose/
│   │   ├── landmarks.py          # Landmark index definitions
│   │   ├── skeleton.py           # Skeleton drawing helpers
│   │   └── mediapipe_backend.py  # MediaPipe pose estimator wrapper
│   ├── viz/
│   │   └── squat_hud.py          # Real-time squat overlay HUD
│   ├── geometry.py               # Angle / vector math utilities
│   ├── form_feedback.py          # Post-session coaching tip generator
│   ├── pipeline.py               # Frame-by-frame tracking pipeline
│   └── profile.py                # UserProfile dataclass + TrainingGoal enum
└── ui/
    ├── app.py                    # (see root app.py)
    ├── theme.py                  # Colors, fonts, gradients
    ├── components.py             # RoundedPanel, BottomNav, ScrollableFrame, etc.
    ├── paths.py                  # Centralised file path constants
    ├── profile_store.py          # Load/save profile, weight log
    ├── dpi.py                    # Windows Per-Monitor DPI scaling
    ├── onboarding_dialog.py      # First-run setup modal
    ├── home_view.py              # Home tab (start workout, today's feedback, stats)
    ├── history_view.py           # Workout history list
    ├── session_summary_view.py   # Post-session summary screen
    ├── recording_window.py       # Live webcam recording UI
    ├── self_view.py              # Profile, bodyweight tracking, lift progress
    ├── settings_view.py          # Edit profile settings
    └── chat_view.py              # FormCoach AI chat tab
```

---

## Local Data Files

All data is stored locally in the project root. None of these files are committed to git.

| File | Contents |
|---|---|
| `profile.json` | Name, height, weight, training goal |
| `history.json` | All saved workout sessions |
| `weight_log.json` | Timestamped bodyweight entries |
| `api_config.json` | OpenAI API key |

---

## How Rep Counting Works

Each exercise uses a **phase-state machine** that steps through `STANDING → ECCENTRIC → BOTTOM → CONCENTRIC → STANDING`. A rep is counted when the full cycle completes and the movement clears minimum depth thresholds. Thresholds are intentionally lenient so imperfect reps count — but the deviation from ideal form is tracked separately and surfaced as coaching feedback. For example, a pull-up where the user doesn't reach a full dead hang still counts, but the session summary will note that dead hang percentage was low.

---

## FormLogic Chat Setup

1. Navigate to the **Chat** tab.
2. Enter your OpenAI API key (get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)).
3. The key is saved to `api_config.json` locally and is never pushed to git.
4. Ask anything — FormCoach has full access to your profile, workout history, weight log, and pre-computed strength trends.

---

## Technologies Used

| Technology | Role |
|---|---|
| [MediaPipe Pose](https://mediapipe.dev/) | Real-time 33-point body pose estimation |
| [OpenCV](https://opencv.org/) | Webcam capture and frame processing |
| [Tkinter](https://docs.python.org/3/library/tkinter.html) + [Pillow](https://pillow.readthedocs.io/) | Desktop GUI with custom rounded panels and gradients |
| [OpenAI API](https://platform.openai.com/) (gpt-4o-mini) | FormCoach AI chat with fitness data context |
| Python standard library | JSON persistence, threading, dataclasses |

---

## License

See [LICENSE](LICENSE).
