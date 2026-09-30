import 'package:flutter/material.dart';

import 'pin_scoring_screen.dart';
import 'biomechanics_screen.dart';

/// Landing screen: choose which camera role this phone plays for the
/// session -- watching the bowler's approach, or watching the pin deck.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Live Bowling Tracker')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Pick this device\'s role for the session',
                style: TextStyle(fontSize: 16),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                icon: const Icon(Icons.accessibility_new),
                label: const Text('Bowler camera (biomechanics)'),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const BiomechanicsScreen()),
                ),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                icon: const Icon(Icons.sports_score),
                label: const Text('Pin-deck camera (live scoring)'),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const PinScoringScreen()),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
