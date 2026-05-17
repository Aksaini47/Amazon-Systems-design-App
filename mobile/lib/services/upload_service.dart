import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/capture_session.dart';
import 'api_service.dart';

/// Result of an order upload attempt — used by callers (camera screen, gallery
/// retry) to surface status to the user.
enum UploadStatus { success, offline, failed }

class UploadResult {
  final UploadStatus status;
  final String? error;
  final int photosUploaded;
  final bool videoUploaded;

  UploadResult.success({required this.photosUploaded, required this.videoUploaded})
      : status = UploadStatus.success, error = null;
  UploadResult.offline()
      : status = UploadStatus.offline, error = 'Backend unreachable', photosUploaded = 0, videoUploaded = false;
  UploadResult.failed(String e, {this.photosUploaded = 0, this.videoUploaded = false})
      : status = UploadStatus.failed, error = e;
}

/// Orchestrates the full per-session upload to backend:
///   1. Health check (ping) — skip if offline
///   2. Upsert order (POST /api/orders) — required before any upload
///   3. Upload video (POST /api/videos/upload)
///   4. Upload each photo (POST /api/images/upload)
///   5. Write `.uploaded` marker file to the order folder
///
/// Designed to be fire-and-forget from the camera save flow. Failures are
/// surfaced via [UploadResult] but never throw.
class UploadService {
  /// Upload one captured session's files to the backend.
  /// [orderFolderPath] is where to write the .uploaded marker on success.
  static Future<UploadResult> uploadSession({
    required CaptureSession session,
    required String orderFolderPath,
  }) async {
    if (session.orderId == null) {
      return UploadResult.failed('No order ID');
    }

    // 1. Quick health check — bail early if backend is offline
    final online = await ApiService.ping();
    if (!online) return UploadResult.offline();

    int photosUploaded = 0;
    bool videoUploaded = false;
    try {
      // 2. Ensure the order row exists on the server
      await ApiService.upsertOrder(
        orderId: session.orderId!,
        productTitle: session.productTitle,
        awbNumber: session.awb,
      );

      // 3. Upload the video
      if (session.videoPath != null) {
        final file = File(session.videoPath!);
        if (await file.exists()) {
          // PK → packing, RT → unpacking (backend's canonical types)
          final type = session.mode == CaptureMode.pk ? 'packing' : 'unpacking';
          await ApiService.uploadVideo(
            orderId: session.orderId,
            type: type,
            videoFile: file,
            durationSeconds: session.videoDurationSeconds?.toDouble(),
            recordedAt: session.videoStartedAt?.toIso8601String(),
          );
          videoUploaded = true;
          debugPrint('Uploaded video for ${session.orderId}');
        }
      }

      // 4. Upload each captured photo. Continue past per-photo failures so
      //    a single bad image doesn't kill the whole upload.
      final photos = <String?>[
        session.labelPhotoPath,
        session.contentsPhotoPath,
        session.frontPhotoPath,
        session.backPhotoPath,
        session.serialPhotoPath,
      ].whereType<String>().toList();

      for (final photoPath in photos) {
        try {
          final file = File(photoPath);
          if (!await file.exists()) continue;
          await ApiService.uploadImage(orderId: session.orderId!, imageFile: file);
          photosUploaded++;
        } catch (e) {
          debugPrint('Photo upload skipped ($photoPath): $e');
        }
      }

      // 5. Mark the local order folder as uploaded so Gallery can show the badge
      try {
        final marker = File('$orderFolderPath/.uploaded');
        await marker.writeAsString(DateTime.now().toIso8601String());
      } catch (e) {
        debugPrint('Could not write .uploaded marker (non-fatal): $e');
      }

      debugPrint('Upload complete for ${session.orderId}: video=$videoUploaded, photos=$photosUploaded');
      return UploadResult.success(photosUploaded: photosUploaded, videoUploaded: videoUploaded);
    } catch (e) {
      debugPrint('uploadSession failed for ${session.orderId}: $e');
      return UploadResult.failed(
        e.toString(),
        photosUploaded: photosUploaded,
        videoUploaded: videoUploaded,
      );
    }
  }

  /// Retry / first-time upload for an order folder on disk — used by the
  /// Gallery "Upload to backend" button. Reconstructs the upload from the
  /// folder contents (no CaptureSession needed). Mode is inferred from the
  /// video filename (`_PK.mp4` → packing, `_RT.mp4` → unpacking).
  static Future<UploadResult> uploadFromFolder({
    required String orderId,
    required String folderPath,
  }) async {
    final online = await ApiService.ping();
    if (!online) return UploadResult.offline();

    int photosUploaded = 0;
    bool videoUploaded = false;
    try {
      await ApiService.upsertOrder(orderId: orderId);

      final dir = Directory(folderPath);
      final entries = dir.listSync(followLinks: false).whereType<File>().toList();

      // Find the video (one .mp4 per order)
      File? videoFile;
      for (final f in entries) {
        if (f.path.toLowerCase().endsWith('.mp4')) { videoFile = f; break; }
      }
      if (videoFile != null) {
        final pk = videoFile.path.contains('_PK.') || videoFile.path.contains('_PK_');
        await ApiService.uploadVideo(
          orderId: orderId,
          type: pk ? 'packing' : 'unpacking',
          videoFile: videoFile,
        );
        videoUploaded = true;
      }

      // Upload every .jpg in the folder
      for (final f in entries) {
        final p = f.path.toLowerCase();
        if (!(p.endsWith('.jpg') || p.endsWith('.jpeg') || p.endsWith('.png'))) continue;
        try {
          await ApiService.uploadImage(orderId: orderId, imageFile: f);
          photosUploaded++;
        } catch (e) {
          debugPrint('Photo upload skipped (${f.path}): $e');
        }
      }

      try {
        await File('$folderPath/.uploaded').writeAsString(DateTime.now().toIso8601String());
      } catch (e) {
        // Failing to write the `.uploaded` marker is not fatal — the order
        // is uploaded — but the queue won't know that on next run and may
        // re-upload everything. Log so storage-full conditions surface.
        debugPrint('uploadFromFolder: could not write .uploaded marker for $orderId — $e');
      }

      return UploadResult.success(photosUploaded: photosUploaded, videoUploaded: videoUploaded);
    } catch (e) {
      debugPrint('uploadFromFolder failed for $orderId: $e');
      return UploadResult.failed(e.toString(),
          photosUploaded: photosUploaded, videoUploaded: videoUploaded);
    }
  }

  /// Returns true if the order folder has a `.uploaded` marker.
  static bool isUploaded(String orderFolderPath) {
    return File('$orderFolderPath/.uploaded').existsSync();
  }

  /// Returns the upload timestamp from `.uploaded` marker, or null if not uploaded.
  static Future<DateTime?> uploadedAt(String orderFolderPath) async {
    try {
      final marker = File('$orderFolderPath/.uploaded');
      if (!await marker.exists()) return null;
      return DateTime.parse(await marker.readAsString());
    } catch (_) {
      return null;
    }
  }
}
