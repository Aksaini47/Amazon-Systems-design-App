import 'package:flutter/material.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';

/// What [VerdictBottomSheet] resolves to — the verdict, plus whichever
/// sub-reason card(s) were picked underneath it. Empty for OK; exactly one
/// for DAMAGED / DIFFERENT / EMPTY BOX; two for DAMAGED + DIFFERENT (one
/// from each family, collected across the two sub-panels in sequence).
class QcVerdictResult {
  final QCVerdict verdict;
  final List<QCSubReason> subReasons;
  const QcVerdictResult(this.verdict, this.subReasons);
}

/// Which card grid is currently showing inside the sheet. A tap on DAMAGED
/// or DIFFERENT on the main panel doesn't close the sheet — it SLIDES to a
/// sub-reason panel underneath (Sir, 2026-09-12: "tap karte hi suboptions
/// slide hoke aata hai, dropdown nahi"). EMPTY BOX and OK have nothing to
/// ask, so they resolve straight from the main panel.
enum _Panel { main, damagedSub, differentSub }

class VerdictBottomSheet extends StatefulWidget {
  final String? orderId;

  const VerdictBottomSheet({super.key, this.orderId});

  @override
  State<VerdictBottomSheet> createState() => _VerdictBottomSheetState();
}

class _VerdictBottomSheetState extends State<VerdictBottomSheet> {
  // Explicit history stack rather than a hardcoded "back goes to main" —
  // DAMAGED + DIFFERENT visits damagedSub then differentSub, and Back from
  // differentSub in THAT flow must return to damagedSub, not main, while
  // Back from differentSub reached via plain DIFFERENT must return to main.
  final List<_Panel> _history = [_Panel.main];
  _Panel get _panel => _history.last;
  bool _forward = true;

  // Verdict the sub-panels are currently resolving, and the damaged-family
  // pick made on the way to differentSub in the DAMAGED+DIFFERENT flow.
  // A single overwritable field, not an accumulating list — Back from
  // differentSub returns to damagedSub with the flow still "live", and
  // picking again must REPLACE the earlier choice, not add a second one.
  QCVerdict? _pendingVerdict;
  QCSubReason? _damagedPick;

  void _goTo(_Panel panel, {QCVerdict? verdict}) {
    if (verdict != null) _pendingVerdict = verdict;
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
      if (_history.last == _Panel.main) {
        _pendingVerdict = null;
        _damagedPick = null;
      }
    });
  }

  void _finish(QCVerdict verdict, List<QCSubReason> subReasons) {
    Navigator.pop(context, QcVerdictResult(verdict, subReasons));
  }

  void _onDamagedSubPicked(QCSubReason picked) {
    if (_pendingVerdict == QCVerdict.damagedDifferent) {
      _damagedPick = picked; // overwrite, not accumulate — see field doc
      _goTo(_Panel.differentSub);
    } else {
      _finish(QCVerdict.damaged, [picked]);
    }
  }

  void _onDifferentSubPicked(QCSubReason picked) {
    if (_pendingVerdict == QCVerdict.damagedDifferent) {
      // No fraud-confirm dialog on this path — matches the pre-existing
      // behaviour where DAMAGED + DIFFERENT never showed it either, only
      // plain DIFFERENT did.
      _finish(QCVerdict.damagedDifferent, [_damagedPick!, picked]);
      return;
    }
    _confirmDifferent(picked);
  }

  void _confirmDifferent(QCSubReason picked) {
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
                  Text(_titleFor(_panel), style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
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
              color: Colors.green,
              onTap: () => _finish(QCVerdict.ok, const []),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.warning_amber_rounded,
              label: 'DAMAGED',
              description: 'Arrived damaged or defective',
              color: Colors.orange,
              onTap: () => _goTo(_Panel.damagedSub, verdict: QCVerdict.damaged),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.dangerous_outlined,
              label: 'DIFFERENT',
              description: 'Fraud / swap — different item',
              color: Colors.red,
              onTap: () => _goTo(_Panel.differentSub, verdict: QCVerdict.different),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.broken_image_outlined,
              label: 'DAMAGED + DIFFERENT',
              description: 'Damaged AND different item',
              color: RfColors.error,
              onTap: () => _goTo(_Panel.damagedSub, verdict: QCVerdict.damagedDifferent),
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
              color: Colors.orange,
              onTap: () => _onDamagedSubPicked(QCSubReason.heavilyDamaged),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.warning_amber_rounded,
              label: 'MINOR DAMAGE',
              description: QCSubReason.minorDamage.label,
              color: Colors.orange,
              onTap: () => _onDamagedSubPicked(QCSubReason.minorDamage),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.recycling_rounded,
              label: 'MILDLY USED',
              description: QCSubReason.mildlyUsed.label,
              color: Colors.orange,
              onTap: () => _onDamagedSubPicked(QCSubReason.mildlyUsed),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.delete_sweep_rounded,
              label: 'HEAVILY USED',
              description: QCSubReason.heavilyUsed.label,
              color: Colors.orange,
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
              color: Colors.red,
              onTap: () => _onDifferentSubPicked(QCSubReason.differentItem),
            ),
            const SizedBox(height: 8),
            _VerdictButton(
              icon: Icons.gpp_bad_rounded,
              label: 'COUNTERFEIT / FAKE',
              description: QCSubReason.counterfeitItem.label,
              color: Colors.red,
              onTap: () => _onDifferentSubPicked(QCSubReason.counterfeitItem),
            ),
            const SizedBox(height: 16),
            _footerButton(label: '← Back', onTap: _goBack),
          ],
        );
    }
  }

  Widget _footerButton({required String label, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: RfGlassContainer(
        blurEnabled: false,
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Center(child: Text(label, style: const TextStyle(color: Colors.white54, fontSize: 14))),
      ),
    );
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
