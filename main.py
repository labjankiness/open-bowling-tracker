"""CLI entry point for the Live Bowling Tracker.

Two subcommands:
    track   Biomechanics analysis from a bowler-approach video (pose-based).
    score   Auto-score a full recorded game from a pin-deck video.

Examples:
    python main.py track --video data/input/back_view.mp4 --view back
    python main.py track --video data/input/side_view.mp4 --view side --save-video
    python main.py score --pin-video data/input/pin_deck_game1.mp4
"""

import argparse
import sys
from pathlib import Path

import config
from core.game_tracker import GameTracker
from core.metrics_logger import GameLogger, MetricsLogger
from core.pin_detector import PinDeckAnalyzer
from core.tracker import BowlingTracker


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Two-handed bowling tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    track_parser = subparsers.add_parser("track", help="Biomechanics analysis from an approach video")
    track_parser.add_argument("--video", required=True, help="Path to the input video file")
    track_parser.add_argument(
        "--view",
        required=True,
        choices=config.SUPPORTED_VIEWS,
        help="Camera angle the video was filmed from",
    )
    track_parser.add_argument(
        "--pixels-per-meter",
        type=float,
        default=None,
        help="Optional calibration factor to report distances/velocity in metric units",
    )
    track_parser.add_argument(
        "--save-video",
        action="store_true",
        help="Write an annotated (pose-overlay) copy of the video to data/output/",
    )
    track_parser.add_argument(
        "--log-path",
        default=str(config.METRICS_LOG_PATH),
        help="CSV file to append this run's peak metrics to",
    )

    score_parser = subparsers.add_parser("score", help="Auto-score a full game from a pin-deck video")
    score_parser.add_argument("--pin-video", required=True, help="Path to the pin-deck video for one full game")
    score_parser.add_argument(
        "--game-log-path",
        default=str(config.GAME_LOG_PATH),
        help="CSV file to append this game's scorecard to",
    )

    return parser


def run_track(args: argparse.Namespace) -> int:
    annotate_output_path = None
    if args.save_video:
        stem = Path(args.video).stem
        annotate_output_path = str(config.DATA_OUTPUT_DIR / f"{stem}_{args.view}_annotated.mp4")

    tracker = BowlingTracker(
        video_path=args.video,
        view=args.view,
        pixels_per_meter=args.pixels_per_meter,
        annotate_output_path=annotate_output_path,
    )

    print(f"Processing '{args.video}' ({args.view}-view)...")
    summary = tracker.run()

    logger = MetricsLogger(log_path=Path(args.log_path))
    logger.log_run(summary)

    print(f"Frames processed : {summary.frame_count} ({summary.fps} fps, {summary.duration_s}s)")
    print(f"Peak spine tilt              : {summary.peak_spine_tilt_deg} deg")
    print(f"Peak knee flexion            : {summary.peak_knee_flexion_deg} deg")
    print(f"Peak hip-shoulder separation : {summary.peak_hip_shoulder_separation_deg} deg")
    print(f"Peak lateral ball-ankle dist : {summary.peak_lateral_ball_ankle_distance_px}")
    print(f"Peak release velocity        : {summary.peak_release_velocity_px_s}")
    print(f"Logged to '{args.log_path}'")
    if annotate_output_path:
        print(f"Annotated video saved to '{annotate_output_path}'")

    return 0


def run_score(args: argparse.Namespace) -> int:
    tracker = GameTracker(pin_video_path=args.pin_video, analyzer=PinDeckAnalyzer())

    print(f"Analyzing pin deck in '{args.pin_video}'...")
    summary = tracker.run()

    logger = GameLogger(log_path=Path(args.game_log_path))
    logger.log_game(summary)

    print(f"Detected rolls : {summary.rolls}")
    print("Frame | Rolls       | Frame score | Cumulative")
    for frame in summary.frames:
        tag = "STRIKE" if frame.is_strike else "SPARE" if frame.is_spare else ""
        print(f"{frame.frame_number:>5} | {str(frame.rolls):<11} | {frame.frame_score:>11} | {frame.cumulative_score:>10} {tag}")

    if summary.is_complete:
        print(f"\nFinal score: {summary.total_score}")
    else:
        print(f"\nGame incomplete ({len(summary.frames)}/10 frames resolved) — "
              f"check camera framing/lighting if this looks wrong.")

    print(f"Logged to '{args.game_log_path}'")
    return 0


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "track":
        return run_track(args)
    if args.command == "score":
        return run_score(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
