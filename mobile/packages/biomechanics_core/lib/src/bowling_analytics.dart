/// Geometric math core for two-handed bowling biomechanics.
///
/// Direct port of the Python prototype's `core/analytics.py`. Every
/// function is pure: it takes `Point2D`s (pixel-space x, y) and returns a
/// scalar metric. No pose-detector or camera dependency, so it is
/// unit-tested here with plain points, then reused by whatever Flutter
/// pose-detection plugin the app wires up.
///
/// Sign / units convention (matches the Python version exactly):
///   - Points are (x, y) pixel coordinates, origin top-left, y increasing
///     downward (camera/image convention).
///   - All angles are returned in degrees.
///   - Distances/velocities are in pixels / pixels-per-second unless a
///     `pixelsPerMeter` calibration factor is supplied, in which case
///     results are converted to metric units.
library;

import 'dart:math' as math;

import 'point2d.dart';

const Point2D verticalAxis = Point2D(0.0, -1.0); // "up" in image coordinates

double _angleBetween(Point2D v1, Point2D v2) {
  final normProduct = v1.length * v2.length;
  if (normProduct == 0.0) return 0.0;
  var cosTheta = v1.dot(v2) / normProduct;
  cosTheta = cosTheta.clamp(-1.0, 1.0);
  return _degrees(math.acos(cosTheta));
}

double _degrees(double radians) => radians * 180.0 / math.pi;

/// Angle ABC (in degrees) at vertex [b], formed by points a-b-c.
///
/// Used for joint angles such as the knee: a=hip, b=knee, c=ankle.
/// 180 degrees == fully extended/straight joint.
double calculateJointAngle(Point2D a, Point2D b, Point2D c) {
  final ba = a - b;
  final bc = c - b;
  return _angleBetween(ba, bc);
}

/// Forward/lateral spine tilt in degrees from vertical.
///
/// Defined as the angle between the shoulder-midpoint -> hip-midpoint
/// vector (the trunk line) and the vertical image axis. 0 degrees is a
/// perfectly upright trunk.
double calculateSpineTilt(
  Point2D leftShoulder,
  Point2D rightShoulder,
  Point2D leftHip,
  Point2D rightHip,
) {
  final shoulderMid = Point2D.midpoint(leftShoulder, rightShoulder);
  final hipMid = Point2D.midpoint(leftHip, rightHip);
  final trunkVector = shoulderMid - hipMid;
  return _angleBetween(trunkVector, verticalAxis);
}

/// Knee flexion angle in degrees.
///
/// Reported as (180 - jointAngle) so that 0 degrees means a straight leg
/// and larger values mean deeper bend, matching how flexion is described
/// clinically/athletically.
double calculateKneeFlexion(Point2D hip, Point2D knee, Point2D ankle) {
  final jointAngle = calculateJointAngle(hip, knee, ankle);
  return 180.0 - jointAngle;
}

/// Hip-to-shoulder rotational separation ("X-factor") in degrees.
///
/// Computed as the difference between the shoulder-line orientation and
/// the hip-line orientation (each measured with atan2 against the
/// horizontal axis), wrapped into [-90, 90] degrees. A larger absolute
/// value indicates more torso coil/counter-rotation between the hips and
/// shoulders, a key power metric in a two-handed delivery.
double calculateHipShoulderSeparation(
  Point2D leftShoulder,
  Point2D rightShoulder,
  Point2D leftHip,
  Point2D rightHip,
) {
  final shoulderVector = rightShoulder - leftShoulder;
  final hipVector = rightHip - leftHip;

  final shoulderAngle = _degrees(math.atan2(shoulderVector.y, shoulderVector.x));
  final hipAngle = _degrees(math.atan2(hipVector.y, hipVector.x));

  var separation = shoulderAngle - hipAngle;
  // Wrap to (-90, 90] since a line's orientation is only meaningful mod 180.
  separation = (separation + 90.0) % 180.0 - 90.0;
  return separation;
}

/// Lateral (horizontal-axis only) distance between the ball and the ankle.
///
/// Captures how far the ball drifts outside/inside the sliding foot at
/// release, a key line-repeatability metric for two-handed bowlers.
double calculateLateralBallAnkleDistance(
  Point2D ballPosition,
  Point2D ankle, {
  double? pixelsPerMeter,
}) {
  final distancePx = (ballPosition.x - ankle.x).abs();
  if (pixelsPerMeter != null && pixelsPerMeter != 0) {
    return distancePx / pixelsPerMeter;
  }
  return distancePx;
}

/// Straight-line distance between two points.
double calculateEuclideanDistance(
  Point2D pointA,
  Point2D pointB, {
  double? pixelsPerMeter,
}) {
  final distancePx = (pointA - pointB).length;
  if (pixelsPerMeter != null && pixelsPerMeter != 0) {
    return distancePx / pixelsPerMeter;
  }
  return distancePx;
}

/// Instantaneous velocity of the ball between two consecutive frames.
///
/// velocity = |currPosition - prevPosition| / dt
///
/// Returns pixels/second, or meters/second when [pixelsPerMeter] is
/// supplied as a calibration factor.
double calculateReleaseVelocity(
  Point2D prevPosition,
  Point2D currPosition,
  double dtSeconds, {
  double? pixelsPerMeter,
}) {
  if (dtSeconds <= 0.0) return 0.0;
  final displacement = calculateEuclideanDistance(
    prevPosition,
    currPosition,
    pixelsPerMeter: pixelsPerMeter,
  );
  return displacement / dtSeconds;
}

/// Proxy for the ball's position in a two-handed delivery.
///
/// Pose landmarks have no ball landmark, so the midpoint of both wrists is
/// used as a stand-in for the ball centroid while the bowler is in
/// possession (both hands cradling the ball is characteristic of the
/// two-handed style). Isolated in its own function so a dedicated
/// ball-detector can be swapped in later without touching anything
/// downstream.
Point2D estimateBallPosition(Point2D leftWrist, Point2D rightWrist) {
  return Point2D.midpoint(leftWrist, rightWrist);
}
