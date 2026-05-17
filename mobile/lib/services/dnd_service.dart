import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Do Not Disturb control — wraps the Android NotificationManager.setInterruptionFilter
/// API via a platform channel (see MainActivity.kt → "com.repairfully.camera/dnd").
///
/// ACCESS_NOTIFICATION_POLICY is granted by the user via a system settings
/// page (not a runtime permission prompt). Call [isPermissionGranted] first;
/// if false, call [openSettings] to send the user to that page, then re-check
/// when the user comes back.
///
/// Filter levels match Android's NotificationManager constants:
///   ALL      (1) — normal, everything allowed
///   PRIORITY (2) — only priority calls/messages, blocks notifications/sounds
///   NONE     (3) — total silence, blocks even priority interruptions
class DndService {
  static const _channel = MethodChannel('com.repairfully.camera/dnd');

  static const int filterAll = 1;
  static const int filterPriority = 2;
  static const int filterNone = 3;

  /// Has the user granted Notification Policy access to this app?
  static Future<bool> isPermissionGranted() async {
    try {
      return await _channel.invokeMethod<bool>('isPermissionGranted') ?? false;
    } catch (e) {
      debugPrint('DndService.isPermissionGranted failed: $e');
      return false;
    }
  }

  /// Open the system DND access settings page so the user can grant permission.
  /// Returns true if the page was launched. Caller should re-check permission
  /// when the user returns to the app.
  static Future<bool> openSettings() async {
    try {
      return await _channel.invokeMethod<bool>('openSettings') ?? false;
    } catch (e) {
      debugPrint('DndService.openSettings failed: $e');
      return false;
    }
  }

  /// Set the interruption filter. Returns false if permission isn't granted
  /// (silently no-ops — caller doesn't need to crash recording for this).
  static Future<bool> setFilter(int level) async {
    try {
      return await _channel.invokeMethod<bool>('setFilter', {'level': level}) ?? false;
    } catch (e) {
      debugPrint('DndService.setFilter($level) failed: $e');
      return false;
    }
  }

  /// Read the current interruption filter level. Returns null on failure.
  static Future<int?> getFilter() async {
    try {
      return await _channel.invokeMethod<int>('getFilter');
    } catch (e) {
      debugPrint('DndService.getFilter failed: $e');
      return null;
    }
  }
}
