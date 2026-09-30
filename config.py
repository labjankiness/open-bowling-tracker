"""Project-wide constants for the Live Bowling Tracker."""

from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
LOGS_DIR = PROJECT_ROOT / "logs"
METRICS_LOG_PATH = LOGS_DIR / "metrics_log.csv"
GAME_LOG_PATH = LOGS_DIR / "game_log.csv"

# --- MediaPipe Pose landmark indices used by the analytics core ---
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_WRIST = 15
RIGHT_WRIST = 16

REQUIRED_LANDMARKS = [
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_WRIST, RIGHT_WRIST,
]

# --- MediaPipe Pose model settings ---
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6
MODEL_COMPLEXITY = 1

# --- Supported camera views ---
VIEW_BACK = "back"
VIEW_SIDE = "side"
SUPPORTED_VIEWS = (VIEW_BACK, VIEW_SIDE)

# --- Visibility threshold: landmarks below this confidence are treated as missing ---
LANDMARK_VISIBILITY_THRESHOLD = 0.5

# --- Pin-deck analyzer defaults (see core/pin_detector.py for tuning guidance) ---
PIN_DECK_ROI = None  # (x, y, width, height) in pixels, or None for full frame
PIN_MIN_AREA = 150.0
PIN_MAX_AREA = 6000.0
PIN_MOTION_THRESHOLD = 20000.0
PIN_REST_FRAMES_REQUIRED = 8
