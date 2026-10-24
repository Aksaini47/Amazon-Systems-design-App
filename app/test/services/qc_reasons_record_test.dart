import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/services/activity_log_service.dart';
import 'package:repairfully_camera/services/local_storage_service.dart';

/// Where the QC main reason and its sub-reason are RECORDED: the activity-log
/// txt (`qc=` + `qc_sub=` on the same line) and meta.json. Sir, 2026-10-24:
/// the sub-reason goes in together with the main reason, and sub-reasons exist
/// only inside "damaged" and "different".
void main() {
  group('activity log txt line', () {
    final now = DateTime(2026, 10, 24, 11, 2, 9);

    String line(QCVerdict verdict, List<QCSubReason> picked, {Map<String, String>? extra}) =>
        ActivityLogService.formatLine(
          now: now,
          event: 'barcode_saved',
          mode: CaptureMode.rt,
          orderId: '402-1234567-1234567',
          awb: '123456789012',
          qc: verdict.name,
          qcSub: verdict.logSubReasons(picked),
          extra: extra,
        );

    test('main reason and sub-reason sit side by side', () {
      expect(
        line(QCVerdict.damaged, [QCSubReason.heavilyDamaged]),
        '2026-10-24 11:02:09 | RT | order=402-1234567-1234567 | awb=123456789012 | '
        'event=barcode_saved | qc=damaged | qc_sub=heavilyDamaged',
      );
      expect(
        line(QCVerdict.different, [QCSubReason.counterfeitItem]),
        contains('qc=different | qc_sub=counterfeitItem'),
      );
    });

    test('DAMAGED + DIFFERENT is one main reason with no sub-reason', () {
      final l = line(QCVerdict.damagedDifferent, const []);
      expect(l, contains('qc=damagedDifferent'));
      expect(l, isNot(contains('qc_sub')));
    });

    test('OK and EMPTY BOX write no sub-reason either', () {
      expect(line(QCVerdict.ok, const []), isNot(contains('qc_sub')));
      expect(
        line(QCVerdict.emptyBox, const [QCSubReason.emptyBoxReceived]),
        isNot(contains('qc_sub')),
      );
    });

    test('extra fields follow the QC fields; a line without a verdict has none', () {
      expect(
        line(QCVerdict.damaged, [QCSubReason.minorDamage], extra: {'folder': '/x'}),
        endsWith('qc=damaged | qc_sub=minorDamage | folder=/x'),
      );
      final plain = ActivityLogService.formatLine(now: now, event: 'app_open');
      expect(plain, '2026-10-24 11:02:09 | event=app_open');
    });
  });

  group('meta.json merge', () {
    final storage = LocalStorageService();

    CaptureSession session(QCVerdict? verdict, [List<QCSubReason> subs = const []]) => CaptureSession(
          orderId: '402-1234567-1234567',
          mode: CaptureMode.rt,
          sessionStartedAt: DateTime(2026, 10, 24),
          verdict: verdict,
          subReasons: subs,
        );

    test('writes the main reason with its sub-reason (machine name + Amazon wording)', () {
      final m = storage.mergeSession({}, session(QCVerdict.damaged, [QCSubReason.heavilyDamaged]));
      expect(m['verdict'], 'damaged');
      expect(m['qc_sub_reasons'], ['heavilyDamaged']);
      expect(m['qc_sub_reason_labels'], ['Product heavily damaged']);
    });

    test('a verdict without a sub-reason REPLACES the old one — nothing stale is left', () {
      final existing = storage.mergeSession(
        {},
        session(QCVerdict.damaged, [QCSubReason.heavilyDamaged]),
      );
      for (final v in [QCVerdict.ok, QCVerdict.damagedDifferent]) {
        final m = storage.mergeSession(existing, session(v));
        expect(m['verdict'], v.name);
        expect(m.containsKey('qc_sub_reasons'), isFalse, reason: '${v.name} keeps no sub-reason');
        expect(m.containsKey('qc_sub_reason_labels'), isFalse);
      }
    });

    test('EMPTY BOX still carries its auto-assigned sub-reason', () {
      final m = storage.mergeSession({}, session(QCVerdict.emptyBox, [QCSubReason.emptyBoxReceived]));
      expect(m['qc_sub_reasons'], ['emptyBoxReceived']);
    });

    test('a write with no verdict (PK, photo edits) leaves stored QC fields alone', () {
      final existing = {
        'qc_sub_reasons': ['minorDamage'],
        'qc_sub_reason_labels': ['Product with minor damaged/dents/scratches'],
      };
      final m = storage.mergeSession(existing, session(null));
      expect(m['qc_sub_reasons'], ['minorDamage']);
    });
  });
}
