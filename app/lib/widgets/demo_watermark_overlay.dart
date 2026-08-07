import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Tiled "DEMO - TRIAL" overlay for the demo flavor's live camera preview
/// and gallery video playback. Display-only — per Sir's decision, this does
/// NOT touch the saved video bytes (unlike photos, which get a real
/// burned-in watermark; see ImageProcessingUtils.addDemoWatermark). A raw
/// video file pulled off the device during the trial will be clean.
///
/// [IgnorePointer]-wrapped internally so it never steals tap-to-focus,
/// pinch-to-zoom, or video-player tap-to-toggle-controls gestures from
/// whatever it's layered over.
class DemoWatermarkOverlay extends StatelessWidget {
  const DemoWatermarkOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return const IgnorePointer(
      child: CustomPaint(
        painter: _DemoTilePainter(),
        size: Size.infinite,
      ),
    );
  }
}

class _DemoTilePainter extends CustomPainter {
  const _DemoTilePainter();

  static const _text = 'DEMO • TRIAL';

  @override
  void paint(Canvas canvas, Size size) {
    final textStyle = TextStyle(
      color: Colors.white.withValues(alpha: 0.30),
      fontSize: size.shortestSide * 0.075,
      fontWeight: FontWeight.w800,
      letterSpacing: 1.5,
    );
    final tp = TextPainter(
      text: TextSpan(text: _text, style: textStyle),
      textDirection: TextDirection.ltr,
    )..layout();

    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(-28 * math.pi / 180);
    canvas.translate(-size.width / 2, -size.height / 2);

    final stepX = tp.width * 1.7;
    final stepY = tp.height * 3.2;
    final overflow = size.width + size.height;
    for (double y = -overflow; y < size.height + overflow; y += stepY) {
      for (double x = -overflow; x < size.width + overflow; x += stepX) {
        tp.paint(canvas, Offset(x, y));
      }
    }
    canvas.restore();
  }

  // Static pattern, nothing to animate/react to — never needs a repaint.
  @override
  bool shouldRepaint(covariant _DemoTilePainter oldDelegate) => false;
}
