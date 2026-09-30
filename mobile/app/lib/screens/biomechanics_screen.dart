import 'package:flutter/material.dart';

/// Placeholder for the bowler-camera view. Phase 2 wires this up to a live
/// camera preview + on-device MediaPipe Tasks Pose Landmarker, porting the
/// geometry from `core/analytics.py` to compute spine tilt, knee flexion,
/// hip-shoulder separation, lateral ball-ankle distance, and release
/// velocity in real time, mirroring the Python prototype's `track` command.
class BiomechanicsScreen extends StatelessWidget {
  const BiomechanicsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bowler Camera')),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Live pose tracking lands in Phase 2.\n\n'
            'This screen will show a camera preview with a pose skeleton '
            'overlay and live spine tilt / knee flexion / hip-shoulder '
            'separation / release velocity readouts, ported from the '
            'Python core/analytics.py + core/tracker.py.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
