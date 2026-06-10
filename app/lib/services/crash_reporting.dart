import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import '../models/capture_session.dart';

/// Thin Crashlytics helpers — non-fatal breadcrumbs for ops debugging.
class CrashReporting {
  CrashReporting._();

  static bool get _active => Firebase.apps.isNotEmpty;

  static Future<void> setCaptureContext({
    required CaptureMode mode,
    String? orderId,
    String? phase,
  }) async {
    if (!_active) return;
    try {
      await FirebaseCrashlytics.instance.setCustomKey('capture_mode', mode.name);
      if (orderId != null) {
        await FirebaseCrashlytics.instance.setCustomKey('order_id', orderId);
      }
      if (phase != null) {
        await FirebaseCrashlytics.instance.setCustomKey('capture_phase', phase);
      }
    } catch (e) {
      debugPrint('CrashReporting.setCaptureContext: $e');
    }
  }

  static Future<void> recordNonFatal(
    Object error,
    StackTrace stack, {
    String? reason,
    bool fatal = false,
  }) async {
    if (!_active) return;
    try {
      await FirebaseCrashlytics.instance.recordError(
        error,
        stack,
        reason: reason,
        fatal: fatal,
      );
    } catch (e) {
      debugPrint('CrashReporting.recordNonFatal: $e');
    }
  }
}
