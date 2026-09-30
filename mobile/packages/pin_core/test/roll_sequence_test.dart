// Direct port of tests/test_pin_detector.py's observations_to_rolls cases.
import 'package:pin_core/pin_core.dart';
import 'package:test/test.dart';

void main() {
  test('simple open frame sequence', () {
    final observations = [7, 3];
    expect(observationsToRolls(observations), [3, 4]);
  });

  test('strike then reset then open frame', () {
    final observations = [0, 10, 6, 2];
    expect(observationsToRolls(observations), [10, 4, 4]);
  });

  test('spare then reset', () {
    final observations = [4, 0, 10];
    expect(observationsToRolls(observations), [6, 4]);
  });

  test('empty observations yields no rolls', () {
    expect(observationsToRolls([]), <int>[]);
  });
}
