import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
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

  // A faded return label once made the app save an AWB two characters short —
  // the carrier patterns accept almost any 9-16 character value, so nothing
  // noticed. RT saves now need exactly 12 digits.
  group('isValidReturnAwb', () {
    test('accepts exactly 12 ASCII digits, ignoring surrounding whitespace', () {
      expect(isValidReturnAwb('123456789012'), isTrue);
      expect(isValidReturnAwb('  123456789012 \n'), isTrue);
    });

    test('rejects an AWB that lost (or gained) characters', () {
      expect(isValidReturnAwb('1234567890'), isFalse, reason: '2 short');
      expect(isValidReturnAwb('12345678901'), isFalse, reason: '1 short');
      expect(isValidReturnAwb('1234567890123'), isFalse, reason: '1 long');
      expect(isValidReturnAwb('12345678901234'), isFalse, reason: 'a 14-digit AWB');
      expect(isValidReturnAwb(''), isFalse);
    });

    test('rejects letters, separators and non-ASCII digits', () {
      expect(isValidReturnAwb('12345678901A'), isFalse);
      expect(isValidReturnAwb('EK123456789IN'), isFalse);
      expect(isValidReturnAwb('1234-5678-9012'), isFalse);
      expect(isValidReturnAwb('123 456 789 012'), isFalse);
      // Twelve Arabic-Indic digits.
      expect(isValidReturnAwb('١٢٣٤٥٦٧٨٩٠١٢'),
          isFalse, reason: 'only 0-9 count as digits');
    });
  });

  group('awbAllowsSave', () {
    test('RT saves need a 12-digit AWB', () {
      expect(awbAllowsSave(CaptureMode.rt, '123456789012'), isTrue);
      expect(awbAllowsSave(CaptureMode.rt, '1234567890'), isFalse);
      expect(awbAllowsSave(CaptureMode.rt, ''), isFalse);
    });

    test('PK keeps the open rule: any AWB, or none', () {
      expect(awbAllowsSave(CaptureMode.pk, ''), isTrue);
      expect(awbAllowsSave(CaptureMode.pk, '12345678901234'), isTrue);
      expect(awbAllowsSave(CaptureMode.pk, 'EK123456789IN'), isTrue);
    });
  });

  group('accept filter (what RT passes so a truncated read cannot become the AWB)', () {
    test('barcodes: a 12-digit AWB beats a 14-digit code that scores higher', () {
      // Unfiltered, the 14-digit value wins (Delhivery 0.75 vs 12-digit 0.65).
      expect(CarrierPatterns.pickAwbFromBarcodes(['12345678901234', '123456789012'])?.value,
          '12345678901234');
      expect(
        CarrierPatterns.pickAwbFromBarcodes(
          ['12345678901234', '123456789012'],
          accept: isValidReturnAwb,
        )?.value,
        '123456789012',
      );
    });

    test('barcodes: a truncated read is not picked at all', () {
      expect(CarrierPatterns.pickAwbFromBarcodes(['1234567890']), isNotNull,
          reason: 'without the filter the carrier patterns take it');
      expect(CarrierPatterns.pickAwbFromBarcodes(['1234567890'], accept: isValidReturnAwb), isNull);
    });

    test('OCR text: only a 12-digit token is taken, order ids still skipped', () {
      const text = 'AWB 1234567890 order 407-1234567-1234567 qty 2';
      expect(CarrierPatterns.findAwbInText(text), isNotNull,
          reason: 'without the filter the 10-digit token is taken');
      expect(CarrierPatterns.findAwbInText(text, accept: isValidReturnAwb), isNull);
      expect(
        CarrierPatterns.findAwbInText('$text 123456789012', accept: isValidReturnAwb)?.value,
        '123456789012',
      );
    });
  });
}
