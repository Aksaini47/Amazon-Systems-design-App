import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/rf_colors.dart';

/// RepairFully Camera App buttons — Mahika doctrine.
///
/// Authority: `~/.claude/skills/mahika.md §IV "BUTTON STANDARDS" + §V
/// "SMOOTH ANIMATIONS"`.
///
/// **Visual language:**
///   - Solid fill (no gradients, no inner bevels) — clean operational look
///   - 10px border radius (Mahika §IV — `BorderRadius.circular(10)`)
///   - 48dp minimum touch target (Material guideline + Mahika §IV)
///   - FontWeight 600 for labels
///   - Material outlined icons for status, filled rounded for primary actions
///
/// **Press feedback (Mahika §V #1 — canonical pattern):**
///   - `ScaleTransition` driven by AnimationController
///   - Scale 1.0 → 0.95 on press-down
///   - 200ms `Curves.easeOut`
///   - Reverses on tap-up / cancel
///   - Pairs with a `HapticFeedback.selectionClick()` on release
///   - Light color-deepen layered on top (visual confirmation)
///
/// **Variants (semantic, not promotional):**
///   - [RfButton.primary]   — action coral fill, white text (SAVE / CAPTURE / CONFIRM)
///   - [RfButton.service]   — navy fill, white text (ACCEPT / VIEW)
///   - [RfButton.secondary] — transparent + 1px white border (CANCEL / BACK / SKIP)
///   - [RfButton.danger]    — error red fill, white text (DELETE / FLAG)
///   - [RfButton.tonal]     — small chip-style toggle (zoom/aspect rows)
class RfButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final RfButtonVariant variant;
  final RfButtonSize size;
  final bool fullWidth;
  final bool active;  // for tonal toggles

  const RfButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.variant = RfButtonVariant.primary,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.active = false,
  });

  const RfButton.primary({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.active = false,
  }) : variant = RfButtonVariant.primary;

  const RfButton.service({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.active = false,
  }) : variant = RfButtonVariant.service;

  const RfButton.secondary({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.active = false,
  }) : variant = RfButtonVariant.secondary;

  const RfButton.danger({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.medium,
    this.fullWidth = false,
    this.active = false,
  }) : variant = RfButtonVariant.danger;

  const RfButton.tonal({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.size = RfButtonSize.small,
    this.fullWidth = false,
    this.active = false,
  }) : variant = RfButtonVariant.tonal;

  @override
  State<RfButton> createState() => _RfButtonState();
}

enum RfButtonVariant { primary, service, secondary, danger, tonal }

enum RfButtonSize { small, medium, large }

class _RfButtonState extends State<RfButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  bool _hover = false;  // tracks tap-down for color-deepen

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: RfDuration.press,
      lowerBound: 0.0,
      upperBound: 1.0,
    );
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

  ({Color fill, Color text, Color? border}) _palette() {
    final pressed = _hover;
    Color darker(Color c, [double amount = 0.12]) => Color.lerp(c, Colors.black, amount)!;

    switch (widget.variant) {
      case RfButtonVariant.primary:
        return (
          fill: pressed ? darker(RfColors.action) : RfColors.action,
          text: Colors.white,
          border: null,
        );
      case RfButtonVariant.service:
        return (
          fill: pressed ? darker(RfColors.navy, 0.2) : RfColors.navy,
          text: Colors.white,
          border: null,
        );
      case RfButtonVariant.secondary:
        return (
          fill: pressed ? RfColors.glassFill(0.22) : RfColors.glassFill(0.10),
          text: Colors.white,
          border: RfColors.glassBorder(pressed ? 0.35 : 0.28),
        );
      case RfButtonVariant.danger:
        return (
          fill: pressed ? RfColors.errorDark : RfColors.error,
          text: Colors.white,
          border: null,
        );
      case RfButtonVariant.tonal:
        return widget.active
            ? (
                fill: pressed ? const Color(0xFFE5E7EB) : Colors.white,
                text: RfColors.navy,
                border: null,
              )
            : (
                fill: pressed ? RfColors.glassFill(0.28) : RfColors.glassFill(0.12),
                text: Colors.white,
                border: RfColors.glassBorder(0.24),
              );
    }
  }

  @override
  Widget build(BuildContext context) {
    final dims = _dims();
    final palette = _palette();
    final disabled = widget.onPressed == null;

    final body = Container(
      height: dims.h,
      padding: EdgeInsets.symmetric(horizontal: dims.padH),
      decoration: BoxDecoration(
        color: palette.fill,
        borderRadius: BorderRadius.circular(RfRadius.button),
        border: palette.border != null ? Border.all(color: palette.border!, width: 1) : null,
      ),
      child: Row(
        mainAxisSize: widget.fullWidth ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (widget.icon != null) ...[
            Icon(widget.icon, size: dims.iconSize, color: palette.text),
            SizedBox(width: widget.label.isEmpty ? 0 : 8),
          ],
          if (widget.label.isNotEmpty)
            Text(
              widget.label,
              style: TextStyle(
                color: palette.text,
                fontSize: dims.font,
                fontWeight: FontWeight.w600,
              ),
            ),
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

/// Compact toggle chip — for zoom + aspect rows in camera UI.
/// ScaleTransition press matches RfButton (consistent feel across the app).
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
    final fill = widget.active
        ? Colors.white
        : RfColors.glassFill(0.12);
    final textColor = widget.active ? RfColors.navy : Colors.white;
    final borderColor = widget.active ? Colors.transparent : RfColors.glassBorder(0.24);

    final visual = Container(
      constraints: BoxConstraints(minWidth: widget.minWidth ?? 0, minHeight: 36),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(RfRadius.chip),
        border: Border.all(color: borderColor, width: 1),
      ),
      child: Center(
        child: Text(
          widget.label,
          style: TextStyle(
            color: textColor,
            fontSize: 13,
            fontWeight: widget.active ? FontWeight.w700 : FontWeight.w600,
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

/// Circular icon button — for AppBar close X, mic-mute toggle, etc.
/// ScaleTransition press matches RfButton.
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
    final bg = widget.bgColor ?? RfColors.glassFill(0.18);
    final fg = widget.color ?? Colors.white;
    final pressedBg = Color.lerp(bg, Colors.black, 0.25)!;

    final visual = Container(
      width: widget.size,
      height: widget.size,
      decoration: BoxDecoration(
        color: _pressed ? pressedBg : bg,
        shape: BoxShape.circle,
        border: Border.all(color: RfColors.glassBorder(0.28), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
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
  const RfRecordingPulse({super.key, this.size = 12, this.color = const Color(0xFFFF7B72)});

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
