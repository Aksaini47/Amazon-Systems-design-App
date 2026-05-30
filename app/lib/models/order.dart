/// Typed model for an Amazon order synced from SP-API.
class Order {
  final String orderId;
  final String? purchaseDate;
  final String? orderStatus;
  final String? fulfillmentChannel;
  final String? asin;
  final String? sku;
  final String? productTitle;
  final int quantity;
  final bool hasReturn;

  const Order({
    required this.orderId,
    this.purchaseDate,
    this.orderStatus,
    this.fulfillmentChannel,
    this.asin,
    this.sku,
    this.productTitle,
    this.quantity = 1,
    this.hasReturn = false,
  });

  factory Order.fromJson(Map<String, dynamic> json) {
    return Order(
      orderId: json['order_id'] as String,
      purchaseDate: json['purchase_date'] as String?,
      orderStatus: json['order_status'] as String?,
      fulfillmentChannel: json['fulfillment_channel'] as String?,
      asin: json['asin'] as String?,
      sku: json['sku'] as String?,
      productTitle: json['product_title'] as String?,
      quantity: (json['quantity'] as int?) ?? 1,
      hasReturn: ((json['has_return'] as int?) ?? 0) == 1,
    );
  }

  bool get isFbm => fulfillmentChannel == 'MFN';
  bool get isFba => fulfillmentChannel == 'AFN';

  @override
  String toString() => 'Order($orderId, $productTitle)';
}
