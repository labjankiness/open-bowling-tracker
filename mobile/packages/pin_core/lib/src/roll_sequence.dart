/// Converts a sequence of standing-pin counts into per-roll pins-knocked-down.
/// Direct port of `observations_to_rolls` in the Python prototype's
/// `core/pin_detector.py`.
library;

const int pinsPerRack = 10;

/// Standing-pin count can only decrease across consecutive throws within a
/// frame. Any observation that is *higher* than the current reference count
/// means the pinsetter has cleared and re-racked the deck (which happens
/// automatically after a strike or a completed frame) rather than a real
/// throw, so it is treated as a silent reset instead of a roll.
List<int> observationsToRolls(List<int> observations, {int fullRack = pinsPerRack}) {
  final rolls = <int>[];
  var reference = fullRack;
  for (final standing in observations) {
    if (standing > reference) {
      reference = standing; // pinsetter reset; not a roll
      continue;
    }
    final knocked = reference - standing;
    rolls.add(knocked);
    reference = standing;
  }
  return rolls;
}
