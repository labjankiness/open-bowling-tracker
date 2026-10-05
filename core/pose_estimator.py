"""MediaPipe Pose wrapper: turns a raw BGR frame into pixel-space landmarks.

Uses the MediaPipe Tasks API (`mp.tasks.vision.PoseLandmarker`), not the
older `mp.solutions.pose` API -- the legacy `solutions` module has been
removed from current MediaPipe releases. Requires a downloaded model
bundle; see `config.POSE_MODEL_PATH`.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import mediapipe as mp

import config


@dataclass
class Landmark:
    x: float
    y: float
    visibility: float

    @property
    def xy(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=np.float64)


class PoseEstimator:
    """Thin, stateful wrapper around `mediapipe.tasks.vision.PoseLandmarker`.

    Kept separate from the analytics math so the geometry core in
    `analytics.py` never has to know anything about MediaPipe itself.
    Runs in VIDEO mode (`detect_for_video`), which requires monotonically
    increasing per-frame timestamps -- tracked internally from the video's
    fps so callers just call `process(frame)` per decoded frame.
    """

    def __init__(
        self,
        model_path: str = config.POSE_MODEL_PATH,
        fps: float = 30.0,
        min_detection_confidence: float = config.MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = config.MIN_TRACKING_CONFIDENCE,
    ) -> None:
        base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
        vision = mp.tasks.vision
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._connections = vision.PoseLandmarksConnections.POSE_LANDMARKS
        self._drawing_utils = vision.drawing_utils
        self._ms_per_frame = 1000.0 / fps if fps > 0 else 1000.0 / 30.0
        self._next_timestamp_ms = 0
        self._prev_raw_landmarks = None

    def process(self, frame_bgr: np.ndarray) -> Optional["FrameLandmarks"]:
        """Run pose inference on one BGR frame with temporal smoothing.

        Returns None if no pose was detected in the frame.
        """
        rgb = frame_bgr[:, :, ::-1]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))

        timestamp_ms = self._next_timestamp_ms
        self._next_timestamp_ms += int(round(self._ms_per_frame))
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks:
            return None

        height, width = frame_bgr.shape[:2]
        raw_landmarks = result.pose_landmarks[0]

        # Temporal landmark smoothing (EMA filter) to remove jitter and glitches
        if self._prev_raw_landmarks is not None:
            for i, lm in enumerate(raw_landmarks):
                prev = self._prev_raw_landmarks[i]
                alpha = 0.70 if lm.visibility >= config.LANDMARK_VISIBILITY_THRESHOLD else 0.25
                lm.x = alpha * lm.x + (1.0 - alpha) * prev.x
                lm.y = alpha * lm.y + (1.0 - alpha) * prev.y
                lm.z = alpha * lm.z + (1.0 - alpha) * prev.z
        self._prev_raw_landmarks = raw_landmarks

        landmarks: Dict[int, Landmark] = {}
        for idx in config.REQUIRED_LANDMARKS:
            lm = raw_landmarks[idx]
            landmarks[idx] = Landmark(
                x=lm.x * width,
                y=lm.y * height,
                visibility=lm.visibility,
            )

        return FrameLandmarks(landmarks=landmarks, raw_landmarks=raw_landmarks)

    def draw(self, frame_bgr: np.ndarray, frame_landmarks: "FrameLandmarks") -> np.ndarray:
        """Draw the pose skeleton onto a copy of the frame for visualization/export."""
        annotated = frame_bgr.copy()
        self._drawing_utils.draw_landmarks(
            annotated,
            frame_landmarks.raw_landmarks,
            connections=self._connections,
        )
        return annotated

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


@dataclass
class FrameLandmarks:
    """Pixel-space landmarks for a single processed frame."""

    landmarks: Dict[int, Landmark]
    raw_landmarks: object

    def get(self, index: int) -> Optional[Landmark]:
        lm = self.landmarks.get(index)
        if lm is None or lm.visibility < config.LANDMARK_VISIBILITY_THRESHOLD:
            return None
        return lm

    def all_visible(self, *indices: int) -> bool:
        return all(self.get(i) is not None for i in indices)
