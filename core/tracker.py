"""Frame-by-frame video processing pipeline for the bowling tracker.

Wires together `PoseEstimator` (perception) and the pure functions in
`analytics` (math) into a single `BowlingTracker` that consumes a video
file and produces a per-frame metrics history plus a peak-value summary.
"""

from collections import deque
from pathlib import Path
from statistics import median
from typing import List, Optional

import cv2
import numpy as np

import config
from core import analytics
from core.metrics_logger import RunSummary
from core.pose_estimator import FrameLandmarks, PoseEstimator


class BowlingTracker:
    """Runs pose estimation + biomechanical analytics over one video."""

    def __init__(
        self,
        video_path: str,
        view: str,
        pixels_per_meter: Optional[float] = None,
        annotate_output_path: Optional[str] = None,
    ) -> None:
        if view not in config.SUPPORTED_VIEWS:
            raise ValueError(f"view must be one of {config.SUPPORTED_VIEWS}, got {view!r}")

        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {self.video_path}")

        self.view = view
        self.pixels_per_meter = pixels_per_meter
        self.annotate_output_path = annotate_output_path

        self.history: List[analytics.FrameMetrics] = []
        self.fps: float = 0.0
        self.frame_count: int = 0

        # Rolling window of accepted frame-to-frame ball displacements, used
        # to reject single-frame landmark glitches (see _is_displacement_outlier).
        self._recent_displacements: deque = deque(maxlen=config.VELOCITY_OUTLIER_WINDOW)

    def run(self) -> RunSummary:
        """Process the full video and return the peak-value summary."""
        capture = cv2.VideoCapture(str(self.video_path))
        if not capture.isOpened():
            raise IOError(f"Could not open video: {self.video_path}")

        self.fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        dt_seconds = 1.0 / self.fps

        writer = self._build_writer(capture) if self.annotate_output_path else None
        prev_ball_position: Optional[np.ndarray] = None

        try:
            with PoseEstimator(fps=self.fps) as estimator:
                frame_index = 0
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    frame_landmarks = estimator.process(frame)
                    if frame_landmarks is not None:
                        metrics, prev_ball_position = self._compute_frame_metrics(
                            frame_landmarks, frame_index, dt_seconds, prev_ball_position
                        )
                        if metrics is not None:
                            self.history.append(metrics)

                        if writer is not None:
                            writer.write(estimator.draw(frame, frame_landmarks))
                    elif writer is not None:
                        writer.write(frame)

                    frame_index += 1

                self.frame_count = frame_index
        finally:
            capture.release()
            if writer is not None:
                writer.release()

        return self._build_summary()

    def _compute_frame_metrics(
        self,
        landmarks: FrameLandmarks,
        frame_index: int,
        dt_seconds: float,
        prev_ball_position: Optional[np.ndarray],
    ):
        required = (
            config.LEFT_SHOULDER, config.RIGHT_SHOULDER,
            config.LEFT_HIP, config.RIGHT_HIP,
            config.LEFT_KNEE, config.RIGHT_KNEE,
            config.LEFT_ANKLE, config.RIGHT_ANKLE,
            config.LEFT_WRIST, config.RIGHT_WRIST,
        )
        if not landmarks.all_visible(*required):
            return None, prev_ball_position

        left_shoulder = landmarks.get(config.LEFT_SHOULDER).xy
        right_shoulder = landmarks.get(config.RIGHT_SHOULDER).xy
        left_hip = landmarks.get(config.LEFT_HIP).xy
        right_hip = landmarks.get(config.RIGHT_HIP).xy
        left_knee = landmarks.get(config.LEFT_KNEE).xy
        right_knee = landmarks.get(config.RIGHT_KNEE).xy
        left_ankle = landmarks.get(config.LEFT_ANKLE).xy
        right_ankle = landmarks.get(config.RIGHT_ANKLE).xy
        left_wrist = landmarks.get(config.LEFT_WRIST).xy
        right_wrist = landmarks.get(config.RIGHT_WRIST).xy

        ball_position = analytics.estimate_ball_position(left_wrist, right_wrist)

        displacement = None
        if prev_ball_position is not None:
            displacement = analytics.calculate_euclidean_distance(prev_ball_position, ball_position)
            if self._is_displacement_outlier(displacement):
                # A single-frame landmark glitch (e.g. a misplaced wrist) can
                # otherwise produce an implausible velocity/lateral-distance
                # spike; skip this frame rather than let it corrupt metrics
                # and peaks, and keep the last good ball position for the
                # next frame's comparison.
                return None, prev_ball_position

        # Lead-leg selection differs by view: back-view tracks the sliding
        # (front) leg's knee/ankle for flexion and lateral drift; side-view
        # is assumed to be filmed from the sliding-leg side already.
        knee, ankle = (left_knee, left_ankle) if self.view == config.VIEW_BACK else (right_knee, right_ankle)
        hip_for_knee = left_hip if self.view == config.VIEW_BACK else right_hip

        spine_tilt = analytics.calculate_spine_tilt(left_shoulder, right_shoulder, left_hip, right_hip)
        knee_flexion = analytics.calculate_knee_flexion(hip_for_knee, knee, ankle)
        hip_shoulder_separation = analytics.calculate_hip_shoulder_separation(
            left_shoulder, right_shoulder, left_hip, right_hip
        )
        lateral_ball_ankle_distance = analytics.calculate_lateral_ball_ankle_distance(
            ball_position, ankle, self.pixels_per_meter
        )

        velocity = 0.0
        if displacement is not None:
            self._recent_displacements.append(displacement)
            distance = displacement
            if self.pixels_per_meter:
                distance /= self.pixels_per_meter
            velocity = distance / dt_seconds if dt_seconds > 0 else 0.0

        metrics = analytics.FrameMetrics(
            frame_index=frame_index,
            timestamp_s=frame_index * dt_seconds,
            spine_tilt_deg=spine_tilt,
            knee_flexion_deg=knee_flexion,
            hip_shoulder_separation_deg=hip_shoulder_separation,
            lateral_ball_ankle_distance=lateral_ball_ankle_distance,
            ball_velocity=velocity,
        )
        return metrics, ball_position

    def _is_displacement_outlier(self, displacement: float) -> bool:
        """True if `displacement` is implausibly large next to recent frames.

        Calibration-free: uses the median of recently *accepted* ball
        displacements as a running baseline rather than an absolute
        pixel/velocity threshold, since that baseline scales naturally with
        camera distance, resolution, and frame rate.
        """
        if len(self._recent_displacements) < config.VELOCITY_OUTLIER_MIN_SAMPLES:
            return False
        baseline = median(self._recent_displacements)
        if baseline <= 0:
            return False
        return displacement > baseline * config.VELOCITY_OUTLIER_FACTOR

    def _build_summary(self) -> RunSummary:
        from core.metrics_logger import MetricsLogger

        duration_s = self.frame_count / self.fps if self.fps else 0.0

        if not self.history:
            peak_spine_tilt = peak_knee_flexion = peak_separation = 0.0
            peak_lateral_distance = peak_velocity = 0.0
        else:
            peak_spine_tilt = max(m.spine_tilt_deg for m in self.history)
            peak_knee_flexion = max(m.knee_flexion_deg for m in self.history)
            peak_separation = max(abs(m.hip_shoulder_separation_deg) for m in self.history)
            peak_lateral_distance = max(m.lateral_ball_ankle_distance for m in self.history)
            peak_velocity = max(m.ball_velocity for m in self.history)

        return RunSummary(
            timestamp=MetricsLogger.timestamp_now(),
            video_name=self.video_path.name,
            view=self.view,
            frame_count=self.frame_count,
            fps=round(self.fps, 3),
            duration_s=round(duration_s, 3),
            peak_spine_tilt_deg=round(peak_spine_tilt, 3),
            peak_knee_flexion_deg=round(peak_knee_flexion, 3),
            peak_hip_shoulder_separation_deg=round(peak_separation, 3),
            peak_lateral_ball_ankle_distance_px=round(peak_lateral_distance, 3),
            peak_release_velocity_px_s=round(peak_velocity, 3),
        )

    def _build_writer(self, capture: cv2.VideoCapture) -> cv2.VideoWriter:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        Path(self.annotate_output_path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.VideoWriter(str(self.annotate_output_path), fourcc, fps, (width, height))
