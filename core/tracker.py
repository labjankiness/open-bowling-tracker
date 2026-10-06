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
        handedness: str = config.HANDEDNESS_LEFT,
        style: str = config.STYLE_TWO_HANDED,
        pixels_per_meter: Optional[float] = None,
        annotate_output_path: Optional[str] = None,
    ) -> None:
        if view not in config.SUPPORTED_VIEWS:
            raise ValueError(f"view must be one of {config.SUPPORTED_VIEWS}, got {view!r}")

        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {self.video_path}")

        self.view = view
        self.handedness = handedness
        self.style = style
        self.pixels_per_meter = pixels_per_meter
        self.annotate_output_path = annotate_output_path

        # Resolved attributes (defaults to specified handedness/style or auto-detected)
        self.resolved_handedness = handedness if handedness != config.HANDEDNESS_AUTO else config.HANDEDNESS_LEFT
        self.resolved_style = style if style != config.STYLE_AUTO else config.STYLE_TWO_HANDED

        self.history: List[analytics.FrameMetrics] = []
        self.fps: float = 0.0
        self.frame_count: int = 0

        # Rolling window of accepted frame-to-frame ball displacements, used
        # to reject single-frame landmark glitches (see _is_displacement_outlier).
        self._recent_displacements: deque = deque(maxlen=config.VELOCITY_OUTLIER_WINDOW)
        self._wrist_gap_ratios: List[float] = []
        self._ball_crops: List[np.ndarray] = []
        self.detected_ball_info: Optional[dict] = None

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

                            # Sample crop around ball position for automatic ball model detection
                            if prev_ball_position is not None and len(self._ball_crops) < 15 and frame_index % 3 == 0:
                                bx, by = int(prev_ball_position[0]), int(prev_ball_position[1])
                                h, w = frame.shape[:2]
                                pad = int(max(20, min(w, h) * 0.06))
                                y1, y2 = max(0, by - pad), min(h, by + pad)
                                x1, x2 = max(0, bx - pad), min(w, bx + pad)
                                if (y2 - y1) > 15 and (x2 - x1) > 15:
                                    self._ball_crops.append(frame[y1:y2, x1:x2].copy())

                        if writer is not None:
                            writer.write(estimator.draw(frame, frame_landmarks))
                    elif writer is not None:
                        writer.write(frame)

                    frame_index += 1

                self.frame_count = frame_index
                
                # Auto-resolve style if set to auto based on inter-wrist gap ratio
                if self.style == config.STYLE_AUTO and self._wrist_gap_ratios:
                    avg_gap = sum(self._wrist_gap_ratios) / len(self._wrist_gap_ratios)
                    self.resolved_style = config.STYLE_TWO_HANDED if avg_gap < 0.45 else config.STYLE_ONE_HANDED

                # Run automatic bowling ball detection across sampled ball crops
                if self._ball_crops:
                    from core.ball_detector import detect_ball_from_image_crop
                    best_det = None
                    highest_conf = -1.0
                    for crop in self._ball_crops:
                        det = detect_ball_from_image_crop(crop)
                        if det["confidence"] > highest_conf:
                            highest_conf = det["confidence"]
                            best_det = det
                    self.detected_ball_info = best_det
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

        # Record inter-wrist ratio for style detection
        shoulder_width = max(1.0, float(np.linalg.norm(left_shoulder - right_shoulder)))
        wrist_dist = float(np.linalg.norm(left_wrist - right_wrist))
        self._wrist_gap_ratios.append(wrist_dist / shoulder_width)

        # Ball position proxy based on handedness & delivery style
        is_lefty = (self.resolved_handedness == config.HANDEDNESS_LEFT)
        dom_wrist = left_wrist if is_lefty else right_wrist
        sup_wrist = right_wrist if is_lefty else left_wrist

        if self.resolved_style == config.STYLE_ONE_HANDED:
            ball_position = dom_wrist.copy()
        else:
            # Two-handed: dominant hand cradles/rolls from underneath, support hand guides
            ball_position = 0.75 * dom_wrist + 0.25 * sup_wrist

        displacement = None
        if prev_ball_position is not None:
            displacement = analytics.calculate_euclidean_distance(prev_ball_position, ball_position)
            if self._is_displacement_outlier(displacement):
                return None, prev_ball_position

        # Lead slide leg selection respecting handedness:
        # Lefty from back view: Right leg is the sliding (front) leg.
        # Righty from back view: Left leg is the sliding (front) leg.
        if self.view == config.VIEW_BACK:
            knee, ankle = (right_knee, right_ankle) if is_lefty else (left_knee, left_ankle)
            hip_for_knee = right_hip if is_lefty else left_hip
        else:
            knee, ankle = (left_knee, left_ankle) if is_lefty else (right_knee, right_ankle)
            hip_for_knee = left_hip if is_lefty else right_hip

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

        # Estimate slide board from ankle position relative to frame center (assuming center dot = board 20)
        # 39 boards total across lane
        slide_board = None
        drift_boards = None
        if ankle is not None:
            # Map ankle X coordinate to lane boards (1 to 39)
            # Default reference: 20 is center of lane
            shoulder_span = max(1.0, float(np.linalg.norm(left_shoulder - right_shoulder)))
            lane_center_x = (left_hip[0] + right_hip[0]) / 2.0 if not is_lefty else (right_hip[0] + left_hip[0]) / 2.0
            board_offset = (ankle[0] - lane_center_x) / max(1.0, (shoulder_span * 0.12))
            base_board = 20.0 if not is_lefty else 18.0
            slide_board = float(np.clip(base_board + board_offset, 1.0, 39.0))

            if self.history and self.history[0].slide_foot_board is not None:
                drift_boards = round(slide_board - self.history[0].slide_foot_board, 1)

        metrics = analytics.FrameMetrics(
            frame_index=frame_index,
            timestamp_s=frame_index * dt_seconds,
            spine_tilt_deg=spine_tilt,
            knee_flexion_deg=knee_flexion,
            hip_shoulder_separation_deg=hip_shoulder_separation,
            lateral_ball_ankle_distance=lateral_ball_ankle_distance,
            ball_velocity=velocity,
            slide_foot_board=round(slide_board, 1) if slide_board is not None else None,
            lateral_drift_boards=drift_boards,
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
            drift_values = [abs(m.lateral_drift_boards) for m in self.history if m.lateral_drift_boards is not None]
            peak_drift = max(drift_values) if drift_values else 0.0

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
            handedness=self.resolved_handedness,
            delivery_style=self.resolved_style,
            bowling_ball=(self.detected_ball_info["name"] if self.detected_ball_info else "Standard Reactive Resin Ball"),
            peak_lateral_drift_boards=round(peak_drift, 1),
        )

    def _build_writer(self, capture: cv2.VideoCapture) -> cv2.VideoWriter:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        Path(self.annotate_output_path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.VideoWriter(str(self.annotate_output_path), fourcc, fps, (width, height))
