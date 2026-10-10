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

  testWidgets('DAMAGED + DIFFERENT pops the combined verdict — and it must trigger a claim',
      (tester) async {
    final r = await showSheetAndTap(
      tester,
      ['DAMAGED + DIFFERENT', 'HEAVILY DAMAGED', 'DIFFERENT ITEM'],
    );
    expect(r?.verdict, QCVerdict.damagedDifferent);
    expect(r?.subReasons, [QCSubReason.heavilyDamaged, QCSubReason.differentItem]);
    expect(r!.verdict.triggersClaim, isTrue);
  });

  testWidgets('sheet shows the order id', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: VerdictBottomSheet(orderId: '407-1234567-1234567')),
    ));
    expect(find.textContaining('407-1234567-1234567'), findsOneWidget);
  });
}
