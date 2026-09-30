import 'package:bowling_core/bowling_core.dart';
import 'package:flutter/material.dart';

/// Live scoring screen. For now, rolls are entered manually with this
/// scorecard UI so the ported `bowling_core` engine is fully wired end to
/// end; Phase 2 replaces the manual entry with on-device pin detection
/// feeding `BowlingScorer.addRoll` automatically from the camera feed.
class PinScoringScreen extends StatefulWidget {
  const PinScoringScreen({super.key});

  @override
  State<PinScoringScreen> createState() => _PinScoringScreenState();
}

class _PinScoringScreenState extends State<PinScoringScreen> {
  final BowlingScorer _scorer = BowlingScorer();

  int get _pinsStandingThisRoll {
    // How many pins are still up for the *next* roll (10 at the start of a
    // frame, or whatever's left after the frame's first roll).
    final frames = _scorer.frameResults();
    final resolvedRolls = frames.fold<int>(0, (sum, f) => sum + f.rolls.length);
    final rolls = _scorer.rolls;
    if (resolvedRolls >= rolls.length) return pinsPerRack;

    // Rolls beyond the resolved frames belong to the frame in progress.
    final pendingRolls = rolls.sublist(resolvedRolls);
    var standing = pinsPerRack;
    for (final r in pendingRolls) {
      standing -= r;
    }
    return standing;
  }

  void _addRoll(int pins) {
    setState(() => _scorer.addRoll(pins));
  }

  @override
  Widget build(BuildContext context) {
    final frames = _scorer.frameResults();
    final maxPins = _pinsStandingThisRoll;

    return Scaffold(
      appBar: AppBar(title: const Text('Pin-Deck Scoring')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
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
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Text(
                  _scorer.isComplete
                      ? 'Final score: ${_scorer.totalScore}'
                      : 'Frame ${_scorer.currentFrameNumber} of 10',
                  style: const TextStyle(fontSize: 18),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    for (var pins = 0; pins <= maxPins; pins++)
                      OutlinedButton(
                        onPressed: _scorer.isComplete ? null : () => _addRoll(pins),
                        child: Text('$pins'),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
