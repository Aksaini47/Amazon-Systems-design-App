import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shorebird_code_push/shorebird_code_push.dart';
import '../utils/debug_session_log.dart';

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
      '2.0.0+8:4 - Pinch zoom in gallery photos and video\n'
      '• Pinch to zoom photos in fullscreen viewer\n'
      '• Pinch to zoom inline video in order and draft detail';

  static const _kLastSeenPatchKey = 'shorebird_last_seen_patch_v1';
  static const _kLastSeenBuildKey = 'shorebird_last_seen_build_v1';

  /// True only when the Shorebird native engine is linked (shorebird release
  /// APK). False for `flutter run`, `flutter build apk`, and debug builds.
  ///
  /// Do NOT use [readCurrentPatch] here — it returns null when no patch is
  /// installed *and* when the updater is unavailable, which made Settings
  /// show "Active" while manual check returned unavailable.
  static Future<bool> get isAvailable async => _updater.isAvailable;

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
    if (!_updater.isAvailable) {
      debugPrint('UpdateService: Shorebird engine not linked — skip silent check');
      return false;
    }
    try {
      final status = await _updater.checkForUpdate();
      // #region agent log
      String? installedBuild;
      try {
        final info = await PackageInfo.fromPlatform();
        installedBuild = '${info.version}+${info.buildNumber}';
      } catch (_) {}
      final currentPatch = await currentPatchNumber();
      DebugSessionLog.log(
        location: 'update_service.dart:checkAndDownloadSilently',
        message: 'shorebird check result',
        hypothesisId: 'H1',
        data: {
          'status': status.name,
          'installedBuild': installedBuild,
          'currentPatch': currentPatch,
          'nextPatch': await nextPatchNumber(),
        },
      );
      // #endregion
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
          debugPrint('UpdateService: updater unavailable (${_unavailableReason()})');
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
    if (!_updater.isAvailable) {
      return UpdateCheckResult(
        outcome: UpdateOutcome.unavailable,
        message: await _unavailableMessage(),
      );
    }
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
          return UpdateCheckResult(
            outcome: UpdateOutcome.upToDate,
            message: await _upToDateMessage(),
          );
        case UpdateStatus.restartRequired:
          final next = await nextPatchNumber();
          return UpdateCheckResult(
            outcome: UpdateOutcome.restartRequired,
            patchNumber: next,
            message: 'Update ready. Restart the app to apply.',
          );
        case UpdateStatus.unavailable:
          return UpdateCheckResult(
            outcome: UpdateOutcome.unavailable,
            message: await _unavailableMessage(),
          );
      }
    } catch (e) {
      return UpdateCheckResult(
        outcome: UpdateOutcome.failed,
        message: 'Update check failed: $e',
      );
    }
  }

  static String _unavailableReason() =>
      kReleaseMode ? 'not a Shorebird release APK' : 'debug build';

  static Future<String> _unavailableMessage() async {
    if (!kReleaseMode) {
      return 'OTA updates work only in release builds (not flutter run / debug).';
    }
    try {
      final info = await PackageInfo.fromPlatform();
      final installed = '${info.version}+${info.buildNumber}';
      return 'No Shorebird OTA on this install ($installed). '
          'Reinstall the Shorebird release APK for this version, then patches apply over-the-air.';
    } catch (_) {
      return 'No Shorebird OTA on this install. '
          'Install the Shorebird release APK, then patches apply over-the-air.';
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
      final lastSeenPatch = prefs.getInt(_kLastSeenPatchKey);
      final lastSeenBuild = prefs.getString(_kLastSeenBuildKey);
      final currentPatch = await currentPatchNumber() ?? 0;

      String? installedBuild;
      try {
        final info = await PackageInfo.fromPlatform();
        installedBuild = '${info.version}+${info.buildNumber}';
      } catch (_) {}

      // Fresh install: seed keys, no banner (user just installed manually).
      if (lastSeenPatch == null && lastSeenBuild == null) {
        await prefs.setInt(_kLastSeenPatchKey, currentPatch);
        if (installedBuild != null) {
          await prefs.setString(_kLastSeenBuildKey, installedBuild);
        }
        return null;
      }

      final patchUpdated = lastSeenPatch != null && currentPatch > lastSeenPatch;
      final buildUpdated = installedBuild != null &&
          lastSeenBuild != null &&
          installedBuild != lastSeenBuild;

      if (patchUpdated || buildUpdated) {
        await prefs.setInt(_kLastSeenPatchKey, currentPatch);
        if (installedBuild != null) {
          await prefs.setString(_kLastSeenBuildKey, installedBuild);
        }
        // #region agent log
        DebugSessionLog.log(
          location: 'update_service.dart:consumePendingChangelog',
          message: 'changelog will show',
          hypothesisId: 'H1',
          data: {
            'patchUpdated': patchUpdated,
            'buildUpdated': buildUpdated,
            'currentPatch': currentPatch,
            'installedBuild': installedBuild,
          },
        );
        // #endregion
        return latestChangelog;
      }

      // #region agent log
      DebugSessionLog.log(
        location: 'update_service.dart:consumePendingChangelog',
        message: 'no changelog banner',
        hypothesisId: 'H1',
        data: {
          'lastSeenPatch': lastSeenPatch,
          'currentPatch': currentPatch,
          'lastSeenBuild': lastSeenBuild,
          'installedBuild': installedBuild,
        },
      );
      // #endregion
      return null;
    } catch (e) {
      debugPrint('UpdateService: consumePendingChangelog failed — $e');
      return null;
    }
  }

  /// Shorebird OTA only delivers patches within the *same* release version.
  /// A new Play Store build (e.g. 1.0.2 → 1.0.3) is never pushed OTA.
  static Future<String> _upToDateMessage() async {
    try {
      final info = await PackageInfo.fromPlatform();
      final installed = '${info.version}+${info.buildNumber}';
      final patch = await currentPatchNumber();
      final patchLabel = patch == null ? 'base release (no patch yet)' : 'patch #$patch';
      return 'Already on latest OTA for $installed ($patchLabel).';
    } catch (_) {
      return 'Already on latest OTA patch for this release.';
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
