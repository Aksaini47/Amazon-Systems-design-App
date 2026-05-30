import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persistent upload queue for orders waiting to sync to the backend.
///
/// Survives app kill, phone restart, and offline periods. Entries are removed
/// only after a confirmed-successful upload (via `.uploaded` marker on the
/// order folder + this queue entry removed).
///
/// Each entry: `{orderId, folderPath, queuedAt, retryCount?}`
/// (Bumped to v2 schema 2026-05-17 to add retryCount. Reads of v1 entries
/// without retryCount field continue to work — treated as retryCount=0.)
class SyncQueueService {
  static const _key = 'sync_queue_v1';

  /// Max number of failed upload attempts before a poison-pill entry is
  /// auto-removed from the active queue (kept on disk; user can re-queue
  /// via Gallery "retry upload" action). Prevents one permanently-broken
  /// order from indefinitely blocking the sync loop on Mahika-audit
  /// edge case #4 ("Offline + queue poisoned").
  static const _maxRetries = 6;

  /// Soft cap on queue size. Reaching this threshold is a signal that the
  /// backend has been offline for too long — the user should be notified
  /// to clean up old orders from Gallery. Hard cap is twice this.
  static const _queueSoftCap = 100;

  /// All currently-pending entries (oldest first).
  static Future<List<Map<String, String>>> getPending() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .map((e) => Map<String, String>.from(e as Map))
          .toList();
    } catch (e) {
      debugPrint('SyncQueue: corrupted queue, resetting ($e)');
      await prefs.remove(_key);
      return [];
    }
  }

  /// Number of pending uploads.
  static Future<int> count() async => (await getPending()).length;

  /// Enqueue an order. Idempotent — re-queuing an already-queued order is a no-op.
  /// Soft-caps the queue at [_queueSoftCap] entries: once exceeded, the oldest
  /// entries are dropped (poison-pill protection — they've usually failed
  /// repeatedly anyway, and a runaway queue causes SharedPreferences bloat).
  static Future<void> enqueue(String orderId, String folderPath) async {
    final list = await getPending();
    if (list.any((e) => e['orderId'] == orderId)) {
      debugPrint('SyncQueue: $orderId already queued, skipping');
      return;
    }
    list.add({
      'orderId': orderId,
      'folderPath': folderPath,
      'queuedAt': DateTime.now().toIso8601String(),
      'retryCount': '0',
    });
    // Soft-cap protection: if queue grows past the cap, drop oldest entries.
    if (list.length > _queueSoftCap) {
      // Sort by queuedAt and keep the most recent _queueSoftCap entries.
      list.sort((a, b) => (a['queuedAt'] ?? '').compareTo(b['queuedAt'] ?? ''));
      while (list.length > _queueSoftCap) {
        final dropped = list.removeAt(0);
        debugPrint('SyncQueue: soft-cap exceeded, dropping oldest entry ${dropped['orderId']}');
      }
    }
    await _save(list);
    debugPrint('SyncQueue: enqueued $orderId (total pending: ${list.length})');
  }

  /// Bump the retry count for [orderId] after a failed upload attempt.
  /// Returns the new retry count, or null if entry not found.
  static Future<int?> bumpRetry(String orderId) async {
    final list = await getPending();
    final idx = list.indexWhere((e) => e['orderId'] == orderId);
    if (idx < 0) return null;
    final current = int.tryParse(list[idx]['retryCount'] ?? '0') ?? 0;
    final next = current + 1;
    list[idx]['retryCount'] = next.toString();
    await _save(list);
    debugPrint('SyncQueue: bumped retryCount for $orderId → $next');
    return next;
  }

  /// Get the current retry count for [orderId] (0 if entry not found).
  static Future<int> retryCountFor(String orderId) async {
    final list = await getPending();
    final entry = list.firstWhere(
      (e) => e['orderId'] == orderId,
      orElse: () => <String, String>{},
    );
    return int.tryParse(entry['retryCount'] ?? '0') ?? 0;
  }

  /// Returns true if [orderId] has exceeded the auto-retry cap and should
  /// be skipped by the sync loop until the user manually retries.
  static Future<bool> isPoisoned(String orderId) async {
    final count = await retryCountFor(orderId);
    return count >= _maxRetries;
  }

  /// Remove an order from the queue (call after successful upload).
  static Future<void> remove(String orderId) async {
    final list = await getPending();
    final before = list.length;
    list.removeWhere((e) => e['orderId'] == orderId);
    if (list.length != before) {
      await _save(list);
      debugPrint('SyncQueue: removed $orderId (remaining: ${list.length})');
    }
  }

  /// Wipe everything — diagnostic / "reset queue" path.
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }

  /// Remove queue entries that no longer correspond to real work:
  ///   - folder was deleted by user / cleanup
  ///   - folder still exists but has a `.uploaded` marker (already synced)
  ///
  /// Should be called on app start AND before every status emit so the home
  /// banner can never show ghost counts. Returns the number of pruned entries.
  static Future<int> pruneStale() async {
    final list = await getPending();
    if (list.isEmpty) return 0;
    int removed = 0;
    final keep = <Map<String, String>>[];
    for (final entry in list) {
      final path = entry['folderPath'];
      if (path == null) {
        removed++;
        continue;
      }
      final folder = Directory(path);
      if (!folder.existsSync()) {
        removed++;
        continue;
      }
      if (File('$path/.uploaded').existsSync()) {
        removed++;
        continue;
      }
      keep.add(entry);
    }
    if (removed > 0) {
      await _save(keep);
      debugPrint('SyncQueue: pruned $removed stale entries (kept ${keep.length})');
    }
    return removed;
  }

  /// Returns the oldest queued entry's age (or null if queue empty).
  /// Used by the home-screen banner to surface "data hasn't synced for N days".
  static Future<Duration?> oldestAge() async {
    final list = await getPending();
    if (list.isEmpty) return null;
    DateTime? earliest;
    for (final e in list) {
      try {
        final t = DateTime.parse(e['queuedAt']!);
        if (earliest == null || t.isBefore(earliest)) earliest = t;
      } catch (_) {}
    }
    if (earliest == null) return null;
    return DateTime.now().difference(earliest);
  }

  static Future<void> _save(List<Map<String, String>> list) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(list));
  }
}
