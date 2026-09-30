# Live Bowling Tracker — Mobile

Flutter app, structured as three packages:

```
mobile/
├── packages/
│   ├── bowling_core/         # Pure-Dart 10-pin scoring engine, zero Flutter dependency
│   │   ├── lib/src/bowling_scorer.dart     # Direct port of core/scoring.py
│   │   └── test/bowling_scorer_test.dart   # Direct port of tests/test_scoring.py
│   └── biomechanics_core/    # Pure-Dart biomechanics geometry, zero Flutter dependency
│       ├── lib/src/point2d.dart
│       ├── lib/src/bowling_analytics.dart  # Direct port of core/analytics.py
│       ├── lib/src/frame_metrics.dart      # FrameMetrics + PeakMetricsTracker
│       └── test/bowling_analytics_test.dart # Direct port of tests/test_analytics.py
└── app/                      # The actual Flutter app
    └── lib/
        ├── main.dart
        ├── pose/
        │   ├── pose_landmark_mapper.dart    # ML Kit Pose -> FrameMetrics adapter
        │   └── camera_image_converter.dart  # CameraImage -> ML Kit InputImage
        └── screens/
            ├── home_screen.dart          # Pick this device's camera role
            ├── pin_scoring_screen.dart   # Live scorecard (manual entry for now)
            └── biomechanics_screen.dart  # Live camera + pose overlay (Phase 2)
```

Both `bowling_core` and `biomechanics_core` are deliberately UI-independent so
they're unit-testable with just the Dart SDK, no Flutter/Android toolchain
required. Verified so far:

- `bowling_core`: 9/9 tests passing, matches `tests/test_scoring.py` case-for-case.
- `biomechanics_core`: 8/8 tests passing, matches `tests/test_analytics.py`
  case-for-case (plus one extra test for the peak-tracking helper).

## What's implemented vs. what's untested

The pure math (both packages above) is verified the same way the Python
prototype was — direct ported unit tests, run and passing.

The **Flutter/camera/pose-detector wiring** (`biomechanics_screen.dart`,
`camera_image_converter.dart`, `pose_landmark_mapper.dart`) is written but
**not yet run on a real device** — there's no Flutter/Android toolchain in
the environment this was built in. Be aware of two things when you first run it:

1. `camera_image_converter.dart` converts raw camera frames to the format
   ML Kit expects. Byte-plane layout and rotation handling are notoriously
   device-specific (YUV_420_888 on Android varies by manufacturer). If pose
   detection doesn't fire or the skeleton looks rotated/mirrored on your
   device, that file is the first place to check — it follows the common
   pattern from ML Kit's official Flutter examples but hasn't been verified
   against real hardware yet.
2. The `google_mlkit_pose_detection` and `camera` package versions pinned in
   `app/pubspec.yaml` are best-effort; run `flutter pub get` and bump them if
   they're outdated by the time you build.

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
```

## Roadmap

- **Phase 1 (done)**: project scaffold, ported scoring engine, placeholder UI.
- **Phase 2 (done, untested on hardware)**: bowler-camera screen — live camera
  preview + on-device ML Kit Pose Detection, computing the same five
  biomechanics metrics as `core/analytics.py`/`core/tracker.py`, with a live
  overlay and running session peaks. **Needs a real device test pass next.**
- **Phase 3**: pin-camera screen — live camera preview + a first pass at
  pin detection (start with a ported version of the classical CV heuristic).
- **Phase 4**: replace classical-CV pin detection with a trained on-device
  TFLite model, using real pin-deck footage for training data.
- **Phase 5**: two-device session pairing/sync, combined scorecard + biomechanics view.
- **Phase 6**: Play Store release (privacy policy, signed build, closed testing).
- **Phase 7**: port to iOS, App Store release.
