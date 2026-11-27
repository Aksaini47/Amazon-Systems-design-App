import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/utils/activity_log_model.dart';

/// The activity log in plain words, grouped per order (Sir, 2026-11-27:
/// "ek particular order ko exact dhoondhna mushkil, language technical").
void main() {
  // One RT recording session as the app writes it: the Order ID only turns up
  // when the label is scanned at the end.
  const rtSession = [
    '2026-11-09 10:00:01 | RT | event=camera_ready | ctx=open | init_ms=420',
    '2026-11-09 10:00:05 | RT | event=video_start',
    '2026-11-09 10:01:17 | RT | event=video_stop | duration_sec=72',
    '2026-11-09 10:01:18 | RT | event=draft_saved | size=15728640 | salvaged=false',
    '2026-11-09 10:01:30 | RT | event=qc_verdict | qc=damaged | qc_sub=heavilyDamaged | qc_label=Item received damaged | qc_sub_label=Product heavily damaged',
    '2026-11-09 10:01:40 | RT | event=photo_saved | qc=damaged | qc_sub=heavilyDamaged | type=contents',
    '2026-11-09 10:01:50 | RT | event=photo_saved | qc=damaged | qc_sub=heavilyDamaged | type=front',
    '2026-11-09 10:02:00 | RT | event=photo_saved | qc=damaged | qc_sub=heavilyDamaged | type=back',
    '2026-11-09 10:02:10 | RT | event=photo_saved | qc=damaged | qc_sub=heavilyDamaged | type=label',
    '2026-11-09 10:02:30 | RT | order=402-1234567-7654321 | awb=123456789012 | event=barcode_saved | qc=damaged | qc_sub=heavilyDamaged | verified=true | auto_source=live',
    '2026-11-09 10:02:31 | RT | order=402-1234567-7654321 | awb=123456789012 | event=meta_written | qc=damaged | qc_sub=heavilyDamaged | folder=/x/y',
    '2026-11-09 10:02:32 | RT | order=402-1234567-7654321 | awb=123456789012 | event=shipment_saved | qc=damaged | qc_sub=heavilyDamaged | path=/x/y/v.mp4',
  ];

  final day = DateTime(2026, 11, 9);

  group('parseActivityLine', () {
    test('reads time, mode, order, awb, event, qc and the other fields', () {
      final e = parseActivityLine(rtSession[9]);
      expect(e.time, DateTime(2026, 11, 9, 10, 2, 30));
      expect(e.mode, 'RT');
      expect(e.orderId, '402-1234567-7654321');
      expect(e.awb, '123456789012');
      expect(e.event, 'barcode_saved');
      expect(e.qc, 'damaged');
      expect(e.qcSub, 'heavilyDamaged');
      expect(e.extra, {'verified': 'true', 'auto_source': 'live'});
      expect(e.raw, rtSession[9], reason: 'the line is kept verbatim');
    });

    test('a value that itself contains " | " is kept whole', () {
      final e = parseActivityLine('2026-11-09 10:00:00 | PK | event=camera_init_failed | error=bad | thing happened | ctx=open');
      expect(e.extra['error'], 'bad | thing happened');
      expect(e.extra['ctx'], 'open');
    });

    test('a line in no known shape becomes a note and never throws', () {
      final e = parseActivityLine('something odd');
      expect(e.event, 'note');
      expect(e.time, isNull);
      expect(e.raw, 'something odd');
      expect(parseActivityLine('').event, 'note');
    });
  });

  group('plain words', () {
    ActivityEventInfo say(String line) => describeActivityEvent(parseActivityLine(line));

    test('durations, sizes and photos read naturally', () {
      expect(say(rtSession[2]).detail, 'length 1 min 12 s');
      expect(say(rtSession[3]).detail, '15.0 MB');
      expect(say(rtSession[5]).label, 'Photo taken - Package contents');
      expect(say(rtSession[1]).label, 'Recording started');
    });

    test('the QC reason is named in words', () {
      final i = say(rtSession[4]);
      expect(i.label, 'QC reason: Damaged');
      expect(i.detail, 'Product heavily damaged');
      expect(activityQcName('damagedDifferent'), 'Damaged + Different');
      expect(activityQcSubName('heavilyDamaged'), 'Heavily damaged');
    });

    test('housekeeping is minor, failures are errors, success is green', () {
      expect(say(rtSession[0]).minor, isTrue);
      expect(say('2026-11-09 10:00:00 | RT | event=photo_failed | type=front | error=disk full').severity, ActivitySeverity.error);
      expect(say(rtSession[11]).severity, ActivitySeverity.success);
    });

    test('auto-save reasons are put in plain language', () {
      expect(say('2026-11-09 10:00:00 | PK | event=auto_save_blocked | reason=awb_missing | source=live').detail,
          'the AWB was not read yet');
    });

    test('an unknown event is made readable, not dropped', () {
      expect(say('2026-11-09 10:00:00 | PK | event=some_new_event').label, 'Some new event');
    });
  });

  group('groupActivityDay', () {
    test('one recording session becomes ONE order: the early lines join it when the Order ID turns up', () {
      final m = groupActivityDay(day, rtSession);
      expect(m.groups, hasLength(1));
      final g = m.groups.single;
      expect(g.orderId, '402-1234567-7654321');
      expect(g.mode, 'RT');
      expect(g.events, hasLength(rtSession.length), reason: 'nothing lost');
      expect([for (final e in g.events) e.raw], rtSession, reason: 'verbatim, in order');
      expect(g.outcome, ActivityOutcome.saved);
      expect(g.awb, '123456789012');
      expect(g.qc, 'damaged');
      expect(g.photoCount, 4);
      expect(g.videoLength, '1 min 12 s');
      expect(g.issueCount, 0);
      expect(m.system, isNull);
    });

    test('the timeline hides housekeeping until asked for', () {
      final g = groupActivityDay(day, rtSession).groups.single;
      expect(g.majorEvents.length, lessThan(g.events.length));
      expect(g.majorEvents.any((e) => e.event == 'camera_ready'), isFalse);
      expect(g.majorEvents.any((e) => e.event == 'shipment_saved'), isTrue);
    });

    test('two orders in a row stay two orders', () {
      final second = [
        '2026-11-09 11:00:05 | PK | event=video_start',
        '2026-11-09 11:00:50 | PK | event=video_stop | duration_sec=45',
        '2026-11-09 11:01:10 | PK | order=403-1111111-2222222 | awb=EK123456789IN | event=barcode_saved | auto_source=manual',
        '2026-11-09 11:01:12 | PK | order=403-1111111-2222222 | awb=EK123456789IN | event=shipment_saved',
      ];
      final m = groupActivityDay(day, [...rtSession, ...second]);
      expect(m.groups, hasLength(2));
      expect(m.groups.first.orderId, '403-1111111-2222222', reason: 'newest first');
      expect(m.groups.first.mode, 'PK');
      expect(m.groups.last.orderId, '402-1234567-7654321');
      expect(m.groups.first.events, hasLength(second.length));
      expect(m.groups.last.events, hasLength(rtSession.length));
    });

    test('a recording left in Drafts is a draft with no Order ID', () {
      final m = groupActivityDay(day, [
        '2026-11-09 12:00:05 | PK | event=video_start',
        '2026-11-09 12:00:40 | PK | event=video_stop | duration_sec=35',
        '2026-11-09 12:00:41 | PK | event=draft_saved | size=1048576 | salvaged=false',
        '2026-11-09 12:00:50 | PK | event=draft_retained',
      ]);
      final g = m.groups.single;
      expect(g.orderId, isNull);
      expect(g.outcome, ActivityOutcome.draft);
    });

    test('a failed save is a problem', () {
      final g = groupActivityDay(day, [
        '2026-11-09 12:00:05 | PK | event=video_start',
        '2026-11-09 12:01:00 | PK | order=403-1111111-2222222 | event=barcode_saved',
        '2026-11-09 12:01:02 | PK | order=403-1111111-2222222 | event=shipment_save_failed | error=Video recording was empty',
      ]).groups.single;
      expect(g.outcome, ActivityOutcome.problem);
      expect(g.issueCount, 1);
    });

    test('app-level lines and camera-only sessions go to the day\'s app group, not a card', () {
      final m = groupActivityDay(day, [
        '2026-11-09 09:00:00 | event=app_open | is_demo=false',
        '2026-11-09 09:00:10 | PK | event=camera_ready | init_ms=300',
        '2026-11-09 09:00:20 | event=orphan_sweep | recovered=1',
      ]);
      expect(m.groups, isEmpty);
      expect(m.system!.events, hasLength(3));
      expect(m.eventCount, 3);
    });

    test('editing an old order never swallows a recording that is still open', () {
      final m = groupActivityDay(day, [
        '2026-11-09 09:00:05 | PK | event=video_start',
        '2026-11-09 09:05:00 | PK | order=403-9999999-8888888 | event=order_metadata_updated | previousId=403-9999999-8888887',
      ]);
      expect(m.groups, hasLength(2));
      final edited = m.groups.firstWhere((g) => g.orderId != null);
      expect(edited.events, hasLength(1));
      expect(edited.outcome, ActivityOutcome.edited);
      expect(m.groups.firstWhere((g) => g.orderId == null).events.single.event, 'video_start');
    });

    test('an empty day has no groups', () {
      final m = groupActivityDay(day, const []);
      expect(m.groups, isEmpty);
      expect(m.system, isNull);
    });

    test('day counts add up', () {
      final m = groupActivityDay(day, [
        ...rtSession,
        '2026-11-09 12:00:05 | PK | event=video_start',
        '2026-11-09 12:00:41 | PK | event=draft_saved | size=1 | salvaged=false',
      ]);
      expect(m.orderCount, 2);
      expect(m.count(ActivityOutcome.saved), 1);
      expect(m.count(ActivityOutcome.draft), 1);
      expect(m.problemCount, 0);
    });
  });

  group('find', () {
    final days = [
      groupActivityDay(day, [
        ...rtSession,
        '2026-11-09 11:00:05 | PK | event=video_start',
        '2026-11-09 11:01:10 | PK | order=403-1111111-2222222 | awb=EK123456789IN | event=barcode_saved',
        '2026-11-09 11:01:12 | PK | order=403-1111111-2222222 | awb=EK123456789IN | event=shipment_saved',
      ]),
      groupActivityDay(DateTime(2026, 11, 8), [
        '2026-11-08 09:00:05 | PK | event=video_start',
        '2026-11-08 09:01:10 | PK | order=404-5555555-6666666 | event=barcode_saved',
        '2026-11-08 09:01:12 | PK | order=404-5555555-6666666 | event=shipment_save_failed | error=Video recording was empty',
      ]),
    ];

    List<String?> ids(List<ActivityDayModel> r) => [for (final d in r) for (final g in d.groups) g.orderId];

    test('an Order ID is found with or without hyphens, part of it, any case', () {
      expect(ids(filterActivityDays(days, query: '402-1234567-7654321')), ['402-1234567-7654321']);
      expect(ids(filterActivityDays(days, query: '4021234567')), ['402-1234567-7654321']);
      expect(ids(filterActivityDays(days, query: '7654321')), ['402-1234567-7654321']);
      expect(ids(filterActivityDays(days, query: ' 404 5555555 ')), ['404-5555555-6666666']);
    });

    test('an AWB is found, any case', () {
      expect(ids(filterActivityDays(days, query: 'ek123456789in')), ['403-1111111-2222222']);
      expect(ids(filterActivityDays(days, query: '123456789012')), ['402-1234567-7654321']);
    });

    test('a plain word is looked up in the steps and the raw lines', () {
      expect(ids(filterActivityDays(days, query: 'heavily damaged')), ['402-1234567-7654321']);
      expect(ids(filterActivityDays(days, query: 'recording was empty')), ['404-5555555-6666666']);
    });

    test('days with no match are dropped; nothing found is an empty list', () {
      expect(filterActivityDays(days, query: '404-5555555').length, 1);
      expect(filterActivityDays(days, query: 'zzzzzz'), isEmpty);
    });

    test('quick filters', () {
      expect(ids(filterActivityDays(days, filter: ActivityFilter.rt)), ['402-1234567-7654321']);
      expect(ids(filterActivityDays(days, filter: ActivityFilter.pk)), ['403-1111111-2222222', '404-5555555-6666666']);
      expect(ids(filterActivityDays(days, filter: ActivityFilter.problems)), ['404-5555555-6666666']);
    });

    test('no query and no filter returns the very same list', () {
      expect(identical(filterActivityDays(days), days), isTrue);
    });

    test('raw lines are filtered the same way', () {
      expect(filterRawLines(rtSession, '4021234567'), hasLength(3));
      expect(filterRawLines(rtSession, 'photo_saved'), hasLength(4));
      expect(filterRawLines(rtSession, ''), rtSession);
    });
  });
}
