import 'dart:io';

import 'package:image_picker/image_picker.dart';

import '../models/capture_session.dart';
import '../utils/image_processing.dart';
import 'activity_log_service.dart';
import 'camera_settings_service.dart';
import 'local_storage_service.dart';
import 'sync_queue_service.dart';
import 'upload_service.dart';

/// Promote a grouped draft session (video + photos) into a saved order.
class DraftSaveService {
  DraftSaveService._();

  static PhotoSide? photoSideFromDraftName(String fileName) {
    for (final side in PhotoSide.values) {
      if (fileName.contains('_${side.name}_')) return side;
    }
    return null;
  }

  static Map<PhotoSide, String> mapDraftPhotos(List<String> paths) {
    final map = <PhotoSide, String>{};
    for (final path in paths) {
      final name = path.split(Platform.pathSeparator).last;
      final side = photoSideFromDraftName(name);
      if (side != null) map[side] = path;
    }
    return map;
  }

  static List<PhotoSide> missingRequiredPhotos(
    CaptureMode mode, {
    required Map<PhotoSide, String> photos,
    QCVerdict? verdict,
  }) {
    if (mode == CaptureMode.pk) {
      return [
        if (!photos.containsKey(PhotoSide.front)) PhotoSide.front,
        if (!photos.containsKey(PhotoSide.back)) PhotoSide.back,
      ];
    }
    if (verdict == null) return const [];
    // RT QC OK: front + back only (serial optional).
    if (verdict == QCVerdict.ok) {
      return [
        if (!photos.containsKey(PhotoSide.front)) PhotoSide.front,
        if (!photos.containsKey(PhotoSide.back)) PhotoSide.back,
      ];
    }
    // RT damaged / different / etc.: label + contents + front + back.
    return [
      if (!photos.containsKey(PhotoSide.label)) PhotoSide.label,
      if (!photos.containsKey(PhotoSide.contents)) PhotoSide.contents,
      if (!photos.containsKey(PhotoSide.front)) PhotoSide.front,
      if (!photos.containsKey(PhotoSide.back)) PhotoSide.back,
    ];
  }

  static String labelForSide(PhotoSide side) {
    switch (side) {
      case PhotoSide.label:
        return 'Return label';
      case PhotoSide.contents:
        return 'Package contents';
      case PhotoSide.front:
        return 'Product front';
      case PhotoSide.back:
        return 'Product back';
      case PhotoSide.serial:
        return 'Serial / FPC';
    }
  }

  /// Capture one missing photo with the device camera and save to drafts/.
  static Future<String?> captureMissingPhoto(
    CaptureMode mode,
    PhotoSide side,
    LocalStorageService storage,
  ) async {
    final picked = await ImagePicker().pickImage(
      source: ImageSource.camera,
      preferredCameraDevice: CameraDevice.rear,
      imageQuality: 92,
    );
    if (picked == null) return null;
    return storage.saveDraftPhoto(File(picked.path), mode, side);
  }

  /// Promote draft files into an order folder, write meta, enqueue upload.
  static Future<CaptureSession> promoteDraftSession({
    required String orderId,
    String? awb,
    required CaptureMode mode,
    required String videoPath,
    required Map<PhotoSide, String> photosBySide,
    QCVerdict? verdict,
    LocalStorageService? storage,
  }) async {
    final local = storage ?? LocalStorageService();
    final timestampOnPhotos = await CameraSettingsService.getTimestampImage();

    final videoFile = File(videoPath);
    if (!await videoFile.exists()) {
      throw Exception('Draft video missing');
    }
    if (await videoFile.length() < 50000) {
      throw Exception('Draft video is too short or empty');
    }

    final savedVideoPath = await local.promoteDraftVideo(videoPath, orderId, mode);

    final Map<PhotoSide, String> finalPaths = {};
    for (final entry in photosBySide.entries) {
      final draftPath = entry.value;
      if (!await File(draftPath).exists()) continue;
      try {
        if (timestampOnPhotos) {
          await ImageProcessingUtils.processPhoto(
            File(draftPath),
            orientation: CustomOrientation.portraitUp,
            addTimestamp: true,
            prefix: '${mode.name.toUpperCase()}-$orderId',
          );
        }
        finalPaths[entry.key] = await local.promoteDraftPhoto(
          draftPath,
          orderId,
          mode,
          entry.key,
        );
      } catch (e) {
        throw Exception('Failed to save ${entry.key.name} photo: $e');
      }
    }

    final session = CaptureSession(
      orderId: orderId,
      awb: awb,
      mode: mode,
      sessionStartedAt: DateTime.now(),
      videoPath: savedVideoPath,
      frontPhotoPath: finalPaths[PhotoSide.front],
      backPhotoPath: finalPaths[PhotoSide.back],
      labelPhotoPath: finalPaths[PhotoSide.label],
      contentsPhotoPath: finalPaths[PhotoSide.contents],
      serialPhotoPath: finalPaths[PhotoSide.serial],
      verdict: verdict,
    );

    if (!session.isReadyToSave) {
      throw Exception('Missing required photos for this ${mode.name.toUpperCase()} session');
    }

    await local.writeMetaJson(session);

    final orderFolder = await local.getOrderFolder(orderId, mode: mode);
    final storageKey = orderFolder.path.split(Platform.pathSeparator).last;
    await SyncQueueService.enqueue(storageKey, orderFolder.path);

    await ActivityLogService.log(
      event: 'draft_promoted',
      mode: mode,
      orderId: orderId,
      awb: awb,
      qc: verdict?.name,
      extra: {'folder': orderFolder.path},
    );

    // Fire-and-forget upload
    // ignore: unawaited_futures
    UploadService.uploadSession(session: session, orderFolderPath: orderFolder.path)
        .then((r) async {
      if (r.status == UploadStatus.success) {
        await SyncQueueService.remove(storageKey);
      }
    });

    return session;
  }
}
