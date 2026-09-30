/// Streaming motion-then-rest state machine: feed it one motion-energy
/// reading per camera frame, and it reports the moment a throw has just
/// settled -- the point to prompt for a pin count.
///
/// Same state machine as the Python prototype's
/// `PinDeckAnalyzer.extract_rest_observations` (`core/pin_detector.py`),
/// adapted from a batch video-file loop to an incremental per-frame API
/// suited to a live camera stream.
class ThrowDetector {
  final int motionThreshold;
  final int restFramesRequired;

  bool _inMotion = false;
  int _restStreak = 0;

  ThrowDetector({
    this.motionThreshold = 20000,
    this.restFramesRequired = 8,
  });

  /// Feed one frame's motion-energy reading (see `motionEnergy`).
  /// Returns true exactly on the frame where a throw has just settled.
  bool onFrame(int energy) {
    final moving = energy > motionThreshold;

    if (moving) {
      _inMotion = true;
      _restStreak = 0;
      return false;
    }

    if (_inMotion) {
      _restStreak++;
      if (_restStreak >= restFramesRequired) {
        _inMotion = false;
        _restStreak = 0;
        return true;
      }
    }
    return false;
  }
}
