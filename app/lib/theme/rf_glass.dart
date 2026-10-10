import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'rf_colors.dart';

/// Glass design tokens + reusable surfaces for RF Logger.
///
/// 2026-10-10 revamp (Sir): the look is tinted liquid glass on a warm dark
/// grey canvas — translucent tint with a vertical sheen, a thin gradient rim
/// (bright top-left, dim bottom-right) and a short specular arc on the top
/// edge ([RfGlassSurface]). Backdrop blur is reserved for the few surfaces
/// that sit over something worth blurring (dialogs, sheets); over a live
/// camera texture it would re-run every frame, so camera chrome keeps it off.
class RfGlass {
  RfGlass._();

  static const double blurLight = 8;
  static const double blurStandard = 14;
  static const double blurHeavy = 22;

  /// Primary translucent panel fill.
  static Color fill([double opacity = 0.14]) => RfColors.glassFill(opacity);

  /// Slightly denser panel (modals).
  static Color fillElevated([double opacity = 0.22]) =>
      RfColors.glassElevated(opacity);

  /// Hairline glass border.
  static Color border([double opacity = 0.28]) =>
      Colors.white.withValues(alpha: opacity);

  /// Inner top-edge highlight (simulates light refraction).
  static Color highlight([double opacity = 0.10]) =>
      Colors.white.withValues(alpha: opacity);

  static BorderRadius radius([double r = RfRadius.card]) =>
      BorderRadius.circular(r);

  static BoxDecoration decoration({
    double radius = RfRadius.card,
    Color? tint,
    Color? borderColor,
    double borderWidth = 1,
  }) {
    return BoxDecoration(
      borderRadius: BorderRadius.circular(radius),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          (tint ?? fill(0.16)).withValues(alpha: ((tint ?? fill(0.16)).a * 1.15).clamp(0.0, 1.0)),
          tint ?? fill(0.10),
        ],
      ),
      border: Border.all(
        color: borderColor ?? border(0.14),
        width: borderWidth,
      ),
    );
  }

  /// Liquid-glass decoration — like [decoration] but with a brighter
  /// top-left specular highlight, evoking light refracting through curved
  /// glass rather than a flat frosted panel. No box shadow on either: both
  /// are drawn inside a ClipRRect over a translucent fill, so the shadow only
  /// ever showed THROUGH the fill as a muddy darker band.
  static BoxDecoration liquidDecoration({
    double radius = RfRadius.lg,
    Color? tint,
    Color? borderColor,
  }) {
    final base = tint ?? fill(0.16);
    return BoxDecoration(
      borderRadius: BorderRadius.circular(radius),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color.lerp(base, Colors.white, 0.20)!.withValues(alpha: (base.a * 1.7).clamp(0.0, 1.0)),
          base,
          Color.lerp(base, Colors.black, 0.12)!.withValues(alpha: base.a),
        ],
        stops: const [0.0, 0.5, 1.0],
      ),
      border: Border.all(color: borderColor ?? border(0.20)),
    );
  }

  /// Thin specular highlight along the top edge — pair with
  /// [liquidDecoration] as a `Positioned` overlay to simulate light
  /// catching curved glass.
  static Widget specularArc({double radius = RfRadius.lg, double inset = 0.35}) {
    return Positioned(
      top: 1,
      left: 0,
      right: 0,
      child: IgnorePointer(
        child: Container(
          height: 1.4,
          margin: EdgeInsets.symmetric(horizontal: radius * inset),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(2),
            gradient: LinearGradient(
              colors: [
                Colors.white.withValues(alpha: 0),
                Colors.white.withValues(alpha: 0.5),
                Colors.white.withValues(alpha: 0),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Neutral warm-grey canvas gradient — barely there, just enough depth that
  /// the screen is not one flat slab.
  static LinearGradient meshGradient = const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF2B2B29),
      Color(0xFF262624),
      Color(0xFF222221),
    ],
    stops: [0.0, 0.5, 1.0],
  );
}

/// Tinted liquid-glass surface — the one primitive behind every pill, chip
/// and round control.
///
/// [tint] at [strength] opacity forms the glass: a clear glass is white at
/// ~0.08, an accent button is its accent at ~0.7. A vertical sheen lightens
/// the top edge, a thin gradient rim and a short specular arc are painted on
/// top. No backdrop blur unless [blur] > 0 — see the class doc of this file.
class RfGlassSurface extends StatelessWidget {
  final Widget child;
  final Color tint;
  final double strength;
  final double radius;
  final bool pressed;
  final double blur;
  final bool shadow;
  final EdgeInsetsGeometry? padding;
  final AlignmentGeometry? alignment;
  final double? width;
  final double? height;

  const RfGlassSurface({
    super.key,
    required this.child,
    this.tint = Colors.white,
    this.strength = 0.08,
    this.radius = RfRadius.pill,
    this.pressed = false,
    this.blur = 0,
    this.shadow = false,
    this.padding,
    this.alignment,
    this.width,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    final deepen = pressed ? 0.08 : 0.0;
    final top = Color.lerp(tint, Colors.white, pressed ? 0.08 : 0.17)!
        .withValues(alpha: (strength + deepen + 0.09).clamp(0.0, 1.0));
    final bottom = tint.withValues(alpha: (strength + deepen).clamp(0.0, 1.0));
    final shape = BorderRadius.circular(radius);

    Widget body = DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: shape,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [top, bottom],
        ),
        boxShadow: shadow
            ? [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.20),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                  spreadRadius: -2,
                ),
              ]
            : null,
      ),
      child: CustomPaint(
        foregroundPainter: _GlassRimPainter(radius: radius, pressed: pressed),
        child: Container(
          width: width,
          height: height,
          padding: padding,
          alignment: alignment,
          child: child,
        ),
      ),
    );

    if (blur > 0) {
      body = ClipRRect(
        borderRadius: shape,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: body,
        ),
      );
    }
    return body;
  }
}

class _GlassRimPainter extends CustomPainter {
  final double radius;
  final bool pressed;

  const _GlassRimPainter({required this.radius, required this.pressed});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final r = math.min(radius, math.min(size.width, size.height) / 2);
    final rect = Offset.zero & size;
    final k = pressed ? 0.7 : 1.0;

    canvas.drawRRect(
      RRect.fromRectAndRadius(rect.deflate(0.5), Radius.circular(math.max(0, r - 0.5))),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..shader = LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withValues(alpha: 0.62 * k),
            Colors.white.withValues(alpha: 0.14 * k),
            Colors.white.withValues(alpha: 0.30 * k),
          ],
          stops: const [0.0, 0.55, 1.0],
        ).createShader(rect),
    );

    // Specular arc — only along the straight part of the top edge, otherwise
    // it would stick out past the curved corners.
    if (size.width - 2 * r > 14) {
      final x0 = r + 3;
      final x1 = size.width - r - 3;
      canvas.drawLine(
        Offset(x0, 1.3),
        Offset(x1, 1.3),
        Paint()
          ..strokeWidth = 1.2
          ..strokeCap = StrokeCap.round
          ..shader = LinearGradient(
            colors: [
              Colors.white.withValues(alpha: 0),
              Colors.white.withValues(alpha: 0.55 * k),
              Colors.white.withValues(alpha: 0),
            ],
          ).createShader(Rect.fromLTRB(x0, 0, x1, 2)),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _GlassRimPainter old) =>
      old.radius != radius || old.pressed != pressed;
}

/// Ambient background — neutral dark-grey gradient, with an optional grid
/// pattern. No colored glow orbs (Sir 2026-08-11). The grid is opt-in — Home
/// is the only screen with the textured grid; every other screen is the flat
/// grey gradient alone.
class RfGlassBackground extends StatelessWidget {
  final Widget? child;
  final bool showGrid;

  const RfGlassBackground({
    super.key,
    this.child,
    this.showGrid = false,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        DecoratedBox(decoration: BoxDecoration(gradient: RfGlass.meshGradient)),
        if (showGrid)
          CustomPaint(painter: _GlassGridPainter(color: RfColors.textSecondary)),
        if (child != null) child!,
      ],
    );
  }
}

class _GlassGridPainter extends CustomPainter {
  // 2026-10-05 (Sir): 1.5x denser (spacing 32 -> 32/1.5) and much fainter.
  // 2026-10-10: the lines are now a light warm grey on a lighter canvas, so
  // the alpha drops again to keep the same faint look.
  static const _opacity = 0.06;
  static const _spacing = 32.0 / 1.5;
  static const _stroke = 0.5;

  final Color color;

  _GlassGridPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: _opacity)
      ..strokeWidth = _stroke
      ..style = PaintingStyle.stroke;

    for (double x = 0; x <= size.width; x += _spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += _spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _GlassGridPainter old) => old.color != color;
}

/// Translucent panel. Backdrop blur only when [blurEnabled] — a zero-sigma
/// BackdropFilter used to be inserted anyway, which still cost a compositing
/// layer per card for nothing.
class RfGlassContainer extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final double radius;
  final Color? tint;
  final Color? borderColor;
  final double blur;
  final bool blurEnabled;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  const RfGlassContainer({
    super.key,
    required this.child,
    this.padding,
    this.margin,
    this.radius = RfRadius.card,
    this.tint,
    this.borderColor,
    this.blur = RfGlass.blurStandard,
    this.blurEnabled = true,
    this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final inner = DecoratedBox(
      decoration: RfGlass.decoration(
        radius: radius,
        tint: tint,
        borderColor: borderColor,
      ),
      child: Padding(
        padding: padding ?? EdgeInsets.zero,
        child: child,
      ),
    );
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: blurEnabled
          ? BackdropFilter(
              filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
              child: inner,
            )
          : inner,
    );

    final wrapped = margin != null
        ? Padding(padding: margin!, child: content)
        : content;

    if (onTap == null && onLongPress == null) return wrapped;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(radius),
        splashColor: Colors.white.withValues(alpha: 0.06),
        highlightColor: Colors.white.withValues(alpha: 0.04),
        child: wrapped,
      ),
    );
  }
}

/// Liquid-glass card/container — heavier blur, specular top highlight,
/// larger radius, and (when tappable) a press-morph: scale + the same
/// 200ms/easeOut timing as the rest of the app's press feedback, evoking
/// soft glass giving slightly under a touch. [blur] <= 0 skips the
/// BackdropFilter entirely (use that over a live camera).
class RfLiquidGlassContainer extends StatefulWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double radius;
  final Color? tint;
  final Color? borderColor;
  final double blur;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  const RfLiquidGlassContainer({
    super.key,
    required this.child,
    this.padding,
    this.radius = RfRadius.lg,
    this.tint,
    this.borderColor,
    this.blur = RfGlass.blurHeavy,
    this.onTap,
    this.onLongPress,
  });

  @override
  State<RfLiquidGlassContainer> createState() => _RfLiquidGlassContainerState();
}

class _RfLiquidGlassContainerState extends State<RfLiquidGlassContainer> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.97)
        .animate(CurvedAnimation(parent: _ctrl, curve: RfDuration.pressCurve));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final inner = Stack(
      children: [
        DecoratedBox(
          decoration: RfGlass.liquidDecoration(
            radius: widget.radius,
            tint: widget.tint,
            borderColor: widget.borderColor,
          ),
          child: Padding(
            padding: widget.padding ?? EdgeInsets.zero,
            child: widget.child,
          ),
        ),
        RfGlass.specularArc(radius: widget.radius),
      ],
    );
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(widget.radius),
      child: widget.blur > 0
          ? BackdropFilter(
              filter: ImageFilter.blur(sigmaX: widget.blur, sigmaY: widget.blur),
              child: inner,
            )
          : inner,
    );

    if (widget.onTap == null && widget.onLongPress == null) return content;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _ctrl.forward(),
      onTapUp: (_) => _ctrl.reverse(),
      onTapCancel: () => _ctrl.reverse(),
      onTap: widget.onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              widget.onTap!();
            },
      onLongPress: widget.onLongPress == null
          ? null
          : () {
              HapticFeedback.mediumImpact();
              widget.onLongPress!();
            },
      child: ScaleTransition(scale: _scale, child: content),
    );
  }
}

/// App scaffold with the neutral grey background.
///
/// [showGrid] defaults to false — the textured grid is a Home-only accent
/// (Sir 2026-08-11); every other screen renders the flat grey gradient.
class RfGlassScaffold extends StatelessWidget {
  final PreferredSizeWidget? appBar;
  final Widget body;
  final Widget? floatingActionButton;
  final bool extendBodyBehindAppBar;
  final bool showGrid;

  const RfGlassScaffold({
    super.key,
    this.appBar,
    required this.body,
    this.floatingActionButton,
    this.extendBodyBehindAppBar = false,
    this.showGrid = false,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: RfColors.bg,
      extendBodyBehindAppBar: extendBodyBehindAppBar,
      appBar: appBar,
      floatingActionButton: floatingActionButton,
      body: RfGlassBackground(
        showGrid: showGrid,
        child: body,
      ),
    );
  }
}

/// App bar — transparent over the page with a hairline underneath, the way
/// the Claude desktop header sits on its canvas. (It used to blur; there is
/// nothing behind it to blur, so that was pure compositing cost.)
class RfGlassAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String? title;
  final Widget? titleWidget;
  final List<Widget>? actions;
  final Widget? leading;
  final double? leadingWidth;
  final bool centerTitle;
  final PreferredSizeWidget? bottom;

  const RfGlassAppBar({
    super.key,
    this.title,
    this.titleWidget,
    this.actions,
    this.leading,
    this.leadingWidth,
    this.centerTitle = false,
    this.bottom,
  });

  @override
  Size get preferredSize =>
      Size.fromHeight(kToolbarHeight + (bottom?.preferredSize.height ?? 0));

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: Colors.transparent,
      foregroundColor: RfColors.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: centerTitle,
      leading: leading,
      leadingWidth: leadingWidth,
      title: titleWidget ??
          (title != null
              ? Text(
                  title!,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                )
              : null),
      actions: actions,
      bottom: bottom,
      shape: Border(
        bottom: BorderSide(color: RfGlass.border(0.08)),
      ),
    );
  }
}

/// Bottom sheet shell — near-opaque elevated grey with a light blur.
class RfGlassSheet extends StatelessWidget {
  final Widget child;
  final double? maxHeightFactor;

  const RfGlassSheet({
    super.key,
    required this.child,
    this.maxHeightFactor,
  });

  @override
  Widget build(BuildContext context) {
    final maxH = maxHeightFactor != null
        ? MediaQuery.sizeOf(context).height * maxHeightFactor!
        : null;

    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(RfRadius.lg)),
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: RfGlass.blurStandard,
          sigmaY: RfGlass.blurStandard,
        ),
        child: Container(
          constraints: maxH != null ? BoxConstraints(maxHeight: maxH) : null,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                RfGlass.fillElevated(0.90),
                RfGlass.fillElevated(0.96),
              ],
            ),
            border: Border(
              top: BorderSide(color: RfGlass.border(0.22)),
              left: BorderSide(color: RfGlass.border(0.10)),
              right: BorderSide(color: RfGlass.border(0.10)),
            ),
          ),
          child: child,
        ),
      ),
    );
  }
}

/// Glass-styled alert dialog wrapper.
class RfGlassDialog extends StatelessWidget {
  final Widget child;

  const RfGlassDialog({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(RfRadius.lg),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: RfGlass.blurStandard, sigmaY: RfGlass.blurStandard),
        child: DecoratedBox(
          decoration: RfGlass.decoration(radius: RfRadius.lg, tint: RfGlass.fillElevated(0.94)),
          child: child,
        ),
      ),
    );
  }
}
