import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_commons/google_mlkit_commons.dart';

/// Converts a `CameraImage` frame from the `camera` plugin's image stream
/// into an ML Kit `InputImage`.
///
/// CAVEAT (read before relying on this in production): camera image format
/// and byte-plane layout are platform- and device-dependent (YUV_420_888
/// on most Android devices, BGRA8888 on iOS), and correct output also
/// depends on combining the camera sensor orientation with the device's
/// current rotation. This follows the common pattern used in ML Kit's
/// official Flutter examples, but it has NOT been exercised on a real
/// device in this environment (no Flutter/Android toolchain available
/// here) -- treat first-run image orientation/greyscale issues on your
/// device as expected debugging, not necessarily a logic bug elsewhere.
InputImage? convertCameraImage({
  required CameraImage image,
  required CameraDescription camera,
  required int sensorOrientationDegrees,
}) {
  final rotation = _rotationFromDegrees(sensorOrientationDegrees);
  if (rotation == null) return null;

  if (Platform.isAndroid) {
    if (image.format.group != ImageFormatGroup.nv21 &&
        image.format.group != ImageFormatGroup.yuv420) {
      return null;
    }
    final allBytes = <int>[];
    for (final plane in image.planes) {
      allBytes.addAll(plane.bytes);
    }
    final bytes = Uint8List.fromList(allBytes);

    return InputImage.fromBytes(
      bytes: bytes,
      metadata: InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: InputImageFormat.nv21,
        bytesPerRow: image.planes.first.bytesPerRow,
      ),
    );
  }

  if (Platform.isIOS) {
    if (image.format.group != ImageFormatGroup.bgra8888) return null;
    final plane = image.planes.first;

    return InputImage.fromBytes(
      bytes: plane.bytes,
      metadata: InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: InputImageFormat.bgra8888,
        bytesPerRow: plane.bytesPerRow,
      ),
    );
  }

  return null;
}

InputImageRotation? _rotationFromDegrees(int degrees) {
  switch (degrees) {
    case 0:
      return InputImageRotation.rotation0deg;
    case 90:
      return InputImageRotation.rotation90deg;
    case 180:
      return InputImageRotation.rotation180deg;
    case 270:
      return InputImageRotation.rotation270deg;
    default:
      return null;
  }
}
