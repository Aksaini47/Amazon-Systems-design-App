import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/screens/verdict_bottom_sheet.dart';

void main() {
  /// Opens the sheet and taps [labels] in order (a verdict can need a
  /// sub-reason tap or two before the sheet pops its result).
  Future<QcVerdictResult?> showSheetAndTap(WidgetTester tester, List<String> labels) async {
    QcVerdictResult? result;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () async {
                result = await showModalBottomSheet<QcVerdictResult>(
                  context: context,
                  isScrollControlled: true,
                  builder: (_) => const VerdictBottomSheet(orderId: '407-1234567-1234567'),
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    for (final label in labels) {
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    return result;
  }

  testWidgets('OK pops QCVerdict.ok with no sub-reason', (tester) async {
    final r = await showSheetAndTap(tester, ['OK']);
    expect(r?.verdict, QCVerdict.ok);
    expect(r?.subReasons, isEmpty);
  });

  testWidgets('DAMAGED pops QCVerdict.damaged after a sub-reason', (tester) async {
    final r = await showSheetAndTap(tester, ['DAMAGED', 'HEAVILY DAMAGED']);
    expect(r?.verdict, QCVerdict.damaged);
    expect(r?.subReasons, [QCSubReason.heavilyDamaged]);
  });

  testWidgets('DAMAGED offers the four damaged sub-reasons and no different ones', (tester) async {
    await showSheetAndTap(tester, ['DAMAGED']);
    for (final r in QCSubReason.damagedFamily) {
      expect(find.text(r.shortLabel), findsOneWidget);
    }
    for (final r in QCSubReason.differentFamily) {
      expect(find.text(r.shortLabel), findsNothing);
    }
  });

  testWidgets('DIFFERENT asks a sub-reason, then the fraud confirm, then pops', (tester) async {
    final r = await showSheetAndTap(
      tester,
      ['DIFFERENT', 'COUNTERFEIT / FAKE', 'Yes, Flag Fraud'],
    );
    expect(r?.verdict, QCVerdict.different);
    expect(r?.subReasons, [QCSubReason.counterfeitItem]);
  });

  testWidgets('DIFFERENT offers the two different sub-reasons and no damaged ones', (tester) async {
    await showSheetAndTap(tester, ['DIFFERENT']);
    for (final r in QCSubReason.differentFamily) {
      expect(find.text(r.shortLabel), findsOneWidget);
    }
    for (final r in QCSubReason.damagedFamily) {
      expect(find.text(r.shortLabel), findsNothing);
    }
  });

  // Sir, 2026-10-24: the damaged sub-reasons used to be asked inside DAMAGED +
  // DIFFERENT (damaged panel, then different panel). Sub-reasons now exist only
  // inside "damaged" and "different", so the combined verdict resolves at once.
  testWidgets('DAMAGED + DIFFERENT pops at once with no sub-reasons — and it must trigger a claim',
      (tester) async {
    final r = await showSheetAndTap(tester, ['DAMAGED + DIFFERENT']);
    expect(r?.verdict, QCVerdict.damagedDifferent);
    expect(r?.subReasons, isEmpty);
    expect(r!.verdict.triggersClaim, isTrue);
    for (final s in QCSubReason.values) {
      expect(find.text(s.shortLabel), findsNothing);
    }
  });

  testWidgets('EMPTY BOX pops with its auto-assigned sub-reason', (tester) async {
    final r = await showSheetAndTap(tester, ['EMPTY BOX']);
    expect(r?.verdict, QCVerdict.emptyBox);
    expect(r?.subReasons, [QCSubReason.emptyBoxReceived]);
  });

  testWidgets('Back from a sub-reason panel returns to the main verdicts', (tester) async {
    final r = await showSheetAndTap(tester, ['DAMAGED', '← Back']);
    expect(r, isNull); // the sheet is still open
    expect(find.text('DAMAGED + DIFFERENT'), findsOneWidget);
    expect(find.text('HEAVILY DAMAGED'), findsNothing);
  });

  test('a sub-reason that belongs to another main reason is rejected', () {
    expect(
      () => QcVerdictResult(QCVerdict.damagedDifferent, [QCSubReason.heavilyDamaged]),
      throwsAssertionError,
    );
    expect(
      () => QcVerdictResult(QCVerdict.different, [QCSubReason.minorDamage]),
      throwsAssertionError,
    );
  });

  testWidgets('sheet shows the order id', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: VerdictBottomSheet(orderId: '407-1234567-1234567')),
    ));
    expect(find.textContaining('407-1234567-1234567'), findsOneWidget);
  });
}
