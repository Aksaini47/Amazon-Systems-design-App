import 'package:flutter/material.dart';
import '../services/trial_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import 'home_screen.dart';
import 'trial_expired_screen.dart';

/// Root widget for the demo flavor (main_demo.dart's MaterialApp.home).
/// Runs the trial check-in once at boot, then either lets the user into the
/// real app or hard-locks them behind TrialExpiredScreen. See
/// TrialService for the full design/rationale.
class TrialGate extends StatefulWidget {
  const TrialGate({super.key});

  @override
  State<TrialGate> createState() => _TrialGateState();
}

class _TrialGateState extends State<TrialGate> {
  late final Future<TrialStatus> _future;

  @override
  void initState() {
    super.initState();
    _future = TrialService.checkIn();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TrialStatus>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done || !snapshot.hasData) {
          return const RfGlassScaffold(
            body: Center(
              child: CircularProgressIndicator(color: RfColors.action),
            ),
          );
        }

        final status = snapshot.data!;
        if (status.blocked) {
          return TrialExpiredScreen(reason: status.reason);
        }
        return const HomeScreen();
      },
    );
  }
}
