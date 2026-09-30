import 'dart:io';

import 'package:camera/camera.dart';

/// Extracts a single-channel brightness ("luma") buffer from one
/// `CameraImage` frame, for `pin_core`'s `motionEnergy` to compare between
/// frames.
///
/// CAVEAT (same spirit as `pose/camera_image_converter.dart`): on Android
/// this is just the Y plane of YUV_420_888/NV21 -- cheap and exact. On iOS
/// the `camera` plugin delivers BGRA8888, so luma is approximated per pixel
/// from the color channels; this has not been exercised on real iOS
/// hardware in this environment (no Flutter/iOS toolchain available here).
List<int>? extractLuma(CameraImage image) {
  if (Platform.isAndroid) {
    if (image.format.group != ImageFormatGroup.yuv420 &&
        image.format.group != ImageFormatGroup.nv21) {
      return null;
    }
    return image.planes.first.bytes;
  }

  if (Platform.isIOS) {
    if (image.format.group != ImageFormatGroup.bgra8888) return null;
    final plane = image.planes.first;
    final bytesPerPixel = 4;
    final pixelCount = plane.bytes.length ~/ bytesPerPixel;
    final luma = List<int>.filled(pixelCount, 0);
    for (var i = 0; i < pixelCount; i++) {
      final offset = i * bytesPerPixel;
      final b = plane.bytes[offset];
      final g = plane.bytes[offset + 1];
      final r = plane.bytes[offset + 2];
      // Standard perceptual luma weighting.
      luma[i] = (0.299 * r + 0.587 * g + 0.114 * b).round();
    }
    return luma;
  }

  return null;
}
