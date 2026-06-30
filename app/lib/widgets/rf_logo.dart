import 'package:flutter/material.dart';

import '../theme/rf_colors.dart';

/// RepairFully brand mark — barcode scanner logo on orange.
class RfLogo extends StatelessWidget {
  final double size;
  final bool showLabel;
  final Color? labelColor;

  const RfLogo({
    super.key,
    this.size = 36,
    this.showLabel = false,
    this.labelColor,
  });

  @override
  Widget build(BuildContext context) {
    final mark = ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.22),
      child: Image.asset(
        'assets/branding/rf_logo.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: RfColors.navy,
            borderRadius: BorderRadius.circular(size * 0.22),
          ),
          child: Icon(Icons.camera_outlined, color: RfColors.action, size: size * 0.55),
        ),
      ),
    );

    if (!showLabel) return mark;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        const SizedBox(width: 10),
        Text(
          'RepairFully',
          style: TextStyle(
            color: labelColor ?? RfColors.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: size * 0.45,
          ),
        ),
      ],
    );
  }
}
