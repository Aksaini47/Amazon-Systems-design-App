import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';

/// RepairFully Camera App buttons — tinted liquid-glass pills.
///
/// **Visual language (2026-10-10 revamp, Sir):**
///   - Fully-rounded pill ([RfRadius.pill]) on [RfGlassSurface]: a translucent
///     tint with a top sheen, a thin gradient rim and a specular arc. No
///     drop shadow, no backdrop blur (buttons also sit over a live camera).
///   - 48dp minimum touch target (Material guideline + Mahika §IV)
///   - FontWeight 600 labels, white on filled tints
///   - Optional trailing chevron on full-width CTAs ([RfButton.trailingChevron])
///
/// **Press feedback (Mahika §V #1 — canonical pattern):**
///   - `ScaleTransition` 1.0 → 0.95 over 200ms `Curves.easeOut`, reversing on
///     tap-up / cancel, with a `HapticFeedback.selectionClick()` on release
///   - The glass deepens (a little more tint, less sheen) while pressed
///
/// **Variants (semantic, not promotional):**
///   - [RfButton.primary]   — terracotta glass (SAVE / SCAN / CONFIRM)
///   - [RfButton.service]   — blue glass (ACCEPT / VIEW)
///   - [RfButton.secondary] — clear glass (CANCEL / BACK / SKIP); an
///     `accentColor` tints the rim, fill and label
///   - [RfButton.danger]    — red glass (DELETE / FLAG)
///
/// For chip-style toggles (zoom/aspect rows) use [RfChip], not RfButton.
class RfButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final RfButtonVariant variant;
  final RfButtonSize size;
  final bool fullWidth;
  /// Tints text/icon/fill — honored only by [RfButtonVariant.secondary], for
  /// the handful of spots that color-code an otherwise-neutral action (e.g.
  /// rtAccent/pkAccent). Ignored by every other variant.
  final Color? accentColor;
  /// Left-aligned label with a `>` at the right end — the call-to-action look.
  /// Only applies together with [fullWidth].
  final bool trailingChevron;

  const RfButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.variant = RfButtonVariant.primary,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.accentColor,
    this.trailingChevron = false,
  });

  const RfButton.primary({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.trailingChevron = false,
  })  : variant = RfButtonVariant.primary,
        accentColor = null;

  const RfButton.service({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.trailingChevron = false,
  })  : variant = RfButtonVariant.service,
        accentColor = null;

  const RfButton.secondary({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.accentColor,
    this.trailingChevron = false,
  }) : variant = RfButtonVariant.secondary;

  const RfButton.danger({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.trailingChevron = false,
  })  : variant = RfButtonVariant.danger,
        accentColor = null;

  @override
  State<RfButton> createState() => _RfButtonState();
}

enum RfButtonVariant { primary, service, secondary, danger }

enum RfButtonSize { small, medium, large }

class _RfButtonState extends State<RfButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  bool _hover = false;  // tracks tap-down for the glass deepen

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    // 1.0 → 0.95 on press, matching Mahika §V #1 spec.
    _scale = Tween<double>(begin: 1.0, end: 0.95)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _down() {
    if (widget.onPressed == null) return;
    _ctrl.forward();
    setState(() => _hover = true);
  }

  void _up() {
    if (widget.onPressed == null) return;
    _ctrl.reverse();
    setState(() => _hover = false);
  }

  ({double h, double padH, double font, double iconSize}) _dims() {
    switch (widget.size) {
      case RfButtonSize.small:
        return (h: RfButtonHeight.chip, padH: 14, font: 13, iconSize: 16);
      case RfButtonSize.medium:
        return (h: RfButtonHeight.standard, padH: 20, font: 14, iconSize: 18);
      case RfButtonSize.large:
        return (h: RfButtonHeight.large, padH: 24, font: 16, iconSize: 20);
    }
  }

  ({Color tint, double strength, Color text}) _style() {
    switch (widget.variant) {
      case RfButtonVariant.primary:
        return (tint: RfColors.action, strength: 0.72, text: Colors.white);
      case RfButtonVariant.service:
        return (tint: RfColors.info, strength: 0.60, text: Colors.white);
      case RfButtonVariant.secondary:
        final accent = widget.accentColor;
        return accent != null
            ? (tint: accent, strength: 0.16, text: accent)
            : (tint: Colors.white, strength: 0.08, text: RfColors.textPrimary);
      case RfButtonVariant.danger:
        return (tint: RfColors.error, strength: 0.66, text: Colors.white);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dims = _dims();
    final style = _style();
    final disabled = widget.onPressed == null;
    final cta = widget.trailingChevron && widget.fullWidth;

    final label = widget.label.isEmpty
        ? null
        : Text(
            widget.label,
            overflow: TextOverflow.ellipsis,
            softWrap: false,
            textAlign: cta ? TextAlign.left : TextAlign.center,
            style: TextStyle(
              color: style.text,
              fontSize: dims.font,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.1,
            ),
          );

    final body = RfGlassSurface(
      tint: style.tint,
      strength: style.strength,
      pressed: _hover,
      height: dims.h,
      padding: EdgeInsets.symmetric(horizontal: dims.padH),
      child: Row(
        mainAxisSize: widget.fullWidth ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: cta ? MainAxisAlignment.start : MainAxisAlignment.center,
        children: [
          if (widget.icon != null) ...[
            Icon(widget.icon, size: dims.iconSize, color: style.text),
            SizedBox(width: widget.label.isEmpty ? 0 : 8),
          ],
          if (label != null) cta ? Expanded(child: label) : Flexible(child: label),
          if (cta) Icon(Icons.chevron_right_rounded, size: dims.iconSize + 6, color: style.text),
        ],
      ),
    );

    final visual = Opacity(opacity: disabled ? 0.5 : 1, child: body);

    final scaled = ScaleTransition(scale: _scale, child: visual);

    // Enforce 48x48 minimum hit region without enlarging the visual.
    final hitPad = (dims.h < RfButtonHeight.standard)
        ? (RfButtonHeight.standard - dims.h) / 2
        : 0.0;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: disabled ? null : (_) => _down(),
      onTapUp: disabled ? null : (_) => _up(),
      onTapCancel: disabled ? null : _up,
      onTap: disabled
          ? null
          : () {
              HapticFeedback.selectionClick();
              widget.onPressed!();
            },
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: hitPad),
        child: widget.fullWidth ? SizedBox(width: double.infinity, child: scaled) : scaled,
      ),
    );
  }
}

/// Compact toggle chip — for zoom + aspect rows in camera UI. A glass pill:
/// inactive is clear glass, active is a light (warm-white) glass with dark
/// text so the selected option stays unmistakable. ScaleTransition press
/// matches RfButton (consistent feel across the app).
class RfChip extends StatefulWidget {
  final String label;
  final bool active;
  final VoidCallback? onPressed;
  final double? minWidth;

  const RfChip({
    super.key,
    required this.label,
    required this.active,
    required this.onPressed,
    this.minWidth,
  });

  @override
  State<RfChip> createState() => _RfChipState();
}

class _RfChipState extends State<RfChip> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.95)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final disabled = widget.onPressed == null;
    final active = widget.active;

    final visual = ConstrainedBox(
      constraints: BoxConstraints(minWidth: widget.minWidth ?? 0, minHeight: 36),
      child: RfGlassSurface(
        tint: active ? RfColors.textPrimary : Colors.white,
        strength: active ? 0.90 : 0.08,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        alignment: Alignment.center,
        child: Text(
          widget.label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: active ? RfColors.bg : RfColors.textPrimary,
            fontSize: 13,
            fontWeight: active ? FontWeight.w700 : FontWeight.w600,
          ),
        ),
      ),
    );

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: disabled ? null : (_) => _ctrl.forward(),
      onTapUp: disabled ? null : (_) => _ctrl.reverse(),
      onTapCancel: disabled ? null : () => _ctrl.reverse(),
      onTap: disabled
          ? null
          : () {
              HapticFeedback.selectionClick();
              widget.onPressed!();
            },
      child: ScaleTransition(scale: _scale, child: visual),
    );
  }
}

/// Circular icon button — for AppBar close X, mic-mute toggle, etc. A round
/// glass disc: dark-tinted by default so the white icon stays legible both on
/// the grey canvas and over a bright live camera. ScaleTransition press
/// matches RfButton.
class RfIconButton extends StatefulWidget {
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;
  final Color? bgColor;
  final double size;
  final String? tooltip;

  const RfIconButton({
    super.key,
    required this.icon,
    required this.onPressed,
    this.color,
    this.bgColor,
    this.size = 44,
    this.tooltip,
  });

  @override
  State<RfIconButton> createState() => _RfIconButtonState();
}

class _RfIconButtonState extends State<RfIconButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  bool _pressed = false;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.92)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final disabled = widget.onPressed == null;
    final base = widget.bgColor ?? Colors.black.withValues(alpha: 0.34);
    final fg = widget.color ?? RfColors.textPrimary;

    final visual = RfGlassSurface(
      tint: base.withValues(alpha: 1),
      strength: base.a,
      pressed: _pressed,
      width: widget.size,
      height: widget.size,
      alignment: Alignment.center,
      child: Icon(widget.icon, size: widget.size * 0.5, color: fg.withAlpha(disabled ? 100 : 255)),
    );

    return Tooltip(
      message: widget.tooltip ?? '',
      preferBelow: false,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: disabled ? null : (_) {
          setState(() => _pressed = true);
          _ctrl.forward();
        },
        onTapUp: disabled ? null : (_) {
          setState(() => _pressed = false);
          _ctrl.reverse();
        },
        onTapCancel: disabled ? null : () {
          setState(() => _pressed = false);
          _ctrl.reverse();
        },
        onTap: disabled
            ? null
            : () {
                HapticFeedback.selectionClick();
                widget.onPressed!();
              },
        child: ScaleTransition(scale: _scale, child: visual),
      ),
    );
  }
}

/// Recording pulse — Mahika §V #4 canonical pattern. Used inside the REC
/// indicator dot during active video recording. Endless 1.0 → 1.1 cycle
/// at 1000ms easeInOut to draw the eye without becoming distracting.
class RfRecordingPulse extends StatefulWidget {
  final double size;
  final Color color;
  const RfRecordingPulse({super.key, this.size = 12, this.color = RfColors.recording});

  @override
  State<RfRecordingPulse> createState() => _RfRecordingPulseState();
}

class _RfRecordingPulseState extends State<RfRecordingPulse> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.pulse)..repeat(reverse: true);
    _scale = Tween<double>(begin: 1.0, end: 1.1)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      child: Container(
        width: widget.size,
        height: widget.size,
        decoration: BoxDecoration(shape: BoxShape.circle, color: widget.color),
      ),
    );
  }
}
