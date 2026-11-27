import '../models/capture_session.dart';

/// Turns the plain-text activity log into something a person can read: events
/// in plain words, grouped per order, with a result per order.
///
/// Nothing is thrown away — every group keeps its raw lines verbatim (see
/// [ActivityEvent.raw]) and the screen shows them under "Technical details".
///
/// Pure Dart, no widgets: this is the part that is unit-tested.

// ─── One log line ────────────────────────────────────────────────────────

/// One parsed line of `activity_YYYY-MM-DD.txt`:
/// `2026-10-24 11:02:09 | RT | order=402-… | awb=… | event=qc_verdict | qc=damaged | …`
class ActivityEvent {
  /// The line exactly as written.
  final String raw;
  final DateTime? time;

  /// 'PK' / 'RT', or null (app-level events).
  final String? mode;
  final String event;
  final String? orderId;
  final String? awb;
  final String? qc;
  final String? qcSub;

  /// Every other `key=value` of the line.
  final Map<String, String> extra;

  const ActivityEvent({
    required this.raw,
    required this.time,
    required this.mode,
    required this.event,
    required this.orderId,
    required this.awb,
    required this.qc,
    required this.qcSub,
    required this.extra,
  });
}

final _stamp = RegExp(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})');

/// Parses one log line. Never throws: a line that is not in the usual shape
/// comes back as an `event: note` carrying the raw text.
ActivityEvent parseActivityLine(String line) {
  final raw = line.trimRight();
  final parts = raw.split(' | ');

  DateTime? time;
  final m = _stamp.firstMatch(parts.first);
  if (m != null) {
    time = DateTime(
      int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!),
      int.parse(m[4]!), int.parse(m[5]!), int.parse(m[6]!),
    );
  }

  String? mode, event, orderId, awb, qc, qcSub;
  final extra = <String, String>{};
  String? lastKey; // a value that itself contained " | " continues here
  for (var i = time == null ? 0 : 1; i < parts.length; i++) {
    final p = parts[i].trim();
    if (p.isEmpty) continue;
    if (p == 'PK' || p == 'RT') {
      mode = p;
      continue;
    }
    final eq = p.indexOf('=');
    if (eq <= 0) {
      if (lastKey != null) {
        if (lastKey == '\u0000event') {
          event = '$event | $p';
        } else {
          extra[lastKey] = '${extra[lastKey]} | $p';
        }
      }
      continue;
    }
    final key = p.substring(0, eq);
    final value = p.substring(eq + 1);
    switch (key) {
      case 'order':
        orderId = value;
        lastKey = null;
      case 'awb':
        awb = value;
        lastKey = null;
      case 'event':
        event = value;
        lastKey = '\u0000event';
      case 'qc':
        qc = value;
        lastKey = null;
      case 'qc_sub':
        qcSub = value;
        lastKey = null;
      default:
        extra[key] = value;
        lastKey = key;
    }
  }

  return ActivityEvent(
    raw: raw,
    time: time,
    mode: mode,
    event: event ?? 'note',
    orderId: (orderId == null || orderId.isEmpty) ? null : orderId,
    awb: (awb == null || awb.isEmpty) ? null : awb,
    qc: (qc == null || qc.isEmpty) ? null : qc,
    qcSub: (qcSub == null || qcSub.isEmpty) ? null : qcSub,
    extra: extra,
  );
}

// ─── Plain words ─────────────────────────────────────────────────────────

enum ActivitySeverity { info, success, warning, error }

/// What one event says, in words.
class ActivityEventInfo {
  final String label;

  /// A second, smaller line (a duration, an error text), or null.
  final String? detail;
  final ActivitySeverity severity;

  /// Housekeeping that is hidden from the story until asked for (camera
  /// start-up, files written ...).
  final bool minor;

  const ActivityEventInfo(this.label, {this.detail, this.severity = ActivitySeverity.info, this.minor = false});
}

String _photoName(String? side) => switch (side) {
      'label' => 'Return label',
      'contents' => 'Package contents',
      'front' => 'Product front',
      'back' => 'Product back',
      'serial' => 'Serial / FPC',
      _ => side == null || side.isEmpty ? 'Photo' : side,
    };

/// "72" seconds -> "1 min 12 s".
String activityDuration(String? seconds) {
  final s = int.tryParse(seconds ?? '');
  if (s == null) return '';
  if (s < 60) return '$s s';
  final m = s ~/ 60;
  final r = s % 60;
  return r == 0 ? '$m min' : '$m min $r s';
}

String _millis(String? ms) {
  final v = int.tryParse(ms ?? '');
  if (v == null) return '';
  return v < 1000 ? '$v ms' : '${(v / 1000).toStringAsFixed(1)} s';
}

String _megabytes(String? bytes) {
  final v = int.tryParse(bytes ?? '');
  if (v == null) return '';
  return '${(v / (1024 * 1024)).toStringAsFixed(1)} MB';
}

String _short(String text, [int max = 140]) {
  final t = text.replaceAll(RegExp(r'\s+'), ' ').trim();
  return t.length <= max ? t : '${t.substring(0, max - 1)}…';
}

/// "damagedDifferent" -> "Damaged + Different".
String activityQcName(String? qc) {
  if (qc == null || qc.isEmpty) return '';
  for (final v in QCVerdict.values) {
    if (v.name == qc) {
      return switch (v) {
        QCVerdict.ok => 'OK',
        QCVerdict.damaged => 'Damaged',
        QCVerdict.different => 'Different item',
        QCVerdict.damagedDifferent => 'Damaged + Different',
        QCVerdict.emptyBox => 'Empty box',
      };
    }
  }
  return _prettify(qc);
}

/// "heavilyDamaged+minorDamage" -> "Heavily damaged, Minor damage".
String activityQcSubName(String? sub) {
  if (sub == null || sub.isEmpty) return '';
  return sub.split('+').map((name) {
    for (final r in QCSubReason.values) {
      if (r.name == name) {
        final t = r.shortLabel.toLowerCase();
        return t[0].toUpperCase() + t.substring(1);
      }
    }
    return _prettify(name);
  }).join(', ');
}

String _prettify(String id) {
  final spaced = id
      .replaceAll('_', ' ')
      .replaceAllMapped(RegExp(r'([a-z])([A-Z])'), (m) => '${m[1]} ${m[2]!.toLowerCase()}')
      .trim();
  if (spaced.isEmpty) return id;
  return spaced[0].toUpperCase() + spaced.substring(1);
}

String _autoSaveReason(String? reason) => switch (reason) {
      'setting_off' => 'auto-save is switched off',
      'order_id_invalid' => 'the Order ID is not complete',
      'awb_missing' => 'the AWB was not read yet',
      'awb_needs_review' => 'the AWB needs checking',
      'awb_not_12_digits' => 'the AWB is too short',
      'order_id_conflict' => 'barcode and text gave different Order IDs',
      'duplicate' => 'this Order ID is already saved',
      _ => reason == null || reason.isEmpty ? 'a check failed' : reason.replaceAll('_', ' '),
    };

/// One event in plain words.
ActivityEventInfo describeActivityEvent(ActivityEvent e) {
  final x = e.extra;
  switch (e.event) {
    case 'app_open':
      return const ActivityEventInfo('App opened');
    case 'camera_ready':
      final took = _millis(x['init_ms']);
      return ActivityEventInfo('Camera ready', detail: took.isEmpty ? null : 'started in $took', minor: true);
    case 'camera_init_failed':
      return ActivityEventInfo('Camera could not start',
          detail: x['error'] == null ? null : _short(x['error']!), severity: ActivitySeverity.error);
    case 'camera_init_blocked':
      return const ActivityEventInfo('Camera start skipped (already busy)', minor: true);
    case 'camera_dispose_failed':
      return ActivityEventInfo('Camera did not close cleanly',
          detail: x['error'] == null ? null : _short(x['error']!), severity: ActivitySeverity.warning, minor: true);
    case 'dnd_engage':
      return ActivityEventInfo(x['granted'] == 'false' ? 'Do Not Disturb not allowed' : 'Do Not Disturb on', minor: true);
    case 'dnd_prompt_skipped':
      return const ActivityEventInfo('Do Not Disturb prompt skipped', minor: true);
    case 'video_start':
      return const ActivityEventInfo('Recording started');
    case 'video_stop':
      final d = activityDuration(x['duration_sec']);
      return ActivityEventInfo('Recording stopped', detail: d.isEmpty ? null : 'length $d');
    case 'video_stop_failed':
      return ActivityEventInfo('Recording could not be stopped cleanly',
          detail: x['error'] == null ? null : _short(x['error']!), severity: ActivitySeverity.error);
    case 'draft_saved':
      final size = _megabytes(x['size']);
      final salvaged = x['salvaged'] == 'true';
      return ActivityEventInfo(
        salvaged ? 'Video recovered and kept as a draft' : 'Video kept safely as a draft',
        detail: size.isEmpty ? null : size,
        severity: salvaged ? ActivitySeverity.warning : ActivitySeverity.info,
      );
    case 'draft_retained':
      return const ActivityEventInfo('Cancelled - video kept in Drafts', severity: ActivitySeverity.warning);
    case 'draft_promoted':
      return const ActivityEventInfo('Draft saved as an order', severity: ActivitySeverity.success);
    case 'capture_reset':
      return const ActivityEventInfo('Ready for the next recording', minor: true);
    case 'qc_verdict':
      final main = activityQcName(e.qc);
      final sub = x['qc_sub_label'] ?? activityQcSubName(e.qcSub);
      return ActivityEventInfo(
        main.isEmpty ? 'QC reason chosen' : 'QC reason: $main',
        detail: sub.isEmpty ? null : sub,
      );
    case 'photo_saved':
      return ActivityEventInfo('Photo taken - ${_photoName(x['type'])}');
    case 'photo_failed':
      return ActivityEventInfo('Photo failed - ${_photoName(x['type'])}',
          detail: x['error'] == null ? null : _short(x['error']!), severity: ActivitySeverity.error);
    case 'label_popup_open':
      return ActivityEventInfo('Label screen opened',
          detail: x['barcode_mode'] == 'false' ? 'text (OCR) scanner' : 'barcode scanner', minor: true);
    case 'barcode_scanner_first_detection':
      final t = _millis(x['ms_since_open']);
      return ActivityEventInfo('First barcode read', detail: t.isEmpty ? null : 'after $t', minor: true);
    case 'barcode_scanner_stuck':
      return const ActivityEventInfo('Barcode camera was not starting', severity: ActivitySeverity.warning);
    case 'barcode_scanner_retry':
      return const ActivityEventInfo('Barcode scanner restarted', minor: true);
    case 'auto_save_blocked':
      return ActivityEventInfo('Auto-save waited', detail: _autoSaveReason(x['reason']), severity: ActivitySeverity.warning, minor: true);
    case 'barcode_saved':
      final auto = x['auto_source'] != null && x['auto_source'] != 'manual';
      return ActivityEventInfo(
        'Order ID and AWB confirmed',
        detail: auto ? 'saved automatically' : 'saved with the Save button',
      );
    case 'shipment_saved':
      return const ActivityEventInfo('Order saved', severity: ActivitySeverity.success);
    case 'shipment_save_failed':
      return ActivityEventInfo('Order could not be saved',
          detail: x['error'] == null ? null : _short(x['error']!), severity: ActivitySeverity.error);
    case 'meta_written':
      return const ActivityEventInfo('Order details file written', minor: true);
    case 'order_metadata_updated':
      final prev = x['previousId'];
      return ActivityEventInfo(
        'Order edited',
        detail: prev != null && prev != e.orderId ? 'Order ID changed from $prev' : null,
      );
    case 'orphan_sweep':
      final n = x['recovered'] ?? '0';
      return ActivityEventInfo('Recordings recovered after a crash', detail: '$n recovered', severity: ActivitySeverity.warning);
    case 'record_blocked_low_storage':
      final free = _megabytes(x['free_bytes']);
      return ActivityEventInfo('Recording blocked - storage is low',
          detail: free.isEmpty ? null : '$free free', severity: ActivitySeverity.error);
    case 'record_autostop_low_storage':
      final free = _megabytes(x['free_bytes']);
      return ActivityEventInfo('Recording stopped - storage ran out',
          detail: free.isEmpty ? null : '$free free', severity: ActivitySeverity.error);
    case 'record_start_blocked':
      final why = switch (x['reason']) {
        'camera_not_ready' => 'camera not ready',
        'camera_transitioning' => 'camera was switching',
        final r? => r.replaceAll('_', ' '),
        _ => null,
      };
      return ActivityEventInfo('Recording could not start', detail: why, severity: ActivitySeverity.warning);
    case 'note':
      return ActivityEventInfo(_short(e.raw));
    default:
      return ActivityEventInfo(_prettify(e.event));
  }
}

// ─── Groups ──────────────────────────────────────────────────────────────

/// How an order's story ended, for the coloured result chip.
enum ActivityOutcome {
  /// Saved as an order.
  saved,

  /// Recorded but left in Drafts.
  draft,

  /// Something failed and it was not saved.
  problem,

  /// Only an edit of an already saved order.
  edited,

  /// Started but nothing says how it ended.
  incomplete,
}

/// One order's events in a day - or the day's app-level events.
class ActivityGroup {
  final bool isSystem;
  final String? mode;
  String? orderId;
  final List<ActivityEvent> events = [];

  ActivityGroup({required this.isSystem, this.mode, this.orderId});

  DateTime? get start => events.isEmpty ? null : events.first.time;
  DateTime? get end => events.isEmpty ? null : events.last.time;

  /// Latest value seen for each field.
  String? get awb => _last((e) => e.awb);
  String? get qc => _last((e) => e.qc);
  String? get qcSub => _last((e) => e.qcSub);

  String? _last(String? Function(ActivityEvent e) pick) {
    for (var i = events.length - 1; i >= 0; i--) {
      final v = pick(events[i]);
      if (v != null) return v;
    }
    return null;
  }

  bool _has(Set<String> names) => events.any((e) => names.contains(e.event));

  static const _savedEvents = {'shipment_saved', 'draft_promoted'};
  static const _draftEvents = {'draft_saved', 'draft_retained'};
  static const _failEvents = {
    'shipment_save_failed',
    'video_stop_failed',
    'record_blocked_low_storage',
    'record_autostop_low_storage',
  };
  static const _editOnly = {'order_metadata_updated', 'meta_written'};

  ActivityOutcome get outcome {
    if (_has(_savedEvents)) return ActivityOutcome.saved;
    if (_has(_failEvents)) return ActivityOutcome.problem;
    if (events.isNotEmpty && events.every((e) => _editOnly.contains(e.event))) return ActivityOutcome.edited;
    if (_has(_draftEvents)) return ActivityOutcome.draft;
    return ActivityOutcome.incomplete;
  }

  /// Events that went wrong (red), saved or not.
  int get issueCount =>
      events.where((e) => describeActivityEvent(e).severity == ActivitySeverity.error).length;

  int get photoCount => events.where((e) => e.event == 'photo_saved').length;

  /// "1 min 12 s" of the recording, or ''.
  String get videoLength {
    for (var i = events.length - 1; i >= 0; i--) {
      if (events[i].event == 'video_stop') return activityDuration(events[i].extra['duration_sec']);
    }
    return '';
  }

  /// Steps shown by default (housekeeping left out).
  List<ActivityEvent> get majorEvents =>
      events.where((e) => !describeActivityEvent(e).minor).toList();
}

/// One calendar day, grouped.
class ActivityDayModel {
  final DateTime day;

  /// Orders / sessions of the day, newest first.
  final List<ActivityGroup> groups;

  /// App-level events of the day (app opened, recovery ...), or null.
  final ActivityGroup? system;

  const ActivityDayModel(this.day, this.groups, this.system);

  int get orderCount => groups.length;
  int count(ActivityOutcome o) => groups.where((g) => g.outcome == o).length;
  int get problemCount => groups.where((g) => g.outcome == ActivityOutcome.problem || g.issueCount > 0).length;
  int get eventCount => groups.fold(system?.events.length ?? 0, (n, g) => n + g.events.length);
}

/// Events that say what happened in a recording session, as opposed to
/// housekeeping. A session with none of these is folded into the day's
/// app-level group instead of becoming a card.
const _sessionEvents = {
  'video_start', 'video_stop', 'video_stop_failed', 'draft_saved', 'draft_retained', 'qc_verdict',
  'photo_saved', 'photo_failed', 'barcode_saved', 'shipment_saved', 'shipment_save_failed',
  'draft_promoted', 'order_metadata_updated', 'record_blocked_low_storage', 'record_autostop_low_storage',
};

const _editEvents = {'order_metadata_updated', 'meta_written'};

/// Groups one day's lines per order.
///
/// Lines of a capture carry no Order ID until the label is scanned at the end
/// (and RT photos come before it), so lines with a mode but no order are kept
/// in the recording session they belong to - from `video_start` until the
/// session ends - and take the Order ID when it turns up.
ActivityDayModel groupActivityDay(DateTime day, List<String> lines) {
  final events = [for (final l in lines) if (l.trim().isNotEmpty) parseActivityLine(l)];

  final groups = <ActivityGroup>[];
  final system = ActivityGroup(isSystem: true);
  final open = <String, ActivityGroup?>{'PK': null, 'RT': null};
  final pendingTech = <String, List<ActivityEvent>>{'PK': [], 'RT': []};

  ActivityGroup newGroup(String? mode, String? orderId) {
    final g = ActivityGroup(isSystem: false, mode: mode, orderId: orderId);
    groups.add(g);
    return g;
  }

  for (final e in events) {
    final m = e.mode;
    if (e.orderId != null) {
      ActivityGroup? g = m == null ? null : open[m];
      // An edit of a saved order says nothing about a recording that is still
      // open, and a session left dangling hours ago must not swallow a later
      // order either.
      final canAdopt = g != null &&
          g.orderId == null &&
          !_editEvents.contains(e.event) &&
          (g.end == null || e.time == null || e.time!.difference(g.end!) <= const Duration(hours: 3));
      if (g != null && (canAdopt || g.orderId == e.orderId)) {
        g.orderId = e.orderId;
      } else {
        g = null;
        for (var i = groups.length - 1; i >= 0; i--) {
          if (groups[i].orderId == e.orderId && groups[i].mode == m) {
            g = groups[i];
            break;
          }
        }
        g ??= newGroup(m, e.orderId);
      }
      if (m != null && open[m] == null && g.events.isEmpty) open[m] = g;
      g.events.addAll(pendingTech[m] ?? const []);
      pendingTech[m]?.clear();
      g.events.add(e);
      if (m != null && (e.event == 'shipment_saved' || e.event == 'draft_promoted' || e.event == 'shipment_save_failed')) {
        open[m] = null;
      }
    } else if (m == null) {
      system.events.add(e);
    } else {
      var g = open[m];
      if (e.event == 'video_start') {
        g = newGroup(m, null);
        open[m] = g;
        g.events.addAll(pendingTech[m]!);
        pendingTech[m]!.clear();
        g.events.add(e);
      } else if (g != null) {
        g.events.add(e);
        if (e.event == 'capture_reset' || e.event == 'draft_retained') open[m] = null;
      } else if (_sessionEvents.contains(e.event)) {
        g = newGroup(m, null);
        g.events.add(e);
        open[m] = g;
      } else {
        pendingTech[m]!.add(e);
      }
    }
  }

  // Housekeeping that never joined a session, and sessions that are only
  // housekeeping, belong to the day's app-level group.
  for (final list in pendingTech.values) {
    system.events.addAll(list);
  }
  final real = <ActivityGroup>[];
  for (final g in groups) {
    if (g.orderId == null && !g.events.any((e) => _sessionEvents.contains(e.event))) {
      system.events.addAll(g.events);
    } else {
      real.add(g);
    }
  }
  system.events.sort((a, b) => _cmpTime(a.time, b.time));
  real.sort((a, b) => _cmpTime(b.start, a.start)); // newest first
  return ActivityDayModel(day, real, system.events.isEmpty ? null : system);
}

int _cmpTime(DateTime? a, DateTime? b) {
  if (a == null && b == null) return 0;
  if (a == null) return -1;
  if (b == null) return 1;
  return a.compareTo(b);
}

// ─── Find ────────────────────────────────────────────────────────────────

/// Quick filters under the search box.
enum ActivityFilter { all, pk, rt, problems, drafts }

String _alnum(String s) => s.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');

/// Whether [g] answers a search. Order IDs and AWBs are compared without
/// hyphens, spaces or case, so `4071234567` finds `407-1234567-1234567`; any
/// other word (a QC reason, an error text) is looked up in the raw lines.
bool activityGroupMatches(ActivityGroup g, String query) {
  final q = query.trim();
  if (q.isEmpty) return true;
  final digits = _alnum(q);
  if (digits.isNotEmpty) {
    if (g.orderId != null && _alnum(g.orderId!).contains(digits)) return true;
    for (final e in g.events) {
      if (e.awb != null && _alnum(e.awb!).contains(digits)) return true;
    }
  }
  final lower = q.toLowerCase();
  for (final e in g.events) {
    if (e.raw.toLowerCase().contains(lower)) return true;
    final info = describeActivityEvent(e);
    if (info.label.toLowerCase().contains(lower) || (info.detail?.toLowerCase().contains(lower) ?? false)) {
      return true;
    }
  }
  return false;
}

bool _passes(ActivityGroup g, ActivityFilter f) => switch (f) {
      ActivityFilter.all => true,
      ActivityFilter.pk => g.mode == 'PK',
      ActivityFilter.rt => g.mode == 'RT',
      ActivityFilter.problems => g.outcome == ActivityOutcome.problem || g.issueCount > 0,
      ActivityFilter.drafts => g.outcome == ActivityOutcome.draft || g.outcome == ActivityOutcome.incomplete,
    };

/// The days with only the groups that pass [filter] and answer [query]; days
/// left empty are dropped. The app-level group shows only for the "all"
/// filter.
List<ActivityDayModel> filterActivityDays(
  List<ActivityDayModel> days, {
  String query = '',
  ActivityFilter filter = ActivityFilter.all,
}) {
  if (query.trim().isEmpty && filter == ActivityFilter.all) return days;
  final out = <ActivityDayModel>[];
  for (final d in days) {
    final groups = [for (final g in d.groups) if (_passes(g, filter) && activityGroupMatches(g, query)) g];
    final sys = (filter == ActivityFilter.all && d.system != null && activityGroupMatches(d.system!, query))
        ? d.system
        : null;
    if (groups.isEmpty && sys == null) continue;
    out.add(ActivityDayModel(d.day, groups, sys));
  }
  return out;
}

/// [lines] of one raw day that contain [query] (case-insensitive; also the
/// hyphen-free form of an Order ID / AWB), for the raw view.
List<String> filterRawLines(List<String> lines, String query) {
  final q = query.trim();
  if (q.isEmpty) return lines;
  final lower = q.toLowerCase();
  final digits = _alnum(q);
  return [
    for (final l in lines)
      if (l.toLowerCase().contains(lower) || (digits.length >= 4 && _alnum(l).contains(digits))) l,
  ];
}
