#!/usr/bin/env python3
"""Batch Learner: Trains a personal Bowler Baseline Profile across all bowling videos.

Extracts biomechanical distributions (spine tilt, right slide knee flexion,
hip-shoulder coil, release velocity, lateral drift) across all training clips
to construct a personalized baseline model saved to `data/bowler_profile.json`.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.tracker import BowlingTracker


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Computes mean, median, min, max, and standard deviation."""
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return {"count": 0, "mean": 0.0, "median": 0.0, "std_dev": 0.0, "min": 0.0, "max": 0.0}
    
    n = len(clean)
    clean.sort()
    mean_val = sum(clean) / n
    median_val = clean[n // 2] if n % 2 != 0 else (clean[n // 2 - 1] + clean[n // 2]) / 2.0
    variance = sum((x - mean_val) ** 2 for x in clean) / n
    std_dev = math.sqrt(variance)

    return {
        "count": n,
        "mean": round(mean_val, 2),
        "median": round(median_val, 2),
        "std_dev": round(std_dev, 2),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2)
    }


def train_bowler_profile(
    training_dir: Path = config.DATA_INPUT_DIR / "training_videos",
    output_profile_path: Path = PROJECT_ROOT / "data" / "bowler_profile.json",
    handedness: str = config.HANDEDNESS_LEFT,
    style: str = config.STYLE_TWO_HANDED,
    max_videos: int = None
) -> Dict[str, Any]:
    print(f"==================================================")
    print(f"🎳 Training Bowler Baseline Model")
    print(f"Handedness: {handedness.upper()} | Style: {style.upper()}")
    print(f"Scanning directory: {training_dir}")
    print(f"==================================================")

    if not training_dir.exists():
        print(f"Error: Training folder does not exist at {training_dir}")
        return {}

    video_files = sorted(
        [p for p in training_dir.glob("*.*") if p.suffix.lower() in (".mp4", ".mov", ".m4v")],
        key=lambda f: f.stat().st_size
    )

    if max_videos:
        video_files = video_files[:max_videos]

    total = len(video_files)
    print(f"Found {total} video clips to process.\n")

    if total == 0:
        print("No videos found.")
        return {}

    spine_tilts = []
    knee_flexions = []
    hip_shoulder_seps = []
    velocities_px_s = []
    ball_speeds_mph = []
    lateral_distances = []
    processed_shots = []

    for i, vid_path in enumerate(video_files, 1):
        print(f"[{i}/{total}] Analyzing: {vid_path.name} ({round(vid_path.stat().st_size / 1048576, 1)} MB)...", end=" ", flush=True)
        try:
            tracker = BowlingTracker(
                video_path=str(vid_path),
                view=config.VIEW_BACK,
                handedness=handedness,
                style=style
            )
            summary = tracker.run()

            # Filter out corrupt/empty readings
            if summary.frame_count > 10 and summary.peak_spine_tilt_deg > 0:
                peak_vel = summary.peak_release_velocity_px_s or 0.0
                est_mph = min(22.0, max(11.0, peak_vel * 0.0055 if peak_vel > 500 else 16.2))

                spine_tilts.append(summary.peak_spine_tilt_deg)
                knee_flexions.append(summary.peak_knee_flexion_deg)
                hip_shoulder_seps.append(summary.peak_hip_shoulder_separation_deg)
                velocities_px_s.append(peak_vel)
                ball_speeds_mph.append(est_mph)
                lateral_distances.append(summary.peak_lateral_ball_ankle_distance_px)

                processed_shots.append({
                    "video_name": vid_path.name,
                    "spine_tilt_deg": summary.peak_spine_tilt_deg,
                    "knee_flexion_deg": summary.peak_knee_flexion_deg,
                    "hip_shoulder_sep_deg": summary.peak_hip_shoulder_separation_deg,
                    "ball_speed_mph": round(est_mph, 1),
                    "lateral_drift_px": summary.peak_lateral_ball_ankle_distance_px
                })
                print(f"✓ (Speed: {round(est_mph, 1)} mph | Knee: {round(summary.peak_knee_flexion_deg, 1)}° | Spine: {round(summary.peak_spine_tilt_deg, 1)}°)")
            else:
                print("⚠ (Skipped: insufficient pose visibility)")

        except Exception as e:
            print(f"✗ Error: {e}")

    # Aggregate distributions
    profile = {
        "model_version": "2.0-heavy",
        "created_at": datetime.now().isoformat(),
        "bowler_handedness": handedness,
        "delivery_style": style,
        "training_clips_processed": len(processed_shots),
        "total_clips_scanned": total,
        "baselines": {
            "ball_speed_mph": calculate_stats(ball_speeds_mph),
            "knee_flexion_at_release_deg": calculate_stats(knee_flexions),
            "spine_tilt_at_release_deg": calculate_stats(spine_tilts),
            "hip_shoulder_separation_deg": calculate_stats(hip_shoulder_seps),
            "lateral_drift_px": calculate_stats(lateral_distances),
        },
        "shots_history": processed_shots
    }

    output_profile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    print("\n" + "=" * 50)
    print("✅ Bowler Baseline Profile Generated Successfully!")
    print(f"Saved to: {output_profile_path}")
    print(f"Clips Analyzed: {len(processed_shots)} of {total}")
    if processed_shots:
        print(f"  • Avg Ball Speed: {profile['baselines']['ball_speed_mph']['mean']} mph (±{profile['baselines']['ball_speed_mph']['std_dev']})")
        print(f"  • Avg Slide Knee Bend: {profile['baselines']['knee_flexion_at_release_deg']['mean']}° (±{profile['baselines']['knee_flexion_at_release_deg']['std_dev']})")
        print(f"  • Avg Spine Tilt: {profile['baselines']['spine_tilt_at_release_deg']['mean']}° (±{profile['baselines']['spine_tilt_at_release_deg']['std_dev']})")
    print("=" * 50)

    return profile


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train bowler baseline model from training clips.")
    parser.add_argument("--handedness", default="left", choices=["left", "right", "auto"], help="Bowler handedness")
    parser.add_argument("--style", default="2-handed", choices=["2-handed", "1-handed", "auto"], help="Delivery style")
    parser.add_argument("--max-videos", type=int, default=None, help="Limit number of videos to process")
    args = parser.parse_args()

    train_bowler_profile(handedness=args.handedness, style=args.style, max_videos=args.max_videos)
