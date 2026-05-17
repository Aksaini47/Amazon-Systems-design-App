import 'dart:async';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import '../theme/rf_colors.dart';
import 'record_screen.dart';
import 'scan_screen.dart';
import 'settings_screen.dart';
import 'fba_screen.dart';
import 'history_screen.dart';
import 'live_capture_screen.dart';
import 'local_gallery_screen.dart';
import '../models/capture_session.dart';
import '../services/api_service.dart';
import '../services/discovery_service.dart';
import '../services/local_storage_service.dart';
import '../services/permission_service.dart';
import '../services/sync_manager.dart';
import '../services/sync_queue_service.dart';
import '../services/update_service.dart';
import '../utils/volume_button_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // null = checking, true = connected, false = not connected
  bool? _connected;
  bool _discovering = false;

  @override
  void initState() {
    super.initState();
    _checkConnection();
    _recoverOrphanVideos();  // Recover any videos lost in a crash mid-recording
    _maybeShowChangelog();   // Show "what's new" banner if patch was applied
    // Start the persistent upload queue retry loop (every 2 min) + try
    // immediately on launch. Ensures any orders saved offline on previous
    // sessions get pushed to backend as soon as it's reachable.
    SyncManager.startPeriodic();
    VolumeButtonService().registerListener('home_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (event == 1) _goToLiveCapture(context, CaptureMode.pk);
      if (event == 2) _goToLiveCapture(context, CaptureMode.rt);
    });
  }

  /// If a Shorebird patch was applied since last launch, show its
  /// changelog once via SnackBar. Idempotent — UpdateService persists
  /// the "last seen" patch number so the banner never re-fires for the
  /// same patch.
  Future<void> _maybeShowChangelog() async {
    // Tiny delay so the banner doesn't fire before the home UI is painted —
    // the user should see the app first, then notice the update notice.
    await Future.delayed(const Duration(milliseconds: 800));
    final notes = await UpdateService.consumePendingChangelog();
    if (notes == null || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      duration: const Duration(seconds: 8),
      backgroundColor: const Color(0xFF161B22),
      behavior: SnackBarBehavior.floating,
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      content: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.system_update_outlined, color: Color(0xFF3FB950), size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'App updated',
                  style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(
                  notes,
                  style: const TextStyle(color: Color(0xFFE6EDF3), fontSize: 12, height: 1.35),
                  maxLines: 6,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    ));
  }

  Future<void> _recoverOrphanVideos() async {
    try {
      final recovered = await LocalStorageService().recoverOrphanVideos();
      if (recovered > 0 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Row(children: [
            const Icon(Icons.restore, color: Colors.amber, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text('Recovered $recovered orphan video${recovered == 1 ? '' : 's'} from a previous session. Find them in Gallery → Drafts.')),
          ]),
          duration: const Duration(seconds: 5),
          backgroundColor: Colors.black87,
        ));
      }
    } catch (e) {
      debugPrint('Orphan recovery failed (non-fatal): $e');
    }
  }

  @override
  void dispose() {
    VolumeButtonService().unregisterListener('home_screen');
    super.dispose();
  }

  Future<void> _checkConnection() async {
    setState(() { _connected = null; });
    final ok = await ApiService.ping();
    if (!mounted) return;
    if (ok) {
      setState(() { _connected = true; });
    } else {
      // Not reachable — try mDNS auto-discovery silently
      setState(() { _discovering = true; });
      final url = await DiscoveryService.discover();
      if (!mounted) return;
      if (url != null) {
        await ApiService.setBaseUrl(url);
        final confirmed = await ApiService.ping();
        if (mounted) setState(() { _connected = confirmed; _discovering = false; });
      } else {
        if (mounted) setState(() { _connected = false; _discovering = false; });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: RfColors.bg,
      appBar: AppBar(
        backgroundColor: RfColors.card,  // dark header, matches Settings/Gallery
        elevation: 0,
        title: const Text('RepairFully', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.photo_library_outlined),
            tooltip: 'Local Gallery',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const LocalGalleryScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.cloud_outlined),
            tooltip: 'Backend History',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const HistoryScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () async {
              await Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen()));
              _checkConnection(); // recheck after returning from settings
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          // Navy grid pattern background — faded 20% opacity, subtle texture
          Positioned.fill(
            child: CustomPaint(painter: _GridPatternPainter(color: RfColors.navy, opacity: 0.20)),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ConnectionBanner(connected: _connected, discovering: _discovering, onRetry: _checkConnection),
              const _SyncBanner(),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                  const SizedBox(height: 16),
                  const Text(
                    'Record a video',
                    style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Record first, then scan Order ID at the end.',
                    style: TextStyle(color: RfColors.textSecondary, fontSize: 14),
                  ),
                  const SizedBox(height: 32),
                  _ActionCard(
                    icon: Icons.inventory_2_outlined,
                    title: 'PK Mode',
                    subtitle: 'Record dispatch — front/back photos + video',
                    color: RfColors.pkAccent,
                    onTap: () => _goToLiveCapture(context, CaptureMode.pk),
                  ),
                  const SizedBox(height: 16),
                  _ActionCard(
                    icon: Icons.open_in_new_rounded,
                    title: 'RT Mode',
                    subtitle: 'Record return — label/front/back photos + video',
                    color: RfColors.rtAccent,
                    onTap: () => _goToLiveCapture(context, CaptureMode.rt),
                  ),
                  const SizedBox(height: 16),
                  _ActionCard(
                    icon: Icons.warehouse_outlined,
                    title: 'FBA Packing',
                    subtitle: 'Record packing for Amazon warehouse',
                    color: RfColors.fbaAccent,
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const FbaScreen())),
                  ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _goToLiveCapture(BuildContext context, CaptureMode mode) async {
    // Request permissions first
    final cameraOk = await PermissionService.isCameraGranted();
    if (!cameraOk) {
      final results = await PermissionService.requestCameraPermissions();
      if (!results[Permission.camera]!.isGranted) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Camera permission required'),
            action: SnackBarAction(label: 'Settings', onPressed: PermissionService.openSettings),
          ),
        );
        return;
      }
    }

    // Request storage/media permissions for saving files
    final storageOk = await PermissionService.isStorageGranted();
    if (!storageOk) {
      await PermissionService.requestStoragePermission();
    }

    // LiveCaptureScreen opens directly — video starts immediately, barcode scanned at end
    await Future.delayed(const Duration(milliseconds: 300));
    if (!mounted) return;
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => LiveCaptureScreen(mode: mode),
    ));
  }
}

class _ConnectionBanner extends StatelessWidget {
  final bool? connected;
  final bool discovering;
  final VoidCallback onRetry;

  const _ConnectionBanner({required this.connected, required this.discovering, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    if (connected == true) return const SizedBox.shrink(); // no banner when connected

    if (connected == null || discovering) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        color: RfColors.navy,
        child: Row(
          children: [
            const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: RfColors.textSecondary)),
            const SizedBox(width: 10),
            Text(
              discovering ? 'Looking for backend on WiFi...' : 'Checking connection...',
              style: const TextStyle(color: RfColors.textSecondary, fontSize: 13),
            ),
          ],
        ),
      );
    }

    // connected == false
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: RfColors.errorBg,
      child: Row(
        children: [
          const Icon(Icons.wifi_off_rounded, color: RfColors.error, size: 16),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'Backend not found. Start the server on your PC.',
              style: TextStyle(color: RfColors.error, fontSize: 13),
            ),
          ),
          GestureDetector(
            onTap: onRetry,
            child: const Text('Retry', style: TextStyle(color: RfColors.info, fontSize: 13, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

/// Pending-upload banner — visible only when the queue is non-empty.
/// Live updates via SyncManager.statusStream.
class _SyncBanner extends StatefulWidget {
  const _SyncBanner();

  @override
  State<_SyncBanner> createState() => _SyncBannerState();
}

class _SyncBannerState extends State<_SyncBanner> {
  SyncStatus _status = const SyncStatus(pendingCount: 0, syncing: false);
  Duration? _oldestAge;
  // CRITICAL FIX (Mahika audit 2026-05-17): the previous code called
  // `_stream.listen(...)` without storing the returned StreamSubscription,
  // so the listener was never cancelled. That caused (1) a real memory
  // leak — the banner kept holding the State after navigation away, and
  // (2) "setState() called after dispose()" exceptions in logcat when
  // the SyncManager emitted events post-dispose.
  StreamSubscription<SyncStatus>? _statusSub;

  @override
  void initState() {
    super.initState();
    _statusSub = SyncManager.statusStream.listen((s) {
      if (!mounted) return;
      setState(() => _status = s);
      _refreshOldestAge();
    });
    SyncManager.currentStatus().then((s) {
      if (mounted) setState(() => _status = s);
    });
    _refreshOldestAge();
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    super.dispose();
  }

  Future<void> _refreshOldestAge() async {
    final age = await SyncQueueService.oldestAge();
    if (mounted) setState(() => _oldestAge = age);
  }

  String _ageText(Duration d) {
    if (d.inDays >= 1) return '${d.inDays}d ago';
    if (d.inHours >= 1) return '${d.inHours}h ago';
    if (d.inMinutes >= 1) return '${d.inMinutes}m ago';
    return 'just now';
  }

  @override
  Widget build(BuildContext context) {
    if (_status.pendingCount == 0) return const SizedBox.shrink();
    final n = _status.pendingCount;
    final oldest = _oldestAge;
    final urgent = oldest != null && oldest.inHours >= 24;
    final bg = urgent ? const Color(0x40FF7B72) : const Color(0x40FFA657);
    final fg = urgent ? const Color(0xFFFF7B72) : const Color(0xFFFFA657);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: bg,
      child: Row(
        children: [
          Icon(urgent ? Icons.warning_amber_rounded : Icons.cloud_upload_outlined, color: fg, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '$n order${n == 1 ? '' : 's'} pending upload',
                  style: TextStyle(color: fg, fontSize: 13, fontWeight: FontWeight.w600),
                ),
                if (oldest != null)
                  Text(
                    'Oldest queued ${_ageText(oldest)}${urgent ? ' — agent will miss this' : ''}',
                    style: TextStyle(color: fg.withOpacity(0.85), fontSize: 11),
                  ),
              ],
            ),
          ),
          _status.syncing
              ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: fg))
              : GestureDetector(
                  onTap: SyncManager.syncNow,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(color: fg.withOpacity(0.25), borderRadius: BorderRadius.circular(8)),
                    child: Text('Sync now', style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w700)),
                  ),
                ),
        ],
      ),
    );
  }
}

/// Faded navy grid lines for subtle background texture on the home screen.
class _GridPatternPainter extends CustomPainter {
  final Color color;
  final double opacity;
  final double spacing;
  final double stroke;

  _GridPatternPainter({
    required this.color,
    this.opacity = 0.20,
    this.spacing = 32,
    this.stroke = 0.6,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withOpacity(opacity)
      ..strokeWidth = stroke
      ..style = PaintingStyle.stroke;

    for (double x = 0; x <= size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _GridPatternPainter old) =>
      old.color != color || old.opacity != opacity || old.spacing != spacing;
}

class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _ActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: RfColors.card,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: RfColors.border),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(subtitle, style: const TextStyle(color: RfColors.textSecondary, fontSize: 13)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: RfColors.textSecondary),
          ],
        ),
      ),
    );
  }
}
