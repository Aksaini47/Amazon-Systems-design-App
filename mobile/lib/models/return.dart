/// A return record linked to an order.
class Return {
  final int id;
  final String orderId;
  final String? returnDate;
  final String? amazonRmaId;
  final String? returnTracking;
  final String? reasonCode;
  final double refundAmount;
  final String claimStatus; // 'none' | 'pending' | 'filed' | 'resolved'

  const Return({
    required this.id,
    required this.orderId,
    this.returnDate,
    this.amazonRmaId,
    this.returnTracking,
    this.reasonCode,
    this.refundAmount = 0,
    this.claimStatus = 'none',
  });

  factory Return.fromJson(Map<String, dynamic> json) {
    return Return(
      id: json['id'] as int,
      orderId: json['order_id'] as String,
      returnDate: json['return_date'] as String?,
      amazonRmaId: json['amazon_rma_id'] as String?,
      returnTracking: json['return_tracking'] as String?,
      reasonCode: json['reason_code'] as String?,
      refundAmount: (json['refund_amount'] as num?)?.toDouble() ?? 0.0,
      claimStatus: (json['claim_status'] as String?) ?? 'none',
    );
  }

  bool get hasClaim => claimStatus != 'none';

  @override
  String toString() => 'Return($id, $orderId, $claimStatus)';
}
