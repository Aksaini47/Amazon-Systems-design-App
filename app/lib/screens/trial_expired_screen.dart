import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/trial_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';

// wa.me format: country code + number, no spaces or "+".
const _kContactWhatsAppNumber = '917015436711';

/// Full hard-lock screen shown once the demo trial is blocked (expired,
/// remotely kill-switched, or unverifiable). This IS the whole app at that
/// point — there is nothing behind it to navigate back to (TrialGate is the
/// MaterialApp's home), so the system back button simply exits, which is
/// the correct behavior here, not a bypass.
class TrialExpiredScreen extends StatelessWidget {
  final TrialBlockReason reason;

  const TrialExpiredScreen({super.key, required this.reason});

  ({IconData icon, String headline, String body}) get _copy {
    switch (reason) {
      case TrialBlockReason.killSwitch:
        return (
          icon: Icons.pause_circle_outline_rounded,
          headline: 'Demo paused',
          body: 'This demo has been paused by RF Logger. '
              'Contact us to continue.',
        );
      case TrialBlockReason.unverifiable:
        return (
          icon: Icons.wifi_off_rounded,
          headline: "Can't verify trial",
          body: 'Connect to the internet and reopen the app to continue '
              'your trial.',
        );
      case TrialBlockReason.expired:
      case TrialBlockReason.none:
        return (
          icon: Icons.lock_clock_rounded,
          headline: 'Trial period over',
          body: 'Your 30-day RF Logger trial has ended. '
              'Contact us to activate the full version.',
        );
    }
  }

  Future<void> _contactUs() async {
    final uri = Uri.parse('https://wa.me/$_kContactWhatsAppNumber');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final copy = _copy;
    return RfGlassScaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: RfGlassContainer(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 36),
              radius: RfRadius.lg,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(copy.icon, size: 56, color: RfColors.amber),
                  const SizedBox(height: 20),
                  Text(
                    copy.headline,
                    textAlign: TextAlign.center,
                    style: RfType.title,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    copy.body,
                    textAlign: TextAlign.center,
                    style: RfType.body.copyWith(color: RfColors.textSecondary),
                  ),
                  const SizedBox(height: 28),
                  RfButton.primary(
                    label: 'CONTACT US ON WHATSAPP',
                    icon: Icons.chat_rounded,
                    fullWidth: true,
                    onPressed: reason == TrialBlockReason.unverifiable ? null : _contactUs,
                  ),
                  if (reason == TrialBlockReason.unverifiable) ...[
                    const SizedBox(height: 14),
                    Text(
                      'Reconnect to the internet, then reopen the app.',
                      textAlign: TextAlign.center,
                      style: RfType.caption,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
