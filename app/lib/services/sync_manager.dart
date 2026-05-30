import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'sync_queue_service.dart';
import 'upload_service.dart';

/// Drives the upload queue forward:
///   - syncNow()        — attempts every pending order once
///   - startPeriodic()  — auto-retries every 2 minutes (call from HomeScreen)
///   - stopPeriodic()   — cancels the timer (called from app shutdown)
///
/// Callers can subscribe to [statusStream] to drive UI badges live.
class SyncManager {
  static Timer? _timer;
  static bool _syncing = false;
  static final _statusController = StreamController<SyncStatus>.broadcast();

  /// Live status updates — emits whenever queue size or syncing state changes.
  /// Listen from the home screen banner.
  static Stream<SyncStatus> get statusStream => _statusController.stream;

  /// Snapshot of current state. Prunes stale entries first so the count is
  /// guaranteed to reflect only real, unsynced orders that exist on disk.
  static Future<SyncStatus> currentStatus() async {
    await SyncQueueService.pruneStale();
    final pending = await SyncQueueService.count();
    return SyncStatus(pendingCount: pending, syncing: _syncing);
  }

  /// Force a status emit. Use after external queue changes (e.g. order deleted)
  /// so the home-screen banner re-reads the (possibly now-zero) pending count.
  /// Prunes stale entries before emitting so the count is never inflated.
  static Future<void> refreshStatus() async {
    await SyncQueueService.pruneStale();
    await _emit();
  }

  /// Start the background retry timer. Safe to call multiple times — only one
  /// timer runs at a time. Prunes any stale entries on startup so the user
  /// doesn't see ghost counts from previous sessions where orders were
  /// deleted while uploads were still queued.
  static void startPeriodic({Duration interval = const Duration(minutes: 2)}) {
    _timer?.cancel();
    _timer = Timer.periodic(interval, (_) => syncNow());
    // Prune + try once immediately on startup
    SyncQueueService.pruneStale().then((_) => _emit());
    syncNow();
  }

  static void stopPeriodic() {
    _timer?.cancel();
    _timer = null;
  }

  /// One pass over the queue. Tries every pending order against the backend.
  /// Returns the count of newly-uploaded orders.
  static Future<int> syncNow() async {
    if (_syncing) {
      debugPrint('SyncManager: already syncing, skipping this tick');
      return 0;
    }
    _syncing = true;
    await _emit();
    try {
      final pending = await SyncQueueService.getPending();
      if (pending.isEmpty) return 0;

      // Single health-check before iterating — if backend down, skip everything
      // (saves time and avoids burning through retries unnecessarily).
      final online = await ApiService.ping();
      if (!online) {
        debugPrint('SyncManager: backend offline, ${pending.length} stays pending');
        return 0;
      }

      int success = 0;
      for (final entry in pending) {
        final orderId = entry['orderId']!;
        final folderPath = entry['folderPath']!;
        // Poison-pill skip: if this order has already failed N times, don't
        // re-attempt in the background loop. User can manually re-trigger
        // via Gallery → "retry upload" action (which resets the count).
        if (await SyncQueueService.isPoisoned(orderId)) {
          debugPrint('SyncManager: skipping poisoned entry $orderId (max retries reached)');
          continue;
        }
        try {
          final result = await UploadService.uploadFromFolder(
            orderId: orderId,
            folderPath: folderPath,
          );
          if (result.status == UploadStatus.success) {
            await SyncQueueService.remove(orderId);
            success++;
            debugPrint('SyncManager: ✓ uploaded $orderId');
          } else {
            // Track failure so a permanently-broken order eventually stops
            // burning sync ticks.
            final retries = await SyncQueueService.bumpRetry(orderId);
            debugPrint('SyncManager: ✗ failed $orderId (retry=$retries, error=${result.error})');
          }
        } catch (e) {
          await SyncQueueService.bumpRetry(orderId);
          debugPrint('SyncManager: exception on $orderId: $e');
        }
      }
      if (success > 0) debugPrint('SyncManager: synced $success/${pending.length} orders');
      return success;
    } finally {
      _syncing = false;
      await _emit();
    }
  }

  static Future<void> _emit() async {
    if (_statusController.isClosed) return;
    final pending = await SyncQueueService.count();
    _statusController.add(SyncStatus(pendingCount: pending, syncing: _syncing));
  }
}

class SyncStatus {
  final int pendingCount;
  final bool syncing;
  const SyncStatus({required this.pendingCount, required this.syncing});
}
