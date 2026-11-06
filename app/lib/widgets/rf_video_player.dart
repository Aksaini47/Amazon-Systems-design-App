import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../theme/rf_colors.dart';
import '../utils/video_gestures.dart';

/// In-app video player for the gallery (order and draft detail screens).
///
///  - Pinch to zoom up to 6x, pan while zoomed, double-tap the middle to zoom
///    in / out around the tap.
///  - Double-tap the left / right edge to skip 10 s back / forward; keep
///    tapping within a second to keep skipping (10 s, 20 s, 30 s ...).
///  - Swipe sideways (when not zoomed) to scrub; the seek bar has a 48 dp
///    touch target, a draggable thumb and a time bubble.
///  - Real full screen: immersive, screen kept awake, rotate button, swipe
///    down to close. The SAME controller is handed over, so playback carries
///    straight on from the inline view and back.
///  - Pauses when the app goes to the background; replay at the end; 0.5x-2x
///    speed chip.
///
/// [RfVideoPlayer] is the inline view (it owns the controller).
class RfVideoPlayer extends StatefulWidget {
  final String path;

  /// Called with true while the video is zoomed in. The parent list should
  /// stop scrolling then, or a vertical pan scrolls the page instead of
  /// moving the picture.
  final ValueChanged<bool>? onZoomChanged;

  const RfVideoPlayer({super.key, required this.path, this.onZoomChanged});

  @override
  State<RfVideoPlayer> createState() => _RfVideoPlayerState();
}

class _RfVideoPlayerState extends State<RfVideoPlayer> {
  VideoPlayerController? _ctrl;
  bool _failed = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      final file = File(widget.path);
      if (!await file.exists()) {
        if (mounted) setState(() { _failed = true; _errorMessage = 'File missing'; });
        return;
      }
      final c = VideoPlayerController.file(file);
      _ctrl = c;
      await c.initialize();
      if (!mounted) return;
      setState(() {});
    } catch (e) {
      debugPrint('Video init failed: $e');
      if (mounted) setState(() { _failed = true; _errorMessage = e.toString(); });
    }
  }

  @override
  void dispose() {
    _ctrl?.dispose();
    super.dispose();
  }

  Widget _box(Widget child) => Container(
        height: 200,
        decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12)),
        child: Center(child: child),
      );

  @override
  Widget build(BuildContext context) {
    if (_failed) {
      return _box(Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.broken_image, color: Colors.white24, size: 40),
        const SizedBox(height: 8),
        Text(_errorMessage ?? 'Could not load video',
            style: const TextStyle(color: RfColors.textSecondary, fontSize: 12)),
      ]));
    }
    final c = _ctrl;
    if (c == null || !c.value.isInitialized) {
      return _box(const CircularProgressIndicator(color: RfColors.textMuted));
    }

    final aspect = videoDisplayAspect(size: c.value.size, aspectRatio: c.value.aspectRatio);
    return LayoutBuilder(builder: (context, constraints) {
      final h = (constraints.maxWidth / aspect).clamp(220.0, 520.0);
      return ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Container(
          height: h,
          color: Colors.black,
          child: _VideoStage(
            controller: c,
            fullscreen: false,
            onZoomChanged: widget.onZoomChanged,
            topActions: [
              _OverlayIconButton(
                icon: Icons.fullscreen_rounded,
                tooltip: 'Full screen',
                onPressed: () => openRfVideoFullscreen(context, c),
              ),
            ],
          ),
        ),
      );
    });
  }
}

/// Opens [controller] full screen. The route does not own the controller.
Future<void> openRfVideoFullscreen(BuildContext context, VideoPlayerController controller) {
  return Navigator.of(context).push<void>(PageRouteBuilder<void>(
    transitionDuration: const Duration(milliseconds: 200),
    reverseTransitionDuration: const Duration(milliseconds: 160),
    pageBuilder: (_, __, ___) => _RfVideoFullscreenPage(controller: controller),
    transitionsBuilder: (_, animation, __, child) => FadeTransition(opacity: animation, child: child),
  ));
}

class _RfVideoFullscreenPage extends StatefulWidget {
  final VideoPlayerController controller;
  const _RfVideoFullscreenPage({required this.controller});

  @override
  State<_RfVideoFullscreenPage> createState() => _RfVideoFullscreenPageState();
}

class _RfVideoFullscreenPageState extends State<_RfVideoFullscreenPage> {
  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _keepAwake(true);
  }

  @override
  void dispose() {
    // Same restore the capture screen does when it leaves.
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    _keepAwake(false);
    super.dispose();
  }

  Future<void> _keepAwake(bool on) async {
    try {
      if (on) {
        await WakelockPlus.enable();
      } else {
        await WakelockPlus.disable();
      }
    } catch (e) {
      debugPrint('Wakelock failed (non-fatal): $e');
    }
  }

  /// The device may have auto-rotate off, so a button flips between portrait
  /// and landscape. It stays pinned until the button is tapped again or the
  /// player closes (freeing it earlier would snap straight back to whichever
  /// way the phone is held).
  void _rotate() {
    final portrait = MediaQuery.orientationOf(context) == Orientation.portrait;
    SystemChrome.setPreferredOrientations(
      portrait
          ? const [DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight]
          : const [DeviceOrientation.portraitUp],
    );
  }

  void _close() => Navigator.of(context).maybePop();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: _VideoStage(
        controller: widget.controller,
        fullscreen: true,
        onDismiss: _close,
        topLeading: _OverlayIconButton(
          icon: Icons.arrow_back_rounded,
          tooltip: 'Close full screen',
          onPressed: _close,
        ),
        topActions: [
          _OverlayIconButton(
            icon: Icons.screen_rotation_rounded,
            tooltip: 'Rotate',
            onPressed: _rotate,
          ),
        ],
      ),
    );
  }
}

// ─── The playing surface: gestures + controls ────────────────────────────

class _VideoStage extends StatefulWidget {
  final VideoPlayerController controller;
  final bool fullscreen;
  final Widget? topLeading;
  final List<Widget> topActions;
  final ValueChanged<bool>? onZoomChanged;

  /// Swipe-down on the picture (full screen only).
  final VoidCallback? onDismiss;

  const _VideoStage({
    required this.controller,
    required this.fullscreen,
    this.topLeading,
    this.topActions = const [],
    this.onZoomChanged,
    this.onDismiss,
  });

  @override
  State<_VideoStage> createState() => _VideoStageState();
}

class _VideoStageState extends State<_VideoStage>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  static const _hideAfter = Duration(milliseconds: 3500);
  static const _skipChain = Duration(milliseconds: 1000);

  late final TransformationController _zoom;
  late final AnimationController _zoomAnim;
  Matrix4 _zoomFrom = Matrix4.identity();
  Matrix4 _zoomTo = Matrix4.identity();
  bool _zoomed = false;

  bool _controlsVisible = true;
  bool _wasPlaying = false;
  Timer? _hideTimer;

  Size _viewport = Size.zero;
  Offset _tapPos = Offset.zero;
  Offset _doubleTapPos = Offset.zero;

  // Skip feedback ("« 10 sec") and the chain of repeated skips.
  VideoTapZone _flashZone = VideoTapZone.forward;
  bool _flashOn = false;
  int _flashSeconds = 0;
  Duration? _flashTarget;
  Timer? _flashTimer;

  // Scrubbing, from the seek bar or a sideways swipe.
  bool _scrubbing = false;
  Duration? _scrubPos;
  bool _resumeAfterScrub = false;
  DateTime _lastLiveSeek = DateTime.fromMillisecondsSinceEpoch(0);
  bool _swipeActive = false;
  double _swipeDx = 0;
  Duration _swipeBase = Duration.zero;
  double _pullDy = 0;

  VideoPlayerController get _c => widget.controller;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _zoom = TransformationController()..addListener(_onZoomTick);
    _zoomAnim = AnimationController(vsync: this, duration: const Duration(milliseconds: 220))
      ..addListener(() {
        _zoom.value = lerpZoom(_zoomFrom, _zoomTo, Curves.easeOutCubic.transform(_zoomAnim.value));
      });
    _wasPlaying = _c.value.isPlaying;
    _c.addListener(_onController);
    _restartHideTimer();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _c.removeListener(_onController);
    _hideTimer?.cancel();
    _flashTimer?.cancel();
    _zoomAnim.dispose();
    _zoom.dispose();
    if (_zoomed && widget.onZoomChanged != null) {
      // The parent may be mid-teardown; tell it once the frame is done.
      final cb = widget.onZoomChanged!;
      WidgetsBinding.instance.addPostFrameCallback((_) => cb(false));
    }
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Only a real trip to the background; `inactive` also fires for the
    // notification shade and system dialogs.
    final away = state == AppLifecycleState.paused || state == AppLifecycleState.hidden;
    if (away && _c.value.isPlaying) unawaited(_c.pause());
  }

  void _onController() {
    if (!mounted) return;
    final playing = _c.value.isPlaying;
    if (playing != _wasPlaying) {
      _wasPlaying = playing;
      if (!playing) _controlsVisible = true;
      _restartHideTimer();
    }
    setState(() {});
  }

  void _onZoomTick() {
    final z = isVideoZoomed(_zoom.value);
    if (z == _zoomed) return;
    setState(() => _zoomed = z);
    widget.onZoomChanged?.call(z);
  }

  bool get _showUi => _controlsVisible || !_c.value.isPlaying || _scrubbing;

  void _restartHideTimer() {
    _hideTimer?.cancel();
    if (!_c.value.isPlaying || _scrubbing) return;
    _hideTimer = Timer(_hideAfter, () {
      if (mounted && _c.value.isPlaying && !_scrubbing) {
        setState(() => _controlsVisible = false);
      }
    });
  }

  bool _atEnd(VideoPlayerValue v) =>
      v.duration > Duration.zero && v.position >= v.duration - const Duration(milliseconds: 250);

  // ── Play / pause / speed ────────────────────────────────────────────────

  Future<void> _togglePlay() async {
    final v = _c.value;
    if (v.isPlaying) {
      await _c.pause();
    } else {
      if (_atEnd(v)) await _c.seekTo(Duration.zero);
      await _c.play();
    }
    _restartHideTimer();
  }

  void _cycleSpeed() {
    unawaited(_c.setPlaybackSpeed(nextVideoSpeed(_c.value.playbackSpeed)));
    _restartHideTimer();
  }

  // ── Taps ────────────────────────────────────────────────────────────────

  void _onTap() {
    // Inside a skip chain a single tap on an edge keeps skipping.
    if (_flashTimer?.isActive ?? false) {
      final zone = videoTapZone(_tapPos.dx, _viewport.width);
      if (zone != VideoTapZone.middle) {
        _skip(zone);
        return;
      }
    }
    setState(() => _controlsVisible = !_showUi);
    _restartHideTimer();
  }

  void _onDoubleTap() {
    final zone = videoTapZone(_doubleTapPos.dx, _viewport.width);
    if (zone == VideoTapZone.middle) {
      _toggleZoomAt(_doubleTapPos);
    } else {
      _skip(zone);
    }
  }

  void _skip(VideoTapZone zone) {
    final v = _c.value;
    final chained = _flashTimer?.isActive ?? false;
    // A skip is asked of the position the LAST skip aimed at: the player only
    // reports the new position a moment later, and quick taps would all start
    // from the old one.
    final base = chained && _flashTarget != null ? _flashTarget! : v.position;
    final delta = Duration(seconds: zone == VideoTapZone.back ? -kVideoSkipSeconds : kVideoSkipSeconds);
    final target = seekClamped(base, v.duration, delta);
    _flashTarget = target;
    unawaited(_c.seekTo(target));
    HapticFeedback.selectionClick();
    setState(() {
      _flashSeconds = chained && _flashZone == zone ? _flashSeconds + kVideoSkipSeconds : kVideoSkipSeconds;
      _flashZone = zone;
      _flashOn = true;
    });
    _flashTimer?.cancel();
    _flashTimer = Timer(_skipChain, () {
      if (!mounted) return;
      setState(() => _flashOn = false);
    });
  }

  // ── Zoom ────────────────────────────────────────────────────────────────

  void _animateZoom(Matrix4 to) {
    _zoomFrom = _zoom.value.clone();
    _zoomTo = to;
    _zoomAnim.forward(from: 0);
  }

  void _toggleZoomAt(Offset focal) {
    _animateZoom(_zoomed ? Matrix4.identity() : zoomAbout(focal, kVideoDoubleTapZoom));
  }

  // ── Scrubbing ───────────────────────────────────────────────────────────

  void _scrubStart() {
    _resumeAfterScrub = _c.value.isPlaying;
    if (_resumeAfterScrub) unawaited(_c.pause());
    _hideTimer?.cancel();
    setState(() {
      _scrubbing = true;
      _scrubPos = _c.value.position;
    });
  }

  void _scrub(Duration t) {
    setState(() => _scrubPos = t);
    // Show the frame under the thumb while it moves, not only on release.
    final now = DateTime.now();
    if (now.difference(_lastLiveSeek) > const Duration(milliseconds: 120)) {
      _lastLiveSeek = now;
      unawaited(_c.seekTo(t));
    }
  }

  Future<void> _scrubEnd(Duration t) async {
    final resume = _resumeAfterScrub;
    _resumeAfterScrub = false;
    if (mounted) {
      setState(() {
        _scrubbing = false;
        _scrubPos = null;
      });
    }
    await _c.seekTo(t);
    if (resume && t < _c.value.duration - const Duration(milliseconds: 250)) {
      await _c.play();
    }
    _restartHideTimer();
  }

  void _swipeStart(DragStartDetails d) {
    _swipeActive = true;
    _swipeDx = 0;
    _swipeBase = _c.value.position;
    _scrubStart();
  }

  void _swipeUpdate(DragUpdateDetails d) {
    if (!_swipeActive) return;
    _swipeDx += d.delta.dx;
    _scrub(scrubTarget(
      start: _swipeBase,
      dx: _swipeDx,
      width: _viewport.width,
      duration: _c.value.duration,
    ));
  }

  void _swipeEnd([DragEndDetails? _]) {
    // Also called on cancel, including for drags that never started.
    if (!_swipeActive) return;
    _swipeActive = false;
    unawaited(_scrubEnd(_scrubPos ?? _swipeBase));
  }

  // ── Build ───────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final v = _c.value;
    final showUi = _showUi;
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned.fill(child: _buildGestureLayer(v)),
        if (_scrubbing && _scrubPos != null)
          Center(child: IgnorePointer(child: _TimePill(position: _scrubPos!, duration: v.duration))),
        _buildSkipFlash(),
        Positioned.fill(
          child: IgnorePointer(
            ignoring: !showUi,
            child: AnimatedOpacity(
              opacity: showUi ? 1 : 0,
              duration: RfDuration.controlsFade,
              child: _buildControls(v),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildGestureLayer(VideoPlayerValue v) {
    final aspect = videoDisplayAspect(size: v.size, aspectRatio: v.aspectRatio);
    return LayoutBuilder(builder: (context, constraints) {
      _viewport = constraints.biggest;
      final canSwipe = !_zoomed;
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (d) => _tapPos = d.localPosition,
        onTap: _onTap,
        onDoubleTapDown: (d) => _doubleTapPos = d.localPosition,
        onDoubleTap: _onDoubleTap,
        // Not zoomed: sideways = scrub. Zoomed: these are off, so the
        // InteractiveViewer below gets every drag and pans the picture.
        onHorizontalDragStart: canSwipe ? _swipeStart : null,
        onHorizontalDragUpdate: canSwipe ? _swipeUpdate : null,
        onHorizontalDragEnd: canSwipe ? _swipeEnd : null,
        onHorizontalDragCancel: canSwipe ? _swipeEnd : null,
        onVerticalDragStart: canSwipe && widget.onDismiss != null ? (_) => _pullDy = 0 : null,
        onVerticalDragUpdate: canSwipe && widget.onDismiss != null ? (d) => _pullDy += d.delta.dy : null,
        onVerticalDragEnd: canSwipe && widget.onDismiss != null
            ? (d) {
                if (_pullDy > 140 || (d.primaryVelocity ?? 0) > 900) widget.onDismiss!();
              }
            : null,
        child: InteractiveViewer(
          transformationController: _zoom,
          minScale: 1.0,
          maxScale: kVideoMaxZoom,
          onInteractionStart: (_) => _zoomAnim.stop(),
          child: SizedBox.expand(
            child: Center(
              child: AspectRatio(aspectRatio: aspect, child: VideoPlayer(_c)),
            ),
          ),
        ),
      );
    });
  }

  Widget _buildSkipFlash() {
    final back = _flashZone == VideoTapZone.back;
    return Positioned.fill(
      child: IgnorePointer(
        child: Align(
          alignment: Alignment(back ? -0.62 : 0.62, 0),
          child: AnimatedOpacity(
            opacity: _flashOn ? 1 : 0,
            duration: const Duration(milliseconds: 160),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              decoration: BoxDecoration(
                color: Colors.black.withAlpha(120),
                borderRadius: BorderRadius.circular(40),
              ),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(back ? Icons.fast_rewind_rounded : Icons.fast_forward_rounded,
                    color: Colors.white, size: 30),
                const SizedBox(height: 2),
                Text('$_flashSeconds sec',
                    style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
              ]),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildControls(VideoPlayerValue v) {
    final inset = widget.fullscreen ? MediaQuery.paddingOf(context) : EdgeInsets.zero;
    final atEnd = _atEnd(v) && !v.isPlaying;
    final shownPos = _scrubPos ?? v.position;
    const timeStyle = TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace');

    return Stack(
      children: [
        Positioned(
          top: 0, left: 0, right: 0,
          child: IgnorePointer(
            child: Container(
              height: 96 + inset.top,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x99000000), Color(0x00000000)],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          bottom: 0, left: 0, right: 0,
          child: IgnorePointer(
            child: Container(
              height: 120 + inset.bottom,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x00000000), Color(0xB3000000)],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          top: inset.top + 4,
          left: inset.left + 8,
          right: inset.right + 8,
          child: Row(children: [
            if (widget.topLeading != null) widget.topLeading!,
            const Spacer(),
            _SpeedChip(speed: v.playbackSpeed, onTap: _cycleSpeed),
            if (_zoomed) ...[
              const SizedBox(width: 6),
              _OverlayIconButton(
                icon: Icons.zoom_out_map_rounded,
                tooltip: 'Reset zoom',
                onPressed: () => _animateZoom(Matrix4.identity()),
              ),
            ],
            for (final a in widget.topActions) ...[const SizedBox(width: 6), a],
          ]),
        ),
        Center(
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            _OverlayIconButton(
              icon: Icons.replay_10_rounded,
              tooltip: 'Back 10 seconds',
              size: 56,
              iconSize: 30,
              onPressed: () => _skip(VideoTapZone.back),
            ),
            const SizedBox(width: 20),
            _OverlayIconButton(
              icon: atEnd
                  ? Icons.replay_rounded
                  : (v.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded),
              tooltip: atEnd ? 'Replay' : (v.isPlaying ? 'Pause' : 'Play'),
              size: 68,
              iconSize: 42,
              onPressed: _togglePlay,
            ),
            const SizedBox(width: 20),
            _OverlayIconButton(
              icon: Icons.forward_10_rounded,
              tooltip: 'Forward 10 seconds',
              size: 56,
              iconSize: 30,
              onPressed: () => _skip(VideoTapZone.forward),
            ),
          ]),
        ),
        Positioned(
          left: inset.left + 12,
          right: inset.right + 12,
          bottom: inset.bottom + 4,
          child: Row(children: [
            Text(formatVideoTime(shownPos), style: timeStyle),
            Expanded(
              child: RfSeekBar(
                position: v.position,
                duration: v.duration,
                onScrubStart: _scrubStart,
                onScrub: _scrub,
                onScrubEnd: (t) => unawaited(_scrubEnd(t)),
              ),
            ),
            Text(formatVideoTime(v.duration), style: timeStyle),
          ]),
        ),
      ],
    );
  }
}

// ─── Small pieces ────────────────────────────────────────────────────────

/// Round translucent icon button with a 48 dp (or bigger) touch target.
class _OverlayIconButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final double size;
  final double iconSize;

  const _OverlayIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.size = 48,
    this.iconSize = 26,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Semantics(
        button: true,
        label: tooltip,
        child: SizedBox(
          width: size,
          height: size,
          child: Material(
            color: Colors.black.withAlpha(120),
            shape: const CircleBorder(),
            clipBehavior: Clip.antiAlias,
            // The whole disc is the touch target, not just a 48 dp core.
            child: InkWell(
              onTap: onPressed,
              child: Center(child: Icon(icon, size: iconSize, color: Colors.white)),
            ),
          ),
        ),
      ),
    );
  }
}

class _SpeedChip extends StatelessWidget {
  final double speed;
  final VoidCallback onTap;
  const _SpeedChip({required this.speed, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Playback speed',
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        // 48 dp tall touch area around a 32 dp pill.
        child: SizedBox(
          height: 48,
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: Colors.black.withAlpha(120),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white24),
              ),
              child: Text(
                formatVideoSpeed(speed),
                style: TextStyle(
                  color: (speed - 1.0).abs() < 0.01 ? Colors.white : RfColors.amber,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// "01:23 / 03:10" shown over the picture while scrubbing.
class _TimePill extends StatelessWidget {
  final Duration position;
  final Duration duration;
  const _TimePill({required this.position, required this.duration});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.black.withAlpha(150),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        '${formatVideoTime(position)} / ${formatVideoTime(duration)}',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          fontFamily: 'monospace',
        ),
      ),
    );
  }
}

/// Seek bar with a 48 dp tall touch target (the line itself is thin): tap
/// anywhere on it to jump, drag the thumb to scrub, with a time bubble above
/// the thumb while it is held.
///
/// [onScrubStart] / [onScrub] / [onScrubEnd] frame a scrub; a plain tap is a
/// start immediately followed by an end at the tapped spot.
class RfSeekBar extends StatefulWidget {
  final Duration position;
  final Duration duration;
  final VoidCallback? onScrubStart;
  final ValueChanged<Duration>? onScrub;
  final ValueChanged<Duration>? onScrubEnd;

  const RfSeekBar({
    super.key,
    required this.position,
    required this.duration,
    this.onScrubStart,
    this.onScrub,
    this.onScrubEnd,
  });

  /// Room kept at each end so the thumb is not clipped there.
  static const double thumbPad = 14;

  /// Height of the whole touch target.
  static const double height = 48;

  @override
  State<RfSeekBar> createState() => _RfSeekBarState();
}

class _RfSeekBarState extends State<RfSeekBar> {
  /// Fraction under the finger while scrubbing; null otherwise.
  double? _drag;

  double _fractionFor(double dx, double width) {
    final track = width - 2 * RfSeekBar.thumbPad;
    if (track <= 0) return 0;
    return ((dx - RfSeekBar.thumbPad) / track).clamp(0.0, 1.0);
  }

  Duration _at(double f) => Duration(milliseconds: (widget.duration.inMilliseconds * f).round());

  double get _fraction {
    if (_drag != null) return _drag!;
    final total = widget.duration.inMilliseconds;
    if (total <= 0) return 0;
    return (widget.position.inMilliseconds / total).clamp(0.0, 1.0);
  }

  void _dragStart(double dx, double w) {
    widget.onScrubStart?.call();
    final f = _fractionFor(dx, w);
    setState(() => _drag = f);
    widget.onScrub?.call(_at(f));
  }

  void _dragUpdate(double dx, double w) {
    if (_drag == null) return;
    final f = _fractionFor(dx, w);
    setState(() => _drag = f);
    widget.onScrub?.call(_at(f));
  }

  void _dragEnd() {
    final f = _drag;
    if (f == null) return; // also fires for drags that never started
    setState(() => _drag = null);
    widget.onScrubEnd?.call(_at(f));
  }

  void _tap(double dx, double w) {
    final t = _at(_fractionFor(dx, w));
    widget.onScrubStart?.call();
    widget.onScrubEnd?.call(t);
  }

  @override
  Widget build(BuildContext context) {
    final dragging = _drag != null;
    return Semantics(
      label: 'Video position',
      value: '${formatVideoTime(widget.position)} of ${formatVideoTime(widget.duration)}',
      child: LayoutBuilder(builder: (context, constraints) {
        final w = constraints.maxWidth;
        final track = w - 2 * RfSeekBar.thumbPad;
        final thumbX = RfSeekBar.thumbPad + (track > 0 ? track * _fraction : 0);
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapUp: (d) => _tap(d.localPosition.dx, w),
          onHorizontalDragStart: (d) => _dragStart(d.localPosition.dx, w),
          onHorizontalDragUpdate: (d) => _dragUpdate(d.localPosition.dx, w),
          onHorizontalDragEnd: (_) => _dragEnd(),
          onHorizontalDragCancel: _dragEnd,
          child: SizedBox(
            height: RfSeekBar.height,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: _SeekPainter(fraction: _fraction, active: dragging),
                  ),
                ),
                if (dragging)
                  Positioned(
                    left: thumbX - 30,
                    width: 60,
                    top: -34,
                    child: IgnorePointer(
                      child: Container(
                        alignment: Alignment.center,
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black.withAlpha(190),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          formatVideoTime(_at(_drag!)),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            fontFamily: 'monospace',
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      }),
    );
  }
}

class _SeekPainter extends CustomPainter {
  final double fraction;
  final bool active;
  const _SeekPainter({required this.fraction, required this.active});

  @override
  void paint(Canvas canvas, Size size) {
    final cy = size.height / 2;
    final left = RfSeekBar.thumbPad;
    final right = size.width - RfSeekBar.thumbPad;
    if (right <= left) return;
    final trackH = active ? 6.0 : 4.0;
    final x = left + (right - left) * fraction;

    RRect bar(double from, double to) => RRect.fromRectAndRadius(
          Rect.fromLTRB(from, cy - trackH / 2, to, cy + trackH / 2),
          Radius.circular(trackH / 2),
        );

    canvas.drawRRect(bar(left, right), Paint()..color = Colors.white24);
    canvas.drawRRect(bar(left, x), Paint()..color = RfColors.pkAccent);

    final r = active ? 10.0 : 7.0;
    canvas.drawCircle(Offset(x, cy), r + 1.5, Paint()..color = Colors.black38);
    canvas.drawCircle(Offset(x, cy), r, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(_SeekPainter old) => old.fraction != fraction || old.active != active;
}
