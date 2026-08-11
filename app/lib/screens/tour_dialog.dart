import 'package:flutter/material.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';

/// 10-point first-run tour. Auto-shown once from home_screen.dart (demo
/// build only — see AppConfig.isDemo there); replayable anytime via
/// Settings -> About & Updates, or the "?" icon on the Home app bar.
class TourDialog {
  TourDialog._();

  static Future<void> show(BuildContext context) {
    return showDialog<void>(
      context: context,
      builder: (ctx) => const _TourDialogContent(),
    );
  }
}

class _TourPage {
  final IconData icon;
  final String title;
  final String body;
  const _TourPage({required this.icon, required this.title, required this.body});
}

// Content grounded in the app's real behavior (not generic placeholder
// copy) — see the demo build plan for the verification behind each point.
const _pages = <_TourPage>[
  _TourPage(
    icon: Icons.waving_hand_rounded,
    title: 'Welcome to RF Logger',
    body: 'Tamper-evident PK/RT video + photo evidence for Amazon SAFE-T '
        'claims — everything you record is timestamped and filed by Order ID.',
  ),
  _TourPage(
    icon: Icons.inventory_2_rounded,
    title: 'PK Mode — Pickup / Packing',
    body: 'Front + back photos first — video recording then starts '
        'automatically, capturing the item exactly as it’s packed.',
  ),
  _TourPage(
    icon: Icons.assignment_return_rounded,
    title: 'RT Mode — Return / Unpacking',
    body: 'Opposite order from PK: recording starts immediately on tap. '
        'Unbox on camera, then stop — the QC verdict comes after.',
  ),
  _TourPage(
    icon: Icons.qr_code_scanner_rounded,
    title: 'Order ID auto-detect',
    body: 'Barcode + OCR scan the shipping label together right after you '
        'stop recording — no manual typing of Order IDs.',
  ),
  _TourPage(
    icon: Icons.volume_up_rounded,
    title: 'Volume buttons as shutter',
    body: 'Volume Up starts/stops recording — from Home it jumps straight '
        'into PK/RT. Volume Down toggles the microphone.',
  ),
  _TourPage(
    icon: Icons.fact_check_rounded,
    title: 'QC Verdict (RT only)',
    body: 'OK, Damaged, Different, or Both. Anything other than OK walks you '
        'automatically through label, contents, front, and back claim photos.',
  ),
  _TourPage(
    icon: Icons.verified_rounded,
    title: 'Timestamp watermark',
    body: 'Every photo is stamped with date/time burned into the pixels — '
        'one-way, by design, for evidence integrity.',
  ),
  _TourPage(
    icon: Icons.photo_library_rounded,
    title: 'Gallery',
    body: 'Review, replace, or re-tag any photo per order. Drafts holds '
        'anything not yet assigned an Order ID.',
  ),
  _TourPage(
    icon: Icons.history_rounded,
    title: 'Activity log',
    body: 'A running audit trail of every capture session on this device.',
  ),
  _TourPage(
    icon: Icons.settings_rounded,
    title: 'Settings',
    body: 'Customize resolution, FPS, storage path, countdown, and more. '
        'Replay this tour anytime from here, or the ? icon on Home.',
  ),
];

class _TourDialogContent extends StatefulWidget {
  const _TourDialogContent();

  @override
  State<_TourDialogContent> createState() => _TourDialogContentState();
}

class _TourDialogContentState extends State<_TourDialogContent> {
  final _pageController = PageController();
  int _index = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _next() {
    if (_index == _pages.length - 1) {
      Navigator.of(context).pop();
      return;
    }
    _pageController.nextPage(
      duration: RfDuration.pageTransition,
      curve: RfDuration.enter,
    );
  }

  void _back() {
    _pageController.previousPage(
      duration: RfDuration.pageTransition,
      curve: RfDuration.enter,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLast = _index == _pages.length - 1;

    return RfGlassDialog(
      child: AlertDialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
        contentPadding: const EdgeInsets.fromLTRB(20, 24, 20, 8),
        content: SizedBox(
          width: 320,
          height: 300,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Expanded(
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: _pages.length,
                  onPageChanged: (i) => setState(() => _index = i),
                  itemBuilder: (context, i) {
                    final page = _pages[i];
                    return Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(page.icon, size: 44, color: RfColors.amber),
                        const SizedBox(height: 16),
                        Text(page.title, textAlign: TextAlign.center, style: RfType.heading),
                        const SizedBox(height: 10),
                        Text(
                          page.body,
                          textAlign: TextAlign.center,
                          style: RfType.body.copyWith(color: RfColors.textSecondary),
                        ),
                      ],
                    );
                  },
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  _pages.length,
                  (i) => AnimatedContainer(
                    duration: RfDuration.fade,
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    width: i == _index ? 18 : 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: i == _index ? RfColors.action : RfColors.glassBorder(0.3),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        actionsPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        actionsAlignment: MainAxisAlignment.spaceBetween,
        actions: [
          isLast
              ? const SizedBox(width: 8)
              : RfButton.secondary(
                  label: 'Skip',
                  onPressed: () => Navigator.of(context).pop(),
                ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_index > 0) ...[
                RfButton.secondary(label: 'Back', onPressed: _back),
                const SizedBox(width: 8),
              ],
              RfButton.primary(label: isLast ? 'Got it' : 'Next', onPressed: _next),
            ],
          ),
        ],
      ),
    );
  }
}
