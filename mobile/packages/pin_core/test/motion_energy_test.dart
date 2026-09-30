import 'package:pin_core/pin_core.dart';
import 'package:test/test.dart';

void main() {
  test('identical frames have zero motion energy', () {
    final frame = List<int>.filled(100, 128);
    expect(motionEnergy(frame, frame), 0);
  });

  test('counts only pixels that changed more than the threshold', () {
    final prev = List<int>.filled(100, 100);
    final curr = List<int>.from(prev);
    curr[0] = 100 + 30; // above default threshold of 25
    curr[1] = 100 + 10; // below threshold, should not count
    expect(motionEnergy(prev, curr), 1);
  });

  test('custom threshold is respected', () {
    final prev = [0, 0, 0];
    final curr = [5, 15, 50];
    // diffs are 5, 15, 50 -- only 15 and 50 exceed a threshold of 10.
    expect(motionEnergy(prev, curr, diffThreshold: 10), 2);
  });
}
