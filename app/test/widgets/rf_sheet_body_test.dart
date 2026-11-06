import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/widgets/rf_sheet_body.dart';

/// Sir, 2026-11-06: the edit-order sheet's Save / Cancel sat under the Android
/// navigation buttons. RfSheetBody keeps a sheet's content above the system
/// navigation bar AND the keyboard.
void main() {
  const screen = Size(400, 800);
  final contentKey = GlobalKey();

  Future<void> pumpSheet(
    WidgetTester tester, {
    EdgeInsets viewPadding = EdgeInsets.zero,
    EdgeInsets viewInsets = EdgeInsets.zero,
    double contentHeight = 100,
  }) {
    // A phone-sized window, so "flush with the bottom" means y == 800.
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = screen;
    addTearDown(tester.view.reset);
    return tester.pumpWidget(MediaQuery(
      data: MediaQueryData(
        size: screen,
        padding: viewPadding,
        viewPadding: viewPadding,
        viewInsets: viewInsets,
      ),
      child: Directionality(
        textDirection: TextDirection.ltr,
        child: Align(
          alignment: Alignment.bottomCenter,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxHeight: screen.height - viewInsets.bottom),
            child: RfSheetBody(
              child: SizedBox(key: contentKey, height: contentHeight),
            ),
          ),
        ),
      ),
    ));
  }

  testWidgets('content ends above the navigation bar', (tester) async {
    await pumpSheet(tester, viewPadding: const EdgeInsets.only(bottom: 48));
    // The sheet is flush with the screen bottom: base padding (16) + the
    // 48 dp navigation bar sit under the content.
    expect(tester.getRect(find.byKey(contentKey)).bottom, closeTo(screen.height - 16 - 48, 0.5));
  });

  testWidgets('with a gesture-nav strip the content is lifted by that strip too', (tester) async {
    await pumpSheet(tester, viewPadding: const EdgeInsets.only(bottom: 24));
    expect(tester.getRect(find.byKey(contentKey)).bottom, closeTo(screen.height - 16 - 24, 0.5));
  });

  testWidgets('no system bar at all keeps just the base padding', (tester) async {
    await pumpSheet(tester);
    expect(tester.getRect(find.byKey(contentKey)).bottom, closeTo(screen.height - 16, 0.5));
  });

  testWidgets('keyboard and nav bar overlap: the larger one counts, not the sum', (tester) async {
    await pumpSheet(
      tester,
      viewPadding: const EdgeInsets.only(bottom: 48),
      viewInsets: const EdgeInsets.only(bottom: 300),
    );
    // 300 (keyboard, which already covers the bar), not 348.
    expect(tester.getRect(find.byKey(contentKey)).bottom, closeTo(screen.height - 16 - 300, 0.5));
  });

  testWidgets('a sheet taller than the space scrolls instead of overflowing', (tester) async {
    await pumpSheet(
      tester,
      viewPadding: const EdgeInsets.only(bottom: 48),
      viewInsets: const EdgeInsets.only(bottom: 300),
      contentHeight: 2000,
    );
    expect(tester.takeException(), isNull);
    expect(find.byType(SingleChildScrollView), findsOneWidget);

    final before = tester.getRect(find.byKey(contentKey)).top;
    await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -200));
    await tester.pump();
    expect(tester.getRect(find.byKey(contentKey)).top, lessThan(before));
  });
}
