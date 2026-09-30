"""Standard 10-pin bowling scoring engine.

Pure game logic: consumes a sequence of "pins knocked down per roll" and
produces the official frame-by-frame scorecard (strike/spare bonuses,
10th-frame special case included). Has no dependency on video, CV, or
how the roll counts were obtained — `PinDeckAnalyzer` produces the rolls,
this class turns them into a score.
"""

from dataclasses import dataclass
from typing import List, Optional

PINS_PER_RACK = 10
NUM_FRAMES = 10


@dataclass
class FrameResult:
    """One resolved frame on the scorecard."""

    frame_number: int
    rolls: List[int]
    is_strike: bool
    is_spare: bool
    frame_score: int
    cumulative_score: int


class BowlingScorer:
    """Stateful scorecard: call `add_roll(pins)` once per throw, in order."""

    def __init__(self) -> None:
        self.rolls: List[int] = []

    def add_roll(self, pins: int) -> None:
        if self.is_complete:
            raise ValueError("Cannot add a roll: the game is already complete")
        if not (0 <= pins <= PINS_PER_RACK):
            raise ValueError(f"pins must be between 0 and {PINS_PER_RACK}, got {pins}")
        self.rolls.append(pins)

    @property
    def is_complete(self) -> bool:
        return len(self._resolve_frames()) == NUM_FRAMES

    @property
    def current_frame_number(self) -> int:
        resolved = self._resolve_frames()
        return min(len(resolved) + 1, NUM_FRAMES)

    @property
    def total_score(self) -> Optional[int]:
        frames = self._resolve_frames()
        if len(frames) != NUM_FRAMES:
            return None
        return frames[-1].cumulative_score

    def frame_results(self) -> List[FrameResult]:
        """All frames resolved so far (a frame only appears once its bonus rolls are known)."""
        return self._resolve_frames()

    def _resolve_frames(self) -> List[FrameResult]:
        frames: List[FrameResult] = []
        roll_index = 0
        running_total = 0
        rolls = self.rolls

        for frame_number in range(1, NUM_FRAMES + 1):
            if frame_number < NUM_FRAMES:
                if roll_index >= len(rolls):
                    break
                first = rolls[roll_index]

                if first == PINS_PER_RACK:  # strike
                    if roll_index + 2 >= len(rolls):
                        break
                    frame_rolls = [first]
                    frame_score = first + rolls[roll_index + 1] + rolls[roll_index + 2]
                    roll_index += 1
                    is_strike, is_spare = True, False
                else:
                    if roll_index + 1 >= len(rolls):
                        break
                    second = rolls[roll_index + 1]
                    frame_rolls = [first, second]
                    if first + second == PINS_PER_RACK:  # spare
                        if roll_index + 2 >= len(rolls):
                            break
                        frame_score = PINS_PER_RACK + rolls[roll_index + 2]
                        is_strike, is_spare = False, True
                    else:
                        frame_score = first + second
                        is_strike, is_spare = False, False
                    roll_index += 2
            else:
                # 10th frame: up to 3 rolls, no further bonus lookahead needed.
                if roll_index + 1 >= len(rolls):
                    break
                first, second = rolls[roll_index], rolls[roll_index + 1]
                if first == PINS_PER_RACK or first + second == PINS_PER_RACK:
                    if roll_index + 2 >= len(rolls):
                        break
                    third = rolls[roll_index + 2]
                    frame_rolls = [first, second, third]
                    frame_score = first + second + third
                    roll_index += 3
                else:
                    frame_rolls = [first, second]
                    frame_score = first + second
                    roll_index += 2
                is_strike = first == PINS_PER_RACK
                is_spare = (not is_strike) and (first + second == PINS_PER_RACK)

            running_total += frame_score
            frames.append(
                FrameResult(
                    frame_number=frame_number,
                    rolls=frame_rolls,
                    is_strike=is_strike,
                    is_spare=is_spare,
                    frame_score=frame_score,
                    cumulative_score=running_total,
                )
            )

        return frames
