import '../models/capture_session.dart';

/// Pure utility — all filename patterns in one place.
/// Never does I/O, never has side effects.
class FileNamingService {
  /// e.g. "407-1234567-1234567_PK.mp4"
  static String videoFileName(String orderId, CaptureMode mode) {
    return '${orderId}_${mode.name.toUpperCase()}.mp4';
  }

  /// e.g. "407-1234567-1234567_PK_front.jpg"
  static String photoFileName(String orderId, CaptureMode mode, PhotoSide side) {
    return '${orderId}_${mode.name.toUpperCase()}_${side.name}.jpg';
  }

  /// e.g. "407-1234567-1234567_meta.json"
  static String metaFileName(String orderId) {
    return '${orderId}_meta.json';
  }

  /// e.g. "407-1234567-1234567_compare.jpg" (Phase 3)
  static String compareFileName(String orderId) {
    return '${orderId}_compare.jpg';
  }

  /// Folder name = order ID + mode suffix so PK and RT for the same order
  /// never collide (e.g. `407-1234567-1234567-RT`).
  static String orderFolderName(String orderId, CaptureMode mode) {
    final safe = orderId.replaceAll(RegExp(r'[^\w\-.]'), '_');
    return '$safe-${mode.name.toUpperCase()}';
  }

  /// Bare Amazon order ID stripped from a storage folder name.
  static String bareOrderIdFromFolder(String folderName) {
    if (folderName.endsWith('-PK')) {
      return folderName.substring(0, folderName.length - 3);
    }
    if (folderName.endsWith('-RT')) {
      return folderName.substring(0, folderName.length - 3);
    }
    return folderName;
  }

  static CaptureMode? modeFromFolder(String folderName) {
    if (folderName.endsWith('-PK')) return CaptureMode.pk;
    if (folderName.endsWith('-RT')) return CaptureMode.rt;
    return null;
  }
}