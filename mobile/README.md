# Live Bowling Tracker — Mobile (Phase 1 scaffold)

Flutter app, structured as two packages:

```
mobile/
├── packages/
│   └── bowling_core/       # Pure-Dart scoring engine, zero Flutter dependency
│       ├── lib/src/bowling_scorer.dart   # Direct port of core/scoring.py
│       └── test/bowling_scorer_test.dart # Direct port of tests/test_scoring.py
└── app/                    # The actual Flutter app
    └── lib/
        ├── main.dart
        └── screens/
            ├── home_screen.dart          # Pick this device's camera role
            ├── pin_scoring_screen.dart   # Live scorecard (manual entry for now)
            └── biomechanics_screen.dart  # Placeholder for Phase 2 pose tracking
```

`bowling_core` is deliberately UI-independent so it can be unit-tested with
just the Dart SDK, no Flutter/Android toolchain required — that's how it was
verified while this app was scaffolded (9/9 tests passing, matching the
Python `tests/test_scoring.py` suite case-for-case).

## Setup (on your own machine)

This scaffold was built without the full Flutter SDK installed (it's a large,
platform-heavy toolchain not suited to a sandboxed environment). To actually
run the app you'll need, on your dev machine:

1. **Install Flutter**: https://docs.flutter.dev/get-started/install
   (includes the Dart SDK). Run `flutter doctor` and resolve anything it flags.
2. **Android setup**: install Android Studio + an Android SDK/emulator (or
   plug in a physical device with USB debugging enabled) — `flutter doctor`
   will guide you through licenses.
3. From `mobile/app/`:
   ```bash
   flutter pub get
   flutter run
   ```

## Testing the scoring engine right now (Dart SDK only, no Flutter needed)

```bash
cd mobile/packages/bowling_core
dart pub get
dart test
```

## Roadmap (see main project conversation for full detail)

- **Phase 1 (done)**: project scaffold, ported scoring engine, placeholder UI.
- **Phase 2**: bowler-camera screen — live camera preview + on-device
  MediaPipe Tasks Pose Landmarker, porting `core/analytics.py`'s geometry.
- **Phase 3**: pin-camera screen — live camera preview + a first pass at
  pin detection (start with a ported version of the classical CV heuristic).
- **Phase 4**: replace classical-CV pin detection with a trained on-device
  TFLite model, using real pin-deck footage for training data.
- **Phase 5**: two-device session pairing/sync, combined scorecard + biomechanics view.
- **Phase 6**: Play Store release (privacy policy, signed build, closed testing).
- **Phase 7**: port to iOS, App Store release.
