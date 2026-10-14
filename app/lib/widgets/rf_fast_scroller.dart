import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';

/// Google-style fast scroller: a slim pill thumb on the right edge that can be
/// grabbed and dragged to leaf through a long list, with a bubble showing
/// where you are (a date, a letter...) while dragging.
///
/// It only watches [controller] and moves it — the scrollable itself is not
/// wrapped or replaced, so text selection, flings and pull-to-refresh keep
/// working. The thumb rests faintly when idle (so it is discoverable), lights
/// up while the list scrolls, and widens while it is being dragged.
///
/// Dragging maps the finger travel onto the whole scroll extent, so the thumb
/// is only as honest as `maxScrollExtent`: give the list exact item extents
/// (fixed / `itemExtentBuilder`) rather than letting it estimate.
class RfFastScroller extends StatefulWidget {
  final ScrollController controller;
  final Widget child;

  /// Bubble text for a given scroll offset (px). Null → no bubble.
  final String Function(double offset)? labelAt;

  /// False hides the thumb (e.g. while the list is not yet its final length).
  final bool enabled;

  /// Space the thumb keeps clear of the top / bottom of the track.
  final double topInset;
  final double bottomInset;

  const RfFastScroller({
    super.key,
    required this.controller,
    required this.child,
    this.labelAt,
    this.enabled = true,
    this.topInset = 4,
    this.bottomInset = 4,
  });

  @override
  State<RfFastScroller> createState() => _RfFastScrollerState();
}

class _RfFastScrollerState extends State<RfFastScroller> {
  static const _thumbHeight = 56.0;
  static const _grabWidth = 44.0;
  static const _idleFade = Duration(milliseconds: 1800);
  static const _accent = RfColors.pkAccent;

  bool _recentlyScrolled = false;
  bool _dragging = false;
  String _label = '';
  Timer? _fadeTimer;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onScroll);
  }

  @override
  void didUpdateWidget(RfFastScroller oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onScroll);
      widget.controller.addListener(_onScroll);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onScroll);
    _fadeTimer?.cancel();
    super.dispose();
  }

  void _onScroll() {
    if (!_recentlyScrolled && mounted) setState(() => _recentlyScrolled = true);
    _armFade();
  }

  void _armFade() {
    _fadeTimer?.cancel();
    _fadeTimer = Timer(_idleFade, () {
      if (mounted && !_dragging) setState(() => _recentlyScrolled = false);
    });
  }

  void _dragStart() {
    final pos = widget.controller.position;
    setState(() {
      _dragging = true;
      _recentlyScrolled = true;
      _label = widget.labelAt?.call(pos.pixels) ?? '';
    });
    HapticFeedback.selectionClick();
  }

  void _dragUpdate(DragUpdateDetails d, double travel) {
    final pos = widget.controller.position;
    final max = pos.maxScrollExtent;
    if (max <= 0 || travel <= 0) return;
    final target = (pos.pixels + d.delta.dy / travel * max).clamp(0.0, max);
    widget.controller.jumpTo(target);
    final label = widget.labelAt?.call(target) ?? '';
    if (label != _label) {
      HapticFeedback.selectionClick();
      setState(() => _label = label);
    }
  }

  void _dragEnd() {
    if (!mounted) return;
    setState(() => _dragging = false);
    _armFade();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Positioned.fill(
          // The controller does not notify when the content or viewport size
          // changes (first layout, rotation, a longer list), but the thumb
          // must appear / resize then — the metrics notification does.
          child: NotificationListener<ScrollMetricsNotification>(
            onNotification: (_) {
              if (mounted) setState(() {});
              return false;
            },
            child: widget.child,
          ),
        ),
        Positioned.fill(
          child: LayoutBuilder(
            builder: (context, constraints) => ListenableBuilder(
              listenable: widget.controller,
              builder: (context, _) => _overlay(constraints.maxHeight),
            ),
          ),
        ),
      ],
    );
  }

  Widget _overlay(double height) {
    final c = widget.controller;
    if (!widget.enabled || !c.hasClients || !c.position.hasContentDimensions) {
      return const SizedBox.shrink();
    }
    final max = c.position.maxScrollExtent;
    final travel = height - widget.topInset - widget.bottomInset - _thumbHeight;
    if (max <= 0 || travel <= 0) return const SizedBox.shrink();

    final fraction = (c.position.pixels / max).clamp(0.0, 1.0);
    final thumbTop = widget.topInset + fraction * travel;
    final lit = _dragging || _recentlyScrolled;

    return Stack(
      clipBehavior: Clip.none,
      children: [
        // Grab zone: opaque, so a drag that starts on the thumb never also
        // scrolls the list underneath. Empty parts of the overlay are not hit,
        // so the list keeps every other touch.
        Positioned(
          right: 0,
          top: thumbTop - 14,
          width: _grabWidth,
          height: _thumbHeight + 28,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onVerticalDragStart: (_) => _dragStart(),
            onVerticalDragUpdate: (d) => _dragUpdate(d, travel),
            onVerticalDragEnd: (_) => _dragEnd(),
            onVerticalDragCancel: _dragEnd,
            child: Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(right: 3),
                child: AnimatedOpacity(
                  duration: const Duration(milliseconds: 220),
                  opacity: lit ? 1 : 0.35,
                  child: AnimatedContainer(
                    key: const Key('rf_fast_scroller_thumb'),
                    duration: const Duration(milliseconds: 140),
                    width: _dragging ? 12 : 6,
                    height: _thumbHeight,
                    child: const RfGlassSurface(
                      tint: _accent,
                      strength: 0.85,
                      child: SizedBox.expand(),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
        if (_dragging && _label.isNotEmpty)
          Positioned(
            right: _grabWidth + 4,
            top: thumbTop + _thumbHeight / 2 - 18,
            child: IgnorePointer(
              child: RfGlassSurface(
                key: const Key('rf_fast_scroller_bubble'),
                tint: _accent,
                // Fully opaque: the bubble sits over text, which must not
                // ghost through it.
                strength: 1,
                shadow: true,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                child: Text(
                  _label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.2,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
