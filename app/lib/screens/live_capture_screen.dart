import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import 'package:native_camera_sound/native_camera_sound.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../services/camera_settings_service.dart';
import '../services/local_storage_service.dart';
import '../services/upload_service.dart';
import '../services/sync_queue_service.dart';
import '../services/sync_manager.dart';
import '../services/dnd_service.dart';
import '../services/file_naming_service.dart';
import '../utils/volume_button_service.dart';
import '../utils/image_processing.dart';
import '../widgets/rf_button.dart';
import 'barcode_save_popup.dart';
import 'verdict_bottom_sheet.dart';

/// Zoom level with label and position (0-1 range representing min to max zoom).
class ZoomLevel {
  final String label;
  final double position; // 0 = min zoom, 1 = max zoom
  const ZoomLevel(this.label, this.position);
}

/// Internal capture phases within the state machine.
enum CapturePhase {
  loading,
  recording,
  stopped,
  saving,
  complete,
  error,
}

class LiveCaptureScreen extends StatefulWidget {
  final CaptureMode mode;

  const LiveCaptureScreen({super.key, required this.mode});

  @override
  State<LiveCaptureScreen> createState() => _LiveCaptureScreenState();
}

class _LiveCaptureScreenState extends State<LiveCaptureScreen> with TickerProviderStateMixin {
  // ─── Camera ────────────────────────────────────────────────────────────
  CameraController? _camera;
  List<CameraDescription> _cameras = [];
  bool _cameraReady = false;

  // ─── Recording ─────────────────────────────────────────────────────────
  bool _isRecording = false;
  final _stopwatch = Stopwatch();
  Timer? _timerTick;

  // ─── Session state ─────────────────────────────────────────────────────
  CapturePhase _phase = CapturePhase.loading;
  final Map<String, dynamic> _session = {};

  // ─── Countdown ───────────────────────────────────────────────────────
  bool _showCountdown = false;
  int _countdownSeconds = 5;
  PhotoSide _nextPhotoSide = PhotoSide.front;
  Timer? _countdownTimer;

  // Zoom levels: label = displayed on button, position = actual camera zoom multiplier
  // position is used directly as setZoomLevel value (NOT normalized)
  static const List<ZoomLevel> _zoomLevels = [
    ZoomLevel('1×', 1.0),   // index 0 → actual camera zoom 1.0x
    ZoomLevel('2×', 2.0),  // index 1 → actual camera zoom 2.0x
    ZoomLevel('3×', 3.0),  // index 2 → actual camera zoom 3.0x
  ];
  int _currentZoomIndex = 0; // Default to 1× (index 0)

  double _minZoom = 1.0;
  double _maxZoom = 8.0;
  ResolutionPreset _resolution = ResolutionPreset.veryHigh;
  int _fps = 30;
  bool _micEnabled = false;
  bool _soundEnabled = true;
  bool _timestampOnPhotos = false;

  // ─── Temp photos (saved before order ID is known) ─────────────────────
  final Map<PhotoSide, String> _tempPhotoPaths = {};

  // ─── Save state ───────────────────────────────────────────────────────
  bool _isSaving = false;
  String? _errorMessage;

  // ─── Utilities ─────────────────────────────────────────────────────────
  final _localStorage = LocalStorageService();

  late AnimationController _focusAnimCtrl;
  late Animation<double> _focusAnim;
  bool _showFocus = false;
  double _focusX = 0, _focusY = 0;

  bool _audioUsedForRecording = false;  // Audio setting used for current recording
  bool _isCameraTransitioning = false;  // THE MUTEX LOCK — blocks re-entrant camera ops
  int? _previousDndFilter;              // Saved DND state, restored on recording stop

  // ─── Aspect ratio ──────────────────────────────────────────────────────
  // Width/height ratio (portrait orientation):
  //   _aspectFull (16:9 portrait) = 9/16 ≈ 0.5625  — no crop, fills phone screen
  //   _aspect34   (3:4 portrait)  = 3/4  = 0.75    — taller crop
  //   _aspect11   (1:1 square)    = 1.0            — square crop
  // Photos are cropped to this ratio after capture.
  // Video records native 16:9 (camera package limitation; FFmpeg crop unreliable).
  static const double _aspectFull = 9 / 16;
  static const double _aspect34 = 3 / 4;
  static const double _aspect11 = 1.0;
  double _aspectRatio = _aspectFull;
  bool get _isAspectCropped => (_aspectRatio - _aspectFull).abs() > 0.001;

  // Capture countdown duration from settings. 0 = manual capture mode.
  int _captureCountdownSec = 3;

  // ─── RT claim-photo flow state ────────────────────────────────────────
  bool _inClaimFlow = false;             // True during the 5-photo claim sequence
  bool _skipCurrentClaimPhoto = false;   // Skip the in-progress countdown
  Completer<bool>? _manualCaptureCompleter;  // For manual capture mode (countdown=0)

  // ─── Lifecycle ─────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    // ROOT-CAUSE FIX (2026-05-17): Lock device to portraitUp BEFORE camera
    // init. Without this, the camera plugin records videos using the sensor's
    // landscape orientation + missing/wrong rotation metadata, which makes
    // the saved MP4 play back stretched in the gallery (video_player computes
    // aspectRatio from raw sensor dims = 16/9 = 1.78 instead of portrait
    // 9/16 = 0.5625). Locking here forces the plugin to write proper
    // portrait dimensions + rotation flag, so playback fills correctly.
    SystemChrome.setPreferredOrientations(const [
      DeviceOrientation.portraitUp,
    ]);
    _focusAnimCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 600));
    _focusAnim = Tween(begin: 1.2, end: 0.9).animate(CurvedAnimation(parent: _focusAnimCtrl, curve: Curves.easeOut));
    _loadSettings();
    _setupVolumeButtons();
  }

  Future<void> _loadSettings() async {
    _resolution = await CameraSettingsService.getResolution();
    _fps = await CameraSettingsService.getFps();
    _micEnabled = await CameraSettingsService.getMicDefault();
    _soundEnabled = await CameraSettingsService.getSound();
    _timestampOnPhotos = await CameraSettingsService.getTimestampImage();
    _captureCountdownSec = await CameraSettingsService.getCaptureCountdown();
    _aspectRatio = await CameraSettingsService.getAspectDefault();
    if (mounted) setState(() {});
    _initCamera();
  }

  @override
  void dispose() {
    _timerTick?.cancel();
    _countdownTimer?.cancel();
    _focusAnimCtrl.dispose();
    _camera?.dispose();
    // Always release wakelock + restore system UI on exit, in case the
    // user backed out mid-recording without going through _stopRecording.
    _disableRecordingMode();
    VolumeButtonService().unregisterListener('live_capture_screen');
    // Restore all orientations so other app screens (gallery, settings)
    // remain free to rotate.
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    super.dispose();
  }

  void _setupVolumeButtons() {
    VolumeButtonService().registerListener('live_capture_screen', (event) {
      if (!mounted) return;
      // ROUTE GUARD: ignore volume events when another route (e.g. barcode
      // save popup) is on top. Without this guard, volume presses would
      // simultaneously trigger BOTH the popup's _scan() AND our handler's
      // _stopRecording()/_toggleMic(), causing the UI to hang.
      final route = ModalRoute.of(context);
      if (route != null && !route.isCurrent) {
        debugPrint('VolumeButtons: ignored — live_capture not current route');
        return;
      }
      if (_isSaving || _phase == CapturePhase.complete) return;
      if (event == 1) {
        // Volume up: skip countdown or stop recording
        if (_showCountdown) {
          _skipCountdown();
        } else if (_isRecording) {
          _stopRecording();
        }
      } else if (event == 2) {
        // Volume down: toggle mic
        _toggleMic();
      }
    });
  }

  // ─── Camera init ─────────────────────────────────────────────────────

  Future<void> _initCamera() async {
    // MUTEX LOCK: Reject if camera is already transitioning
    if (_isCameraTransitioning) {
      debugPrint('BLOCKED: _initCamera rejected — camera transitioning');
      return;
    }
    _isCameraTransitioning = true;

    try {
      // NOTE: Do NOT clear _errorMessage here — it preserves error state
      // from a previous failed init attempt so the UI can display it properly.
      // Only clear on a fresh cold-start init (checked via _camera == null).

      // Only clear error on fresh cold-start, not on re-init from modal return
      final isColdStart = _camera == null;
      if (isColdStart) {
        _errorMessage = null;
      }

      // CRITICAL: 300ms delay is REQUIRED before camera initialization.
      // Android camera hardware needs time to fully release after dispose().
      // Without this delay, availableCameras() returns stale list and initialize()
      // throws CameraException — causing the camera loop bug.
      await Future.delayed(const Duration(milliseconds: 300));
      if (!mounted) return;

      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        _setError('No camera found');
        return;
      }

      final cam = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      _camera = CameraController(cam, _resolution, enableAudio: _micEnabled, fps: _fps);
      debugPrint('Camera init: enableAudio=$_micEnabled, resolution=$_resolution, fps=$_fps');

      try {
        await _camera!.initialize();
        // Pin the camera's capture orientation to portraitUp. This guarantees
        // recorded video files get the correct rotation flag + portrait
        // dimensions in their MP4 header — otherwise the camera plugin can
        // record landscape and the gallery player stretches it.
        try {
          await _camera!.lockCaptureOrientation(DeviceOrientation.portraitUp);
        } catch (e) {
          debugPrint('lockCaptureOrientation skipped (non-fatal): $e');
        }
        _minZoom = await _camera!.getMinZoomLevel();
        _maxZoom = await _camera!.getMaxZoomLevel();
        if (mounted) {
          setState(() => _cameraReady = true);
          _startSession();
          // Apply default zoom (1x) to newly initialized camera
          _applyZoom();
      }
    } on CameraException catch (e) {
      // Camera disposed/busy while initializing — show retry path
      if (mounted) {
        setState(() {
          _errorMessage = 'Camera busy — tap retry';
          _phase = CapturePhase.error;
        });
      }
      debugPrint('CameraException in _initCamera: $e');
    } catch (e) {
      _setError('Camera error: $e');
    }
    } finally {
      _isCameraTransitioning = false;  // Release mutex lock
    }
  }

  Future<void> _reinitCamera() async {
    if (_isCameraTransitioning) return;  // MUTEX guard
    _timerTick?.cancel();
    await _camera?.dispose();
    setState(() { _cameraReady = false; _isRecording = false; });
    await _initCamera();
  }

  /// Re-initialize camera with a specific audio setting.
  /// Used after modal closes to restore camera with the same audio setting
  /// that was used during recording.
  Future<void> _initCameraWithAudio(bool enableAudio) async {
    // MUTEX LOCK: Reject if camera is already transitioning
    if (_isCameraTransitioning) {
      debugPrint('BLOCKED: _initCameraWithAudio rejected — camera transitioning');
      return;
    }
    _isCameraTransitioning = true;

    try {
      await Future.delayed(const Duration(milliseconds: 300));
      if (!mounted) return;

      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        _setError('No camera found');
        return;
      }

      final cam = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      _camera = CameraController(cam, _resolution, enableAudio: enableAudio, fps: _fps);

      try {
        await _camera!.initialize();
        // Lock capture orientation (see _initCamera for rationale).
        try {
          await _camera!.lockCaptureOrientation(DeviceOrientation.portraitUp);
        } catch (e) {
          debugPrint('lockCaptureOrientation skipped (non-fatal): $e');
        }
        _minZoom = await _camera!.getMinZoomLevel();
        _maxZoom = await _camera!.getMaxZoomLevel();
        if (mounted) {
          setState(() => _cameraReady = true);
          _startSession();
          _applyZoom();
        }
      } on CameraException catch (e) {
        // Camera disposed/busy while initializing — show retry path
        if (mounted) {
          setState(() {
            _errorMessage = 'Camera busy — tap retry';
            _phase = CapturePhase.error;
          });
        }
        debugPrint('CameraException in _initCameraWithAudio: $e');
      } catch (e) {
        _setError('Camera error: $e');
      }
    } finally {
      _isCameraTransitioning = false;  // Release mutex lock
    }
  }

  // ─── Session start ───────────────────────────────────────────────────

  void _startSession() {
    _session['sessionStartedAt'] = DateTime.now();
    // Don't auto-start — wait for user to tap capture button
    setState(() { _phase = CapturePhase.stopped; });
  }

  void _onCapturePressed() {
    // Manual-photo mode mid-countdown: the bottom button completes the capture.
    // This path is reached if the user has countdown=0 AND _showCountdown is
    // somehow active (e.g. RT claim flow). PK photo capture below does NOT
    // enter the overlay state any more.
    if (_showCountdown && _captureCountdownSec <= 0) {
      _countdownTimer?.cancel();
      _onManualCaptureTap();
      return;
    }

    if (_phase == CapturePhase.stopped && !_isRecording) {
      if (widget.mode == CaptureMode.pk) {
        // PK direct-capture flow.
        //
        // Old flow (removed):  Tap → overlay "Position FRONT facing" + wait
        //                       → Tap again → photo captures.
        //
        // New flow (this method): Tap → photo captures IMMEDIATELY.
        // The instruction is shown as a persistent banner on the main
        // screen (see _buildPkInstructionBanner), so the user already knows
        // which side to capture before tapping.
        if (_captureCountdownSec > 0) {
          // Legacy: user explicitly chose an auto-countdown in settings →
          // honor it via the overlay flow.
          _startPhotoSequence();
        } else {
          _capturePkPhotoDirect();
        }
      } else {
        // RT mode: video starts immediately, no photo sequence
        _startRecording();
      }
    }
  }

  /// Re-entrancy guard for [_capturePkPhotoDirect]. `takePicture` can take
  /// 400-800ms on mid-range Android — a rapid double-tap would otherwise
  /// fire two captures and corrupt `_tempPhotoPaths`.
  bool _photoCaptureInProgress = false;

  /// PK direct-capture: take a still immediately. Determines what to do
  /// from the state of [_tempPhotoPaths]:
  ///   - front missing  → capture front photo
  ///   - back missing   → capture back photo
  ///   - both captured  → start video recording
  Future<void> _capturePkPhotoDirect() async {
    if (_camera == null || !_cameraReady || _isCameraTransitioning) return;
    if (_photoCaptureInProgress) return;  // block double-tap during capture
    final hasFront = _tempPhotoPaths.containsKey(PhotoSide.front);
    final hasBack = _tempPhotoPaths.containsKey(PhotoSide.back);
    if (hasFront && hasBack) {
      // Both photos done — third tap = start video
      _startRecording();
      return;
    }
    _photoCaptureInProgress = true;
    try {
      _nextPhotoSide = hasFront ? PhotoSide.back : PhotoSide.front;
      setState(() { _phase = CapturePhase.recording; });
      await _onPhotoCountdownComplete();
    } finally {
      _photoCaptureInProgress = false;
    }
  }

  /// Returns the instruction text + icon to display in the PK banner.
  /// Computed from _tempPhotoPaths so it's always in sync with progress.
  ({String text, IconData icon}) _pkInstructionFor() {
    final hasFront = _tempPhotoPaths.containsKey(PhotoSide.front);
    final hasBack = _tempPhotoPaths.containsKey(PhotoSide.back);
    if (!hasFront) {
      return (text: 'Position FRONT facing camera, then tap', icon: Icons.crop_portrait);
    }
    if (!hasBack) {
      return (text: 'Now position BACK facing camera, then tap', icon: Icons.flip_to_back);
    }
    return (text: 'Photos done — tap to start video recording', icon: Icons.videocam_rounded);
  }

  // ─── Photo sequence (PK mode) ──────────────────────────────────────────

  void _startPhotoSequence() {
    // Start with front photo, honoring user's countdown setting (0 = manual)
    _nextPhotoSide = PhotoSide.front;
    _showCountdownForPhoto('Position FRONT facing', _captureCountdownSec);
  }

  void _showCountdownForPhoto(String instruction, int seconds) {
    _countdownSeconds = seconds;
    setState(() { _showCountdown = true; _phase = CapturePhase.recording; });
    _countdownTimer?.cancel();
    if (seconds <= 0) {
      // Manual capture mode: no timer. User taps CAPTURE button in overlay
      // which calls _onPhotoCountdownComplete().
      return;
    }
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) { timer.cancel(); return; }
      setState(() {
        _countdownSeconds--;
        if (_countdownSeconds <= 0) {
          timer.cancel();
          _onPhotoCountdownComplete();
        }
      });
      if (_countdownSeconds > 0 && _soundEnabled) {
        HapticFeedback.selectionClick();
      }
    });
  }

  Future<void> _onPhotoCountdownComplete() async {
    HapticFeedback.mediumImpact();
    if (_soundEnabled) NativeCameraSound.playShutter();

    // Direct-tap mode = user has countdown=0 AND we're not in the RT claim
    // photo flow (which has its own manual handling). In direct mode the
    // post-capture behavior is "go back to idle so the banner updates"; the
    // user explicitly taps again for the next photo / video start.
    final isDirectMode = _captureCountdownSec <= 0 && !_inClaimFlow;

    try {
      final xFile = await _camera!.takePicture();
      final savedPath = await _processAndSaveTempPhoto(xFile);
      _tempPhotoPaths[_nextPhotoSide] = savedPath;

      if (_nextPhotoSide == PhotoSide.front) {
        // Front photo just landed → next is back. In direct mode we return
        // to idle so the user can frame the back photo + tap once to capture
        // it. In countdown mode we auto-cycle.
        _nextPhotoSide = PhotoSide.back;
        setState(() {
          _showCountdown = false;
          _phase = CapturePhase.stopped;  // back to idle so banner refreshes
        });
        if (isDirectMode) return;  // user will tap again for back photo
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) _showCountdownForPhoto('Position BACK facing', _captureCountdownSec);
        });
      } else {
        // BACK photo just landed → both photos done. Auto-start video
        // recording (REGARDLESS of direct vs countdown mode) per user
        // request: "pk mode mei 2 images click hone ke baad apne aap video
        // start hona chahiye". Eliminates one tap from the PK flow — the
        // capture button taps are: 1) front, 2) back, 3) recording auto-
        // begins immediately. User just taps STOP when done packing.
        setState(() {
          _showCountdown = false;
          _phase = CapturePhase.stopped;
        });
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) _startRecording();
        });
      }
    } catch (e) {
      debugPrint('Photo capture failed: $e');
      if (widget.mode == CaptureMode.pk && _nextPhotoSide == PhotoSide.front) {
        // Try back photo
        _nextPhotoSide = PhotoSide.back;
        setState(() {
          _showCountdown = false;
          _phase = CapturePhase.stopped;
        });
        if (isDirectMode) return;
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) _showCountdownForPhoto('Position BACK facing', _captureCountdownSec);
        });
      } else {
        setState(() {
          _showCountdown = false;
          _phase = CapturePhase.stopped;
        });
        if (isDirectMode) return;
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) _startRecording();
        });
      }
    }
  }

  // ─── Recording ─────────────────────────────────────────────────────────

  /// Re-entrancy guard for [_startRecording]. The DND prompt (line 539) can
  /// pause this method for seconds; without this flag a rapid double-tap
  /// fires `startVideoRecording()` twice and the camera plugin throws.
  bool _startingRecording = false;

  Future<void> _startRecording() async {
    if (_camera == null || !_cameraReady) return;
    if (_isCameraTransitioning) return;  // MUTEX guard
    if (_isRecording) return;            // already recording — block duplicate
    if (_startingRecording) return;      // start-in-progress — block double-tap
    _startingRecording = true;

    try {
      // First-time DND prompt. If user opts to go to system settings, the
      // method returns false and we abort this recording attempt — recording
      // can't proceed while the app is backgrounded. They tap record again
      // after granting permission.
      final shouldProceed = await _maybePromptDndPermission();
      if (!shouldProceed || !mounted) return;

      _session['videoStartedAt'] = DateTime.now();
      _stopwatch.reset();
      _stopwatch.start();
      _timerTick?.cancel();
      _timerTick = Timer.periodic(const Duration(seconds: 1), (_) { if (mounted) setState(() {}); });

      if (_soundEnabled) NativeCameraSound.playStartRecord();

      try {
        // Save audio setting for re-init after modal closes
        _audioUsedForRecording = _micEnabled;
        // Guard against camera being disposed while we awaited DND.
        if (_camera == null) {
          _stopwatch.stop();
          return;
        }
        await _camera!.startVideoRecording();
        if (!mounted) return;
        setState(() { _isRecording = true; _phase = CapturePhase.recording; });
        // Engage recording-mode: screen stays on, system bars hidden
        await _enableRecordingMode();
      } catch (e) {
        _stopwatch.stop();
        _setError('Failed to start recording: $e');
      }
    } finally {
      _startingRecording = false;
    }
  }

  /// One-time DND-access prompt. Returns true if recording should proceed,
  /// false if the user opted to go to settings (recording aborts; they tap
  /// record again when they're back).
  ///
  /// "Skip" choice is sticky (won't re-prompt). "Grant" choice is NOT sticky —
  /// if user comes back without enabling, next record attempt re-prompts so
  /// they don't get stuck.
  Future<bool> _maybePromptDndPermission() async {
    if (!mounted) return true;
    try {
      // Already granted in system settings? proceed silently.
      final granted = await DndService.isPermissionGranted();
      if (granted) return true;

      // Previously tapped Skip? proceed without DND, don't re-prompt.
      final prefs = await SharedPreferences.getInstance();
      final skipped = prefs.getBool('dnd_prompt_skipped') ?? false;
      if (skipped) return true;

      if (!mounted) return true;
      final choice = await showDialog<bool>(
        context: context,
        barrierDismissible: true,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF161B22),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(children: [
            Icon(Icons.do_not_disturb_on_rounded, color: Color(0xFFFFA657), size: 22),
            SizedBox(width: 10),
            Text('Silence interruptions?', style: TextStyle(color: Colors.white)),
          ]),
          content: const Text(
            'Grant Do Not Disturb access so RepairFully can mute notifications, '
            'ringer, and non-urgent calls while you\'re recording. Auto-restores '
            'your previous settings when you stop.\n\n'
            'You can change this anytime in your phone\'s settings.',
            style: TextStyle(color: Color(0xFF8B949E), fontSize: 13),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Skip', style: TextStyle(color: Colors.white54)),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Grant', style: TextStyle(color: Color(0xFFFFA657), fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      );

      if (choice == true) {
        // User chose Grant → open settings → ABORT this recording attempt.
        // Recording can't proceed while the app is backgrounded; user must
        // come back and tap record again. We do NOT mark "asked" so they
        // won't get stuck if they back out without granting.
        await DndService.openSettings();
        if (mounted) {
          ScaffoldMessenger.of(context).clearSnackBars();
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: const Row(children: [
              Icon(Icons.touch_app, color: Color(0xFFFFA657), size: 18),
              SizedBox(width: 8),
              Expanded(child: Text('Toggle RepairFully ON in DND access, then come back and tap record')),
            ]),
            duration: const Duration(seconds: 5),
            backgroundColor: Colors.black87,
            behavior: SnackBarBehavior.floating,
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 100),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ));
        }
        return false;  // Abort: don't start recording in background
      }

      // User chose Skip → remember it so we never re-prompt
      await prefs.setBool('dnd_prompt_skipped', true);
      return true;
    } catch (e) {
      debugPrint('_maybePromptDndPermission failed (non-fatal): $e');
      return true;
    }
  }

  /// Engage all recording-time guards so the user isn't interrupted:
  ///   - Wakelock — prevents screen-off / sleep
  ///   - Immersive sticky — hides status + nav bars
  ///   - DND (priority mode) — silences notifications, ringer, and non-priority
  ///     calls during recording. Saves the previous DND state so we can restore
  ///     it exactly when recording stops. Silently no-ops if user hasn't
  ///     granted DND permission yet (offered as one-time prompt elsewhere).
  Future<void> _enableRecordingMode() async {
    try {
      await WakelockPlus.enable();
      await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

      // Save current filter so _disableRecordingMode can restore it exactly,
      // then switch to priority-only (silences notifications + ringer but
      // still lets through priority calls/messages — safer than total NONE).
      final granted = await DndService.isPermissionGranted();
      if (granted) {
        _previousDndFilter = await DndService.getFilter();
        await DndService.setFilter(DndService.filterPriority);
        debugPrint('DND: switched to priority (was: $_previousDndFilter)');
      } else {
        _previousDndFilter = null;
      }
    } catch (e) {
      debugPrint('enableRecordingMode failed (non-fatal): $e');
    }
  }

  /// Release recording-mode guards. Called from _stopRecording and dispose().
  Future<void> _disableRecordingMode() async {
    try {
      await WakelockPlus.disable();
      await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);

      if (_previousDndFilter != null) {
        await DndService.setFilter(_previousDndFilter!);
        debugPrint('DND: restored to filter $_previousDndFilter');
        _previousDndFilter = null;
      }
    } catch (e) {
      debugPrint('disableRecordingMode failed (non-fatal): $e');
    }
  }

  Future<void> _stopRecording() async {
    if (!_isRecording) return;
    _timerTick?.cancel();
    _stopwatch.stop();
    _countdownTimer?.cancel();
    if (_soundEnabled) NativeCameraSound.playStopRecord();

    try {
      // Guard against camera disposal racing with the stop call. If the
      // user backed out of the screen while we were waiting for the stop
      // tap, `_camera` may already be null — without this check we'd
      // throw a NullPointerException instead of failing gracefully.
      if (_camera == null) {
        if (mounted) {
          setState(() { _isRecording = false; _phase = CapturePhase.stopped; });
        }
        return;
      }
      final xfile = await _camera!.stopVideoRecording();
      _session['videoStoppedAt'] = DateTime.now();
      _session['videoDurationSeconds'] = _stopwatch.elapsed.inSeconds;

      // Validate the recording before saving as a draft — a tap-START + immediate-tap-STOP
      // produces a 0-byte file that clutters drafts/ and breaks save later. Treat as failed
      // recording, discard the temp file, show user a toast, stay on camera screen.
      final tempFile = File(xfile.path);
      int fileSize = 0;
      try { fileSize = await tempFile.length(); } catch (_) {}
      final tooShort = _stopwatch.elapsed.inMilliseconds < 1000;
      if (fileSize < 50000 || tooShort) {
        debugPrint('Recording too short / empty (${fileSize}B, ${_stopwatch.elapsed.inMilliseconds}ms) — discarding');
        try { await tempFile.delete(); } catch (_) {}
        // ROLLBACK PK PHOTOS — the user's front/back photos were captured
        // BEFORE recording started. If we keep them while discarding the
        // video, the next recording attempt would promote them to disk
        // alongside the new video, mixing two attempts. Per Mahika audit
        // 2026-05-17 (edge case #7), clear them so the user re-frames a
        // clean PK session from scratch.
        for (final p in _tempPhotoPaths.values) {
          try { await File(p).delete(); } catch (_) {}
        }
        _tempPhotoPaths.clear();
        _nextPhotoSide = PhotoSide.front;  // reset PK sequence
        await _disableRecordingMode();
        if (mounted) {
          setState(() { _isRecording = false; _showCountdown = false; _phase = CapturePhase.stopped; });
          ScaffoldMessenger.of(context).clearSnackBars();
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: const Row(children: [
              Icon(Icons.error_outline, color: Color(0xFFFF7B72), size: 18),
              SizedBox(width: 8),
              Expanded(child: Text('Recording too short — re-capture from the beginning')),
            ]),
            duration: const Duration(milliseconds: 2400),
            backgroundColor: Colors.black87,
          ));
        }
        return;  // stay on camera, user can retry
      }

      // CRITICAL: Save valid video to drafts folder IMMEDIATELY.
      // The video file must NEVER be lost — even if the user cancels the save
      // flow, the app crashes, or storage runs out later. The draft is in the
      // user's persistent storage (sibling of orders/), not Android's temp dir
      // (which gets cleaned up). _saveSession() promotes the draft to the
      // order folder once the order ID is known.
      final draftPath = await _localStorage.saveDraftVideo(xfile, widget.mode);
      _session['videoPath'] = draftPath;
      _session['isDraft'] = true;
      debugPrint('Video saved to drafts: $draftPath');

      // Release wakelock + restore system UI now that recording is done
      await _disableRecordingMode();

      // Fully dispose camera before modal opens — modal uses its own camera
      await _camera?.dispose();
      _camera = null;
      _cameraReady = false;
      setState(() { _isRecording = false; _showCountdown = false; _phase = CapturePhase.stopped; });
      _openBarcodePopup();
    } catch (e) {
      _setError('Failed to stop recording: $e');
    }
  }

  // ─── Manual capture (used when Photo Countdown setting = Off) ─────

  /// Wait for the user to tap the CAPTURE button (or Skip).
  /// Returns true if captured, false if skipped.
  Future<bool> _waitForManualCapture() async {
    _manualCaptureCompleter = Completer<bool>();
    final result = await _manualCaptureCompleter!.future;
    _manualCaptureCompleter = null;
    return result;
  }

  /// Triggered when user taps CAPTURE button in the manual overlay.
  /// PK mode: fires _onPhotoCountdownComplete. RT claim: completes the wait.
  void _onManualCaptureTap() {
    if (_inClaimFlow) {
      if (_manualCaptureCompleter != null && !_manualCaptureCompleter!.isCompleted) {
        _manualCaptureCompleter!.complete(true);
      }
    } else {
      // PK flow — same path as countdown completion
      _countdownTimer?.cancel();
      _onPhotoCountdownComplete();
    }
  }

  /// Triggered when user taps Skip button during manual capture (claim flow only).
  void _onSkipManualCapture() {
    _skipCurrentClaimPhoto = true;
    if (_manualCaptureCompleter != null && !_manualCaptureCompleter!.isCompleted) {
      _manualCaptureCompleter!.complete(false);
    }
    setState(() => _showCountdown = false);
  }

  // ─── Skip countdown (volume-up shortcut, PK mode only) ──────────────

  void _skipCountdown() {
    _countdownTimer?.cancel();
    // PK photo countdown: trigger capture immediately
    if (widget.mode == CaptureMode.pk && _showCountdown) {
      _onPhotoCountdownComplete();
      return;
    }
    // RT claim flow uses fixed-duration manual timers; ignore skip
  }

  Future<String> _processAndSaveTempPhoto(XFile xFile) async {
    final source = File(xFile.path);
    // Save to drafts/ (persistent storage) — NOT temp dir. Photos captured
    // before video starts (PK front/back) must survive cancellation, crashes,
    // and OS temp-dir cleanup. Watermark is applied later in
    // LocalStorageService.savePhoto() once the order ID is known.
    final draftPath = await _localStorage.saveDraftPhoto(source, widget.mode, _nextPhotoSide);
    final draft = File(draftPath);

    // Apply aspect-ratio center crop if user picked non-default ratio
    if (_isAspectCropped) {
      await ImageProcessingUtils.cropToAspectRatio(draft, _aspectRatio);
    }
    return draft.path;
  }

  // ─── Mic toggle ───────────────────────────────────────────────────────

  Future<void> _toggleMic() async {
    if (_isRecording) return;          // Don't toggle mid-recording
    if (_isCameraTransitioning) return; // Don't toggle mid-init (button is disabled in UI)

    _micEnabled = !_micEnabled;
    await CameraSettingsService.setMicDefault(_micEnabled);
    setState(() {});  // Flip the icon/label immediately

    // Tear down current controller, then re-init. enableAudio is baked into
    // the controller at construction — we MUST replace the controller to apply
    // the new audio state.
    try {
      _timerTick?.cancel();
      await _camera?.dispose();
    } catch (e) {
      debugPrint('_toggleMic dispose failed: $e');
    }
    _camera = null;
    _cameraReady = false;
    if (mounted) setState(() {});
    await _initCamera();  // builds new controller with current _micEnabled
  }

  // ─── Zoom ─────────────────────────────────────────────────────────────

  /// Set zoom by level index (0=ultra, 1=1x, 2=2x, 3=3x)
  void _setZoomByIndex(int index) {
    if (index < 0 || index >= _zoomLevels.length) return;
    _currentZoomIndex = index;
    _applyZoom();
  }

  /// Cycle through zoom levels
  void _cycleZoom() {
    _currentZoomIndex = (_currentZoomIndex + 1) % _zoomLevels.length;
    _applyZoom();
  }

  /// Apply current zoom level to camera
  void _applyZoom() {
    if (_camera == null || !_cameraReady) return;
    final level = _zoomLevels[_currentZoomIndex];
    // level.position is the actual camera zoom multiplier (1.0x, 2.0x, 3.0x)
    final targetZoom = level.position.clamp(_minZoom, _maxZoom);
    _camera!.setZoomLevel(targetZoom);
    setState(() {});
  }

  /// Handle pinch-to-zoom gesture
  void _handleScaleUpdate(ScaleUpdateDetails details) {
    if (_camera == null || !_cameraReady) return;

    // details.scale is the ratio of current pinch distance to initial pinch distance
    // We map it to our zoom levels:
    // scale < 1.5 → 1× (zoom out or slight zoom in)
    // scale 1.5–2.5 → 2×
    // scale > 2.5 → 3×
    final scale = details.scale;

    if (scale < 1.5) {
      if (_currentZoomIndex != 0) _setZoomByIndex(0);
    } else if (scale < 2.5) {
      if (_currentZoomIndex != 1) _setZoomByIndex(1);
    } else {
      if (_currentZoomIndex != 2) _setZoomByIndex(2);
    }
  }

  void _onTapFocus(TapUpDetails details) async {
    if (_camera == null || !_cameraReady) return;
    final renderBox = context.findRenderObject() as RenderBox?;
    if (renderBox == null) return;

    try {
      final size = renderBox.size;
      final x = (details.localPosition.dx / size.width).clamp(0.0, 1.0);
      final y = (details.localPosition.dy / size.height).clamp(0.0, 1.0);
      await _camera!.setFocusPoint(Offset(x, y));
      await _camera!.setExposurePoint(Offset(x, y));
    } catch (_) {}

    setState(() { _showFocus = true; _focusX = details.localPosition.dx; _focusY = details.localPosition.dy; });
    _focusAnimCtrl.forward(from: 0);
    Future.delayed(const Duration(seconds: 2), () { if (mounted) setState(() => _showFocus = false); });
  }

  // ─── Barcode popup ─────────────────────────────────────────────────────

  void _openBarcodePopup() async {
    // Camera was disposed by _stopRecording(). BarcodeSavePopup runs its
    // own camera. We use a full-screen route (not bottom sheet) so the
    // label-scan UI gets the entire screen — bigger camera, AppBar with
    // SAVE button always visible without scrolling.
    final result = await Navigator.of(context).push<Map<String, String?>>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => BarcodeSavePopup(mode: widget.mode),
      ),
    );

    if (result == null || result['orderId'] == null) {
      // User cancelled — wait 500ms for hardware to fully release, then reinit
      if (mounted) setState(() => _phase = CapturePhase.stopped);
      await Future.delayed(const Duration(milliseconds: 500));
      await _initCameraWithAudio(_audioUsedForRecording);
      return;
    }

    _session['orderId'] = result['orderId'];
    _session['awb'] = result['awb'];

    if (widget.mode == CaptureMode.rt) {
      _openVerdictSheet();
    } else {
      _saveSession();
    }
  }

  // ─── Verdict sheet ─────────────────────────────────────────────────────

  void _openVerdictSheet() async {
    final verdict = await showModalBottomSheet<QCVerdict>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => VerdictBottomSheet(orderId: _session['orderId']),
    );

    if (verdict == null) {
      if (mounted) setState(() => _phase = CapturePhase.stopped);
      await _initCameraWithAudio(_audioUsedForRecording);
      return;
    }

    _session['verdict'] = verdict;

    // OK verdict → save directly, no claim photos needed.
    if (verdict == QCVerdict.ok) {
      _saveSession();
      return;
    }

    // Non-OK verdict (DAMAGED / DIFFERENT / DAMAGED+DIFFERENT) → run 5-photo
    // claim sequence before saving. Photos: label → contents → front → back → serial(optional).
    await _runClaimPhotoSequence();
    if (!mounted) return;
    _saveSession();
  }

  // ─── RT claim-photo flow ─────────────────────────────────────────────

  /// Re-inits camera (audio off for photos) and runs the 5-photo claim sequence.
  /// Each photo has a 3-second countdown with a Skip button below — skippable.
  /// If camera fails to init, saves what we have without photos.
  Future<void> _runClaimPhotoSequence() async {
    // Restore UI to capture mode + re-init camera (no audio needed for photos)
    if (mounted) setState(() => _phase = CapturePhase.stopped);
    await _initCameraWithAudio(false);
    if (!mounted) return;
    if (_camera == null || !_cameraReady) {
      debugPrint('Claim photo flow: camera unavailable, skipping photos');
      return;
    }

    _inClaimFlow = true;
    try {
      // 5-step sequence. (side, instruction)
      const sequence = <(PhotoSide, String)>[
        (PhotoSide.label, 'Position RETURN LABEL in frame'),
        (PhotoSide.contents, 'Position package CONTENTS in frame'),
        (PhotoSide.front, 'Position product FRONT facing up'),
        (PhotoSide.back, 'Position product BACK facing up'),
        (PhotoSide.serial, 'Capture SERIAL / FPC closeup (optional)'),
      ];

      for (final (side, _) in sequence) {
        if (!mounted || _camera == null || !_cameraReady) return;
        await _captureClaimPhoto(side);
      }
    } finally {
      _inClaimFlow = false;
    }
  }

  /// Single photo with countdown overlay + inline Skip button.
  /// Honors _captureCountdownSec from settings (0 = manual; 3/5/10 = auto).
  /// User can tap Skip → photo skipped, sequence continues.
  Future<void> _captureClaimPhoto(PhotoSide side) async {
    if (_camera == null || !_cameraReady || !mounted) return;

    _skipCurrentClaimPhoto = false;
    setState(() {
      _nextPhotoSide = side;
      _showCountdown = true;
      _countdownSeconds = _captureCountdownSec;
      _phase = CapturePhase.recording;
    });

    if (_captureCountdownSec <= 0) {
      // Manual capture mode — wait for user to tap CAPTURE or Skip button
      final captured = await _waitForManualCapture();
      if (!mounted || !captured || _skipCurrentClaimPhoto) {
        if (mounted) setState(() => _showCountdown = false);
        if (!captured) debugPrint('Claim photo skipped (manual): ${side.name}');
        return;
      }
    } else {
      // Auto countdown — checks skip flag each tick
      for (int i = _captureCountdownSec; i > 0; i--) {
        if (!mounted || _skipCurrentClaimPhoto) break;
        setState(() => _countdownSeconds = i);
        if (_soundEnabled) HapticFeedback.selectionClick();
        await Future.delayed(const Duration(seconds: 1));
      }
      if (!mounted) return;
      setState(() => _showCountdown = false);
      if (_skipCurrentClaimPhoto) {
        debugPrint('Claim photo skipped (countdown): ${side.name}');
        return;
      }
    }

    HapticFeedback.mediumImpact();
    if (_soundEnabled) NativeCameraSound.playShutter();

    try {
      final xFile = await _camera!.takePicture();
      final savedPath = await _processAndSaveTempPhoto(xFile);
      _tempPhotoPaths[side] = savedPath;
      debugPrint('Claim photo captured: ${side.name} → $savedPath');
    } catch (e) {
      debugPrint('Claim photo capture failed for ${side.name}: $e');
    }

    // Brief pause between photos so user can reposition
    if (mounted) await Future.delayed(const Duration(milliseconds: 600));
  }

  // ─── Save ─────────────────────────────────────────────────────────────

  Future<void> _saveSession() async {
    if (_isSaving) return;
    // Camera already disposed in _stopRecording — no need to dispose again
    setState(() { _isSaving = true; _phase = CapturePhase.saving; });

    try {
      final orderId = _session['orderId'] as String?;
      if (orderId == null) throw Exception('No order ID - barcode not captured');

      final videoPath = _session['videoPath'] as String?;
      if (videoPath == null) throw Exception('No video recorded');

      // Use XFile for video file operations
      final videoXFile = XFile(videoPath);

      // Check if video file exists
      final videoFile = File(videoPath);
      if (!await videoFile.exists()) {
        throw Exception('Video file missing at: $videoPath');
      }

      // Sanity check — should never trigger now that _stopRecording rejects
      // sub-50KB recordings up front, but keep as a defense-in-depth check
      // in case something corrupts a draft between save-stop and save-promote.
      final videoSize = await videoFile.length();
      if (videoSize < 50000) {
        throw Exception('Video recording was empty. Please re-record');
      }

      // Move video to final location.
      // Most paths produce a draft (see _stopRecording) — promote it via rename.
      // Legacy path: fall back to the copy-based saveVideo if no draft marker.
      String savedVideoPath;
      final isDraft = _session['isDraft'] as bool? ?? false;
      try {
        if (isDraft) {
          savedVideoPath = await _localStorage.promoteDraftVideo(
            videoPath, orderId, widget.mode,
          );
        } else {
          savedVideoPath = await _localStorage.saveVideo(
            orderId, XFile(videoPath), widget.mode,
          );
        }
      } catch (e) {
        throw Exception('Failed to save video: $e');
      }

      // Move all captured photos from drafts/ to the order folder.
      // Photos were saved to drafts/ at capture time (data-loss protection);
      // here we watermark them in-place, then atomically rename into the
      // order folder. Much cheaper than copy-on-save.
      final Map<PhotoSide, String> finalPaths = {};
      for (final side in _tempPhotoPaths.keys) {
        final draftPhotoPath = _tempPhotoPaths[side]!;
        if (await File(draftPhotoPath).exists()) {
          try {
            // Apply watermark (order ID + datetime) — respects user setting
            await ImageProcessingUtils.processPhoto(
              File(draftPhotoPath),
              orientation: CustomOrientation.portraitUp,
              addTimestamp: _timestampOnPhotos,
              prefix: '${widget.mode.name.toUpperCase()}-$orderId',
            );
            // Promote (rename) to order folder
            finalPaths[side] = await _localStorage.promoteDraftPhoto(
              draftPhotoPath, orderId, widget.mode, side,
            );
          } catch (e) {
            debugPrint('Failed to promote photo $side: $e');
            // Continue — partial save is acceptable; photo stays in drafts
          }
        }
      }

      // Build session
      final session = CaptureSession(
        orderId: orderId,
        awb: _session['awb'] as String?,
        mode: widget.mode,
        sessionStartedAt: _session['sessionStartedAt'] as DateTime? ?? DateTime.now(),
        videoStartedAt: _session['videoStartedAt'] as DateTime?,
        videoStoppedAt: _session['videoStoppedAt'] as DateTime?,
        videoDurationSeconds: _session['videoDurationSeconds'] as int?,
        videoPath: savedVideoPath,
        frontPhotoPath: finalPaths[PhotoSide.front],
        backPhotoPath: finalPaths[PhotoSide.back],
        labelPhotoPath: finalPaths[PhotoSide.label],
        contentsPhotoPath: finalPaths[PhotoSide.contents],
        serialPhotoPath: finalPaths[PhotoSide.serial],
        verdict: _session['verdict'] as QCVerdict?,
      );

      await _localStorage.writeMetaJson(session);

      // Enqueue to persistent queue FIRST — this is the source of truth.
      // If the immediate upload below succeeds, SyncManager / UploadService
      // will remove it on success. If it fails (offline, network blip, app
      // killed mid-upload), the queue retries via SyncManager every 2 min
      // and on next app open.
      final orderFolder = await _localStorage.getOrderFolder(orderId);
      await SyncQueueService.enqueue(orderId, orderFolder.path);

      // Kick off immediate upload — fire-and-forget. Does not block the save
      // flow; user goes straight back to the camera. Result surfaces via
      // a second toast (offline / failed). Success is silent.
      // ignore: unawaited_futures
      UploadService.uploadSession(session: session, orderFolderPath: orderFolder.path)
          .then((r) async {
        if (r.status == UploadStatus.success) {
          await SyncQueueService.remove(orderId);
        }
        // Trigger a SyncManager status emit so banners refresh
        // ignore: unawaited_futures
        SyncManager.syncNow();
        if (!mounted) return;
        if (r.status == UploadStatus.offline) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: const Row(children: [
              Icon(Icons.wifi_off, color: Color(0xFFFF7B72), size: 18),
              SizedBox(width: 8),
              Expanded(child: Text('Backend offline — saved locally, upload pending')),
            ]),
            duration: const Duration(milliseconds: 2200),
            backgroundColor: Colors.black87,
            behavior: SnackBarBehavior.floating,
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 100),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ));
        } else if (r.status == UploadStatus.failed) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Row(children: [
              const Icon(Icons.error_outline, color: Color(0xFFFF7B72), size: 18),
              const SizedBox(width: 8),
              Expanded(child: Text('Upload failed — retry from Gallery. ${r.error ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis)),
            ]),
            duration: const Duration(milliseconds: 3000),
            backgroundColor: Colors.black87,
            behavior: SnackBarBehavior.floating,
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 100),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ));
        }
        // Success: silent — Gallery shows the "Uploaded" badge.
      });

      if (mounted) {
        _showSavedToast(orderId);
        await _resetForNextCapture();
      }
    } catch (e, st) {
      debugPrint('Save failed: $e');
      debugPrint('Stack trace: $st');
      // Strip technical prefixes / clean up underlying-exception text for the
      // user-facing error overlay. The raw $e goes to debugPrint above for diagnostics.
      final clean = '$e'
          .replaceFirst('Exception: ', '')
          .replaceFirst(RegExp(r' - recording may have failed'), '')
          .replaceFirst(RegExp(r'Video file too small \(\d+B\)'), 'Video recording was empty. Please re-record');
      _setError(clean);
    }
  }

  void _setError(String msg) {
    debugPrint(msg);
    if (mounted) setState(() { _errorMessage = msg; _phase = CapturePhase.error; _isSaving = false; });
  }

  /// Brief, non-blocking confirmation that save completed.
  void _showSavedToast(String orderId) {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(
      content: Row(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.check_circle, color: Color(0xFF3FB950), size: 18),
        const SizedBox(width: 10),
        Text('Saved · $orderId', style: const TextStyle(color: Colors.white, fontSize: 13)),
      ]),
      duration: const Duration(milliseconds: 1600),
      backgroundColor: Colors.black87,
      behavior: SnackBarBehavior.floating,
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 100),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ));
  }

  /// Reset all session state and re-init camera for the next capture.
  /// Stays on this screen instead of popping to home.
  Future<void> _resetForNextCapture() async {
    _timerTick?.cancel();
    _countdownTimer?.cancel();
    _stopwatch.reset();
    setState(() {
      _session.clear();
      _tempPhotoPaths.clear();
      _isRecording = false;
      _isSaving = false;
      _showCountdown = false;
      _countdownSeconds = 5;
      _nextPhotoSide = PhotoSide.front;
      _errorMessage = null;
      _camera = null;
      _cameraReady = false;
      _phase = CapturePhase.loading;
    });
    await _initCamera();
  }

  // ─── Helpers ─────────────────────────────────────────────────────────

  String get _elapsedLabel {
    final s = _stopwatch.elapsed.inSeconds;
    return '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';
  }

  String get _countdownInstruction {
    if (widget.mode == CaptureMode.pk) {
      return _nextPhotoSide == PhotoSide.front
          ? 'Position product FRONT facing up'
          : 'Position product BACK facing up';
    } else {
      switch (_nextPhotoSide) {
        case PhotoSide.label: return 'Position RETURN LABEL in frame';
        case PhotoSide.contents: return 'Position package CONTENTS in frame';
        case PhotoSide.front: return 'Position product FRONT facing up';
        case PhotoSide.back: return 'Position product BACK facing up';
        case PhotoSide.serial: return 'Capture SERIAL / FPC closeup';
      }
    }
  }

  void _close() {
    if (_isRecording) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Discard recording?'),
          content: const Text('Recording is in progress. Close anyway?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            TextButton(
              onPressed: () { Navigator.pop(ctx); Navigator.pop(context); },
              child: const Text('Discard', style: TextStyle(color: Colors.red)),
            ),
          ],
        ),
      );
    } else {
      Navigator.pop(context);
    }
  }

  // ─── UI ─────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final isPk = widget.mode == CaptureMode.pk;
    final accent = isPk ? RfColors.pkAccent : RfColors.rtAccent;

    // Terminal phases — render overlay without requiring camera
    if (_phase == CapturePhase.saving) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(child: Stack(children: [_buildSavingOverlay()])),
      );
    }
    if (_phase == CapturePhase.complete) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(child: Stack(children: [_buildCompleteOverlay(accent)])),
      );
    }
    if (_phase == CapturePhase.error) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(child: Stack(children: [_buildErrorOverlay()])),
      );
    }

    // Camera-loading screen — only during cold start or active transition
    if (_camera == null || !_cameraReady) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const CircularProgressIndicator(color: Colors.white38),
            const SizedBox(height: 16),
            const Text('Starting camera...', style: TextStyle(color: Colors.white54, fontSize: 13)),
          ]),
        ),
      );
    }

    // Hide camera preview during non-recording states — prevents stale preview hang
    final showPreview = _phase == CapturePhase.recording || _phase == CapturePhase.stopped;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            // Camera preview — only shown when active
            if (showPreview)
              Positioned.fill(
                child: GestureDetector(
                  onScaleUpdate: _handleScaleUpdate,
                  onTapUp: _onTapFocus,
                  child: _buildCroppedPreview(),
                ),
              ),

            // Focus ring
            if (_showFocus)
              Positioned(
                left: _focusX - 28, top: _focusY - 28,
                child: AnimatedBuilder(
                  animation: _focusAnim,
                  builder: (_, __) => Transform.scale(
                    scale: _focusAnim.value,
                    child: Container(
                      width: 56, height: 56,
                      decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: accent, width: 2)),
                    ),
                  ),
                ),
              ),

            // Top bar
            _buildTopBar(accent),

            // Phase badge
            _buildPhaseBadge(accent),

            // Aspect ratio info — only when non-default ratio selected
            if (_isAspectCropped) _buildAspectInfo(),

            // REC indicator
            if (_isRecording) _buildRecIndicator(),

            // Countdown overlay
            if (_showCountdown) _buildCountdownOverlay(accent),

            // Saving overlay
            if (_phase == CapturePhase.saving) _buildSavingOverlay(),

            // Complete overlay
            if (_phase == CapturePhase.complete) _buildCompleteOverlay(accent),

            // Error overlay
            if (_phase == CapturePhase.error) _buildErrorOverlay(),

            // Bottom controls visibility:
            //   Manual photo phase (PK + RT claim) → SHOW (START = trigger)
            //   Auto countdown                     → HIDE (number-only overlay)
            //   Recording / idle                   → SHOW (START/STOP behavior)
            //
            // RT claim manual is now treated identically to PK manual — the
            // bottom START button is the capture trigger, the giant center
            // button has been removed.
            if (_phase != CapturePhase.complete
                && _phase != CapturePhase.saving
                && !(_showCountdown && _captureCountdownSec > 0))
              _buildBottomControls(accent),
          ],
        ),
      ),
    );
  }

  // ─── Cropped preview ─────────────────────────────────────────────────
  /// CameraPreview rendered without stretching, using the canonical
  /// "OverflowBox" cover pattern:
  ///   1. Compute the on-screen viewport (vpW × vpH) for the chosen frame
  ///   2. Compute the camera's natural display size at cover-scale
  ///      (sized so the smaller dimension matches the viewport)
  ///   3. Render CameraPreview at that explicit size inside an OverflowBox
  ///      so it bleeds outside the clip, then ClipRect crops the overflow.
  ///
  /// `CameraPreview` internally wraps its texture in `AspectRatio`, so we
  /// can't pin it to arbitrary pixel dimensions — we must give it the right
  /// proportional size or it'll be letterboxed. This implementation gives
  /// it a SizedBox that matches the camera's natural ratio, so AspectRatio
  /// fills the SizedBox completely with no letterboxing.
  ///
  /// IMPORTANT: During active video recording, aspect cropping is FORCED OFF
  /// in the preview. The camera plugin records at the sensor's native
  /// resolution (16:9) and there is no in-plugin way to crop video on the
  /// fly — so showing a 1:1 / 3:4 preview during recording would lie to the
  /// user about what's actually being recorded. The user reported exactly
  /// this: "jaise hi video start hota hai yeh 16:9 pe switch karke video
  /// record karta hai". This guard keeps preview === recorded output.
  Widget _buildCroppedPreview() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final availW = constraints.maxWidth;
        final availH = constraints.maxHeight;

        // During recording, the saved video is full 16:9 sensor — disable
        // visual crop so what the user sees == what gets saved.
        final effectiveCropped = _isAspectCropped && !_isRecording;

        // On-screen viewport rect (the cropped area visible to the user).
        double vpW;
        double vpH;
        if (effectiveCropped) {
          vpW = availW;
          vpH = availW / _aspectRatio;
          if (vpH > availH) {
            vpH = availH;
            vpW = availH * _aspectRatio;
          }
        } else {
          vpW = availW;
          vpH = availH;
        }

        // Camera's natural portrait W/H. `controller.value.aspectRatio` is
        // given in LANDSCAPE coords (e.g. 1920/1080 = 1.78) — in portrait
        // display the actual on-screen ratio is its inverse (≈0.5625).
        final landscapeAR = _camera!.value.aspectRatio;
        final camPortraitAR = landscapeAR > 0 ? (1.0 / landscapeAR) : (9.0 / 16.0);

        // COVER sizing: the preview is rendered at the smallest size that
        // entirely covers the viewport while preserving its natural aspect.
        // Whichever dimension is "tight" against the viewport gets matched;
        // the other one overflows and is clipped.
        final viewportAR = vpW / vpH;
        double previewW;
        double previewH;
        if (viewportAR > camPortraitAR) {
          // Viewport is wider than the camera's natural view → match width,
          // let height overflow.
          previewW = vpW;
          previewH = vpW / camPortraitAR;
        } else {
          // Viewport is taller (or same) → match height, let width overflow.
          previewH = vpH;
          previewW = vpH * camPortraitAR;
        }

        return Container(
          color: Colors.black,
          child: Center(
            child: ClipRect(
              child: SizedBox(
                width: vpW,
                height: vpH,
                child: OverflowBox(
                  minWidth: previewW,
                  maxWidth: previewW,
                  minHeight: previewH,
                  maxHeight: previewH,
                  alignment: Alignment.center,
                  child: CameraPreview(_camera!),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  // ─── Top bar ─────────────────────────────────────────────────────────

  Widget _buildTopBar(Color accent) {
    return Positioned(
      top: 0, left: 0, right: 0,
      child: Container(
        color: Colors.black.withAlpha(140),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: Row(
          children: [
            GestureDetector(
              onTap: _close,
              child: Container(
                padding: const EdgeInsets.all(7),
                decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.close, color: Colors.white, size: 20),
              ),
            ),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: accent.withAlpha(200), borderRadius: BorderRadius.circular(12)),
              child: Text(
                widget.mode == CaptureMode.pk ? 'PK MODE' : 'RT MODE',
                style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // (Legacy _buildZoomButton + _buildAspectButton removed — replaced by the
  //  skeuomorphic RfChip widget from lib/widgets/rf_button.dart.)

  /// Aspect button tap handler. Persists the choice but is a NO-OP for the
  /// preview during recording (since video is always recorded at native
  /// 16:9 by the camera plugin — see [_buildCroppedPreview] comment).
  Future<void> _onAspectTap(String label, double ratio) async {
    debugPrint('AspectButton: tap label=$label ratio=$ratio (current=$_aspectRatio, isRecording=$_isRecording)');
    // During recording, frames don't apply (video is always 16:9). Show a
    // notice instead of changing state — keeps preview === recorded output.
    if (_isRecording) {
      ScaffoldMessenger.of(context)
        ..removeCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: const Text(
            'Frame applies to photos only. Video records at 16:9 portrait.',
            style: TextStyle(fontSize: 12),
          ),
          duration: const Duration(milliseconds: 1500),
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.only(bottom: 220, left: 40, right: 40),
          backgroundColor: Colors.black.withAlpha(220),
        ));
      return;
    }
    if ((_aspectRatio - ratio).abs() < 0.001) return;  // no-op tap
    setState(() => _aspectRatio = ratio);
    await CameraSettingsService.setAspectDefault(ratio);
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..removeCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text('Frame: $label', style: const TextStyle(fontSize: 12)),
        duration: const Duration(milliseconds: 900),
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.only(bottom: 220, left: 40, right: 40),
        backgroundColor: Colors.black.withAlpha(220),
      ));
  }

  // ─── PK instruction banner ────────────────────────────────────────────
  //
  // Sits ABOVE the capture button in the bottom controls. Shows the user
  // what the next tap will do — capture FRONT, capture BACK, or start
  // video. Replaces the old "tap → overlay → tap again" two-step flow:
  // now the banner is always visible so the user knows in advance, and a
  // single tap on the START button executes the action.
  Widget _buildPkInstructionBanner(Color accent) {
    final info = _pkInstructionFor();
    final hasFront = _tempPhotoPaths.containsKey(PhotoSide.front);
    final hasBack = _tempPhotoPaths.containsKey(PhotoSide.back);
    final stepN = !hasFront ? 1 : (!hasBack ? 2 : 3);
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [accent.withAlpha(200), accent.withAlpha(140)],
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withAlpha(80), width: 1),
          boxShadow: [
            BoxShadow(color: accent.withAlpha(120), blurRadius: 12, offset: const Offset(0, 4)),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white.withAlpha(60),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'STEP $stepN/3',
                style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: 0.8),
              ),
            ),
            const SizedBox(width: 10),
            Icon(info.icon, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                info.text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
                  shadows: [Shadow(color: Color(0x88000000), blurRadius: 2, offset: Offset(0, 1))],
                ),
                textAlign: TextAlign.left,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Phase badge ──────────────────────────────────────────────────────

  Widget _buildPhaseBadge(Color accent) {
    if (_phase == CapturePhase.complete || _phase == CapturePhase.loading) return const SizedBox.shrink();

    String text;
    switch (_phase) {
      case CapturePhase.recording:
        if (_showCountdown) {
          // No badge during countdown — the countdown overlay itself shows
          // the instruction; a second "CAPTURING X" badge is visual noise.
          return const SizedBox.shrink();
        } else {
          text = 'RECORDING';
        }
      case CapturePhase.stopped: text = 'READY TO SAVE';
      case CapturePhase.saving: text = 'SAVING';
      case CapturePhase.error: text = 'ERROR';
      default: return const SizedBox.shrink();
    }

    return Positioned(
      top: 56, left: 0, right: 0,
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
          decoration: BoxDecoration(color: Colors.black.withAlpha(150), borderRadius: BorderRadius.circular(16)),
          child: Text(text, style: TextStyle(color: accent, fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 0.8)),
        ),
      ),
    );
  }

  // ─── Aspect info banner ──────────────────────────────────────────────

  Widget _buildAspectInfo() {
    final ratioLabel = _aspectRatio == _aspect11 ? '1:1' : '3:4';
    return Positioned(
      top: 90,
      left: 0, right: 0,
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: Colors.black.withAlpha(140),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(
            'Photos $ratioLabel  ·  Video 16:9',
            style: const TextStyle(color: Colors.white60, fontSize: 10, fontWeight: FontWeight.w500),
          ),
        ),
      ),
    );
  }

  // ─── REC indicator ─────────────────────────────────────────────────────

  Widget _buildRecIndicator() {
    return Positioned(
      top: 56,
      right: 12,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        // Mic-state badge — live truth from _audioUsedForRecording (set at
        // the moment of startVideoRecording). Outlined icons per Mahika
        // §VII "Icon System" — Material outlined style for status badges.
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: _audioUsedForRecording ? RfColors.error : Colors.black54,
            borderRadius: BorderRadius.circular(RfRadius.chip),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(
              _audioUsedForRecording ? Icons.mic_outlined : Icons.mic_off_outlined,
              color: Colors.white,
              size: 12,
            ),
            const SizedBox(width: 4),
            Text(
              _audioUsedForRecording ? 'AUDIO' : 'MUTED',
              style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 0.5),
            ),
          ]),
        ),
        const SizedBox(width: 8),
        // Animated pulse dot per Mahika §V #4. 1.0 → 1.1 cycle, 1000ms,
        // easeInOut. Draws the eye without being distracting.
        const RfRecordingPulse(size: 10, color: Color(0xFFFF3B30)),
        const SizedBox(width: 6),
        Text(
          _elapsedLabel,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.bold,
            fontFamily: 'monospace',
          ),
        ),
      ]),
    );
  }

  // ─── Countdown overlay ────────────────────────────────────────────────

  Widget _buildCountdownOverlay(Color accent) {
    final instruction = widget.mode == CaptureMode.pk
        ? (_nextPhotoSide == PhotoSide.front ? 'Position FRONT facing' : 'Position BACK facing')
        : _countdownInstruction;

    return Stack(
      children: [
        // (Top bar is rendered separately by _buildTopBar at the parent Stack level —
        //  no need to duplicate close+mode badge here.)

        // Center content:
        //   Auto countdown         → big countdown number
        //   Manual (countdown=0)   → just instruction text. The bottom
        //                            START/CAPTURE button is the ONLY trigger.
        //
        // NOTE: The big white center-CAPTURE button was removed per user
        // feedback — the bottom button now handles both PK and RT claim
        // manual capture, so the UI is uniform across modes.
        Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            if (_captureCountdownSec > 0)
              Text(
                '$_countdownSeconds',
                style: TextStyle(
                  fontSize: 140,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  shadows: [Shadow(color: accent, blurRadius: 40)],
                ),
              ),
            const SizedBox(height: 20),
            Text(
              instruction,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, fontSize: 18, fontWeight: FontWeight.w400),
            ),
            if (_captureCountdownSec <= 0) ...[
              const SizedBox(height: 8),
              const Text(
                'Tap CAPTURE below',
                style: TextStyle(color: Colors.white38, fontSize: 12, fontStyle: FontStyle.italic),
              ),
            ],
          ]),
        ),

        // (The RT claim Skip button is rendered inside _buildBottomControls,
        //  ABOVE the capture button, instead of being positioned absolutely
        //  here. The previous absolute Positioned(bottom: 160) sat INSIDE
        //  the bottom-controls gradient and was hidden behind the capture
        //  button — the user explicitly reported "skip button chup raha hai".)
      ],
    );
  }

  // ─── Bottom controls ──────────────────────────────────────────────────

  Widget _buildBottomControls(Color accent) {
    return Positioned(
      bottom: 0, left: 0, right: 0,
      child: Container(
        padding: const EdgeInsets.fromLTRB(24, 36, 24, 36),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.black.withAlpha(0),
              Colors.black.withAlpha(200),
              Colors.black.withAlpha(230),
            ],
          ),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          // ── RT claim-flow Skip pill ─────────────────────────────────
          // Lives at the TOP of the bottom-controls column so it is never
          // obscured by the capture button. Previously rendered as an
          // absolute Positioned widget which got hidden behind the bigger
          // capture button — user reported "skip button chup raha hai".
          if (_inClaimFlow)
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: RfButton.secondary(
                label: 'SKIP THIS PHOTO',
                icon: Icons.skip_next_rounded,
                size: RfButtonSize.medium,
                onPressed: () {
                  if (_captureCountdownSec <= 0) {
                    _onSkipManualCapture();
                  } else {
                    setState(() => _skipCurrentClaimPhoto = true);
                  }
                },
              ),
            ),

          // ── PK direct-capture instruction banner ────────────────────
          // Persistent, prominent banner showing what the next tap will do
          // (capture FRONT / capture BACK / start video). Replaces the old
          // "show overlay, wait for second tap" flow — user sees the
          // instruction at all times and a single tap triggers the action.
          if (!_isRecording
              && widget.mode == CaptureMode.pk
              && _captureCountdownSec <= 0
              && _phase == CapturePhase.stopped)
            _buildPkInstructionBanner(accent),

          // Mode instructions during recording
          if (_isRecording)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                widget.mode == CaptureMode.pk
                    ? 'Pack the product. Tap STOP when done.'
                    : 'Inspect the return. Tap STOP when done.',
                style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                textAlign: TextAlign.center,
              ),
            ),

          // Main capture button — skeuomorphic press-feedback (scale + glow)
          _CapturePressButton(
            isRecording: _isRecording,
            onTap: _isRecording ? _stopRecording : _onCapturePressed,
          ),

          const SizedBox(height: 12),

          // Button label — only shown during ACTIVE recording (where it
          // confirms "TAP TO STOP"). Removed for idle/photo state per user
          // request — the giant capture button + persistent PK instruction
          // banner above already convey the action; a label below adds
          // noise.
          if (_isRecording)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withAlpha(180),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: Colors.white.withAlpha(40), width: 1),
              ),
              child: const Text(
                'TAP TO STOP',
                style: TextStyle(
                  color: Colors.red,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.5,
                ),
              ),
            ),

          const SizedBox(height: 20),

          // Camera controls row — skeuomorphic chips (zoom + aspect + mic).
          // FittedBox prevents overflow on narrow screens.
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withAlpha(160),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Zoom buttons — always visible (PK, RT, all phases incl. claim photo)
                  RfChip(label: '1×', active: _currentZoomIndex == 0, onPressed: () => _setZoomByIndex(0)),
                  const SizedBox(width: 4),
                  RfChip(label: '2×', active: _currentZoomIndex == 1, onPressed: () => _setZoomByIndex(1)),
                  const SizedBox(width: 4),
                  RfChip(label: '3×', active: _currentZoomIndex == 2, onPressed: () => _setZoomByIndex(2)),

                  const SizedBox(width: 8),
                  Container(width: 1, height: 28, color: Colors.white24),
                  const SizedBox(width: 8),

                  // Aspect ratio chips — dimmed during recording (video can
                  // only be saved at native 16:9; the toggle still surfaces
                  // a notice but doesn't change the preview).
                  Opacity(
                    opacity: _isRecording ? 0.45 : 1.0,
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      RfChip(label: '1:1', active: !_isRecording && (_aspectRatio - _aspect11).abs() < 0.001, onPressed: () => _onAspectTap('1:1', _aspect11)),
                      const SizedBox(width: 4),
                      RfChip(label: '3:4', active: !_isRecording && (_aspectRatio - _aspect34).abs() < 0.001, onPressed: () => _onAspectTap('3:4', _aspect34)),
                      const SizedBox(width: 4),
                      RfChip(label: '16:9', active: _isRecording || (_aspectRatio - _aspectFull).abs() < 0.001, onPressed: () => _onAspectTap('16:9', _aspectFull)),
                    ]),
                  ),

                  const SizedBox(width: 8),
                  Container(width: 1, height: 28, color: Colors.white24),
                  const SizedBox(width: 8),

                  // Mic toggle — skeuomorphic icon button. Disabled during
                  // camera transitions to avoid the audio-state race bug.
                  _MicToggleButton(
                    enabled: _micEnabled,
                    disabled: _isCameraTransitioning,
                    onTap: _isCameraTransitioning ? null : _toggleMic,
                  ),
                ],
              ),
            ),
          ),
        ]),
      ),
    );
  }

  // ─── Saving overlay ──────────────────────────────────────────────────

  Widget _buildSavingOverlay() {
    return Positioned.fill(
      child: Container(
        color: Colors.black.withAlpha(200),
        child: const Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
            SizedBox(height: 16),
            Text('Saving files...', style: TextStyle(color: Colors.white70, fontSize: 14)),
          ]),
        ),
      ),
    );
  }

  // ─── Complete overlay ─────────────────────────────────────────────────

  Widget _buildCompleteOverlay(Color accent) {
    return Positioned.fill(
      child: Container(
        color: Colors.black.withAlpha(220),
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.check_circle_rounded, color: Colors.green.shade400, size: 64),
            const SizedBox(height: 16),
            const Text('Saved!', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(
              widget.mode == CaptureMode.pk ? 'PK session complete' : 'RT session complete',
              style: const TextStyle(color: Colors.white54, fontSize: 13),
            ),
            const SizedBox(height: 24),
            Row(mainAxisSize: MainAxisSize.min, children: [
              RfButton.primary(
                label: 'CAPTURE NEXT',
                icon: Icons.replay_rounded,
                size: RfButtonSize.large,
                onPressed: _resetForNextCapture,
              ),
              const SizedBox(width: 12),
              RfButton.secondary(
                label: 'EXIT',
                size: RfButtonSize.large,
                onPressed: () => Navigator.pop(context, true),
              ),
            ]),
          ]),
        ),
      ),
    );
  }

  // ─── Error overlay ────────────────────────────────────────────────────
  //
  // Surfaces three actions to recover from camera/permission failures:
  //   RETRY   — re-init the camera (handles transient "camera busy" errors)
  //   SETTINGS — open the OS app-settings page so the user can grant the
  //              permission that's blocking init (handles permission-denied
  //              cases per Mahika edge-case audit #2)
  //   CLOSE   — back out to home
  //
  // The Settings button is gated on whether the error message looks like
  // a permission issue, so we don't surface a confusing "Settings" CTA for
  // genuinely transient errors like "Camera busy".

  bool get _errorLooksLikePermission {
    final msg = (_errorMessage ?? '').toLowerCase();
    return msg.contains('permission') ||
        msg.contains('denied') ||
        msg.contains('no camera') ||
        msg.contains('access');
  }

  Widget _buildErrorOverlay() {
    return Positioned.fill(
      child: Container(
        color: Colors.black.withAlpha(220),
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline_rounded, color: Colors.red, size: 56),
            const SizedBox(height: 16),
            Text(_errorMessage ?? 'An error occurred', style: const TextStyle(color: Colors.white, fontSize: 14), textAlign: TextAlign.center),
            if (_errorLooksLikePermission) ...[
              const SizedBox(height: 10),
              const Text(
                'Camera or storage permission is blocked. Grant it in Settings, then come back.',
                style: TextStyle(color: Colors.white60, fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 24),
            Wrap(spacing: 12, runSpacing: 10, alignment: WrapAlignment.center, children: [
              RfButton.primary(
                label: 'RETRY',
                icon: Icons.refresh_rounded,
                size: RfButtonSize.medium,
                onPressed: () {
                  setState(() {
                    _phase = CapturePhase.loading;
                    _errorMessage = null;
                    _camera = null;
                    _cameraReady = false;
                  });
                  _initCamera();
                },
              ),
              if (_errorLooksLikePermission)
                RfButton.service(
                  label: 'OPEN SETTINGS',
                  icon: Icons.settings_outlined,
                  size: RfButtonSize.medium,
                  onPressed: () async {
                    await openAppSettings();
                  },
                ),
              RfButton.secondary(
                label: 'CLOSE',
                size: RfButtonSize.medium,
                onPressed: () => Navigator.pop(context),
              ),
            ]),
          ]),
        ),
      ),
    );
  }
}

// ─── Helper widgets — Mahika camera-app doctrine ──────────────────────────
//
// Pattern (Mahika §V #1): ScaleTransition 1.0 → 0.95 over 200ms easeOut on
// tap-down, reverses on release. Combined with light bg-darken + haptic
// confirmation. Matches the rest of the app via shared RfDuration.press
// timing token.

/// The big circular shutter button. Solid white ring, white circle when
/// idle, red rounded-square when recording. ScaleTransition press feedback.
class _CapturePressButton extends StatefulWidget {
  final bool isRecording;
  final VoidCallback onTap;
  const _CapturePressButton({required this.isRecording, required this.onTap});

  @override
  State<_CapturePressButton> createState() => _CapturePressButtonState();
}

class _CapturePressButtonState extends State<_CapturePressButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.92)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isRec = widget.isRecording;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _ctrl.forward(),
      onTapUp: (_) => _ctrl.reverse(),
      onTapCancel: () => _ctrl.reverse(),
      onTap: () {
        HapticFeedback.mediumImpact();
        widget.onTap();
      },
      child: ScaleTransition(
        scale: _scale,
        child: Container(
          width: 76,
          height: 76,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withAlpha(25),
            border: Border.all(color: Colors.white, width: 4),
          ),
          child: Center(
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: isRec ? 30 : 54,
              height: isRec ? 30 : 54,
              decoration: BoxDecoration(
                color: isRec ? RfColors.error : Colors.white,
                borderRadius: BorderRadius.circular(isRec ? 7 : 27),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Mic toggle — Mahika §IV §"Toggle Button (Mic On/Off)" pattern.
/// Red filled when mic is ON, neutral dark surface when MUTED. Outlined
/// mic icon. ScaleTransition press.
class _MicToggleButton extends StatefulWidget {
  final bool enabled;
  final bool disabled;
  final VoidCallback? onTap;
  const _MicToggleButton({required this.enabled, required this.disabled, required this.onTap});

  @override
  State<_MicToggleButton> createState() => _MicToggleButtonState();
}

class _MicToggleButtonState extends State<_MicToggleButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.95)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fill = widget.enabled ? RfColors.error : Colors.white.withAlpha(20);
    final fg = widget.enabled ? Colors.white : Colors.white70;
    final disabled = widget.disabled || widget.onTap == null;
    return Opacity(
      opacity: widget.disabled ? 0.4 : 1,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: disabled ? null : (_) => _ctrl.forward(),
        onTapUp: disabled ? null : (_) => _ctrl.reverse(),
        onTapCancel: disabled ? null : () => _ctrl.reverse(),
        onTap: disabled
            ? null
            : () {
                HapticFeedback.selectionClick();
                widget.onTap!();
              },
        child: ScaleTransition(
          scale: _scale,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: fill,
              borderRadius: BorderRadius.circular(RfRadius.chip),
              border: Border.all(
                color: widget.enabled ? Colors.transparent : Colors.white.withAlpha(60),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(widget.enabled ? Icons.mic_outlined : Icons.mic_off_outlined, color: fg, size: 18),
                const SizedBox(width: 6),
                Text(
                  widget.enabled ? 'MIC ON' : 'MIC OFF',
                  style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
