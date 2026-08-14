import 'dart:async';
import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';
import '../config/app_config.dart';
import 'settings_screen.dart';
import 'live_capture_screen.dart';
import 'local_gallery_screen.dart';
import 'tour_dialog.dart';
import '../models/capture_session.dart';
import '../services/local_storage_service.dart';
import '../services/permission_service.dart';
import '../services/update_service.dart';
import '../utils/volume_button_service.dart';

const _kHasSeenTourKey = 'has_seen_tour_v1';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  PackageInfo? _appInfo;
  int? _currentPatch;
  bool _shorebirdAvailable = false;

  @override
  void initState() {
    super.initState();
    _loadAppInfo();
    _recoverOrphanVideos();
    _maybeShowChangelog();
    _maybeShowTour();
    VolumeButtonService().registerListener('home_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (event == 1) _goToLiveCapture(context, CaptureMode.pk);
      if (event == 2) _goToLiveCapture(context, CaptureMode.rt);
    });
  }

  Future<void> _loadAppInfo() async {
    try {
      _appInfo = await PackageInfo.fromPlatform();
    } catch (_) {}
    _shorebirdAvailable = await UpdateService.isAvailable;
    _currentPatch = await UpdateService.currentPatchNumber();
    if (mounted) setState(() {});
  }

  Future<void> _maybeShowChangelog() async {
    await Future<void>.delayed(const Duration(milliseconds: 800));
    final notes = await UpdateService.consumePendingChangelog();
    if (notes == null) {
      await _maybeShowUpdatePending();
      return;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      duration: const Duration(seconds: 8),
      backgroundColor: RfColors.card,
      behavior: SnackBarBehavior.floating,
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      content: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.system_update_outlined, color: RfColors.successLight, size: 22),
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
                  style: const TextStyle(color: RfColors.textPrimary, fontSize: 12, height: 1.35),
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

  /// Shorebird patches apply only on the *next cold process start* — a
  /// plain task-switch (home button, recents) often leaves the process
  /// alive, so a silently-downloaded patch can sit staged indefinitely
  /// with zero on-screen sign it's waiting. This nags on every Home mount
  /// until the patch actually goes active (root cause of "OTA not
  /// landing" reports 2026-08-14 — the download was fine, nothing ever
  /// told the user a real restart was needed).
  Future<void> _maybeShowUpdatePending() async {
    if (!await UpdateService.isAvailable) return;
    final current = await UpdateService.currentPatchNumber();
    final next = await UpdateService.nextPatchNumber();
    if (next == null || next == current || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      duration: const Duration(seconds: 7),
      backgroundColor: RfColors.card,
      behavior: SnackBarBehavior.floating,
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      content: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.restart_alt_rounded, color: RfColors.amber, size: 22),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Update downloaded but not applied yet. Swipe this app away from '
              'Recents (fully close it) and reopen — switching apps isn\'t enough.',
              style: TextStyle(color: Colors.white, fontSize: 12, height: 1.35),
            ),
          ),
        ],
      ),
    ));
  }

  /// Auto-popup is demo-flavor only — prod (Sir's own phone) never needs
  /// it. Manual replay (Settings, AppBar "?" icon) works on both flavors so
  /// Sir can preview exactly what a prospect sees without installing the
  /// demo build separately.
  Future<void> _maybeShowTour() async {
    if (!AppConfig.isDemo) return;
    await Future<void>.delayed(const Duration(milliseconds: 800));
    if (!mounted) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (prefs.getBool(_kHasSeenTourKey) == true) return;
      await prefs.setBool(_kHasSeenTourKey, true);
      if (!mounted) return;
      await TourDialog.show(context);
    } catch (e) {
      debugPrint('_maybeShowTour failed (non-fatal): $e');
    }
  }

  Future<void> _recoverOrphanVideos() async {
    try {
      final storage = LocalStorageService();
      await storage.sweepJunkDrafts();
      final recovered = await storage.recoverOrphanVideos();
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

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      showGrid: true,
      appBar: RfGlassAppBar(
        titleWidget: _buildTitle(),
        actions: [
          RfIconButton(
            icon: Icons.photo_library_outlined,
            tooltip: 'Local Gallery',
            size: 40,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute<void>(builder: (_) => const LocalGalleryScreen()),
            ),
          ),
          const SizedBox(width: 8),
          RfIconButton(
            icon: Icons.settings_outlined,
            tooltip: 'Settings',
            size: 40,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
          ),
          const SizedBox(width: 8),
          RfIconButton(
            icon: Icons.help_outline_rounded,
            tooltip: 'How to use RF Logger',
            size: 40,
            onPressed: () => TourDialog.show(context),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SingleChildScrollView(
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
          ],
        ),
      ),
    );
  }

  /// App name + version, with the active Shorebird patch number appended
  /// once one exists — mirrors the same source (`PackageInfo`,
  /// `UpdateService`) Settings' About card reads, so the two never disagree.
  Widget _buildTitle() {
    final name = _appInfo?.appName ?? 'RepairFully';
    String? subtitle;
    if (_appInfo != null) {
      subtitle = 'v${_appInfo!.version} (${_appInfo!.buildNumber})';
      if (_shorebirdAvailable && _currentPatch != null) {
        subtitle = '$subtitle · Patch #$_currentPatch';
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          name,
          style: const TextStyle(
            color: RfColors.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 15.3,
          ),
        ),
        if (subtitle != null)
          Text(
            subtitle,
            style: const TextStyle(
              color: RfColors.textSecondary,
              fontSize: 10.5,
              fontFamily: 'monospace',
            ),
          ),
      ],
    );
  }

  Future<void> _goToLiveCapture(BuildContext context, CaptureMode mode) async {
    final cameraOk = await PermissionService.isCameraGranted();
    if (!cameraOk) {
      final results = await PermissionService.requestCameraPermissions();
      if (!results[Permission.camera]!.isGranted) {
        if (!context.mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Camera permission required'),
            action: SnackBarAction(label: 'Settings', onPressed: PermissionService.openSettings),
          ),
        );
        return;
      }
    }

    final storageOk = await PermissionService.isStorageGranted();
    if (!storageOk) {
      await PermissionService.requestStoragePermission();
    }

    await Future<void>.delayed(const Duration(milliseconds: 300));
    if (!context.mounted) return;
    unawaited(Navigator.push(context, MaterialPageRoute<bool>(
      builder: (_) => LiveCaptureScreen(mode: mode),
    )));
  }
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
    return RfLiquidGlassContainer(
      onTap: onTap,
      padding: const EdgeInsets.all(20),
      borderColor: color.withValues(alpha: 0.32),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(RfRadius.card),
              border: Border.all(color: color.withValues(alpha: 0.35)),
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
    );
  }
}
