/// Platform-agnostic pin-deck math: motion-energy comparison and the
/// observation -> roll-sequence conversion, shared by the Flutter app.
///
/// No camera/image-plugin dependency here on purpose -- this package works
/// on plain byte buffers and integers, so it is unit-testable with the
/// plain Dart SDK. The Flutter app adapts `CameraImage` frames into the
/// inputs this package expects.
library pin_core;

export 'src/motion_energy.dart';
export 'src/roll_sequence.dart';
export 'src/throw_detector.dart';
