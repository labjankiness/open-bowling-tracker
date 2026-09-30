// Direct port of tests/test_scoring.py -- keeps the Dart and Python scoring
// engines verified against the same set of cases.
import 'package:bowling_core/bowling_core.dart';
import 'package:test/test.dart';

BowlingScorer play(List<int> rolls) {
  final scorer = BowlingScorer();
  for (final pins in rolls) {
    scorer.addRoll(pins);
  }
  return scorer;
}

void main() {
  test('all gutter game scores zero', () {
    final scorer = play(List.filled(20, 0));
    expect(scorer.isComplete, isTrue);
    expect(scorer.totalScore, 0);
  });

  test('perfect game scores 300', () {
    final scorer = play(List.filled(12, 10));
    expect(scorer.isComplete, isTrue);
    expect(scorer.totalScore, 300);
  });

  test('all spares with five pin bonus', () {
    final rolls = List.generate(20, (i) => 5)..add(5);
    final scorer = play(rolls);
    expect(scorer.isComplete, isTrue);
    expect(scorer.totalScore, 150);
  });

  test('simple open frames', () {
    final rolls = [3, 4, 2, 2, ...List.filled(16, 0)];
    final scorer = play(rolls);
    expect(scorer.isComplete, isTrue);
    final frames = scorer.frameResults();
    expect(frames[0].frameScore, 7);
    expect(frames[0].cumulativeScore, 7);
    expect(frames[1].frameScore, 4);
    expect(frames[1].cumulativeScore, 11);
    expect(scorer.totalScore, 11);
  });

  test('strike bonus uses next two rolls', () {
    final rolls = [10, 3, 4, ...List.filled(16, 0)];
    final scorer = play(rolls);
    final frames = scorer.frameResults();
    expect(frames[0].isStrike, isTrue);
    expect(frames[0].frameScore, 10 + 3 + 4);
    expect(frames[1].frameScore, 7);
    expect(frames[0].cumulativeScore, 17);
    expect(frames[1].cumulativeScore, 24);
  });

  test('game incomplete until bonus rolls are known', () {
    final scorer = BowlingScorer();
    scorer.addRoll(10); // strike in frame 1, bonus unresolved
    expect(scorer.frameResults(), isEmpty);
    expect(scorer.isComplete, isFalse);
    expect(scorer.totalScore, isNull);
  });

  test('tenth frame strike awards two extra rolls', () {
    final rolls = [...List.filled(18, 0), 10, 10, 10];
    final scorer = play(rolls);
    expect(scorer.isComplete, isTrue);
    final frames = scorer.frameResults();
    expect(frames.last.frameScore, 30);
    expect(scorer.totalScore, 30);
  });

  test('rejects out-of-range pins', () {
    final scorer = BowlingScorer();
    expect(() => scorer.addRoll(11), throwsArgumentError);
  });

  test('rejects rolls after completion', () {
    final scorer = play(List.filled(12, 10));
    expect(() => scorer.addRoll(0), throwsStateError);
  });
}
