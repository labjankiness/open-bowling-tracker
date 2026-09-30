import 'package:biomechanics_core/biomechanics_core.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

/// Which leg/side the metrics should read from, mirroring the Python
/// prototype's `--view {back,side}` flag and the same rationale in
/// `core/tracker.py`: back-view tracks the sliding (front) leg's
/// knee/ankle; side-view is assumed to already be filmed from that side.
enum BowlerView { back, side }

/// Landmarks below this confidence are treated as missing.
/// Mirrors `config.LANDMARK_VISIBILITY_THRESHOLD` in the Python prototype.
const double landmarkVisibilityThreshold = 0.5;

/// Converts one ML Kit `Pose` detection into a `FrameMetrics`, given the
/// previous frame's ball position (for velocity) and elapsed time.
///
/// Returns null if any required landmark is missing or below the
/// visibility threshold -- mirrors `FrameLandmarks.all_visible(...)` in the
/// Python prototype's `pose_estimator.py`.
class PoseFrameMapper {
  final BowlerView view;

  PoseFrameMapper({required this.view});

  Point2D? _point(Pose pose, PoseLandmarkType type) {
    final lm = pose.landmarks[type];
    if (lm == null || lm.likelihood < landmarkVisibilityThreshold) return null;
    return Point2D(lm.x, lm.y);
  }

  ({FrameMetrics? metrics, Point2D? ballPosition}) map({
    required Pose pose,
    required int frameIndex,
    required double timestampS,
    required double dtSeconds,
    Point2D? previousBallPosition,
    double? pixelsPerMeter,
  }) {
    final leftShoulder = _point(pose, PoseLandmarkType.leftShoulder);
    final rightShoulder = _point(pose, PoseLandmarkType.rightShoulder);
    final leftHip = _point(pose, PoseLandmarkType.leftHip);
    final rightHip = _point(pose, PoseLandmarkType.rightHip);
    final leftKnee = _point(pose, PoseLandmarkType.leftKnee);
    final rightKnee = _point(pose, PoseLandmarkType.rightKnee);
    final leftAnkle = _point(pose, PoseLandmarkType.leftAnkle);
    final rightAnkle = _point(pose, PoseLandmarkType.rightAnkle);
    final leftWrist = _point(pose, PoseLandmarkType.leftWrist);
    final rightWrist = _point(pose, PoseLandmarkType.rightWrist);

    if ([
      leftShoulder, rightShoulder,
      leftHip, rightHip,
      leftKnee, rightKnee,
      leftAnkle, rightAnkle,
      leftWrist, rightWrist,
    ].contains(null)) {
      return (metrics: null, ballPosition: previousBallPosition);
    }

    final ballPosition = estimateBallPosition(leftWrist!, rightWrist!);

    final useLeft = view == BowlerView.back;
    final knee = useLeft ? leftKnee! : rightKnee!;
    final ankle = useLeft ? leftAnkle! : rightAnkle!;
    final hipForKnee = useLeft ? leftHip! : rightHip!;

    final spineTilt = calculateSpineTilt(leftShoulder!, rightShoulder!, leftHip!, rightHip!);
    final kneeFlexion = calculateKneeFlexion(hipForKnee, knee, ankle);
    final hipShoulderSeparation =
        calculateHipShoulderSeparation(leftShoulder, rightShoulder, leftHip, rightHip);
    final lateralBallAnkleDistance = calculateLateralBallAnkleDistance(
      ballPosition,
      ankle,
      pixelsPerMeter: pixelsPerMeter,
    );

    var velocity = 0.0;
    if (previousBallPosition != null) {
      velocity = calculateReleaseVelocity(
        previousBallPosition,
        ballPosition,
        dtSeconds,
        pixelsPerMeter: pixelsPerMeter,
      );
    }

    final metrics = FrameMetrics(
      frameIndex: frameIndex,
      timestampS: timestampS,
      spineTiltDeg: spineTilt,
      kneeFlexionDeg: kneeFlexion,
      hipShoulderSeparationDeg: hipShoulderSeparation,
      lateralBallAnkleDistance: lateralBallAnkleDistance,
      ballVelocity: velocity,
    );

    return (metrics: metrics, ballPosition: ballPosition);
  }
}
