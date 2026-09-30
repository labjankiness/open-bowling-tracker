"""Unit tests for the pure bowling scoring engine (no video/CV involved)."""

from core.scoring import BowlingScorer


def _play(rolls):
    scorer = BowlingScorer()
    for pins in rolls:
        scorer.add_roll(pins)
    return scorer


def test_all_gutter_game_scores_zero():
    scorer = _play([0] * 20)
    assert scorer.is_complete
    assert scorer.total_score == 0


def test_perfect_game_scores_300():
    scorer = _play([10] * 12)
    assert scorer.is_complete
    assert scorer.total_score == 300


def test_all_spares_with_five_pin_bonus():
    # 10 spares of 5+5, plus one bonus roll of 5 in the 10th.
    scorer = _play([5, 5] * 10 + [5])
    assert scorer.is_complete
    assert scorer.total_score == 150


def test_simple_open_frames():
    # Frame 1: 3+4=7, Frame 2: 2+2=4, rest gutter.
    rolls = [3, 4, 2, 2] + [0] * 16
    scorer = _play(rolls)
    assert scorer.is_complete
    frames = scorer.frame_results()
    assert frames[0].frame_score == 7
    assert frames[0].cumulative_score == 7
    assert frames[1].frame_score == 4
    assert frames[1].cumulative_score == 11
    assert scorer.total_score == 11


def test_strike_bonus_uses_next_two_rolls():
    # Frame 1: strike. Frame 2: 3, 4 (open). Rest gutter.
    rolls = [10, 3, 4] + [0] * 16
    scorer = _play(rolls)
    frames = scorer.frame_results()
    assert frames[0].is_strike
    assert frames[0].frame_score == 10 + 3 + 4
    assert frames[1].frame_score == 7
    assert frames[0].cumulative_score == 17
    assert frames[1].cumulative_score == 24


def test_game_incomplete_until_bonus_rolls_are_known():
    scorer = BowlingScorer()
    scorer.add_roll(10)  # strike in frame 1, bonus unresolved
    assert scorer.frame_results() == []  # frame 1 not yet resolvable
    assert not scorer.is_complete
    assert scorer.total_score is None


def test_tenth_frame_strike_awards_two_extra_rolls():
    rolls = [0] * 18 + [10, 10, 10]
    scorer = _play(rolls)
    assert scorer.is_complete
    frames = scorer.frame_results()
    assert frames[-1].frame_score == 30
    assert scorer.total_score == 30


def test_rejects_out_of_range_pins():
    scorer = BowlingScorer()
    try:
        scorer.add_roll(11)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_rejects_rolls_after_completion():
    scorer = _play([10] * 12)
    try:
        scorer.add_roll(0)
        assert False, "expected ValueError"
    except ValueError:
        pass
