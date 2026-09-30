import 'package:bowling_core/bowling_core.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:pin_core/pin_core.dart';

import '../pin/camera_luma_extractor.dart';

/// Camera-assisted pin scoring: watches the pin deck for a motion-then-rest
/// pattern (a ball rolling through) via `pin_core`'s `ThrowDetector`, and
/// prompts for a manual pin count the moment it settles.
///
/// This is deliberately NOT full automatic pin counting -- real-footage
/// testing of the classical-CV pin counter (see the Python prototype's
/// README "Findings from real footage") showed pins are too small/low
/// contrast at typical camera distances for reliable automated counting.
/// What IS automated here is knowing *when* a throw happened; the count
/// itself stays a one-tap manual confirmation until a trained detector
/// (Phase 4) replaces it.
class PinCameraScreen extends StatefulWidget {
  const PinCameraScreen({super.key});

  @override
  State<PinCameraScreen> createState() => _PinCameraScreenState();
}

class _PinCameraScreenState extends State<PinCameraScreen> {
  CameraController? _controller;
  String? _error;
  bool _busy = false;

  List<int>? _prevLuma;
  final ThrowDetector _throwDetector = ThrowDetector();
  final List<int> _observations = [];
  BowlingScorer _scorer = BowlingScorer();

  bool _promptOpen = false;
  int _throwsDetected = 0;

  @override
  void initState() {
    super.initState();
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
      final controller = CameraController(camera, ResolutionPreset.medium, enableAudio: false);
      await controller.initialize();
      await controller.startImageStream(_onCameraImage);

      if (!mounted) return;
      setState(() => _controller = controller);
    } catch (e) {
      setState(() => _error = 'Camera init failed: $e');
    }
  }

  void _onCameraImage(CameraImage image) {
    if (_busy || _promptOpen) return;
    _busy = true;
    try {
      final luma = extractLuma(image);
      if (luma == null) return;

      if (_prevLuma != null) {
        final energy = motionEnergy(_prevLuma!, luma);
        if (_throwDetector.onFrame(energy)) {
          _throwsDetected++;
          _promptForPinCount();
        }
      }
      _prevLuma = luma;
    } finally {
      _busy = false;
    }
  }

  void _promptForPinCount() {
    if (!mounted) return;
    setState(() => _promptOpen = true);
    showModalBottomSheet<void>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      builder: (context) => _PinCountSheet(
        onSelected: (standing) {
          Navigator.of(context).pop();
          _recordObservation(standing);
        },
      ),
    ).whenComplete(() {
      if (mounted) setState(() => _promptOpen = false);
    });
  }

  void _recordObservation(int standingPins) {
    _observations.add(standingPins);
    final rolls = observationsToRolls(_observations);
    final scorer = BowlingScorer();
    for (final pins in rolls) {
      if (scorer.isComplete) break;
      scorer.addRoll(pins);
    }
    setState(() => _scorer = scorer);
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pin Camera'),
        actions: [
          IconButton(
            tooltip: 'Manually log a throw',
            icon: const Icon(Icons.add_circle_outline),
            onPressed: _promptOpen ? null : _promptForPinCount,
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

    final frames = _scorer.frameResults();

    return Column(
      children: [
        AspectRatio(
          aspectRatio: controller.value.aspectRatio,
          child: CameraPreview(controller),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Throws detected: $_throwsDetected', style: Theme.of(context).textTheme.bodySmall),
              Text(
                _scorer.isComplete ? 'Final: ${_scorer.totalScore}' : 'Frame ${_scorer.currentFrameNumber} of 10',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: frames.isEmpty
              ? const Center(child: Text('Watching the pin deck for the first throw...'))
              : ListView.builder(
                  itemCount: frames.length,
                  itemBuilder: (context, i) {
                    final f = frames[i];
                    final tag = f.isStrike ? 'STRIKE' : (f.isSpare ? 'SPARE' : '');
                    return ListTile(
                      leading: CircleAvatar(child: Text('${f.frameNumber}')),
                      title: Text('Rolls: ${f.rolls} $tag'),
                      trailing: Text(
                        '${f.cumulativeScore}',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _PinCountSheet extends StatelessWidget {
  final void Function(int standingPins) onSelected;

  const _PinCountSheet({required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Throw detected -- how many pins are standing now?',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (var pins = 0; pins <= pinsPerRack; pins++)
                  OutlinedButton(
                    onPressed: () => onSelected(pins),
                    child: Text('$pins'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
