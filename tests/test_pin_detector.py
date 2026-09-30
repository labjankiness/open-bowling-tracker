"""Unit tests for the pure observation->roll conversion logic (no video/CV)."""

from core.pin_detector import observations_to_rolls


def test_simple_open_frame_sequence():
    # Frame 1: 10 -> 7 standing (3 knocked), then 7 -> 3 standing (4 knocked).
    observations = [7, 3]
    assert observations_to_rolls(observations) == [3, 4]


def test_strike_then_reset_then_open_frame():
    # Strike (10 -> 0), pinsetter resets to 10 (ignored), then open frame.
    observations = [0, 10, 6, 2]
    assert observations_to_rolls(observations) == [10, 4, 4]


def test_spare_then_reset():
    # 10 -> 4 (6 knocked), 4 -> 0 (spare, 4 knocked), reset to 10 (ignored).
    observations = [4, 0, 10]
    assert observations_to_rolls(observations) == [6, 4]


def test_empty_observations_yields_no_rolls():
    assert observations_to_rolls([]) == []
