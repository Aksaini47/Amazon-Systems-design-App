import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum TrialBlockReason { none, expired, killSwitch, unverifiable }

class TrialStatus {
  final bool blocked;
  final TrialBlockReason reason;
  final int daysRemaining;
  final bool fromCache;

  const TrialStatus({
    required this.blocked,
    required this.reason,
    required this.daysRemaining,
    required this.fromCache,
  });
}

/// Demo-flavor hard trial gate (see the RF Logger demo build plan for full
/// background). Summary of the design:
///
///   - Device anchor: Settings.Secure.ANDROID_ID, fetched via the native
///     `com.repairfully.camera/device_id` channel (MainActivity.kt) — NOT
///     device_info_plus, whose `id` field returns Build.ID (the OS firmware
///     build, identical across every device on that build) since androidId
///     was dropped from that package in v4.0.0. Android ID survives an
///     app-data-clear/reinstall of the same signed APK, which is the whole
///     point of using it as the anchor.
///   - Truth lives server-side: Firestore doc `demo_trials/{androidId}`.
///     `installedAt` is set exactly once, only to the server's own request
///     time (enforced by firestore.rules) — the client can never backdate
///     it. `lastSeenAt` is bumped forward on every check-in under the same
///     server-time constraint.
///   - Trial length + a remote kill switch come from Remote Config so Sir
///     can adjust either without shipping a new APK.
///   - Monitoring: every device that ever checks in gets a doc in Firebase
///     console -> Firestore Database -> demo_trials, tagged with its model/
///     manufacturer/Android version (set once at first check-in) alongside
///     installedAt/lastSeenAt — enough to see, per device, "is this the
///     right phone, and is it actually being opened." To force-lock
///     everything immediately (not wait for day 30): Firebase console ->
///     Remote Config -> flip demo_kill_switch to true -> Publish. Takes
///     effect on the device's next check-in (needs it to have internet).
///   - Firestore's default offline persistence is explicitly disabled and
///     reads/writes are forced to `Source.server` — otherwise a device in
///     airplane mode could "successfully" check in against its own local
///     write queue, silently defeating the gate.
///   - A short offline grace window (72h) trusts the last server-confirmed
///     result so the app stays usable without signal briefly. Beyond that,
///     or on a first-ever launch with no network at all, it fails CLOSED —
///     never grants access without at least one real server confirmation.
///
/// This is deliberately not paired with code obfuscation in v1 (see plan) —
/// the actual guarantee is that `installedAt`/`lastSeenAt` can't be forged
/// without control over the Firestore project, which holds regardless of
/// whether this Dart source is readable in a decompiled APK.
class TrialService {
  TrialService._();

  static const _deviceIdChannel =
      MethodChannel('com.repairfully.camera/device_id');
  static const _collection = 'demo_trials';

  static const _kCachedInstalledAtMs = 'trial_cached_installed_at_ms_v1';
  static const _kCachedLastSeenAtMs = 'trial_cached_last_seen_at_ms_v1';
  static const _kCachedBlocked = 'trial_cached_blocked_v1';
  static const _kCacheWrittenAtMs = 'trial_cache_written_at_ms_v1';

  static const _offlineGrace = Duration(hours: 72);
  static const _defaultTrialDays = 30;

  /// Runs the full check-in: device anchor -> Firestore create/update ->
  /// Remote Config -> blocked/allowed decision. Never throws — falls back
  /// to the cached last-known result (then fails closed) on any error.
  static Future<TrialStatus> checkIn() async {
    try {
      if (Firebase.apps.isEmpty) {
        // Firebase didn't initialize (e.g. demo google-services.json not
        // dropped in yet) — fail closed rather than silently granting
        // unlimited access.
        return _fallback(reason: TrialBlockReason.unverifiable);
      }

      final androidId = await _deviceAnchorId();
      if (androidId == null || androidId.isEmpty) {
        return _fallback(reason: TrialBlockReason.unverifiable);
      }

      FirebaseFirestore.instance.settings =
          const Settings(persistenceEnabled: false);

      final docRef =
          FirebaseFirestore.instance.collection(_collection).doc(androidId);
      final existing =
          await docRef.get(const GetOptions(source: Source.server));

      if (!existing.exists) {
        await docRef.set({
          'installedAt': FieldValue.serverTimestamp(),
          'lastSeenAt': FieldValue.serverTimestamp(),
          ...await _deviceLabel(),
        });
      } else {
        await docRef.update({'lastSeenAt': FieldValue.serverTimestamp()});
      }

      final resolved =
          await docRef.get(const GetOptions(source: Source.server));
      final data = resolved.data();
      final installedAt = (data?['installedAt'] as Timestamp?)?.toDate();
      final lastSeenAt = (data?['lastSeenAt'] as Timestamp?)?.toDate();
      if (installedAt == null || lastSeenAt == null) {
        return _fallback(reason: TrialBlockReason.unverifiable);
      }

      final rc = FirebaseRemoteConfig.instance;
      await rc.setConfigSettings(RemoteConfigSettings(
        fetchTimeout: const Duration(seconds: 10),
        // Default minimumFetchInterval is 12h — a freshly-flipped kill
        // switch must take effect on the NEXT check-in, not up to half a
        // day later.
        minimumFetchInterval: Duration.zero,
      ));
      await rc.setDefaults(const {
        'demo_trial_days': _defaultTrialDays,
        'demo_kill_switch': false,
      });
      try {
        await rc.fetchAndActivate();
      } catch (e) {
        debugPrint('TrialService: Remote Config fetch failed, using defaults — $e');
      }
      final fetchedTrialDays = rc.getInt('demo_trial_days');
      final killSwitch = rc.getBool('demo_kill_switch');
      final trialDays = fetchedTrialDays > 0 ? fetchedTrialDays : _defaultTrialDays;

      final elapsedDays = lastSeenAt.difference(installedAt).inDays;
      final expired = elapsedDays >= trialDays;
      final blocked = expired || killSwitch;

      await _writeCache(
        installedAtMs: installedAt.millisecondsSinceEpoch,
        lastSeenAtMs: lastSeenAt.millisecondsSinceEpoch,
        blocked: blocked,
      );

      return TrialStatus(
        blocked: blocked,
        reason: killSwitch
            ? TrialBlockReason.killSwitch
            : expired
                ? TrialBlockReason.expired
                : TrialBlockReason.none,
        daysRemaining: (trialDays - elapsedDays).clamp(0, trialDays),
        fromCache: false,
      );
    } catch (e) {
      debugPrint('TrialService: check-in failed, falling back to cache — $e');
      return _fallback(reason: TrialBlockReason.unverifiable);
    }
  }

  /// Best-effort device metadata for the Firebase console's Firestore view
  /// only — never read back by app logic, so a failure here can't affect
  /// the trial decision. Written once at doc creation (device model doesn't
  /// change over a trial's lifetime, so no need to refresh on every
  /// check-in / no security-rule change needed for it).
  static Future<Map<String, dynamic>> _deviceLabel() async {
    try {
      final info = await DeviceInfoPlugin().androidInfo;
      return {
        'deviceModel': info.model,
        'deviceManufacturer': info.manufacturer,
        'androidRelease': info.version.release,
      };
    } catch (e) {
      debugPrint('TrialService: device label lookup failed (non-fatal) — $e');
      return const {};
    }
  }

  static Future<String?> _deviceAnchorId() async {
    try {
      return await _deviceIdChannel.invokeMethod<String>('getAndroidId');
    } catch (e) {
      debugPrint('TrialService: getAndroidId channel failed — $e');
      return null;
    }
  }

  static Future<void> _writeCache({
    required int installedAtMs,
    required int lastSeenAtMs,
    required bool blocked,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_kCachedInstalledAtMs, installedAtMs);
    await prefs.setInt(_kCachedLastSeenAtMs, lastSeenAtMs);
    await prefs.setBool(_kCachedBlocked, blocked);
    await prefs.setInt(_kCacheWrittenAtMs, DateTime.now().millisecondsSinceEpoch);
  }

  /// Offline/error path. Trusts the last server-confirmed `blocked` value
  /// for up to 72h past the last successful check-in; beyond that — or if
  /// no check-in has ever succeeded — fails closed. `daysRemaining` here is
  /// a local-clock best-effort DISPLAY value only; it never drives the
  /// blocked decision, so a wrong device clock can't be used to bypass
  /// anything — it can only make the app's own "N days left" label wrong
  /// for the person who tampered with their own clock.
  static Future<TrialStatus> _fallback({required TrialBlockReason reason}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cacheWrittenAtMs = prefs.getInt(_kCacheWrittenAtMs);
      if (cacheWrittenAtMs == null) {
        // No cache at all — e.g. very first launch with no network. Do NOT
        // grant 30 days blind; that would be a trivial "install with WiFi
        // off" bypass of the very first check-in.
        return const TrialStatus(
          blocked: true,
          reason: TrialBlockReason.unverifiable,
          daysRemaining: 0,
          fromCache: false,
        );
      }

      final cacheWrittenAt = DateTime.fromMillisecondsSinceEpoch(cacheWrittenAtMs);
      final withinGrace = DateTime.now().difference(cacheWrittenAt) <= _offlineGrace;
      final cachedBlocked = prefs.getBool(_kCachedBlocked) ?? true;

      if (!withinGrace) {
        return const TrialStatus(
          blocked: true,
          reason: TrialBlockReason.unverifiable,
          daysRemaining: 0,
          fromCache: true,
        );
      }

      var daysRemaining = 0;
      final installedAtMs = prefs.getInt(_kCachedInstalledAtMs);
      if (!cachedBlocked && installedAtMs != null) {
        final installedAt = DateTime.fromMillisecondsSinceEpoch(installedAtMs);
        final elapsed = DateTime.now().difference(installedAt).inDays;
        daysRemaining = (_defaultTrialDays - elapsed).clamp(0, _defaultTrialDays);
      }

      return TrialStatus(
        blocked: cachedBlocked,
        reason: cachedBlocked ? reason : TrialBlockReason.none,
        daysRemaining: daysRemaining,
        fromCache: true,
      );
    } catch (e) {
      debugPrint('TrialService: cache read failed — $e');
      return const TrialStatus(
        blocked: true,
        reason: TrialBlockReason.unverifiable,
        daysRemaining: 0,
        fromCache: false,
      );
    }
  }
}
