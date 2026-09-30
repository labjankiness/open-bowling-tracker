/// Rejects single-frame landmark glitches in a stream of frame-to-frame ball
/// displacements. Direct port of the same logic in the Python prototype's
/// `core/tracker.py` (`_is_displacement_outlier`).
///
/// Calibration-free: judges each displacement against the median of
/// recently *accepted* displacements rather than an absolute threshold, so
/// it scales naturally with camera distance, resolution, and frame rate.
class DisplacementOutlierFilter {
  final double factor;
  final int minSamples;
  final int windowSize;

  final List<double> _recent = [];

  DisplacementOutlierFilter({
    this.factor = 6.0,
    this.minSamples = 5,
    this.windowSize = 15,
  });

  /// True if [displacement] is implausibly large next to recent frames.
  bool isOutlier(double displacement) {
    if (_recent.length < minSamples) return false;
    final baseline = _median(_recent);
    if (baseline <= 0) return false;
    return displacement > baseline * factor;
  }

  /// Record an accepted (non-outlier) displacement into the rolling window.
  void accept(double displacement) {
    _recent.add(displacement);
    if (_recent.length > windowSize) {
      _recent.removeAt(0);
    }
  }

  double _median(List<double> values) {
    final sorted = List<double>.from(values)..sort();
    final mid = sorted.length ~/ 2;
    if (sorted.length.isOdd) return sorted[mid];
    return (sorted[mid - 1] + sorted[mid]) / 2.0;
  }
}
