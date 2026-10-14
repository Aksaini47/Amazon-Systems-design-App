import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/activity_log_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';
import '../widgets/rf_fast_scroller.dart';

/// One calendar day of the activity log: the day and its raw log lines.
class ActivityLogDay {
  final DateTime day;
  final List<String> lines;

  const ActivityLogDay(this.day, this.lines);

  /// The non-empty lines of a day file (tolerates CRLF).
  static List<String> splitLines(String content) => [
        for (final raw in content.split('\n'))
          if (raw.trim().isNotEmpty) raw.trimRight(),
      ];
}

enum ActivityLogRowKind { header, lines, footer }

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/// "Wed, 14 Oct 2026" — the title of a day block and the fast-scroll bubble.
@visibleForTesting
String activityDayTitle(DateTime day) =>
    '${_weekdays[day.weekday - 1]}, ${day.day} ${_months[day.month - 1]} ${day.year}';

/// The whole log as one flat list of rows — per day a date header, its log
/// lines in blocks of [linesPerBlock], then a closing rule — with every row's
/// height measured up front.
///
/// Exact heights are what make the fast scroller honest: the list knows its
/// true length (no estimate that shifts while you drag), and a scroll offset
/// maps straight back to the day under it for the bubble. Lines wrap, so the
/// heights come from laying the text out at the real width; that is done in
/// short slices so the UI keeps painting while a few thousand lines measure,
/// and the newest days are handed out early ([measure]'s `onFirstBatch`) so
/// the screen does not wait for the whole 60 days.
///
/// Rows are blocks of lines rather than single lines because a list with
/// per-row extents re-adds all of them on every layout pass (O(rows) per
/// frame): thousands of one-line rows would make deep scrolling stutter.
class ActivityLogLayout {
  /// Room taken by a day's date header and by its closing rule, and the gap
  /// kept under every log line.
  static const headerExtent = 66.0;
  static const footerExtent = 40.0;
  static const lineGap = 4.0;

  /// Log lines per list row.
  static const linesPerBlock = 8;

  /// `inherit: false` so the ambient theme cannot change the metrics the rows
  /// were measured with.
  static const lineStyle = TextStyle(
    inherit: false,
    color: RfColors.textPrimary,
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: FontWeight.w400,
    fontStyle: FontStyle.normal,
    height: 1.45,
    letterSpacing: 0,
    wordSpacing: 0,
  );

  final List<ActivityLogDay> days;

  /// Width the lines were wrapped at, and the text scale they were measured at.
  final double width;
  final TextScaler textScaler;

  final List<double> _extents;
  final List<double> _starts; // _starts[i] = top of row i, last = total height
  final List<int> _rowDay;
  final List<int> _dayFirstRow;

  ActivityLogLayout._(
    this.days,
    this.width,
    this.textScaler,
    this._extents,
    this._rowDay,
    this._dayFirstRow,
  ) : _starts = _prefixSums(_extents);

  static List<double> _prefixSums(List<double> extents) {
    final starts = List<double>.filled(extents.length + 1, 0);
    for (var i = 0; i < extents.length; i++) {
      starts[i + 1] = starts[i] + extents[i];
    }
    return starts;
  }

  /// Measures [days] wrapped at [width]. Yields to the event loop every few
  /// milliseconds; returns null if [isCancelled] turns true meanwhile.
  ///
  /// When more days follow, [onFirstBatch] gets a layout of the first whole
  /// days holding at least [firstBatchLines] lines as soon as they are
  /// measured (its rows are exactly the first rows of the final layout), so a
  /// long log shows its newest days at once and fills in the rest behind them.
  static Future<ActivityLogLayout?> measure({
    required List<ActivityLogDay> days,
    required double width,
    required TextScaler textScaler,
    bool Function()? isCancelled,
    void Function(ActivityLogLayout firstDays)? onFirstBatch,
    int firstBatchLines = 250,
    Duration slice = const Duration(milliseconds: 6),
  }) async {
    final painter = TextPainter(textDirection: TextDirection.ltr, textScaler: textScaler);
    final extents = <double>[];
    final rowDay = <int>[];
    final dayFirstRow = <int>[];
    final clock = Stopwatch()..start();
    var measuredLines = 0;
    var batchPending = onFirstBatch != null;
    try {
      for (var d = 0; d < days.length; d++) {
        dayFirstRow.add(extents.length);
        extents.add(headerExtent);
        rowDay.add(d);
        var blockExtent = 0.0;
        var inBlock = 0;
        for (final line in days[d].lines) {
          painter
            ..text = TextSpan(text: line, style: lineStyle)
            ..layout(maxWidth: width);
          blockExtent += painter.height + lineGap;
          if (++inBlock == linesPerBlock) {
            extents.add(blockExtent);
            rowDay.add(d);
            blockExtent = 0;
            inBlock = 0;
          }
          if (clock.elapsed > slice) {
            await Future<void>.delayed(Duration.zero);
            if (isCancelled?.call() ?? false) return null;
            clock.reset();
          }
        }
        if (inBlock > 0) {
          extents.add(blockExtent);
          rowDay.add(d);
        }
        extents.add(footerExtent);
        rowDay.add(d);
        measuredLines += days[d].lines.length;
        if (batchPending && measuredLines >= firstBatchLines && d + 1 < days.length) {
          batchPending = false;
          onFirstBatch!(ActivityLogLayout._(
            days.sublist(0, d + 1),
            width,
            textScaler,
            List.of(extents),
            List.of(rowDay),
            List.of(dayFirstRow),
          ));
          // Let that first frame paint before measuring on.
          await Future<void>.delayed(Duration.zero);
          if (isCancelled?.call() ?? false) return null;
          clock.reset();
        }
      }
    } finally {
      painter.dispose();
    }
    return ActivityLogLayout._(days, width, textScaler, extents, rowDay, dayFirstRow);
  }

  int get rowCount => _extents.length;
  double get totalExtent => _starts.last;
  double extentAt(int row) => _extents[row];
  int dayOfRow(int row) => _rowDay[row];

  /// Rows holding the [lineCount] lines of one day.
  static int blocksFor(int lineCount) => (lineCount + linesPerBlock - 1) ~/ linesPerBlock;

  ActivityLogRowKind kindAt(int row) {
    final d = _rowDay[row];
    final local = row - _dayFirstRow[d];
    if (local == 0) return ActivityLogRowKind.header;
    return local > blocksFor(days[d].lines.length)
        ? ActivityLogRowKind.footer
        : ActivityLogRowKind.lines;
  }

  /// The log lines of a [ActivityLogRowKind.lines] row.
  List<String> linesAt(int row) {
    final d = _rowDay[row];
    final all = days[d].lines;
    final start = (row - _dayFirstRow[d] - 1) * linesPerBlock;
    return all.sublist(start, math.min(start + linesPerBlock, all.length));
  }

  /// The row whose top is at or above [offset] — i.e. the row that covers it.
  int rowAtOffset(double offset) {
    var lo = 0;
    var hi = rowCount - 1;
    while (lo < hi) {
      final mid = (lo + hi + 1) >> 1;
      if (_starts[mid] <= offset) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }
    return lo;
  }

  /// Index into [days] of the day block covering [offset].
  int dayAtOffset(double offset) => _rowDay[rowAtOffset(offset)];
}

/// What the screen shows: the log folder and the days that have entries
/// (newest first).
typedef ActivityLogSnapshot = ({String path, List<ActivityLogDay> days});

/// The shape of [ActivityLogLayout.measure] the screen depends on.
typedef ActivityLogMeasurer = Future<ActivityLogLayout?> Function({
  required List<ActivityLogDay> days,
  required double width,
  required TextScaler textScaler,
  bool Function()? isCancelled,
  void Function(ActivityLogLayout firstDays)? onFirstBatch,
});

Future<ActivityLogSnapshot> _readDeviceLog() async {
  final path = await ActivityLogService.logsDirectoryPath();
  final listed = await ActivityLogService.listLogDays();
  final days = <ActivityLogDay>[];
  for (final day in listed) {
    final lines = ActivityLogDay.splitLines(await ActivityLogService.readDay(day));
    if (lines.isNotEmpty) days.add(ActivityLogDay(day, lines));
  }
  return (path: path, days: days);
}

/// Scrollable viewer for the last 60 days of plain-text activity logs, one
/// blue-ruled block per day, with a Google-style fast scroller on the right.
class ActivityLogScreen extends StatefulWidget {
  const ActivityLogScreen({
    super.key,
    this.loader = _readDeviceLog,
    this.measurer = ActivityLogLayout.measure,
  });

  /// Where the days come from — the on-device log files. Tests pass canned data.
  final Future<ActivityLogSnapshot> Function() loader;

  /// How the rows get their heights. Tests step it by hand.
  final ActivityLogMeasurer measurer;

  @override
  State<ActivityLogScreen> createState() => _ActivityLogScreenState();
}

class _ActivityLogScreenState extends State<ActivityLogScreen> {
  /// Space on the right of the lines for the fast-scroller thumb, and above
  /// the first / below the last row of the list.
  static const _gutter = 14.0;
  static const _listPadTop = 4.0;
  static const _listPadBottom = 8.0;

  final ScrollController _scroll = ScrollController();

  List<ActivityLogDay>? _days;
  ActivityLogLayout? _layout;

  /// False while [_layout] only holds the newest days and the rest is still
  /// being measured.
  bool _layoutComplete = false;
  DateTime _loadedAt = DateTime.now();
  String _logPath = '';
  bool _loading = true;

  /// Bumped whenever the measurement in flight stops being wanted (new data,
  /// new width, screen gone).
  int _measureToken = 0;
  ({double width, TextScaler scaler})? _measuring;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _measureToken++;
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    ActivityLogSnapshot snapshot;
    try {
      snapshot = await widget.loader();
    } catch (e) {
      // Never leave the spinner up for ever — show the empty state instead.
      debugPrint('ActivityLogScreen: loading the log failed: $e');
      snapshot = (path: _logPath, days: const <ActivityLogDay>[]);
    }
    if (!mounted) return;
    _measureToken++;
    setState(() {
      _logPath = snapshot.path;
      _days = snapshot.days;
      _layout = null;
      _layoutComplete = false;
      _measuring = null;
      _loadedAt = DateTime.now();
      _loading = false;
    });
  }

  /// Makes sure a layout for this width / text scale is measured or being
  /// measured. Called from build, so the work itself starts after the frame.
  void _ensureLayout(double width, TextScaler scaler) {
    final days = _days;
    if (days == null || days.isEmpty) return;
    final current = _layout;
    if (current != null && current.width == width && current.textScaler == scaler) return;
    final inFlight = _measuring;
    if (inFlight != null && inFlight.width == width && inFlight.scaler == scaler) return;

    _measuring = (width: width, scaler: scaler);
    final token = ++_measureToken;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted || token != _measureToken) return;
      final layout = await widget.measurer(
        days: days,
        width: width,
        textScaler: scaler,
        isCancelled: () => !mounted || token != _measureToken,
        onFirstBatch: (firstDays) {
          if (!mounted || token != _measureToken) return;
          setState(() {
            _layout = firstDays;
            _layoutComplete = false;
          });
        },
      );
      if (layout == null || !mounted || token != _measureToken) return;
      setState(() {
        _layout = layout;
        _layoutComplete = true;
        _measuring = null;
      });
    });
  }

  Future<void> _copyPath() async {
    await Clipboard.setData(ClipboardData(text: _logPath));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Log folder path copied'),
      duration: Duration(milliseconds: 1600),
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: RfGlassAppBar(
        title: 'Activity log',
        actions: [
          RfIconButton(
            icon: Icons.refresh_rounded,
            tooltip: 'Refresh',
            size: 40,
            onPressed: _loading ? null : _load,
          ),
          const SizedBox(width: 8),
          RfIconButton(
            icon: Icons.copy_rounded,
            tooltip: 'Copy folder path',
            size: 40,
            onPressed: _logPath.isEmpty ? null : _copyPath,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Text(
              'Last ${ActivityLogService.retentionDays} days · $_logPath',
              style: const TextStyle(color: RfColors.textSecondary, fontSize: 11),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
              child: RfGlassContainer(
                blurEnabled: false,
                padding: const EdgeInsets.fromLTRB(12, 6, 4, 6),
                child: _content(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _content() {
    const spinner = Center(child: CircularProgressIndicator(color: RfColors.textMuted));
    final days = _days;
    if (_loading || days == null) return spinner;
    if (days.isEmpty) {
      return const Center(
        child: Text(
          'No activity logged yet.',
          style: TextStyle(color: RfColors.textSecondary, fontSize: 13),
        ),
      );
    }
    return LayoutBuilder(builder: (context, constraints) {
      final width = constraints.maxWidth - _gutter;
      final scaler = MediaQuery.textScalerOf(context);
      _ensureLayout(width, scaler);
      final layout = _layout;
      if (layout == null || layout.width != width || layout.textScaler != scaler) {
        return spinner;
      }
      // While older days are still being measured the list ends in a
      // "loading" row and the thumb stays away: the list is not its final
      // length yet, so a drag would not land where the thumb says.
      final complete = _layoutComplete;
      return RfFastScroller(
        controller: _scroll,
        enabled: complete,
        labelAt: (offset) => activityDayTitle(layout.days[layout.dayAtOffset(offset - _listPadTop)].day),
        child: SelectionArea(
          child: ListView.custom(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(0, _listPadTop, _gutter, _listPadBottom),
            itemExtentBuilder: (row, _) =>
                row < layout.rowCount ? layout.extentAt(row) : _LoadingOlderDays.extent,
            childrenDelegate: _MeasuredRowsDelegate(
              builder: (context, row) =>
                  row < layout.rowCount ? _buildRow(layout, row) : const _LoadingOlderDays(),
              childCount: layout.rowCount + (complete ? 0 : 1),
              totalExtent: layout.totalExtent + (complete ? 0 : _LoadingOlderDays.extent),
            ),
          ),
        ),
      );
    });
  }

  Widget _buildRow(ActivityLogLayout layout, int row) {
    switch (layout.kindAt(row)) {
      case ActivityLogRowKind.header:
        final d = layout.dayOfRow(row);
        final day = layout.days[d];
        return _DayHeader(
          key: ValueKey('activity_day_header_$d'),
          day: day.day,
          events: day.lines.length,
          now: _loadedAt,
        );
      case ActivityLogRowKind.lines:
        return _LogLines(layout.linesAt(row));
      case ActivityLogRowKind.footer:
        return _DayFooter(key: ValueKey('activity_day_footer_${layout.dayOfRow(row)}'));
    }
  }
}

/// Tells the list its true length. Without this a list with per-row extents
/// still *extrapolates* its length from the average of the rows built so far,
/// so the scroll extent — and with it the fast-scroll thumb — would drift as
/// rows get built.
class _MeasuredRowsDelegate extends SliverChildBuilderDelegate {
  _MeasuredRowsDelegate({
    required NullableIndexedWidgetBuilder builder,
    required int childCount,
    required this.totalExtent,
  }) : super(builder, childCount: childCount, addAutomaticKeepAlives: false);

  final double totalExtent;

  @override
  double? estimateMaxScrollOffset(
    int firstIndex,
    int lastIndex,
    double leadingScrollOffset,
    double trailingScrollOffset,
  ) =>
      totalExtent;
}

/// A block of consecutive log lines, each exactly as tall as it was measured.
class _LogLines extends StatelessWidget {
  final List<String> lines;

  const _LogLines(this.lines);

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final line in lines)
          Padding(
            padding: const EdgeInsets.only(bottom: ActivityLogLayout.lineGap),
            child: Text(line, style: ActivityLogLayout.lineStyle),
          ),
      ],
    );
  }
}

/// Last row while older days are still being measured.
class _LoadingOlderDays extends StatelessWidget {
  const _LoadingOlderDays();

  static const extent = 56.0;

  @override
  Widget build(BuildContext context) {
    return const SelectionContainer.disabled(
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(strokeWidth: 2, color: RfColors.textMuted),
          ),
          SizedBox(width: 10),
          Text(
            'Loading older days…',
            style: TextStyle(color: RfColors.textMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

/// Opening of a day's block: its date on a blue glass pill between two blue
/// rules that fade out towards the edges, and a small "Today · 87 events" line.
class _DayHeader extends StatelessWidget {
  final DateTime day;
  final int events;
  final DateTime now;

  const _DayHeader({super.key, required this.day, required this.events, required this.now});

  static const _rule = 1.2;

  @override
  Widget build(BuildContext context) {
    final count = events == 1 ? '1 event' : '$events events';
    final caption = DateUtils.isSameDay(day, now)
        ? 'Today · $count'
        : DateUtils.isSameDay(day, now.subtract(const Duration(days: 1)))
            ? 'Yesterday · $count'
            : count;
    // Decorative chrome: fixed size, never selected / copied with the lines.
    return SelectionContainer.disabled(
      child: MediaQuery.withNoTextScaling(
        child: Padding(
          padding: const EdgeInsets.only(top: 12, bottom: 8),
          child: Column(
            children: [
              SizedBox(
                height: 28,
                child: LayoutBuilder(builder: (context, constraints) {
                  // Keep a stub of rule on both sides however long the title is.
                  final maxPill = (constraints.maxWidth - 2 * (24 + 10)).clamp(0.0, double.infinity);
                  return Row(
                    children: [
                      const Expanded(child: _FadingRule(brightEnd: Alignment.centerRight)),
                      const SizedBox(width: 10),
                      ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: maxPill),
                        child: RfGlassSurface(
                          tint: RfColors.info,
                          strength: 0.16,
                          height: 28,
                          padding: const EdgeInsets.symmetric(horizontal: 14),
                          // widthFactor: shrink-wrap the title, do not fill maxPill.
                          child: Center(
                            widthFactor: 1,
                            child: Text(
                              activityDayTitle(day),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: RfColors.info,
                                fontSize: 12.5,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.3,
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      const Expanded(child: _FadingRule(brightEnd: Alignment.centerLeft)),
                    ],
                  );
                }),
              ),
              const SizedBox(height: 4),
              SizedBox(
                height: 14,
                child: Text(
                  caption,
                  style: TextStyle(
                    color: RfColors.info.withValues(alpha: 0.75),
                    fontSize: 11,
                    height: 1.2,
                    letterSpacing: 0.2,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Closing of a day's block: a hairline blue rule that fades out at both ends,
/// with room above and below so the next day does not run into it.
class _DayFooter extends StatelessWidget {
  const _DayFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return SelectionContainer.disabled(
      child: Padding(
        padding: const EdgeInsets.only(top: 14, bottom: 24.8),
        child: Align(
          alignment: Alignment.topCenter,
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  RfColors.info.withValues(alpha: 0),
                  RfColors.info.withValues(alpha: 0.5),
                  RfColors.info.withValues(alpha: 0),
                ],
              ),
            ),
            child: const SizedBox(height: _DayHeader._rule, width: double.infinity),
          ),
        ),
      ),
    );
  }
}

/// A blue hairline that is bright at [brightEnd] and fades to nothing at the
/// other end.
class _FadingRule extends StatelessWidget {
  final Alignment brightEnd;

  const _FadingRule({required this.brightEnd});

  @override
  Widget build(BuildContext context) {
    final bright = RfColors.info.withValues(alpha: 0.7);
    final faded = RfColors.info.withValues(alpha: 0);
    final brightOnRight = brightEnd == Alignment.centerRight;
    return Center(
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: brightOnRight ? [faded, bright] : [bright, faded],
          ),
        ),
        child: const SizedBox(height: _DayHeader._rule, width: double.infinity),
      ),
    );
  }
}
