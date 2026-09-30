# Live Bowling Tracker

Computer-vision toolkit for two-handed bowling: a MediaPipe-Pose biomechanics
tracker for the approach/release, and a classical-CV pin-deck analyzer that
auto-scores a full recorded game.

## 1. Biomechanics tracking (`track`)

Processes a back-view or side-view approach video and computes, per frame:

- **Spine tilt** — trunk-line angle from vertical
- **Knee flexion** — bend of the sliding-leg knee
- **Hip-to-shoulder separation** — torso coil ("X-factor") between hip and shoulder lines
- **Lateral ball-to-ankle distance** — horizontal ball drift relative to the sliding foot
- **Release velocity** — frame-to-frame speed of the ball (wrist-midpoint proxy)

```bash
python main.py track --video data/input/back_view.mp4 --view back
python main.py track --video data/input/side_view.mp4 --view side --save-video
```

- `--view {back,side}` (required) — tells the tracker which leg/side to read for
  knee flexion and lateral drift.
- `--save-video` — writes a pose-overlay annotated copy to `data/output/`.
- `--pixels-per-meter <float>` — optional calibration factor to report distance
  and velocity metrics in meters/meters-per-second instead of pixels.

Each run appends one row of peak metrics to `logs/metrics_log.csv`.

## 2. Automatic game scoring (`score`)

Record a full game with a **fixed camera pointed at the pin deck** (separate
from the bowler-approach camera used for `track`). The analyzer watches for
motion (a ball rolling through / pins falling) followed by stillness, counts
standing pins at each rest point, and converts the sequence into a roll-by-roll
score using standard 10-pin rules (strikes, spares, 10th-frame bonus rolls).

```bash
python main.py score --pin-video data/input/pin_deck_game1.mp4
```

Output includes the full frame-by-frame scorecard and final score, and appends
one row (roll sequence, frame scores, total) to `logs/game_log.csv`.

**Camera setup matters.** This is a classical-CV pipeline (thresholding +
contour counting + frame differencing), not a trained model, so accuracy
depends on your setup:
- Mount the camera so it has a steady, unobstructed view of the full pin deck.
- Good, even lighting with pins visibly brighter than the lane/background helps
  contour-based counting a lot.
- If detection misses throws or double-counts them, tune the constructor
  arguments on `PinDeckAnalyzer` (`core/pin_detector.py`): `roi` to crop out
  distracting background, `motion_threshold`/`rest_frames_required` to match
  your frame rate, and `min_pin_area`/`max_pin_area` to match pin size at your
  camera's resolution and distance.
- If a game ends up "incomplete," the CLI tells you how many frames it
  resolved — that's usually a sign the thresholds need adjusting for your feed.

## Project layout

```
LiveBowlingTracker/
├── main.py                  # CLI entry point (track / score subcommands)
├── config.py                # Paths, landmark indices, pin-detector defaults
├── core/
│   ├── pose_estimator.py    # MediaPipe Pose wrapper (perception only)
│   ├── analytics.py         # Pure NumPy biomechanics math
│   ├── tracker.py           # Orchestrates video -> pose -> metrics -> summary
│   ├── pin_detector.py      # Pin-deck CV: standing-pin count + motion segmentation
│   ├── scoring.py           # Pure 10-pin scoring engine (rolls -> scorecard)
│   ├── game_tracker.py      # Orchestrates pin video -> rolls -> scorecard
│   └── metrics_logger.py    # Appends to logs/metrics_log.csv and logs/game_log.csv
├── data/
│   ├── input/                # Put source videos here (approach + pin-deck)
│   └── output/                # Annotated (pose-overlay) videos land here
├── logs/
│   ├── metrics_log.csv       # One row per `track` run (created automatically)
│   └── game_log.csv          # One row per `score` run (created automatically)
├── tests/
│   ├── test_analytics.py     # Unit tests for the biomechanics math core
│   ├── test_scoring.py       # Unit tests for the 10-pin scoring engine
│   └── test_pin_detector.py  # Unit tests for observation -> roll conversion
└── requirements.txt
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Tests

```bash
pip install pytest
pytest tests/
```

## Notes on the ball position

MediaPipe Pose has no ball landmark. Since a two-handed delivery keeps the ball
cradled in both hands through most of the approach, `analytics.estimate_ball_position`
uses the midpoint of the left/right wrist landmarks as a proxy. This is isolated
in its own function so a dedicated ball detector (e.g. a Hough-circle color
tracker, or a small object-detection model) can be substituted later without
touching any of the downstream metric calculations.
