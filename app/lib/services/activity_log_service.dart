import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../models/capture_session.dart';

/// Plain-text, day-wise activity log for shipments and capture events.
/// Files live under `{appDocuments}/RepairFully/logs/activity_YYYY-MM-DD.txt`.
class ActivityLogService {
  ActivityLogService._();

  static const _logDirName = 'RepairFully/logs';
  static const retentionDays = 60;

  static Future<Directory> _logsDir() async {
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory('${base.path}/$_logDirName');
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    return dir;
  }

  static String _dayKey(DateTime dt) {
    final y = dt.year.toString().padLeft(4, '0');
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  static String _fileNameFor(DateTime dt) => 'activity_${_dayKey(dt)}.txt';

  /// Append one activity line. Fire-and-forget — never throws to callers.
  static Future<void> log({
    required String event,
    CaptureMode? mode,
    String? orderId,
    String? awb,
    String? qc,
    Map<String, String>? extra,
  }) async {
    try {
      final now = DateTime.now();
      final ts = '${_dayKey(now)} '
          '${now.hour.toString().padLeft(2, '0')}:'
          '${now.minute.toString().padLeft(2, '0')}:'
          '${now.second.toString().padLeft(2, '0')}';

      final parts = <String>[
        ts,
        if (mode != null) mode.name.toUpperCase(),
        if (orderId != null && orderId.isNotEmpty) 'order=$orderId',
        if (awb != null && awb.isNotEmpty) 'awb=$awb',
        'event=$event',
        if (qc != null && qc.isNotEmpty) 'qc=$qc',
        if (extra != null)
          ...extra.entries
              .where((e) => e.value.isNotEmpty)
              .map((e) => '${e.key}=${e.value}'),
      ];

      final line = '${parts.join(' | ')}\n';
      final dir = await _logsDir();
      final file = File('${dir.path}/${_fileNameFor(now)}');
      await file.writeAsString(line, mode: FileMode.append, flush: true);

      // Best-effort prune — ignore failures.
      // ignore: unawaited_futures
      _pruneOlderThan(retentionDays);
    } catch (e, st) {
      debugPrint('ActivityLogService: write failed: $e\n$st');
    }
  }

  static Future<void> _pruneOlderThan(int days) async {
    try {
      final dir = await _logsDir();
      final cutoff = DateTime.now().subtract(Duration(days: days));
      await for (final entity in dir.list()) {
        if (entity is! File) continue;
        final name = entity.uri.pathSegments.last;
        final match = RegExp(r'^activity_(\d{4}-\d{2}-\d{2})\.txt$').firstMatch(name);
        if (match == null) continue;
        final parts = match.group(1)!.split('-');
        final fileDate = DateTime(
          int.parse(parts[0]),
          int.parse(parts[1]),
          int.parse(parts[2]),
        );
        if (fileDate.isBefore(cutoff)) {
          await entity.delete();
        }
      }
    } catch (e) {
      debugPrint('ActivityLogService: prune failed: $e');
    }
  }

  /// Distinct log days (newest first), up to [lastN].
  static Future<List<DateTime>> listLogDays({int lastN = retentionDays}) async {
    try {
      final dir = await _logsDir();
      final days = <DateTime>[];
      await for (final entity in dir.list()) {
        if (entity is! File) continue;
        final name = entity.uri.pathSegments.last;
        final match = RegExp(r'^activity_(\d{4}-\d{2}-\d{2})\.txt$').firstMatch(name);
        if (match == null) continue;
        final parts = match.group(1)!.split('-');
        days.add(DateTime(
          int.parse(parts[0]),
          int.parse(parts[1]),
          int.parse(parts[2]),
        ));
      }
      days.sort((a, b) => b.compareTo(a));
      if (days.length > lastN) {
        return days.sublist(0, lastN);
      }
      return days;
    } catch (e) {
      debugPrint('ActivityLogService: listLogDays failed: $e');
      return [];
    }
  }

  static Future<String> readDay(DateTime day) async {
    try {
      final dir = await _logsDir();
      final file = File('${dir.path}/${_fileNameFor(day)}');
      if (!await file.exists()) return '';
      return file.readAsString();
    } catch (e) {
      debugPrint('ActivityLogService: readDay failed: $e');
      return '';
    }
  }

  /// Merged text for the last [days] calendar days (newest day first).
  static Future<String> readLastDays(int days) async {
    final listed = await listLogDays(lastN: days);
    if (listed.isEmpty) {
      return 'No activity logged yet.\n';
    }

    final buffer = StringBuffer();
    for (final day in listed) {
      final content = await readDay(day);
      if (content.trim().isEmpty) continue;
      buffer.writeln('=== ${_dayKey(day)} ===');
      buffer.write(content.endsWith('\n') ? content : '$content\n');
      buffer.writeln();
    }
    return buffer.toString();
  }

  static Future<String> logsDirectoryPath() async {
    final dir = await _logsDir();
    return dir.path;
  }
}
