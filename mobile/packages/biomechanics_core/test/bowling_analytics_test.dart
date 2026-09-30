// Direct port of tests/test_analytics.py -- keeps the Dart and Python
// biomechanics math verified against the same set of cases.
import 'package:biomechanics_core/biomechanics_core.dart';
import 'package:test/test.dart';

void main() {
  test('spine tilt upright is zero', () {
    const leftShoulder = Point2D(40.0, 0.0);
    const rightShoulder = Point2D(60.0, 0.0);
    const leftHip = Point2D(40.0, 100.0);
    const rightHip = Point2D(60.0, 100.0);
    final tilt = calculateSpineTilt(leftShoulder, rightShoulder, leftHip, rightHip);
    expect(tilt.abs(), lessThan(1e-6));
  });

  test('knee flexion straight leg is zero', () {
    const hip = Point2D(50.0, 0.0);
    const knee = Point2D(50.0, 50.0);
    const ankle = Point2D(50.0, 100.0);
    final flexion = calculateKneeFlexion(hip, knee, ankle);
    expect(flexion.abs(), lessThan(1e-6));
  });

  test('knee flexion right angle bend', () {
    const hip = Point2D(50.0, 0.0);
    const knee = Point2D(50.0, 50.0);
    const ankle = Point2D(100.0, 50.0);
    final flexion = calculateKneeFlexion(hip, knee, ankle);
    expect((flexion - 90.0).abs(), lessThan(1e-6));
  });

  test('hip shoulder separation no rotation is zero', () {
    const leftShoulder = Point2D(40.0, 0.0);
    const rightShoulder = Point2D(60.0, 0.0);
    const leftHip = Point2D(40.0, 100.0);
    const rightHip = Point2D(60.0, 100.0);
    final separation =
        calculateHipShoulderSeparation(leftShoulder, rightShoulder, leftHip, rightHip);
    expect(separation.abs(), lessThan(1e-6));
  });

  test('lateral ball ankle distance is horizontal only', () {
    const ball = Point2D(120.0, 40.0);
    const ankle = Point2D(100.0, 400.0);
    final distance = calculateLateralBallAnkleDistance(ball, ankle);
    expect((distance - 20.0).abs(), lessThan(1e-6));
  });

  test('release velocity basic', () {
    const prevPos = Point2D(0.0, 0.0);
    const currPos = Point2D(30.0, 40.0); // 3-4-5 triangle -> distance 50
    final velocity = calculateReleaseVelocity(prevPos, currPos, 0.5);
    expect((velocity - 100.0).abs(), lessThan(1e-6));
  });

  test('estimate ball position is wrist midpoint', () {
    const leftWrist = Point2D(10.0, 10.0);
    const rightWrist = Point2D(30.0, 20.0);
    final ball = estimateBallPosition(leftWrist, rightWrist);
    expect(ball.x, closeTo(20.0, 1e-9));
    expect(ball.y, closeTo(15.0, 1e-9));
  });

  test('peak metrics tracker keeps running maxima', () {
    final tracker = PeakMetricsTracker();
    tracker.update(const FrameMetrics(
      frameIndex: 0,
      timestampS: 0.0,
      spineTiltDeg: 10,
      kneeFlexionDeg: 20,
      hipShoulderSeparationDeg: -5,
      lateralBallAnkleDistance: 3,
      ballVelocity: 100,
    ));
    tracker.update(const FrameMetrics(
      frameIndex: 1,
      timestampS: 0.033,
      spineTiltDeg: 8,
      kneeFlexionDeg: 35,
      hipShoulderSeparationDeg: 12,
      lateralBallAnkleDistance: 1,
      ballVelocity: 250,
    ));
    expect(tracker.frameCount, 2);
    expect(tracker.peakSpineTiltDeg, 10);
    expect(tracker.peakKneeFlexionDeg, 35);
    expect(tracker.peakHipShoulderSeparationDeg, 12); // abs() of -5 vs 12
    expect(tracker.peakLateralBallAnkleDistance, 3);
    expect(tracker.peakReleaseVelocity, 250);
  });
}
