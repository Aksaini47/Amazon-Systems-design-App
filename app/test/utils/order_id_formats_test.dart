import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/services/awb_classifier.dart';
import 'package:repairfully_camera/utils/order_id_input_formatter.dart';
import 'package:repairfully_camera/utils/order_id_matcher.dart';

/// Two order id shapes live side by side (Sir, 2026-11-04): Amazon
/// `407-1234567-1234567` and the website's `RF-YYMMDD-NNNN`. They must never
/// clash - in validation, in typing, or in the scanner's AWB picking.
void main() {
  group('website order id RF-YYMMDD-NNNN', () {
    test('accepts the real example and other valid dates', () {
      expect(isWebsiteOrderId('RF-261104-0004'), isTrue);
      expect(isWebsiteOrderId('  RF-261104-0004 '), isTrue);
      expect(isWebsiteOrderId('RF-240229-1234'), isTrue, reason: '2024 is a leap year');
      expect(isWebsiteOrderId('RF-261231-9999'), isTrue);
    });

    test('rejects impossible dates, wrong lengths and look-alikes', () {
      expect(isWebsiteOrderId('RF-261304-0004'), isFalse, reason: 'month 13');
      expect(isWebsiteOrderId('RF-261100-0004'), isFalse, reason: 'day 00');
      expect(isWebsiteOrderId('RF-261131-0004'), isFalse, reason: '31 Nov');
      expect(isWebsiteOrderId('RF-250229-0004'), isFalse, reason: '2025 is not a leap year');
      expect(isWebsiteOrderId('RF-261104-004'), isFalse);
      expect(isWebsiteOrderId('RF-261104-00045'), isFalse);
      expect(isWebsiteOrderId('RF-26110-0004'), isFalse);
      expect(isWebsiteOrderId('rf-261104-0004'), isFalse, reason: 'stored upper-case');
      expect(isWebsiteOrderId('RF261104-0004'), isFalse);
      expect(isWebsiteOrderId('RF-261104-0004-PK'), isFalse);
    });

    test('never overlaps with the Amazon shape or its prefix rule', () {
      expect(isPlausibleOrderId('RF-261104-0004'), isFalse);
      expect(isWebsiteOrderId('407-1234567-1234567'), isFalse);
      expect(isOrderIdShape('RF-261104-0004'), isTrue);
      expect(isOrderIdShape('407-1234567-1234567'), isTrue);
      expect(isOrderIdShape('999-1234567-1234567'), isTrue, reason: 'shape only; prefix gate is separate');
      expect(isValidOrderId('999-1234567-1234567'), isFalse);
      expect(isValidOrderId('407-1234567-1234567'), isTrue);
      expect(isValidOrderId('RF-261104-0004'), isTrue);
      expect(isValidOrderId('RF-269999-0004'), isFalse);
    });

    test('is never picked as an AWB by the scanner', () {
      expect(CarrierPatterns.pickAwbFromBarcodes(['RF-261104-0004']), isNull);
      expect(CarrierPatterns.pickAwbFromBarcodes(['RF-261104-0004', '123456789012'])?.value, '123456789012');
      expect(CarrierPatterns.findAwbInText('order RF-261104-0004 awb 123456789012')?.value, '123456789012');
    });

    test('no PK/RT near-match against it (that check is Amazon digits only)', () {
      expect(findNearMatch('RF-261104-0004', {'RF-261104-0005', '407-1234567-1234567'}), isNull);
      expect(findNearMatch('407-1234567-1234567', {'RF-261104-0005'}), isNull);
    });
  });

  group('OrderIdInputFormatter', () {
    final f = OrderIdInputFormatter();
    String type(String text, {String old = ''}) => f
        .formatEditUpdate(
          TextEditingValue(text: old),
          TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length)),
        )
        .text;

    test('Amazon typing is unchanged: digits only, hyphens after 3 and 10, 17 max', () {
      expect(type('407'), '407');
      expect(type('4071'), '407-1');
      expect(type('40712345671'), '407-1234567-1');
      expect(type('407123456712345678999'), '407-1234567-1234567');
      expect(type('40a7-1'), '407-1');
    });

    test('website typing: RF- prefix, hyphen after the 6th digit, 10 digits max', () {
      expect(type('R'), 'RF-');
      expect(type('rf'), 'RF-');
      expect(type('RF-2'), 'RF-2');
      expect(type('RF-261104'), 'RF-261104');
      expect(type('RF-2611040'), 'RF-261104-0');
      expect(type('RF-2611040004'), 'RF-261104-0004');
      expect(type('rf2611040004999'), 'RF-261104-0004');
      expect(type('RF-26-11-04-0004'), 'RF-261104-0004', reason: 'a pasted, oddly punctuated id');
    });

    test('the auto-inserted RF- can be deleted again', () {
      expect(type('RF', old: 'RF-'), '', reason: 'backspace over the hyphen');
      expect(type('RF-', old: 'RF-2'), 'RF-', reason: 'deleting the last digit keeps the prefix');
      expect(type('RF-261104', old: 'RF-261104-'), 'RF-261104');
    });
  });

  group('scannedOrderId - the website id as a barcode / QR (Sir, 2026-11-23)', () {
    test('the printed form and its look-alikes all come back as RF-YYMMDD-NNNN', () {
      for (final raw in [
        'RF-261104-0004',
        'rf-261104-0004',
        ' RF-261104-0004 ',
        'RF2611040004',
        'RF 261104 0004',
        'RF_261104_0004',
        'Order: RF-261104-0004',
        'https://repairfully.in/order/RF-261104-0004?x=1',
      ]) {
        expect(scannedOrderId(raw), 'RF-261104-0004', reason: raw);
      }
    });

    test('Amazon ids must already be exact 3-7-7 - nothing is guessed', () {
      expect(scannedOrderId('407-1234567-1234567'), '407-1234567-1234567');
      expect(scannedOrderId('40712345671234567'), isNull);
      expect(scannedOrderId('407 1234567 1234567'), isNull);
    });

    test('a fake date, a wrong length or a longer code is not an order id', () {
      expect(scannedOrderId('RF-261304-0004'), isNull, reason: 'month 13');
      expect(scannedOrderId('RF-261131-0004'), isNull, reason: '31 Nov');
      expect(scannedOrderId('RF-261104-004'), isNull);
      expect(scannedOrderId('RF-261104-00041'), isNull);
      expect(scannedOrderId('XRF-261104-0004'), isNull, reason: 'letter glued in front');
    });

    test('courier AWBs are not taken for it, and are still read as AWBs', () {
      for (final awb in ['EK123456789IN', 'X12345678', '123456789012', 'SF12345678AB']) {
        expect(scannedOrderId(awb), isNull, reason: awb);
      }
      final pick = CarrierPatterns.pickAwbFromBarcodes(['RF2611040004', '123456789012']);
      expect(pick?.value, '123456789012', reason: 'the RF barcode is skipped as an AWB');
    });
  });
}
