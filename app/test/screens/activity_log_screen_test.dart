import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/screens/activity_log_screen.dart';
import 'package:repairfully_camera/theme/rf_colors.dart';
import 'package:repairfully_camera/theme/rf_theme.dart';

void main() {
  const noScaling = TextScaler.noScaling;

  group('ActivityLogDay.splitLines', () {
    test('drops blank lines and trailing CR / spaces, keeps the rest verbatim', () {
      final lines = ActivityLogDay.splitLines('a | 1\r\n\r\n  b | 2  \n\n');
      expect(lines, ['a | 1', '  b | 2']);
    });

    test('an empty file has no lines', () {
      expect(ActivityLogDay.splitLines(''), isEmpty);
      expect(ActivityLogDay.splitLines('\n\n  \n'), isEmpty);
    });
  });

  test('activityDayTitle is weekday, day, month, year', () {
    expect(activityDayTitle(DateTime(2026, 10, 14)), 'Wed, 14 Oct 2026');
    expect(activityDayTitle(DateTime(2026)), 'Thu, 1 Jan 2026');
  });

  group('ActivityLogLayout', () {
    final days = [
      ActivityLogDay(DateTime(2026, 10, 14), ['one', 'two ' * 40, 'three']),
      ActivityLogDay(DateTime(2026, 10, 13), ['only']),
    ];

    Future<ActivityLogLayout> measure({double width = 200}) async =>
        (await ActivityLogLayout.measure(days: days, width: width, textScaler: noScaling))!;

    // What one log line takes at [width]: its wrapped text plus the gap under it.
    double lineExtent(String text, double width) {
      final painter = TextPainter(
        text: TextSpan(text: text, style: ActivityLogLayout.lineStyle),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: width);
      return painter.height + ActivityLogLayout.lineGap;
    }

    test('rows are header, a block of lines, footer per day — in order', () async {
      final l = await measure();
      expect(l.rowCount, 3 + 3);
      expect([for (var i = 0; i < l.rowCount; i++) l.kindAt(i)], [
        ActivityLogRowKind.header,
        ActivityLogRowKind.lines,
        ActivityLogRowKind.footer,
        ActivityLogRowKind.header,
        ActivityLogRowKind.lines,
        ActivityLogRowKind.footer,
      ]);
      expect([for (var i = 0; i < l.rowCount; i++) l.dayOfRow(i)], [0, 0, 0, 1, 1, 1]);
      expect(l.linesAt(1), ['one', 'two ' * 40, 'three']);
      expect(l.linesAt(4), ['only']);
    });

    test('a long day is split into blocks of linesPerBlock, in order, none lost', () async {
      const n = 2 * ActivityLogLayout.linesPerBlock + 3;
      final lines = [for (var i = 0; i < n; i++) 'line $i'];
      final l = (await ActivityLogLayout.measure(
        days: [ActivityLogDay(DateTime(2026, 10, 14), lines)],
        width: 200,
        textScaler: noScaling,
      ))!;

      expect(ActivityLogLayout.blocksFor(n), 3);
      expect(l.rowCount, 1 + 3 + 1);
      expect(l.kindAt(0), ActivityLogRowKind.header);
      expect([for (var i = 1; i <= 3; i++) l.kindAt(i)], everyElement(ActivityLogRowKind.lines));
      expect(l.kindAt(4), ActivityLogRowKind.footer);
      expect([for (var i = 1; i <= 3; i++) l.linesAt(i).length], [8, 8, 3]);
      expect([for (var i = 1; i <= 3; i++) ...l.linesAt(i)], lines);
    });

    test('header and footer have their fixed room; a block is the sum of its wrapped lines', () async {
      final l = await measure();
      expect(l.extentAt(0), ActivityLogLayout.headerExtent);
      expect(l.extentAt(2), ActivityLogLayout.footerExtent);
      expect(
        l.extentAt(1),
        closeTo(lineExtent('one', 200) + lineExtent('two ' * 40, 200) + lineExtent('three', 200), 1e-9),
      );
      expect(lineExtent('two ' * 40, 200), greaterThan(lineExtent('one', 200) * 2), reason: 'wraps to several rows');
      expect(l.extentAt(4), closeTo(lineExtent('only', 200), 1e-9));
    });

    test('a narrower width wraps more, so the total grows', () async {
      expect((await measure(width: 120)).totalExtent, greaterThan((await measure(width: 400)).totalExtent));
    });

    test('total extent is the sum of the row extents', () async {
      final l = await measure();
      var sum = 0.0;
      for (var i = 0; i < l.rowCount; i++) {
        sum += l.extentAt(i);
      }
      expect(l.totalExtent, closeTo(sum, 1e-9));
    });

    test('an offset maps to the row and day that cover it', () async {
      final l = await measure();
      var top = 0.0;
      final tops = <double>[];
      for (var i = 0; i < l.rowCount; i++) {
        tops.add(top);
        top += l.extentAt(i);
      }
      for (var i = 0; i < l.rowCount; i++) {
        expect(l.rowAtOffset(tops[i]), i, reason: 'top of row $i');
        expect(l.rowAtOffset(tops[i] + l.extentAt(i) - 0.01), i, reason: 'bottom of row $i');
      }
      expect(l.rowAtOffset(-50), 0);
      expect(l.rowAtOffset(l.totalExtent + 500), l.rowCount - 1);
      expect(l.dayAtOffset(tops[2]), 0, reason: 'the closing rule still belongs to day 0');
      expect(l.dayAtOffset(tops[3]), 1);
    });

    test('hands out the newest whole days early, and they are the start of the final layout', () async {
      final many = [
        for (var d = 0; d < 5; d++)
          ActivityLogDay(
            DateTime(2026, 10, 14 - d),
            [for (var i = 0; i < 100; i++) 'line $i of day $d ' * (1 + i % 3)],
          ),
      ];
      ActivityLogLayout? first;
      final full = (await ActivityLogLayout.measure(
        days: many,
        width: 200,
        textScaler: noScaling,
        firstBatchLines: 150,
        onFirstBatch: (l) => first = l,
      ))!;

      expect(first, isNotNull);
      expect(first!.days.length, 2, reason: '100 lines is not enough, 2 whole days is');
      expect(first!.rowCount, 2 * (ActivityLogLayout.blocksFor(100) + 2));
      for (var i = 0; i < first!.rowCount; i++) {
        expect(first!.extentAt(i), full.extentAt(i), reason: 'row $i');
        expect(first!.kindAt(i), full.kindAt(i), reason: 'row $i');
      }
      expect(first!.totalExtent, lessThan(full.totalExtent));
      expect(full.days.length, 5);
    });

    test('no early batch when the whole log is the first batch', () async {
      var calls = 0;
      await ActivityLogLayout.measure(
        days: days,
        width: 200,
        textScaler: noScaling,
        firstBatchLines: 2, // day 0 alone has 3 lines, but day 1 is still to come…
        onFirstBatch: (_) => calls++,
      );
      expect(calls, 1);

      calls = 0;
      await ActivityLogLayout.measure(
        days: [days.first],
        width: 200,
        textScaler: noScaling,
        firstBatchLines: 2,
        onFirstBatch: (_) => calls++,
      );
      expect(calls, 0, reason: 'nothing follows the first day, so the final layout is enough');
    });

    test('measuring can be cancelled between slices', () async {
      final many = [
        ActivityLogDay(DateTime(2026, 10, 14), List.filled(500, 'a line ' * 12)),
      ];
      final l = await ActivityLogLayout.measure(
        days: many,
        width: 200,
        textScaler: noScaling,
        isCancelled: () => true,
        slice: Duration.zero,
      );
      expect(l, isNull);
    });
  });

  group('ActivityLogScreen', () {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final older = today.subtract(const Duration(days: 9));

    ActivityLogSnapshot snapshot() => (
          path: '/data/logs',
          days: [
            ActivityLogDay(today, ['2026-10-14 09:00:00 | PK | event=a', '2026-10-14 09:05:00 | RT | event=b']),
            ActivityLogDay(yesterday, ['2026-10-13 18:00:00 | event=c']),
            ActivityLogDay(older, ['2026-10-05 10:00:00 | event=d']),
          ],
        );

    void phone(WidgetTester tester, {double width = 360, double height = 780}) {
      tester.view.physicalSize = Size(width * 3, height * 3);
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
    }

    Future<void> open(WidgetTester tester, Future<ActivityLogSnapshot> Function() loader) async {
      await tester.pumpWidget(MaterialApp(
        theme: buildRfTheme(),
        home: ActivityLogScreen(loader: loader),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('every day is its own block: date header, its lines, closing rule', (tester) async {
      phone(tester);
      await open(tester, () async => snapshot());

      for (var d = 0; d < 3; d++) {
        expect(find.byKey(ValueKey('activity_day_header_$d')), findsOneWidget, reason: 'header $d');
        expect(find.byKey(ValueKey('activity_day_footer_$d')), findsOneWidget, reason: 'footer $d');
      }
      expect(find.text(activityDayTitle(today)), findsOneWidget);
      expect(find.text(activityDayTitle(yesterday)), findsOneWidget);
      expect(find.text('Today · 2 events'), findsOneWidget);
      expect(find.text('Yesterday · 1 event'), findsOneWidget);
      expect(find.text('1 event'), findsOneWidget, reason: 'older days carry just the count');

      // Newest day first, each block under the previous one.
      final tops = [
        for (var d = 0; d < 3; d++) tester.getTopLeft(find.byKey(ValueKey('activity_day_header_$d'))).dy,
      ];
      expect(tops[0], lessThan(tops[1]));
      expect(tops[1], lessThan(tops[2]));
    });

    testWidgets('older days still measuring: newest days show at once, no thumb until complete', (tester) async {
      phone(tester);
      final days = [
        for (var d = 0; d < 6; d++)
          ActivityLogDay(
            today.subtract(Duration(days: d)),
            ['2026-10-14 09:00:00 | PK | a', '2026-10-14 09:01:00 | RT | b'],
          ),
      ];
      final finish = Completer<void>();
      await tester.pumpWidget(MaterialApp(
        theme: buildRfTheme(),
        home: ActivityLogScreen(
          loader: () async => (path: '/p', days: days),
          // A measurer stepped by hand: the newest two days, then — once the
          // test says so — everything.
          measurer: ({
            required days,
            required width,
            required textScaler,
            isCancelled,
            onFirstBatch,
          }) async {
            final first = await ActivityLogLayout.measure(
              days: days.sublist(0, 2),
              width: width,
              textScaler: textScaler,
              slice: const Duration(hours: 1),
            );
            onFirstBatch!(first!);
            await finish.future;
            return ActivityLogLayout.measure(
              days: days,
              width: width,
              textScaler: textScaler,
              slice: const Duration(hours: 1),
            );
          },
        ),
      ));
      await tester.pump(); // loader answers → list builds, measuring starts
      await tester.pump(); // first batch arrives → its list builds

      expect(find.text(activityDayTitle(days[0].day)), findsOneWidget);
      expect(find.text('Loading older days…'), findsOneWidget);
      expect(find.byKey(const Key('rf_fast_scroller_thumb')), findsNothing);

      finish.complete();
      await tester.pumpAndSettle();
      expect(find.text('Loading older days…'), findsNothing);
      expect(find.byKey(const Key('rf_fast_scroller_thumb')), findsOneWidget);

      // The oldest day is there now, at the end of the list.
      final controller = tester.widget<ListView>(find.byType(ListView)).controller!;
      controller.jumpTo(controller.position.maxScrollExtent);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('activity_day_footer_5')), findsOneWidget);
      expect(find.text(activityDayTitle(days[5].day)), findsWidgets);
    });

    testWidgets('the list is exactly as long as the measured rows, wherever you are in it', (tester) async {
      phone(tester);
      // Lines of very different lengths: an average-based length estimate
      // would be well off.
      final manyDays = [
        for (var d = 0; d < 30; d++)
          ActivityLogDay(
            today.subtract(Duration(days: d)),
            [for (var i = 0; i < 40; i++) '2026-10-14 09:00:00 | ${'x' * (5 + (i * 37 + d * 11) % 120)}'],
          ),
      ];
      await open(tester, () async => (path: '/p', days: manyDays));

      final list = tester.getSize(find.byType(ListView));
      final layout = (await ActivityLogLayout.measure(
        days: manyDays,
        width: list.width - 14, // right gutter
        textScaler: noScaling,
        slice: const Duration(hours: 1),
      ))!;
      // The list's padding is 4 above and 8 below the rows.
      final exact = layout.totalExtent + 4 + 8 - list.height;

      final controller = tester.widget<ListView>(find.byType(ListView)).controller!;
      expect(controller.position.maxScrollExtent, closeTo(exact, 1e-6), reason: 'at the top');
      for (final fraction in [0.1, 0.37, 0.8]) {
        controller.jumpTo(exact * fraction);
        await tester.pump();
        expect(controller.position.maxScrollExtent, closeTo(exact, 1e-6), reason: 'at ${fraction * 100}%');
      }
      controller.jumpTo(exact);
      await tester.pump();
      expect(find.byKey(const ValueKey('activity_day_footer_29')), findsOneWidget, reason: 'the true end');
    });

    testWidgets('the day title is blue', (tester) async {
      phone(tester);
      await open(tester, () async => snapshot());
      final title = tester.widget<Text>(find.text(activityDayTitle(today)));
      expect(title.style?.color, RfColors.info);
    });

    testWidgets('log lines are shown verbatim and can be selected', (tester) async {
      phone(tester);
      await open(tester, () async => snapshot());
      expect(find.text('2026-10-14 09:00:00 | PK | event=a'), findsOneWidget);
      expect(find.byType(SelectionArea), findsOneWidget);
    });

    testWidgets('no logged days shows the empty message', (tester) async {
      phone(tester);
      await open(tester, () async => (path: '/data/logs', days: <ActivityLogDay>[]));
      expect(find.text('No activity logged yet.'), findsOneWidget);
      expect(find.byType(ListView), findsNothing);
    });

    testWidgets('a log that cannot be read ends in the empty message, not a spinner for ever', (tester) async {
      phone(tester);
      await open(tester, () async => throw StateError('disk gone'));
      expect(find.text('No activity logged yet.'), findsOneWidget);
    });

    testWidgets('refresh reads the log again', (tester) async {
      phone(tester);
      var reads = 0;
      await open(tester, () async {
        reads++;
        return snapshot();
      });
      expect(reads, 1);
      await tester.tap(find.byTooltip('Refresh'));
      await tester.pumpAndSettle();
      expect(reads, 2);
      expect(find.text(activityDayTitle(today)), findsOneWidget);
    });

    // The fast scroller trusts the list's length and the offset→day mapping,
    // so every row must be exactly as tall as it was measured.
    for (final scale in [1.0, 1.6]) {
      testWidgets('each line is exactly its measured height (text scale $scale)', (tester) async {
        phone(tester);
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        final lines = [
          '2026-10-14 09:00:00 | PK | order=403-1234567-8901234 | awb=SF12345678901 | event=order_saved | size_mb=104.5',
          '2026-10-14 09:05:00 | RT | order=402-7654321-1234567 | event=draft_saved | qc=Damaged | sub=Screen cracked',
          'short',
        ];
        await open(tester, () async => (path: '/p', days: [ActivityLogDay(today, lines)]));

        final width = tester.getSize(find.byType(ListView)).width - 14; // right gutter
        final heights = <double>[];
        for (final line in lines) {
          final painter = TextPainter(
            text: TextSpan(text: line, style: ActivityLogLayout.lineStyle),
            textDirection: TextDirection.ltr,
            textScaler: TextScaler.linear(scale),
          )..layout(maxWidth: width);
          heights.add(painter.height);
          expect(tester.getSize(find.text(line)).height, painter.height, reason: line);
        }
        for (var i = 0; i + 1 < lines.length; i++) {
          final gap = tester.getTopLeft(find.text(lines[i + 1])).dy - tester.getTopLeft(find.text(lines[i])).dy;
          expect(gap, closeTo(heights[i] + ActivityLogLayout.lineGap, 1e-6), reason: 'line $i → ${i + 1}');
        }
      });
    }

    testWidgets('a new width re-wraps the lines and keeps them exact', (tester) async {
      phone(tester);
      const line = '2026-10-14 09:00:00 | PK | order=403-1234567-8901234 | awb=SF12345678901 | event=order_saved';
      await open(tester, () async => (path: '/p', days: [ActivityLogDay(today, [line, line])]));
      final narrow = tester.getSize(find.text(line).first).height;

      phone(tester, width: 600);
      await tester.pumpAndSettle();
      final wide = tester.getSize(find.text(line).first).height;
      expect(wide, lessThan(narrow), reason: 'wider screen wraps into fewer rows');

      final painter = TextPainter(
        text: const TextSpan(text: line, style: ActivityLogLayout.lineStyle),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: tester.getSize(find.byType(ListView)).width - 14);
      expect(wide, painter.height);
    });

    testWidgets('dragging the fast-scroll thumb names the day under the top edge', (tester) async {
      phone(tester);
      final manyDays = [
        for (var d = 0; d < 30; d++)
          ActivityLogDay(
            today.subtract(Duration(days: d)),
            [for (var i = 0; i < 12; i++) '2026-10-14 09:0$i:00 | PK | order=403-1234567-890123$i | event=capture_start'],
          ),
      ];
      await open(tester, () async => (path: '/p', days: manyDays));

      final thumb = find.byKey(const Key('rf_fast_scroller_thumb'));
      expect(thumb, findsOneWidget);
      final gesture = await tester.startGesture(tester.getCenter(thumb));
      await gesture.moveBy(const Offset(0, 40));
      await gesture.moveBy(const Offset(0, 120));
      await tester.pump();

      final list = tester.widget<ListView>(find.byType(ListView));
      final offset = list.controller!.offset;
      expect(offset, greaterThan(0));
      // A long slice: measure() must not yield here — the fake-async clock of
      // a widget test would never wake it.
      final layout = (await ActivityLogLayout.measure(
        days: manyDays,
        width: tester.getSize(find.byType(ListView)).width - 14,
        textScaler: noScaling,
        slice: const Duration(hours: 1),
      ))!;
      final expectedDay = manyDays[layout.dayAtOffset(offset - 4)].day;
      expect(
        find.descendant(
          of: find.byKey(const Key('rf_fast_scroller_bubble')),
          matching: find.text(activityDayTitle(expectedDay)),
        ),
        findsOneWidget,
      );
      await gesture.up();
      await tester.pump(const Duration(seconds: 2));
    });
  });
}
