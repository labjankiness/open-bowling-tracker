import 'package:pin_core/pin_core.dart';
import 'package:test/test.dart';

void main() {
  test('stays quiet with no motion at all', () {
    final detector = ThrowDetector(motionThreshold: 100, restFramesRequired: 3);
    for (var i = 0; i < 10; i++) {
      expect(detector.onFrame(0), isFalse);
    }
  });

  test('fires once after motion settles for restFramesRequired frames', () {
    final detector = ThrowDetector(motionThreshold: 100, restFramesRequired: 3);
    expect(detector.onFrame(500), isFalse); // motion starts
    expect(detector.onFrame(500), isFalse); // still moving
    expect(detector.onFrame(10), isFalse); // rest 1
    expect(detector.onFrame(10), isFalse); // rest 2
    expect(detector.onFrame(10), isTrue); // rest 3 -> settled, fires
    expect(detector.onFrame(10), isFalse); // stays quiet after firing
  });

  test('resets the rest streak if motion resumes before settling', () {
    final detector = ThrowDetector(motionThreshold: 100, restFramesRequired: 3);
    detector.onFrame(500); // motion
    detector.onFrame(10); // rest 1
    detector.onFrame(10); // rest 2
    detector.onFrame(500); // motion again -- resets rest streak
    expect(detector.onFrame(10), isFalse); // rest 1 again, not yet settled
    expect(detector.onFrame(10), isFalse); // rest 2
    expect(detector.onFrame(10), isTrue); // rest 3 -> settled
  });

  test('detects a second throw after the first settles', () {
    final detector = ThrowDetector(motionThreshold: 100, restFramesRequired: 2);
    detector.onFrame(500);
    detector.onFrame(10);
    expect(detector.onFrame(10), isTrue); // first throw settles

    detector.onFrame(500);
    detector.onFrame(10);
    expect(detector.onFrame(10), isTrue); // second throw settles
  });
}
