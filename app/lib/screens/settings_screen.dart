import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import 'package:file_picker/file_picker.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../screens/activity_log_screen.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../models/capture_session.dart';
import '../services/camera_settings_service.dart';
import '../services/local_storage_service.dart';
import '../services/update_service.dart';
import '../widgets/rf_button.dart';
import 'tour_dialog.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // Camera settings
  ResolutionPreset _resolution = ResolutionPreset.veryHigh;
  int _fps = 60;
  bool _sound = true;
  bool _timestampImage = false;
  // Default mic state when entering camera
  bool _micDefault = false;
  bool _autoLabelScan = false;
  bool _autoLabelSave = true;
  bool _claimPhotoCountdown = false;
  // New: capture countdown (0=manual, 3/5/10=seconds)
  int _captureCountdown = 3;
  // Per-mode aspect ratio default (9/16 = 16:9 portrait, 3/4 = 3:4, 1.0 = 1:1)
  double _aspectDefaultPk = CameraSettingsService.aspectFull;
  double _aspectDefaultRt = CameraSettingsService.aspectFull;
  // Per-mode zoom default (0=1x, 1=2x, 2=3x)
  int _zoomDefaultPk = 0;
  int _zoomDefaultRt = 0;
  // Label popup: seconds to hold the captured still before auto-confirming
  // (0 = instant, old behavior)
  int _labelReviewHoldSeconds = 3;
  // Storage path settings
  String _selectedStoragePath = CameraSettingsService.storageDefault;

  // Accordion open/close state — multi-open (opening one doesn't close
  // others). Only Camera starts open so the page opens as a readable index.
  final Set<String> _openSections = {'Camera'};

  @override
  void initState() {
    super.initState();
    _loadCameraSettings();
  }

  Future<void> _loadCameraSettings() async {
    _resolution = await CameraSettingsService.getResolution();
    _fps = await CameraSettingsService.getFps();
    _sound = await CameraSettingsService.getSound();
    _timestampImage = await CameraSettingsService.getTimestampImage();
    _micDefault = await CameraSettingsService.getMicDefault();
    _captureCountdown = await CameraSettingsService.getCaptureCountdown();
    _aspectDefaultPk = await CameraSettingsService.getAspectDefaultForMode(CaptureMode.pk);
    _aspectDefaultRt = await CameraSettingsService.getAspectDefaultForMode(CaptureMode.rt);
    _zoomDefaultPk = await CameraSettingsService.getZoomDefaultForMode(CaptureMode.pk);
    _zoomDefaultRt = await CameraSettingsService.getZoomDefaultForMode(CaptureMode.rt);
    _labelReviewHoldSeconds = await CameraSettingsService.getLabelReviewHoldSeconds();
    _autoLabelScan = await CameraSettingsService.getAutoLabelScan();
    _autoLabelSave = await CameraSettingsService.getAutoLabelSave();
    _claimPhotoCountdown = await CameraSettingsService.getClaimPhotoCountdown();
    _selectedStoragePath = await CameraSettingsService.getStoragePath();
    if (mounted) setState(() {});
  }

  Future<void> _restoreDefaults() async {
    await CameraSettingsService.restoreDefaults();
    await _loadCameraSettings();
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Settings restored to defaults')));
  }

  void _toggleSection(String key) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_openSections.contains(key)) {
        _openSections.remove(key);
      } else {
        _openSections.add(key);
      }
    });
  }

  /// Short summary shown on a collapsed section header — so the index is
  /// still informative without expanding (standard settings-app pattern).
  String _summaryFor(String key) {
    switch (key) {
      case 'Camera':
        return '${_resolutionLabel(_resolution)} · $_fps fps';
      case 'Capture & QC':
        return _captureCountdown == 0 ? 'Manual capture' : '${_captureCountdown}s countdown';
      case 'Storage':
        return _selectedStoragePath.isNotEmpty
            ? _selectedStoragePath.split('/').last
            : 'Not set';
      default:
        return '';
    }
  }

  static String _resolutionLabel(ResolutionPreset p) => switch (p) {
        ResolutionPreset.low => '240p',
        ResolutionPreset.medium => '480p',
        ResolutionPreset.high => '720p',
        ResolutionPreset.veryHigh => '1080p',
        ResolutionPreset.ultraHigh => '4K',
        ResolutionPreset.max => 'Max',
      };

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: const RfGlassAppBar(title: 'Settings'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildAccordionSection(
              icon: Icons.videocam_outlined,
              label: 'Camera',
              sectionKey: 'Camera',
              children: [
                _buildRow(
                  label: 'Resolution',
                  isFirst: true,
                  trailing: _buildDropdown<ResolutionPreset>(
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
                ),
                _buildRow(
                  label: 'Frame rate',
                  trailing: _buildDropdown<int>(
                    value: _fps,
                    items: const {30: '30 fps', 60: '60 fps'},
                    onChanged: (v) {
                      setState(() => _fps = v);
                      CameraSettingsService.setFps(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'PK frame ratio',
                  subtitle: 'Default aspect for packing sessions',
                  trailing: _buildDropdown<double>(
                    value: CameraSettingsService.normalizeAspect(_aspectDefaultPk),
                    items: {
                      CameraSettingsService.aspectFull: '16:9',
                      CameraSettingsService.aspect34: '3:4',
                      CameraSettingsService.aspect11: '1:1',
                    },
                    onChanged: (v) {
                      setState(() => _aspectDefaultPk = v);
                      CameraSettingsService.setAspectDefaultForMode(CaptureMode.pk, v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'RT frame ratio',
                  subtitle: 'Default aspect for return sessions',
                  trailing: _buildDropdown<double>(
                    value: CameraSettingsService.normalizeAspect(_aspectDefaultRt),
                    items: {
                      CameraSettingsService.aspectFull: '16:9',
                      CameraSettingsService.aspect34: '3:4',
                      CameraSettingsService.aspect11: '1:1',
                    },
                    onChanged: (v) {
                      setState(() => _aspectDefaultRt = v);
                      CameraSettingsService.setAspectDefaultForMode(CaptureMode.rt, v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'PK default zoom',
                  trailing: _buildDropdown<int>(
                    value: _zoomDefaultPk,
                    items: const {0: '1×', 1: '2×', 2: '3×'},
                    onChanged: (v) {
                      setState(() => _zoomDefaultPk = v);
                      CameraSettingsService.setZoomDefaultForMode(CaptureMode.pk, v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'RT default zoom',
                  trailing: _buildDropdown<int>(
                    value: _zoomDefaultRt,
                    items: const {0: '1×', 1: '2×', 2: '3×'},
                    onChanged: (v) {
                      setState(() => _zoomDefaultRt = v);
                      CameraSettingsService.setZoomDefaultForMode(CaptureMode.rt, v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Shutter sounds',
                  subtitle: 'Play a sound when capturing or starting a recording',
                  trailing: _buildSwitch(
                    value: _sound,
                    onChanged: (v) {
                      setState(() => _sound = v);
                      CameraSettingsService.setSound(v);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildAccordionSection(
              icon: Icons.tune_rounded,
              label: 'Capture & QC',
              sectionKey: 'Capture & QC',
              children: [
                _buildRow(
                  label: 'Microphone default',
                  subtitle: 'Start PK/RT sessions with the mic on',
                  isFirst: true,
                  trailing: _buildSwitch(
                    value: _micDefault,
                    onChanged: (v) {
                      setState(() => _micDefault = v);
                      CameraSettingsService.setMicDefault(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Photo countdown',
                  trailing: _buildDropdown<int>(
                    value: _captureCountdown,
                    items: const {
                      0: 'Off',
                      3: '3 sec',
                      5: '5 sec',
                      10: '10 sec',
                    },
                    onChanged: (v) {
                      setState(() => _captureCountdown = v);
                      CameraSettingsService.setCaptureCountdown(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'RT claim photo countdown',
                  subtitle: 'Countdown before each return photo',
                  trailing: _buildSwitch(
                    value: _claimPhotoCountdown,
                    onChanged: (v) {
                      setState(() => _claimPhotoCountdown = v);
                      CameraSettingsService.setClaimPhotoCountdown(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Return images by QC',
                  subtitle: 'QC OK: front/back only. Damaged or different: label, contents, front and back. Fixed by design.',
                  trailing: const Icon(Icons.lock_outline_rounded, size: 18, color: RfColors.textMuted),
                ),
                _buildRow(
                  label: 'Photo timestamp',
                  subtitle: 'Overlay date and time on saved photos',
                  trailing: _buildSwitch(
                    value: _timestampImage,
                    onChanged: (v) {
                      setState(() => _timestampImage = v);
                      CameraSettingsService.setTimestampImage(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Auto label scan',
                  subtitle: 'Scan the label once when the Order ID popup opens',
                  trailing: _buildSwitch(
                    value: _autoLabelScan,
                    onChanged: (v) {
                      setState(() => _autoLabelScan = v);
                      CameraSettingsService.setAutoLabelScan(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Auto save after scan',
                  subtitle: 'Close the label popup once the Order ID is valid',
                  trailing: _buildSwitch(
                    value: _autoLabelSave,
                    onChanged: (v) {
                      setState(() => _autoLabelSave = v);
                      CameraSettingsService.setAutoLabelSave(v);
                    },
                  ),
                ),
                _buildRow(
                  label: 'Label review hold',
                  subtitle: 'Pause to confirm the print before auto-saving',
                  trailing: _buildDropdown<int>(
                    value: _labelReviewHoldSeconds,
                    items: const {0: 'Off', 2: '2 sec', 3: '3 sec', 5: '5 sec'},
                    onChanged: (v) {
                      setState(() => _labelReviewHoldSeconds = v);
                      CameraSettingsService.setLabelReviewHoldSeconds(v);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildAccordionSection(
              icon: Icons.folder_outlined,
              label: 'Storage',
              sectionKey: 'Storage',
              children: [
                _buildRow(
                  label: 'Storage location',
                  subtitle: _selectedStoragePath.isNotEmpty ? _selectedStoragePath : 'Tap to select a folder',
                  isFirst: true,
                  trailing: const Icon(Icons.chevron_right_rounded, size: 20, color: RfColors.textSecondary),
                  onTap: () async {
                    final selectedDir = await FilePicker.platform.getDirectoryPath();
                    if (selectedDir != null) {
                      setState(() => _selectedStoragePath = selectedDir);
                      await CameraSettingsService.setStoragePath(selectedDir);
                      LocalStorageService.clearCache();
                    }
                  },
                ),
                _buildRow(
                  label: 'Activity log',
                  subtitle: 'Last 60 days — shipment events by day',
                  trailing: const Icon(Icons.chevron_right_rounded, size: 20, color: RfColors.textSecondary),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(builder: (_) => const ActivityLogScreen()),
                    );
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildAccordionSection(
              icon: Icons.info_outline_rounded,
              label: 'About & Updates',
              sectionKey: 'About & Updates',
              children: const [_AboutCard()],
            ),

            const SizedBox(height: 28),

            RfButton.secondary(
              icon: Icons.restore_rounded,
              label: 'Restore defaults',
              accentColor: RfColors.error,
              fullWidth: true,
              onPressed: _restoreDefaults,
            ),
          ],
        ),
      ),
    );
  }

  // ─── Widget Builders ─────────────────────────────────────────────────────

  /// One accordion section, rendered as a self-contained card: tappable
  /// header (icon badge + title + summary + rotating chevron) over a
  /// collapsing body. Multi-open — toggling one never closes another
  /// (state lives in [_openSections]).
  Widget _buildAccordionSection({
    required IconData icon,
    required String label,
    required String sectionKey,
    required List<Widget> children,
  }) {
    final isOpen = _openSections.contains(sectionKey);
    final summary = isOpen ? '' : _summaryFor(sectionKey);

    return RfGlassContainer(
      blurEnabled: false,
      radius: RfRadius.lg,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            onTap: () => _toggleSection(sectionKey),
            borderRadius: BorderRadius.circular(RfRadius.lg),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 15, 16, 15),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.07),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
                    ),
                    child: Icon(icon, size: 18, color: RfColors.textSecondary),
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Text(
                      label,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (summary.isNotEmpty) ...[
                    Flexible(
                      child: Text(
                        summary,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.right,
                        style: const TextStyle(color: RfColors.textSecondary, fontSize: 13),
                      ),
                    ),
                    const SizedBox(width: 6),
                  ],
                  AnimatedRotation(
                    turns: isOpen ? 0.25 : 0,
                    duration: RfDuration.fade,
                    child: const Icon(Icons.chevron_right_rounded, size: 20, color: RfColors.textSecondary),
                  ),
                ],
              ),
            ),
          ),
          AnimatedSize(
            duration: RfDuration.controlsFade,
            curve: Curves.easeInOut,
            alignment: Alignment.topCenter,
            child: isOpen
                ? Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _hairline(),
                        ...children,
                      ],
                    ),
                  )
                : const SizedBox(width: double.infinity, height: 0),
          ),
        ],
      ),
    );
  }

  static Widget _hairline({double indent = 0}) => Divider(
        height: 1,
        thickness: 1,
        indent: indent,
        color: Colors.white.withValues(alpha: 0.09),
      );

  /// One settings row — label (+ optional subtitle) on the left, control on
  /// the right, hairline separator above unless [isFirst].
  Widget _buildRow({
    required String label,
    String? subtitle,
    required Widget trailing,
    VoidCallback? onTap,
    bool isFirst = false,
  }) {
    final content = Padding(
      padding: const EdgeInsets.fromLTRB(16, 11, 16, 11),
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 32),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      subtitle,
                      style: const TextStyle(color: RfColors.textSecondary, fontSize: 12, height: 1.35),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 14),
            trailing,
          ],
        ),
      ),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!isFirst) _hairline(indent: 16),
        if (onTap == null) content else InkWell(onTap: onTap, child: content),
      ],
    );
  }

  Widget _buildSwitch({required bool value, required ValueChanged<bool> onChanged}) {
    return Switch(
      value: value,
      onChanged: onChanged,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return RfColors.success;
        return RfColors.border;
      }),
      thumbColor: WidgetStateProperty.all(Colors.white),
      trackOutlineColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return RfColors.success.withValues(alpha: 0.6);
        return RfColors.border;
      }),
    );
  }

  /// Value control — a proper filled pill (value + chevron), tappable as a
  /// whole. Mechanism is unchanged [PopupMenuButton]; only the trigger's
  /// visual is a real control instead of bare text.
  Widget _buildDropdown<T>({
    required T value,
    required Map<T, String> items,
    required ValueChanged<T> onChanged,
  }) {
    return PopupMenuButton<T>(
      initialValue: value,
      onSelected: onChanged,
      offset: const Offset(0, 42),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      color: RfColors.surface,
      elevation: 8,
      tooltip: '',
      child: Container(
        constraints: const BoxConstraints(minHeight: 36),
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.07),
          borderRadius: BorderRadius.circular(RfRadius.chip),
          border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              items[value] ?? value.toString(),
              style: const TextStyle(color: Colors.white, fontSize: 13.5, fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 6),
            const Icon(Icons.expand_more_rounded, color: RfColors.textSecondary, size: 17),
          ],
        ),
      ),
      itemBuilder: (context) => items.entries.map((e) {
        final isSelected = e.key == value;
        return PopupMenuItem<T>(
          value: e.key,
          height: 44,
          child: Row(
            children: [
              Expanded(
                child: Text(
                  e.value,
                  style: TextStyle(
                    color: isSelected ? Colors.white : RfColors.textPrimary,
                    fontSize: 14,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
              if (isSelected) const Icon(Icons.check_rounded, color: RfColors.successLight, size: 18),
            ],
          ),
        );
      }).toList(),
    );
  }
}

// ─── About card ──────────────────────────────────────────────────────────
//
// Surfaces app version, Shorebird code-push state, Firebase Crashlytics
// status, and the update / changelog / tour actions. Read-only diagnostics
// for the operator (Mahika) to verify the rig is healthy. Lives inside the
// "About & Updates" accordion section, so it carries no card chrome of its
// own — it matches the row rhythm of the other sections.

class _AboutCard extends StatefulWidget {
  const _AboutCard();

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
    if (!_shorebirdAvailable) {
      final r = await UpdateService.checkManually();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Row(children: [
          const Icon(Icons.info_outline, color: RfColors.amber, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(r.message)),
        ]),
        duration: const Duration(seconds: 5),
        backgroundColor: Colors.black87,
      ));
      return;
    }
    setState(() => _checking = true);
    final r = await UpdateService.checkManually();
    if (!mounted) return;
    setState(() => _checking = false);
    await _load();
    if (!mounted) return;
    final icon = switch (r.outcome) {
      UpdateOutcome.upToDate => Icons.check_circle_outline,
      UpdateOutcome.downloaded || UpdateOutcome.restartRequired => Icons.cloud_download_outlined,
      UpdateOutcome.unavailable => Icons.info_outline,
      UpdateOutcome.failed => Icons.error_outline,
    };
    final color = switch (r.outcome) {
      UpdateOutcome.failed => RfColors.error,
      UpdateOutcome.unavailable => RfColors.amber,
      _ => RfColors.successLight,
    };
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(child: Text(r.message)),
      ]),
      duration: Duration(seconds: r.outcome == UpdateOutcome.unavailable ? 5 : 3),
      backgroundColor: Colors.black87,
    ));
  }

  void _showChangelog() {
    showDialog<void>(
      context: context,
      builder: (ctx) => RfGlassDialog(
        child: AlertDialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
          title: const Row(children: [
            Icon(Icons.history_rounded, color: RfColors.rtAccent, size: 22),
            SizedBox(width: 10),
            Text('What\'s new', style: TextStyle(color: Colors.white)),
          ]),
          content: SingleChildScrollView(
            child: Text(
              UpdateService.latestChangelog,
              style: const TextStyle(color: RfColors.textPrimary, fontSize: 13, height: 1.4),
            ),
          ),
          actions: [
            RfButton.secondary(
              label: 'Close',
              onPressed: () => Navigator.pop(ctx),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final firebaseUp = Firebase.apps.isNotEmpty;
    final appName = _info?.appName ?? 'RF Logger';
    final version = _info != null ? '${_info!.version} (build ${_info!.buildNumber})' : '—';
    final packageName = _info?.packageName ?? '—';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Identity block: app icon + name + version
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
          child: Row(children: [
            SizedBox(
              width: 46,
              height: 46,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.asset(
                  'assets/branding/rf_logo.png',
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    color: RfColors.pkAccent.withAlpha(40),
                    child: const Icon(Icons.camera_outlined, color: RfColors.pkAccent, size: 22),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(appName,
                      style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 3),
                  Text('v$version',
                      style: const TextStyle(color: RfColors.textSecondary, fontSize: 12, fontFamily: 'monospace')),
                ],
              ),
            ),
          ]),
        ),

        _SettingsScreenState._hairline(indent: 16),

        // Diagnostics
        _infoRow(Icons.tag_outlined, 'Package', packageName, monospace: true),
        _infoRow(
          Icons.cloud_outlined,
          'Crashlytics',
          firebaseUp ? 'Connected' : 'Not connected',
          valueColor: firebaseUp ? RfColors.successLight : RfColors.error,
        ),
        _infoRow(
          Icons.system_update_outlined,
          'Code-push',
          _shorebirdAvailable
              ? (_currentPatch == null ? 'Base release' : 'Patch #$_currentPatch')
              : (kReleaseMode ? 'Inactive' : 'Debug build'),
          valueColor: _shorebirdAvailable ? RfColors.successLight : RfColors.textSecondary,
        ),
        if (_nextPatch != null)
          _infoRow(
            Icons.download_for_offline_outlined,
            'Staged update',
            'Patch #$_nextPatch',
            valueColor: RfColors.amber,
          ),
        _infoRow(Icons.security_outlined, 'Signed by', 'debug keystore', monospace: true),

        _SettingsScreenState._hairline(indent: 16),

        // Actions — full-width rows rather than a cramped 3-button strip.
        _actionRow(
          Icons.refresh_rounded,
          _checking ? 'Checking…' : 'Check for updates',
          _checking ? null : _checkUpdates,
        ),
        _SettingsScreenState._hairline(indent: 52),
        _actionRow(Icons.history_rounded, 'What\'s new', _showChangelog),
        _SettingsScreenState._hairline(indent: 52),
        _actionRow(Icons.help_outline_rounded, 'Replay tour', () => TourDialog.show(context)),
      ],
    );
  }

  Widget _infoRow(IconData icon, String label, String value,
      {Color? valueColor, bool monospace = false}) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 11, 16, 11),
      child: Row(children: [
        Icon(icon, color: RfColors.textMuted, size: 17),
        const SizedBox(width: 13),
        Text(label, style: const TextStyle(color: RfColors.textSecondary, fontSize: 13)),
        const Spacer(),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: valueColor ?? Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w600,
              fontFamily: monospace ? 'monospace' : null,
            ),
          ),
        ),
      ]),
    );
  }

  Widget _actionRow(IconData icon, String label, VoidCallback? onTap) {
    final disabled = onTap == null;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        child: Row(children: [
          Icon(icon, size: 19, color: disabled ? RfColors.textMuted : RfColors.rtAccent),
          const SizedBox(width: 13),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: disabled ? RfColors.textSecondary : Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const Icon(Icons.chevron_right_rounded, size: 20, color: RfColors.textSecondary),
        ]),
      ),
    );
  }
}
