/// All computed biomechanics metrics for a single video/camera frame.
/// Mirrors `core/analytics.py`'s `FrameMetrics` dataclass.
class FrameMetrics {
  final int frameIndex;
  final double timestampS;
  final double spineTiltDeg;
  final double kneeFlexionDeg;
  final double hipShoulderSeparationDeg;
  final double lateralBallAnkleDistance;
  final double ballVelocity;

  const FrameMetrics({
    required this.frameIndex,
    required this.timestampS,
    required this.spineTiltDeg,
    required this.kneeFlexionDeg,
    required this.hipShoulderSeparationDeg,
    required this.lateralBallAnkleDistance,
    required this.ballVelocity,
  });
}

/// Running peak values across a session, updated one frame at a time.
/// Mirrors the peak-tracking done in the Python `BowlingTracker._build_summary`.
class PeakMetricsTracker {
  double peakSpineTiltDeg = 0.0;
  double peakKneeFlexionDeg = 0.0;
  double peakHipShoulderSeparationDeg = 0.0;
  double peakLateralBallAnkleDistance = 0.0;
  double peakReleaseVelocity = 0.0;
  int frameCount = 0;

  void update(FrameMetrics metrics) {
    frameCount += 1;
    if (metrics.spineTiltDeg > peakSpineTiltDeg) {
      peakSpineTiltDeg = metrics.spineTiltDeg;
    }
    if (metrics.kneeFlexionDeg > peakKneeFlexionDeg) {
      peakKneeFlexionDeg = metrics.kneeFlexionDeg;
    }
    final absSeparation = metrics.hipShoulderSeparationDeg.abs();
    if (absSeparation > peakHipShoulderSeparationDeg) {
      peakHipShoulderSeparationDeg = absSeparation;
    }
    if (metrics.lateralBallAnkleDistance > peakLateralBallAnkleDistance) {
      peakLateralBallAnkleDistance = metrics.lateralBallAnkleDistance;
    }
    if (metrics.ballVelocity > peakReleaseVelocity) {
      peakReleaseVelocity = metrics.ballVelocity;
    }
  }
}
