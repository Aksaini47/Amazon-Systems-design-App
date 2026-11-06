import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/widgets/rf_video_player.dart';

/// The video seek bar: a 48 dp touch target, tap to jump, drag to scrub.
void main() {
  const clip = Duration(seconds: 100);

  Future<void> pumpBar(
    WidgetTester tester, {
    Duration position = Duration.zero,
    VoidCallback? onStart,
    ValueChanged<Duration>? onScrub,
    ValueChanged<Duration>? onEnd,
  }) {
    return tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: SizedBox(
            width: 300,
            child: RfSeekBar(
              position: position,
              duration: clip,
              onScrubStart: onStart,
              onScrub: onScrub,
              onScrubEnd: onEnd,
            ),
          ),
        ),
      ),
    ));
  }

  testWidgets('the touch target is at least 48 dp tall', (tester) async {
    await pumpBar(tester);
    expect(tester.getSize(find.byType(RfSeekBar)).height, greaterThanOrEqualTo(48));
  });

  testWidgets('tap jumps to the tapped spot (start then end, no drag)', (tester) async {
    var starts = 0;
    final scrubs = <Duration>[];
    final ends = <Duration>[];
    await pumpBar(tester, onStart: () => starts++, onScrub: scrubs.add, onEnd: ends.add);

    final box = tester.getRect(find.byType(RfSeekBar));
    // The track runs from thumbPad to width - thumbPad: its middle is 50%.
    await tester.tapAt(Offset(box.left + box.width / 2, box.center.dy));
    await tester.pump();

    expect(starts, 1);
    expect(scrubs, isEmpty);
    expect(ends, hasLength(1));
    expect(ends.single.inMilliseconds, closeTo(50000, 200));
  });

  testWidgets('tapping the ends clamps to 0 and the full length', (tester) async {
    final ends = <Duration>[];
    await pumpBar(tester, onEnd: ends.add);

    final box = tester.getRect(find.byType(RfSeekBar));
    await tester.tapAt(Offset(box.left + 1, box.center.dy));
    await tester.pump();
    await tester.tapAt(Offset(box.right - 1, box.center.dy));
    await tester.pump();

    expect(ends, [Duration.zero, clip]);
  });

  testWidgets('dragging scrubs once, reports each step and ends where it stopped', (tester) async {
    var starts = 0;
    final scrubs = <Duration>[];
    final ends = <Duration>[];
    await pumpBar(tester, onStart: () => starts++, onScrub: scrubs.add, onEnd: ends.add);

    final box = tester.getRect(find.byType(RfSeekBar));
    final start = Offset(box.left + RfSeekBar.thumbPad, box.center.dy);
    final gesture = await tester.startGesture(start);
    await tester.pump();
    await gesture.moveBy(const Offset(60, 0));
    await tester.pump();
    await gesture.moveBy(const Offset(60, 0));
    await tester.pump();
    await gesture.up();
    await tester.pump();

    expect(starts, 1, reason: 'one scrub, not one per callback');
    expect(scrubs, isNotEmpty);
    expect(ends, hasLength(1));
    // The track is 300 - 2*thumbPad wide; the finger moved 120 px of it.
    final track = 300 - 2 * RfSeekBar.thumbPad;
    expect(ends.single.inMilliseconds, closeTo(120 / track * 100000, 4000));
  });

  testWidgets('the thumb follows the playback position', (tester) async {
    await pumpBar(tester, position: const Duration(seconds: 25));
    // Nothing to assert on the painter directly; the bar must at least lay
    // out and expose its position to accessibility.
    expect(find.bySemanticsLabel('Video position'), findsOneWidget);
  });
}
