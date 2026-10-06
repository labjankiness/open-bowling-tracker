"""Appends per-run peak metrics and per-game scorecards to structured CSV logs."""

import csv
import json
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from core.game_tracker import GameSummary


@dataclass
class RunSummary:
    """One row of `metrics_log.csv`: the peak metrics from a single video run."""

    timestamp: str
    video_name: str
    view: str
    frame_count: int
    fps: float
    duration_s: float
    peak_spine_tilt_deg: float
    peak_knee_flexion_deg: float
    peak_hip_shoulder_separation_deg: float
    peak_lateral_ball_ankle_distance_px: float
    peak_release_velocity_px_s: float
    handedness: str = "left"
    delivery_style: str = "2-handed"
    bowling_ball: str = "Standard Reactive Resin Ball"
    peak_lateral_drift_boards: float = 0.0


class MetricsLogger:
    """Creates/appends to `metrics_log.csv`, writing the header on first use."""

    def __init__(self, log_path: Path = config.METRICS_LOG_PATH) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fieldnames = [f.name for f in fields(RunSummary)]
        if not self.log_path.exists():
            with self.log_path.open("w", newline="") as f:
                csv.DictWriter(f, fieldnames=self._fieldnames).writeheader()

    def log_run(self, summary: RunSummary) -> None:
        with self.log_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._fieldnames)
            writer.writerow(summary.__dict__)

    @staticmethod
    def timestamp_now() -> str:
        return datetime.now().isoformat(timespec="seconds")


class GameLogger:
    """Creates/appends to `game_log.csv`, one row per fully or partially scored game."""

    _FIELDNAMES = [
        "timestamp",
        "video_name",
        "rolls",
        "total_score",
        "is_complete",
        "frame_scores",
    ]

    def __init__(self, log_path: Path = config.GAME_LOG_PATH) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            with self.log_path.open("w", newline="") as f:
                csv.DictWriter(f, fieldnames=self._FIELDNAMES).writeheader()

    def log_game(self, summary: "GameSummary") -> None:
        row = {
            "timestamp": MetricsLogger.timestamp_now(),
            "video_name": summary.video_name,
            "rolls": json.dumps(summary.rolls),
            "total_score": summary.total_score if summary.total_score is not None else "",
            "is_complete": summary.is_complete,
            "frame_scores": json.dumps([f.cumulative_score for f in summary.frames]),
        }
        with self.log_path.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=self._FIELDNAMES).writerow(row)
