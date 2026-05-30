import 'video.dart';

/// FBA inbound shipment (seller → Amazon warehouse).
class FbaShipment {
  final String shipmentId;
  final String? shipmentName;
  final String? destinationFc;
  final String shipmentStatus;
  final int unitCount;
  final String? createdDate;
  final int videoCount;

  const FbaShipment({
    required this.shipmentId,
    this.shipmentName,
    this.destinationFc,
    required this.shipmentStatus,
    this.unitCount = 0,
    this.createdDate,
    this.videoCount = 0,
  });

  factory FbaShipment.fromJson(Map<String, dynamic> json) {
    return FbaShipment(
      shipmentId: json['shipment_id'] as String,
      shipmentName: json['shipment_name'] as String?,
      destinationFc: json['destination_fc'] as String?,
      shipmentStatus: (json['shipment_status'] as String?) ?? 'WORKING',
      unitCount: (json['unit_count'] as int?) ?? 0,
      createdDate: json['created_date'] as String?,
      videoCount: (json['video_count'] as int?) ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'shipment_id': shipmentId,
    'shipment_name': shipmentName,
    'destination_fc': destinationFc,
    'shipment_status': shipmentStatus,
    'unit_count': unitCount,
    'created_date': createdDate,
    'video_count': videoCount,
  };

  @override
  String toString() => 'FbaShipment($shipmentId, $shipmentStatus)';
}

/// Shipment detail with its associated videos.
class FbaShipmentDetail extends FbaShipment {
  final List<Video> videos;

  const FbaShipmentDetail({
    required super.shipmentId,
    super.shipmentName,
    super.destinationFc,
    required super.shipmentStatus,
    super.unitCount,
    super.createdDate,
    super.videoCount,
    required this.videos,
  });

  factory FbaShipmentDetail.fromJson(Map<String, dynamic> json) {
    final base = FbaShipment.fromJson(json);
    final rawVideos = json['videos'] as List<dynamic>? ?? [];
    return FbaShipmentDetail(
      shipmentId: base.shipmentId,
      shipmentName: base.shipmentName,
      destinationFc: base.destinationFc,
      shipmentStatus: base.shipmentStatus,
      unitCount: base.unitCount,
      createdDate: base.createdDate,
      videoCount: base.videoCount,
      videos: rawVideos.map((v) => Video.fromJson(v as Map<String, dynamic>)).toList(),
    );
  }
}
