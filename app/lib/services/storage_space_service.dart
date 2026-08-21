import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Free-space probe for the volume recordings land on.
///
/// Why this exists: the camera plugin records into Android's app cache
/// directory (`File.createTempFile(..., getCacheDir())`, hardcoded — see
/// flutter/flutter#91680) and Android reclaims cache whenever the device runs
/// low on space, with no exemption for foreground apps. CameraX 1.5 also
/// aborts and deletes its own output on ERROR_INSUFFICIENT_STORAGE, an error
/// the Flutter plugin never surfaces. On 2026-08-19 that combination silently
/// destroyed two shipment videos on a phone with under 2 GB free.
///
/// Dart has no disk-free API, so the numbers come from the native side
/// (`MainActivity.freeBytes()`), which prefers
/// `StorageManager.getAllocatableBytes()` over a raw `StatFs`.
class StorageSpaceService {
  StorageSpaceService._();

  static const _channel = MethodChannel('com.repairfully.camera/storage');

  /// Below this, recording is refused outright. A 4K/60 clip plus the copy
  /// out of cache needs real headroom, and Android starts evicting caches
  /// well before the disk is actually full.
  static const int blockBytes = 1500 * 1024 * 1024;  // 1.5 GB

  /// Below this, recording proceeds but the user is warned.
  static const int warnBytes = 3000 * 1024 * 1024;   // 3 GB

  /// Usable free bytes, or -1 when unknown.
  ///
  /// Returns -1 rather than throwing on any failure — including
  /// [MissingPluginException], which is what an older installed APK gives
  /// when this Dart code arrives ahead of the native half via a Shorebird
  /// patch. Callers must treat -1 as "allow": a broken probe should never
  /// stop Sir from recording a shipment.
  static Future<int> freeBytes() async {
    try {
      final v = await _channel.invokeMethod<Object?>('freeBytes');
      if (v is int) return v;
      if (v is num) return v.toInt();
      return -1;
    } on MissingPluginException {
      return -1;
    } catch (e) {
      debugPrint('StorageSpaceService.freeBytes failed — $e');
      return -1;
    }
  }

  /// True when [free] is a known value under [blockBytes].
  static bool isCritical(int free) => free >= 0 && free < blockBytes;

  /// True when [free] is a known value under [warnBytes] but not critical.
  static bool isLow(int free) => free >= 0 && free < warnBytes && !isCritical(free);

  /// "1.4 GB" / "820 MB" — for user-facing messages.
  static String format(int bytes) {
    if (bytes < 0) return 'unknown';
    const mb = 1024 * 1024;
    if (bytes >= 1024 * mb) {
      return '${(bytes / (1024 * mb)).toStringAsFixed(1)} GB';
    }
    return '${(bytes / mb).round()} MB';
  }
}
