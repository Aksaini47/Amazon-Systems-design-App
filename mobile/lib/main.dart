import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'theme/rf_colors.dart';
import 'screens/home_screen.dart';
import 'services/update_service.dart';
import 'utils/volume_button_service.dart';

/// Bootstraps the app inside a Zone so uncaught async errors funnel through
/// Crashlytics. Firebase initialization is GATED on whether the platform
/// can find `google-services.json` — when Sir hasn't dropped the file yet,
/// `Firebase.initializeApp` throws and we fall back to a no-Crashlytics
/// mode so the app still boots normally.
Future<void> main() async {
  // runZonedGuarded captures async errors that Flutter's framework can't
  // see (e.g. Future errors that never get awaited). Without this, those
  // crashes would silently lost.
  runZonedGuarded<Future<void>>(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // Try Firebase. If google-services.json isn't present at build time
    // OR the runtime native init fails, we just skip Crashlytics — the
    // rest of the app continues normally. Sir's flag for "is the JSON
    // wired?" is purely runtime via `Firebase.apps.isNotEmpty`.
    bool crashlyticsActive = false;
    try {
      await Firebase.initializeApp();
      crashlyticsActive = Firebase.apps.isNotEmpty;
      if (crashlyticsActive) {
        // Route every uncaught Flutter framework error into Crashlytics.
        // PlatformDispatcher catches platform-channel errors that Flutter
        // doesn't (e.g. Dart code crashes outside the framework).
        FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
        PlatformDispatcher.instance.onError = (error, stack) {
          FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
          return true;
        };
        // Disable Crashlytics in debug to avoid log noise — only ship reports
        // from release builds.
        await FirebaseCrashlytics.instance
            .setCrashlyticsCollectionEnabled(kReleaseMode);
        debugPrint('Crashlytics: enabled (collection=${kReleaseMode ? "release" : "debug-paused"})');
      }
    } catch (e) {
      // Firebase initialization failed (most commonly: google-services.json
      // missing). Surface in logcat so it's not invisible, but don't crash.
      debugPrint('Crashlytics: skipped — Firebase init failed ($e)');
    }

    VolumeButtonService(); // Initialize singleton, register MethodChannel

    // Fire-and-forget silent Shorebird update check. We DO NOT await this
    // — the user shouldn't wait at the splash for a network round-trip.
    // If a patch is staged it'll apply on the NEXT launch (Shorebird's
    // standard model). The changelog surfaces via
    // UpdateService.consumePendingChangelog() on home screen mount.
    unawaited(UpdateService.checkAndDownloadSilently());

    runApp(const RepairfullyApp());
  }, (error, stack) {
    // runZonedGuarded handler: forward to Crashlytics when active, always
    // log to stderr so local dev sees the trace.
    debugPrint('UNCAUGHT ZONE ERROR: $error\n$stack');
    if (Firebase.apps.isNotEmpty) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    }
  });
}

class RepairfullyApp extends StatelessWidget {
  const RepairfullyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RF Logger',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: RfColors.navy,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: RfColors.bg,
        appBarTheme: const AppBarTheme(
          backgroundColor: RfColors.card,
          foregroundColor: Colors.white,
          elevation: 0,
        ),
      ),
      home: const HomeScreen(),
    );
  }
}
