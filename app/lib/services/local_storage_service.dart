import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:image_picker/image_picker.dart';
import '../models/capture_session.dart';
import '../utils/debug_session_log.dart';
import 'file_naming_service.dart';
import 'camera_settings_service.dart';
import 'activity_log_service.dart';
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

  /// Get or create the folder for a specific order — WRITE paths only.
  ///
  /// With [mode]: creates `{orderId}-PK` or `{orderId}-RT`.
  /// Without [mode]: [orderId] is treated as the on-disk folder key (gallery /
  /// delete paths that already include the suffix).
  Future<Directory> getOrderFolder(String orderId, {CaptureMode? mode}) async {
    final folder = await _orderFolderRef(orderId, mode: mode);
    if (!await folder.exists()) await folder.create(recursive: true);
    return folder;
  }

  /// Locate an order folder without creating it — READ paths. Returns null
  /// when absent so existence checks stay meaningful.
  Future<Directory?> findOrderFolder(String orderId, {CaptureMode? mode}) async {
    final folder = await _orderFolderRef(orderId, mode: mode);
    return await folder.exists() ? folder : null;
  }

  Future<Directory> _orderFolderRef(String orderId, {CaptureMode? mode}) async {
    final base = await _ordersDir();
    final folderName = mode != null
        ? FileNamingService.orderFolderName(orderId, mode)
        : orderId.replaceAll(RegExp(r'[^\w\-.]'), '_');
    return Directory('${base.path}/$folderName');
  }

  // ─── Crash recovery + listing + delete ─────────────────────────────────

  /// True while the capture screen holds a live recording. The camera
  /// plugin records straight into the app cache dir that
  /// [recoverOrphanVideos] sweeps, so without this flag a sweep that
  /// happens to run mid-recording would copy-and-DELETE the file CameraX
  /// is still writing. The writer's fd stays valid on an unlinked inode,
  /// so the recording appears to succeed and only fails minutes later when
  /// saveDraftVideo() cannot find the path — indistinguishable from the
  /// 2026-08-19 storage-eviction crash. Set by _startRecording/_stopRecording.
  static bool recordingInFlight = false;

  /// A recording still being finalised must never be treated as an orphan.
  /// CameraX flushes the moov atom after its stop Future resolves, so a
  /// file touched seconds ago may be a live capture, not crash debris.
  static const _orphanMinAge = Duration(minutes: 2);

  /// Scan the camera plugin's cache directory for orphan recording files
  /// left over from an app crash mid-recording, and migrate any valid ones
  /// to drafts/. Called once on app launch.
  /// Returns the number of files recovered.
  Future<int> recoverOrphanVideos() async {
    // Never race a live recording — see [recordingInFlight].
    if (recordingInFlight) {
      debugPrint('recoverOrphanVideos: skipped — recording in flight');
      return 0;
    }
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
      final now = DateTime.now();
      for (final file in candidates) {
        try {
          if (recordingInFlight) break;  // a recording started mid-sweep
          final age = now.difference((await file.stat()).modified);
          if (age < _orphanMinAge) {
            debugPrint('Skipping ${file.path} — only ${age.inSeconds}s old, may be live');
            continue;
          }
          final size = await file.length();
          if (size < 50000) {
            // <50KB → almost certainly not a valid video. Only now that the
            // age gate above proves it is not mid-flush is deleting safe;
            // a single small read on a live file is NOT proof of failure
            // (the lesson of the 2026-07-24 video-loss fix, which was
            // applied to _stopRecording but never backported here).
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

  /// Last-ditch rescue for a recording whose plugin-reported path could not
  /// be copied. Returns the new draft path, or null if nothing was found.
  ///
  /// Two real failure modes make this worth trying rather than giving up:
  ///   * The camera plugin never clears its `videoOutputPath` after a stop
  ///     and silently no-ops `startVideoCapturing` when its `recording`
  ///     field is stale, so the path handed back can belong to an EARLIER
  ///     capture while this capture's file sits in cache under a different
  ///     REC* name — perfectly intact, just unreferenced.
  ///   * A partially-flushed file may be readable even when the exact
  ///     reported path is not.
  ///
  /// Unlike [recoverOrphanVideos] this inverts the age gate — it takes the
  /// NEWEST file, because we are looking for the recording that just ended.
  /// [notBefore] must be the moment the capture started: anything older
  /// belongs to a different capture and attaching it to this order would be
  /// worse than reporting the loss. It copies without deleting: if the guess
  /// is wrong the original is still there for the next boot sweep.
  Future<String?> salvageOrphanRecording(
    CaptureMode mode, {
    required DateTime notBefore,
  }) async {
    try {
      final tempDir = await getTemporaryDirectory();
      if (!await tempDir.exists()) return null;
      File? best;
      DateTime? bestAt;
      for (final entity in tempDir.listSync(recursive: true, followLinks: false)) {
        if (entity is! File) continue;
        if (!entity.path.toLowerCase().endsWith('.mp4')) continue;
        try {
          if (await entity.length() < 50000) continue;
          final at = (await entity.stat()).modified;
          // Only files written by the capture that just finished.
          if (at.isBefore(notBefore)) continue;
          if (bestAt == null || at.isAfter(bestAt)) {
            best = entity;
            bestAt = at;
          }
        } catch (_) {/* unreadable — skip */}
      }
      if (best == null) return null;

      final draftsDir = await getDraftsFolder();
      String two(int v) => v.toString().padLeft(2, '0');
      final t = bestAt!;
      final stamp = '${t.year}-${two(t.month)}-${two(t.day)}_'
                    '${two(t.hour)}-${two(t.minute)}-${two(t.second)}';
      final suffix = (t.millisecondsSinceEpoch & 0xFFFFFF).toRadixString(16);
      final destPath =
          '${draftsDir.path}/${mode.name.toUpperCase()}_DRAFT_${stamp}_$suffix.mp4';
      await best.copy(destPath);
      if (!await File(destPath).exists()) return null;
      await _scanFile(destPath);
      debugPrint('Salvaged recording: ${best.path} -> $destPath');
      return destPath;
    } catch (e) {
      debugPrint('salvageOrphanRecording failed: $e');
      return null;
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
        out.add({
          'orderId': name,
          'bareOrderId': FileNamingService.bareOrderIdFromFolder(name),
          'mode': FileNamingService.modeFromFolder(name)?.name,
          'folderPath': entity.path,
          'videoPath': video?.path,
          'photoPaths': photos.map((f) => f.path).toList(),
          'metaPath': meta?.path,
          'modifiedAt': stat.modified.toIso8601String(),
          'sizeBytes': totalBytes,
        });
      } catch (e) {
        debugPrint('listOrders: skipped ${entity.path} ($e)');
      }
    }
    out.sort((a, b) => (b['modifiedAt'] as String).compareTo(a['modifiedAt'] as String));
    return out;
  }

  // Junk thresholds: below these a draft has no recoverable content
  // (too-short recording / failed capture).
  static const _minVideoBytes = 50000;
  static const _minPhotoBytes = 5000;

  /// List drafts (both videos and photos) — pure read, no side effects.
  /// Junk-sized files are hidden from the list; [sweepJunkDrafts] deletes them.
  /// Returns list of maps: path, fileName, sizeBytes, modifiedAt, kind, suspect.
  ///
  /// Exception: an undersized VIDEO is still listed, flagged `suspect: true`.
  /// _stopRecording keeps such a recording on purpose and tells the user to
  /// double-check it in Drafts — hiding it here made that message a lie and
  /// left a real (if short) capture invisible until the sweep removed it.
  Future<List<Map<String, dynamic>>> listDrafts() async {
    final out = <Map<String, dynamic>>[];
    for (final (file, stat, isVideo) in await _draftFiles()) {
      final undersized = stat.size < (isVideo ? _minVideoBytes : _minPhotoBytes);
      if (undersized && !isVideo) continue;
      out.add({
        'path': file.path,
        'fileName': file.path.split(Platform.pathSeparator).last,
        'sizeBytes': stat.size,
        'modifiedAt': stat.modified.toIso8601String(),
        'kind': isVideo ? 'video' : 'photo',
        'suspect': undersized,
      });
    }
    out.sort((a, b) => (b['modifiedAt'] as String).compareTo(a['modifiedAt'] as String));
    return out;
  }

  /// Delete junk-sized drafts. Called once at boot (from HomeScreen), not
  /// from read paths. Returns the number of files deleted; failures logged.
  ///
  /// Videos get a 24h grace period on top of the size test. _stopRecording
  /// deliberately KEEPS an undersized-but-real recording ("saved to Drafts,
  /// please double-check it") rather than destroying the only copy — but
  /// this sweep runs before the Drafts list is ever shown, so without the
  /// grace period it silently deleted exactly the file the user was being
  /// asked to inspect, revoking that guarantee at the next launch.
  static const _junkVideoGrace = Duration(hours: 24);

  Future<int> sweepJunkDrafts() async {
    var purged = 0;
    final now = DateTime.now();
    for (final (file, stat, isVideo) in await _draftFiles()) {
      if (stat.size >= (isVideo ? _minVideoBytes : _minPhotoBytes)) continue;
      if (isVideo && now.difference(stat.modified) < _junkVideoGrace) {
        debugPrint('sweepJunkDrafts: keeping recent small video ${file.path}');
        continue;
      }
      try {
        await file.delete();
        purged++;
      } catch (e) {
        debugPrint('sweepJunkDrafts: could not delete ${file.path} — $e');
      }
    }
    if (purged > 0) debugPrint('sweepJunkDrafts: purged $purged junk file(s)');
    return purged;
  }

  /// Shared draft-folder scan: media files with their stat + video flag.
  /// Unreadable entries are logged and skipped so one bad file can't hide
  /// the rest of the list.
  Future<List<(File, FileStat, bool)>> _draftFiles() async {
    final draftsDir = await getDraftsFolder();
    if (!await draftsDir.exists()) return [];
    final out = <(File, FileStat, bool)>[];
    for (final entity in draftsDir.listSync(followLinks: false)) {
      if (entity is! File) continue;
      final p = entity.path.toLowerCase();
      final isVideo = p.endsWith('.mp4');
      final isImage = p.endsWith('.jpg') || p.endsWith('.jpeg') || p.endsWith('.png');
      if (!isVideo && !isImage) continue;
      try {
        out.add((entity, await entity.stat(), isVideo));
      } catch (e) {
        debugPrint('draft scan: skipped ${entity.path} — $e');
      }
    }
    return out;
  }

  /// Delete an entire order folder.
  Future<bool> deleteOrder(String orderId) async {
    try {
      // #region agent log
      final folder = await _orderFolderRef(orderId);
      final folderExistsBefore = await folder.exists();
      final pathsBefore = <String>[];
      if (folderExistsBefore) {
        for (final entity in folder.listSync(followLinks: false)) {
          if (entity is File) pathsBefore.add(entity.path);
        }
      }
      DebugSessionLog.log(
        location: 'local_storage_service.dart:deleteOrder',
        message: 'deleteOrder start',
        hypothesisId: 'H3-H4',
        data: {
          'orderId': orderId,
          'folderPath': folder.path,
          'folderExistsBefore': folderExistsBefore,
          'fileCount': pathsBefore.length,
        },
      );
      // #endregion

      if (folderExistsBefore) {
        for (final path in pathsBefore) {
          await _removeFromMediaStore(path);
        }
        await folder.delete(recursive: true);
      }

      final folderExistsAfter = await folder.exists();
      // #region agent log
      DebugSessionLog.log(
        location: 'local_storage_service.dart:deleteOrder',
        message: 'deleteOrder end',
        hypothesisId: 'H3-H4',
        data: {
          'orderId': orderId,
          'folderExistsAfter': folderExistsAfter,
          'deleted': folderExistsBefore && !folderExistsAfter,
        },
      );
      // #endregion
      return folderExistsBefore && !folderExistsAfter;
    } catch (e) {
      debugPrint('deleteOrder failed: $e');
      // #region agent log
      DebugSessionLog.log(
        location: 'local_storage_service.dart:deleteOrder',
        message: 'deleteOrder error',
        hypothesisId: 'H4',
        data: {'orderId': orderId, 'error': e.toString()},
      );
      // #endregion
      return false;
    }
  }

  /// Delete a single draft file.
  Future<bool> deleteDraft(String draftPath) async {
    try {
      final f = File(draftPath);
      final existsBefore = await f.exists();
      // #region agent log
      DebugSessionLog.log(
        location: 'local_storage_service.dart:deleteDraft',
        message: 'deleteDraft start',
        hypothesisId: 'H2-H3',
        data: {
          'draftPath': draftPath,
          'existsBefore': existsBefore,
        },
      );
      // #endregion
      if (existsBefore) {
        await _removeFromMediaStore(draftPath);
        await f.delete();
      }
      final existsAfter = await f.exists();
      // #region agent log
      DebugSessionLog.log(
        location: 'local_storage_service.dart:deleteDraft',
        message: 'deleteDraft end',
        hypothesisId: 'H2-H3',
        data: {
          'draftPath': draftPath,
          'existsAfter': existsAfter,
          'deleted': existsBefore && !existsAfter,
        },
      );
      // #endregion
      return existsBefore && !existsAfter;
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
    final folder = await getOrderFolder(orderId, mode: mode);
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
    final folder = await getOrderFolder(orderId, mode: mode);
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
    // #region agent log
    final draftStillExists = await draftFile.exists();
    DebugSessionLog.log(
      location: 'local_storage_service.dart:promoteDraftVideo',
      message: 'promoteDraftVideo complete',
      hypothesisId: 'H6',
      data: {
        'draftPath': draftPath,
        'destPath': destPath,
        'draftStillExists': draftStillExists,
      },
    );
    // #endregion
    if (draftStillExists) {
      await _removeFromMediaStore(draftPath);
      try {
        await draftFile.delete();
      } catch (_) {}
    }
    debugPrint('Draft promoted to order: $draftPath → $destPath');
    return destPath;
  }

  // ─── Video ──────────────────────────────────────────────────────────────

  /// Save video file to order folder. Returns the saved file path.
  /// Uses XFile.saveTo() for reliable copy (works on all Android versions).
  Future<String> saveVideo(String orderId, XFile videoFile, CaptureMode mode) async {
    final folder = await getOrderFolder(orderId, mode: mode);
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

  /// Save a photo into the order folder, normalising orientation and adding
  /// the order-ID/timestamp watermark IF the Photo Timestamp setting is on.
  /// Returns the saved file path.
  Future<String> savePhoto(
    String orderId,
    XFile photoFile,
    CaptureMode mode,
    PhotoSide side,
  ) async {
    final folder = await getOrderFolder(orderId, mode: mode);
    final fileName = FileNamingService.photoFileName(orderId, mode, side);
    final destPath = '${folder.path}/$fileName';

    try {
      final addTimestamp = await CameraSettingsService.getTimestampImage();
      final watermarked = await ImageProcessingUtils.processPhoto(
        File(photoFile.path),
        orientation: CustomOrientation.portraitUp,
        addTimestamp: addTimestamp,
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

  /// Remove a deleted file from Android MediaStore / Files app index.
  Future<void> _removeFromMediaStore(String path) async {
    try {
      const channel = MethodChannel('com.repairfully.camera/media_scanner');
      await channel.invokeMethod('deleteFile', {'path': path});
    } catch (e) {
      debugPrint('MediaStore delete failed (non-fatal): $e');
    }
  }

  // ─── meta.json ─────────────────────────────────────────────────────────

  /// Write session data to order's meta.json.
  Future<void> writeMetaJson(CaptureSession session) async {
    if (session.orderId == null) return;
    final folder = await getOrderFolder(session.orderId!, mode: session.mode);
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
      await ActivityLogService.log(
        event: 'meta_written',
        mode: session.mode,
        orderId: session.orderId,
        awb: session.awb,
        qc: session.verdict?.name,
        extra: {'folder': folder.path},
      );
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

  /// Read existing meta.json. [folderKey] is the on-disk folder name
  /// (e.g. `407-xxx-RT`). [bareOrderId] is the Amazon order ID used in
  /// filenames (e.g. `407-xxx`). When omitted, [folderKey] is used for both.
  Future<Map<String, dynamic>?> readMetaJson(
    String folderKey, {
    String? bareOrderId,
  }) async {
    final folder = await _orderFolderRef(folderKey);
    final metaId = bareOrderId ?? folderKey;
    final file = File('${folder.path}/${FileNamingService.metaFileName(metaId)}');
    if (!await file.exists()) return null;
    try {
      final content = await file.readAsString();
      return jsonDecode(content) as Map<String, dynamic>;
    } catch (e) {
      debugPrint('readMetaJson: corrupt meta for $folderKey — $e');
      return null;
    }
  }

  /// Rebuild a [CaptureSession] from order folder + meta.json + filesystem.
  Future<CaptureSession?> sessionFromOrderFolder({
    required String folderKey,
    required String bareOrderId,
    required CaptureMode mode,
  }) async {
    final folder = await findOrderFolder(folderKey);
    if (folder == null) return null;
    final meta = await readMetaJson(folderKey, bareOrderId: bareOrderId);

    String? videoPath;
    DateTime? videoStartedAt;
    DateTime? videoStoppedAt;
    int? videoDurationSeconds;
    if (meta?['video'] is Map) {
      final v = meta!['video'] as Map<String, dynamic>;
      videoPath = v['file'] as String?;
      if (v['started_at'] != null) {
        videoStartedAt = DateTime.tryParse(v['started_at'] as String);
      }
      if (v['stopped_at'] != null) {
        videoStoppedAt = DateTime.tryParse(v['stopped_at'] as String);
      }
      videoDurationSeconds = v['duration_seconds'] as int?;
    }
    if (videoPath == null || !await File(videoPath).exists()) {
      for (final entity in folder.listSync(followLinks: false)) {
        if (entity is File && entity.path.toLowerCase().endsWith('.mp4')) {
          videoPath = entity.path;
          break;
        }
      }
    }

    Future<String?> resolvePhoto(PhotoSide side) async {
      final modeKey = mode.name;
      final photosRoot = meta?['photos'];
      if (photosRoot is Map) {
        final modePhotos = photosRoot[modeKey] as Map<String, dynamic>?;
        final entry = modePhotos?[side.name];
        if (entry is Map) {
          final path = entry['file'] as String?;
          if (path != null && await File(path).exists()) return path;
        }
      }
      final expected = '${folder.path}/${FileNamingService.photoFileName(bareOrderId, mode, side)}';
      if (await File(expected).exists()) return expected;
      return null;
    }

    QCVerdict? verdict;
    final verdictStr = meta?['verdict'] as String?;
    if (verdictStr != null) {
      for (final v in QCVerdict.values) {
        if (v.name == verdictStr) {
          verdict = v;
          break;
        }
      }
    }

    DateTime sessionStartedAt = DateTime.now();
    if (meta?['session_started_at'] != null) {
      sessionStartedAt =
          DateTime.tryParse(meta!['session_started_at'] as String) ?? sessionStartedAt;
    }

    return CaptureSession(
      orderId: bareOrderId,
      awb: meta?['awb'] as String?,
      mode: mode,
      sessionStartedAt: sessionStartedAt,
      videoStartedAt: videoStartedAt,
      videoStoppedAt: videoStoppedAt,
      videoDurationSeconds: videoDurationSeconds,
      videoPath: videoPath,
      frontPhotoPath: await resolvePhoto(PhotoSide.front),
      backPhotoPath: await resolvePhoto(PhotoSide.back),
      labelPhotoPath: await resolvePhoto(PhotoSide.label),
      contentsPhotoPath: await resolvePhoto(PhotoSide.contents),
      serialPhotoPath: await resolvePhoto(PhotoSide.serial),
      verdict: verdict,
      productTitle: meta?['product_title'] as String?,
    );
  }

  /// Replace or remove one photo in a saved order. Rewrites meta.json.
  Future<bool> updateOrderPhoto({
    required String folderKey,
    required String bareOrderId,
    required CaptureMode mode,
    required PhotoSide side,
    XFile? newPhoto,
    bool remove = false,
  }) async {
    try {
      final session = await sessionFromOrderFolder(
        folderKey: folderKey,
        bareOrderId: bareOrderId,
        mode: mode,
      );
      if (session == null) return false;

      final oldPath = session.photoPathFor(side);
      if (remove) {
        if (oldPath != null) {
          await _removeFromMediaStore(oldPath);
          try {
            await File(oldPath).delete();
          } catch (_) {}
        }
        await writeMetaJson(session.withPhotoSide(side, null));
        return true;
      }

      if (newPhoto == null) return false;

      if (oldPath != null) {
        await _removeFromMediaStore(oldPath);
        try {
          await File(oldPath).delete();
        } catch (_) {}
      }

      final newPath = await savePhoto(bareOrderId, newPhoto, mode, side);
      await writeMetaJson(session.withPhotoSide(side, newPath));
      return true;
    } catch (e) {
      debugPrint('updateOrderPhoto failed: $e');
      return false;
    }
  }

  /// Update saved order metadata — order ID, AWB, RT QC verdict, capture
  /// timestamp. Renames folder + files when order ID changes. Returns new
  /// folder path.
  Future<String> updateOrderMetadata({
    required String folderKey,
    required String newBareOrderId,
    String? awb,
    QCVerdict? verdict,
    DateTime? newSessionStartedAt,
  }) async {
    final trimmed = newBareOrderId.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError('Order ID is required');
    }

    final mode = FileNamingService.modeFromFolder(folderKey);
    if (mode == null) {
      throw StateError('Invalid order folder: $folderKey');
    }

    final oldBareId = FileNamingService.bareOrderIdFromFolder(folderKey);
    final safeNewId = trimmed.replaceAll(RegExp(r'[^\w\-.]'), '_');
    final newFolderKey = FileNamingService.orderFolderName(trimmed, mode);

    final oldFolder = await findOrderFolder(folderKey);
    if (oldFolder == null) {
      throw StateError('Order folder not found');
    }

    if (folderKey != newFolderKey) {
      final ordersDir = await _ordersDir();
      if (Directory('${ordersDir.path}/$newFolderKey').existsSync()) {
        throw StateError('Order already exists for ${mode.name.toUpperCase()} mode');
      }
    }

    if (safeNewId != oldBareId) {
      for (final entity in oldFolder.listSync(followLinks: false)) {
        if (entity is! File) continue;
        final name = entity.path.split(Platform.pathSeparator).last;
        String? newName;
        if (name.toLowerCase().endsWith('.mp4')) {
          newName = FileNamingService.videoFileName(safeNewId, mode);
        } else if (name.endsWith('_meta.json')) {
          newName = FileNamingService.metaFileName(safeNewId);
        } else {
          for (final side in PhotoSide.values) {
            if (name.contains('_${side.name}.')) {
              newName = FileNamingService.photoFileName(safeNewId, mode, side);
              break;
            }
          }
        }
        if (newName != null && newName != name) {
          await entity.rename('${oldFolder.path}/$newName');
        }
      }
    }

    Directory targetFolder = oldFolder;
    if (folderKey != newFolderKey) {
      final ordersDir = await _ordersDir();
      final newPath = '${ordersDir.path}/$newFolderKey';
      await oldFolder.rename(newPath);
      targetFolder = Directory(newPath);
    }

    final session = await sessionFromOrderFolder(
      folderKey: newFolderKey,
      bareOrderId: safeNewId,
      mode: mode,
    );
    if (session == null) {
      throw StateError('Failed to reload order after update');
    }

    final normalizedAwb = awb?.trim();
    final previousStartedAt = session.sessionStartedAt;
    final updated = session.copyWith(
      orderId: safeNewId,
      awb: (normalizedAwb == null || normalizedAwb.isEmpty) ? null : normalizedAwb,
      verdict: mode == CaptureMode.rt ? (verdict ?? session.verdict) : session.verdict,
      sessionStartedAt: newSessionStartedAt,
    );
    await writeMetaJson(updated);

    await ActivityLogService.log(
      event: 'order_metadata_updated',
      mode: mode,
      orderId: safeNewId,
      awb: updated.awb,
      qc: updated.verdict?.name,
      extra: {
        'folder': targetFolder.path,
        'previousId': oldBareId,
        if (newSessionStartedAt != null) ...{
          'previousTimestamp': previousStartedAt.toIso8601String(),
          'newTimestamp': updated.sessionStartedAt.toIso8601String(),
        },
      },
    );

    return targetFolder.path;
  }

  /// Merge partial session into existing meta.
  Map<String, dynamic> _mergeSession(Map<String, dynamic> existing, CaptureSession session) {
    final mode = session.mode.name.toUpperCase();

    final merged = Map<String, dynamic>.from(existing);
    merged['order_id'] = session.orderId ?? existing['order_id'];
    merged['awb'] = session.awb ?? existing['awb'];
    merged['mode'] = mode;
    merged['session_started_at'] = session.sessionStartedAt.toIso8601String();
    merged['app_version'] = CaptureSession.appVersion;
    merged['storage_key'] = FileNamingService.orderFolderName(
      session.orderId!,
      session.mode,
    );

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
      if (session.contentsPhotoPath != null)
        'contents': {'captured_at': DateTime.now().toIso8601String(), 'file': session.contentsPhotoPath},
      if (session.serialPhotoPath != null)
        'serial': {'captured_at': DateTime.now().toIso8601String(), 'file': session.serialPhotoPath},
    };
    merged['photos'] = photos;

    if (session.verdict != null) {
      merged['verdict'] = session.verdict!.name;
      merged['claim_trigger'] = session.verdict!.triggersClaim;
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
    final folder = await findOrderFolder(orderId);
    return folder?.listSync() ?? [];
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