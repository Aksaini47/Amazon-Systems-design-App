import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shorebird_code_push/shorebird_code_push.dart';

/// Centralized Shorebird code-push wrapper.
///
/// Behavior (per Sir's directive 2026-05-17):
///   1. On app start, silently check for a new patch in the background.
///   2. If a new patch is available, download + install it. The patch
///      applies on NEXT launch (Shorebird's standard model — no live
///      hot-swap of running Dart code).
///   3. The next time the user opens the app, the new patch is active.
///      [UpdateService.consumePendingChangelog] returns the changelog
///      bundled with the patch (read from a local `CHANGELOG.md`-style
///      source compiled into the Dart code), and the AboutSettings UI
///      surfaces it as a one-time toast/banner.
///
/// Changelog source:
///   The Shorebird patch protocol does NOT carry an arbitrary description
///   payload to the device. So the "changelog for patch N" is shipped
///   inside the Dart code itself as the [latestChangelog] constant — when
///   Sir pushes a new patch, the constant is bumped in the same commit.
///   At runtime, when the installed patch number changes, the new
///   constant becomes available; we compare against the last-seen patch
///   number from SharedPreferences and surface the diff exactly once.
class UpdateService {
  UpdateService._();

  static final _updater = ShorebirdUpdater();

  /// Bumped each time Sir cuts a `shorebird patch` push. Format:
  ///   '<release-version>:<patch-number> — <short summary>\n• bullet 1\n• bullet 2'
  /// The patch-number portion is what the device uses to detect "did this
  /// changelog already display?"; everything before the colon is the
  /// associated release version.
  static const String latestChangelog =
      '1.0.1+2:0 — Initial release\n'
      '• Camera capture (PK + RT modes)\n'
      '• Barcode + OCR scanner with carrier classification\n'
      '• Local gallery with order/draft sessions\n'
      '• Firebase Crashlytics + Shorebird OTA wired';

  static const _kLastSeenPatchKey = 'shorebird_last_seen_patch_v1';

  /// True only on devices where the Shorebird native engine is present
  /// (release / patched builds). Always false in `flutter run` debug.
  static Future<bool> get isAvailable async {
    try {
      // ShorebirdUpdater throws if the native engine isn't linked.
      await _updater.readCurrentPatch();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Currently-installed patch number (null if none / debug build).
  static Future<int?> currentPatchNumber() async {
    try {
      final patch = await _updater.readCurrentPatch();
      return patch?.number;
    } catch (_) {
      return null;
    }
  }

  /// Patch number that's staged for the next launch (null if none).
  static Future<int?> nextPatchNumber() async {
    try {
      final patch = await _updater.readNextPatch();
      return patch?.number;
    } catch (_) {
      return null;
    }
  }

  /// Background-check + silent-download. Idempotent — safe to call from
  /// many places. Logs progress but never blocks UI; the download happens
  /// off the main isolate inside the Shorebird native code.
  ///
  /// Returns true if a patch is staged for next launch.
  static Future<bool> checkAndDownloadSilently() async {
    try {
      final status = await _updater.checkForUpdate();
      switch (status) {
        case UpdateStatus.outdated:
          debugPrint('UpdateService: outdated → downloading patch silently');
          await _updater.update();
          final next = await nextPatchNumber();
          debugPrint('UpdateService: patch staged for next launch (next=$next)');
          return next != null;
        case UpdateStatus.upToDate:
          debugPrint('UpdateService: up to date');
          return false;
        case UpdateStatus.restartRequired:
          debugPrint('UpdateService: patch already downloaded — applies on next launch');
          return true;
        case UpdateStatus.unavailable:
          debugPrint('UpdateService: updater unavailable (debug build?)');
          return false;
      }
    } catch (e) {
      // Don't surface to the user — silent failure mode by design.
      // Crashlytics will pick it up via runZonedGuarded if it's fatal.
      debugPrint('UpdateService: silent check failed — $e');
      return false;
    }
  }

  /// Manual "Check for updates" from the About panel. Same logic as the
  /// silent path, but the caller can show a spinner + toast on outcome.
  static Future<UpdateCheckResult> checkManually() async {
    try {
      final status = await _updater.checkForUpdate();
      switch (status) {
        case UpdateStatus.outdated:
          await _updater.update();
          final next = await nextPatchNumber();
          return UpdateCheckResult(
            outcome: UpdateOutcome.downloaded,
            patchNumber: next,
            message: 'Update downloaded. Restart the app to apply.',
          );
        case UpdateStatus.upToDate:
          return const UpdateCheckResult(
            outcome: UpdateOutcome.upToDate,
            message: 'You are on the latest version.',
          );
        case UpdateStatus.restartRequired:
          final next = await nextPatchNumber();
          return UpdateCheckResult(
            outcome: UpdateOutcome.restartRequired,
            patchNumber: next,
            message: 'Update ready. Restart the app to apply.',
          );
        case UpdateStatus.unavailable:
          return const UpdateCheckResult(
            outcome: UpdateOutcome.unavailable,
            message: 'Updates not available in this build.',
          );
      }
    } catch (e) {
      return UpdateCheckResult(
        outcome: UpdateOutcome.failed,
        message: 'Update check failed: $e',
      );
    }
  }

  /// Returns the changelog string IF the device just applied a new patch
  /// since last launch, OR null if we've already shown it. Stores the
  /// "last-seen" patch number in SharedPreferences so the same changelog
  /// is never shown twice.
  ///
  /// Called by the home screen on first build; the home screen shows it
  /// as a one-time banner.
  static Future<String?> consumePendingChangelog() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final lastSeen = prefs.getInt(_kLastSeenPatchKey);
      final current = await currentPatchNumber() ?? 0;
      if (lastSeen == null) {
        // First-ever launch — seed but don't show changelog (nothing has
        // changed from the user's perspective).
        await prefs.setInt(_kLastSeenPatchKey, current);
        return null;
      }
      if (current > lastSeen) {
        await prefs.setInt(_kLastSeenPatchKey, current);
        return latestChangelog;
      }
      return null;
    } catch (e) {
      debugPrint('UpdateService: consumePendingChangelog failed — $e');
      return null;
    }
  }
}

enum UpdateOutcome { upToDate, downloaded, restartRequired, unavailable, failed }

class UpdateCheckResult {
  final UpdateOutcome outcome;
  final int? patchNumber;
  final String message;
  const UpdateCheckResult({
    required this.outcome,
    this.patchNumber,
    required this.message,
  });
}
