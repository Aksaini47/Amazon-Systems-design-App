import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/screens/activity_log_screen.dart';
import 'package:repairfully_camera/theme/rf_theme.dart';

/// The Orders view of the activity log: a card per order, Find, quick filters,
/// the story sheet - with the raw lines still one tap away.
void main() {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final yesterday = today.subtract(const Duration(days: 1));

  String stamp(DateTime d, String hms) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')} $hms';

  List<String> rtSaved(DateTime d) => [
        '${stamp(d, '10:00:05')} | RT | event=video_start',
        '${stamp(d, '10:01:17')} | RT | event=video_stop | duration_sec=72',
        '${stamp(d, '10:01:30')} | RT | event=qc_verdict | qc=damaged | qc_sub=heavilyDamaged',
        '${stamp(d, '10:01:40')} | RT | qc=damaged | qc_sub=heavilyDamaged | event=photo_saved | type=front',
        '${stamp(d, '10:02:30')} | RT | order=402-1234567-7654321 | awb=123456789012 | event=barcode_saved | qc=damaged | qc_sub=heavilyDamaged | auto_source=live',
        '${stamp(d, '10:02:32')} | RT | order=402-1234567-7654321 | awb=123456789012 | event=shipment_saved | qc=damaged | qc_sub=heavilyDamaged',
      ];

  List<String> pkFailed(DateTime d) => [
        '${stamp(d, '09:00:05')} | PK | event=video_start',
        '${stamp(d, '09:01:10')} | PK | order=403-1111111-2222222 | event=barcode_saved',
        '${stamp(d, '09:01:12')} | PK | order=403-1111111-2222222 | event=shipment_save_failed | error=Video recording was empty',
      ];

  ActivityLogSnapshot snapshot() => (
        path: '/data/logs',
        days: [
          ActivityLogDay(today, rtSaved(today)),
          ActivityLogDay(yesterday, [...pkFailed(yesterday), '${stamp(yesterday, '08:00:00')} | event=app_open | is_demo=false']),
        ],
      );

  void phone(WidgetTester tester) {
    tester.view.physicalSize = const Size(360 * 3, 780 * 3);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
  }

  Future<void> open(WidgetTester tester) async {
    phone(tester);
    await tester.pumpWidget(MaterialApp(
      theme: buildRfTheme(),
      home: ActivityLogScreen(loader: () async => snapshot()),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('opens on Orders: a card per order under its day, in plain words', (tester) async {
    await open(tester);

    expect(find.textContaining('Today', findRichText: true), findsOneWidget);
    expect(find.text('402-1234567-7654321'), findsOneWidget);
    expect(find.text('Saved'), findsOneWidget);
    expect(find.text('Damaged · Heavily damaged'), findsOneWidget);
    expect(find.textContaining('AWB 123456789012'), findsOneWidget);
    expect(find.textContaining('Video 1 min 12 s'), findsOneWidget);
    // Nothing technical on the cards.
    expect(find.textContaining('event='), findsNothing);
    expect(find.textContaining('barcode_saved'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Find narrows to one order, hyphens do not matter, and Clear brings everything back', (tester) async {
    await open(tester);
    expect(find.text('403-1111111-2222222'), findsOneWidget, reason: 'yesterday is on screen too');

    await tester.tap(find.byTooltip('Find'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '4021234567');
    await tester.pumpAndSettle();

    expect(find.textContaining('402-1234567-7654321', findRichText: true), findsOneWidget);
    expect(find.text('403-1111111-2222222'), findsNothing);
    expect(find.text('1 match in 1 day'), findsOneWidget);

    await tester.tap(find.text('Clear'));
    await tester.pumpAndSettle();
    expect(find.text('403-1111111-2222222'), findsOneWidget);
    expect(find.text('1 match in 1 day'), findsNothing);
  });

  testWidgets('a search with no hit says so, kindly', (tester) async {
    await open(tester);
    await tester.tap(find.byTooltip('Find'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '999999');
    await tester.pumpAndSettle();

    expect(find.text('Nothing found'), findsWidgets);
    expect(find.textContaining('Try a shorter part'), findsOneWidget);
  });

  testWidgets('the quick filters narrow: RT, Problems', (tester) async {
    await open(tester);

    await tester.tap(find.text('Problems'));
    await tester.pumpAndSettle();
    expect(find.text('403-1111111-2222222'), findsOneWidget);
    expect(find.text('402-1234567-7654321'), findsNothing);

    await tester.tap(find.text('RT'));
    await tester.pumpAndSettle();
    expect(find.text('402-1234567-7654321'), findsOneWidget);
    expect(find.text('403-1111111-2222222'), findsNothing);

    await tester.tap(find.text('All'));
    await tester.pumpAndSettle();
    expect(find.text('402-1234567-7654321'), findsOneWidget);
    expect(find.text('403-1111111-2222222'), findsOneWidget);
  });

  testWidgets('a card opens the whole story; the raw lines are under Technical details, verbatim', (tester) async {
    await open(tester);
    await tester.tap(find.text('402-1234567-7654321'));
    await tester.pumpAndSettle();

    expect(find.text('WHAT HAPPENED'), findsOneWidget);
    expect(find.text('Recording stopped'), findsOneWidget);
    expect(find.text('QC reason: Damaged'), findsOneWidget);
    // The sheet is a lazy list: scroll down to the end of the story.
    final sheet = find.byType(ListView).last;
    await tester.dragUntilVisible(find.text('Order saved'), sheet, const Offset(0, -120));
    expect(find.text('Order saved'), findsOneWidget);
    expect(find.text('Photo taken - Product front'), findsOneWidget);

    final raw = rtSaved(today).first;
    expect(find.text(raw, findRichText: true), findsNothing, reason: 'collapsed by default');
    await tester.dragUntilVisible(find.textContaining('Technical details'), sheet, const Offset(0, -120));
    await tester.tap(find.textContaining('Technical details'));
    await tester.pumpAndSettle();
    expect(find.textContaining(raw, findRichText: true), findsOneWidget);
    expect(find.textContaining('order=402-1234567-7654321', findRichText: true), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('the Raw log tab is the old viewer with every line verbatim', (tester) async {
    await open(tester);
    await tester.tap(find.text('Raw log'));
    await tester.pumpAndSettle();
    expect(find.text(rtSaved(today).first), findsOneWidget);
    expect(find.byType(SelectionArea), findsOneWidget);

    await tester.tap(find.text('Orders'));
    await tester.pumpAndSettle();
    expect(find.text('402-1234567-7654321'), findsOneWidget);
  });

  testWidgets('Find also works in the Raw log', (tester) async {
    await open(tester);
    await tester.tap(find.text('Raw log'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Find'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'shipment_save_failed');
    await tester.pumpAndSettle();

    expect(find.textContaining('shipment_save_failed'), findsWidgets);
    expect(find.textContaining('shipment_saved'), findsNothing);
  });

  for (final scale in [1.0, 1.6, 2.0]) {
    testWidgets('no overflow at text size $scale', (tester) async {
      phone(tester);
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(MaterialApp(
        theme: buildRfTheme(),
        home: ActivityLogScreen(loader: () async => snapshot()),
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Find'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.tap(find.textContaining('402-1234567', findRichText: true).first);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('every card is exactly as tall as it was planned: the list is as long as its rows', (tester) async {
    phone(tester);
    final days = [
      for (var d = 0; d < 20; d++) ActivityLogDay(today.subtract(Duration(days: d)), [...rtSaved(today.subtract(Duration(days: d))), ...pkFailed(today.subtract(Duration(days: d)))]),
    ];
    await tester.pumpWidget(MaterialApp(
      theme: buildRfTheme(),
      home: ActivityLogScreen(loader: () async => (path: '/p', days: days)),
    ));
    await tester.pumpAndSettle();

    final list = tester.widget<ListView>(find.byType(ListView).last);
    final c = list.controller!;
    final max = c.position.maxScrollExtent;
    for (final f in [0.2, 0.55, 0.9]) {
      c.jumpTo(max * f);
      await tester.pump();
      expect(c.position.maxScrollExtent, closeTo(max, 1e-6), reason: 'at ${f * 100}%');
    }
    c.jumpTo(max);
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('an empty log still says so', (tester) async {
    phone(tester);
    await tester.pumpWidget(MaterialApp(
      theme: buildRfTheme(),
      home: ActivityLogScreen(loader: () async => (path: '/p', days: <ActivityLogDay>[])),
    ));
    await tester.pumpAndSettle();
    expect(find.text('No activity logged yet.'), findsOneWidget);
  });
}
