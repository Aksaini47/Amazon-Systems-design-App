import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:image_picker/image_picker.dart';
import '../models/capture_session.dart';
import 'file_naming_service.dart';
import 'camera_settings_service.dart';
import 'sync_queue_service.dart';
import '../utils/image_processing.dart';

/// Core local storage — handles all file I/O for orders.
/// Uses configurable storage path from CameraSettingsService.
///
/// NOTE: This is used as a singleton. Cache is shared across all instances.
class LocalStorageService {
  /// Static cache - shared across all instances
  static Directory? _cachedOrdersDir;
  static String? _currentStoragePath;

  /// Clear cached directory when storage path changes.
  /// Call this when user changes storage location in settings.
  static void clearCache() {
    _cachedOrdersDir = null;
    _currentStoragePath = null;
    debugPrint('Storage cache cleared');
  }

  /// Get the base orders directory path.
  Future<Directory> _ordersDir() async {
    // Always re-read storage path from settings to ensure we use current setting
    final storagePath = await CameraSettingsService.getStoragePath();

    // Check if path changed - if so, clear cache
    if (_currentStoragePath != null && _currentStoragePath != storagePath) {
      debugPrint('Storage path changed from $_currentStoragePath to $storagePath - clearing cache');
      _cachedOrdersDir = null;
    }
    _currentStoragePath = storagePath;

    if (_cachedOrdersDir != null) return _cachedOrdersDir!;

    // Determine base path based on storage type
    // storagePath may already contain 'orders' from CameraSettingsService default
    Directory ordersDir;
    if (storagePath.endsWith('/orders') || storagePath.endsWith('\\orders')) {
      ordersDir = Directory(storagePath);
    } else {
      ordersDir = Directory('$storagePath/orders');
    }

    if (!await ordersDir.exists()) {
      await ordersDir.create(recursive: true);
    }

    _cachedOrdersDir = ordersDir;
    return _cachedOrdersDir!;
  }

  /// Get the base orders directory path for display/debugging purposes.
  Future<String> getStoragePath() async {
    final storagePath = await CameraSettingsService.getStoragePath();
    if (storagePath.endsWith('/orders') || storagePath.endsWith('\\orders')) {
      return storagePath;
    }
    return '$storagePath/orders';
  }

  /// Get or create the folder for a specific order.
  Future<Directory> getOrderFolder(String orderId) async {
    final base = await _ordersDir();
    // Sanitize orderId to prevent path traversal
    final safeOrderId = orderId.replaceAll(RegExp(r'[^\w\-.]'), '_');
    final folder = Directory('${base.path}/$safeOrderId');
    if (!await folder.exists()) await folder.create(recursive: true);
    return folder;
  }

  // ─── Crash recovery + listing + delete ─────────────────────────────────

  /// Scan the camera plugin's cache directory for orphan recording files
  /// left over from an app crash mid-recording, and migrate any valid ones
  /// to drafts/. Called once on app launch.
  /// Returns the number of files recovered.
  Future<int> recoverOrphanVideos() async {
    try {
      final tempDir = await getTemporaryDirectory();
      if (!await tempDir.exists()) return 0;
      // Camera plugin writes to subdirs like "CameraXCaptures" / direct .mp4
      final candidates = <File>[];
      for (final entity in tempDir.listSync(recursive: true, followLinks: false)) {
        if (entity is File && entity.path.toLowerCase().endsWith('.mp4')) {
          candidates.add(entity);
        }
      }
      if (candidates.isEmpty) return 0;

      final draftsDir = await getDraftsFolder();
      int recovered = 0;
      for (final file in candidates) {
        try {
          final size = await file.length();
          if (size < 50000) {
            // <50KB → almost certainly not a valid video. Delete.
            try { await file.delete(); } catch (_) {}
            continue;
          }
          final stat = await file.stat();
          String two(int v) => v.toString().padLeft(2, '0');
          final t = stat.modified;
          final stamp = '${t.year}-${two(t.month)}-${two(t.day)}_'
                        '${two(t.hour)}-${two(t.minute)}-${two(t.second)}';
          final suffix = (t.millisecondsSinceEpoch & 0xFFFFFF).toRadixString(16);
          final destPath = '${draftsDir.path}/RECOVERED_${stamp}_$suffix.mp4';
          await file.copy(destPath);
          try { await file.delete(); } catch (_) {}
          await _scanFile(destPath);
          recovered++;
          debugPrint('Recovered orphan video: ${file.path} -> $destPath');
        } catch (e) {
          debugPrint('Recovery failed for ${file.path}: $e');
        }
      }
      return recovered;
    } catch (e) {
      debugPrint('recoverOrphanVideos failed: $e');
      return 0;
    }
  }

  /// List all saved orders. Returns a list of maps with keys:
  ///   orderId, folderPath, videoPath, photoPaths, metaPath, modifiedAt, sizeBytes
  Future<List<Map<String, dynamic>>> listOrders() async {
    final ordersDir = await _ordersDir();
    if (!await ordersDir.exists()) return [];
    final out = <Map<String, dynamic>>[];
    for (final entity in ordersDir.listSync(followLinks: false)) {
      if (entity is! Directory) continue;
      final name = entity.path.split(Platform.pathSeparator).last;
      if (name == 'drafts') continue;  // skip the drafts subfolder if it lands here
      try {
        final files = entity.listSync().whereType<File>().toList();
        File? video;
        File? meta;
        final photos = <File>[];
        for (final f in files) {
          final p = f.path.toLowerCase();
          if (p.endsWith('.mp4')) { video = f; }
          else if (p.endsWith('_meta.json')) { meta = f; }
          else if (p.endsWith('.jpg') || p.endsWith('.jpeg') || p.endsWith('.png')) { photos.add(f); }
        }
        photos.sort((a, b) => a.path.compareTo(b.path));
        final stat = await entity.stat();
        int totalBytes = 0;
        for (final f in files) {
          try { totalBytes += await f.length(); } catch (_) {}
        }
        // Check for upload marker — written by UploadService.uploadSession on success
        final uploadedMarker = File('${entity.path}/.uploaded');
        final isUploaded = await uploadedMarker.exists();
        String? uploadedAt;
        if (isUploaded) {
          try { uploadedAt = await uploadedMarker.readAsString(); } catch (_) {}
        }
        out.add({
          'orderId': name,
          'folderPath': entity.path,
          'videoPath': video?.path,
          'photoPaths': photos.map((f) => f.path).toList(),
          'metaPath': meta?.path,
          'modifiedAt': stat.modified.toIso8601String(),
          'sizeBytes': totalBytes,
          'isUploaded': isUploaded,
          'uploadedAt': uploadedAt,
        });
      } catch (e) {
        debugPrint('listOrders: skipped ${entity.path} ($e)');
      }
    }
    out.sort((a, b) => (b['modifiedAt'] as String).compareTo(a['modifiedAt'] as String));
    return out;
  }

  /// List drafts (both videos and photos). Returns list of maps:
  ///   path, fileName, sizeBytes, modifiedAt, kind ('video' | 'photo')
  ///
  /// Auto-purges junk files (videos < 50KB, photos < 5KB) on the fly — these
  /// are usually leftover from too-short recordings or capture failures and
  /// have no recoverable content.
  Future<List<Map<String, dynamic>>> listDrafts() async {
    final draftsDir = await getDraftsFolder();
    if (!await draftsDir.exists()) return [];
    final out = <Map<String, dynamic>>[];
    int purged = 0;
    for (final entity in draftsDir.listSync(followLinks: false)) {
      if (entity is! File) continue;
      final p = entity.path.toLowerCase();
      final isVideo = p.endsWith('.mp4');
      final isImage = p.endsWith('.jpg') || p.endsWith('.jpeg') || p.endsWith('.png');
      if (!isVideo && !isImage) continue;
      try {
        final stat = await entity.stat();
        // Purge junk: tiny / empty files
        final minSize = isVideo ? 50000 : 5000;
        if (stat.size < minSize) {
          try { await entity.delete(); purged++; } catch (_) {}
          continue;
        }
        out.add({
          'path': entity.path,
          'fileName': entity.path.split(Platform.pathSeparator).last,
          'sizeBytes': stat.size,
          'modifiedAt': stat.modified.toIso8601String(),
          'kind': isVideo ? 'video' : 'photo',
        });
      } catch (e) {
        // Log so we don't silently lose a draft from the list — a permission
        // error or filesystem race here would otherwise be invisible.
        debugPrint('listDrafts: skipped ${entity.path} — $e');
      }
    }
    if (purged > 0) debugPrint('listDrafts: auto-purged $purged junk file(s)');
    out.sort((a, b) => (b['modifiedAt'] as String).compareTo(a['modifiedAt'] as String));
    return out;
  }

  /// Delete an entire order folder AND remove any matching entry from the
  /// upload queue. Otherwise the home-screen banner would keep showing a
  /// stale "pending upload" for an order whose files no longer exist on disk.
  Future<bool> deleteOrder(String orderId) async {
    try {
      // Always drop from queue first — even if folder delete fails, the queue
      // entry would be useless anyway (uploadFromFolder would error on the
      // missing folder).
      await SyncQueueService.remove(orderId);

      final folder = await getOrderFolder(orderId);
      if (await folder.exists()) {
        await folder.delete(recursive: true);
        return true;
      }
      return false;
    } catch (e) {
      debugPrint('deleteOrder failed: $e');
      return false;
    }
  }

  /// Delete a single draft file.
  Future<bool> deleteDraft(String draftPath) async {
    try {
      final f = File(draftPath);
      if (await f.exists()) { await f.delete(); return true; }
      return false;
    } catch (e) {
      debugPrint('deleteDraft failed: $e');
      return false;
    }
  }

  // ─── Drafts ─────────────────────────────────────────────────────────────

  /// Get or create the drafts folder (sibling of orders/).
  /// Drafts are videos saved before an order ID is assigned — protects
  /// against video loss when user cancels mid-save-flow.
  Future<Directory> getDraftsFolder() async {
    final ordersDir = await _ordersDir();
    final draftsDir = Directory('${ordersDir.parent.path}/drafts');
    if (!await draftsDir.exists()) await draftsDir.create(recursive: true);
    return draftsDir;
  }

  /// Save video to drafts folder immediately. Used in _stopRecording() — the
  /// video file is preserved here even if the user cancels the save flow.
  /// Returns the draft file path. Later, _saveSession() calls
  /// [promoteDraftVideo] to move it to the proper order folder.
  Future<String> saveDraftVideo(XFile videoFile, CaptureMode mode) async {
    final draftsDir = await getDraftsFolder();
    final ts = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    final stamp = '${ts.year}-${two(ts.month)}-${two(ts.day)}_'
                  '${two(ts.hour)}-${two(ts.minute)}-${two(ts.second)}';
    final suffix = (ts.millisecondsSinceEpoch & 0xFFFFFF).toRadixString(16);
    final fileName = '${mode.name.toUpperCase()}_DRAFT_${stamp}_$suffix.mp4';
    final destPath = '${draftsDir.path}/$fileName';

    await videoFile.saveTo(destPath);
    final dest = File(destPath);
    if (!await dest.exists()) {
      throw Exception('Draft video was not created: $destPath');
    }
    final size = await dest.length();
    debugPrint('Draft video saved: $destPath (${_formatBytes(size)})');
    await _scanFile(destPath);
    return destPath;
  }

  /// Save a photo to drafts/ folder. Used for photos captured BEFORE the
  /// order ID is known (e.g. PK mode front/back shots before video starts).
  /// Returns the draft photo path. Promoted later via [promoteDraftPhoto].
  Future<String> saveDraftPhoto(File sourceFile, CaptureMode mode, PhotoSide side) async {
    final draftsDir = await getDraftsFolder();
    final ts = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    final stamp = '${ts.year}-${two(ts.month)}-${two(ts.day)}_'
                  '${two(ts.hour)}-${two(ts.minute)}-${two(ts.second)}';
    final suffix = (ts.millisecondsSinceEpoch & 0xFFFFFF).toRadixString(16);
    final fileName = '${mode.name.toUpperCase()}_DRAFT_${side.name}_${stamp}_$suffix.jpg';
    final destPath = '${draftsDir.path}/$fileName';

    await sourceFile.copy(destPath);
    final dest = File(destPath);
    if (!await dest.exists()) {
      throw Exception('Draft photo was not created: $destPath');
    }
    await _scanFile(destPath);
    return destPath;
  }

  /// Promote a draft photo to its final order folder. Uses rename when
  /// possible; falls back to copy+delete across volumes.
  Future<String> promoteDraftPhoto(String draftPath, String orderId, CaptureMode mode, PhotoSide side) async {
    final folder = await getOrderFolder(orderId);
    final fileName = FileNamingService.photoFileName(orderId, mode, side);
    final destPath = '${folder.path}/$fileName';

    final draftFile = File(draftPath);
    if (!await draftFile.exists()) {
      throw Exception('Draft photo missing: $draftPath');
    }

    try {
      await draftFile.rename(destPath);
    } catch (_) {
      await draftFile.copy(destPath);
      try { await draftFile.delete(); } catch (_) {}
    }
    await _scanFile(destPath);
    return destPath;
  }

  /// Promote a draft video to its final order folder. Uses rename when
  /// same-filesystem (fast, atomic) and falls back to copy+delete across
  /// volumes. The draft file is removed on success.
  Future<String> promoteDraftVideo(String draftPath, String orderId, CaptureMode mode) async {
    final folder = await getOrderFolder(orderId);
    final fileName = FileNamingService.videoFileName(orderId, mode);
    final destPath = '${folder.path}/$fileName';

    final draftFile = File(draftPath);
    if (!await draftFile.exists()) {
      throw Exception('Draft video missing: $draftPath');
    }

    try {
      await draftFile.rename(destPath);
    } catch (_) {
      // Cross-volume rename failed — copy then delete
      await draftFile.copy(destPath);
      try { await draftFile.delete(); } catch (_) {}
    }
    await _scanFile(destPath);
    debugPrint('Draft promoted to order: $draftPath → $destPath');
    return destPath;
  }

  // ─── Video ──────────────────────────────────────────────────────────────

  /// Save video file to order folder. Returns the saved file path.
  /// Uses XFile.saveTo() for reliable copy (works on all Android versions).
  Future<String> saveVideo(String orderId, XFile videoFile, CaptureMode mode) async {
    final folder = await getOrderFolder(orderId);
    final fileName = FileNamingService.videoFileName(orderId, mode);
    final destPath = '${folder.path}/$fileName';

    try {
      // Use XFile.saveTo() - the reliable method that works on all Android versions
      // This bypasses permission issues that readAsBytes/writeAsBytes have
      await videoFile.saveTo(destPath);

      final dest = File(destPath);

      // Verify copy succeeded
      if (!await dest.exists()) {
        throw Exception('Destination file was not created: $destPath');
      }

      final size = await dest.length();
      debugPrint('Video saved: $destPath (${_formatBytes(size)})');

      // Refresh MediaStore so file appears in Files app
      await _scanFile(destPath);

      return destPath;
    } catch (e) {
      throw Exception('Failed to save video: $e');
    }
  }

  // ─── Photos ───────────────────────────────────────────────────────────

  /// Save a photo file. Returns the saved file path.
  /// Uses XFile.saveTo() for reliable copy.
  /// Applies timestamp watermark with order ID and datetime (always, no setting toggle).
  Future<String> savePhoto(
    String orderId,
    XFile photoFile,
    CaptureMode mode,
    PhotoSide side,
  ) async {
    final folder = await getOrderFolder(orderId);
    final fileName = FileNamingService.photoFileName(orderId, mode, side);
    final destPath = '${folder.path}/$fileName';

    try {
      // Apply watermark only if user has Photo Timestamp setting enabled
      var fileToSave = photoFile;
      final prefix = mode == CaptureMode.pk ? 'PK' : 'RT';
      final addTimestamp = await CameraSettingsService.getTimestampImage();
      final watermarked = await ImageProcessingUtils.processPhoto(
        File(photoFile.path),
        orientation: CustomOrientation.portraitUp,
        addTimestamp: addTimestamp,
        prefix: '$prefix-$orderId',
      );
      // Write watermarked bytes to dest directly to preserve watermark
      await watermarked.readAsBytes().then(
        (bytes) => File(destPath).writeAsBytes(bytes),
      );
      final dest = File(destPath);
      if (!await dest.exists()) {
        throw Exception('Destination photo was not created: $destPath');
      }
      final size = await dest.length();
      debugPrint('Photo saved with watermark: $destPath (${_formatBytes(size)})');
      await _scanFile(destPath);
      return destPath;
    } catch (e) {
      throw Exception('Failed to save photo: $e');
    }
  }

  // ─── MediaScan ─────────────────────────────────────────────────────────

  /// Refresh MediaStore so file appears in Files app immediately.
  /// Uses MediaScannerConnection which properly indexes files.
  Future<void> _scanFile(String path) async {
    try {
      const channel = MethodChannel('com.repairfully.camera/media_scanner');
      await channel.invokeMethod('scanFile', {'path': path});
    } catch (e) {
      debugPrint('MediaScan failed (non-fatal): $e');
    }
  }

  /// Scan entire order directory into MediaStore
  Future<void> _scanDirectory(String dirPath) async {
    try {
      const channel = MethodChannel('com.repairfully.camera/media_scanner');
      await channel.invokeMethod('scanDirectory', {'dir': dirPath});
    } catch (e) {
      debugPrint('Directory scan failed (non-fatal): $e');
    }
  }

  // ─── meta.json ─────────────────────────────────────────────────────────

  /// Write session data to order's meta.json.
  Future<void> writeMetaJson(CaptureSession session) async {
    if (session.orderId == null) return;
    final folder = await getOrderFolder(session.orderId!);
    final file = File('${folder.path}/${FileNamingService.metaFileName(session.orderId!)}');

    Map<String, dynamic> existing = {};
    // Safely read existing meta.json
    try {
      if (await file.exists()) {
        final content = await file.readAsString();
        existing = jsonDecode(content) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('Could not read existing meta.json: $e');
    }

    final merged = _mergeSession(existing, session);
    final encoder = const JsonEncoder.withIndent('  ');

    // Safely write meta.json with fallback
    try {
      await file.writeAsString(encoder.convert(merged), flush: true);
      debugPrint('Meta saved: ${file.path}');
    } catch (e) {
      debugPrint('Failed to write meta.json: $e');
      // Try cache fallback
      try {
        final cacheFile = File('${(await getTemporaryDirectory()).path}/meta_backup.json');
        await cacheFile.writeAsString(encoder.convert(merged));
        debugPrint('Meta saved to cache: ${cacheFile.path}');
      } catch (e2) {
        debugPrint('Cache fallback also failed: $e2');
      }
    }
  }

  /// Read existing meta.json. Returns null if not found OR if the file is
  /// corrupt (logs the corruption so it surfaces in debug builds — silent
  /// nulls hide bugs that take days to track).
  Future<Map<String, dynamic>?> readMetaJson(String orderId) async {
    final folder = await getOrderFolder(orderId);
    final file = File('${folder.path}/${FileNamingService.metaFileName(orderId)}');
    if (!await file.exists()) return null;
    try {
      final content = await file.readAsString();
      return jsonDecode(content) as Map<String, dynamic>;
    } catch (e) {
      debugPrint('readMetaJson: corrupt meta for $orderId — $e');
      return null;
    }
  }

  /// Merge partial session into existing meta.
  Map<String, dynamic> _mergeSession(Map<String, dynamic> existing, CaptureSession session) {
    final mode = session.mode.name.toUpperCase();

    final merged = Map<String, dynamic>.from(existing);
    merged['order_id'] = session.orderId ?? existing['order_id'];
    merged['awb'] = session.awb ?? existing['awb'];
    merged['mode'] = mode;
    merged['session_started_at'] = session.sessionStartedAt.toIso8601String();
    merged['app_version'] = '1.0.0';

    if (session.videoPath != null) {
      merged['video'] = {
        'started_at': session.videoStartedAt?.toIso8601String(),
        'stopped_at': session.videoStoppedAt?.toIso8601String(),
        'duration_seconds': session.videoDurationSeconds,
        'file': session.videoPath,
        'mode': mode,
      };
    }

    final photos = Map<String, dynamic>.from(existing['photos'] as Map<String, dynamic>? ?? {});
    photos[mode.toLowerCase()] = {
      if (session.frontPhotoPath != null)
        'front': {'captured_at': DateTime.now().toIso8601String(), 'file': session.frontPhotoPath},
      if (session.backPhotoPath != null)
        'back': {'captured_at': DateTime.now().toIso8601String(), 'file': session.backPhotoPath},
      if (session.labelPhotoPath != null)
        'label': {'captured_at': DateTime.now().toIso8601String(), 'file': session.labelPhotoPath},
      if (session.serialPhotoPath != null)
        'serial': {'captured_at': DateTime.now().toIso8601String(), 'file': session.serialPhotoPath},
    };
    merged['photos'] = photos;

    if (session.verdict != null) {
      merged['verdict'] = session.verdict!.name;
      merged['claim_trigger'] = session.verdict == QCVerdict.damaged || session.verdict == QCVerdict.different;
    }

    if (session.productTitle != null) {
      merged['product_title'] = session.productTitle;
    }

    return merged;
  }

  // ─── Query ─────────────────────────────────────────────────────────────

  Future<List<String>> listOrderIds() async {
    final base = await _ordersDir();
    final entries = await base.list().toList();
    return entries
        .whereType<Directory>()
        .map((d) => d.path.split(Platform.pathSeparator).last)
        .where((name) => name.contains('-'))
        .toList();
  }

  Future<List<FileSystemEntity>> getOrderFiles(String orderId) async {
    final folder = await getOrderFolder(orderId);
    return folder.listSync();
  }

  Future<bool> orderFolderExists(String orderId) async {
    final base = await _ordersDir();
    final folder = Directory('${base.path}/$orderId');
    return folder.exists();
  }

  /// Format bytes to human readable string
  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}