import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/screens/barcode_save_popup.dart';
import 'package:repairfully_camera/theme/rf_theme.dart';
import 'package:repairfully_camera/widgets/rf_button.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The popup's SAVE gate: an RT save needs a valid Order ID AND a 12-digit AWB
/// (a faded return label once got an AWB two characters short saved); PK keeps
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
      home: BarcodeSavePopup(mode: mode),
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
    testWidgets('SAVE stays disabled without an AWB, however good the Order ID', (tester) async {
      await open(tester, CaptureMode.rt);
      expect(saveEnabled(tester), isFalse);
      await type(tester, orderField(), orderId);
      expect(tester.widget<TextField>(orderField()).controller!.text, '407-1234567-1234567');
      expect(saveEnabled(tester), isFalse);
    });

    testWidgets('an AWB that is not 12 digits blocks SAVE and says how many were entered', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);

      await type(tester, awbField(), '1234567890'); // the incident: 2 digits short
      expect(saveEnabled(tester), isFalse);
      expect(find.text('AWB must be exactly 12 digits (10 entered)'), findsOneWidget);

      await type(tester, awbField(), '12345678901');
      expect(saveEnabled(tester), isFalse);
      expect(find.text('AWB must be exactly 12 digits (11 entered)'), findsOneWidget);
    });

    testWidgets('12 digits unlock SAVE; losing a digit locks it again', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, orderField(), orderId);

      await type(tester, awbField(), '123456789012');
      expect(saveEnabled(tester), isTrue);
      expect(find.textContaining('AWB must be exactly 12 digits'), findsNothing);

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

    testWidgets('the AWB field takes numbers only, at most 12', (tester) async {
      await open(tester, CaptureMode.rt);
      await type(tester, awbField(), '12ab34-56 7890123456');
      expect(tester.widget<TextField>(awbField()).controller!.text, '123456789012');
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
      expect(find.textContaining('AWB must be exactly 12 digits'), findsNothing);
    });
  });
}
