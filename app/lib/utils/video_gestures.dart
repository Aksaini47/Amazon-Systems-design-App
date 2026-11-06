import 'dart:math' as math;
import 'package:flutter/widgets.dart';

/// Pure helpers behind the in-app video player (rf_video_player.dart): time
/// text, tap zones, seek maths and the zoom matrix. Kept free of widgets and of
/// the video_player plugin so they can be unit-tested.

/// Deepest pinch zoom, and the zoom a centre double-tap jumps to.
const double kVideoMaxZoom = 6.0;
const double kVideoDoubleTapZoom = 2.5;

/// Seconds a double-tap on the left / right edge skips.
const int kVideoSkipSeconds = 10;

/// Playback speeds the speed chip cycles through.
const List<double> kVideoSpeeds = [0.5, 1.0, 1.5, 2.0];

/// "mm:ss", or "h:mm:ss" from one hour up. Negative values read as 00:00.
String formatVideoTime(Duration d) {
  if (d.isNegative) d = Duration.zero;
  String two(int n) => n.toString().padLeft(2, '0');
  final s = two(d.inSeconds % 60);
  if (d.inHours > 0) return '${d.inHours}:${two(d.inMinutes % 60)}:$s';
  return '${two(d.inMinutes)}:$s';
}

/// Speed label, "1×" / "1.5×".
String formatVideoSpeed(double speed) {
  final whole = speed == speed.roundToDouble();
  return '${whole ? speed.toInt() : speed}×';
}

/// The speed after [current] in [kVideoSpeeds], wrapping; an unknown value
/// restarts at normal speed.
double nextVideoSpeed(double current) {
  final i = kVideoSpeeds.indexWhere((s) => (s - current).abs() < 0.01);
  if (i < 0) return 1.0;
  return kVideoSpeeds[(i + 1) % kVideoSpeeds.length];
}

/// Which third of the video a tap landed in. The outer 35% each side are the
/// skip zones; the middle 30% is the zoom zone.
enum VideoTapZone { back, middle, forward }

VideoTapZone videoTapZone(double x, double width) {
  if (width <= 0) return VideoTapZone.middle;
  final f = x / width;
  if (f < 0.35) return VideoTapZone.back;
  if (f > 0.65) return VideoTapZone.forward;
  return VideoTapZone.middle;
}

/// [position] moved by [delta], kept inside 0..[duration].
Duration seekClamped(Duration position, Duration duration, Duration delta) {
  final t = position + delta;
  if (t < Duration.zero) return Duration.zero;
  if (t > duration) return duration;
  return t;
}

/// Where a horizontal swipe of [dx] pixels over a [width]-wide video lands.
/// A full-width swipe covers 60 s (or the whole clip when it is shorter), so a
/// short thumb swipe is a fine scrub and a long one is a big jump.
Duration scrubTarget({
  required Duration start,
  required double dx,
  required double width,
  required Duration duration,
}) {
  if (width <= 0 || duration <= Duration.zero) return start;
  final span = math.min(60.0, math.max(5.0, duration.inMilliseconds / 1000.0));
  final deltaMs = (dx / width * span * 1000).round();
  return seekClamped(start, duration, Duration(milliseconds: deltaMs));
}

/// True once the content is meaningfully zoomed in.
bool isVideoZoomed(Matrix4 m) => m.getMaxScaleOnAxis() > 1.02;

/// Matrix that scales the viewport by [scale] keeping [focal] (viewport
/// coordinates) fixed. Valid for content exactly as big as the viewport, which
/// is how the player lays its video out.
Matrix4 zoomAbout(Offset focal, double scale) {
  final tx = focal.dx * (1 - scale);
  final ty = focal.dy * (1 - scale);
  return Matrix4(scale, 0, 0, 0, 0, scale, 0, 0, 0, 0, 1, 0, tx, ty, 0, 1);
}

/// Straight interpolation between two scale+translate matrices. Both ends are
/// inside the pan bounds, and the bounds are linear in the scale, so every
/// step in between is too.
Matrix4 lerpZoom(Matrix4 a, Matrix4 b, double t) {
  double mix(double x, double y) => x + (y - x) * t;
  final s = mix(a.storage[0], b.storage[0]);
  return Matrix4(
    s, 0, 0, 0,
    0, s, 0, 0,
    0, 0, 1, 0,
    mix(a.storage[12], b.storage[12]), mix(a.storage[13], b.storage[13]), 0, 1,
  );
}

/// Aspect ratio to draw the video at.
///
/// video_player_android reports the CODED size (1920x1080) and ignores the
/// MP4's rotation flag, while the texture it hands over is already rotated
/// (1080x1920). This app records portrait, so a landscape-looking size means
/// "rotation ignored" and the slot has to be the swapped, portrait ratio —
/// drawing it at 1.78 is the stretched-playback bug fixed on 2026-05-17.
double videoDisplayAspect({required Size size, required double aspectRatio}) {
  final ignoredRotation = size.width > size.height && size.height > 0;
  final a = ignoredRotation ? size.height / size.width : aspectRatio;
  return (a.isFinite && a > 0) ? a : 9 / 16;
}
