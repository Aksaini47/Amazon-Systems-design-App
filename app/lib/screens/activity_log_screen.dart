import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/activity_log_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';

/// Scrollable viewer for the last 60 days of plain-text activity logs.
class ActivityLogScreen extends StatefulWidget {
  const ActivityLogScreen({super.key});

  @override
  State<ActivityLogScreen> createState() => _ActivityLogScreenState();
}

class _ActivityLogScreenState extends State<ActivityLogScreen> {
  String _content = '';
  String _logPath = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final path = await ActivityLogService.logsDirectoryPath();
    final text = await ActivityLogService.readLastDays(ActivityLogService.retentionDays);
    if (!mounted) return;
    setState(() {
      _logPath = path;
      _content = text;
      _loading = false;
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
      showMeshOrbs: false,
      appBar: RfGlassAppBar(
        title: 'Activity log',
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
          IconButton(
            tooltip: 'Copy folder path',
            onPressed: _logPath.isEmpty ? null : _copyPath,
            icon: const Icon(Icons.copy_rounded),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Colors.white38))
          : Column(
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
                      padding: const EdgeInsets.all(12),
                      child: Scrollbar(
                        thumbVisibility: true,
                        child: SingleChildScrollView(
                          primary: true,
                          child: SelectableText(
                            _content,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontFamily: 'monospace',
                              height: 1.45,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
