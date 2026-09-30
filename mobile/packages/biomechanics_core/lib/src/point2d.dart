import 'dart:math' as math;

/// A minimal 2D point/vector, pixel-space (x, y), origin top-left, y
/// increasing downward (matches the camera image / OpenCV convention used
/// by the Python prototype's `core/analytics.py`).
class Point2D {
  final double x;
  final double y;

  const Point2D(this.x, this.y);

  Point2D operator +(Point2D other) => Point2D(x + other.x, y + other.y);
  Point2D operator -(Point2D other) => Point2D(x - other.x, y - other.y);
  Point2D operator /(double scalar) => Point2D(x / scalar, y / scalar);

  double dot(Point2D other) => x * other.x + y * other.y;

  double get length => math.sqrt(x * x + y * y);

  static Point2D midpoint(Point2D a, Point2D b) => (a + b) / 2.0;
}
