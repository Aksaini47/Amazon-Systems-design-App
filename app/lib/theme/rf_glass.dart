import 'dart:ui';

import 'package:flutter/material.dart';

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

/// Ambient background — gradient mesh + optional grid + soft orbs.
class RfGlassBackground extends StatelessWidget {
  final Widget? child;
  final bool showGrid;
  final bool showOrbs;

  const RfGlassBackground({
    super.key,
    this.child,
    this.showGrid = true,
    this.showOrbs = true,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        DecoratedBox(decoration: BoxDecoration(gradient: RfGlass.meshGradient)),
        if (showOrbs) ...[
          Positioned(
            top: -80,
            right: -40,
            child: _orb(RfColors.navy, 220, 0.35),
          ),
          Positioned(
            bottom: 120,
            left: -60,
            child: _orb(RfColors.rtAccent, 180, 0.12),
          ),
          Positioned(
            top: MediaQuery.sizeOf(context).height * 0.35,
            right: -30,
            child: _orb(RfColors.pkAccent, 140, 0.08),
          ),
        ],
        if (showGrid)
          CustomPaint(
            painter: _GlassGridPainter(
              color: RfColors.navy,
              opacity: 0.14,
            ),
          ),
        if (child != null) child!,
      ],
    );
  }

  Widget _orb(Color color, double size, double opacity) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [
              color.withValues(alpha: opacity),
              color.withValues(alpha: 0),
            ],
          ),
        ),
      ),
    );
  }
}

class _GlassGridPainter extends CustomPainter {
  final Color color;
  final double opacity;
  final double spacing;
  final double stroke;

  _GlassGridPainter({
    required this.color,
    this.opacity = 0.14,
    this.spacing = 32,
    this.stroke = 0.5,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: opacity)
      ..strokeWidth = stroke
      ..style = PaintingStyle.stroke;

    for (double x = 0; x <= size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _GlassGridPainter old) =>
      old.color != color || old.opacity != opacity;
}

/// Frosted overlay for camera chrome (top/bottom bars over live preview).
class RfGlassOverlay extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final BorderRadius borderRadius;
  final double blur;
  final Color? tint;
  final bool showBottomBorder;

  const RfGlassOverlay({
    super.key,
    required this.child,
    this.padding,
    this.borderRadius = BorderRadius.zero,
    this.blur = RfGlass.blurStandard,
    this.tint,
    this.showBottomBorder = false,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: borderRadius,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: tint ?? RfGlass.fillElevated(0.48),
            border: showBottomBorder
                ? Border(bottom: BorderSide(color: RfGlass.border(0.14)))
                : null,
          ),
          child: Padding(
            padding: padding ?? EdgeInsets.zero,
            child: child,
          ),
        ),
      ),
    );
  }
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
  });

  @override
  Widget build(BuildContext context) {
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: blurEnabled
            ? ImageFilter.blur(sigmaX: blur, sigmaY: blur)
            : ImageFilter.blur(sigmaX: 0, sigmaY: 0),
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

    if (onTap == null) return wrapped;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(radius),
        splashColor: Colors.white.withValues(alpha: 0.06),
        highlightColor: Colors.white.withValues(alpha: 0.04),
        child: wrapped,
      ),
    );
  }
}

/// App scaffold with glass mesh background.
class RfGlassScaffold extends StatelessWidget {
  final PreferredSizeWidget? appBar;
  final Widget body;
  final Widget? floatingActionButton;
  final bool extendBodyBehindAppBar;
  final bool showMeshOrbs;

  const RfGlassScaffold({
    super.key,
    this.appBar,
    required this.body,
    this.floatingActionButton,
    this.extendBodyBehindAppBar = false,
    this.showMeshOrbs = true,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: RfColors.bg,
      extendBodyBehindAppBar: extendBodyBehindAppBar,
      appBar: appBar,
      floatingActionButton: floatingActionButton,
      body: RfGlassBackground(
        showOrbs: showMeshOrbs,
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

/// Horizontal status banner with glass tint.
class RfGlassBanner extends StatelessWidget {
  final Widget child;
  final Color? tint;
  final EdgeInsetsGeometry padding;

  const RfGlassBanner({
    super.key,
    required this.child,
    this.tint,
    this.padding = const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
  });

  @override
  Widget build(BuildContext context) {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: RfGlass.blurLight, sigmaY: RfGlass.blurLight),
        child: Container(
          width: double.infinity,
          padding: padding,
          decoration: BoxDecoration(
            color: (tint ?? RfGlass.fill(0.20)).withValues(alpha: 0.85),
            border: Border(
              bottom: BorderSide(color: RfGlass.border(0.10)),
            ),
          ),
          child: child,
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
