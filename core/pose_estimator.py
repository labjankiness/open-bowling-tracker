"""MediaPipe Pose wrapper: turns a raw BGR frame into pixel-space landmarks."""

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
    """Thin, stateful wrapper around `mediapipe.solutions.pose.Pose`.

    Kept separate from the analytics math so the geometry core in
    `analytics.py` never has to know anything about MediaPipe itself.
    """

    def __init__(
        self,
        min_detection_confidence: float = config.MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = config.MIN_TRACKING_CONFIDENCE,
        model_complexity: int = config.MODEL_COMPLEXITY,
    ) -> None:
        self._mp_pose = mp.solutions.pose
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.drawing_utils = mp.solutions.drawing_utils
        self.drawing_styles = mp.solutions.drawing_styles
        self.pose_connections = self._mp_pose.POSE_CONNECTIONS

    def process(self, frame_bgr: np.ndarray) -> Optional["FrameLandmarks"]:
        """Run pose inference on one BGR frame.

        Returns None if no pose was detected in the frame.
        """
        frame_rgb = frame_bgr[:, :, ::-1]
        frame_rgb.flags.writeable = False
        results = self._pose.process(frame_rgb)
        frame_rgb.flags.writeable = True

        if not results.pose_landmarks:
            return None

        height, width = frame_bgr.shape[:2]
        landmarks: Dict[int, Landmark] = {}
        for idx in config.REQUIRED_LANDMARKS:
            lm = results.pose_landmarks.landmark[idx]
            landmarks[idx] = Landmark(
                x=lm.x * width,
                y=lm.y * height,
                visibility=lm.visibility,
            )

        return FrameLandmarks(landmarks=landmarks, raw_result=results)

    def draw(self, frame_bgr: np.ndarray, frame_landmarks: "FrameLandmarks") -> np.ndarray:
        """Draw the pose skeleton onto a copy of the frame for visualization/export."""
        annotated = frame_bgr.copy()
        self.drawing_utils.draw_landmarks(
            annotated,
            frame_landmarks.raw_result.pose_landmarks,
            self.pose_connections,
            landmark_drawing_spec=self.drawing_styles.get_default_pose_landmarks_style(),
        )
        return annotated

    def close(self) -> None:
        self._pose.close()

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


@dataclass
class FrameLandmarks:
    """Pixel-space landmarks for a single processed frame."""

    landmarks: Dict[int, Landmark]
    raw_result: object

    def get(self, index: int) -> Optional[Landmark]:
        lm = self.landmarks.get(index)
        if lm is None or lm.visibility < config.LANDMARK_VISIBILITY_THRESHOLD:
            return None
        return lm

    def all_visible(self, *indices: int) -> bool:
        return all(self.get(i) is not None for i in indices)
