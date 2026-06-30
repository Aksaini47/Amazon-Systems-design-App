import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';

/// A screen showing all previously uploaded videos, grouped by date.
/// Tapping a video opens a detail sheet with metadata.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Video> _videos = [];
  bool _loading = true;
  String? _error;

  static const _prefKey = 'backend_url';

  @override
  void initState() {
    super.initState();
    _loadVideos();
  }

  Future<String> _getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getString(_prefKey) ?? 'http://localhost:3001').trimRight().replaceAll(RegExp(r'/$'), '');
  }

  Future<void> _loadVideos() async {
    setState(() { _loading = true; _error = null; });
    try {
      final base = await _getBaseUrl();
      final res = await http.get(
        Uri.parse('$base/api/videos?limit=200'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(seconds: 8));

      if (res.statusCode != 200) throw Exception('Server error ${res.statusCode}');
      final json = jsonDecode(res.body) as Map<String, dynamic>;
      final list = (json['videos'] as List<dynamic>? ?? [])
          .map((v) => Video.fromJson(v as Map<String, dynamic>))
          .toList();
      // Most recent first
      list.sort((a, b) => (b.recordedAt ?? '').compareTo(a.recordedAt ?? ''));
      setState(() { _videos = list; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  /// Group videos by calendar date (YYYY-MM-DD).
  Map<String, List<Video>> get _byDate {
    final map = <String, List<Video>>{};
    for (final v in _videos) {
      final day = (v.recordedAt ?? '').split('T').first;
      final key = day.isEmpty ? 'Unknown date' : day;
      (map[key] ??= []).add(v);
    }
    return map;
  }

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: RfGlassAppBar(
        title: 'Recorded Videos',
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _loadVideos,
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF3B82F6)));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, color: Colors.red, size: 48),
              const SizedBox(height: 12),
              Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red, fontSize: 13)),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: _loadVideos, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (_videos.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.videocam_off, color: Colors.grey, size: 52),
            SizedBox(height: 12),
            Text('No videos uploaded yet', style: TextStyle(color: Colors.grey, fontSize: 15)),
            SizedBox(height: 4),
            Text('Record a packing video to see it here', style: TextStyle(color: Color(0xFF4B5563), fontSize: 12)),
          ],
        ),
      );
    }

    final grouped = _byDate;
    final dates = grouped.keys.toList();

    return RefreshIndicator(
      onRefresh: _loadVideos,
      color: RfColors.navy,
      backgroundColor: RfColors.glassElevated(0.72),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: dates.length,
        itemBuilder: (context, i) {
          final date = dates[i];
          final items = grouped[date]!;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _DateHeader(dateStr: date),
              ...items.map((v) => _VideoTile(video: v)),
            ],
          );
        },
      ),
    );
  }
}

class _DateHeader extends StatelessWidget {
  final String dateStr;
  const _DateHeader({required this.dateStr});

  String _label() {
    try {
      final dt = DateTime.parse(dateStr);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final d = DateTime(dt.year, dt.month, dt.day);
      if (d == today) return 'Today';
      if (d == today.subtract(const Duration(days: 1))) return 'Yesterday';
      return '${dt.day} ${_months[dt.month - 1]} ${dt.year}';
    } catch (_) {
      return dateStr;
    }
  }

  static const _months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
      child: Text(
        _label(),
        style: const TextStyle(
          color: Color(0xFF6B7280),
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.8,
        ),
      ),
    );
  }
}

class _VideoTile extends StatelessWidget {
  final Video video;
  const _VideoTile({required this.video});

  @override
  Widget build(BuildContext context) {
    final isPacking = video.isPacking;
    return InkWell(
      onTap: () => _showDetail(context),
      child: RfGlassContainer(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            // Icon badge
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: isPacking ? RfColors.pkAccent : RfColors.navyDeep,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                isPacking ? Icons.inventory_2_rounded : Icons.unarchive_rounded,
                color: isPacking ? RfColors.pkAccent : RfColors.rtAccent,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: isPacking ? RfColors.pkAccent : RfColors.navyDeep,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          isPacking ? 'PACKING' : 'UNPACKING',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.5,
                            color: isPacking ? RfColors.pkAccent : RfColors.rtAccent,
                          ),
                        ),
                      ),
                      if (video.fbaShipmentId != null) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: RfColors.navyDeep,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('FBA', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 0.5, color: Color(0xFFA78BFA))),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    video.orderId ?? video.fbaShipmentId ?? '—',
                    style: const TextStyle(color: Color(0xFF93C5FD), fontFamily: 'monospace', fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _formatTime(video.recordedAt),
                    style: const TextStyle(color: Color(0xFF4B5563), fontSize: 11),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            // Duration + size
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(video.durationLabel, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, fontWeight: FontWeight.w500)),
                const SizedBox(height: 2),
                Text(video.sizeLabel, style: const TextStyle(color: Color(0xFF4B5563), fontSize: 10)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatTime(String? isoStr) {
    if (isoStr == null) return '';
    try {
      final dt = DateTime.parse(isoStr).toLocal();
      final h = dt.hour > 12 ? dt.hour - 12 : (dt.hour == 0 ? 12 : dt.hour);
      final m = dt.minute.toString().padLeft(2, '0');
      final ampm = dt.hour >= 12 ? 'PM' : 'AM';
      return '$h:$m $ampm';
    } catch (_) {
      return isoStr;
    }
  }

  void _showDetail(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => RfGlassSheet(child: _VideoDetail(video: video)),
    );
  }
}

class _VideoDetail extends StatelessWidget {
  final Video video;
  const _VideoDetail({required this.video});

  @override
  Widget build(BuildContext context) {
    final rows = <_DetailRow>[
      _DetailRow('Type', video.type.toUpperCase()),
      if (video.orderId != null) _DetailRow('Order ID', video.orderId!),
      if (video.fbaShipmentId != null) _DetailRow('FBA Shipment', video.fbaShipmentId!),
      if (video.fbaBoxNumber != null) _DetailRow('Box Number', 'Box ${video.fbaBoxNumber}'),
      _DetailRow('Duration', video.durationLabel),
      _DetailRow('File Size', video.sizeLabel.isEmpty ? '—' : video.sizeLabel),
      if (video.fileName != null) _DetailRow('File', video.fileName!),
      if (video.recordedAt != null) _DetailRow('Recorded', video.recordedAt!),
    ];

    return Padding(
      padding: EdgeInsets.only(
        top: 20,
        left: 20,
        right: 20,
        bottom: 20 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                video.isPacking ? 'Packing Video' : 'Unpacking Video',
                style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.grey),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...rows.map((r) => _DetailRowWidget(row: r)),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}

class _DetailRow {
  final String label;
  final String value;
  const _DetailRow(this.label, this.value);
}

class _DetailRowWidget extends StatelessWidget {
  final _DetailRow row;
  const _DetailRowWidget({required this.row});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(row.label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
          ),
          Expanded(
            child: Text(
              row.value,
              style: const TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace'),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
