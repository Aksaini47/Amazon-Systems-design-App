import 'dart:async';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_logo.dart';
import 'settings_screen.dart';
import 'live_capture_screen.dart';
import 'local_gallery_screen.dart';
import '../models/capture_session.dart';
import '../services/local_storage_service.dart';
import '../services/permission_service.dart';
import '../services/update_service.dart';
import '../utils/volume_button_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    _recoverOrphanVideos();
    _maybeShowChangelog();
    VolumeButtonService().registerListener('home_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (event == 1) _goToLiveCapture(context, CaptureMode.pk);
      if (event == 2) _goToLiveCapture(context, CaptureMode.rt);
    });
  }

  Future<void> _maybeShowChangelog() async {
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

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: RfGlassAppBar(
        titleWidget: const RfLogo(size: 34, showLabel: true),
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
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
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

  Future<void> _goToLiveCapture(BuildContext context, CaptureMode mode) async {
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

    final storageOk = await PermissionService.isStorageGranted();
    if (!storageOk) {
      await PermissionService.requestStoragePermission();
    }

    await Future.delayed(const Duration(milliseconds: 300));
    if (!mounted) return;
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => LiveCaptureScreen(mode: mode),
    ));
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
    return RfGlassContainer(
      onTap: onTap,
      padding: const EdgeInsets.all(20),
      radius: RfRadius.lg,
      borderColor: color.withValues(alpha: 0.25),
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
