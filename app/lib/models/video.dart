/// Type-safe video record as stored/returned by the backend.
class Video {
  final int id;
  final String? orderId;
  final String? fbaShipmentId;
  final int? fbaBoxNumber;
  final String type; // 'packing' | 'unpacking'
  final String? fileName;
  final double? durationSeconds;
  final int? fileSizeBytes;
  final String? recordedAt;
  final String? uploadedAt;

  const Video({
    required this.id,
    this.orderId,
    this.fbaShipmentId,
    this.fbaBoxNumber,
    required this.type,
    this.fileName,
    this.durationSeconds,
    this.fileSizeBytes,
    this.recordedAt,
    this.uploadedAt,
  });

  factory Video.fromJson(Map<String, dynamic> json) {
    return Video(
      id: json['id'] as int,
      orderId: json['order_id'] as String?,
      fbaShipmentId: json['fba_shipment_id'] as String?,
      fbaBoxNumber: json['fba_box_number'] as int?,
      type: (json['type'] as String?) ?? 'packing',
      fileName: json['file_name'] as String?,
      durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
      fileSizeBytes: json['file_size_bytes'] as int?,
      recordedAt: json['recorded_at'] as String?,
      uploadedAt: json['uploaded_at'] as String?,
    );
  }

  bool get isPacking => type == 'packing';
  bool get isUnpacking => type == 'unpacking';

  /// Duration formatted as MM:SS
  String get durationLabel {
    if (durationSeconds == null) return '--:--';
    final s = durationSeconds!.round();
    final mm = (s ~/ 60).toString().padLeft(2, '0');
    final ss = (s % 60).toString().padLeft(2, '0');
    return '$mm:$ss';
  }

  /// File size in MB
  String get sizeLabel {
    if (fileSizeBytes == null) return '';
    final mb = fileSizeBytes! / (1024 * 1024);
    return '${mb.toStringAsFixed(1)} MB';
  }

  @override
  String toString() => 'Video($id, $type, $fileName)';
}
