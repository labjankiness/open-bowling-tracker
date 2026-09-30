import 'package:biomechanics_core/biomechanics_core.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

import '../pose/camera_image_converter.dart';
import '../pose/pose_landmark_mapper.dart';

/// Live bowler-camera view: camera preview + on-device pose detection,
/// computing the same five biomechanics metrics as the Python prototype's
/// `main.py track` command, updated frame by frame instead of after the
/// fact. Session peaks are tracked the same way `BowlingTracker._build_summary`
/// does on the Python side.
class BiomechanicsScreen extends StatefulWidget {
  const BiomechanicsScreen({super.key});

  @override
  State<BiomechanicsScreen> createState() => _BiomechanicsScreenState();
}

class _BiomechanicsScreenState extends State<BiomechanicsScreen> {
  CameraController? _controller;
  PoseDetector? _poseDetector;
  BowlerView _view = BowlerView.back;

  final PeakMetricsTracker _peaks = PeakMetricsTracker();
  FrameMetrics? _latestMetrics;
  Point2D? _lastBallPosition;
  DateTime? _lastFrameTime;
  int _frameIndex = 0;

  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _poseDetector = PoseDetector(
      options: PoseDetectorOptions(mode: PoseDetectionMode.stream),
    );
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _error = 'No camera available on this device.');
        return;
      }
      final camera = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      final controller = CameraController(
        camera,
        ResolutionPreset.medium,
        enableAudio: false,
      );
      await controller.initialize();
      await controller.startImageStream((image) => _onCameraImage(image, camera));

      if (!mounted) return;
      setState(() => _controller = controller);
    } catch (e) {
      setState(() => _error = 'Camera init failed: $e');
    }
  }

  void _onCameraImage(CameraImage image, CameraDescription camera) {
    if (_busy || _poseDetector == null) return;
    _busy = true;
    _processImage(image, camera).whenComplete(() => _busy = false);
  }

  Future<void> _processImage(CameraImage image, CameraDescription camera) async {
    final inputImage = convertCameraImage(
      image: image,
      camera: camera,
      sensorOrientationDegrees: camera.sensorOrientation,
    );
    if (inputImage == null) return;

    final poses = await _poseDetector!.processImage(inputImage);
    if (poses.isEmpty) return;

    final now = DateTime.now();
    final dtSeconds = _lastFrameTime == null
        ? 0.0
        : now.difference(_lastFrameTime!).inMicroseconds / 1e6;
    _lastFrameTime = now;

    final mapper = PoseFrameMapper(view: _view);
    final result = mapper.map(
      pose: poses.first,
      frameIndex: _frameIndex++,
      timestampS: now.millisecondsSinceEpoch / 1000.0,
      dtSeconds: dtSeconds,
      previousBallPosition: _lastBallPosition,
    );

    _lastBallPosition = result.ballPosition;
    if (result.metrics == null) return;

    _peaks.update(result.metrics!);
    if (mounted) {
      setState(() => _latestMetrics = result.metrics);
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    _poseDetector?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bowler Camera'),
        actions: [
          PopupMenuButton<BowlerView>(
            initialValue: _view,
            onSelected: (v) => setState(() => _view = v),
            itemBuilder: (_) => const [
              PopupMenuItem(value: BowlerView.back, child: Text('Back view')),
              PopupMenuItem(value: BowlerView.side, child: Text('Side view')),
            ],
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_error!)));
    }
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return const Center(child: CircularProgressIndicator());
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        CameraPreview(controller),
        _MetricsOverlay(latest: _latestMetrics, peaks: _peaks, view: _view),
      ],
    );
  }
}

class _MetricsOverlay extends StatelessWidget {
  final FrameMetrics? latest;
  final PeakMetricsTracker peaks;
  final BowlerView view;

  const _MetricsOverlay({required this.latest, required this.peaks, required this.view});

  String _fmt(double v) => v.toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        width: double.infinity,
        color: Colors.black54,
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('View: ${view.name}', style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 4),
            if (latest == null)
              const Text('Waiting for a full-body pose...', style: TextStyle(color: Colors.white))
            else
              Text(
                'Spine tilt: ${_fmt(latest!.spineTiltDeg)} deg   '
                'Knee flexion: ${_fmt(latest!.kneeFlexionDeg)} deg\n'
                'Hip-shoulder sep: ${_fmt(latest!.hipShoulderSeparationDeg)} deg   '
                'Lateral ball-ankle: ${_fmt(latest!.lateralBallAnkleDistance)} px\n'
                'Ball velocity: ${_fmt(latest!.ballVelocity)} px/s',
                style: const TextStyle(color: Colors.white),
              ),
            const Divider(color: Colors.white30, height: 16),
            Text(
              'Peaks -- tilt: ${_fmt(peaks.peakSpineTiltDeg)}  '
              'flexion: ${_fmt(peaks.peakKneeFlexionDeg)}  '
              'separation: ${_fmt(peaks.peakHipShoulderSeparationDeg)}  '
              'lateral: ${_fmt(peaks.peakLateralBallAnkleDistance)}  '
              'velocity: ${_fmt(peaks.peakReleaseVelocity)}',
              style: const TextStyle(color: Colors.amberAccent, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}
