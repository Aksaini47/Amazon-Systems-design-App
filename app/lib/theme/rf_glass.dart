import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'rf_colors.dart';

/// Glassmorphic design tokens + reusable surfaces for RF Logger.
///
/// Frosted panels: blur + translucent fill + soft white border highlight.
/// Works on the dark navy mesh background used app-wide.
class RfGlass {
  RfGlass._();

  static const double blurLight = 8;
  static const double blurStandard = 14;
  static const double blurHeavy = 22;

  /// Primary frosted panel fill.
  static Color fill([double opacity = 0.14]) =>
      RfColors.card.withValues(alpha: opacity);

  /// Slightly denser panel (app bar, modals).
  static Color fillElevated([double opacity = 0.22]) =>
      RfColors.surface.withValues(alpha: opacity);

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
    bool showHighlight = true,
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
        color: borderColor ?? border(0.22),
        width: borderWidth,
      ),
      boxShadow: showHighlight
          ? [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.25),
                blurRadius: 16,
                offset: const Offset(0, 8),
              ),
            ]
          : null,
    );
  }

  /// Liquid-glass decoration — like [decoration] but with a brighter
  /// top-left specular highlight and a softer, wider shadow, evoking light
  /// refracting through curved glass rather than a flat frosted panel.
  /// New addition for the design-system revamp (Feature 6 pilot) — existing
  /// [decoration] callers elsewhere in the app are untouched.
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
      border: Border.all(color: borderColor ?? border(0.30)),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.30),
          blurRadius: 30,
          offset: const Offset(0, 16),
          spreadRadius: -8,
        ),
      ],
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
                Colors.white.withValues(alpha: 0.65),
                Colors.white.withValues(alpha: 0),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static LinearGradient meshGradient = const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF0A1428),
      Color(0xFF0D1117),
      Color(0xFF101828),
    ],
    stops: [0.0, 0.55, 1.0],
  );
}

/// Ambient background — dark gradient, with an optional grid pattern.
/// No colored glow orbs (removed per Sir's direction 2026-08-11: flat,
/// minimal, no blue/orange fades). The grid itself is opt-in per Sir's
/// 2026-08-11 follow-up — Home is the only screen with the textured grid;
/// every other screen is the flat charcoal gradient alone.
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
  // Slightly more visible than before (0.14->0.18) now that it's the
  // background's main texture, not a backdrop for glow orbs.
  static const _opacity = 0.18;
  static const _spacing = 32.0;
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

/// Frosted pill / toast over camera or modal content.
class RfGlassPill extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? tint;
  final Color? borderColor;
  final double radius;

  const RfGlassPill({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    this.tint,
    this.borderColor,
    this.radius = RfRadius.button,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: RfGlass.blurLight, sigmaY: RfGlass.blurLight),
        child: DecoratedBox(
          decoration: RfGlass.decoration(
            radius: radius,
            tint: tint ?? RfGlass.fill(0.22),
            borderColor: borderColor,
            showHighlight: false,
          ),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// Frosted panel with backdrop blur.
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
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: blurEnabled
            ? ImageFilter.blur(sigmaX: blur, sigmaY: blur)
            : ImageFilter.blur(),
        child: DecoratedBox(
          decoration: RfGlass.decoration(
            radius: radius,
            tint: tint,
            borderColor: borderColor,
            showHighlight: blurEnabled,
          ),
          child: Padding(
            padding: padding ?? EdgeInsets.zero,
            child: child,
          ),
        ),
      ),
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
/// soft glass giving slightly under a touch. New widget for the
/// design-system revamp (Feature 6 pilot on Home) — existing
/// [RfGlassContainer] usages elsewhere in the app are untouched.
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
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(widget.radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: widget.blur, sigmaY: widget.blur),
        child: Stack(
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
        ),
      ),
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

/// App scaffold with glass mesh background.
///
/// [showGrid] defaults to false — the textured grid is a Home-only accent
/// (Sir 2026-08-11); every other screen renders the flat charcoal gradient.
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

/// Frosted app bar — translucent with blur.
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
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: RfGlass.blurStandard,
          sigmaY: RfGlass.blurStandard,
        ),
        child: AppBar(
          backgroundColor: RfGlass.fillElevated(0.55),
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
            bottom: BorderSide(color: RfGlass.border(0.12)),
          ),
        ),
      ),
    );
  }
}

/// Bottom sheet shell with heavy glass blur.
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
          sigmaX: RfGlass.blurHeavy,
          sigmaY: RfGlass.blurHeavy,
        ),
        child: Container(
          constraints: maxH != null ? BoxConstraints(maxHeight: maxH) : null,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                RfGlass.fillElevated(0.72),
                RfGlass.fillElevated(0.88),
              ],
            ),
            border: Border(
              top: BorderSide(color: RfGlass.border(0.25)),
              left: BorderSide(color: RfGlass.border(0.12)),
              right: BorderSide(color: RfGlass.border(0.12)),
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
        filter: ImageFilter.blur(sigmaX: RfGlass.blurHeavy, sigmaY: RfGlass.blurHeavy),
        child: DecoratedBox(
          decoration: RfGlass.decoration(radius: RfRadius.lg, tint: RfGlass.fillElevated(0.75)),
          child: child,
        ),
      ),
    );
  }
}
