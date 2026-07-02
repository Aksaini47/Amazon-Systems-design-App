import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:video_player/video_player.dart';
import '../models/capture_session.dart';
import '../services/draft_save_service.dart';
import '../services/file_naming_service.dart';
import '../services/local_storage_service.dart';
import '../utils/debug_session_log.dart';
import '../services/sync_manager.dart';
import '../services/upload_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';
import 'barcode_save_popup.dart';
import 'verdict_bottom_sheet.dart';

/// Local Gallery — browses videos and photos saved on this device.
/// Two tabs: Orders (completed sessions) and Drafts (videos saved on stop
/// before a save flow was completed — includes crash-recovered videos).
class LocalGalleryScreen extends StatefulWidget {
  const LocalGalleryScreen({super.key});

  @override
  State<LocalGalleryScreen> createState() => _LocalGalleryScreenState();
}

class _LocalGalleryScreenState extends State<LocalGalleryScreen> with SingleTickerProviderStateMixin {
  late TabController _tabs;
  List<Map<String, dynamic>> _orders = [];
  List<Map<String, dynamic>> _drafts = [];
  // Drafts grouped by session (mode + time proximity). Each entry is a map:
  //   sessionId, mode ('PK'|'RT'), videoPath, photoPaths, draftPaths,
  //   modifiedAt, sizeBytes, hasRecovered
  List<Map<String, dynamic>> _draftSessions = [];
  bool _loading = true;
  final _storage = LocalStorageService();

  // ─── Multi-select state ──────────────────────────────────────────────
  bool _selectionMode = false;
  final Set<String> _selectedOrders = {};  // by orderId
  // Draft selection is now per-session — key = sessionId
  final Set<String> _selectedDrafts = {};

  int get _selectedCount =>
      _tabs.index == 0 ? _selectedOrders.length : _selectedDrafts.length;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(_onTabChange);
    _reload();
  }

  void _onTabChange() {
    // When tab changes during selection mode, clear the OTHER tab's selection
    // so only one tab's items are ever in the active selection set.
    if (_selectionMode) setState(() {});
  }

  // ─── Selection mode helpers ──────────────────────────────────────────

  void _enterSelectionMode() {
    setState(() => _selectionMode = true);
  }

  void _exitSelectionMode() {
    setState(() {
      _selectionMode = false;
      _selectedOrders.clear();
      _selectedDrafts.clear();
    });
  }

  void _toggleSelectOrder(String orderId) {
    setState(() {
      if (_selectedOrders.contains(orderId)) {
        _selectedOrders.remove(orderId);
      } else {
        _selectedOrders.add(orderId);
      }
    });
  }

  void _toggleSelectDraft(String sessionId) {
    setState(() {
      if (_selectedDrafts.contains(sessionId)) {
        _selectedDrafts.remove(sessionId);
      } else {
        _selectedDrafts.add(sessionId);
      }
    });
  }

  void _selectAll() {
    setState(() {
      if (_tabs.index == 0) {
        _selectedOrders.addAll(_orders.map((o) => o['orderId'] as String));
      } else {
        _selectedDrafts.addAll(_draftSessions.map((d) => d['sessionId'] as String));
      }
    });
  }

  Future<void> _deleteSelected() async {
    final n = _selectedCount;
    if (n == 0) return;
    final kind = _tabs.index == 0 ? 'order${n == 1 ? '' : 's'}' : 'draft${n == 1 ? '' : 's'}';

    // Count selected items that haven't been uploaded yet (Orders tab only —
    // drafts by definition aren't uploaded).
    int notUploaded = 0;
    if (_tabs.index == 0) {
      for (final o in _orders) {
        if (_selectedOrders.contains(o['orderId']) && !(o['isUploaded'] as bool? ?? false)) {
          notUploaded++;
        }
      }
    } else {
      notUploaded = n;  // all drafts are by definition not uploaded
    }

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Delete $n $kind?', style: const TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('This cannot be undone.', style: TextStyle(color: Color(0xFF8B949E), fontSize: 13)),
            if (notUploaded > 0) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0x33FF7B72),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFF7B72)),
                ),
                child: Row(children: [
                  const Icon(Icons.warning_amber_rounded, color: Color(0xFFFF7B72), size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '$notUploaded NOT yet uploaded to backend. Agent will not have this data for SAFE-T claims.',
                      style: const TextStyle(color: Color(0xFFFF7B72), fontSize: 12, fontWeight: FontWeight.w500),
                    ),
                  ),
                ]),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel', style: TextStyle(color: Colors.white54))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text(notUploaded > 0 ? 'Delete anyway' : 'Delete', style: const TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (ok != true) return;
    int deleted = 0;
    if (_tabs.index == 0) {
      for (final id in _selectedOrders.toList()) {
        if (await _storage.deleteOrder(id)) deleted++;
      }
    } else {
      // Selected drafts are now sessionIds — delete every file in each
      // selected session.
      final selectedIds = _selectedDrafts.toList();
      for (final sid in selectedIds) {
        final session = _draftSessions.firstWhere(
          (s) => s['sessionId'] == sid,
          orElse: () => <String, dynamic>{},
        );
        final paths = (session['draftPaths'] as List?)?.cast<String>() ?? const <String>[];
        for (final p in paths) {
          if (await _storage.deleteDraft(p)) deleted++;
        }
      }
    }
    _exitSelectionMode();
    await SyncManager.refreshStatus();
    await _reload();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('$deleted item${deleted == 1 ? '' : 's'} deleted'),
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    }
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() => _loading = true);
    final orders = await _storage.listOrders();
    final drafts = await _storage.listDrafts();
    final sessions = _groupDraftsBySession(drafts);
    // #region agent log
    DebugSessionLog.log(
      location: 'local_gallery_screen.dart:_reload',
      message: 'gallery data loaded',
      hypothesisId: 'H2-H11',
      data: {
        'orderCount': orders.length,
        'draftFileCount': drafts.length,
        'draftSessionCount': sessions.length,
        'draftPaths': drafts.take(5).map((d) => d['path']).toList(),
      },
    );
    // #endregion
    if (!mounted) return;
    setState(() {
      _orders = orders;
      _drafts = drafts;
      _draftSessions = sessions;
      _loading = false;
    });
  }

  /// Group draft files into "sessions" so unsaved recordings show up as
  /// single entries (1 video + its associated photos), matching the order-
  /// card UI. Grouping rules:
  ///   - Same mode prefix (PK_DRAFT or RT_DRAFT)
  ///   - Modified-times within a 10-minute window of each other
  ///   - Each session is anchored on a video (if present); orphan photos
  ///     within the window join the nearest video's session, otherwise
  ///     form their own photo-only session
  ///
  /// Session map fields:
  ///   sessionId       — deterministic key (mode + earliest timestamp ms)
  ///   mode            — 'PK' or 'RT'
  ///   videoPath       — String? (null if photo-only session)
  ///   photoPaths      — List<String>
  ///   draftPaths      — List<String> of ALL files (used for delete-all)
  ///   modifiedAt      — most recent file's modified time (ISO string)
  ///   sizeBytes       — sum of all file sizes
  ///   hasRecovered    — true if any file starts with RECOVERED_
  List<Map<String, dynamic>> _groupDraftsBySession(List<Map<String, dynamic>> drafts) {
    if (drafts.isEmpty) return [];
    // Sort by modifiedAt ascending so the sweep can attach later files to
    // earlier sessions when within the time window.
    final sorted = List<Map<String, dynamic>>.from(drafts)
      ..sort((a, b) => (a['modifiedAt'] as String).compareTo(b['modifiedAt'] as String));

    String modeOf(String fileName) {
      if (fileName.startsWith('PK_')) return 'PK';
      if (fileName.startsWith('RT_')) return 'RT';
      return 'UNKNOWN';
    }

    const windowMs = 10 * 60 * 1000;  // 10 minutes
    final sessions = <Map<String, dynamic>>[];

    for (final d in sorted) {
      final fileName = d['fileName'] as String;
      final mode = modeOf(fileName);
      final isVideo = (d['kind'] as String) == 'video';
      final modAtMs = DateTime.parse(d['modifiedAt'] as String).millisecondsSinceEpoch;
      final isRecovered = fileName.startsWith('RECOVERED_');

      // Find an existing session of same mode within window
      Map<String, dynamic>? target;
      for (final s in sessions) {
        if (s['mode'] != mode) continue;
        final firstMs = s['firstMs'] as int;
        final lastMs = s['lastMs'] as int;
        if ((modAtMs - lastMs).abs() <= windowMs ||
            (modAtMs >= firstMs && modAtMs <= lastMs + windowMs)) {
          target = s;
          break;
        }
      }

      if (target == null) {
        target = {
          'sessionId': '${mode}_$modAtMs',
          'mode': mode,
          'videoPath': null,
          'photoPaths': <String>[],
          'draftPaths': <String>[],
          'firstMs': modAtMs,
          'lastMs': modAtMs,
          'sizeBytes': 0,
          'hasRecovered': false,
        };
        sessions.add(target);
      }

      target['lastMs'] = (target['lastMs'] as int) < modAtMs ? modAtMs : target['lastMs'];
      target['firstMs'] = (target['firstMs'] as int) > modAtMs ? modAtMs : target['firstMs'];
      (target['draftPaths'] as List<String>).add(d['path'] as String);
      target['sizeBytes'] = (target['sizeBytes'] as int) + (d['sizeBytes'] as int);
      if (isRecovered) target['hasRecovered'] = true;

      if (isVideo) {
        // If multiple videos land in the window, keep the latest one as
        // primary — older ones still appear as additional draftPaths for
        // delete-all but only one video plays in the detail view.
        target['videoPath'] = d['path'];
      } else {
        (target['photoPaths'] as List<String>).add(d['path'] as String);
      }
    }

    // Convert firstMs/lastMs into a single modifiedAt ISO timestamp.
    for (final s in sessions) {
      final lastMs = s['lastMs'] as int;
      s['modifiedAt'] = DateTime.fromMillisecondsSinceEpoch(lastMs).toIso8601String();
      s.remove('firstMs');
      s.remove('lastMs');
    }

    // Newest sessions first (matches order list ordering).
    sessions.sort((a, b) => (b['modifiedAt'] as String).compareTo(a['modifiedAt'] as String));
    return sessions;
  }

  /// Generic confirmation dialog.
  /// [warnNotUploaded] adds a red warning block when the item hasn't been
  /// uploaded yet — prevents accidental loss of un-backed-up data.
  Future<bool> _confirmDelete(String label, {bool warnNotUploaded = false}) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete?', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Permanently delete $label?\n\nThis cannot be undone.',
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13),
            ),
            if (warnNotUploaded) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0x33FF7B72),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFF7B72)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: Color(0xFFFF7B72), size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'NOT yet uploaded to backend. Deleting will permanently lose this data — agent will not have it for SAFE-T claim.',
                        style: TextStyle(color: Color(0xFFFF7B72), fontSize: 12, fontWeight: FontWeight.w500),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(
              warnNotUploaded ? 'Delete anyway' : 'Delete',
              style: const TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    );
    return ok ?? false;
  }

  Future<void> _deleteOrder(Map<String, dynamic> order) async {
    final isUploaded = order['isUploaded'] as bool? ?? false;
    final ok = await _confirmDelete(
      'order ${order['orderId']}',
      warnNotUploaded: !isUploaded,
    );
    if (!ok) return;
    final deleted = await _storage.deleteOrder(order['orderId'] as String);
    if (deleted && mounted) {
      // Push a fresh status emit so the home banner reflects the now-smaller
      // queue immediately (deleteOrder already dropped the queue entry).
      await SyncManager.refreshStatus();
      _reload();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Order deleted'),
        duration: Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    }
  }

  /// Delete an entire draft session — every video + every photo within
  /// the same time window. Matches the "delete order" semantics so users
  /// don't have to delete photos one-by-one after deleting the video.
  Future<void> _deleteDraftSession(Map<String, dynamic> session) async {
    final mode = session['mode'] as String;
    final paths = (session['draftPaths'] as List).cast<String>();
    final n = paths.length;
    final ok = await _confirmDelete('$mode draft session ($n file${n == 1 ? '' : 's'})');
    if (!ok) return;
    int deleted = 0;
    for (final p in paths) {
      if (await _storage.deleteDraft(p)) deleted++;
    }
    if (mounted) {
      _reload();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Deleted $deleted file${deleted == 1 ? '' : 's'}'),
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: _selectionMode ? _buildSelectionAppBar() : _buildNormalAppBar(),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Colors.white38))
          : TabBarView(
              controller: _tabs,
              children: [
                _buildOrdersList(),
                _buildDraftsList(),
              ],
            ),
    );
  }

  PreferredSizeWidget _buildNormalAppBar() {
    return RfGlassAppBar(
      title: 'Gallery',
      bottom: TabBar(
        controller: _tabs,
        indicatorColor: RfColors.rtAccent,
        labelColor: Colors.white,
        unselectedLabelColor: Colors.white54,
        tabs: [
          Tab(text: 'Orders (${_orders.length})'),
          Tab(text: 'Drafts (${_draftSessions.length})'),
        ],
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.checklist_rounded),
          tooltip: 'Select',
          onPressed: (_orders.isEmpty && _drafts.isEmpty) ? null : _enterSelectionMode,
        ),
        IconButton(icon: const Icon(Icons.refresh), onPressed: _reload),
      ],
    );
  }

  PreferredSizeWidget _buildSelectionAppBar() {
    final n = _selectedCount;
    final total = _tabs.index == 0 ? _orders.length : _draftSessions.length;
    final allSelected = n == total && total > 0;
    return RfGlassAppBar(
      leading: IconButton(
        icon: const Icon(Icons.close, color: Colors.white),
        onPressed: _exitSelectionMode,
      ),
      titleWidget: Text(
        n == 0 ? 'Select items' : '$n selected',
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
      ),
      bottom: TabBar(
        controller: _tabs,
        indicatorColor: RfColors.rtAccent,
        labelColor: Colors.white,
        unselectedLabelColor: Colors.white54,
        tabs: [
          Tab(text: 'Orders (${_orders.length})'),
          Tab(text: 'Drafts (${_draftSessions.length})'),
        ],
      ),
      actions: [
        TextButton(
          onPressed: total == 0 ? null : (allSelected ? () {
            setState(() {
              if (_tabs.index == 0) _selectedOrders.clear();
              else _selectedDrafts.clear();
            });
          } : _selectAll),
          child: Text(
            allSelected ? 'Clear' : 'Select all',
            style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
          ),
        ),
        IconButton(
          icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
          tooltip: 'Delete selected',
          onPressed: n == 0 ? null : _deleteSelected,
        ),
      ],
    );
  }

  Widget _buildOrdersList() {
    if (_orders.isEmpty) {
      return _buildEmpty('No saved orders yet', 'Complete a PK or RT session to see it here.');
    }
    final uploaded = _orders.where((o) => o['isUploaded'] as bool? ?? false).length;
    final pending = _orders.length - uploaded;
    return RefreshIndicator(
      onRefresh: _reload,
      color: RfColors.rtAccent,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        // +1 for the stats card at index 0
        itemCount: _orders.length + 1,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          if (i == 0) return _buildOrdersStats(uploaded: uploaded, pending: pending);
          final idx = i - 1;
          final o = _orders[idx];
          final id = o['orderId'] as String;
          final selected = _selectedOrders.contains(id);
          return _OrderCard(
            order: o,
            selectionMode: _selectionMode,
            selected: selected,
            onTap: () async {
              if (_selectionMode) {
                _toggleSelectOrder(id);
                return;
              }
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => _OrderDetailScreen(order: o)),
              );
              _reload();
            },
            onLongPress: () {
              if (!_selectionMode) _enterSelectionMode();
              _toggleSelectOrder(id);
            },
            onDelete: () => _deleteOrder(o),
          );
        },
      ),
    );
  }

  /// Compact stats card for the Orders tab — counts synced vs pending.
  /// Tap "Sync all" to push every pending order through the upload pipeline.
  Widget _buildOrdersStats({required int uploaded, required int pending}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: RfGlass.decoration(),
      child: Row(
        children: [
          _statChip(Icons.cloud_done_rounded, '$uploaded uploaded', const Color(0xFF3FB950)),
          const SizedBox(width: 8),
          _statChip(Icons.cloud_off_rounded, '$pending pending', pending == 0 ? const Color(0xFF8B949E) : const Color(0xFFFFA657)),
          const Spacer(),
          if (pending > 0)
            GestureDetector(
              onTap: _syncAllPending,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0x33FFA657),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0x66FFA657)),
                ),
                child: const Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.cloud_upload_outlined, color: Color(0xFFFFA657), size: 14),
                  SizedBox(width: 4),
                  Text('Sync all', style: TextStyle(color: Color(0xFFFFA657), fontSize: 11, fontWeight: FontWeight.w700)),
                ]),
              ),
            ),
        ],
      ),
    );
  }

  Widget _statChip(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, color: color, size: 13),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
      ]),
    );
  }

  /// Push every pending order through the upload pipeline. Uses the same
  /// retry-from-folder method that the Order Detail "Upload" button uses.
  Future<void> _syncAllPending() async {
    final pending = _orders.where((o) => !(o['isUploaded'] as bool? ?? false)).toList();
    if (pending.isEmpty) return;
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Row(children: [
        const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFFFA657))),
        const SizedBox(width: 10),
        Text('Syncing ${pending.length} order${pending.length == 1 ? '' : 's'}…'),
      ]),
      duration: const Duration(seconds: 30),
      backgroundColor: Colors.black87,
    ));
    int ok = 0;
    int failed = 0;
    for (final o in pending) {
      final result = await UploadService.uploadFromFolder(
        orderId: o['orderId'] as String,
        folderPath: o['folderPath'] as String,
      );
      if (result.status == UploadStatus.success) {
        ok++;
      } else {
        failed++;
      }
    }
    if (!mounted) return;
    await SyncManager.refreshStatus();
    await _reload();
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(failed == 0
          ? 'All $ok synced'
          : '$ok synced, $failed still pending (backend offline or error)'),
      duration: const Duration(seconds: 3),
      backgroundColor: Colors.black87,
    ));
  }

  Widget _buildDraftsStats() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: RfGlass.decoration(),
      child: Row(children: [
        _statChip(Icons.drafts_outlined, '${_draftSessions.length} session${_draftSessions.length == 1 ? '' : 's'}', const Color(0xFF8B949E)),
        const SizedBox(width: 6),
        const Expanded(
          child: Text(
            'Capture sessions saved before order ID was assigned — tap to view video + photos',
            style: TextStyle(color: Color(0xFF8B949E), fontSize: 11),
          ),
        ),
      ]),
    );
  }

  Widget _buildDraftsList() {
    if (_draftSessions.isEmpty) {
      return _buildEmpty('No drafts', 'Cancel after stop keeps the video here — tap Finish save to add Order ID.');
    }
    return RefreshIndicator(
      onRefresh: _reload,
      color: RfColors.rtAccent,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        // +1 for stats card
        itemCount: _draftSessions.length + 1,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          if (i == 0) return _buildDraftsStats();
          final idx = i - 1;
          final s = _draftSessions[idx];
          final sid = s['sessionId'] as String;
          final selected = _selectedDrafts.contains(sid);
          return _DraftSessionCard(
            session: s,
            selectionMode: _selectionMode,
            selected: selected,
            onTap: () {
              Navigator.push(context, MaterialPageRoute(
                builder: (_) => _DraftDetailScreen(session: s),
              )).then((_) => _reload());
            },
            onTapInSelectionMode: () => _toggleSelectDraft(sid),
            onLongPress: () {
              if (!_selectionMode) _enterSelectionMode();
              _toggleSelectDraft(sid);
            },
            onDelete: () => _deleteDraftSession(s),
          );
        },
      ),
    );
  }

  Widget _buildEmpty(String title, String subtitle) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.inbox_outlined, color: Color(0xFF4D5565), size: 56),
            const SizedBox(height: 16),
            Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Text(subtitle, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13)),
          ],
        ),
      ),
    );
  }
}

// ─── Photo edit helpers ───────────────────────────────────────────────

enum _PhotoAction { replace, remove, retag }

Future<_PhotoAction?> _showPhotoActionSheet(
  BuildContext context, {
  required String sideLabel,
  bool showRetag = false,
}) {
  return showModalBottomSheet<_PhotoAction>(
    context: context,
    backgroundColor: const Color(0xFF161B22),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0x33FFFFFF),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                sideLabel.toUpperCase(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.camera_alt_outlined, color: Color(0xFF58A6FF)),
            title: const Text('Replace photo', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Capture a new image', style: TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
            onTap: () => Navigator.pop(ctx, _PhotoAction.replace),
          ),
          if (showRetag)
            ListTile(
              leading: const Icon(Icons.label_outline, color: Color(0xFFFFA657)),
              title: const Text('Re-tag photo', style: TextStyle(color: Colors.white)),
              subtitle: const Text('Change side label', style: TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
              onTap: () => Navigator.pop(ctx, _PhotoAction.retag),
            ),
          ListTile(
            leading: const Icon(Icons.delete_outline, color: Colors.redAccent),
            title: const Text('Remove photo', style: TextStyle(color: Colors.redAccent)),
            onTap: () => Navigator.pop(ctx, _PhotoAction.remove),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: GestureDetector(
              onTap: () => Navigator.pop(ctx),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.white10,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Center(child: Text('Cancel', style: TextStyle(color: Colors.white70))),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

Future<bool> _confirmRemovePhoto(BuildContext context, String sideLabel) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: const Text('Remove photo?', style: TextStyle(color: Colors.white)),
      content: Text(
        'Permanently remove the $sideLabel photo?\n\nThis cannot be undone.',
        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
        ),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Remove', style: TextStyle(color: Colors.red)),
        ),
      ],
    ),
  );
  return ok ?? false;
}

PhotoSide? _photoSideFromOrderPath(String path) {
  final filename = path.split(Platform.pathSeparator).last;
  final base = filename.replaceAll(RegExp(r'\.(jpg|jpeg|png)$', caseSensitive: false), '');
  final parts = base.split('_');
  if (parts.length < 3) return null;
  final sideName = parts.last;
  for (final side in PhotoSide.values) {
    if (side.name == sideName) return side;
  }
  return null;
}

// ─── Order card ────────────────────────────────────────────────────────

class _OrderCard extends StatelessWidget {
  final Map<String, dynamic> order;
  final bool selectionMode;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onLongPress;
  final VoidCallback onDelete;

  const _OrderCard({
    required this.order,
    required this.selectionMode,
    required this.selected,
    required this.onTap,
    required this.onLongPress,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final photoPaths = (order['photoPaths'] as List).cast<String>();
    final hasVideo = order['videoPath'] != null;
    final sizeMb = ((order['sizeBytes'] as int) / (1024 * 1024)).toStringAsFixed(1);
    final modified = DateTime.parse(order['modifiedAt'] as String);
    final ts = '${modified.day}/${modified.month}/${modified.year} '
               '${modified.hour.toString().padLeft(2, '0')}:${modified.minute.toString().padLeft(2, '0')}';

    return Material(
      color: selected ? const Color(0x402F81F7) : RfColors.card,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: selected ? const Color(0xFF2F81F7) : RfColors.border, width: selected ? 1.5 : 1),
          ),
          child: Row(
            children: [
              // Selection checkbox (only in selection mode)
              if (selectionMode) ...[
                Icon(
                  selected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: selected ? const Color(0xFF2F81F7) : Colors.white38,
                  size: 22,
                ),
                const SizedBox(width: 10),
              ],
              // Thumbnail — first photo if available, else video icon
              Container(
                width: 64, height: 64,
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white12),
                ),
                clipBehavior: Clip.hardEdge,
                child: photoPaths.isNotEmpty
                    ? Image.file(File(photoPaths.first), fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const Icon(Icons.broken_image, color: Colors.white24))
                    : Icon(hasVideo ? Icons.videocam : Icons.folder, color: Colors.white38, size: 28),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      order['bareOrderId'] as String? ?? order['orderId'] as String,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(ts, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                    const SizedBox(height: 4),
                    Wrap(spacing: 8, runSpacing: 4, children: [
                      if (order['mode'] != null)
                        _chip(
                          Icons.label_outline,
                          (order['mode'] as String).toUpperCase(),
                          (order['mode'] as String) == 'pk'
                              ? const Color(0xFFE86C2B)
                              : const Color(0xFF388BFD),
                        ),
                      _chip(Icons.videocam, hasVideo ? 'Video' : 'No video', hasVideo ? const Color(0xFF3FB950) : const Color(0xFF8B949E)),
                      _chip(Icons.photo, '${photoPaths.length} photo${photoPaths.length == 1 ? '' : 's'}', const Color(0xFF8B949E)),
                      _chip(Icons.sd_storage, '${sizeMb} MB', const Color(0xFF8B949E)),
                      _chip(
                        (order['isUploaded'] as bool? ?? false) ? Icons.cloud_done_rounded : Icons.cloud_off_rounded,
                        (order['isUploaded'] as bool? ?? false) ? 'Uploaded' : 'Pending upload',
                        (order['isUploaded'] as bool? ?? false) ? const Color(0xFF3FB950) : const Color(0xFFFFA657),
                      ),
                    ]),
                  ],
                ),
              ),
              if (!selectionMode)
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                  onPressed: onDelete,
                  tooltip: 'Delete',
                ),
            ],
          ),
        ),
      ),
    );
  }

  static Widget _chip(IconData icon, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 11, color: color),
        const SizedBox(width: 3),
        Text(text, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w500)),
      ]),
    );
  }
}

// ─── Draft session card ────────────────────────────────────────────────
//
// Mirrors _OrderCard layout (thumbnail + title + chips + delete) so the
// drafts list visually matches the orders list. A "session" is a group of
// draft files (1 video + 0-N photos) that were captured close together,
// before the user assigned an Order ID via the save flow.
//
// Replaces the old _DraftCard which showed each file as a separate row
// and forced photos/videos to open in separate viewers — the user
// explicitly asked: "make draft entries similar to order entries / upon
// tap shows video and images". This card opens _DraftDetailScreen which
// renders the inline video player + photos grid, exactly like
// _OrderDetailScreen does for completed orders.

class _DraftSessionCard extends StatelessWidget {
  final Map<String, dynamic> session;
  final bool selectionMode;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onTapInSelectionMode;
  final VoidCallback onLongPress;
  final VoidCallback onDelete;

  const _DraftSessionCard({
    required this.session,
    required this.selectionMode,
    required this.selected,
    required this.onTap,
    required this.onTapInSelectionMode,
    required this.onLongPress,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final mode = session['mode'] as String;
    final videoPath = session['videoPath'] as String?;
    final photoPaths = (session['photoPaths'] as List).cast<String>();
    final sizeMb = ((session['sizeBytes'] as int) / (1024 * 1024)).toStringAsFixed(1);
    final modified = DateTime.parse(session['modifiedAt'] as String);
    final ts = '${modified.day}/${modified.month}/${modified.year} '
               '${modified.hour.toString().padLeft(2, '0')}:${modified.minute.toString().padLeft(2, '0')}';
    final hasRecovered = session['hasRecovered'] as bool? ?? false;
    final hasVideo = videoPath != null;

    // Thumbnail: first photo if available, else video icon
    final Widget thumbnail = photoPaths.isNotEmpty
        ? Image.file(File(photoPaths.first), fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => const Icon(Icons.broken_image, color: Colors.white24))
        : Stack(alignment: Alignment.center, children: [
            Icon(
              hasRecovered ? Icons.restore_rounded : (hasVideo ? Icons.videocam_outlined : Icons.photo),
              color: hasRecovered ? Colors.amber : Colors.white38,
              size: 28,
            ),
            if (hasVideo)
              const Positioned(
                bottom: 4, right: 4,
                child: Icon(Icons.play_arrow_rounded, color: Colors.white70, size: 16),
              ),
          ]);

    final accent = mode == 'PK' ? RfColors.pkAccent : RfColors.rtAccent;

    return Material(
      color: selected ? const Color(0x402F81F7) : RfColors.card,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onLongPress: onLongPress,
        onTap: selectionMode ? onTapInSelectionMode : onTap,
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected
                  ? const Color(0xFF2F81F7)
                  : (hasRecovered ? Colors.amber.withAlpha(120) : RfColors.border),
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              if (selectionMode) ...[
                Icon(
                  selected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: selected ? const Color(0xFF2F81F7) : Colors.white38,
                  size: 22,
                ),
                const SizedBox(width: 10),
              ],
              // Thumbnail
              Container(
                width: 64, height: 64,
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white12),
                ),
                clipBehavior: Clip.hardEdge,
                child: thumbnail,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      // Mode badge (PK/RT) with accent
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(6)),
                        child: Text(
                          '$mode DRAFT',
                          style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                        ),
                      ),
                      const SizedBox(width: 6),
                      const Flexible(
                        child: Text(
                          'No order ID yet',
                          style: TextStyle(color: Color(0xFF8B949E), fontSize: 11, fontStyle: FontStyle.italic),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ]),
                    const SizedBox(height: 4),
                    Text(ts, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                    const SizedBox(height: 4),
                    Wrap(spacing: 8, runSpacing: 4, children: [
                      _chip(Icons.videocam, hasVideo ? 'Video' : 'No video', hasVideo ? const Color(0xFF3FB950) : const Color(0xFF8B949E)),
                      _chip(Icons.photo, '${photoPaths.length} photo${photoPaths.length == 1 ? '' : 's'}', const Color(0xFF8B949E)),
                      _chip(Icons.sd_storage, '$sizeMb MB', const Color(0xFF8B949E)),
                      if (hasRecovered)
                        _chip(Icons.restore_rounded, 'Recovered', Colors.amber),
                    ]),
                  ],
                ),
              ),
              if (!selectionMode)
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                  onPressed: onDelete,
                  tooltip: 'Delete',
                ),
            ],
          ),
        ),
      ),
    );
  }

  static Widget _chip(IconData icon, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 11, color: color),
        const SizedBox(width: 3),
        Text(text, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w500)),
      ]),
    );
  }
}

// ─── Inline video player (used on OrderDetailScreen) ─────────────────

class _InlineVideoPlayer extends StatefulWidget {
  final String path;
  final bool pinchZoom;
  const _InlineVideoPlayer({required this.path, this.pinchZoom = true});

  @override
  State<_InlineVideoPlayer> createState() => _InlineVideoPlayerState();
}

class _InlineVideoPlayerState extends State<_InlineVideoPlayer> {
  VideoPlayerController? _ctrl;
  bool _failed = false;
  bool _showControls = true;
  String? _errorMessage;
  TransformationController? _zoomCtrl;

  @override
  void initState() {
    super.initState();
    if (widget.pinchZoom) _zoomCtrl = TransformationController();
    _init();
  }

  Future<void> _init() async {
    try {
      final file = File(widget.path);
      if (!await file.exists()) {
        setState(() { _failed = true; _errorMessage = 'File missing'; });
        return;
      }
      _ctrl = VideoPlayerController.file(file);
      await _ctrl!.initialize();
      _ctrl!.addListener(() { if (mounted) setState(() {}); });
      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('Video init failed: $e');
      if (mounted) setState(() { _failed = true; _errorMessage = e.toString(); });
    }
  }

  @override
  void dispose() {
    _zoomCtrl?.dispose();
    _ctrl?.dispose();
    super.dispose();
  }

  void _resetVideoZoom() {
    _zoomCtrl?.value = Matrix4.identity();
  }

  void _toggleVideoZoom() {
    final ctrl = _zoomCtrl;
    if (ctrl == null) return;
    final scale = ctrl.value.getMaxScaleOnAxis();
    if (scale > 1.01) {
      ctrl.value = Matrix4.identity();
    } else {
      ctrl.value = Matrix4.identity()..scaleByDouble(2.5);
    }
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) {
      return Container(
        height: 200,
        decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12)),
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.broken_image, color: Colors.white24, size: 40),
            const SizedBox(height: 8),
            Text(_errorMessage ?? 'Could not load video', style: const TextStyle(color: Colors.white54, fontSize: 12)),
          ]),
        ),
      );
    }
    if (_ctrl == null || !_ctrl!.value.isInitialized) {
      return Container(
        height: 200,
        decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12)),
        child: const Center(child: CircularProgressIndicator(color: Colors.white38)),
      );
    }
    final v = _ctrl!.value;
    // ─── ASPECT FIX (no rotation) ─────────────────────────────────────
    //
    // ROOT CAUSE (verified via ffprobe + ffmpeg frame extraction on a
    // real recording):
    //   - MP4 reports coded dimensions 1920×1080 with rotation=-90 in the
    //     Display Matrix side_data
    //   - video_player_android v2.7.x reports value.size = (1920, 1080)
    //     and value.aspectRatio = 1.78 — i.e. it returns the LANDSCAPE
    //     coded dims, ignoring the rotation matrix
    //   - BUT the texture content the platform decoder hands to the
    //     player IS already pre-rotated portrait pixels (1080×1920) —
    //     extracting a frame with `ffmpeg -frames:v 1` produces a 1080×1920
    //     portrait image. The texture content matches what's stored.
    //
    // So: the player widget needs a PORTRAIT-shaped slot. If we render
    // it into a landscape AspectRatio (1.78), the portrait texture gets
    // squished into a landscape rectangle → that's the "stretch" the
    // user reported. A previous attempt added RotatedBox, which only
    // rotated the already-stretched content (still stretched, just
    // sideways).
    //
    // FIX: Detect "ignored rotation" via the same heuristic (our app
    // records portrait, so coded dims > height = ignored rotation) and
    // pass the SWAPPED aspect (height/width = portrait) to AspectRatio.
    // No RotatedBox — the texture is already pre-rotated.
    final ignoredRotation = v.size.width > v.size.height && v.size.height > 0;
    final effectiveAspect = ignoredRotation
        ? v.size.height / v.size.width  // 1080/1920 = 0.5625 portrait
        : v.aspectRatio;

    Widget videoSurface = AspectRatio(
      aspectRatio: effectiveAspect,
      child: VideoPlayer(_ctrl!),
    );
    if (widget.pinchZoom && _zoomCtrl != null) {
      videoSurface = GestureDetector(
        onDoubleTap: _toggleVideoZoom,
        onTap: () => setState(() => _showControls = !_showControls),
        child: InteractiveViewer(
          transformationController: _zoomCtrl,
          minScale: 1.0,
          maxScale: 5.0,
          clipBehavior: Clip.hardEdge,
          child: videoSurface,
        ),
      );
    } else {
      videoSurface = GestureDetector(
        onTap: () => setState(() => _showControls = !_showControls),
        child: videoSurface,
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Stack(
        children: [
          Container(
            constraints: const BoxConstraints(
              minHeight: 220,
              maxHeight: 520,
            ),
            color: Colors.black,
            child: Center(child: videoSurface),
          ),
          // Gradient + play/pause — visual overlay only so pinch reaches video
          if (_showControls || !v.isPlaying)
            Positioned.fill(
              child: IgnorePointer(
                child: AnimatedOpacity(
                  opacity: _showControls || !v.isPlaying ? 1 : 0,
                  duration: const Duration(milliseconds: 250),
                  child: Container(
                    decoration: BoxDecoration(gradient: LinearGradient(
                      begin: Alignment.topCenter, end: Alignment.bottomCenter,
                      colors: [Colors.black.withAlpha(60), Colors.transparent, Colors.black.withAlpha(140)],
                    )),
                  ),
                ),
              ),
            ),
          if (_showControls || !v.isPlaying)
            Center(
              child: GestureDetector(
                onTap: () {
                  v.isPlaying ? _ctrl!.pause() : _ctrl!.play();
                },
                child: AnimatedOpacity(
                  opacity: _showControls || !v.isPlaying ? 1 : 0,
                  duration: const Duration(milliseconds: 250),
                  child: Container(
                    decoration: BoxDecoration(color: Colors.black54, shape: BoxShape.circle),
                    padding: const EdgeInsets.all(14),
                    child: Icon(v.isPlaying ? Icons.pause : Icons.play_arrow, color: Colors.white, size: 40),
                  ),
                ),
              ),
            ),
          if (widget.pinchZoom && _zoomCtrl != null)
            Positioned(
              top: 8,
              right: 8,
              child: AnimatedOpacity(
                opacity: _showControls ? 1 : 0,
                duration: const Duration(milliseconds: 250),
                child: IconButton(
                  icon: const Icon(Icons.zoom_out_map, color: Colors.white70, size: 20),
                  tooltip: 'Reset zoom',
                  onPressed: _resetVideoZoom,
                ),
              ),
            ),
            // Bottom: scrubber + time
            Positioned(
              left: 0, right: 0, bottom: 0,
              child: AnimatedOpacity(
                opacity: _showControls || !v.isPlaying ? 1 : 0,
                duration: const Duration(milliseconds: 250),
                child: Container(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
                  color: Colors.black.withAlpha(140),
                  child: Row(children: [
                    Text(_fmt(v.position), style: const TextStyle(color: Colors.white, fontSize: 11, fontFamily: 'monospace')),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        child: VideoProgressIndicator(
                          _ctrl!,
                          allowScrubbing: true,
                          colors: const VideoProgressColors(
                            playedColor: Color(0xFFFF7B00),
                            bufferedColor: Colors.white24,
                            backgroundColor: Colors.white10,
                          ),
                        ),
                      ),
                    ),
                    Text(_fmt(v.duration), style: const TextStyle(color: Colors.white, fontSize: 11, fontFamily: 'monospace')),
                  ]),
                ),
              ),
            ),
          ],
        ),
    );
  }
}

// ─── Fullscreen video player (for drafts) ─────────────────────────────

class _FullscreenVideoPlayer extends StatelessWidget {
  final String path;
  final String title;
  const _FullscreenVideoPlayer({required this.path, required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black87,
        elevation: 0,
        title: Text(title, style: const TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: _InlineVideoPlayer(path: path),
        ),
      ),
    );
  }
}

// ─── Order detail screen ───────────────────────────────────────────────

class _OrderDetailScreen extends StatefulWidget {
  final Map<String, dynamic> order;
  const _OrderDetailScreen({required this.order});
  @override State<_OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<_OrderDetailScreen> {
  late Map<String, dynamic> order;
  bool _uploading = false;
  final _storage = LocalStorageService();

  @override void initState() {
    super.initState();
    order = Map<String, dynamic>.from(widget.order);
  }

  CaptureMode? get _mode {
    final modeStr = order['mode'] as String?;
    if (modeStr == 'pk') return CaptureMode.pk;
    if (modeStr == 'rt') return CaptureMode.rt;
    return FileNamingService.modeFromFolder(order['orderId'] as String);
  }

  /// Parse the side tag (front/back/label/contents/serial) out of a photo
  /// filename of the form `{orderId}_{PK|RT}_{side}.jpg`.
  String _sideFromPath(String path) {
    return _photoSideFromOrderPath(path)?.name ?? '?';
  }

  Future<void> _reloadOrder() async {
    final all = await _storage.listOrders();
    final fresh = all.firstWhere(
      (o) => o['orderId'] == order['orderId'],
      orElse: () => order,
    );
    if (!mounted) return;
    setState(() => order = Map<String, dynamic>.from(fresh));
  }

  Future<void> _handlePhotoAction(String photoPath) async {
    final side = _photoSideFromOrderPath(photoPath);
    final sideLabel = side?.name ?? _sideFromPath(photoPath);
    final action = await _showPhotoActionSheet(
      context,
      sideLabel: sideLabel,
      showRetag: true,
    );
    if (!mounted || action == null) return;

    switch (action) {
      case _PhotoAction.retag:
        await _showRenameSheet(photoPath);
      case _PhotoAction.replace:
        await _replaceOrderPhoto(photoPath, side);
      case _PhotoAction.remove:
        await _removeOrderPhoto(photoPath, side);
    }
  }

  Future<void> _replaceOrderPhoto(String currentPath, PhotoSide? side) async {
    final mode = _mode;
    if (mode == null) return;
    final resolvedSide = side ?? _photoSideFromOrderPath(currentPath);
    if (resolvedSide == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Could not determine photo type'),
        backgroundColor: Colors.black87,
      ));
      return;
    }

    final picked = await ImagePicker().pickImage(
      source: ImageSource.camera,
      preferredCameraDevice: CameraDevice.rear,
      imageQuality: 92,
    );
    if (picked == null || !mounted) return;

    final folderKey = order['orderId'] as String;
    final bareOrderId = order['bareOrderId'] as String? ?? folderKey;
    final ok = await _storage.updateOrderPhoto(
      folderKey: folderKey,
      bareOrderId: bareOrderId,
      mode: mode,
      side: resolvedSide,
      newPhoto: picked,
    );
    if (!mounted) return;
    if (ok) {
      await _reloadOrder();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('${resolvedSide.name} photo replaced'),
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Replace failed'),
        backgroundColor: Colors.black87,
      ));
    }
  }

  Future<void> _removeOrderPhoto(String currentPath, PhotoSide? side) async {
    final mode = _mode;
    if (mode == null) return;
    final resolvedSide = side ?? _photoSideFromOrderPath(currentPath);
    if (resolvedSide == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Could not determine photo type'),
        backgroundColor: Colors.black87,
      ));
      return;
    }

    final ok = await _confirmRemovePhoto(context, resolvedSide.name);
    if (!ok || !mounted) return;

    final folderKey = order['orderId'] as String;
    final bareOrderId = order['bareOrderId'] as String? ?? folderKey;
    final removed = await _storage.updateOrderPhoto(
      folderKey: folderKey,
      bareOrderId: bareOrderId,
      mode: mode,
      side: resolvedSide,
      remove: true,
    );
    if (!mounted) return;
    if (removed) {
      await _reloadOrder();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('${resolvedSide.name} photo removed'),
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Remove failed'),
        backgroundColor: Colors.black87,
      ));
    }
  }

  /// Show a bottom sheet letting the user re-tag this photo to any of the
  /// 5 canonical sides. Handles the collision case (swap names) so we never
  /// overwrite or lose a photo.
  Future<void> _showRenameSheet(String currentPath) async {
    final currentSide = _sideFromPath(currentPath);
    const sides = ['label', 'contents', 'front', 'back', 'serial'];
    final newSide = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: const Color(0xFF161B22),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Container(width: 36, height: 4, decoration: BoxDecoration(color: const Color(0x33FFFFFF), borderRadius: BorderRadius.circular(2))),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 16, 20, 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('Re-tag this photo', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('If another photo already uses this tag, the two will be swapped.', style: TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
              ),
            ),
            ...sides.map((s) {
              final isCurrent = s == currentSide;
              return ListTile(
                leading: Icon(
                  isCurrent ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                  color: isCurrent ? const Color(0xFFFFA657) : Colors.white54,
                ),
                title: Text(s.toUpperCase(), style: TextStyle(color: isCurrent ? const Color(0xFFFFA657) : Colors.white, fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal)),
                trailing: isCurrent ? const Text('current', style: TextStyle(color: Color(0xFF8B949E), fontSize: 11)) : null,
                onTap: isCurrent ? null : () => Navigator.pop(ctx, s),
              );
            }),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
              child: GestureDetector(
                onTap: () => Navigator.pop(ctx),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  decoration: BoxDecoration(
                    color: Colors.white10,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Center(child: Text('Cancel', style: TextStyle(color: Colors.white70))),
                ),
              ),
            ),
          ],
        ),
      ),
    );
    if (newSide == null || newSide == currentSide) return;
    await _renamePhotoFile(currentPath, newSide);
  }

  Future<void> _syncMetaAfterPhotoPaths() async {
    final mode = _mode;
    if (mode == null) return;
    final folderKey = order['orderId'] as String;
    final bareOrderId = order['bareOrderId'] as String? ?? folderKey;
    final session = await _storage.sessionFromOrderFolder(
      folderKey: folderKey,
      bareOrderId: bareOrderId,
      mode: mode,
    );
    if (session != null) {
      await _storage.writeMetaJson(session);
    }
  }

  /// Rename the file from `_oldSide.jpg` → `_newSide.jpg`. Swaps with any
  /// existing photo that already has the target side. Then reloads the order.
  Future<void> _renamePhotoFile(String currentPath, String newSide) async {
    try {
      final file = File(currentPath);
      if (!await file.exists()) return;

      final dir = file.parent.path;
      final filename = currentPath.split(Platform.pathSeparator).last;
      final base = filename.replaceAll(RegExp(r'\.(jpg|jpeg|png)$', caseSensitive: false), '');
      final ext = filename.substring(base.length);
      final parts = base.split('_');
      parts[parts.length - 1] = newSide;
      final newFilename = '${parts.join('_')}$ext';
      final newPath = '$dir/$newFilename';

      if (newPath == currentPath) return;

      final targetFile = File(newPath);
      if (await targetFile.exists()) {
        // Collision — swap via temp
        final tempPath = '$newPath.swap';
        await targetFile.rename(tempPath);
        await file.rename(newPath);
        await File(tempPath).rename(currentPath);
      } else {
        await file.rename(newPath);
      }

      await _syncMetaAfterPhotoPaths();
      await _reloadOrder();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Re-tagged to $newSide'),
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    } catch (e) {
      debugPrint('Rename photo failed: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Rename failed: $e'),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.black87,
        ));
      }
    }
  }

  Future<void> _retryUpload() async {
    setState(() => _uploading = true);
    final result = await UploadService.uploadFromFolder(
      orderId: order['orderId'] as String,
      folderPath: order['folderPath'] as String,
    );
    if (!mounted) return;
    setState(() {
      _uploading = false;
      if (result.status == UploadStatus.success) {
        order['isUploaded'] = true;
        order['uploadedAt'] = DateTime.now().toIso8601String();
      }
    });
    final msg = switch (result.status) {
      UploadStatus.success => 'Uploaded — video + ${result.photosUploaded} photo${result.photosUploaded == 1 ? '' : 's'}',
      UploadStatus.offline => 'Backend offline. Try again when on same WiFi as PC.',
      UploadStatus.failed  => 'Upload failed: ${result.error ?? ''}',
    };
    final icon = result.status == UploadStatus.success ? Icons.cloud_done : Icons.error_outline;
    final color = result.status == UploadStatus.success ? const Color(0xFF3FB950) : const Color(0xFFFF7B72);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(child: Text(msg, maxLines: 2, overflow: TextOverflow.ellipsis)),
      ]),
      duration: const Duration(seconds: 3),
      backgroundColor: Colors.black87,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final orderId = order['orderId'] as String;
    final videoPath = order['videoPath'] as String?;
    final photoPaths = (order['photoPaths'] as List).cast<String>();
    final sizeMb = ((order['sizeBytes'] as int) / (1024 * 1024)).toStringAsFixed(1);
    final folderPath = order['folderPath'] as String;
    final isUploaded = order['isUploaded'] as bool? ?? false;

    return RfGlassScaffold(
      appBar: RfGlassAppBar(
        titleWidget: Text(orderId, style: const TextStyle(color: Colors.white, fontSize: 14, fontFamily: 'monospace')),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Video player
          if (videoPath != null) ...[
            const _SectionLabel('Video'),
            const SizedBox(height: 8),
            _InlineVideoPlayer(path: videoPath),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                icon: const Icon(Icons.copy, size: 14, color: Colors.white54),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: videoPath));
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Video path copied'),
                    duration: Duration(seconds: 2),
                    backgroundColor: Colors.black87,
                  ));
                },
                label: Text(videoPath.split(Platform.pathSeparator).last,
                    style: const TextStyle(color: Colors.white54, fontSize: 11, fontFamily: 'monospace'),
                    overflow: TextOverflow.ellipsis),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Photos
          if (photoPaths.isNotEmpty) ...[
            const _SectionLabel('Photos'),
            const SizedBox(height: 4),
            const Text(
              'Tap to view · Long-press to edit',
              style: TextStyle(color: Color(0xFF8B949E), fontSize: 11),
            ),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              children: photoPaths.map((p) {
                final side = _sideFromPath(p);
                return GestureDetector(
                  onTap: () => _openPhoto(context, p, photoPaths),
                  onLongPress: () => _handlePhotoAction(p),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Image.file(File(p), fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(color: Colors.black, child: const Icon(Icons.broken_image, color: Colors.white24))),
                        ),
                      ),
                      // Side-tag chip — shows current label, tap-to-retag hint
                      Positioned(
                        left: 6, bottom: 6,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.black.withAlpha(180),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            const Icon(Icons.label_outline, color: Color(0xFFFFA657), size: 11),
                            const SizedBox(width: 4),
                            Text(
                              side.toUpperCase(),
                              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 0.5),
                            ),
                          ]),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
          ],

          // Folder info
          const _SectionLabel('Folder'),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: RfGlass.decoration(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(folderPath, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, fontFamily: 'monospace')),
                const SizedBox(height: 6),
                Text('Total: $sizeMb MB', style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                const SizedBox(height: 8),
                TextButton.icon(
                  icon: const Icon(Icons.copy, size: 14, color: Colors.white54),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: folderPath));
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text('Folder path copied'),
                      duration: Duration(seconds: 2),
                      backgroundColor: Colors.black87,
                    ));
                  },
                  label: const Text('Copy folder path', style: TextStyle(color: Colors.white54, fontSize: 12)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Backend upload status + retry
          Container(
            padding: const EdgeInsets.all(14),
            decoration: RfGlass.decoration(
              borderColor: isUploaded ? const Color(0x553FB950) : const Color(0x55FFA657),
            ),
            child: Row(
              children: [
                Icon(
                  isUploaded ? Icons.cloud_done_rounded : Icons.cloud_off_rounded,
                  color: isUploaded ? const Color(0xFF3FB950) : const Color(0xFFFFA657),
                  size: 22,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isUploaded ? 'Uploaded to backend' : 'Pending upload',
                        style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        isUploaded
                            ? 'Server copy exists. Local files kept as backup.'
                            : 'Backend was offline or upload failed. Tap retry to upload now.',
                        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11),
                      ),
                    ],
                  ),
                ),
                if (!isUploaded)
                  _uploading
                      ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFFFA657)))
                      : TextButton(
                          onPressed: _retryUpload,
                          child: const Text('Upload', style: TextStyle(color: Color(0xFFFFA657), fontWeight: FontWeight.w600)),
                        ),
              ],
            ),
          ),

          const SizedBox(height: 32),

          // Delete
          OutlinedButton.icon(
            icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
            label: const Text('Delete this order', style: TextStyle(color: Colors.redAccent, fontSize: 14)),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              side: const BorderSide(color: Colors.redAccent),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () async {
              final ok = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  backgroundColor: const Color(0xFF161B22),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  title: const Text('Delete order?', style: TextStyle(color: Colors.white)),
                  content: Text(
                    'Permanently delete order $orderId\n(video + ${photoPaths.length} photos)?\n\nThis cannot be undone.',
                    style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13),
                  ),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel', style: TextStyle(color: Colors.white54))),
                    TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
                  ],
                ),
              );
              if (ok == true && context.mounted) {
                final storage = LocalStorageService();
                final deleted = await storage.deleteOrder(orderId);
                if (deleted && context.mounted) {
                  await SyncManager.refreshStatus();
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Order deleted'),
                    duration: Duration(seconds: 2),
                    backgroundColor: Colors.black87,
                  ));
                }
              }
            },
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  void _openPhoto(BuildContext context, String path, List<String> all) {
    showDialog(
      context: context,
      barrierColor: Colors.black,
      builder: (_) => _PhotoViewer(initialPath: path, allPaths: all),
    );
  }
}

// ─── Photo viewer (fullscreen) ─────────────────────────────────────────

class _PhotoViewer extends StatefulWidget {
  final String initialPath;
  final List<String> allPaths;
  const _PhotoViewer({required this.initialPath, required this.allPaths});

  @override
  State<_PhotoViewer> createState() => _PhotoViewerState();
}

class _PhotoViewerState extends State<_PhotoViewer> {
  late PageController _ctrl;
  late int _current;
  late List<TransformationController> _zoomCtrls;
  bool _zoomed = false;

  @override
  void initState() {
    super.initState();
    _current = widget.allPaths.indexOf(widget.initialPath).clamp(0, widget.allPaths.length - 1);
    _ctrl = PageController(initialPage: _current);
    _zoomCtrls = List.generate(widget.allPaths.length, (_) => TransformationController());
    _zoomCtrls[_current].addListener(_onZoomChanged);
  }

  void _onZoomChanged() {
    final scale = _zoomCtrls[_current].value.getMaxScaleOnAxis();
    final zoomed = scale > 1.01;
    if (zoomed != _zoomed) setState(() => _zoomed = zoomed);
  }

  void _attachZoomListener(int index) {
    for (var i = 0; i < _zoomCtrls.length; i++) {
      _zoomCtrls[i].removeListener(_onZoomChanged);
    }
    _zoomCtrls[index].addListener(_onZoomChanged);
    _onZoomChanged();
  }

  void _resetZoom(int index) {
    _zoomCtrls[index].value = Matrix4.identity();
  }

  void _toggleZoom(int index) {
    final ctrl = _zoomCtrls[index];
    final scale = ctrl.value.getMaxScaleOnAxis();
    if (scale > 1.01) {
      ctrl.value = Matrix4.identity();
    } else {
      ctrl.value = Matrix4.identity()..scaleByDouble(2.5);
    }
  }

  @override
  void dispose() {
    for (final c in _zoomCtrls) {
      c.removeListener(_onZoomChanged);
      c.dispose();
    }
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          PageView.builder(
            controller: _ctrl,
            itemCount: widget.allPaths.length,
            physics: _zoomed ? const NeverScrollableScrollPhysics() : const PageScrollPhysics(),
            onPageChanged: (i) {
              _resetZoom(_current);
              setState(() => _current = i);
              _attachZoomListener(i);
            },
            itemBuilder: (_, i) => GestureDetector(
              onDoubleTap: () => _toggleZoom(i),
              child: InteractiveViewer(
                transformationController: _zoomCtrls[i],
                minScale: 1.0,
                maxScale: 5.0,
                clipBehavior: Clip.hardEdge,
                child: Center(
                  child: Image.file(
                    File(widget.allPaths[i]),
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(Icons.broken_image, color: Colors.white24, size: 64),
                  ),
                ),
              ),
            ),
          ),
          // Top bar
          Positioned(
            top: 0, left: 0, right: 0,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed: () => Navigator.pop(context),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(10)),
                      child: Text(
                        '${_current + 1} / ${widget.allPaths.length}',
                        style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ),
                    const SizedBox(width: 48),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2),
    );
  }
}

// ─── Draft detail screen ─────────────────────────────────────────────
//
// Shows a draft session (1 video + 0-N photos) in the same layout
// _OrderDetailScreen uses for completed orders: inline video player at
// the top, then a photo grid. The only thing missing vs orders is the
// Order ID + Upload state (drafts have neither). Lets the user review
// what they captured before deciding to delete or to re-enter via the
// capture flow.

class _DraftDetailScreen extends StatefulWidget {
  final Map<String, dynamic> session;
  const _DraftDetailScreen({required this.session});
  @override
  State<_DraftDetailScreen> createState() => _DraftDetailScreenState();
}

class _DraftDetailScreenState extends State<_DraftDetailScreen> {
  late Map<String, dynamic> session;
  bool _saving = false;
  final _storage = LocalStorageService();

  @override
  void initState() {
    super.initState();
    session = Map<String, dynamic>.from(widget.session);
  }

  void _openPhoto(BuildContext ctx, String path, List<String> all) {
    showDialog(
      context: ctx,
      barrierColor: Colors.black,
      builder: (_) => _PhotoViewer(initialPath: path, allPaths: all),
    );
  }

  Future<void> _handleDraftPhotoAction(String photoPath) async {
    final fileName = photoPath.split(Platform.pathSeparator).last;
    final side = DraftSaveService.photoSideFromDraftName(fileName);
    final sideLabel = side != null ? DraftSaveService.labelForSide(side) : 'photo';
    final action = await _showPhotoActionSheet(context, sideLabel: sideLabel);
    if (!mounted || action == null) return;

    switch (action) {
      case _PhotoAction.replace:
        await _replaceDraftPhoto(photoPath, side);
      case _PhotoAction.remove:
        await _removeDraftPhoto(photoPath);
      case _PhotoAction.retag:
        break;
    }
  }

  Future<void> _replaceDraftPhoto(String oldPath, PhotoSide? side) async {
    final modeStr = session['mode'] as String;
    final mode = modeStr == 'RT' ? CaptureMode.rt : CaptureMode.pk;
    if (side == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Could not determine photo type — remove and recapture instead'),
        backgroundColor: Colors.black87,
      ));
      return;
    }

    final newPath = await DraftSaveService.captureMissingPhoto(mode, side, _storage);
    if (newPath == null || !mounted) return;

    await _storage.deleteDraft(oldPath);
    setState(() {
      final photos = session['photoPaths'] as List<String>;
      final drafts = session['draftPaths'] as List<String>;
      final pIdx = photos.indexOf(oldPath);
      if (pIdx >= 0) photos[pIdx] = newPath;
      final dIdx = drafts.indexOf(oldPath);
      if (dIdx >= 0) drafts[dIdx] = newPath;
    });
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('${DraftSaveService.labelForSide(side)} replaced'),
      duration: const Duration(seconds: 2),
      backgroundColor: Colors.black87,
    ));
  }

  Future<void> _removeDraftPhoto(String path) async {
    final fileName = path.split(Platform.pathSeparator).last;
    final side = DraftSaveService.photoSideFromDraftName(fileName);
    final label = side != null ? DraftSaveService.labelForSide(side) : 'this';
    final ok = await _confirmRemovePhoto(context, label);
    if (!ok || !mounted) return;

    if (await _storage.deleteDraft(path)) {
      setState(() {
        (session['photoPaths'] as List<String>).remove(path);
        (session['draftPaths'] as List<String>).remove(path);
        session['sizeBytes'] = _sumDraftBytes(session['draftPaths'] as List<String>);
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Photo removed'),
        duration: Duration(seconds: 2),
        backgroundColor: Colors.black87,
      ));
    }
  }

  int _sumDraftBytes(List<String> paths) {
    var total = 0;
    for (final p in paths) {
      try {
        total += File(p).lengthSync();
      } catch (_) {}
    }
    return total;
  }

  Future<void> _finishSave() async {
    if (_saving) return;
    final modeStr = session['mode'] as String;
    final mode = modeStr == 'RT' ? CaptureMode.rt : CaptureMode.pk;
    final videoPath = session['videoPath'] as String?;
    if (videoPath == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('This draft has no video to save'),
        backgroundColor: Colors.black87,
      ));
      return;
    }

    QCVerdict? verdict;
    if (mode == CaptureMode.rt) {
      verdict = await showModalBottomSheet<QCVerdict>(
        context: context,
        isScrollControlled: true,
        backgroundColor: Colors.transparent,
        builder: (_) => const VerdictBottomSheet(),
      );
      if (verdict == null || !mounted) return;
    }

    final barcode = await Navigator.of(context).push<Map<String, String?>>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => BarcodeSavePopup(mode: mode),
      ),
    );
    if (barcode == null || barcode['orderId'] == null || !mounted) return;

    var photos = DraftSaveService.mapDraftPhotos(
      (session['photoPaths'] as List).cast<String>(),
    );

    var missing = DraftSaveService.missingRequiredPhotos(
      mode,
      photos: photos,
      verdict: verdict,
    );

    while (missing.isNotEmpty && mounted) {
      final side = missing.first;
      final capture = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF161B22),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Add photo', style: TextStyle(color: Colors.white)),
          content: Text(
            'Capture ${DraftSaveService.labelForSide(side)} for this ${modeStr} shipment.',
            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Capture')),
          ],
        ),
      );
      if (capture != true || !mounted) return;
      final path = await DraftSaveService.captureMissingPhoto(mode, side, _storage);
      if (path == null) return;
      photos = {...photos, side: path};
      (session['photoPaths'] as List<String>).add(path);
      (session['draftPaths'] as List<String>).add(path);
      missing = DraftSaveService.missingRequiredPhotos(
        mode,
        photos: photos,
        verdict: verdict,
      );
    }

    setState(() => _saving = true);
    try {
      await DraftSaveService.promoteDraftSession(
        orderId: barcode['orderId']!,
        awb: barcode['awb'],
        mode: mode,
        videoPath: videoPath,
        photosBySide: photos,
        verdict: verdict,
        storage: _storage,
      );
      if (!mounted) return;
      Navigator.pop(context, true);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Saved order ${barcode['orderId']}'),
        backgroundColor: Colors.black87,
      ));
      // ignore: unawaited_futures
      SyncManager.syncNow();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Save failed: $e'),
        backgroundColor: Colors.black87,
      ));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _deleteAll() async {
    final paths = (session['draftPaths'] as List).cast<String>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete this draft?', style: TextStyle(color: Colors.white)),
        content: Text(
          'Permanently delete all ${paths.length} file${paths.length == 1 ? '' : 's'} in this draft session?\n\nThis cannot be undone.',
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel', style: TextStyle(color: Colors.white54))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (ok != true) return;
    int deleted = 0;
    final storage = LocalStorageService();
    for (final p in paths) {
      if (await storage.deleteDraft(p)) deleted++;
    }
    if (!mounted) return;
    Navigator.pop(context);  // back to list
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('Deleted $deleted file${deleted == 1 ? '' : 's'}'),
      duration: const Duration(seconds: 2),
      backgroundColor: Colors.black87,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final mode = session['mode'] as String;
    final videoPath = session['videoPath'] as String?;
    final photoPaths = (session['photoPaths'] as List).cast<String>();
    final draftPaths = (session['draftPaths'] as List).cast<String>();
    final sizeMb = ((session['sizeBytes'] as int) / (1024 * 1024)).toStringAsFixed(1);
    final modified = DateTime.parse(session['modifiedAt'] as String);
    final ts = '${modified.day}/${modified.month}/${modified.year} '
               '${modified.hour.toString().padLeft(2, '0')}:${modified.minute.toString().padLeft(2, '0')}';
    final hasRecovered = session['hasRecovered'] as bool? ?? false;
    final accent = mode == 'PK' ? RfColors.pkAccent : RfColors.rtAccent;

    return RfGlassScaffold(
      appBar: RfGlassAppBar(
        titleWidget: Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(6)),
            child: Text(
              '$mode DRAFT',
              style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
            ),
          ),
          const SizedBox(width: 10),
          Text(ts, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ]),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
            onPressed: _deleteAll,
            tooltip: 'Delete all',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Status banner ─────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0x33FFA657),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFFFA657).withAlpha(120)),
            ),
            child: Row(children: [
              const Icon(Icons.warning_amber_rounded, color: Color(0xFFFFA657), size: 18),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Draft — no Order ID assigned yet. Will not auto-upload until promoted to an order.',
                  style: TextStyle(color: Color(0xFFFFA657), fontSize: 12, fontWeight: FontWeight.w500),
                ),
              ),
            ]),
          ),
          if (hasRecovered) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(color: Colors.amber.withAlpha(40), borderRadius: BorderRadius.circular(8)),
              child: Row(children: [
                const Icon(Icons.restore_rounded, color: Colors.amber, size: 14),
                const SizedBox(width: 6),
                const Text('Recovered from crash', style: TextStyle(color: Colors.amber, fontSize: 11, fontWeight: FontWeight.w600)),
              ]),
            ),
          ],
          const SizedBox(height: 16),

          RfButton.primary(
            label: _saving ? 'Saving...' : 'Finish save',
            icon: Icons.save_alt_rounded,
            onPressed: (_saving || videoPath == null) ? null : _finishSave,
          ),
          const SizedBox(height: 16),

          // ── Video player ──────────────────────────────────────────────
          if (videoPath != null) ...[
            const _SectionLabel('Video'),
            const SizedBox(height: 8),
            _InlineVideoPlayer(path: videoPath),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                icon: const Icon(Icons.copy, size: 14, color: Colors.white54),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: videoPath));
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Video path copied'),
                    duration: Duration(seconds: 2),
                    backgroundColor: Colors.black87,
                  ));
                },
                label: Text(videoPath.split(Platform.pathSeparator).last,
                    style: const TextStyle(color: Colors.white54, fontSize: 11, fontFamily: 'monospace'),
                    overflow: TextOverflow.ellipsis),
              ),
            ),
            const SizedBox(height: 16),
          ] else ...[
            const _SectionLabel('Video'),
            const SizedBox(height: 8),
            Container(
              height: 120,
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white12),
              ),
              child: const Center(
                child: Text('No video in this session', style: TextStyle(color: Colors.white38, fontSize: 13)),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // ── Photos grid ───────────────────────────────────────────────
          if (photoPaths.isNotEmpty) ...[
            const _SectionLabel('Photos'),
            const SizedBox(height: 4),
            const Text(
              'Tap to view · Long-press to edit',
              style: TextStyle(color: Color(0xFF8B949E), fontSize: 11),
            ),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              children: photoPaths.map((p) {
                final fileName = p.split(Platform.pathSeparator).last;
                final side = DraftSaveService.photoSideFromDraftName(fileName);
                return GestureDetector(
                  onTap: () => _openPhoto(context, p, photoPaths),
                  onLongPress: () => _handleDraftPhotoAction(p),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Image.file(File(p), fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(color: Colors.black, child: const Icon(Icons.broken_image, color: Colors.white24))),
                        ),
                      ),
                      if (side != null)
                        Positioned(
                          left: 6,
                          bottom: 6,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.black.withAlpha(180),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              side.name.toUpperCase(),
                              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 0.5),
                            ),
                          ),
                        ),
                    ],
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
          ],

          // ── Files list (debugging / inspection) ───────────────────────
          const _SectionLabel('Files in this session'),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: RfGlass.decoration(radius: RfRadius.button),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final p in draftPaths) Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    p.split(Platform.pathSeparator).last,
                    style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10, fontFamily: 'monospace'),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$sizeMb MB total · ${draftPaths.length} file${draftPaths.length == 1 ? '' : 's'}',
                  style: const TextStyle(color: Color(0xFF6E7681), fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
