"""Classical-CV pin-deck analysis: turns a full-game pin-deck video into a
roll-by-roll "pins knocked down" sequence for `BowlingScorer`.

This is a heuristic, non-ML pipeline (thresholding + contour counting +
frame-differencing motion detection). It is intentionally isolated behind
`PinDeckAnalyzer.extract_roll_sequence`, so a trained pin-detection model
can be swapped in later without touching `scoring.py` or `game_tracker.py`.

Camera assumption: a fixed, overhead-ish or head-on view of the pin deck,
pins visibly lighter than the lane background, with the deck fully framed
(use `roi` to crop out the approach/gutters if they cause false positives).

Tuning: `min_pin_area`/`max_pin_area` depend on resolution and camera
distance; `motion_threshold` and `rest_frames_required` depend on frame
rate and lighting. Defaults are reasonable starting points, not guarantees.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

import config

PINS_PER_RACK = 10

ROI = Tuple[int, int, int, int]  # (x, y, width, height)


class PinDeckAnalyzer:
    def __init__(
        self,
        roi: Optional[ROI] = config.PIN_DECK_ROI,
        min_pin_area: float = config.PIN_MIN_AREA,
        max_pin_area: float = config.PIN_MAX_AREA,
        motion_threshold: float = config.PIN_MOTION_THRESHOLD,
        rest_frames_required: int = config.PIN_REST_FRAMES_REQUIRED,
        full_rack: int = PINS_PER_RACK,
    ) -> None:
        self.roi = roi
        self.min_pin_area = min_pin_area
        self.max_pin_area = max_pin_area
        self.motion_threshold = motion_threshold
        self.rest_frames_required = rest_frames_required
        self.full_rack = full_rack

    def _crop(self, frame: np.ndarray) -> np.ndarray:
        if self.roi is None:
            return frame
        x, y, w, h = self.roi
        return frame[y : y + h, x : x + w]

    def _to_gray(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(self._crop(frame), cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def count_standing_pins(self, frame: np.ndarray) -> int:
        """Count pin-sized bright contours in one frame of the pin deck."""
        gray = self._to_gray(frame)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pin_count = sum(
            1 for c in contours if self.min_pin_area <= cv2.contourArea(c) <= self.max_pin_area
        )
        return min(pin_count, self.full_rack)

    def _motion_energy(self, prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
        diff = cv2.absdiff(prev_gray, curr_gray)
        _, moving_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        return float(np.count_nonzero(moving_mask))

    def extract_rest_observations(self, video_path: str) -> List[int]:
        """Walk the full video and return the standing-pin count at every
        point the deck goes still after a burst of motion (i.e. right after
        a ball has passed through and/or knocked-down pins have settled).
        """
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise IOError(f"Could not open pin-deck video: {video_path}")

        observations: List[int] = []
        prev_gray: Optional[np.ndarray] = None
        in_motion = False
        rest_streak = 0

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                gray = self._to_gray(frame)
                if prev_gray is not None:
                    moving = self._motion_energy(prev_gray, gray) > self.motion_threshold

                    if moving:
                        in_motion = True
                        rest_streak = 0
                    elif in_motion:
                        rest_streak += 1
                        if rest_streak >= self.rest_frames_required:
                            observations.append(self.count_standing_pins(frame))
                            in_motion = False
                            rest_streak = 0

                prev_gray = gray
        finally:
            capture.release()

        return observations

    def extract_roll_sequence(self, video_path: str, fallback_mode: bool = True) -> List[int]:
        """Full pipeline: video -> rest observations -> per-roll pin counts."""
        observations = self.extract_rest_observations(video_path)
        rolls = observations_to_rolls(observations, full_rack=self.full_rack)

        # If video had motion but pin contrast was too dim to resolve full sequence,
        # produce an estimated roll sequence based on motion events rather than returning empty.
        if not rolls and fallback_mode and observations:
            # Filter out non-zero deductions
            rolls = [min(10, max(0, self.full_rack - obs)) for obs in observations if obs < self.full_rack]

        return rolls


def identify_pin_leaves(standing_pins_count: int) -> List[str]:
    """Map common pin count leaves to tactical spare conversion advice."""
    if standing_pins_count == 0:
        return ["Strike! Perfect pocket hit."]
    elif standing_pins_count == 1:
        return ["Single Pin Spare (Target 10-pin or 7-pin corner roll)"]
    elif standing_pins_count == 2:
        return ["Baby Split / 2-Pin Cluster (e.g., 2-8 or 3-9 sleeper)"]
    elif standing_pins_count == 3:
        return ["3-Pin Triangle / Washout (e.g., 1-2-4 or 1-2-8)"]
    elif standing_pins_count >= 4:
        return ["Split / Multi-Pin Leave (Aim between key pins or convert count)"]
    return ["Standard Spare Leave"]


def observations_to_rolls(observations: List[int], full_rack: int = PINS_PER_RACK) -> List[int]:
    """Convert a sequence of standing-pin counts into per-roll pins-knocked-down.

    Standing-pin count can only decrease across consecutive throws within a
    frame. Any observation that is *higher* than the current reference count
    means the pinsetter has cleared and re-racked the deck (which happens
    automatically after a strike or a completed frame) rather than a real
    throw, so it is treated as a silent reset instead of a roll.
    """
    rolls: List[int] = []
    reference = full_rack
    for standing in observations:
        if standing > reference:
            reference = standing  # pinsetter reset; not a roll
            continue
        knocked = reference - standing
        rolls.append(knocked)
        reference = standing
    return rolls
