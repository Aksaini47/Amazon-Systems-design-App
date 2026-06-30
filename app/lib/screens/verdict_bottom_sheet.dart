import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';

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
                    Text('Order: $orderId', style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12, fontFamily: 'monospace')),
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
                    const SizedBox(height: 10),
                    _VerdictButton(
                      icon: Icons.warning_amber_rounded,
                      label: 'DAMAGED',
                      description: 'Arrived damaged or defective',
                      color: Colors.orange,
                      onTap: () => Navigator.pop(context, QCVerdict.damaged),
                    ),
                    const SizedBox(height: 10),
                    _VerdictButton(
                      icon: Icons.dangerous_outlined,
                      label: 'DIFFERENT',
                      description: 'Swap / fraud — different item returned',
                      color: Colors.red,
                      onTap: () => _confirmDifferent(context),
                    ),
                    const SizedBox(height: 10),
                    _VerdictButton(
                      icon: Icons.broken_image_outlined,
                      label: 'DAMAGED + DIFFERENT',
                      description: 'Both damaged AND different item returned',
                      color: const Color(0xFFDA3633),
                      onTap: () => Navigator.pop(context, QCVerdict.damagedDifferent),
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
    showDialog(
      context: context,
      builder: (ctx) => RfGlassDialog(
        child: AlertDialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
          title: const Text('Flag as Fraud?', style: TextStyle(color: Colors.white)),
        content: const Text(
          'This will flag the order as potential buyer fraud (swap/different item returned).\n\nSAFE-T claim will be triggered automatically.',
          style: TextStyle(color: Color(0xFF8B949E), fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx); // Close dialog
              Navigator.pop(context, QCVerdict.different); // Return verdict
            },
            child: const Text('Yes, Flag Fraud', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
      ),
    );
  }
}

/// Verdict card — Mahika camera-app doctrine.
/// ScaleTransition 1.0 → 0.97 press feedback (slightly less aggressive
/// than the standard 0.95 because cards are larger; the smaller scale
/// keeps the motion proportionate). Solid tinted bg, 1px accent border,
/// material outlined chevron icon.
class _VerdictButton extends StatefulWidget {
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
  State<_VerdictButton> createState() => _VerdictButtonState();
}

class _VerdictButtonState extends State<_VerdictButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.97)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.color;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _ctrl.forward(),
      onTapUp: (_) => _ctrl.reverse(),
      onTapCancel: () => _ctrl.reverse(),
      onTap: () {
        HapticFeedback.selectionClick();
        widget.onTap();
      },
      child: ScaleTransition(
        scale: _scale,
        child: Container(
          padding: const EdgeInsets.all(16),
          constraints: const BoxConstraints(minHeight: 72),
          decoration: RfGlass.decoration(
            radius: RfRadius.card,
            tint: c.withValues(alpha: 0.12),
            borderColor: c.withValues(alpha: 0.45),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: c.withAlpha(45),
                  shape: BoxShape.circle,
                ),
                child: Icon(widget.icon, color: c, size: 24),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.label, style: TextStyle(color: c, fontSize: 15, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(widget.description, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_outlined, color: c.withAlpha(150), size: 22),
            ],
          ),
        ),
      ),
    );
  }
}
