"""Geometric math core for two-handed bowling biomechanics.

Every function here is pure: it takes NumPy point arrays (pixel-space
x, y coordinates) and returns a scalar metric. Nothing in this module
imports MediaPipe or OpenCV, so it can be unit-tested with plain arrays
and re-used against any upstream landmark source.

Sign / units convention:
    - Points are (x, y) pixel coordinates, origin top-left, y increasing
      downward (OpenCV/image convention).
    - All angles are returned in degrees.
    - Distances/velocities are in pixels / pixels-per-second unless a
      `pixels_per_meter` calibration factor is supplied, in which case
      results are converted to metric units.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

VERTICAL_AXIS = np.array([0.0, -1.0])  # "up" in image coordinates


def _angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    """Unsigned angle in degrees between two 2D vectors."""
    norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
    if norm_product == 0.0:
        return 0.0
    cos_theta = np.dot(v1, v2) / norm_product
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def calculate_joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC (in degrees) at vertex `b`, formed by points a-b-c.

    Used for joint angles such as the knee: a=hip, b=knee, c=ankle.
    180 degrees == fully extended/straight joint.
    """
    ba = a - b
    bc = c - b
    return _angle_between(ba, bc)


def calculate_spine_tilt(
    left_shoulder: np.ndarray,
    right_shoulder: np.ndarray,
    left_hip: np.ndarray,
    right_hip: np.ndarray,
) -> float:
    """Forward/lateral spine tilt in degrees from vertical.

    Defined as the angle between the shoulder-midpoint -> hip-midpoint
    vector (the trunk line) and the vertical image axis. 0 degrees is
    a perfectly upright trunk.
    """
    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    trunk_vector = shoulder_mid - hip_mid
    return _angle_between(trunk_vector, VERTICAL_AXIS)


def calculate_knee_flexion(
    hip: np.ndarray,
    knee: np.ndarray,
    ankle: np.ndarray,
) -> float:
    """Knee flexion angle in degrees.

    Reported as (180 - joint_angle) so that 0 degrees means a straight
    leg and larger values mean deeper bend, matching how flexion is
    described clinically/athletically.
    """
    joint_angle = calculate_joint_angle(hip, knee, ankle)
    return float(180.0 - joint_angle)


def calculate_hip_shoulder_separation(
    left_shoulder: np.ndarray,
    right_shoulder: np.ndarray,
    left_hip: np.ndarray,
    right_hip: np.ndarray,
) -> float:
    """Hip-to-shoulder rotational separation ("X-factor") in degrees.

    Computed as the difference between the shoulder-line orientation
    and the hip-line orientation (each measured with atan2 against the
    horizontal axis), wrapped into [-90, 90] degrees. A larger absolute
    value indicates more torso coil/counter-rotation between the hips
    and shoulders, a key power metric in a two-handed delivery.
    """
    shoulder_vector = right_shoulder - left_shoulder
    hip_vector = right_hip - left_hip

    shoulder_angle = np.degrees(np.arctan2(shoulder_vector[1], shoulder_vector[0]))
    hip_angle = np.degrees(np.arctan2(hip_vector[1], hip_vector[0]))

    separation = shoulder_angle - hip_angle
    # Wrap to (-90, 90] since a line's orientation is only meaningful mod 180.
    separation = (separation + 90.0) % 180.0 - 90.0
    return float(separation)


def calculate_lateral_ball_ankle_distance(
    ball_position: np.ndarray,
    ankle: np.ndarray,
    pixels_per_meter: Optional[float] = None,
) -> float:
    """Lateral (horizontal-axis only) distance between the ball and the ankle.

    Captures how far the ball drifts outside/inside the sliding foot at
    release, a key line-repeatability metric for two-handed bowlers.
    """
    distance_px = abs(float(ball_position[0]) - float(ankle[0]))
    if pixels_per_meter:
        return distance_px / pixels_per_meter
    return distance_px


def calculate_euclidean_distance(
    point_a: np.ndarray,
    point_b: np.ndarray,
    pixels_per_meter: Optional[float] = None,
) -> float:
    """Straight-line distance between two points."""
    distance_px = float(np.linalg.norm(point_a - point_b))
    if pixels_per_meter:
        return distance_px / pixels_per_meter
    return distance_px


def calculate_release_velocity(
    prev_position: np.ndarray,
    curr_position: np.ndarray,
    dt_seconds: float,
    pixels_per_meter: Optional[float] = None,
) -> float:
    """Instantaneous velocity of the ball between two consecutive frames.

    velocity = |curr_position - prev_position| / dt

    Returns pixels/second, or meters/second when `pixels_per_meter` is
    supplied as a calibration factor.
    """
    if dt_seconds <= 0.0:
        return 0.0
    displacement = calculate_euclidean_distance(prev_position, curr_position, pixels_per_meter)
    return displacement / dt_seconds


def estimate_ball_position(left_wrist: np.ndarray, right_wrist: np.ndarray) -> np.ndarray:
    """Proxy for the ball's position in a two-handed delivery.

    MediaPipe Pose has no ball landmark, so the midpoint of both wrists
    is used as a stand-in for the ball centroid while the bowler is in
    possession (both hands cradling the ball is characteristic of the
    two-handed style). This is intentionally isolated in its own
    function so a dedicated ball-detector (e.g. Hough circle transform
    or a small object-detection model) can be swapped in later without
    touching the rest of the analytics core.
    """
    return (left_wrist + right_wrist) / 2.0


@dataclass
class FrameMetrics:
    """All computed metrics for a single video frame."""

    frame_index: int
    timestamp_s: float
    spine_tilt_deg: float
    knee_flexion_deg: float
    hip_shoulder_separation_deg: float
    lateral_ball_ankle_distance: float
    ball_velocity: float
