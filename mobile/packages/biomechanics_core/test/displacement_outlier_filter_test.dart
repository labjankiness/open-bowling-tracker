import 'package:biomechanics_core/biomechanics_core.dart';
import 'package:test/test.dart';

void main() {
  test('no outlier flagged until minSamples reached', () {
    final filter = DisplacementOutlierFilter(minSamples: 5);
    for (var i = 0; i < 4; i++) {
      expect(filter.isOutlier(1000.0), isFalse);
      filter.accept(5.0);
    }
  });

  test('flags a displacement far above the recent median', () {
    final filter = DisplacementOutlierFilter(factor: 6.0, minSamples: 5);
    for (var i = 0; i < 6; i++) {
      filter.accept(5.0);
    }
    expect(filter.isOutlier(5.0), isFalse); // normal frame
    expect(filter.isOutlier(100.0), isTrue); // 20x the median -> glitch
  });

  test('accepted displacements shift the rolling baseline', () {
    final filter = DisplacementOutlierFilter(factor: 6.0, minSamples: 5, windowSize: 5);
    for (var i = 0; i < 5; i++) {
      filter.accept(5.0);
    }
    expect(filter.isOutlier(40.0), isTrue);
    // A sustained real speed increase should stop being flagged once it
    // becomes the new normal.
    for (var i = 0; i < 5; i++) {
      filter.accept(40.0);
    }
    expect(filter.isOutlier(42.0), isFalse);
  });
}
