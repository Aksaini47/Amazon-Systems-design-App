import 'package:flutter/material.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';

/// What [VerdictBottomSheet] resolves to — the verdict, plus the sub-reason
/// card picked underneath it. Exactly one for DAMAGED / DIFFERENT (and the
/// auto-assigned "Empty box received" for EMPTY BOX); none for OK and for
/// DAMAGED + DIFFERENT — sub-reasons exist only inside "damaged" and
/// "different" (Sir, 2026-10-24).
class QcVerdictResult {
  final QCVerdict verdict;
  final List<QCSubReason> subReasons;
  QcVerdictResult(this.verdict, this.subReasons)
      : assert(
          verdict.keepValidSubReasons(subReasons).length == subReasons.length,
          'sub-reason does not belong to ${verdict.name}',
        );
}

/// Which card grid is currently showing inside the sheet. A tap on DAMAGED
/// or DIFFERENT on the main panel doesn't close the sheet — it SLIDES to a
/// sub-reason panel underneath (Sir, 2026-09-12: "tap karte hi suboptions
/// slide hoke aata hai, dropdown nahi"). OK, EMPTY BOX and DAMAGED +
/// DIFFERENT have nothing to ask, so they resolve straight from the main
/// panel.
enum _Panel { main, damagedSub, differentSub }

class VerdictBottomSheet extends StatefulWidget {
  final String? orderId;

  const VerdictBottomSheet({super.key, this.orderId});

  @override
  State<VerdictBottomSheet> createState() => _VerdictBottomSheetState();
}

class _VerdictBottomSheetState extends State<VerdictBottomSheet> {
  // Explicit history stack rather than a hardcoded "back goes to main": a
  // sub-panel is only ever entered from main (DAMAGED or DIFFERENT), so Back
  // from it returns to main, and Back from main closes the sheet.
  final List<_Panel> _history = [_Panel.main];
  _Panel get _panel => _history.last;
  bool _forward = true;

  void _goTo(_Panel panel) {
    setState(() {
      _forward = true;
      _history.add(panel);
    });
  }

  void _goBack() {
    if (_history.length == 1) {
      Navigator.pop(context);
      return;
    }
    setState(() {
      _forward = false;
      _history.removeLast();
    });
  }

  void _finish(QCVerdict verdict, List<QCSubReason> subReasons) {
    Navigator.pop(context, QcVerdictResult(verdict, subReasons));
  }

  void _onDamagedSubPicked(QCSubReason picked) => _finish(QCVerdict.damaged, [picked]);

  void _onDifferentSubPicked(QCSubReason picked) => _confirmDifferent(picked);

  void _confirmDifferent(QCSubReason picked) {
    showDialog<void>(
      context: context,
      builder: (ctx) => RfGlassDialog(
        child: AlertDialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
          title: const Text('Flag as Fraud?', style: TextStyle(color: RfColors.textPrimary)),
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
                _finish(QCVerdict.different, [picked]); // Close sheet
              },
            ),
          ],
        ),
      ),
    );
  }

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

            // Title (fixed — swaps with the panel, but stays put so the
            // slide reads as "the choices moved", not "the sheet did").
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                children: [
                  Text(_titleFor(_panel), style: const TextStyle(color: RfColors.textPrimary, fontSize: 17, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  if (widget.orderId != null)
                    Text('Order: ${widget.orderId}', style: const TextStyle(color: RfColors.textSecondary, fontSize: 12, fontFamily: 'monospace')),
                  const SizedBox(height: 16),
                ],
              ),
            ),

            // Panel content — slides horizontally on every switch instead
            // of expanding in place, and resizes smoothly between the
            // 5-card main grid and the shorter sub-reason grids.
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
                child: AnimatedSize(
                  duration: RfDuration.pageTransition,
                  curve: RfDuration.enter,
                  alignment: Alignment.topCenter,
                  child: AnimatedSwitcher(
                    duration: RfDuration.pageTransition,
                    switchInCurve: RfDuration.enter,
                    switchOutCurve: RfDuration.exit,
                    transitionBuilder: (child, animation) {
                      final entering = child.key == ValueKey(_panel);
                      final dx = _forward ? 1.0 : -1.0;
                      final tween = entering
                          ? Tween<Offset>(begin: Offset(dx, 0), end: Offset.zero)
                          : Tween<Offset>(begin: Offset(-dx, 0), end: Offset.zero);
                      return ClipRect(
                        child: SlideTransition(
                          position: tween.animate(animation),
                          child: FadeTransition(opacity: animation, child: child),
                        ),
                      );
                    },
                    layoutBuilder: (currentChild, previousChildren) => Stack(
                      alignment: Alignment.topCenter,
                      children: [...previousChildren, if (currentChild != null) currentChild],
                    ),
                    child: KeyedSubtree(
                      key: ValueKey(_panel),
                      child: _buildPanel(_panel),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _titleFor(_Panel panel) => switch (panel) {
        _Panel.main => 'QC VERDICT',
        _Panel.damagedSub => 'DAMAGE DETAIL',
        _Panel.differentSub => 'RETURN DETAIL',
      };

  Widget _buildPanel(_Panel panel) {
    switch (panel) {
      case _Panel.main:
        return Column(
          key: const ValueKey('main-column'),
          children: [
            _VerdictButton(
              icon: Icons.check_circle_outline,
              label: 'OK',
              description: 'Product matches what was sent',
              color: RfColors.successLight,
              onTap: () => _finish(QCVerdict.ok, const []),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.warning_amber_rounded,
              label: 'DAMAGED',
              description: 'Arrived damaged or defective',
              color: RfColors.amber,
              onTap: () => _goTo(_Panel.damagedSub),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.dangerous_outlined,
              label: 'DIFFERENT',
              description: 'Fraud / swap — different item',
              color: RfColors.error,
              onTap: () => _goTo(_Panel.differentSub),
            ),
            const SizedBox(height: 8),
            // No sub-reason panel here: the damaged / different sub-reasons
            // belong to DAMAGED and DIFFERENT only (Sir, 2026-10-24). It
            // resolves straight away, and — as before — without the
            // fraud-confirm dialog that only plain DIFFERENT shows.
            _VerdictButton(
              icon: Icons.broken_image_outlined,
              label: 'DAMAGED + DIFFERENT',
              description: 'Damaged AND different item',
              color: RfColors.rtAccent,
              onTap: () => _finish(QCVerdict.damagedDifferent, const []),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.inventory_2_outlined,
              label: 'EMPTY BOX',
              description: 'Box arrived with no product inside',
              color: RfColors.warning,
              onTap: () => _finish(QCVerdict.emptyBox, const [QCSubReason.emptyBoxReceived]),
            ),
            const SizedBox(height: 16),
            _footerButton(label: 'Cancel', onTap: () => Navigator.pop(context)),
          ],
        );

      case _Panel.damagedSub:
        return Column(
          key: const ValueKey('damaged-column'),
          children: [
            _VerdictButton(
              icon: Icons.report_problem_rounded,
              label: 'HEAVILY DAMAGED',
              description: QCSubReason.heavilyDamaged.label,
              color: RfColors.amber,
              onTap: () => _onDamagedSubPicked(QCSubReason.heavilyDamaged),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.warning_amber_rounded,
              label: 'MINOR DAMAGE',
              description: QCSubReason.minorDamage.label,
              color: RfColors.amber,
              onTap: () => _onDamagedSubPicked(QCSubReason.minorDamage),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.recycling_rounded,
              label: 'MILDLY USED',
              description: QCSubReason.mildlyUsed.label,
              color: RfColors.amber,
              onTap: () => _onDamagedSubPicked(QCSubReason.mildlyUsed),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.delete_sweep_rounded,
              label: 'HEAVILY USED',
              description: QCSubReason.heavilyUsed.label,
              color: RfColors.amber,
              onTap: () => _onDamagedSubPicked(QCSubReason.heavilyUsed),
            ),
            const SizedBox(height: 16),
            _footerButton(label: '← Back', onTap: _goBack),
          ],
        );

      case _Panel.differentSub:
        return Column(
          key: const ValueKey('different-column'),
          children: [
            _VerdictButton(
              icon: Icons.swap_horiz_rounded,
              label: 'DIFFERENT ITEM',
              description: QCSubReason.differentItem.label,
              color: RfColors.error,
              onTap: () => _onDifferentSubPicked(QCSubReason.differentItem),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.gpp_bad_rounded,
              label: 'COUNTERFEIT / FAKE',
              description: QCSubReason.counterfeitItem.label,
              color: RfColors.error,
              onTap: () => _onDifferentSubPicked(QCSubReason.counterfeitItem),
            ),
            const SizedBox(height: 16),
            _footerButton(label: '← Back', onTap: _goBack),
          ],
        );
    }
  }

  Widget _footerButton({required String label, required VoidCallback onTap}) {
    return RfButton.secondary(label: label, fullWidth: true, onPressed: onTap);
  }
}

/// Verdict / sub-reason card — liquid-glass treatment (fixed, non-scrolling
/// sets qualify per the Phase 4 rollout rule). [RfLiquidGlassContainer]
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
        // No backdrop blur: this sheet is shown over the LIVE camera in RT
        // mode, and five blurred buttons there re-blur the video every frame.
        blur: 0,
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
