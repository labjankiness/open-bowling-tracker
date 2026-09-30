/// Platform-agnostic bowling biomechanics geometry math.
///
/// No Flutter/camera/pose-detector dependency here on purpose: this package
/// takes plain 2D points and returns scalar metrics, so it is unit-testable
/// with the plain Dart SDK. The Flutter app adapts whatever pose-detection
/// plugin it uses into `Point2D`s and calls into this package.
library biomechanics_core;

export 'src/point2d.dart';
export 'src/bowling_analytics.dart';
export 'src/frame_metrics.dart';
export 'src/displacement_outlier_filter.dart';
