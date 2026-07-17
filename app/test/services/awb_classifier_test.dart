import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/services/awb_classifier.dart';

void main() {
  group('classify', () {
    test('Amazon order IDs are never classified as AWBs', () {
      expect(CarrierPatterns.classify('407-1234567-1234567'), isNull);
    });

    test('India Post S10 format wins on strictness', () {
      expect(CarrierPatterns.classify('EK123456789IN')?.name, 'India Post');
    });

    test('most-specific carrier wins among overlapping numeric patterns', () {
      // 12-digit numerics match ATS, FedEx, Ecom Express, and the generic
      // fallback — specificity ordering must pick a named carrier, not the
      // fallback.
      final c = CarrierPatterns.classify('123456789012');
      expect(c, isNotNull);
      expect(c!.name, isNot('Unknown carrier'));
    });

    test('unknown-length numeric still lands in the generic fallback', () {
      expect(CarrierPatterns.classify('1234567890123456')?.name, 'Unknown carrier');
    });

    test('empty and garbage values classify as null', () {
      expect(CarrierPatterns.classify(''), isNull);
      expect(CarrierPatterns.classify('hello-world'), isNull);
    });
  });

  group('detectCarrierFromText', () {
    test('finds carrier by label keyword, case-insensitive', () {
      expect(CarrierPatterns.detectCarrierFromText('shipped via Delhivery Ltd')?.name,
          'Delhivery');
      expect(CarrierPatterns.detectCarrierFromText(null), isNull);
      expect(CarrierPatterns.detectCarrierFromText('   '), isNull);
    });
  });

  group('pickAwbFromBarcodes', () {
    test('skips order-id barcodes and picks the AWB', () {
      final r = CarrierPatterns.pickAwbFromBarcodes(
        ['407-1234567-1234567', 'EK123456789IN'],
      );
      expect(r?.value, 'EK123456789IN');
      expect(r?.carrier.name, 'India Post');
    });

    test('carrier hint boosts its own pattern in a tie', () {
      final hint = CarrierPatterns.detectCarrierFromText('ATSPL logistics');
      final r = CarrierPatterns.pickAwbFromBarcodes(['123456789012'], hint: hint);
      expect(r?.carrier.name, 'ATS');
      expect(r!.confidence, greaterThan(0.6));
    });

    test('returns null when only order-id barcodes present', () {
      expect(CarrierPatterns.pickAwbFromBarcodes(['407-1234567-1234567']), isNull);
    });
  });

  group('findAwbInText', () {
    test('extracts an AWB-shaped token from OCR text', () {
      final r = CarrierPatterns.findAwbInText('AWB: EK123456789IN Handle with care');
      expect(r?.value, 'EK123456789IN');
    });

    test('ignores order ids and short tokens', () {
      expect(CarrierPatterns.findAwbInText('order 407-1234567-1234567 qty 2'), isNull);
    });
  });
}
