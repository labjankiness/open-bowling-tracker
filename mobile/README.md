# Live Bowling Tracker — Mobile

Flutter app, structured as four packages:

```
mobile/
├── packages/
│   ├── bowling_core/         # Pure-Dart 10-pin scoring engine, zero Flutter dependency
│   │   ├── lib/src/bowling_scorer.dart     # Direct port of core/scoring.py
│   │   └── test/bowling_scorer_test.dart   # Direct port of tests/test_scoring.py
│   ├── biomechanics_core/    # Pure-Dart biomechanics geometry, zero Flutter dependency
│   │   ├── lib/src/point2d.dart
│   │   ├── lib/src/bowling_analytics.dart          # Direct port of core/analytics.py
│   │   ├── lib/src/frame_metrics.dart              # FrameMetrics + PeakMetricsTracker
│   │   ├── lib/src/displacement_outlier_filter.dart # Rejects single-frame landmark glitches
│   │   └── test/                                   # Direct ports of the Python test suite
│   └── pin_core/             # Pure-Dart pin-deck throw detection, zero Flutter dependency
│       ├── lib/src/motion_energy.dart      # Frame-differencing motion detection
│       ├── lib/src/throw_detector.dart     # Motion-then-rest state machine
│       ├── lib/src/roll_sequence.dart      # Direct port of observations_to_rolls
│       └── test/                           # Unit tests for all three
└── app/                      # The actual Flutter app
    └── lib/
        ├── main.dart
        ├── pose/
        │   ├── pose_landmark_mapper.dart    # ML Kit Pose -> FrameMetrics adapter
        │   └── camera_image_converter.dart  # CameraImage -> ML Kit InputImage
        ├── pin/
        │   └── camera_luma_extractor.dart   # CameraImage -> brightness buffer for pin_core
        └── screens/
            ├── home_screen.dart          # Pick this device's camera role
            ├── pin_scoring_screen.dart   # Manual-only scorecard (no camera)
            ├── pin_camera_screen.dart    # Camera-assisted scoring (Phase 3)
            └── biomechanics_screen.dart  # Live camera + pose overlay (Phase 2)
```

`bowling_core`, `biomechanics_core`, and `pin_core` are deliberately
UI-independent so they're unit-testable with just the Dart SDK, no
Flutter/Android toolchain required. Verified so far (all passing):

- `bowling_core`: 9/9 tests, matches `tests/test_scoring.py` case-for-case.
- `biomechanics_core`: 11/11 tests, matches `tests/test_analytics.py`
  case-for-case, plus peak-tracking and displacement-outlier-filter tests.
- `pin_core`: 11/11 tests, matches `tests/test_pin_detector.py`'s
  `observations_to_rolls` cases, plus motion-energy and throw-detector tests.

## What's implemented vs. what's untested

The pure math/logic (all three packages above) is verified the same way the
Python prototype was — direct ported unit tests, run and passing.

The **Flutter/camera wiring** (`biomechanics_screen.dart`,
`pin_camera_screen.dart`, and their `camera_image_converter.dart` /
`camera_luma_extractor.dart` adapters) is written but **not yet run on a
real device** — there's no Flutter/Android toolchain in the environment
this was built in. Be aware of these when you first run it:

1. `camera_image_converter.dart` and `camera_luma_extractor.dart` convert
   raw camera frames to the formats ML Kit / `pin_core` expect. Byte-plane
   layout and rotation handling are notoriously device-specific
   (YUV_420_888 on Android varies by manufacturer). If pose detection or
   throw detection doesn't fire, or looks rotated/mirrored, those files are
   the first place to check.
2. The `google_mlkit_pose_detection` and `camera` package versions pinned
   in `app/pubspec.yaml` are best-effort; run `flutter pub get` and bump
   them if outdated by the time you build.
3. `pin_camera_screen.dart`'s throw detection is motion-based, not pin
   counting — see the note below.

## Why pin scoring is camera-*assisted*, not fully automatic (yet)

Real-footage testing of the Python prototype's classical-CV pin counter
(thresholding + contour counting) found it doesn't work at typical camera
distances: pins are only ~20-30px tall in frame, too small/low-contrast to
separate from the ceiling/ad screens/lane reliably (see the Python
prototype's README, "Findings from real footage").

What motion-based throw detection *can* do reliably is know **when** a
throw happened (a burst of motion, then stillness) — that part of the
classical-CV approach is sound and is what `pin_core`'s `ThrowDetector` +
`motionEnergy` implement, ported from the same logic in
`core/pin_detector.py`. `pin_camera_screen.dart` uses that to prompt for a
one-tap manual pin count the moment a throw settles, rather than pretending
to auto-count pins it can't reliably see. Phase 4 replaces the manual tap
with a trained detector once real per-clip labels exist (see the "Pin Deck
Calibrator" labeling tool referenced in the main project conversation).

## Setup (on your own machine)

This scaffold was built without the full Flutter SDK installed (it's a large,
platform-heavy toolchain not suited to a sandboxed environment). To actually
run the app:

1. **Install Flutter**: https://docs.flutter.dev/get-started/install
   (includes the Dart SDK). Run `flutter doctor` and resolve anything it flags.
2. **Android setup**: install Android Studio + an Android SDK/emulator (or
   plug in a physical device with USB debugging enabled) — `flutter doctor`
   will guide you through licenses.
3. **Generate the native platform folders** (they don't exist yet — only
   `lib/` and `pubspec.yaml` were hand-written in this environment):
   ```bash
   cd mobile/app
   flutter create .
   ```
   This is safe to run on an existing project; it fills in `android/`, `ios/`,
   etc. without touching your `lib/` code or existing `pubspec.yaml` dependencies.
4. **Add camera permissions**:
   - Android (`android/app/src/main/AndroidManifest.xml`), inside `<manifest>`:
     ```xml
     <uses-permission android:name="android.permission.CAMERA"/>
     ```
   - iOS (`ios/Runner/Info.plist`), add:
     ```xml
     <key>NSCameraUsageDescription</key>
     <string>Live Bowling Tracker needs the camera to track your bowling form.</string>
     ```
5. Install dependencies and run:
   ```bash
   flutter pub get
   flutter run
   ```

## Testing the pure-Dart packages right now (Dart SDK only, no Flutter needed)

```bash
cd mobile/packages/bowling_core && dart pub get && dart test
cd mobile/packages/biomechanics_core && dart pub get && dart test
cd mobile/packages/pin_core && dart pub get && dart test
```

## Roadmap

- **Phase 1 (done)**: project scaffold, ported scoring engine, placeholder UI.
- **Phase 2 (done, untested on hardware)**: bowler-camera screen — live camera
  preview + on-device ML Kit Pose Detection, computing the same five
  biomechanics metrics as `core/analytics.py`/`core/tracker.py`, with a live
  overlay and running session peaks, plus outlier rejection for landmark
  glitches (verified against real footage in the Python prototype).
- **Phase 3 (done, untested on hardware)**: pin-camera screen — live camera
  preview + motion-based throw detection (ported classical-CV heuristic),
  prompting for a one-tap manual pin count per detected throw rather than
  guessing a full auto-count that real-footage testing showed doesn't work
  yet. **Needs a real device test pass next, same as Phase 2.**
- **Phase 4**: replace the manual pin-count tap with a trained on-device
  TFLite detector, once real per-clip labels exist (pending: labeling pass
  on the 77 real clips via the published "Pin Deck Calibrator" tool).
- **Phase 5**: two-device session pairing/sync, combined scorecard + biomechanics view.
- **Phase 6**: Play Store release (privacy policy, signed build, closed testing).
- **Phase 7**: port to iOS, App Store release.
