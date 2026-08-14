import 'package:camera/camera.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/capture_session.dart';

class CameraSettingsService {
  // --- Storage Path ---
  static const String storageDefault = '/storage/emulated/0/Movies/RepairFully';

  // All storage path options for UI
  static const List<Map<String, String>> storageOptions = [
    {'id': storageDefault, 'label': 'Storage Location', 'description': 'Tap to select folder'},
  ];

  // --- Resolution ---
  static Future<ResolutionPreset> getResolution() async {
    final prefs = await SharedPreferences.getInstance();
    final name = prefs.getString('camera_resolution') ?? 'veryHigh';
    return _parseResolution(name);
  }

  static Future<void> setResolution(ResolutionPreset preset) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('camera_resolution', preset.name);
  }

  // --- FPS ---
  static Future<int> getFps() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('camera_fps') ?? 60;
  }

  static Future<void> setFps(int fps) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('camera_fps', fps);
  }

  // --- Audio (microphone) ---
  static Future<bool> getAudio() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('audio') ?? true;
  }

  static Future<void> setAudio(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('audio', val);
  }

  // --- Mic default for PK/RT sessions (Phase 2: default OFF) ---
  static Future<bool> getMicDefault() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('mic_default') ?? false; // default OFF per spec
  }

  static Future<void> setMicDefault(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('mic_default', val);
  }

  // --- Shutter/Record sounds ---
  static Future<bool> getSound() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('sound') ?? true;
  }

  static Future<void> setSound(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('sound', val);
  }

  // --- Timestamp on images ---
  static Future<bool> getTimestampImage() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('timestamp_image') ?? false;
  }

  static Future<void> setTimestampImage(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('timestamp_image', val);
  }

  // --- File prefix (kept in SharedPreferences for backward compat, but no UI) ---
  static Future<String?> getPrefixOption() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('pref_option');
  }

  static Future<void> setPrefixOption(String? val) async {
    final prefs = await SharedPreferences.getInstance();
    if (val == null) {
      await prefs.remove('pref_option');
    } else {
      await prefs.setString('pref_option', val);
    }
  }

  // --- Label scan popup: periodic auto-scan while camera preview is live ---
  static Future<bool> getAutoLabelScan() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('auto_label_scan') ?? false;
  }

  static Future<void> setAutoLabelScan(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_label_scan', val);
  }

  // --- Auto label scan, PER MODE. Falls back to the legacy global toggle
  // above when a mode hasn't been explicitly set, same migration-seed
  // pattern as aspect ratio's per-mode getter — the legacy key stays
  // read-only, never written to by the per-mode setter below.
  static String _autoScanModeKey(CaptureMode mode) =>
      mode == CaptureMode.pk ? 'auto_label_scan_pk' : 'auto_label_scan_rt';

  static Future<bool> getAutoLabelScanForMode(CaptureMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    final key = _autoScanModeKey(mode);
    if (prefs.containsKey(key)) return prefs.getBool(key) ?? false;
    return getAutoLabelScan();
  }

  static Future<void> setAutoLabelScanForMode(CaptureMode mode, bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_autoScanModeKey(mode), val);
  }

  // --- Delay before auto-scan fires (was hardcoded 900ms) ---
  static Future<int> getAutoScanDelayMs() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('auto_scan_delay_ms') ?? 900;
  }

  static Future<void> setAutoScanDelayMs(int ms) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('auto_scan_delay_ms', ms);
  }

  // --- Label scan popup: auto-pop SAVE when Order ID + AWB lock ---
  static Future<bool> getAutoLabelSave() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('auto_label_save') ?? true;
  }

  static Future<void> setAutoLabelSave(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_label_save', val);
  }

  // --- RT claim photos: use Photo Countdown setting (was always-on pre v1.0.3+4) ---
  static Future<bool> getClaimPhotoCountdown() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('claim_photo_countdown') ?? false;
  }

  static Future<void> setClaimPhotoCountdown(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('claim_photo_countdown', val);
  }

  // --- Capture countdown seconds (0 = manual capture; 3/5/10 = countdown) ---
  static Future<int> getCaptureCountdown() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('capture_countdown') ?? 3;
  }

  static Future<void> setCaptureCountdown(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('capture_countdown', seconds);
  }

  // --- Aspect ratio default (stored as width/height of portrait ratio) ---
  //   9/16 = 16:9 portrait (full screen)   ← default
  //   3/4  = 3:4 portrait
  //   1.0  = 1:1 square
  static const double aspectFull = 9 / 16;
  static const double aspect34 = 3 / 4;
  static const double aspect11 = 1.0;

  /// Snap stored prefs to one of the three supported ratios (float drift safe).
  static double normalizeAspect(double ratio) {
    if ((ratio - aspect11).abs() < 0.02) return aspect11;
    if ((ratio - aspect34).abs() < 0.02) return aspect34;
    return aspectFull;
  }

  static Future<double> getAspectDefault() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getDouble('aspect_default') ?? aspectFull;
    return normalizeAspect(raw);
  }

  static Future<void> setAspectDefault(double ratio) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('aspect_default', normalizeAspect(ratio));
  }

  // --- Aspect ratio default, PER MODE (PK vs RT). Falls back to the legacy
  // global `aspect_default` key when this mode hasn't been explicitly set,
  // so upgrading users keep their previous single choice instead of a
  // silent revert to 16:9. The legacy key is kept read-only as a migration
  // seed — it is never written to by the per-mode setter below.
  static String _aspectModeKey(CaptureMode mode) =>
      mode == CaptureMode.pk ? 'aspect_default_pk' : 'aspect_default_rt';

  static Future<double> getAspectDefaultForMode(CaptureMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getDouble(_aspectModeKey(mode));
    if (raw != null) return normalizeAspect(raw);
    return getAspectDefault();
  }

  static Future<void> setAspectDefaultForMode(CaptureMode mode, double ratio) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_aspectModeKey(mode), normalizeAspect(ratio));
  }

  // --- Zoom default, PER MODE. Index matches LiveCaptureScreen._zoomLevels
  // (0=1x, 1=2x, 2=3x). No legacy key — default is 0 (1x).
  static String _zoomModeKey(CaptureMode mode) =>
      mode == CaptureMode.pk ? 'zoom_default_pk' : 'zoom_default_rt';

  static Future<int> getZoomDefaultForMode(CaptureMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getInt(_zoomModeKey(mode)) ?? 0).clamp(0, 2);
  }

  static Future<void> setZoomDefaultForMode(CaptureMode mode, int index) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_zoomModeKey(mode), index.clamp(0, 2));
  }

  // --- Label popup: hold captured still on screen before auto-confirming.
  //   0 = disabled (old instant-save behavior).
  static Future<int> getLabelReviewHoldSeconds() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('label_review_hold_seconds') ?? 3;
  }

  static Future<void> setLabelReviewHoldSeconds(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('label_review_hold_seconds', seconds);
  }

  // --- Restore all defaults ---
  static Future<void> restoreDefaults() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('camera_resolution');
    await prefs.remove('camera_fps');
    await prefs.remove('audio');
    await prefs.remove('sound');
    await prefs.remove('timestamp_image');
    await prefs.remove('aspect');
    await prefs.remove('pref_option');
    await prefs.remove('mic_default');
    await prefs.remove('storage_path');
    await prefs.remove('use_custom_storage');
    await prefs.remove('capture_countdown');
    await prefs.remove('aspect_default');
    await prefs.remove('aspect_default_pk');
    await prefs.remove('aspect_default_rt');
    await prefs.remove('zoom_default_pk');
    await prefs.remove('zoom_default_rt');
    await prefs.remove('label_review_hold_seconds');
    await prefs.remove('auto_label_scan');
    await prefs.remove('auto_label_scan_pk');
    await prefs.remove('auto_label_scan_rt');
    await prefs.remove('auto_scan_delay_ms');
    await prefs.remove('auto_label_save');
    await prefs.remove('claim_photo_countdown');
    await prefs.remove('mandatory_return_images');
  }

  // --- Storage Path ---
  static Future<String> getStoragePath() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('storage_path') ?? storageDefault;
  }

  static Future<void> setStoragePath(String path) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('storage_path', path);
  }

  static Future<bool> getUseCustomStoragePath() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('use_custom_storage') ?? false;
  }

  static Future<void> setUseCustomStoragePath(bool val) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('use_custom_storage', val);
  }

  static ResolutionPreset _parseResolution(String name) {
    switch (name) {
      case 'low': return ResolutionPreset.low;
      case 'medium': return ResolutionPreset.medium;
      case 'high': return ResolutionPreset.high;
      case 'veryHigh': return ResolutionPreset.veryHigh;
      case 'ultraHigh': return ResolutionPreset.ultraHigh;
      default: return ResolutionPreset.veryHigh;
    }
  }
}
