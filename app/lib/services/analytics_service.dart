import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/capture_session.dart';
import 'update_service.dart';

/// Fire-and-forget mirror of app events into Firestore, so every action can
/// be inspected centrally (Firebase console, or queried directly) instead of
/// only living in each phone's local activity-log text file.
///
/// Reuses the same device anchor as TrialService — Settings.Secure.ANDROID_ID
/// via the native `com.repairfully.camera/device_id` channel — so events
/// from one physical phone group under one doc regardless of app reinstall.
/// Writes to `device_events/{androidId}/events/{autoId}`.
///
/// Never throws and never blocks a caller: every failure (no network, no
/// Firebase, channel missing on an older installed APK) is swallowed here,
/// same fire-and-forget philosophy as ActivityLogService. This must never be
/// able to slow down or interrupt a capture in progress.
class AnalyticsService {
  AnalyticsService._();

  static const _deviceIdChannel =
      MethodChannel('com.repairfully.camera/device_id');
  static const _collection = 'device_events';

  static String? _cachedDeviceId;
  static int? _cachedPatchNumber;
  static bool _patchNumberChecked = false;

  static Future<String?> _deviceId() async {
    if (_cachedDeviceId != null) return _cachedDeviceId;
    try {
      _cachedDeviceId =
          await _deviceIdChannel.invokeMethod<String>('getAndroidId');
    } catch (e) {
      debugPrint('AnalyticsService: getAndroidId failed — $e');
    }
    return _cachedDeviceId;
  }

  // Patch number changes only on relaunch, so one lookup per app run (not
  // per event) is enough — avoids a platform-channel round trip per event.
  static Future<int?> _patchNumber() async {
    if (_patchNumberChecked) return _cachedPatchNumber;
    _patchNumberChecked = true;
    try {
      _cachedPatchNumber = await UpdateService.currentPatchNumber();
    } catch (e) {
      debugPrint('AnalyticsService: currentPatchNumber failed — $e');
    }
    return _cachedPatchNumber;
  }

  /// Record one event. Safe to call unawaited from anywhere — including hot
  /// paths like barcode detection — since every step is wrapped and nothing
  /// here can throw back into the caller.
  static Future<void> record({
    required String event,
    String? mode,
    String? orderId,
    String? awb,
    String? qc,
    String? qcSub,
    Map<String, String>? extra,
  }) async {
    if (Firebase.apps.isEmpty) return;
    try {
      final deviceId = await _deviceId();
      if (deviceId == null || deviceId.isEmpty) return;
      final patch = await _patchNumber();

      await FirebaseFirestore.instance
          .collection(_collection)
          .doc(deviceId)
          .collection('events')
          .add({
        'ts': FieldValue.serverTimestamp(),
        'client_ts': DateTime.now().toIso8601String(),
        'event': event,
        if (mode != null && mode.isNotEmpty) 'mode': mode,
        if (orderId != null && orderId.isNotEmpty) 'order_id': orderId,
        if (awb != null && awb.isNotEmpty) 'awb': awb,
        if (qc != null && qc.isNotEmpty) 'qc': qc,
        if (qcSub != null && qcSub.isNotEmpty) 'qc_sub': qcSub,
        'app_version': CaptureSession.appVersion,
        if (patch != null) 'patch_number': patch,
        if (extra != null && extra.isNotEmpty) 'extra': extra,
      });
    } catch (e) {
      debugPrint('AnalyticsService: record failed — $e');
    }
  }
}
