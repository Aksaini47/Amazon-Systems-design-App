import 'dart:async';
import 'package:bonsoir/bonsoir.dart';

/// Discovers the RepairFully backend on the local network via mDNS.
/// The backend must advertise `_repairfully._tcp`.
class DiscoveryService {
  static const _serviceType = '_repairfully._tcp';

  /// Scans the local network and returns the backend URL if found,
  /// or null if nothing is found within [timeout].
  static Future<String?> discover({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    BonsoirDiscovery? discovery;
    StreamSubscription? sub;
    Timer? timer;
    final completer = Completer<String?>();

    try {
      discovery = BonsoirDiscovery(type: _serviceType);
      await discovery.ready;

      sub = discovery.eventStream!.listen((event) {
        if (event.type == BonsoirDiscoveryEventType.discoveryServiceFound) {
          // Resolve the service to get host + port
          event.service!.resolve(discovery!.serviceResolver);
        } else if (event.type == BonsoirDiscoveryEventType.discoveryServiceResolved) {
          final service = event.service as ResolvedBonsoirService;
          final host = service.host;
          if (host != null && !completer.isCompleted) {
            timer?.cancel();
            completer.complete('http://$host:${service.port}');
          }
        }
      });

      await discovery.start();

      timer = Timer(timeout, () {
        if (!completer.isCompleted) completer.complete(null);
      });

      final result = await completer.future;
      return result;
    } catch (e) {
      if (!completer.isCompleted) completer.complete(null);
      return null;
    } finally {
      await sub?.cancel();
      await discovery?.stop();
    }
  }
}
