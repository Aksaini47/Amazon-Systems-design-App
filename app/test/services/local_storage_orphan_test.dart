import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/services/local_storage_service.dart';

/// The orphan sweep must recover ONLY real orphans (crash / dead phone) — not
/// the leftover cache original of a recording that was saved normally, which
/// used to show up as a duplicate "RECOVERED_" draft after every launch.
void main() {
  late Directory root;
  late Directory cache;
  late Directory drafts;
  late Directory orders;

  setUp(() {
    root = Directory.systemTemp.createTempSync('rf_orphan_');
    cache = Directory('${root.path}/cache')..createSync();
    drafts = Directory('${root.path}/drafts')..createSync();
    orders = Directory('${root.path}/orders')..createSync();
  });

  tearDown(() => root.deleteSync(recursive: true));

  File video(Directory dir, String name, int length, DateTime modified) {
    final f = File('${dir.path}/$name')..writeAsBytesSync(List.filled(length, 7));
    f.setLastModifiedSync(modified);
    return f;
  }

  final now = DateTime(2026, 10, 10, 17);
  DateTime ago(Duration d) => now.subtract(d);

  group('isSameRecording', () {
    final cacheAt = DateTime(2026, 10, 10, 16, 45, 28);

    bool same(int keptLen, DateTime keptAt) => LocalStorageService.isSameRecording(
          cacheLength: 61000,
          cacheModified: cacheAt,
          keptLength: keptLen,
          keptModified: keptAt,
        );

    test('same length written seconds later is the same recording', () {
      expect(same(61000, cacheAt.add(const Duration(seconds: 2))), isTrue);
    });

    test('same length but a different byte count is not', () {
      expect(same(61001, cacheAt.add(const Duration(seconds: 2))), isFalse);
    });

    test('a kept file written well BEFORE the cache file is not its copy', () {
      expect(same(61000, cacheAt.subtract(const Duration(minutes: 3))), isFalse);
    });

    test('a kept file written hours later is not its copy', () {
      expect(same(61000, cacheAt.add(const Duration(hours: 3))), isFalse);
    });
  });

  group('sweepOrphansIn', () {
    test('leftover of a normally-saved recording is dropped, not recovered', () async {
      final at = ago(const Duration(minutes: 20));
      video(cache, 'REC1.mp4', 60000, at);
      video(drafts, 'PK_DRAFT_x.mp4', 60000, at.add(const Duration(seconds: 2)));

      final r = await LocalStorageService.sweepOrphansIn(
          cacheDir: cache, draftsDir: drafts, ordersDir: orders, now: now);

      expect(r.recovered, isEmpty);
      expect(r.duplicatesDropped, 1);
      expect(cache.listSync(), isEmpty);
      expect(drafts.listSync().length, 1, reason: 'no RECOVERED_ copy was made');
    });

    test('leftover whose twin was promoted to a saved order is dropped', () async {
      final at = ago(const Duration(minutes: 40));
      video(cache, 'REC2.mp4', 65000, at);
      final folder = Directory('${orders.path}/403-1111111-2222222-PK')..createSync();
      video(folder, '403-1111111-2222222_PK.mp4', 65000, at.add(const Duration(seconds: 3)));

      final r = await LocalStorageService.sweepOrphansIn(
          cacheDir: cache, draftsDir: drafts, ordersDir: orders, now: now);

      expect(r.recovered, isEmpty);
      expect(r.duplicatesDropped, 1);
      expect(drafts.listSync(), isEmpty);
    });

    test('a real orphan (no twin anywhere) IS recovered into drafts', () async {
      final at = ago(const Duration(minutes: 30));
      video(cache, 'REC3.mp4', 70000, at);

      final r = await LocalStorageService.sweepOrphansIn(
          cacheDir: cache, draftsDir: drafts, ordersDir: orders, now: now);

      expect(r.recovered.length, 1);
      expect(r.duplicatesDropped, 0);
      final names = drafts.listSync().map((e) => e.uri.pathSegments.last).toList();
      expect(names.single, startsWith('RECOVERED_'));
      expect(cache.listSync(), isEmpty);
    });

    test('a recording still inside the 2-minute age gate is left alone', () async {
      video(cache, 'REC4.mp4', 80000, ago(const Duration(minutes: 1)));

      final r = await LocalStorageService.sweepOrphansIn(
          cacheDir: cache, draftsDir: drafts, ordersDir: orders, now: now);

      expect(r.recovered, isEmpty);
      expect(r.duplicatesDropped, 0);
      expect(cache.listSync().length, 1);
    });

    test('a tiny stale file is junk and is deleted, never recovered', () async {
      video(cache, 'REC5.mp4', 1000, ago(const Duration(minutes: 30)));

      final r = await LocalStorageService.sweepOrphansIn(
          cacheDir: cache, draftsDir: drafts, ordersDir: orders, now: now);

      expect(r.recovered, isEmpty);
      expect(cache.listSync(), isEmpty);
      expect(drafts.listSync(), isEmpty);
    });
  });

  group('dropDuplicateRecoveriesIn', () {
    test('removes a RECOVERED_ draft whose twin is a saved order, keeps the rest', () async {
      final cacheAt = DateTime(2026, 10, 10, 16, 45, 28);
      final dupe = video(drafts, 'RECOVERED_2026-10-10_16-45-28_ab12.mp4', 61000, now);
      final folder = Directory('${orders.path}/403-2521348-3734761-PK')..createSync();
      video(folder, '403-2521348-3734761_PK.mp4', 61000, cacheAt.add(const Duration(seconds: 2)));

      // Genuine orphan: no order has this length.
      final orphan = video(drafts, 'RECOVERED_2026-10-10_16-48-08_cd34.mp4', 62000, now);
      // Same time, different length: a different recording.
      final other = video(drafts, 'RECOVERED_2026-10-10_16-49-21_ef56.mp4', 63000, now);
      video(folder, 'other.mp4', 63500, DateTime(2026, 10, 10, 16, 49, 23));
      // A normal draft is never touched.
      final normal = video(drafts, 'PK_DRAFT_2026-10-10_16-45-29_aa.mp4', 61000, now);

      final dropped = await LocalStorageService.dropDuplicateRecoveriesIn(
          draftsDir: drafts, ordersDir: orders);

      expect(dropped.map((p) => File(p).uri.pathSegments.last).toList(),
          ['RECOVERED_2026-10-10_16-45-28_ab12.mp4']);
      expect(dupe.existsSync(), isFalse);
      expect(orphan.existsSync(), isTrue);
      expect(other.existsSync(), isTrue);
      expect(normal.existsSync(), isTrue);
    });
  });

  group('discardCacheOriginal', () {
    test('deletes the cache original once the copy has the same length', () async {
      final f = video(cache, 'REC6.mp4', 60000, now);
      final ok = await LocalStorageService.discardCacheOriginal(
          sourcePath: f.path, copiedLength: 60000, cacheDir: cache);
      expect(ok, isTrue);
      expect(f.existsSync(), isFalse);
    });

    test('keeps it when the copy is not byte-complete', () async {
      final f = video(cache, 'REC7.mp4', 60000, now);
      final ok = await LocalStorageService.discardCacheOriginal(
          sourcePath: f.path, copiedLength: 59999, cacheDir: cache);
      expect(ok, isFalse);
      expect(f.existsSync(), isTrue);
    });

    test('never touches a file outside the cache directory', () async {
      final f = video(drafts, 'keep.mp4', 60000, now);
      final ok = await LocalStorageService.discardCacheOriginal(
          sourcePath: f.path, copiedLength: 60000, cacheDir: cache);
      expect(ok, isFalse);
      expect(f.existsSync(), isTrue);
    });
  });
}
