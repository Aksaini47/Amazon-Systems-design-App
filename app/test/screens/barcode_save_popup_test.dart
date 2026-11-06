import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/screens/barcode_save_popup.dart';
import 'package:repairfully_camera/theme/rf_theme.dart';
import 'package:repairfully_camera/widgets/rf_button.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The popup's SAVE gate: an RT save needs a valid Order ID AND an AWB of at
/// least 12 digits, no maximum (a faded return label once got an AWB two
/// characters short saved); PK keeps
/// the open rule. The camera, scanner and storage plugins are absent in a test
/// — the popup shrugs that off and still renders its fields, which is all this
/// needs.
void main() {
  const orderId = '40712345671234567'; // typed as digits → 407-1234567-1234567

  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<void> open(WidgetTester tester, CaptureMode mode) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: buildRfTheme(),
      // TEXT mode: the barcode reader's plugin does not exist in a test.
      home: BarcodeSavePopup(mode: mode, startInBarcodeMode: false),
    ));
    await tester.pump(const Duration(milliseconds: 100));
  }

  Finder orderField() => find.byType(TextField).at(0);
  Finder awbField() => find.byType(TextField).at(1);

  bool saveEnabled(WidgetTester tester) =>
      tester.widget<RfButton>(find.widgetWithText(RfButton, 'SAVE')).onPressed != null;

  Future<void> type(WidgetTester tester, Finder field, String text) async {
    await tester.enterText(field, text);
    await tester.pump();
  }

  group('RT', () {
    testWidgets('a blank tracking ID can be saved - an Order ID is all it takes', (tester) async {
      await open(tester, CaptureMode.rt);
      expect(saveEnabled(tester), isFalse, reason: 'no Order ID yet');
      await type(tester, orderField(), orderId);
      expect(tester.widget<TextField>(orderField()).controller!.text, '407-1234567-1234567');
      expect(saveEnabled(tester), isTrue);
      expect(find.textContaining('AWB must be at least 12 digits'), findsNothing);
    });

    testWidgets('typing in the tracking ID brings the digit rule in; clearing it lifts it',
        (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);
      await type(tester, awbField(), '12345');
      expect(saveEnabled(tester), isFalse);
      expect(find.text('AWB must be at least 12 digits (5 entered)'), findsOneWidget);
      await type(tester, awbField(), '');
      expect(saveEnabled(tester), isTrue);
      expect(find.textContaining('AWB must be at least 12 digits'), findsNothing);
    });

    testWidgets('an AWB under 12 digits blocks SAVE and says how many were entered', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);

      await type(tester, awbField(), '1234567890'); // the incident: 2 digits short
      expect(saveEnabled(tester), isFalse);
      expect(find.text('AWB must be at least 12 digits (10 entered)'), findsOneWidget);

      await type(tester, awbField(), '12345678901');
      expect(saveEnabled(tester), isFalse);
      expect(find.text('AWB must be at least 12 digits (11 entered)'), findsOneWidget);
    });

    testWidgets('12 digits unlock SAVE; losing a digit locks it again', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);

      await type(tester, awbField(), '123456789012');
      expect(saveEnabled(tester), isTrue);
      expect(find.textContaining('AWB must be at least 12 digits'), findsNothing);

      await type(tester, awbField(), '12345678901');
      expect(saveEnabled(tester), isFalse);
    });

    testWidgets('a valid AWB does not save a bad Order ID', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, awbField(), '123456789012');
      await type(tester, orderField(), '99912345671234567'); // prefix 999 is not Amazon's
      expect(saveEnabled(tester), isFalse);
      expect(find.text('Invalid Order ID prefix'), findsOneWidget);
    });

    testWidgets('the AWB field keeps letters + digits in CAPITALS and drops the rest', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, awbField(), 'ek-123 456 789in');
      expect(tester.widget<TextField>(awbField()).controller!.text, 'EK123456789IN');
    });

    testWidgets('the 5 lettered courier formats save, an unknown lettered code does not', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);
      for (final awb in ['EK123456789IN', 'X12345678', 'SF12345678AB', 'FMPC1234567890', 'XB123456789012']) {
        await type(tester, awbField(), awb);
        expect(saveEnabled(tester), isTrue, reason: awb);
      }
      await type(tester, awbField(), 'ABC12345');
      expect(saveEnabled(tester), isFalse);
      expect(find.textContaining('Not a known format'), findsOneWidget);
    });

    testWidgets('13, 14 and 20 digit AWBs save too - only a short one is blocked', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);
      for (final awb in ['1234567890123', '12345678901234', '12345678901234567890']) {
        await type(tester, awbField(), awb);
        expect(saveEnabled(tester), isTrue, reason: '${awb.length} digits');
        expect(find.textContaining('AWB must be at least 12 digits'), findsNothing);
      }
    });
  });

  group('website order id RF-YYMMDD-NNNN', () {
    testWidgets('typed digits after the RF- shortcut make a saveable order id (RT, blank tracking)',
        (tester) async {
      await open(tester, CaptureMode.rt);
      await tester.tap(find.text('RF-'));
      await tester.pump();
      expect(tester.widget<TextField>(orderField()).controller!.text, 'RF-');
      expect(saveEnabled(tester), isFalse);

      await type(tester, orderField(), 'RF-2611040004');
      expect(tester.widget<TextField>(orderField()).controller!.text, 'RF-261104-0004');
      expect(saveEnabled(tester), isTrue, reason: 'no Amazon prefix gate for the website id');
      expect(find.text('Invalid Order ID prefix'), findsNothing);
    });

    testWidgets('a full id with an impossible date stays unsaveable and says why', (tester) async {
      await open(tester, CaptureMode.pk);
      await type(tester, orderField(), 'RF-2613040004');
      expect(saveEnabled(tester), isFalse);
      expect(find.textContaining('real date'), findsOneWidget);
    });

    testWidgets('Amazon ids keep their prefix gate next to it', (tester) async {
      await open(tester, CaptureMode.pk);
      await type(tester, orderField(), '99912345671234567');
      expect(saveEnabled(tester), isFalse);
      expect(find.text('Invalid Order ID prefix'), findsOneWidget);
      await type(tester, orderField(), '40712345671234567');
      expect(saveEnabled(tester), isTrue);
    });
  });

  group('PK', () {
    testWidgets('keeps the open rule: SAVE needs only a valid Order ID', (tester) async {
      await open(tester, CaptureMode.pk);
      expect(saveEnabled(tester), isFalse);
      await type(tester, orderField(), orderId);
      expect(saveEnabled(tester), isTrue, reason: 'no AWB needed');

      await type(tester, awbField(), '12345678901234'); // a 14-digit carrier AWB
      expect(saveEnabled(tester), isTrue);
      expect(find.textContaining('AWB must be at least 12 digits'), findsNothing);
    });
  });
}
