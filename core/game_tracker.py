"""Orchestrates a full recorded game: pin-deck video -> roll sequence -> scorecard."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.pin_detector import PinDeckAnalyzer
from core.scoring import BowlingScorer, FrameResult


@dataclass
class GameSummary:
    video_name: str
    rolls: List[int]
    frames: List[FrameResult]
    total_score: Optional[int]
    is_complete: bool


class GameTracker:
    """Runs `PinDeckAnalyzer` over a full-game video, then scores the result."""

    def __init__(self, pin_video_path: str, analyzer: Optional[PinDeckAnalyzer] = None) -> None:
        self.pin_video_path = Path(pin_video_path)
        if not self.pin_video_path.exists():
            raise FileNotFoundError(f"Pin-deck video not found: {self.pin_video_path}")
        self.analyzer = analyzer or PinDeckAnalyzer()

    def run(self) -> GameSummary:
        rolls = self.analyzer.extract_roll_sequence(str(self.pin_video_path))

        scorer = BowlingScorer()
        for pins in rolls:
            if scorer.is_complete:
                break
            scorer.add_roll(pins)

        return GameSummary(
            video_name=self.pin_video_path.name,
            rolls=rolls,
            frames=scorer.frame_results(),
            total_score=scorer.total_score,
            is_complete=scorer.is_complete,
        )
