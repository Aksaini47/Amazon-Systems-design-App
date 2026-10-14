import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/widgets/rf_fast_scroller.dart';

void main() {
  const thumbKey = Key('rf_fast_scroller_thumb');
  const bubbleKey = Key('rf_fast_scroller_bubble');

  Widget harness(
    ScrollController controller, {
    int items = 100,
    String Function(double offset)? labelAt,
    bool enabled = true,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          child: SizedBox(
            width: 300,
            height: 400,
            child: RfFastScroller(
              controller: controller,
              labelAt: labelAt,
              enabled: enabled,
              child: ListView.builder(
                controller: controller,
                itemCount: items,
                itemExtent: 50,
                itemBuilder: (_, i) => Text('row $i'),
              ),
            ),
          ),
        ),
      ),
    );
  }

  double thumbOpacity(WidgetTester tester) => tester
      .widget<AnimatedOpacity>(
        find.ancestor(of: find.byKey(thumbKey), matching: find.byType(AnimatedOpacity)),
      )
      .opacity;

  testWidgets('shows a thumb for a list that scrolls, none when it all fits', (tester) async {
    final long = ScrollController();
    addTearDown(long.dispose);
    await tester.pumpWidget(harness(long));
    await tester.pump(); // the metrics notification arrives after first layout
    expect(find.byKey(thumbKey), findsOneWidget);

    final short = ScrollController();
    addTearDown(short.dispose);
    await tester.pumpWidget(harness(short, items: 3));
    await tester.pump();
    expect(find.byKey(thumbKey), findsNothing);
  });

  testWidgets('enabled: false keeps the thumb away, true brings it in', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c, enabled: false));
    await tester.pump();
    expect(find.byKey(thumbKey), findsNothing);

    await tester.pumpWidget(harness(c));
    await tester.pump();
    expect(find.byKey(thumbKey), findsOneWidget);
  });

  testWidgets('thumb follows the scroll position from top to bottom of the track', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c));
    await tester.pump();

    final box = tester.getRect(find.byType(RfFastScroller));
    expect(tester.getRect(find.byKey(thumbKey)).top, closeTo(box.top + 4, 0.5));

    c.jumpTo(c.position.maxScrollExtent);
    await tester.pump();
    expect(tester.getRect(find.byKey(thumbKey)).bottom, closeTo(box.bottom - 4, 0.5));

    c.jumpTo(c.position.maxScrollExtent / 2);
    await tester.pump();
    expect(tester.getCenter(find.byKey(thumbKey)).dy, closeTo(box.center.dy, 0.5));
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('dragging the thumb scrolls the list and shows the bubble until release', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c, labelAt: (o) => 'at ${o.round()}'));
    await tester.pump();
    expect(find.byKey(bubbleKey), findsNothing);

    final gesture = await tester.startGesture(tester.getCenter(find.byKey(thumbKey)));
    await gesture.moveBy(const Offset(0, 60));
    await tester.pump();
    expect(find.byKey(bubbleKey), findsOneWidget);
    expect(c.offset, greaterThan(0));
    expect(find.text('at ${c.offset.round()}'), findsOneWidget, reason: 'bubble names the offset');

    // Far past the end of the track: clamps to the end of the list.
    await gesture.moveBy(const Offset(0, 2000));
    await tester.pump();
    expect(c.offset, c.position.maxScrollExtent);
    expect(find.text('at ${c.position.maxScrollExtent.round()}'), findsOneWidget);

    await gesture.up();
    await tester.pump();
    expect(find.byKey(bubbleKey), findsNothing);
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('dragging the thumb by the whole track travel scrolls the whole list', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c));
    await tester.pump();

    final thumb = tester.getRect(find.byKey(thumbKey));
    final box = tester.getRect(find.byType(RfFastScroller));
    final travel = box.height - 4 - 4 - 56; // insets + thumb height
    final gesture = await tester.startGesture(thumb.center);
    await gesture.moveBy(const Offset(0, 30)); // gets past the touch slop first
    await tester.pump();
    final before = c.offset;
    await gesture.moveBy(Offset(0, travel / 4));
    await tester.pump();
    // A quarter of the travel is a quarter of the scroll extent.
    expect(c.offset - before, closeTo(c.position.maxScrollExtent / 4, 1));
    await gesture.up();
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('touches off the thumb still scroll the list normally', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c, labelAt: (o) => 'at ${o.round()}'));
    await tester.pump();

    await tester.drag(find.text('row 3'), const Offset(0, -200));
    await tester.pump();
    expect(c.offset, greaterThan(100));
    expect(find.byKey(bubbleKey), findsNothing);
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('thumb rests faint, lights up while scrolling, then fades again', (tester) async {
    final c = ScrollController();
    addTearDown(c.dispose);
    await tester.pumpWidget(harness(c));
    await tester.pump();
    expect(thumbOpacity(tester), lessThan(1));

    c.jumpTo(300);
    await tester.pump();
    expect(thumbOpacity(tester), 1);

    await tester.pump(const Duration(seconds: 3));
    expect(thumbOpacity(tester), lessThan(1));
  });
}
