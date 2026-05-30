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

  /// Folder name = order ID (no path separator).
  /// Actual path built by LocalStorageService.
  static String orderFolderName(String orderId) => orderId;
}