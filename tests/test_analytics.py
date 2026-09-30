"""Unit tests for the pure-math analytics core (no video/MediaPipe needed)."""

import numpy as np

from core import analytics


def test_spine_tilt_upright_is_zero():
    left_shoulder = np.array([40.0, 0.0])
    right_shoulder = np.array([60.0, 0.0])
    left_hip = np.array([40.0, 100.0])
    right_hip = np.array([60.0, 100.0])
    tilt = analytics.calculate_spine_tilt(left_shoulder, right_shoulder, left_hip, right_hip)
    assert abs(tilt) < 1e-6


def test_knee_flexion_straight_leg_is_zero():
    hip = np.array([50.0, 0.0])
    knee = np.array([50.0, 50.0])
    ankle = np.array([50.0, 100.0])
    flexion = analytics.calculate_knee_flexion(hip, knee, ankle)
    assert abs(flexion) < 1e-6


def test_knee_flexion_right_angle_bend():
    hip = np.array([50.0, 0.0])
    knee = np.array([50.0, 50.0])
    ankle = np.array([100.0, 50.0])
    flexion = analytics.calculate_knee_flexion(hip, knee, ankle)
    assert abs(flexion - 90.0) < 1e-6


def test_hip_shoulder_separation_no_rotation_is_zero():
    left_shoulder = np.array([40.0, 0.0])
    right_shoulder = np.array([60.0, 0.0])
    left_hip = np.array([40.0, 100.0])
    right_hip = np.array([60.0, 100.0])
    separation = analytics.calculate_hip_shoulder_separation(
        left_shoulder, right_shoulder, left_hip, right_hip
    )
    assert abs(separation) < 1e-6


def test_lateral_ball_ankle_distance_is_horizontal_only():
    ball = np.array([120.0, 40.0])
    ankle = np.array([100.0, 400.0])
    distance = analytics.calculate_lateral_ball_ankle_distance(ball, ankle)
    assert abs(distance - 20.0) < 1e-6


def test_release_velocity_basic():
    prev_pos = np.array([0.0, 0.0])
    curr_pos = np.array([30.0, 40.0])  # 3-4-5 triangle -> distance 50
    velocity = analytics.calculate_release_velocity(prev_pos, curr_pos, dt_seconds=0.5)
    assert abs(velocity - 100.0) < 1e-6


def test_estimate_ball_position_is_wrist_midpoint():
    left_wrist = np.array([10.0, 10.0])
    right_wrist = np.array([30.0, 20.0])
    ball = analytics.estimate_ball_position(left_wrist, right_wrist)
    assert np.allclose(ball, np.array([20.0, 15.0]))
