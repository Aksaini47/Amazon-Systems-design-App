/// Capture mode — replaces the old 'packing'/'unpacking' string.
enum CaptureMode { pk, rt }

/// QC verdict — only applicable to RT mode.
enum QCVerdict {
  /// Product matches what was sent.
  ok,
  /// Product arrived damaged / defective.
  damaged,
  /// Fraud/swap detected — buyer returned a different item.
  different,
  /// Both damaged AND different item returned.
  damagedDifferent,
}

/// Side / type of the product in a photo.
/// Used in both PK mode and RT claim-photo flows.
///   label    — return label / shipping label
///   contents — package contents shot (RT claim flow)
///   front    — product front
///   back     — product back
///   serial   — closeup of serial / FPC sticker (optional)
enum PhotoSide { label, contents, front, back, serial }

/// Holds all metadata and asset paths for one order's capture session.
class CaptureSession {
  final String? orderId;
  final String? awb;
  final CaptureMode mode;
  final DateTime sessionStartedAt;
  final DateTime? videoStartedAt;
  final DateTime? videoStoppedAt;
  final int? videoDurationSeconds;
  final String? videoPath;
  final String? frontPhotoPath;
  final String? backPhotoPath;
  final String? labelPhotoPath; // RT only
  final String? contentsPhotoPath; // RT claim flow only — package contents shot
  final String? serialPhotoPath; // RT only, optional
  final QCVerdict? verdict;
  final String? productTitle;

  const CaptureSession({
    this.orderId,
    this.awb,
    required this.mode,
    required this.sessionStartedAt,
    this.videoStartedAt,
    this.videoStoppedAt,
    this.videoDurationSeconds,
    this.videoPath,
    this.frontPhotoPath,
    this.backPhotoPath,
    this.labelPhotoPath,
    this.contentsPhotoPath,
    this.serialPhotoPath,
    this.verdict,
    this.productTitle,
  });

  static const _unset = Object();

  CaptureSession copyWith({
    String? orderId,
    Object? awb = _unset,
    DateTime? videoStartedAt,
    DateTime? videoStoppedAt,
    int? videoDurationSeconds,
    String? videoPath,
    Object? frontPhotoPath = _unset,
    Object? backPhotoPath = _unset,
    Object? labelPhotoPath = _unset,
    Object? contentsPhotoPath = _unset,
    Object? serialPhotoPath = _unset,
    QCVerdict? verdict,
    String? productTitle,
  }) {
    return CaptureSession(
      orderId: orderId ?? this.orderId,
      awb: identical(awb, _unset) ? this.awb : awb as String?,
      mode: mode,
      sessionStartedAt: sessionStartedAt,
      videoStartedAt: videoStartedAt ?? this.videoStartedAt,
      videoStoppedAt: videoStoppedAt ?? this.videoStoppedAt,
      videoDurationSeconds: videoDurationSeconds ?? this.videoDurationSeconds,
      videoPath: videoPath ?? this.videoPath,
      frontPhotoPath: identical(frontPhotoPath, _unset)
          ? this.frontPhotoPath
          : frontPhotoPath as String?,
      backPhotoPath: identical(backPhotoPath, _unset)
          ? this.backPhotoPath
          : backPhotoPath as String?,
      labelPhotoPath: identical(labelPhotoPath, _unset)
          ? this.labelPhotoPath
          : labelPhotoPath as String?,
      contentsPhotoPath: identical(contentsPhotoPath, _unset)
          ? this.contentsPhotoPath
          : contentsPhotoPath as String?,
      serialPhotoPath: identical(serialPhotoPath, _unset)
          ? this.serialPhotoPath
          : serialPhotoPath as String?,
      verdict: verdict ?? this.verdict,
      productTitle: productTitle ?? this.productTitle,
    );
  }

  String? photoPathFor(PhotoSide side) {
    switch (side) {
      case PhotoSide.front:
        return frontPhotoPath;
      case PhotoSide.back:
        return backPhotoPath;
      case PhotoSide.label:
        return labelPhotoPath;
      case PhotoSide.contents:
        return contentsPhotoPath;
      case PhotoSide.serial:
        return serialPhotoPath;
    }
  }

  CaptureSession withPhotoSide(PhotoSide side, String? path) {
    switch (side) {
      case PhotoSide.front:
        return copyWith(frontPhotoPath: path);
      case PhotoSide.back:
        return copyWith(backPhotoPath: path);
      case PhotoSide.label:
        return copyWith(labelPhotoPath: path);
      case PhotoSide.contents:
        return copyWith(contentsPhotoPath: path);
      case PhotoSide.serial:
        return copyWith(serialPhotoPath: path);
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'order_id': orderId,
      'awb': awb,
      'mode': mode.name.toUpperCase(),
      'session_started_at': sessionStartedAt.toIso8601String(),
      if (videoStartedAt != null) 'video_started_at': videoStartedAt!.toIso8601String(),
      if (videoStoppedAt != null) 'video_stopped_at': videoStoppedAt!.toIso8601String(),
      if (videoDurationSeconds != null) 'video_duration_seconds': videoDurationSeconds,
      if (videoPath != null) 'video_file': videoPath,
      if (frontPhotoPath != null || labelPhotoPath != null || contentsPhotoPath != null)
        'photos': {
          if (labelPhotoPath != null) 'label': {'captured_at': DateTime.now().toIso8601String(), 'file': labelPhotoPath},
          if (contentsPhotoPath != null) 'contents': {'captured_at': DateTime.now().toIso8601String(), 'file': contentsPhotoPath},
          if (frontPhotoPath != null) 'front': {'captured_at': DateTime.now().toIso8601String(), 'file': frontPhotoPath},
          if (backPhotoPath != null) 'back': {'captured_at': DateTime.now().toIso8601String(), 'file': backPhotoPath},
          if (serialPhotoPath != null) 'serial': {'captured_at': DateTime.now().toIso8601String(), 'file': serialPhotoPath},
        },
      if (verdict != null) 'verdict': verdict!.name,
      if (productTitle != null) 'product_title': productTitle,
      'claim_trigger': verdict == QCVerdict.damaged || verdict == QCVerdict.different || verdict == QCVerdict.damagedDifferent,
      'app_version': '1.0.0',
    };
  }

  /// True when RT verdict is Damaged or Different — triggers composite generation.
  bool get triggersClaim =>
      verdict == QCVerdict.damaged || verdict == QCVerdict.different;

  /// Check if all required photos for this mode are captured.
  bool get isPhotoComplete {
    if (mode == CaptureMode.pk) {
      return frontPhotoPath != null && backPhotoPath != null;
    }
    if (verdict == null) return true;
    // RT QC OK: front + back only (serial optional).
    if (verdict == QCVerdict.ok) {
      return frontPhotoPath != null && backPhotoPath != null;
    }
    // RT damaged / different / etc.: label + contents + front + back (serial optional).
    return labelPhotoPath != null
        && contentsPhotoPath != null
        && frontPhotoPath != null
        && backPhotoPath != null;
  }

  /// Check if video is captured.
  bool get isVideoCaptured => videoPath != null;

  /// Check if session is complete (photos + video + orderId).
  bool get isReadyToSave => isPhotoComplete && isVideoCaptured && orderId != null;
}