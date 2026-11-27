import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../utils/activity_log_model.dart';
import '../widgets/rf_fast_scroller.dart';

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// "Wed, 14 Oct 2026".
String activityLongDay(DateTime d) => '${_weekdays[d.weekday - 1]}, ${d.day} ${_months[d.month - 1]} ${d.year}';

/// "Today" / "Yesterday" / "Wed, 14 Oct 2026".
String activityFriendlyDay(DateTime day, DateTime now) {
  if (DateUtils.isSameDay(day, now)) return 'Today';
  if (DateUtils.isSameDay(day, now.subtract(const Duration(days: 1)))) return 'Yesterday';
  return activityLongDay(day);
}

String _hhmm(DateTime? t) =>
    t == null ? '' : '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

String _hhmmss(DateTime? t) => t == null ? '' : '${_hhmm(t)}:${t.second.toString().padLeft(2, '0')}';

Color _outcomeColor(ActivityOutcome o) => switch (o) {
      ActivityOutcome.saved => RfColors.successLight,
      ActivityOutcome.draft => RfColors.amber,
      ActivityOutcome.problem => RfColors.error,
      ActivityOutcome.edited => RfColors.info,
      ActivityOutcome.incomplete => RfColors.textMuted,
    };

String _outcomeLabel(ActivityOutcome o) => switch (o) {
      ActivityOutcome.saved => 'Saved',
      ActivityOutcome.draft => 'Draft',
      ActivityOutcome.problem => 'Problem',
      ActivityOutcome.edited => 'Edited',
      ActivityOutcome.incomplete => 'Not finished',
    };

IconData _outcomeIcon(ActivityOutcome o) => switch (o) {
      ActivityOutcome.saved => Icons.check_circle_rounded,
      ActivityOutcome.draft => Icons.edit_note_rounded,
      ActivityOutcome.problem => Icons.error_rounded,
      ActivityOutcome.edited => Icons.edit_rounded,
      ActivityOutcome.incomplete => Icons.hourglass_empty_rounded,
    };

Color _severityColor(ActivitySeverity s) => switch (s) {
      ActivitySeverity.info => RfColors.textMuted,
      ActivitySeverity.success => RfColors.successLight,
      ActivitySeverity.warning => RfColors.amber,
      ActivitySeverity.error => RfColors.error,
    };

Color _modeColor(String? mode) => mode == 'RT' ? RfColors.rtAccent : RfColors.pkAccent;

/// "QC: Damaged - Heavily damaged" for a group, or ''.
String _qcText(ActivityGroup g) {
  final main = activityQcName(g.qc);
  if (main.isEmpty) return '';
  final sub = activityQcSubName(g.qcSub);
  return sub.isEmpty ? main : '$main · $sub';
}

String _alnum(String s) => s.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');

/// [text] with the part that answers [query] picked out. The query is matched
/// without hyphens / spaces / case, so `4071234567` lights up inside
/// `407-1234567-1234567`.
Widget _highlighted(String text, String query, TextStyle style, {int maxLines = 1}) {
  final q = _alnum(query);
  if (q.isEmpty) return Text(text, style: style, maxLines: maxLines, overflow: TextOverflow.ellipsis);

  final map = <int>[]; // alnum index -> index in text
  final buf = StringBuffer();
  for (var i = 0; i < text.length; i++) {
    final c = text[i].toLowerCase();
    if (RegExp(r'[a-z0-9]').hasMatch(c)) {
      buf.write(c);
      map.add(i);
    }
  }
  final at = buf.toString().indexOf(q);
  if (at < 0) return Text(text, style: style, maxLines: maxLines, overflow: TextOverflow.ellipsis);
  final from = map[at];
  final to = map[at + q.length - 1] + 1;
  return Text.rich(
    TextSpan(children: [
      TextSpan(text: text.substring(0, from)),
      TextSpan(
        text: text.substring(from, to),
        style: style.copyWith(
          color: RfColors.amber,
          fontWeight: FontWeight.w800,
          backgroundColor: RfColors.amber.withValues(alpha: 0.16),
        ),
      ),
      TextSpan(text: text.substring(to)),
    ]),
    style: style,
    maxLines: maxLines,
    overflow: TextOverflow.ellipsis,
  );
}

// ─── Row sizes ───────────────────────────────────────────────────────────
//
// Every row has a size that is worked out up front, so the list knows its
// true length and the fast-scroll thumb lands where it says (the same idea as
// the raw view's measured rows, but nothing needs laying out: the rows are
// single-line and sized from the text scale).

class _Metrics {
  final TextScaler scaler;
  const _Metrics(this.scaler);

  static const double lineHeight = 1.3;
  double e(double px) => scaler.scale(px);

  double get headerTitle => e(15 * 1.25);
  double get headerSummary => e(12 * 1.25);
  double get headerExtent => 16 + headerTitle + 3 + headerSummary + 8;

  double get row1 => e(14 * lineHeight) + 2;
  double get row2 => e(12 * lineHeight) + 8;
  double get row3 => e(12 * lineHeight);
  static const double gap = 8;
  double get cardExtent => 10 + row1 + 6 + row2 + 4 + row3 + 10 + gap;

  double get systemExtent => 12 + e(13 * lineHeight) + 12 + gap;
}

sealed class _Row {
  final int day;
  const _Row(this.day);
}

class _HeaderRow extends _Row {
  const _HeaderRow(super.day);
}

class _GroupRow extends _Row {
  final ActivityGroup group;
  const _GroupRow(super.day, this.group);
}

class _SystemRow extends _Row {
  final ActivityGroup group;
  const _SystemRow(super.day, this.group);
}

class _Plan {
  final List<_Row> rows;
  final List<double> starts; // starts[i] = top of row i, last = total
  final List<int> dayFirstRow;

  _Plan(this.rows, this.starts, this.dayFirstRow);

  factory _Plan.of(List<ActivityDayModel> days, _Metrics m) {
    final rows = <_Row>[];
    final extents = <double>[];
    final dayFirstRow = <int>[];
    for (var d = 0; d < days.length; d++) {
      dayFirstRow.add(rows.length);
      rows.add(_HeaderRow(d));
      extents.add(m.headerExtent);
      for (final g in days[d].groups) {
        rows.add(_GroupRow(d, g));
        extents.add(m.cardExtent);
      }
      final sys = days[d].system;
      if (sys != null) {
        rows.add(_SystemRow(d, sys));
        extents.add(m.systemExtent);
      }
    }
    final starts = List<double>.filled(rows.length + 1, 0);
    for (var i = 0; i < rows.length; i++) {
      starts[i + 1] = starts[i] + extents[i];
    }
    return _Plan(rows, starts, dayFirstRow);
  }

  double get total => starts.last;
  double extentAt(int i) => starts[i + 1] - starts[i];

  int rowAt(double offset) {
    var lo = 0;
    var hi = rows.length - 1;
    while (lo < hi) {
      final mid = (lo + hi + 1) >> 1;
      if (starts[mid] <= offset) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }
    return lo;
  }
}

// ─── The list ────────────────────────────────────────────────────────────

/// The activity log as one card per order, grouped under each day, newest
/// first. Tap a card for its whole story; the raw lines stay under
/// "Technical details" in that sheet.
class ActivityOrdersView extends StatefulWidget {
  /// Already filtered by the search and the quick filters.
  final List<ActivityDayModel> days;
  final String query;
  final DateTime now;

  const ActivityOrdersView({super.key, required this.days, required this.query, required this.now});

  @override
  State<ActivityOrdersView> createState() => ActivityOrdersViewState();
}

class ActivityOrdersViewState extends State<ActivityOrdersView> {
  static const _gutter = 14.0;
  static const _padTop = 4.0;
  static const _padBottom = 16.0;

  final ScrollController _scroll = ScrollController();
  _Plan? _plan;
  List<ActivityDayModel>? _planDays;
  TextScaler? _planScaler;

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  _Plan _planFor(TextScaler scaler) {
    if (_plan == null || !identical(_planDays, widget.days) || _planScaler != scaler) {
      _plan = _Plan.of(widget.days, _Metrics(scaler));
      _planDays = widget.days;
      _planScaler = scaler;
    }
    return _plan!;
  }

  /// Scrolls to the day nearest to [day] (the log only has the days that had
  /// activity).
  void jumpToDay(DateTime day) {
    final plan = _plan;
    if (plan == null || widget.days.isEmpty || !_scroll.hasClients) return;
    var best = 0;
    var bestGap = const Duration(days: 100000);
    for (var i = 0; i < widget.days.length; i++) {
      final gap = widget.days[i].day.difference(day).abs();
      if (gap < bestGap) {
        bestGap = gap;
        best = i;
      }
    }
    final target = plan.starts[plan.dayFirstRow[best]];
    _scroll.animateTo(
      math.min(target, _scroll.position.maxScrollExtent),
      duration: const Duration(milliseconds: 350),
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    final clamped = MediaQuery.textScalerOf(context).clamp(maxScaleFactor: 1.3);
    final plan = _planFor(clamped);
    final metrics = _Metrics(clamped);
    return MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: clamped),
      child: RfFastScroller(
        controller: _scroll,
        labelAt: (offset) {
          if (plan.rows.isEmpty) return '';
          final row = plan.rows[plan.rowAt(offset - _padTop)];
          return activityFriendlyDay(widget.days[row.day].day, widget.now);
        },
        child: ListView.custom(
          controller: _scroll,
          padding: const EdgeInsets.fromLTRB(0, _padTop, _gutter, _padBottom),
          itemExtentBuilder: (row, _) => row < plan.rows.length ? plan.extentAt(row) : 0,
          childrenDelegate: _ExactDelegate(
            builder: (context, i) => i < plan.rows.length ? _build(plan.rows[i], metrics) : null,
            childCount: plan.rows.length,
            totalExtent: plan.total,
          ),
        ),
      ),
    );
  }

  Widget _build(_Row row, _Metrics m) {
    final day = widget.days[row.day];
    switch (row) {
      case _HeaderRow():
        return _DayHeader(key: ValueKey('activity_day_${row.day}'), day: day, now: widget.now, metrics: m);
      case _GroupRow(:final group):
        return _GroupCard(
          group: group,
          query: widget.query,
          metrics: m,
          onTap: () => showActivityGroupSheet(context, group: group, day: day.day, now: widget.now, query: widget.query),
        );
      case _SystemRow(:final group):
        return _SystemCard(
          group: group,
          metrics: m,
          onTap: () => showActivityGroupSheet(context, group: group, day: day.day, now: widget.now, query: widget.query),
        );
    }
  }
}

/// Tells the list its exact length (an item-extent list otherwise estimates it
/// from the rows built so far, so the scroll extent drifts).
class _ExactDelegate extends SliverChildBuilderDelegate {
  _ExactDelegate({
    required NullableIndexedWidgetBuilder builder,
    required int childCount,
    required this.totalExtent,
  }) : super(builder, childCount: childCount, addAutomaticKeepAlives: false);

  final double totalExtent;

  @override
  double? estimateMaxScrollOffset(int firstIndex, int lastIndex, double leadingScrollOffset, double trailingScrollOffset) =>
      totalExtent;
}

TextStyle _ts(double size, {Color color = RfColors.textPrimary, FontWeight weight = FontWeight.w400, bool mono = false, double? height}) =>
    TextStyle(
      color: color,
      fontSize: size,
      fontWeight: weight,
      height: height ?? _Metrics.lineHeight,
      fontFamily: mono ? 'monospace' : null,
    );

// ─── Day header ──────────────────────────────────────────────────────────

class _DayHeader extends StatelessWidget {
  final ActivityDayModel day;
  final DateTime now;
  final _Metrics metrics;

  const _DayHeader({super.key, required this.day, required this.now, required this.metrics});

  @override
  Widget build(BuildContext context) {
    final saved = day.count(ActivityOutcome.saved);
    final drafts = day.count(ActivityOutcome.draft);
    final open = day.count(ActivityOutcome.incomplete);
    final problems = day.problemCount;
    final base = _ts(12, color: RfColors.textSecondary, height: 1.25);

    final spans = <InlineSpan>[
      TextSpan(text: day.orderCount == 1 ? '1 order' : '${day.orderCount} orders'),
      if (saved > 0) TextSpan(text: '  ·  $saved saved', style: base.copyWith(color: RfColors.successLight)),
      if (drafts > 0) TextSpan(text: '  ·  $drafts draft${drafts == 1 ? '' : 's'}', style: base.copyWith(color: RfColors.amber)),
      if (open > 0) TextSpan(text: '  ·  $open not finished'),
      if (problems > 0) TextSpan(text: '  ·  $problems with problems', style: base.copyWith(color: RfColors.error)),
    ];
    final title = activityFriendlyDay(day.day, now);
    final longDay = title == 'Today' || title == 'Yesterday' ? ' · ${activityLongDay(day.day)}' : '';

    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: metrics.headerTitle,
            child: Text.rich(
              TextSpan(children: [
                TextSpan(text: title, style: _ts(15, weight: FontWeight.w800, height: 1.25)),
                if (longDay.isNotEmpty) TextSpan(text: longDay, style: _ts(12, color: RfColors.textMuted, height: 1.25)),
              ]),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(height: 3),
          SizedBox(
            height: metrics.headerSummary,
            child: Text.rich(TextSpan(children: spans), style: base, maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
        ],
      ),
    );
  }
}

// ─── Cards ───────────────────────────────────────────────────────────────

class _ModeBadge extends StatelessWidget {
  final String mode;
  const _ModeBadge(this.mode);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: _modeColor(mode).withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(mode, style: _ts(10, color: _modeColor(mode), weight: FontWeight.w800, height: 1.2)),
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData? icon;
  final String text;
  final Color color;
  const _Chip({this.icon, required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 4),
          ],
          Flexible(
            child: Text(text, maxLines: 1, overflow: TextOverflow.ellipsis, style: _ts(12, color: color, weight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  final ActivityGroup group;
  final String query;
  final _Metrics metrics;
  final VoidCallback onTap;

  const _GroupCard({required this.group, required this.query, required this.metrics, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final g = group;
    final outcome = g.outcome;
    final color = _outcomeColor(outcome);
    final qc = _qcText(g);
    final issues = g.issueCount;
    final hasOrder = g.orderId != null;

    final summary = [
      if (g.awb != null) 'AWB ${g.awb}',
      if (g.videoLength.isNotEmpty) 'Video ${g.videoLength}',
      if (g.photoCount > 0) '${g.photoCount} photo${g.photoCount == 1 ? '' : 's'}',
      '${g.events.length} steps',
    ].join('  ·  ');

    return SizedBox(
      height: metrics.cardExtent,
      child: Padding(
        padding: const EdgeInsets.only(bottom: _Metrics.gap),
        child: Material(
          color: RfColors.card,
          borderRadius: BorderRadius.circular(12),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            onLongPress: hasOrder
                ? () {
                    HapticFeedback.selectionClick();
                    Clipboard.setData(ClipboardData(text: g.orderId!));
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text('Order ID copied'),
                      duration: Duration(milliseconds: 1400),
                      behavior: SnackBarBehavior.floating,
                    ));
                  }
                : null,
            child: Row(
              children: [
                Container(width: 4, color: color),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          height: metrics.row1,
                          child: Row(
                            children: [
                              if (g.mode != null) ...[_ModeBadge(g.mode!), const SizedBox(width: 8)],
                              Expanded(
                                child: hasOrder
                                    ? _highlighted(g.orderId!, query, _ts(14, weight: FontWeight.w700, mono: true))
                                    : Text(
                                        'No Order ID yet',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: _ts(14, color: RfColors.textSecondary, weight: FontWeight.w600),
                                      ),
                              ),
                              const SizedBox(width: 8),
                              Text(_hhmm(g.start), style: _ts(12, color: RfColors.textMuted, mono: true)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 6),
                        SizedBox(
                          height: metrics.row2,
                          child: Row(
                            children: [
                              _Chip(icon: _outcomeIcon(outcome), text: _outcomeLabel(outcome), color: color),
                              if (qc.isNotEmpty) ...[
                                const SizedBox(width: 6),
                                Flexible(child: _Chip(text: qc, color: RfColors.info)),
                              ],
                              if (issues > 0) ...[
                                const SizedBox(width: 6),
                                _Chip(text: issues == 1 ? '1 problem' : '$issues problems', color: RfColors.error),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: 4),
                        SizedBox(
                          height: metrics.row3,
                          child: _highlighted(summary, query, _ts(12, color: RfColors.textSecondary)),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SystemCard extends StatelessWidget {
  final ActivityGroup group;
  final _Metrics metrics;
  final VoidCallback onTap;

  const _SystemCard({required this.group, required this.metrics, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final n = group.events.length;
    final issues = group.issueCount;
    return SizedBox(
      height: metrics.systemExtent,
      child: Padding(
        padding: const EdgeInsets.only(bottom: _Metrics.gap),
        child: Material(
          color: RfColors.card.withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(12),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              child: Row(
                children: [
                  const Icon(Icons.phone_android_rounded, size: 16, color: RfColors.textMuted),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'App and camera activity',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: _ts(13, color: RfColors.textSecondary, weight: FontWeight.w600),
                    ),
                  ),
                  if (issues > 0) ...[
                    Text('$issues problem${issues == 1 ? '' : 's'}', style: _ts(12, color: RfColors.error, weight: FontWeight.w600)),
                    const SizedBox(width: 8),
                  ],
                  Text('$n step${n == 1 ? '' : 's'}', style: _ts(12, color: RfColors.textMuted)),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right_rounded, size: 18, color: RfColors.textMuted),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Detail sheet ────────────────────────────────────────────────────────

/// One order's story: facts at the top, the steps in plain words, and the raw
/// log lines (verbatim, selectable) under "Technical details".
Future<void> showActivityGroupSheet(
  BuildContext context, {
  required ActivityGroup group,
  required DateTime day,
  required DateTime now,
  String query = '',
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.82,
      minChildSize: 0.4,
      maxChildSize: 0.96,
      builder: (ctx, scroll) => RfGlassSheet(
        child: _GroupSheet(group: group, day: day, now: now, query: query, scroll: scroll),
      ),
    ),
  );
}

class _GroupSheet extends StatefulWidget {
  final ActivityGroup group;
  final DateTime day;
  final DateTime now;
  final String query;
  final ScrollController scroll;

  const _GroupSheet({required this.group, required this.day, required this.now, required this.query, required this.scroll});

  @override
  State<_GroupSheet> createState() => _GroupSheetState();
}

class _GroupSheetState extends State<_GroupSheet> {
  bool _technicalSteps = false;
  bool _rawOpen = false;

  void _copy(String text, String what) {
    HapticFeedback.selectionClick();
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('$what copied'),
      duration: const Duration(milliseconds: 1400),
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final g = widget.group;
    final steps = _technicalSteps ? g.events : g.majorEvents;
    final hidden = g.events.length - g.majorEvents.length;
    final outcome = g.outcome;
    final color = _outcomeColor(outcome);
    final qc = _qcText(g);
    final bottom = MediaQuery.viewPaddingOf(context).bottom;
    final span = g.start == null
        ? ''
        : g.end != null && _hhmm(g.end) != _hhmm(g.start)
            ? '${_hhmm(g.start)} – ${_hhmm(g.end)}'
            : _hhmm(g.start);

    return ListView(
      controller: widget.scroll,
      padding: EdgeInsets.fromLTRB(20, 10, 20, 20 + bottom),
      children: [
        Center(
          child: Container(
            width: 36,
            height: 4,
            decoration: BoxDecoration(color: RfColors.glassBorder(0.2), borderRadius: BorderRadius.circular(2)),
          ),
        ),
        const SizedBox(height: 14),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (g.mode != null) ...[_ModeBadge(g.mode!), const SizedBox(width: 10)],
            Expanded(
              child: g.orderId != null
                  ? _highlighted(g.orderId!, widget.query, _ts(18, weight: FontWeight.w800, mono: true), maxLines: 2)
                  : Text(
                      g.isSystem ? 'App and camera activity' : 'No Order ID yet',
                      style: _ts(18, weight: FontWeight.w800),
                    ),
            ),
            if (g.orderId != null)
              IconButton(
                tooltip: 'Copy Order ID',
                constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                icon: const Icon(Icons.copy_rounded, size: 20, color: RfColors.textSecondary),
                onPressed: () => _copy(g.orderId!, 'Order ID'),
              ),
          ],
        ),
        Text(
          '${activityFriendlyDay(widget.day, widget.now)}${activityFriendlyDay(widget.day, widget.now).contains(',') ? '' : ' · ${activityLongDay(widget.day)}'}'
          '${span.isEmpty ? '' : '  ·  $span'}',
          style: _ts(12.5, color: RfColors.textSecondary),
        ),
        if (!g.isSystem) ...[
          const SizedBox(height: 14),
          Wrap(
            spacing: 18,
            runSpacing: 12,
            children: [
              _Fact('Result', _outcomeLabel(outcome), color: color),
              if (qc.isNotEmpty) _Fact('QC reason', qc),
              if (g.awb != null) _Fact('AWB', g.awb!, mono: true, onCopy: () => _copy(g.awb!, 'AWB')),
              if (g.videoLength.isNotEmpty) _Fact('Video', g.videoLength),
              if (g.photoCount > 0) _Fact('Photos', '${g.photoCount}'),
              if (g.issueCount > 0) _Fact('Problems', '${g.issueCount}', color: RfColors.error),
            ],
          ),
        ],
        const SizedBox(height: 20),
        Text('WHAT HAPPENED', style: _ts(11, color: RfColors.textSecondary, weight: FontWeight.w700, height: 1.2).copyWith(letterSpacing: 1.2)),
        const SizedBox(height: 8),
        if (steps.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('Only technical steps were logged.', style: _ts(13, color: RfColors.textMuted)),
          ),
        for (var i = 0; i < steps.length; i++) _Step(event: steps[i], last: i == steps.length - 1),
        if (hidden > 0)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => setState(() => _technicalSteps = !_technicalSteps),
              icon: Icon(_technicalSteps ? Icons.visibility_off_rounded : Icons.visibility_rounded, size: 18),
              label: Text(_technicalSteps ? 'Hide $hidden technical steps' : 'Show $hidden more technical steps'),
              style: TextButton.styleFrom(minimumSize: const Size(48, 48), foregroundColor: RfColors.info),
            ),
          ),
        const SizedBox(height: 8),
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            key: const ValueKey('activity_raw_lines'),
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.zero,
            initiallyExpanded: _rawOpen,
            onExpansionChanged: (v) => _rawOpen = v,
            iconColor: RfColors.textSecondary,
            collapsedIconColor: RfColors.textSecondary,
            title: Text('Technical details · ${g.events.length} log lines',
                style: _ts(13, color: RfColors.textSecondary, weight: FontWeight.w600)),
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => _copy(g.events.map((e) => e.raw).join('\n'), 'Log lines'),
                  icon: const Icon(Icons.copy_all_rounded, size: 18),
                  label: const Text('Copy all lines'),
                  style: TextButton.styleFrom(minimumSize: const Size(48, 48), foregroundColor: RfColors.info),
                ),
              ),
              SelectableText(
                g.events.map((e) => e.raw).join('\n\n'),
                style: const TextStyle(color: RfColors.textPrimary, fontSize: 11.5, fontFamily: 'monospace', height: 1.45),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Fact extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;
  final bool mono;
  final VoidCallback? onCopy;

  const _Fact(this.label, this.value, {this.color, this.mono = false, this.onCopy});

  @override
  Widget build(BuildContext context) {
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: _ts(11, color: RfColors.textMuted, height: 1.2)),
        const SizedBox(height: 2),
        Text(value, style: _ts(14, color: color ?? RfColors.textPrimary, weight: FontWeight.w700, mono: mono)),
      ],
    );
    if (onCopy == null) return content;
    return InkWell(onTap: onCopy, borderRadius: BorderRadius.circular(6), child: Padding(padding: const EdgeInsets.all(2), child: content));
  }
}

/// One step of the timeline: time, a dot on a rail, and the words.
class _Step extends StatelessWidget {
  final ActivityEvent event;
  final bool last;

  const _Step({required this.event, required this.last});

  @override
  Widget build(BuildContext context) {
    final info = describeActivityEvent(event);
    final color = _severityColor(info.severity);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 62,
            child: Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Text(_hhmmss(event.time), style: _ts(11.5, color: RfColors.textMuted, mono: true)),
            ),
          ),
          SizedBox(
            width: 18,
            child: Column(
              children: [
                const SizedBox(height: 5),
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: info.severity == ActivitySeverity.info ? Colors.transparent : color,
                    shape: BoxShape.circle,
                    border: Border.all(color: color, width: 2),
                  ),
                ),
                if (!last) Expanded(child: Container(width: 2, color: Colors.white12)),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    info.label,
                    style: _ts(14,
                        color: info.minor ? RfColors.textSecondary : RfColors.textPrimary,
                        weight: info.severity == ActivitySeverity.info ? FontWeight.w500 : FontWeight.w700),
                  ),
                  if (info.detail != null)
                    Text(info.detail!, style: _ts(12, color: info.severity == ActivitySeverity.error ? RfColors.error : RfColors.textSecondary)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
