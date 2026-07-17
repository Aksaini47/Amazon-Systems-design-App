import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/screens/verdict_bottom_sheet.dart';

void main() {
  Future<QCVerdict?> showSheetAndTap(WidgetTester tester, String label) async {
    QCVerdict? result;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () async {
                result = await showModalBottomSheet<QCVerdict>(
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
    await tester.tap(find.text(label));
    await tester.pumpAndSettle();
    return result;
  }

  testWidgets('OK pops QCVerdict.ok', (tester) async {
    expect(await showSheetAndTap(tester, 'OK'), QCVerdict.ok);
  });

  testWidgets('DAMAGED pops QCVerdict.damaged', (tester) async {
    expect(await showSheetAndTap(tester, 'DAMAGED'), QCVerdict.damaged);
  });

  testWidgets('DAMAGED + DIFFERENT pops the combined verdict — and it must trigger a claim',
      (tester) async {
    final v = await showSheetAndTap(tester, 'DAMAGED + DIFFERENT');
    expect(v, QCVerdict.damagedDifferent);
    expect(v!.triggersClaim, isTrue);
  });

  testWidgets('sheet shows the order id', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: VerdictBottomSheet(orderId: '407-1234567-1234567')),
    ));
    expect(find.textContaining('407-1234567-1234567'), findsOneWidget);
  });
}
