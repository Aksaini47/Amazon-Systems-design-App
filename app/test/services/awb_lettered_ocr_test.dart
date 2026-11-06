import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/services/awb_classifier.dart';
import 'package:repairfully_camera/utils/order_id_input_formatter.dart';

/// Sir, 2026-11-06: RT accepts lettered AWBs of 5 couriers in their EXACT
/// format (some shorter than 12), and OCR look-alikes (0/O, 1/I, 5/S ...) are
/// repaired by position - never guessed.
void main() {
  group('RT lettered courier formats', () {
    test('the 5 couriers are accepted in their exact format', () {
      expect(returnLetteredCourierFor('EK123456789IN'), 'India Post');
      expect(returnLetteredCourierFor('X12345678'), 'DTDC');
      expect(returnLetteredCourierFor('SF12345678AB'), 'Shadowfax');
      expect(returnLetteredCourierFor('FMPC1234567890'), 'Ekart');
      expect(returnLetteredCourierFor('XB123456789012'), 'Xpressbees');
      for (final v in ['EK123456789IN', 'X12345678', 'SF12345678AB', 'FMPC1234567890', 'XB123456789012']) {
        expect(isValidReturnAwb(v), isTrue, reason: v);
        expect(awbAllowsSave(CaptureMode.rt, v), isTrue, reason: v);
      }
    });

    test('near misses and loose patterns are rejected', () {
      expect(isValidReturnAwb('EK12345678IN'), isFalse, reason: 'India Post one digit short');
      expect(isValidReturnAwb('X1234567'), isFalse, reason: 'DTDC one digit short');
      expect(isValidReturnAwb('ABC12345678'), isFalse, reason: 'Trackon-only shape is not accepted for RT');
      expect(isValidReturnAwb('ek123456789in'), isFalse, reason: 'stored in capitals');
      expect(returnLetteredCourierFor('123456789012'), isNull, reason: 'all digits = the 12-digit rule');
    });

    test('the digit rule and blank are unchanged', () {
      expect(isValidReturnAwb('123456789012'), isTrue);
      expect(isValidReturnAwb('12345678901'), isFalse);
      expect(awbAllowsSave(CaptureMode.rt, ''), isTrue);
    });
  });

  group('repairOcrToken - position-based look-alike repair', () {
    test('India Post: digits misread as letters (and IN misread) are put back', () {
      expect(CarrierPatterns.repairOcrToken('EK12345678GIN')?.value, 'EK123456786IN');
      expect(CarrierPatterns.repairOcrToken('EK1234567891N')?.value, 'EK123456789IN');
      expect(CarrierPatterns.repairOcrToken('E0123456789IN')?.value, 'EO123456789IN',
          reason: 'a letter slot holding 0 becomes O');
    });

    test('DTDC and a long numeric AWB', () {
      expect(CarrierPatterns.repairOcrToken('XI2345678')?.value, 'X12345678');
      final r = CarrierPatterns.repairOcrToken('12345678901O');
      expect(r?.value, '123456789010');
      expect(r?.fixes, 1);
    });

    test('never more than 2 swaps', () {
      expect(CarrierPatterns.repairOcrToken('EKIZ3S56789IN'), isNull, reason: '3 swaps needed');
    });

    test('a tie between two different results is refused', () {
      // 14 chars: "AB" + 12 digits is Xpressbees as read, but forcing 2 more
      // letters would also make an Ekart shape - the as-read (0 swaps) wins.
      expect(CarrierPatterns.repairOcrToken('AB123456789012')?.fixes, 0);
    });

    test('accept filter applies to the repaired value', () {
      expect(CarrierPatterns.repairOcrToken('XI2345678', accept: isValidReturnAwb)?.value, 'X12345678');
      expect(CarrierPatterns.repairOcrToken('12345678O1', accept: isValidReturnAwb), isNull,
          reason: '10 digits is short for RT even after repair');
    });
  });

  group('findAwbInText uses the repair only when nothing fits as read', () {
    test('a misread India Post AWB is found and flagged as repaired', () {
      final pick = CarrierPatterns.findAwbInText('SPEED POST EK12345678GIN qty 1', accept: isValidReturnAwb);
      expect(pick?.value, 'EK123456786IN');
      expect(pick?.ocrFixes, 1);
    });

    test('an as-read match keeps ocrFixes 0', () {
      final pick = CarrierPatterns.findAwbInText('AWB 123456789012', accept: isValidReturnAwb);
      expect(pick?.value, '123456789012');
      expect(pick?.ocrFixes, 0);
    });

    test('order ids are still never AWBs', () {
      expect(CarrierPatterns.findAwbInText('407-1234567-1234567 RF-261104-0004'), isNull);
    });
  });

  group('AwbInputFormatter', () {
    final f = AwbInputFormatter();
    String type(String text) => f
        .formatEditUpdate(
          TextEditingValue.empty,
          TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length)),
        )
        .text;

    test('capitals, letters and digits only, 30 max', () {
      expect(type('ek 123-456 789in'), 'EK123456789IN');
      expect(type('sf/12.34'), 'SF1234');
      expect(type('1' * 40), '1' * 30);
    });
  });
}
