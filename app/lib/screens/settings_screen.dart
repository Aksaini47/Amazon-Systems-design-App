import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:file_picker/file_picker.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../theme/rf_colors.dart';
import '../services/api_service.dart';
import '../services/discovery_service.dart';
import '../services/camera_settings_service.dart';
import '../services/local_storage_service.dart';
import '../services/update_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _ctrl = TextEditingController();
  bool _testing = false;
  bool _discovering = false;
  String? _pingResult;

  // Camera settings
  ResolutionPreset _resolution = ResolutionPreset.veryHigh;
  int _fps = 30;
  bool _sound = true;
  bool _timestampImage = false;
  // Default mic state when entering camera
  bool _micDefault = false;
  // New: capture countdown (0=manual, 3/5/10=seconds)
  int _captureCountdown = 3;
  // New: aspect ratio default (9/16 = 16:9 portrait, 3/4 = 3:4, 1.0 = 1:1)
  double _aspectDefault = 9 / 16;
  // Backend info (populated when /api/config responds)
  Map<String, dynamic>? _backendInfo;
  // Storage path settings
  String _selectedStoragePath = CameraSettingsService.storageDefault;
  String _customStoragePath = '';

  @override
  void initState() {
    super.initState();
    ApiService.getBaseUrl().then((url) => _ctrl.text = url);
    _loadCameraSettings();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _loadCameraSettings() async {
    _resolution = await CameraSettingsService.getResolution();
    _fps = await CameraSettingsService.getFps();
    _sound = await CameraSettingsService.getSound();
    _timestampImage = await CameraSettingsService.getTimestampImage();
    _micDefault = await CameraSettingsService.getMicDefault();
    _captureCountdown = await CameraSettingsService.getCaptureCountdown();
    _aspectDefault = await CameraSettingsService.getAspectDefault();
    _selectedStoragePath = await CameraSettingsService.getStoragePath();
    _customStoragePath = _selectedStoragePath;
    if (mounted) setState(() {});
  }

  Future<void> _save() async {
    await ApiService.setBaseUrl(_ctrl.text.trim());
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Backend URL saved')));
  }

  Future<void> _ping() async {
    setState(() { _testing = true; _pingResult = null; _backendInfo = null; });
    final ok = await ApiService.ping();
    final info = ok ? await ApiService.getConfig() : null;
    setState(() {
      _testing = false;
      _pingResult = ok ? 'Connected!' : 'Cannot reach backend. Check URL and ensure server is running.';
      _backendInfo = info;
    });
  }

  Future<void> _autoDiscover() async {
    setState(() { _discovering = true; _pingResult = null; });
    final url = await DiscoveryService.discover();
    if (!mounted) return;
    if (url != null) {
      await ApiService.setBaseUrl(url);
      _ctrl.text = url;
      setState(() { _discovering = false; _pingResult = 'Found backend at $url'; });
    } else {
      setState(() { _discovering = false; _pingResult = 'No backend found on WiFi.'; });
    }
  }

  Future<void> _restoreDefaults() async {
    await CameraSettingsService.restoreDefaults();
    await _loadCameraSettings();
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Settings restored to defaults')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: RfColors.bg,
      appBar: AppBar(
        backgroundColor: RfColors.card,
        title: const Text('Settings', style: TextStyle(fontWeight: FontWeight.w600)),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ══ BACKEND CONNECTION ══════════════════════════════════════════
            _buildSectionHeader(Icons.cloud_outlined, 'Backend Connection'),
            const SizedBox(height: 12),
            _buildTextField(
              controller: _ctrl,
              hint: 'http://192.168.1.X:3001',
              icon: Icons.link_rounded,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _buildPrimaryButton('Save', _save)),
                const SizedBox(width: 10),
                Expanded(
                  child: _testing
                      ? _buildSecondaryButton(null, _buildSpinner())
                      : _buildSecondaryButton(_ping, const Text('Test', style: TextStyle(color: Colors.white, fontSize: 14))),
                ),
              ],
            ),
            const SizedBox(height: 10),
            _buildTertiaryButton(
              iconData: Icons.wifi_find_outlined,
              label: _discovering ? 'Searching...' : 'Auto-Discover on WiFi',
              onPressed: _discovering ? null : _autoDiscover,
              color: RfColors.success,
            ),
            if (_pingResult != null) ...[
              const SizedBox(height: 12),
              _buildStatusBanner(_pingResult!),
            ],
            if (_backendInfo != null) ...[
              const SizedBox(height: 12),
              _buildBackendInfoCard(_backendInfo!),
            ],

            const SizedBox(height: 28),

            // ══ CAMERA SETTINGS ════════════════════════════════════════════
            _buildSectionHeader(Icons.videocam_outlined, 'Camera'),
            const SizedBox(height: 12),

            // Resolution & FPS row (compact stacked tiles)
            Row(
              children: [
                Expanded(child: _buildSettingTile(
                  icon: Icons.high_quality_rounded,
                  label: 'Resolution',
                  child: _buildDropdown<ResolutionPreset>(
                    value: _resolution,
                    items: const {
                      ResolutionPreset.low: '240p',
                      ResolutionPreset.medium: '480p',
                      ResolutionPreset.high: '720p',
                      ResolutionPreset.veryHigh: '1080p',
                      ResolutionPreset.ultraHigh: '4K',
                    },
                    onChanged: (v) {
                      setState(() => _resolution = v);
                      CameraSettingsService.setResolution(v);
                    },
                  ),
                )),
                const SizedBox(width: 10),
                Expanded(child: _buildSettingTile(
                  icon: Icons.speed_rounded,
                  label: 'Frame Rate',
                  child: _buildDropdown<int>(
                    value: _fps,
                    items: const {30: '30 fps', 60: '60 fps'},
                    onChanged: (v) {
                      setState(() => _fps = v);
                      CameraSettingsService.setFps(v);
                    },
                  ),
                )),
              ],
            ),
            const SizedBox(height: 10),

            // Frame Default
            _buildSettingTile(
              icon: Icons.aspect_ratio_rounded,
              label: 'Frame / Aspect Ratio',
              child: _buildDropdown<double>(
                value: _aspectDefault,
                items: {
                  9 / 16: '16:9 (fullscreen)',
                  3 / 4: '3:4 (portrait)',
                  1.0: '1:1 (square)',
                },
                onChanged: (v) {
                  setState(() => _aspectDefault = v);
                  CameraSettingsService.setAspectDefault(v);
                },
              ),
            ),
            const SizedBox(height: 10),

            // Capture Countdown
            _buildSettingTile(
              icon: Icons.timer_outlined,
              label: 'Photo Countdown',
              child: _buildDropdown<int>(
                value: _captureCountdown,
                items: const {
                  0: 'Off (manual)',
                  3: '3 seconds',
                  5: '5 seconds',
                  10: '10 seconds',
                },
                onChanged: (v) {
                  setState(() => _captureCountdown = v);
                  CameraSettingsService.setCaptureCountdown(v);
                },
              ),
            ),

            const SizedBox(height: 28),

            // ══ CAPTURE DEFAULTS ═══════════════════════════════════════════
            _buildSectionHeader(Icons.tune_rounded, 'Capture Defaults'),
            const SizedBox(height: 12),

            _buildSettingToggle(
              icon: Icons.mic_rounded,
              label: 'Microphone',
              subtitle: 'Record video with audio (toggle in camera to override)',
              value: _micDefault,
              onChanged: (v) {
                setState(() => _micDefault = v);
                CameraSettingsService.setMicDefault(v);
              },
            ),
            const SizedBox(height: 10),

            _buildSettingToggle(
              icon: Icons.volume_up_rounded,
              label: 'Shutter Sounds',
              subtitle: 'Play sounds when capturing photos / starting recording',
              value: _sound,
              onChanged: (v) {
                setState(() => _sound = v);
                CameraSettingsService.setSound(v);
              },
            ),
            const SizedBox(height: 10),

            _buildSettingToggle(
              icon: Icons.access_time_rounded,
              label: 'Photo Timestamp',
              subtitle: 'Overlay order ID + date/time on saved photos',
              value: _timestampImage,
              onChanged: (v) {
                setState(() => _timestampImage = v);
                CameraSettingsService.setTimestampImage(v);
              },
            ),

            const SizedBox(height: 28),

            // ══ STORAGE ════════════════════════════════════════════════════
            _buildSectionHeader(Icons.folder_outlined, 'Storage'),
            const SizedBox(height: 12),

            // Single storage selector - opens file manager on tap
            InkWell(
              onTap: () async {
                String? selectedDir = await FilePicker.platform.getDirectoryPath();
                if (selectedDir != null) {
                  setState(() {
                    _selectedStoragePath = selectedDir;
                    _customStoragePath = selectedDir;
                  });
                  CameraSettingsService.setStoragePath(selectedDir);
                  LocalStorageService.clearCache();
                }
              },
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: RfColors.card,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: RfColors.border),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: RfColors.surface,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(
                        Icons.folder_outlined,
                        color: Color(0xFF8B949E),
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Storage Location',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 15,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            _selectedStoragePath.isNotEmpty ? _selectedStoragePath : 'Tap to select folder',
                            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right, color: Color(0xFF8B949E), size: 24),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 28),

            // ══ ABOUT ══════════════════════════════════════════════════════
            _buildSectionHeader(Icons.info_outline_rounded, 'About'),
            const SizedBox(height: 12),
            _AboutCard(),

            const SizedBox(height: 28),

            // ══ RESET ══════════════════════════════════════════════════════
            _buildDangerButton(
              icon: Icons.restore_rounded,
              label: 'Restore Defaults',
              onPressed: _restoreDefaults,
            ),

            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  // ─── Widget Builders ─────────────────────────────────────────────────────

  Widget _buildSectionHeader(IconData icon, String label) {
    return Row(
      children: [
        Icon(icon, color: RfColors.navy, size: 18),
        const SizedBox(width: 8),
        Text(
          label.toUpperCase(),
          style: const TextStyle(
            color: Color(0xFF8B949E),
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
          ),
        ),
      ],
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: RfColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: RfColors.border),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: const BoxDecoration(
              border: Border(right: BorderSide(color: Color(0xFF30363D))),
            ),
            child: Icon(icon, color: RfColors.textSecondary, size: 20),
          ),
          Expanded(
            child: TextField(
              controller: controller,
              style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14),
              decoration: InputDecoration(
                hintText: hint,
                hintStyle: const TextStyle(color: Color(0xFF4D5565)),
                border: InputBorder.none,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPrimaryButton(String label, VoidCallback? onPressed) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: RfColors.navy,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        elevation: 0,
      ),
      child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
    );
  }

  Widget _buildSecondaryButton(VoidCallback? onPressed, Widget child) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
        side: const BorderSide(color: Color(0xFF30363D)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      child: child,
    );
  }

  Widget _buildTertiaryButton({
    required IconData iconData,
    required String label,
    required VoidCallback? onPressed,
    required Color color,
  }) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: color,
        padding: const EdgeInsets.symmetric(vertical: 12),
        side: BorderSide(color: color.withOpacity(0.5)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      icon: Icon(iconData, size: 18, color: color),
      label: Text(label, style: TextStyle(color: color, fontSize: 13)),
    );
  }

  /// Card showing backend details after a successful Test:
  ///   - Where files land on the desktop (storage_root)
  ///   - All local IPs the backend is reachable at (helps when phone hotspot)
  Widget _buildBackendInfoCard(Map<String, dynamic> info) {
    final storageRoot = info['storage_root'] as String? ?? 'unknown';
    final ordersPath = info['orders_path'] as String? ?? '$storageRoot/orders';
    final port = info['port'];
    final ips = (info['local_ips'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final hostname = info['hostname'] as String? ?? '';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: RfColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x553FB950)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.folder_open, color: Color(0xFF3FB950), size: 18),
            const SizedBox(width: 8),
            const Text('Backend storage', style: TextStyle(color: Color(0xFF3FB950), fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1)),
          ]),
          const SizedBox(height: 8),
          Text(ordersPath, style: const TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace')),
          const SizedBox(height: 4),
          Text('on $hostname', style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
          if (ips.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('Reachable at', style: TextStyle(color: Color(0xFF8B949E), fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1)),
            const SizedBox(height: 4),
            ...ips.map((e) => Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(
                    'http://${e['ip']}:$port  (${e['interface']})',
                    style: const TextStyle(color: Colors.white70, fontSize: 11, fontFamily: 'monospace'),
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusBanner(String message) {
    final isSuccess = message.startsWith('Connected') || message.startsWith('Found');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isSuccess ? RfColors.successBg : RfColors.errorBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: isSuccess ? RfColors.successBorder : RfColors.errorBorder),
      ),
      child: Row(
        children: [
          Icon(
            isSuccess ? Icons.check_circle_outline : Icons.error_outline,
            color: isSuccess ? RfColors.success : RfColors.error,
            size: 18,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: isSuccess ? RfColors.success : RfColors.error,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Stacked tile — icon+label on top row, dropdown on full-width row below.
  /// Avoids label truncation when laid out in a narrow Expanded column.
  Widget _buildSettingTile({required IconData icon, required String label, required Widget child}) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        color: RfColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: RfColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(icon, color: RfColors.textSecondary, size: 14),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label.toUpperCase(),
                  style: const TextStyle(
                    color: Color(0xFF8B949E),
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.8,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Align(alignment: Alignment.centerLeft, child: child),
        ],
      ),
    );
  }

  Widget _buildSettingToggle({
    required IconData icon,
    required String label,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: RfColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: RfColors.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: RfColors.textSecondary, size: 22),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
                const SizedBox(height: 2),
                Text(subtitle, style: const TextStyle(color: Color(0xFF4D5565), fontSize: 12)),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: RfColors.navy,
            inactiveTrackColor: RfColors.border,
          ),
        ],
      ),
    );
  }

  Widget _buildDangerButton({required IconData icon, required String label, required VoidCallback onPressed}) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.red.shade400,
        padding: const EdgeInsets.symmetric(vertical: 14),
        side: BorderSide(color: Colors.red.shade800),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      icon: Icon(icon, size: 20),
      label: Text(label, style: const TextStyle(fontSize: 14)),
    );
  }

  Widget _buildDropdown<T>({
    required T value,
    required Map<T, String> items,
    required ValueChanged<T> onChanged,
  }) {
    return PopupMenuButton<T>(
      initialValue: value,
      onSelected: onChanged,
      offset: const Offset(0, 44),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      color: RfColors.surface,
      elevation: 6,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: RfColors.bg,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: RfColors.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              items[value] ?? value.toString(),
              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.expand_more, color: Color(0xFF8B949E), size: 18),
          ],
        ),
      ),
      itemBuilder: (context) => items.entries.map((e) {
        final isSelected = e.key == value;
        return PopupMenuItem<T>(
          value: e.key,
          height: 40,
          child: Row(
            children: [
              if (isSelected) const Icon(Icons.check, color: RfColors.navy, size: 16),
              if (isSelected) const SizedBox(width: 8),
              Expanded(
                child: Text(
                  e.value,
                  style: TextStyle(
                    color: isSelected ? Colors.white : Color(0xFF8B949E),
                    fontSize: 13,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSpinner({double size = 16}) {
    return SizedBox(
      width: size,
      height: size,
      child: const CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF8B949E)),
    );
  }
}

// ─── About card ──────────────────────────────────────────────────────────
//
// Surfaces app version, Shorebird code-push state, Firebase Crashlytics
// status, and a "Check for updates" action. Read-only diagnostics for the
// operator (Mahika) to verify the rig is healthy.

class _AboutCard extends StatefulWidget {
  @override
  State<_AboutCard> createState() => _AboutCardState();
}

class _AboutCardState extends State<_AboutCard> {
  PackageInfo? _info;
  int? _currentPatch;
  int? _nextPatch;
  bool _shorebirdAvailable = false;
  bool _checking = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      _info = await PackageInfo.fromPlatform();
    } catch (_) {}
    _shorebirdAvailable = await UpdateService.isAvailable;
    _currentPatch = await UpdateService.currentPatchNumber();
    _nextPatch = await UpdateService.nextPatchNumber();
    if (mounted) setState(() {});
  }

  Future<void> _checkUpdates() async {
    setState(() => _checking = true);
    final r = await UpdateService.checkManually();
    if (!mounted) return;
    setState(() => _checking = false);
    await _load();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Row(children: [
        Icon(
          r.outcome == UpdateOutcome.upToDate ? Icons.check_circle_outline : Icons.cloud_download_outlined,
          color: r.outcome == UpdateOutcome.failed ? const Color(0xFFFF7B72) : const Color(0xFF3FB950),
          size: 18,
        ),
        const SizedBox(width: 8),
        Expanded(child: Text(r.message)),
      ]),
      duration: const Duration(seconds: 3),
      backgroundColor: Colors.black87,
    ));
  }

  void _showChangelog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(children: [
          Icon(Icons.history_rounded, color: Color(0xFF388BFD), size: 22),
          SizedBox(width: 10),
          Text('What\'s new', style: TextStyle(color: Colors.white)),
        ]),
        content: SingleChildScrollView(
          child: Text(
            UpdateService.latestChangelog,
            style: const TextStyle(color: Color(0xFFE6EDF3), fontSize: 13, height: 1.4),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close', style: TextStyle(color: Colors.white70)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final firebaseUp = Firebase.apps.isNotEmpty;
    final appName = _info?.appName ?? 'RF Logger';
    final version = _info != null ? '${_info!.version} (build ${_info!.buildNumber})' : '—';
    final packageName = _info?.packageName ?? '—';

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header row: app name + version
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
            child: Row(children: [
              Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  color: const Color(0xFFE86C2B).withAlpha(40),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.camera_outlined, color: Color(0xFFE86C2B), size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(appName,
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text('v$version',
                        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12, fontFamily: 'monospace')),
                  ],
                ),
              ),
            ]),
          ),

          const Divider(height: 1, color: Color(0xFF30363D)),

          // Detail rows
          _row(Icons.tag_outlined, 'Package', packageName, monospace: true),
          _row(
            Icons.cloud_outlined,
            'Crashlytics',
            firebaseUp ? 'Connected (rf-logger)' : 'Not connected',
            valueColor: firebaseUp ? const Color(0xFF3FB950) : const Color(0xFFFF7B72),
          ),
          _row(
            Icons.system_update_outlined,
            'Code-push',
            _shorebirdAvailable
                ? (_currentPatch == null
                    ? 'Active · base release (no OTA patch yet)'
                    : 'Active · patch #$_currentPatch')
                : 'Not active — install Shorebird release APK',
            valueColor: _shorebirdAvailable ? const Color(0xFF3FB950) : const Color(0xFF8B949E),
          ),
          if (_nextPatch != null)
            _row(
              Icons.download_for_offline_outlined,
              'Staged update',
              'Patch #$_nextPatch — applies on next launch',
              valueColor: const Color(0xFFFFA657),
            ),
          _row(Icons.security_outlined, 'Signed by', 'repairfully-dev.jks', monospace: true),

          const Divider(height: 1, color: Color(0xFF30363D)),

          // Action buttons
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            child: Row(children: [
              Expanded(
                child: TextButton.icon(
                  onPressed: _checking ? null : _checkUpdates,
                  icon: _checking
                      ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.refresh_rounded, size: 18),
                  label: Text(_checking ? 'Checking…' : 'Check for updates'),
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFF388BFD),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                ),
              ),
              Container(width: 1, height: 22, color: const Color(0xFF30363D)),
              Expanded(
                child: TextButton.icon(
                  onPressed: _showChangelog,
                  icon: const Icon(Icons.history_rounded, size: 18),
                  label: const Text('What\'s new'),
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFFE86C2B),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                ),
              ),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _row(IconData icon, String label, String value,
      {Color? valueColor, bool monospace = false}) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
      child: Row(children: [
        Icon(icon, color: const Color(0xFF8B949E), size: 16),
        const SizedBox(width: 10),
        Text(label, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
        const Spacer(),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: valueColor ?? Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              fontFamily: monospace ? 'monospace' : null,
            ),
          ),
        ),
      ]),
    );
  }
}