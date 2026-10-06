import os
from pathlib import Path


# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DATA_THUMBNAILS_DIR = PROJECT_ROOT / "data" / "thumbnails"
TRAINING_VIDEOS_DIR = Path(os.environ.get("TRAINING_VIDEOS_DIR", str(PROJECT_ROOT / "data" / "training_videos")))
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
# Heavy model has the largest receptive field and deepest convolutional layers,
# providing superior occlusion handling during bowling backswings and releases.
POSE_MODEL_PATH = str(PROJECT_ROOT / "models" / "pose_landmarker_heavy.task")
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

# --- Supported camera views ---
VIEW_BACK = "back"
VIEW_SIDE = "side"
SUPPORTED_VIEWS = (VIEW_BACK, VIEW_SIDE)

# --- Bowler handedness & style options ---
HANDEDNESS_LEFT = "left"
HANDEDNESS_RIGHT = "right"
HANDEDNESS_AUTO = "auto"
SUPPORTED_HANDEDNESS = (HANDEDNESS_LEFT, HANDEDNESS_RIGHT, HANDEDNESS_AUTO)

STYLE_TWO_HANDED = "2-handed"
STYLE_ONE_HANDED = "1-handed"
STYLE_AUTO = "auto"
SUPPORTED_STYLES = (STYLE_TWO_HANDED, STYLE_ONE_HANDED, STYLE_AUTO)

# --- Visibility threshold: landmarks below this confidence are treated as missing ---
LANDMARK_VISIBILITY_THRESHOLD = 0.5

# --- Frame-to-frame ball-displacement outlier rejection (see core/tracker.py) ---
# A displacement more than this many times the recent median is treated as a
# single-frame landmark glitch rather than real motion.
VELOCITY_OUTLIER_FACTOR = 6.0
VELOCITY_OUTLIER_MIN_SAMPLES = 5
VELOCITY_OUTLIER_WINDOW = 15

# --- Pin-deck analyzer defaults (see core/pin_detector.py for tuning guidance) ---
PIN_DECK_ROI = None  # (x, y, width, height) in pixels, or None for full frame
PIN_MIN_AREA = 150.0
PIN_MAX_AREA = 6000.0
PIN_MOTION_THRESHOLD = 20000.0
PIN_REST_FRAMES_REQUIRED = 8
