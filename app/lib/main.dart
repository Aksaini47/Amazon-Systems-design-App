import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'config/app_config.dart';
import 'models/capture_session.dart';
import 'package:flutter/services.dart';
import 'theme/rf_theme.dart';
import 'screens/home_screen.dart';
import 'screens/trial_gate.dart';
import 'services/activity_log_service.dart';
import 'services/update_service.dart';
import 'utils/volume_button_service.dart';
import 'widgets/demo_watermark_overlay.dart';

/// Prod entrypoint — demo entrypoint is lib/main_demo.dart, which calls the
/// same bootstrap() with isDemo: true. Both share this one Dart app; only
/// AppConfig.isDemo (set below) and the Gradle flavor's applicationId differ.
Future<void> main() => bootstrap(isDemo: false);

/// Bootstraps the app inside a Zone so uncaught async errors funnel through
/// Crashlytics. Firebase initialization is GATED on whether the platform
/// can find `google-services.json` — when Sir hasn't dropped the file yet,
/// `Firebase.initializeApp` throws and we fall back to a no-Crashlytics
/// mode so the app still boots normally.
Future<void> bootstrap({required bool isDemo}) async {
  AppConfig.isDemo = isDemo;
  // runZonedGuarded captures async errors that Flutter's framework can't
  // see (e.g. Future errors that never get awaited). Without this, those
  // crashes would silently lost.
  unawaited(runZonedGuarded<Future<void>>(() async {
    WidgetsFlutterBinding.ensureInitialized();
    SystemChrome.setSystemUIOverlayStyle(rfSystemUiStyle);

    // Real installed version for meta.json provenance (never crash the boot
    // over it — the fallback 'unknown' is visible and honest).
    try {
      final info = await PackageInfo.fromPlatform();
      CaptureSession.appVersion = '${info.version}+${info.buildNumber}';
    } catch (e) {
      debugPrint('PackageInfo failed, meta.json keeps app_version=unknown: $e');
    }

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

    // Cold-start marker — first entry in both the local activity log and its
    // Firestore mirror for this launch, so a session's later events can be
    // correlated against which app_version/patch/device they ran on.
    unawaited(ActivityLogService.log(
      event: 'app_open',
      extra: {'is_demo': isDemo.toString()},
    ));

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
  }));
}

class RepairfullyApp extends StatelessWidget {
  const RepairfullyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RF Logger',
      debugShowCheckedModeBanner: false,
      // Dark only (Sir, 2026-10-10): one theme, forced for every system
      // setting. See theme/rf_theme.dart.
      theme: buildRfTheme(),
      darkTheme: buildRfTheme(),
      themeMode: ThemeMode.dark,
      // Demo build: one global tiled "DEMO" overlay covering every screen —
      // Home, Settings, Gallery, camera preview, dialogs (incl. the tour),
      // everything. builder wraps the Navigator's output, so it survives
      // route pushes/pops for free.
      //
      // MUST be Positioned.fill, not a bare Stack child — a bare child gets
      // loose constraints sized to its own preferred size, and
      // DemoWatermarkOverlay's CustomPaint(size: Size.infinite) collapses
      // to zero size under loose constraints instead of filling the
      // screen (confirmed on-device: the overlay was invisible without
      // this wrapper).
      builder: (context, child) {
        if (!AppConfig.isDemo || child == null) return child ?? const SizedBox.shrink();
        return Stack(
          children: [
            child,
            const Positioned.fill(child: DemoWatermarkOverlay()),
          ],
        );
      },
      home: AppConfig.isDemo ? const TrialGate() : const HomeScreen(),
    );
  }
}
