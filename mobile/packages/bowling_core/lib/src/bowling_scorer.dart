/// Standard 10-pin bowling scoring engine.
///
/// Pure game logic: consumes a sequence of "pins knocked down per roll" and
/// produces the official frame-by-frame scorecard (strike/spare bonuses,
/// 10th-frame special case included). This is a direct port of
/// `core/scoring.py` from the Python prototype, kept algorithmically
/// identical so both are covered by parallel test suites.
library;

const int pinsPerRack = 10;
const int numFrames = 10;

/// One resolved frame on the scorecard.
class FrameResult {
  final int frameNumber;
  final List<int> rolls;
  final bool isStrike;
  final bool isSpare;
  final int frameScore;
  final int cumulativeScore;

  const FrameResult({
    required this.frameNumber,
    required this.rolls,
    required this.isStrike,
    required this.isSpare,
    required this.frameScore,
    required this.cumulativeScore,
  });
}

/// Stateful scorecard: call [addRoll] once per throw, in order.
class BowlingScorer {
  final List<int> rolls = [];

  void addRoll(int pins) {
    if (isComplete) {
      throw StateError('Cannot add a roll: the game is already complete');
    }
    if (pins < 0 || pins > pinsPerRack) {
      throw ArgumentError('pins must be between 0 and $pinsPerRack, got $pins');
    }
    rolls.add(pins);
  }

  bool get isComplete => _resolveFrames().length == numFrames;

  int get currentFrameNumber {
    final resolved = _resolveFrames();
    final next = resolved.length + 1;
    return next > numFrames ? numFrames : next;
  }

  int? get totalScore {
    final frames = _resolveFrames();
    if (frames.length != numFrames) return null;
    return frames.last.cumulativeScore;
  }

  /// All frames resolved so far (a frame only appears once its bonus rolls are known).
  List<FrameResult> frameResults() => _resolveFrames();

  List<FrameResult> _resolveFrames() {
    final frames = <FrameResult>[];
    var rollIndex = 0;
    var runningTotal = 0;

    for (var frameNumber = 1; frameNumber <= numFrames; frameNumber++) {
      List<int> frameRolls;
      int frameScore;
      bool isStrike;
      bool isSpare;

      if (frameNumber < numFrames) {
        if (rollIndex >= rolls.length) break;
        final first = rolls[rollIndex];

        if (first == pinsPerRack) {
          // strike
          if (rollIndex + 2 >= rolls.length) break;
          frameRolls = [first];
          frameScore = first + rolls[rollIndex + 1] + rolls[rollIndex + 2];
          rollIndex += 1;
          isStrike = true;
          isSpare = false;
        } else {
          if (rollIndex + 1 >= rolls.length) break;
          final second = rolls[rollIndex + 1];
          frameRolls = [first, second];
          if (first + second == pinsPerRack) {
            // spare
            if (rollIndex + 2 >= rolls.length) break;
            frameScore = pinsPerRack + rolls[rollIndex + 2];
            isStrike = false;
            isSpare = true;
          } else {
            frameScore = first + second;
            isStrike = false;
            isSpare = false;
          }
          rollIndex += 2;
        }
      } else {
        // 10th frame: up to 3 rolls, no further bonus lookahead needed.
        if (rollIndex + 1 >= rolls.length) break;
        final first = rolls[rollIndex];
        final second = rolls[rollIndex + 1];
        if (first == pinsPerRack || first + second == pinsPerRack) {
          if (rollIndex + 2 >= rolls.length) break;
          final third = rolls[rollIndex + 2];
          frameRolls = [first, second, third];
          frameScore = first + second + third;
          rollIndex += 3;
        } else {
          frameRolls = [first, second];
          frameScore = first + second;
          rollIndex += 2;
        }
        isStrike = first == pinsPerRack;
        isSpare = !isStrike && (first + second == pinsPerRack);
      }

      runningTotal += frameScore;
      frames.add(FrameResult(
        frameNumber: frameNumber,
        rolls: frameRolls,
        isStrike: isStrike,
        isSpare: isSpare,
        frameScore: frameScore,
        cumulativeScore: runningTotal,
      ));
    }

    return frames;
  }
}
