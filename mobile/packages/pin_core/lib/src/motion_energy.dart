/// Frame-differencing motion detection on a single-channel luma buffer.
/// Direct port of the Python prototype's `PinDeckAnalyzer._motion_energy`
/// (`core/pin_detector.py`): counts pixels whose brightness changed by more
/// than [diffThreshold] between two frames.
///
/// Takes plain byte buffers (not a camera frame type) so it is testable
/// with the Dart SDK alone; the app layer extracts the luma plane from a
/// `CameraImage` before calling this.
int motionEnergy(
  List<int> previousLuma,
  List<int> currentLuma, {
  int diffThreshold = 25,
}) {
  final length = previousLuma.length < currentLuma.length
      ? previousLuma.length
      : currentLuma.length;
  var changed = 0;
  for (var i = 0; i < length; i++) {
    final diff = (previousLuma[i] - currentLuma[i]).abs();
    if (diff > diffThreshold) changed++;
  }
  return changed;
}
