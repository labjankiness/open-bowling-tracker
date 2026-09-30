import 'package:flutter/material.dart';

import 'screens/home_screen.dart';

void main() {
  runApp(const LiveBowlingTrackerApp());
}

class LiveBowlingTrackerApp extends StatelessWidget {
  const LiveBowlingTrackerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Live Bowling Tracker',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      darkTheme: ThemeData(
        colorSchemeSeed: Colors.indigo,
        brightness: Brightness.dark,
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
