import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/utils/video_gestures.dart';

/// The maths behind the in-app video player: tap zones, skip / scrub targets,
/// the zoom matrix and the portrait-aspect fix.
void main() {
  group('formatVideoTime', () {
    test('mm:ss under an hour, h:mm:ss from an hour', () {
      expect(formatVideoTime(Duration.zero), '00:00');
      expect(formatVideoTime(const Duration(seconds: 7)), '00:07');
      expect(formatVideoTime(const Duration(minutes: 3, seconds: 5)), '03:05');
      expect(formatVideoTime(const Duration(minutes: 75, seconds: 9)), '1:15:09');
    });

    test('negative reads as zero', () {
      expect(formatVideoTime(const Duration(seconds: -4)), '00:00');
    });
  });

  group('speed', () {
    test('labels', () {
      expect(formatVideoSpeed(1.0), '1×');
      expect(formatVideoSpeed(1.5), '1.5×');
      expect(formatVideoSpeed(0.5), '0.5×');
      expect(formatVideoSpeed(2.0), '2×');
    });

    test('cycles 0.5 -> 1 -> 1.5 -> 2 -> 0.5; unknown restarts at 1', () {
      expect(nextVideoSpeed(0.5), 1.0);
      expect(nextVideoSpeed(1.0), 1.5);
      expect(nextVideoSpeed(1.5), 2.0);
      expect(nextVideoSpeed(2.0), 0.5);
      expect(nextVideoSpeed(3.0), 1.0);
    });
  });

  group('videoTapZone', () {
    test('outer 35% each side skip, middle zooms', () {
      expect(videoTapZone(0, 400), VideoTapZone.back);
      expect(videoTapZone(139, 400), VideoTapZone.back);
      expect(videoTapZone(200, 400), VideoTapZone.middle);
      expect(videoTapZone(261, 400), VideoTapZone.forward);
      expect(videoTapZone(400, 400), VideoTapZone.forward);
    });

    test('a zero-width box is the middle', () {
      expect(videoTapZone(10, 0), VideoTapZone.middle);
    });
  });

  group('skip and scrub targets', () {
    const clip = Duration(seconds: 100);

    test('skip stays inside the clip', () {
      expect(seekClamped(const Duration(seconds: 50), clip, const Duration(seconds: 10)),
          const Duration(seconds: 60));
      expect(seekClamped(const Duration(seconds: 4), clip, const Duration(seconds: -10)), Duration.zero);
      expect(seekClamped(const Duration(seconds: 95), clip, const Duration(seconds: 10)), clip);
    });

    test('a full-width swipe is 60 s on a long clip', () {
      final t = scrubTarget(
        start: const Duration(seconds: 10),
        dx: 400,
        width: 400,
        duration: clip,
      );
      expect(t, const Duration(seconds: 70));
    });

    test('a short clip uses its own length as the span', () {
      final t = scrubTarget(
        start: Duration.zero,
        dx: 200,
        width: 400,
        duration: const Duration(seconds: 20),
      );
      expect(t, const Duration(seconds: 10));
    });

    test('left swipe goes back and clamps at 0 / the end', () {
      expect(scrubTarget(start: const Duration(seconds: 5), dx: -400, width: 400, duration: clip), Duration.zero);
      expect(scrubTarget(start: const Duration(seconds: 90), dx: 400, width: 400, duration: clip), clip);
    });

    test('no width or no duration leaves the position alone', () {
      const start = Duration(seconds: 3);
      expect(scrubTarget(start: start, dx: 50, width: 0, duration: clip), start);
      expect(scrubTarget(start: start, dx: 50, width: 400, duration: Duration.zero), start);
    });
  });

  group('zoom matrix', () {
    test('zoomAbout keeps the tapped point where it is', () {
      const focal = Offset(120, 300);
      final m = zoomAbout(focal, 2.5);
      final p = MatrixUtils.transformPoint(m, focal);
      expect(p.dx, closeTo(120, 1e-9));
      expect(p.dy, closeTo(300, 1e-9));
      expect(m.getMaxScaleOnAxis(), closeTo(2.5, 1e-9));
    });

    test('zoomAbout at a corner never shows past the content edge', () {
      // Viewport 400x800 zoomed 2.5x around the top-left: the content's
      // top-left stays at the viewport's top-left (no gap opens up there).
      final m = zoomAbout(Offset.zero, 2.5);
      expect(MatrixUtils.transformPoint(m, Offset.zero), Offset.zero);
      // ...and around the bottom-right, its bottom-right stays put.
      final n = zoomAbout(const Offset(400, 800), 2.5);
      final br = MatrixUtils.transformPoint(n, const Offset(400, 800));
      expect(br.dx, closeTo(400, 1e-9));
      expect(br.dy, closeTo(800, 1e-9));
    });

    test('lerpZoom runs from one matrix to the other', () {
      final a = Matrix4.identity();
      final b = zoomAbout(const Offset(100, 100), 3.0);
      expect(lerpZoom(a, b, 0).getMaxScaleOnAxis(), closeTo(1.0, 1e-9));
      expect(lerpZoom(a, b, 1).getMaxScaleOnAxis(), closeTo(3.0, 1e-9));
      expect(lerpZoom(a, b, 0.5).getMaxScaleOnAxis(), closeTo(2.0, 1e-9));
    });

    test('isVideoZoomed ignores float noise at 1x', () {
      expect(isVideoZoomed(Matrix4.identity()), isFalse);
      expect(isVideoZoomed(zoomAbout(const Offset(10, 10), 1.01)), isFalse);
      expect(isVideoZoomed(zoomAbout(const Offset(10, 10), 1.5)), isTrue);
    });
  });

  group('videoDisplayAspect (portrait-recording fix)', () {
    test('landscape coded size = rotation ignored -> portrait slot', () {
      final a = videoDisplayAspect(size: const Size(1920, 1080), aspectRatio: 1920 / 1080);
      expect(a, closeTo(0.5625, 1e-9));
    });

    test('a size that is already portrait is used as reported', () {
      final a = videoDisplayAspect(size: const Size(1080, 1920), aspectRatio: 1080 / 1920);
      expect(a, closeTo(0.5625, 1e-9));
    });

    test('a nonsense ratio falls back to 9:16', () {
      expect(videoDisplayAspect(size: Size.zero, aspectRatio: 0), closeTo(9 / 16, 1e-9));
      expect(videoDisplayAspect(size: Size.zero, aspectRatio: double.nan), closeTo(9 / 16, 1e-9));
    });
  });
}
