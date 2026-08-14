import 'package:flutter/material.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';

class VerdictBottomSheet extends StatelessWidget {
  final String? orderId;

  const VerdictBottomSheet({super.key, this.orderId});

  @override
  Widget build(BuildContext context) {
    return RfGlassSheet(
      maxHeightFactor: 0.85,
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Drag handle (fixed)
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 8),
              child: Container(width: 36, height: 4, decoration: BoxDecoration(color: RfColors.glassBorder(0.35), borderRadius: BorderRadius.circular(2))),
            ),

            // Title (fixed)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                children: [
                  const Text('QC VERDICT', style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  if (orderId != null)
                    Text('Order: $orderId', style: const TextStyle(color: RfColors.textSecondary, fontSize: 12, fontFamily: 'monospace')),
                  const SizedBox(height: 16),
                ],
              ),
            ),

            // Verdict buttons + Cancel (scrollable if needed)
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
                child: Column(
                  children: [
                    _VerdictButton(
                      icon: Icons.check_circle_outline,
                      label: 'OK',
                      description: 'Product matches what was sent',
                      color: Colors.green,
                      onTap: () => Navigator.pop(context, QCVerdict.ok),
                    ),
                    const SizedBox(height: 8),
                    _VerdictButton(
                      icon: Icons.warning_amber_rounded,
                      label: 'DAMAGED',
                      description: 'Arrived damaged or defective',
                      color: Colors.orange,
                      onTap: () => Navigator.pop(context, QCVerdict.damaged),
                    ),
                    const SizedBox(height: 8),
                    _VerdictButton(
                      icon: Icons.dangerous_outlined,
                      label: 'DIFFERENT',
                      description: 'Fraud / swap — different item',
                      color: Colors.red,
                      onTap: () => _confirmDifferent(context),
                    ),
                    const SizedBox(height: 8),
                    _VerdictButton(
                      icon: Icons.broken_image_outlined,
                      label: 'DAMAGED + DIFFERENT',
                      description: 'Damaged AND different item',
                      color: RfColors.error,
                      onTap: () => Navigator.pop(context, QCVerdict.damagedDifferent),
                    ),
                    const SizedBox(height: 8),
                    _VerdictButton(
                      icon: Icons.inventory_2_outlined,
                      label: 'EMPTY BOX',
                      description: 'Box arrived with no product inside',
                      color: RfColors.warning,
                      onTap: () => Navigator.pop(context, QCVerdict.emptyBox),
                    ),
                    const SizedBox(height: 16),
                    GestureDetector(
                      onTap: () => Navigator.pop(context),
                      child: RfGlassContainer(
                        blurEnabled: false,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        child: const Center(child: Text('Cancel', style: TextStyle(color: Colors.white54, fontSize: 14))),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _confirmDifferent(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => RfGlassDialog(
        child: AlertDialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
          title: const Text('Flag as Fraud?', style: TextStyle(color: Colors.white)),
        content: const Text(
          'This will flag the order as potential buyer fraud (swap/different item returned).\n\nSAFE-T claim will be triggered automatically.',
          style: TextStyle(color: RfColors.textSecondary, fontSize: 13),
        ),
        actions: [
          RfButton.secondary(
            label: 'Cancel',
            onPressed: () => Navigator.pop(ctx),
          ),
          RfButton.danger(
            label: 'Yes, Flag Fraud',
            onPressed: () {
              Navigator.pop(ctx); // Close dialog
              Navigator.pop(context, QCVerdict.different); // Return verdict
            },
          ),
        ],
      ),
      ),
    );
  }
}

/// Verdict card — liquid-glass treatment (fixed 4-card, non-scrolling set
/// qualifies per the Phase 4 rollout rule). [RfLiquidGlassContainer]
/// already provides an equivalent press-morph (1.0 → 0.97) + haptic, so
/// this widget no longer needs its own AnimationController/GestureDetector.
class _VerdictButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String description;
  final Color color;
  final VoidCallback onTap;

  const _VerdictButton({
    required this.icon,
    required this.label,
    required this.description,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 60,
      child: RfLiquidGlassContainer(
        onTap: onTap,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        tint: color.withValues(alpha: 0.12),
        borderColor: color.withValues(alpha: 0.45),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                color: color.withAlpha(45),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: color, size: 18),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(color: color, fontSize: 13.5, fontWeight: FontWeight.w700),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    description,
                    style: const TextStyle(color: RfColors.textSecondary, fontSize: 10.5),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
