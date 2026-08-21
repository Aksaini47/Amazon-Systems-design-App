import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import 'package:native_camera_sound/native_camera_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/capture_session.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../services/camera_settings_service.dart';
import '../services/local_storage_service.dart';
import '../utils/debug_session_log.dart';
import '../services/dnd_service.dart';
import '../services/crash_reporting.dart';
import '../services/activity_log_service.dart';
import '../utils/volume_button_service.dart';
import '../utils/image_processing.dart';
import '../widgets/rf_button.dart';
import '../config/app_config.dart';
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
  _LiveSession _session = _LiveSession();

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
  VoidCallback? _cameraListener;        // Rebuild preview when camera texture updates

  // ─── Aspect ratio ──────────────────────────────────────────────────────
  // Width/height ratio (portrait orientation):
  //   _aspectFull (16:9 portrait) = 9/16 ≈ 0.5625  — no crop, fills phone screen
  //   _aspect34   (3:4 portrait)  = 3/4  = 0.75    — taller crop
  //   _aspect11   (1:1 square)    = 1.0            — square crop
  // Photos are cropped to this ratio after capture.
  // Video records native 16:9 (camera package limitation; FFmpeg crop unreliable).
  static const double _aspectFull = CameraSettingsService.aspectFull;
  static const double _aspect34 = CameraSettingsService.aspect34;
  static const double _aspect11 = CameraSettingsService.aspect11;
  double _aspectRatio = _aspectFull;
  // Collapsible ratio control (Samsung-style): collapsed shows the current
  // ratio, tap expands into the option strip. See _buildRatioControl.
  bool _aspectStripExpanded = false;
  bool get _isAspectCropped =>
      (_aspectRatio - _aspectFull).abs() > 0.001;

  // True once the post-claim-re-init camera texture has stabilized (see
  // _runClaimPhotoSequence). Gates ONLY the brief black-texture risk window
  // right after re-init, not the whole claim-photo sequence — previously
  // the cropped/guided preview was hidden for all 5 claim photos, so the
  // user never saw their selected frame while shooting RT QC images even
  // though the saved files were already being cropped correctly.
  bool _claimPreviewSettled = false;

  /// Full-bleed only during the brief claim re-init settle window, or while
  /// a draft video is still in session.
  bool get _useFullBleedPreview =>
      (_inClaimFlow && !_claimPreviewSettled) ||
      (_session.videoPath != null && _camera != null);

  // Capture countdown duration from settings. 0 = manual capture mode.
  int _captureCountdownSec = 3;
  bool _claimCountdownEnabled = true;
  String? _lastLoggedBuildBranch;

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
    // Engage immersive layout for the WHOLE screen lifetime, not just while
    // recording. Previously this only happened at the instant recording
    // started (_enableRecordingMode), which hid the status/nav bars right
    // as the record button was tapped — the available layout size changed
    // at that exact moment, so the on-screen frame visibly jumped/resized.
    // Setting it once here means idle and recording render in identical
    // screen real estate; see dispose() for the matching restore.
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
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
    _claimCountdownEnabled = await CameraSettingsService.getClaimPhotoCountdown();
    _aspectRatio = await CameraSettingsService.getAspectDefaultForMode(widget.mode);
    _currentZoomIndex = await CameraSettingsService.getZoomDefaultForMode(widget.mode);
    if (mounted) setState(() {});
    unawaited(_initCamera());
  }

  @override
  void dispose() {
    _timerTick?.cancel();
    _countdownTimer?.cancel();
    _focusAnimCtrl.dispose();
    _detachCameraListener();
    _camera?.dispose();
    // Always release wakelock + restore DND on exit, in case the user
    // backed out mid-recording without going through _stopRecording.
    _disableRecordingMode();
    // Must be cleared here too: backing out mid-recording skips
    // _stopRecording's finally, and a flag left true would silently disable
    // orphan recovery for the rest of the process.
    LocalStorageService.recordingInFlight = false;
    VolumeButtonService().unregisterListener('live_capture_screen');
    // Restore all orientations so other app screens (gallery, settings)
    // remain free to rotate.
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    // Leaving the screen — drop the immersive layout engaged in initState().
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
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
      if (_isSaving) return;
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

  void _detachCameraListener() {
    if (_camera != null && _cameraListener != null) {
      _camera!.removeListener(_cameraListener!);
    }
    _cameraListener = null;
  }

  void _attachCameraListener() {
    _detachCameraListener();
    if (_camera == null) return;
    _cameraListener = () {
      if (!mounted) return;
      if (_isRecording ||
          _camera!.value.isRecordingVideo ||
          _inClaimFlow ||
          _session.videoPath != null) {
        setState(() {});
      }
    };
    _camera!.addListener(_cameraListener!);
  }

  void _logPreviewState(String location, {Map<String, dynamic>? extra}) {
    final cam = _camera;
    final value = cam?.value;
    DebugSessionLog.log(
      location: location,
      message: 'camera preview state',
      hypothesisId: 'H7-H8',
      data: {
        'phase': _phase.name,
        'isRecording': _isRecording,
        'cameraReady': _cameraReady,
        'cameraNull': cam == null,
        'initialized': value?.isInitialized ?? false,
        'isRecordingVideo': value?.isRecordingVideo ?? false,
        'aspectRatio': value?.aspectRatio,
        'previewSizeW': value?.previewSize?.width,
        'previewSizeH': value?.previewSize?.height,
        'hasError': value?.hasError ?? false,
        'errorDescription': value?.errorDescription,
        ...?extra,
      },
    );
  }

  void _logBuildBranch(String branch) {
    if (_lastLoggedBuildBranch == branch) return;
    _lastLoggedBuildBranch = branch;
    DebugSessionLog.log(
      location: 'live_capture_screen.dart:build',
      message: 'ui branch',
      hypothesisId: 'H1-H3',
      data: {
        'branch': branch,
        'phase': _phase.name,
        'mode': widget.mode.name,
        'cameraNull': _camera == null,
        'cameraReady': _cameraReady,
        'isRecording': _isRecording,
        'hasVideoDraft': _session.videoPath != null,
        'showCountdown': _showCountdown,
        'inClaimFlow': _inClaimFlow,
      },
    );
  }

  Future<void> _disposeCameraForModal() async {
    _detachCameraListener();
    await _camera?.dispose();
    _camera = null;
    if (mounted) setState(() => _cameraReady = false);
    DebugSessionLog.log(
      location: 'live_capture_screen.dart:_disposeCameraForModal',
      message: 'camera disposed for modal',
      hypothesisId: 'H1',
      data: {'phase': _phase.name, 'hasVideoDraft': _session.videoPath != null},
    );
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
      await Future<void>.delayed(const Duration(milliseconds: 300));
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
          _attachCameraListener();
          setState(() => _cameraReady = true);
          _startSession();
          // Apply default zoom (1x) to newly initialized camera
          _applyZoom();
          _logPreviewState('live_capture_screen.dart:_initCamera');
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
      await Future<void>.delayed(const Duration(milliseconds: 300));
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
          _attachCameraListener();
          setState(() => _cameraReady = true);
          _startSession();
          _applyZoom();
          _logPreviewState('live_capture_screen.dart:_initCameraWithAudio');
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
    _session.sessionStartedAt = DateTime.now();
    // Don't auto-start — wait for user to tap capture button
    setState(() { _phase = CapturePhase.stopped; });
  }

  void _logActivity(String event, {Map<String, String>? extra}) {
    final verdict = _session.verdict;
    ActivityLogService.log(
      event: event,
      mode: widget.mode,
      orderId: _session.orderId,
      awb: _session.awb,
      qc: verdict?.name,
      extra: extra,
    );
  }

  /// Clears countdown / claim-flow UI so the next RT video starts on a clean camera.
  void _clearCaptureOverlayState() {
    _countdownTimer?.cancel();
    _skipCurrentClaimPhoto = false;
    _inClaimFlow = false;
    _claimPreviewSettled = false;
    _nextPhotoSide = PhotoSide.front;
    if (_manualCaptureCompleter != null && !_manualCaptureCompleter!.isCompleted) {
      _manualCaptureCompleter!.complete(false);
    }
    _manualCaptureCompleter = null;
    _showCountdown = false;
    _countdownSeconds = 0;
  }

  void _onCapturePressed() {
    // RT claim photos: CAPTURE takes a still — never start a new video session.
    if (_inClaimFlow) {
      _onManualCaptureTap();
      return;
    }

    // Manual-photo mode mid-countdown: the bottom button completes the capture.
    // This path is reached if the user has countdown=0 AND _showCountdown is
    // somehow active (e.g. legacy overlay). PK photo capture below does NOT
    // enter the overlay state any more.
    if (_showCountdown && _captureCountdownSec <= 0) {
      _countdownTimer?.cancel();
      _onManualCaptureTap();
      return;
    }

    if (_phase == CapturePhase.stopped && !_isRecording) {
      if (widget.mode == CaptureMode.pk) {
        if (_captureCountdownSec > 0) {
          _startPhotoSequence();
        } else {
          _capturePkPhotoDirect();
        }
      } else {
        // RT idle — tap starts return video recording
        unawaited(_startRecording());
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
      unawaited(_startRecording());
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
    unawaited(HapticFeedback.mediumImpact());
    if (_soundEnabled) unawaited(NativeCameraSound.playShutter());

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
    if (_inClaimFlow) return;
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

      _session.videoStartedAt = DateTime.now();
      _logActivity('video_start');
      _stopwatch.reset();
      _stopwatch.start();
      _timerTick?.cancel();
      _timerTick = Timer.periodic(const Duration(seconds: 1), (_) { if (mounted) setState(() {}); });

      if (_soundEnabled) unawaited(NativeCameraSound.playStartRecord());

      try {
        // Save audio setting for re-init after modal closes
        _audioUsedForRecording = _micEnabled;
        // Guard against camera being disposed while we awaited DND.
        if (_camera == null) {
          _stopwatch.stop();
          return;
        }
        // Fence the cache-dir sweepers off this recording BEFORE the plugin
        // creates its temp file there. recoverOrphanVideos() walks the same
        // directory and copy-deletes every *.mp4 it finds; unlinking a live
        // recording leaves the writer's fd valid, so the capture "succeeds"
        // and only fails at stop with a path that no longer exists.
        LocalStorageService.recordingInFlight = true;
        await _camera!.startVideoRecording();
        if (!mounted) return;
        _logPreviewState('live_capture_screen.dart:_startRecording', extra: {
          'step': 'afterStartVideoRecording',
        });
        // Engage recording guards (wakelock + DND) before the preview
        // rebuild. Immersive layout is already engaged (initState), so this
        // no longer resizes the OverflowBox crop path.
        await _enableRecordingMode();
        if (!mounted) return;
        setState(() { _isRecording = true; _phase = CapturePhase.recording; });
        _logPreviewState('live_capture_screen.dart:_startRecording', extra: {
          'step': 'afterSetStateRecording',
        });
      } catch (e) {
        _stopwatch.stop();
        LocalStorageService.recordingInFlight = false;
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
        builder: (ctx) => AlertDialog(
          backgroundColor: RfColors.card,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(children: [
            Icon(Icons.do_not_disturb_on_rounded, color: RfColors.amber, size: 22),
            SizedBox(width: 10),
            Text('Silence interruptions?', style: TextStyle(color: Colors.white)),
          ]),
          content: const Text(
            'Grant Do Not Disturb access so RepairFully can mute notifications, '
            'ringer, and non-urgent calls while you\'re recording. Auto-restores '
            'your previous settings when you stop.\n\n'
            'You can change this anytime in your phone\'s settings.',
            style: TextStyle(color: RfColors.textSecondary, fontSize: 13),
          ),
          actions: [
            RfButton.secondary(
              label: 'Skip',
              onPressed: () => Navigator.pop(ctx, false),
            ),
            RfButton.primary(
              label: 'Grant',
              onPressed: () => Navigator.pop(ctx, true),
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
              Icon(Icons.touch_app, color: RfColors.amber, size: 18),
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
  ///   - DND (priority mode) — silences notifications, ringer, and non-priority
  ///     calls during recording. Saves the previous DND state so we can restore
  ///     it exactly when recording stops. Silently no-ops if user hasn't
  ///     granted DND permission yet (offered as one-time prompt elsewhere).
  ///
  /// Immersive layout is engaged once for the whole screen in initState(),
  /// not here — see the comment there for why.
  Future<void> _enableRecordingMode() async {
    try {
      await WakelockPlus.enable();

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
  /// Does NOT touch the system UI mode — the screen stays immersive for its
  /// whole lifetime (see initState()); reverting here would cause the same
  /// visual jump on stop that this fix removes on start.
  Future<void> _disableRecordingMode() async {
    try {
      await WakelockPlus.disable();

      if (_previousDndFilter != null) {
        await DndService.setFilter(_previousDndFilter!);
        debugPrint('DND: restored to filter $_previousDndFilter');
        _previousDndFilter = null;
      }
    } catch (e) {
      debugPrint('disableRecordingMode failed (non-fatal): $e');
    }
  }

  /// Re-entrancy guard for [_stopRecording] — mirrors [_startingRecording].
  /// Two undebounced triggers can both call this while `_isRecording` is
  /// still true (it isn't cleared until deep in the async success path,
  /// well after the native stopVideoRecording() call): the on-screen
  /// capture button (no debounce) and the hardware volume-up key (Android
  /// re-fires onKeyDown on key-repeat while held — see MainActivity.kt's
  /// repeatCount guard). Without this flag, the second concurrent call
  /// reaches `_camera!.stopVideoRecording()` a second time and either hits
  /// the plugin's `!value.isRecordingVideo` guard (CameraException "No
  /// video is recording") or races the plugin's shared unlocked output-path
  /// state, producing a PathNotFoundException when saveDraftVideo() tries
  /// to copy a temp file that's already gone.
  bool _stoppingRecording = false;

  Future<void> _stopRecording() async {
    if (!_isRecording) return;
    if (_stoppingRecording) return;
    _stoppingRecording = true;
    _timerTick?.cancel();
    _stopwatch.stop();
    _countdownTimer?.cancel();
    if (_soundEnabled) unawaited(NativeCameraSound.playStopRecord());

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
      _session.videoStoppedAt = DateTime.now();
      _session.videoDurationSeconds = _stopwatch.elapsed.inSeconds;
      _logActivity('video_stop', extra: {
        'duration_sec': '${_stopwatch.elapsed.inSeconds}',
      });

      // Validate the recording before saving as a draft. Two independent
      // signals decide this, and they are NOT interchangeable:
      //   - `tooShort` (stopwatch, measured BEFORE the stopVideoRecording()
      //     await above) is a reliable read of what the user actually did —
      //     a tap-START + immediate-tap-STOP with nothing worth keeping.
      //   - `fileSize` is a size probe on CameraX's (camera_android_camerax)
      //     raw temp output, read immediately after its stop call resolves.
      //     CameraX finalizes the MP4 (flushing buffered frames, writing the
      //     moov atom) asynchronously relative to that Future resolving, so
      //     a LONGER recording (more data to flush) can transiently
      //     under-report its size right at this instant — the opposite of
      //     what a naive size check assumes. Treating a small read here as
      //     proof of failure and deleting the only copy is how a fully
      //     recorded unpack video gets silently destroyed on "some
      //     shipments". Re-stat with a few short retries before trusting a
      //     small number, and never delete on that signal alone.
      final tempFile = File(xfile.path);
      final tooShort = _stopwatch.elapsed.inMilliseconds < 1000;

      // A FileSystemException out of length() is NOT "the file is small" —
      // it means the recording is already GONE. The previous loop collapsed
      // both cases into `fileSize = 0`, swallowing five exceptions in a row;
      // that is why the 2026-08-19 failures spent a full second re-probing a
      // file that no longer existed and then walked into saveDraftVideo()
      // with nothing to copy, surfacing as a raw PathNotFoundException.
      // Track the two cases apart, and stop probing the moment it vanishes.
      int fileSize = 0;
      var tempMissing = false;
      Future<void> probeTemp() async {
        try {
          fileSize = await tempFile.length();
        } on FileSystemException {
          tempMissing = !await tempFile.exists();
          if (!tempMissing) fileSize = 0;
        }
      }
      await probeTemp();
      // Retry only while the file still EXISTS and still looks small —
      // CameraX flushes the moov atom asynchronously, so an early small read
      // on a genuinely-recorded video is expected (2026-07-24 fix).
      // (Skipped for a too-short tap — that path discards regardless, so
      // waiting on a flush that does not matter only delays the retry.)
      for (var attempt = 0;
          attempt < 4 && !tooShort && !tempMissing && fileSize < 50000;
          attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 200));
        await probeTemp();
      }

      if (tooShort) {
        // Genuinely near-instant tap — nothing of value was recorded. Safe
        // to discard: there is no evidence here to lose.
        debugPrint('Recording too short (${_stopwatch.elapsed.inMilliseconds}ms, ${fileSize}B) — discarding');
        await CrashReporting.setCaptureContext(
          mode: widget.mode,
          phase: 'stop_too_short',
        );
        await CrashReporting.recordNonFatal(
          Exception('recording_too_short'),
          StackTrace.current,
          reason: 'stop_recording_too_short size=$fileSize ms=${_stopwatch.elapsed.inMilliseconds}',
        );
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
              Icon(Icons.error_outline, color: RfColors.error, size: 18),
              SizedBox(width: 8),
              Expanded(child: Text('Recording too short — re-capture from the beginning')),
            ]),
            duration: const Duration(milliseconds: 2400),
            backgroundColor: Colors.black87,
          ));
        }
        return;  // stay on camera, user can retry
      }

      // CRITICAL: get the evidence OUT of Android's cache directory before
      // doing anything else with it.
      //
      // The camera plugin records into File.createTempFile(..., getCacheDir())
      // and exposes no way to change that (flutter/flutter#91680, open since
      // 2021). Android reclaims cache space whenever the device runs low —
      // there is no exemption for foreground apps — and CameraX 1.5 also
      // aborts and DELETES its own output on ERROR_INSUFFICIENT_STORAGE, an
      // error the Flutter plugin never reads (VideoRecordEventFinalize
      // carries no error field), so it hands back the path of a file that is
      // already gone. That is the 2026-08-19 double failure, on a phone with
      // under 2 GB free. So: copy FIRST, judge the copy second. Everything
      // that used to run before this point was time the only copy of the
      // evidence spent sitting in an evictable directory.
      String? draftPath;
      Object? saveError;
      StackTrace? saveStack;
      if (!tempMissing) {
        try {
          draftPath = await _localStorage.saveDraftVideo(xfile, widget.mode);
        } catch (e, st) {
          saveError = e;
          saveStack = st;
        }
      }
      // The reported path can be stale even when a good file does exist: the
      // plugin never clears videoOutputPath after a stop, and silently
      // no-ops a start when its `recording` field is left over from an
      // earlier capture. Look for the real file before declaring a loss.
      draftPath ??= await _localStorage.salvageOrphanRecording(
        widget.mode,
        // Bound the search to this capture: a file older than the moment
        // recording started belongs to a different shipment, and silently
        // filing that under this order would be worse than reporting a loss.
        notBefore: DateTime.now()
            .subtract(_stopwatch.elapsed + const Duration(seconds: 30)),
      );

      if (draftPath == null) {
        await _handleLostRecording(
          error: saveError ??
              FileSystemException('recording file missing', xfile.path),
          stack: saveStack ?? StackTrace.current,
          tempPath: xfile.path,
          tempMissing: tempMissing,
        );
        return;
      }

      // Evidence is safe now — judge the size from the saved copy, not from
      // the volatile temp file.
      var savedSize = 0;
      try { savedSize = await File(draftPath).length(); } catch (_) {}
      final looksSmall = savedSize < 50000;
      if (looksSmall) {
        // A real recording happened (stopwatch agrees) but it still looks
        // small. Never destroy the only copy on this signal alone — it stays
        // in drafts, listed there flagged as suspect.
        debugPrint('Recording finished (${_stopwatch.elapsed.inMilliseconds}ms) but saved file is small (${savedSize}B) — kept in drafts');
        await CrashReporting.recordNonFatal(
          Exception('recording_small_file_kept'),
          StackTrace.current,
          reason: 'stop_recording_small_but_kept size=$savedSize ms=${_stopwatch.elapsed.inMilliseconds}',
        );
      }

      _session.videoPath = draftPath;
      _session.isDraft = true;
      debugPrint('Video saved to drafts: $draftPath');
      _logActivity('draft_saved', extra: {
        'size': '$savedSize',
        'salvaged': '${saveError != null}',
      });
      // #region agent log
      DebugSessionLog.log(
        location: 'live_capture_screen.dart:_stopRecording',
        message: 'draft saved after stop',
        hypothesisId: 'H2-H11',
        data: {
          'mode': widget.mode.name,
          'draftPath': draftPath,
          'durationSec': _stopwatch.elapsed.inSeconds,
          'fileSize': savedSize,
          'looksSmall': looksSmall,
          'salvaged': saveError != null,
        },
      );
      // #endregion

      // Release wakelock + restore system UI now that recording is done
      await _disableRecordingMode();

      setState(() {
        _isRecording = false;
        _showCountdown = false;
        _phase = CapturePhase.stopped;
      });
      _logPreviewState('live_capture_screen.dart:_stopRecording', extra: {
        'step': 'afterDraftSaved',
        'rtKeepsCamera': widget.mode == CaptureMode.rt,
      });

      if (looksSmall && mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Video file looked smaller than expected — saved to Drafts, please double-check it'),
          duration: Duration(milliseconds: 3000),
          backgroundColor: Colors.black87,
        ));
      }

      if (widget.mode == CaptureMode.rt) {
        // RT: keep camera alive through verdict sheet so user does not see
        // a black "Starting camera..." screen while choosing QC reasons.
        unawaited(_openRtPostVideoFlow());
      } else {
        await _disposeCameraForModal();
        _openBarcodePopup();
      }
    } catch (e, st) {
      await _handleLostRecording(
        error: e,
        stack: st,
        tempPath: '',
        tempMissing: false,
      );
    } finally {
      _stoppingRecording = false;
      LocalStorageService.recordingInFlight = false;
    }
  }

  /// The recording could not be saved and nothing could be salvaged — the
  /// evidence is gone. Everything in here exists because the old catch block
  /// did none of it: it dumped a raw PathNotFoundException on screen and left
  /// the wakelock held, Sir's DND filter un-restored, and the failed
  /// attempt's PK photos sitting in `_tempPhotoPaths`, where the NEXT capture
  /// would have promoted them to disk alongside a different order's video.
  Future<void> _handleLostRecording({
    required Object error,
    required StackTrace stack,
    required String tempPath,
    required bool tempMissing,
  }) async {
    final ms = _stopwatch.elapsed.inMilliseconds;
    await CrashReporting.setCaptureContext(
      mode: widget.mode,
      phase: 'stop_failed',
    );
    await CrashReporting.recordNonFatal(
      error,
      stack,
      reason: 'stop_recording_failed temp_missing=$tempMissing ms=$ms path=$tempPath',
    );
    // The activity log is the only diagnostic Sir can actually reach
    // (Settings → Activity log). Until now a lost recording left no trace
    // in it whatsoever: video_start, video_stop, then silence — shaped
    // exactly like a capture the user simply abandoned.
    _logActivity('video_stop_failed', extra: {
      'temp_missing': '$tempMissing',
      'duration_sec': '${_stopwatch.elapsed.inSeconds}',
      'error': '$error',
    });

    // Same rollback the too-short branch performs: photos belonging to a
    // capture whose video is gone must not survive into the next attempt.
    for (final p in _tempPhotoPaths.values) {
      try { await File(p).delete(); } catch (_) {}
    }
    _tempPhotoPaths.clear();
    _nextPhotoSide = PhotoSide.front;

    await _disableRecordingMode();
    _setError(tempMissing
        ? 'Recording was lost before it could be saved — the phone is out of '
          'storage. Free up space, then re-record this shipment.'
        : 'Could not save the recording: $error');
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
    HapticFeedback.selectionClick();
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

    // Demo build: stamp here too, not just at promotion time. A session
    // abandoned before it ever gets an order ID (never reaches
    // LocalStorageService.savePhoto()) would otherwise sit in Gallery ->
    // Drafts fully clean.
    if (AppConfig.isDemo) {
      await ImageProcessingUtils.addDemoWatermark(draft);
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
      _detachCameraListener();
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
    // Persist as the per-mode default, same mental model as aspect ratio
    // (live taps update the saved default too). Pinch-to-zoom also routes
    // through here — at most a couple writes per gesture (only on threshold
    // crossings, not continuously), not a SharedPreferences-spam risk.
    unawaited(CameraSettingsService.setZoomDefaultForMode(widget.mode, index));
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
    unawaited(_focusAnimCtrl.forward(from: 0));
    Future.delayed(const Duration(seconds: 2), () { if (mounted) setState(() => _showFocus = false); });
  }

  // ─── Barcode popup ─────────────────────────────────────────────────────

  /// User cancelled save flow — draft files stay on disk for Gallery → Drafts.
  Future<void> _retainDraftOnCancel() async {
    final hadVideo = _session.videoPath != null;
    _tempPhotoPaths.clear();
    _nextPhotoSide = PhotoSide.front;
    _session = _LiveSession();
    _session.isDraft = false;
    DebugSessionLog.log(
      location: 'live_capture_screen.dart:_retainDraftOnCancel',
      message: 'save flow cancelled — draft retained',
      hypothesisId: 'H2',
      data: {'hadVideo': hadVideo},
    );
    if (hadVideo) {
      _logActivity('draft_retained');
    }
    if (mounted && hadVideo) {
      ScaffoldMessenger.of(context).clearSnackBars();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Row(children: [
          Icon(Icons.drafts_outlined, color: RfColors.amber, size: 18),
          SizedBox(width: 8),
          Expanded(child: Text('Saved to Drafts — finish save from Gallery')),
        ]),
        duration: Duration(milliseconds: 3200),
        backgroundColor: Colors.black87,
        behavior: SnackBarBehavior.floating,
        margin: EdgeInsets.fromLTRB(16, 0, 16, 100),
      ));
    }
  }

  void _openBarcodePopup() async {
    await _disposeCameraForModal();
    if (!mounted) return;
    final result = await Navigator.of(context).push<Map<String, String?>>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => BarcodeSavePopup(mode: widget.mode),
      ),
    );

    if (result == null || result['orderId'] == null) {
      await _retainDraftOnCancel();
      // User cancelled — wait 500ms for hardware to fully release, then reinit
      if (mounted) setState(() => _phase = CapturePhase.stopped);
      await Future<void>.delayed(const Duration(milliseconds: 500));
      await _initCameraWithAudio(_audioUsedForRecording);
      return;
    }

    _session.orderId = result['orderId'];
    _session.awb = result['awb'];
    unawaited(_saveSession());
  }

  // ─── RT post-video: verdict → order-ID scan → claim photos ───────────

  /// RT only. User picks QC verdict, scans return label / order ID,
  /// then captures claim photos (QC OK: front/back; others: full set).
  Future<void> _openRtPostVideoFlow() async {
    final verdict = await showModalBottomSheet<QCVerdict>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const VerdictBottomSheet(),
    );

    if (verdict == null) {
      await _retainDraftOnCancel();
      await _disposeCameraForModal();
      if (mounted) setState(() => _phase = CapturePhase.stopped);
      await Future<void>.delayed(const Duration(milliseconds: 500));
      await _initCameraWithAudio(_audioUsedForRecording);
      return;
    }

    _session.verdict = verdict;
    _logActivity('qc_verdict', extra: {'qc': verdict.name});

    await _disposeCameraForModal();
    if (!mounted) return;
    final result = await Navigator.of(context).push<Map<String, String?>>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => BarcodeSavePopup(mode: widget.mode),
      ),
    );

    if (result == null || result['orderId'] == null) {
      await _retainDraftOnCancel();
      await _disposeCameraForModal();
      if (mounted) setState(() => _phase = CapturePhase.stopped);
      await Future<void>.delayed(const Duration(milliseconds: 500));
      await _initCameraWithAudio(_audioUsedForRecording);
      return;
    }

    _session.orderId = result['orderId'];
    _session.awb = result['awb'];

    await _runClaimPhotoSequence();
    if (!mounted) return;
    unawaited(_saveSession());
  }

  // ─── RT claim-photo flow ─────────────────────────────────────────────
  /// Manual capture only (no auto countdown) — user taps CAPTURE or Skip.
  /// If camera fails to init, saves what we have without photos.
  Future<void> _runClaimPhotoSequence() async {
    if (mounted) setState(() => _phase = CapturePhase.stopped);
    // Let barcode popup release the camera hardware before we re-open it.
    await Future<void>.delayed(const Duration(milliseconds: 500));
    await _initCameraWithAudio(false);
    if (!mounted) return;
    if (_camera == null || !_cameraReady) {
      debugPrint('Claim photo flow: camera unavailable, skipping photos');
      DebugSessionLog.log(
        location: 'live_capture_screen.dart:_runClaimPhotoSequence',
        message: 'claim camera init failed',
        hypothesisId: 'H9-claim-blank',
        data: {
          'cameraNull': _camera == null,
          'cameraReady': _cameraReady,
          'orderId': _session.orderId,
        },
      );
      return;
    }
    DebugSessionLog.log(
      location: 'live_capture_screen.dart:_runClaimPhotoSequence',
      message: 'claim camera ready',
      hypothesisId: 'H9-claim-blank',
      data: {'orderId': _session.orderId},
    );

    _inClaimFlow = true;
    _claimPreviewSettled = false;
    try {
      // Brief settle window before showing the cropped/guided preview — the
      // OverflowBox crop path can render a black texture on Android right
      // after a camera re-init. 350ms is a starting estimate matching this
      // file's other hardware-settle delays (300ms/500ms above); tune on a
      // real low/mid-tier device if the texture is still visibly black.
      // If the camera drops out during this wait, the per-photo checks
      // below (`if (... _camera == null || !_cameraReady) return;`) catch
      // it on the first iteration — `finally` still resets state correctly.
      await Future<void>.delayed(const Duration(milliseconds: 350));
      if (mounted && _camera != null && _cameraReady) {
        setState(() => _claimPreviewSettled = true);
      }

      final verdict = _session.verdict;
      // QC OK: front + back only — serial is never required to save (see
      // CaptureSession.isPhotoComplete) and is skipped from the prompt too,
      // not just made optional. Others: full sequence including serial.
      final sequence = <(PhotoSide, String)>[
        if (verdict != QCVerdict.ok) ...[
          (PhotoSide.label, 'Position RETURN LABEL in frame'),
          (PhotoSide.contents, 'Position package CONTENTS in frame'),
        ],
        (PhotoSide.front, 'Position product FRONT facing up'),
        (PhotoSide.back, 'Position product BACK facing up'),
        if (verdict != QCVerdict.ok)
          (PhotoSide.serial, 'Capture SERIAL / FPC closeup (optional)'),
      ];

      for (final (side, _) in sequence) {
        if (!mounted || _camera == null || !_cameraReady) return;
        await _captureClaimPhoto(side);
      }
    } finally {
      if (mounted) {
        setState(_clearCaptureOverlayState);
      } else {
        _clearCaptureOverlayState();
      }
    }
  }

  /// Single claim photo — manual or countdown based on settings.
  Future<void> _captureClaimPhoto(PhotoSide side) async {
    if (_camera == null || !_cameraReady || !mounted) return;

    _skipCurrentClaimPhoto = false;
    _nextPhotoSide = side;

    if (_claimCountdownEnabled && _captureCountdownSec > 0) {
      await _captureClaimPhotoWithCountdown(side);
      return;
    }

    setState(() {
      _showCountdown = true;
      _countdownSeconds = 0;
      _phase = CapturePhase.stopped;
    });

    final captured = await _waitForManualCapture();
    if (!mounted || !captured || _skipCurrentClaimPhoto) {
      if (mounted) setState(() => _showCountdown = false);
      if (!captured) debugPrint('Claim photo skipped (manual): ${side.name}');
      return;
    }
    if (mounted) setState(() => _showCountdown = false);

    await _persistClaimPhoto(side);
  }

  Future<void> _captureClaimPhotoWithCountdown(PhotoSide side) async {
    setState(() {
      _showCountdown = true;
      _countdownSeconds = _captureCountdownSec;
      _phase = CapturePhase.stopped;
    });

    for (int i = _captureCountdownSec; i > 0; i--) {
      if (!mounted || _skipCurrentClaimPhoto) break;
      setState(() => _countdownSeconds = i);
      await Future<void>.delayed(const Duration(seconds: 1));
    }

    if (!mounted) return;
    setState(() => _showCountdown = false);

    if (_skipCurrentClaimPhoto) {
      debugPrint('Claim photo skipped (countdown): ${side.name}');
      return;
    }

    await _persistClaimPhoto(side);
  }

  Future<void> _persistClaimPhoto(PhotoSide side) async {
    unawaited(HapticFeedback.mediumImpact());
    if (_soundEnabled) unawaited(NativeCameraSound.playShutter());

    try {
      final xFile = await _camera!.takePicture();
      final savedPath = await _processAndSaveTempPhoto(xFile);
      _tempPhotoPaths[side] = savedPath;
      _logActivity('photo_saved', extra: {'type': side.name});
      debugPrint('Claim photo captured: ${side.name} → $savedPath');
    } catch (e) {
      debugPrint('Claim photo capture failed for ${side.name}: $e');
    }

    if (mounted) await Future<void>.delayed(const Duration(milliseconds: 600));
  }

  // ─── Save ─────────────────────────────────────────────────────────────

  Future<void> _saveSession() async {
    if (_isSaving) return;
    // Camera already disposed in _stopRecording — no need to dispose again
    setState(() { _isSaving = true; _phase = CapturePhase.saving; });

    try {
      final orderId = _session.orderId;
      if (orderId == null) throw Exception('No order ID - barcode not captured');

      final videoPath = _session.videoPath;
      if (videoPath == null) throw Exception('No video recorded');

      // Check if video file exists
      final videoFile = File(videoPath);
      if (!await videoFile.exists()) {
        throw Exception('Video file missing at: $videoPath');
      }

      // Sanity check — _stopRecording only rejects genuinely-instant taps
      // (<1s) up front; a real recording whose file size still looked low
      // after retries is deliberately kept and reaches here instead of
      // being deleted (see _stopRecording). Unlike that earlier gate, this
      // one only throws — the draft file is untouched, so it stays
      // recoverable from Drafts even if this fires.
      final videoSize = await videoFile.length();
      if (videoSize < 50000) {
        throw Exception('Video recording was empty. Please re-record');
      }

      // Move video to final location.
      // Most paths produce a draft (see _stopRecording) — promote it via rename.
      // Legacy path: fall back to the copy-based saveVideo if no draft marker.
      String savedVideoPath;
      final isDraft = _session.isDraft;
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
            // Apply datetime watermark — respects user setting
            await ImageProcessingUtils.processPhoto(
              File(draftPhotoPath),
              orientation: CustomOrientation.portraitUp,
              addTimestamp: _timestampOnPhotos,
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
        awb: _session.awb,
        mode: widget.mode,
        sessionStartedAt: _session.sessionStartedAt ?? DateTime.now(),
        videoStartedAt: _session.videoStartedAt,
        videoStoppedAt: _session.videoStoppedAt,
        videoDurationSeconds: _session.videoDurationSeconds,
        videoPath: savedVideoPath,
        frontPhotoPath: finalPaths[PhotoSide.front],
        backPhotoPath: finalPaths[PhotoSide.back],
        labelPhotoPath: finalPaths[PhotoSide.label],
        contentsPhotoPath: finalPaths[PhotoSide.contents],
        serialPhotoPath: finalPaths[PhotoSide.serial],
        verdict: _session.verdict,
      );

      await _localStorage.writeMetaJson(session);

      _logActivity('shipment_saved', extra: {'path': savedVideoPath});

      if (mounted) {
        _showSavedToast(orderId);
        await _resetForNextCapture();
      }
    } catch (e, st) {
      _logActivity('shipment_save_failed', extra: {'error': '$e'});
      debugPrint('Save failed: $e');
      debugPrint('Stack trace: $st');
      await CrashReporting.setCaptureContext(
        mode: widget.mode,
        orderId: _session.orderId,
        phase: 'save_failed',
      );
      await CrashReporting.recordNonFatal(e, st, reason: 'save_session');
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
    // _isRecording reset here too: whichever call site reached _setError,
    // the native controller is provably no longer recording — either it
    // never started (init/permission failures), or _stopRecording's own
    // catch fired, which only happens once stopVideoRecording() itself has
    // already resolved (successfully or not) — so the real underlying
    // camera state is always "not recording" by this point. Without this,
    // the error-overlay's RETRY button re-inits a fresh CameraController
    // but the capture button stays wired to _stopRecording (isRecording
    // still true), reproducing the identical error on every retry.
    if (mounted) setState(() { _errorMessage = msg; _phase = CapturePhase.error; _isSaving = false; _isRecording = false; });
  }

  /// Brief, non-blocking confirmation that save completed.
  void _showSavedToast(String orderId) {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(
      content: Row(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.check_circle, color: RfColors.successLight, size: 18),
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
    _clearCaptureOverlayState();
    setState(() {
      _session = _LiveSession();
      _tempPhotoPaths.clear();
      _isRecording = false;
      _isSaving = false;
      _errorMessage = null;
      _camera = null;
      _cameraReady = false;
      _phase = CapturePhase.loading;
    });
    _logActivity('capture_reset');
    await _initCamera();
  }

  // ─── Helpers ─────────────────────────────────────────────────────────

  String get _elapsedLabel {
    final s = _stopwatch.elapsed.inSeconds;
    return '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';
  }

  /// Short label for the collapsed ratio button — matches the option text
  /// used in the expanded strip (Samsung reference: plain "3:4"/"9:16" etc.,
  /// not a descriptive sentence).
  String get _selectedAspectLabel {
    if ((_aspectRatio - _aspect11).abs() < 0.001) return '1:1';
    if ((_aspectRatio - _aspect34).abs() < 0.001) return '3:4';
    return '16:9';
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
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: RfColors.card,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Discard recording?', style: TextStyle(color: Colors.white)),
          content: const Text(
            'Recording is in progress. Close anyway?',
            style: TextStyle(color: RfColors.textSecondary, fontSize: 13),
          ),
          actions: [
            RfButton.secondary(
              label: 'Cancel',
              onPressed: () => Navigator.pop(ctx),
            ),
            RfButton.danger(
              label: 'Discard',
              onPressed: () { Navigator.pop(ctx); Navigator.pop(context); },
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
    if (_phase == CapturePhase.error) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(child: Stack(children: [_buildErrorOverlay()])),
      );
    }

    // Camera-loading / handoff — never show draft shell during claim re-init
    if (_camera == null || !_cameraReady) {
      final waitingForLabel =
          _session.videoPath != null &&
          _session.orderId == null &&
          _phase == CapturePhase.stopped;
      if (waitingForLabel) {
        _logBuildBranch('post_stop_draft_shell');
        return _buildPostStopDraftShell(accent);
      }
      _logBuildBranch('camera_loading');
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
    _logBuildBranch(showPreview ? 'camera_preview' : 'no_preview');

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            // Camera preview — only shown when active
            if (showPreview)
              Positioned.fill(
                child: RepaintBoundary(
                  child: GestureDetector(
                    onScaleUpdate: _handleScaleUpdate,
                    onTapUp: _onTapFocus,
                    child: _useFullBleedPreview
                        ? _buildRecordingPreview()
                        : _buildCroppedPreview(),
                  ),
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

            // Aspect ratio info — removed (frame guides only, no top strip)

            // REC indicator
            if (_isRecording) _buildRecIndicator(),

            // Countdown overlay
            if (_showCountdown) _buildCountdownOverlay(accent),

            // Saving overlay
            if (_phase == CapturePhase.saving) _buildSavingOverlay(),

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
            if (_phase != CapturePhase.saving
                && !(_showCountdown && _captureCountdownSec > 0 && !_inClaimFlow))
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
  /// NOTE: the crop is intentionally kept IDENTICAL during idle and active
  /// recording (`_buildCroppedPreview`'s `effectiveCropped` does not check
  /// `_isRecording`) — the user previously saw the frame change shape the
  /// instant they hit record; this widget's job is to hold that steady.
  /// The camera plugin still records native 16:9 regardless of the crop
  /// shown here — the crop is preview-only chrome, applied to captured
  /// photos separately (see `ImageProcessingUtils.cropToAspectRatio`).
  ///
  /// `_buildRecordingPreview` below is a SEPARATE full-bleed fallback used
  /// only for claim-flow re-init and the post-stop draft state (see
  /// `_useFullBleedPreview`) — not for ordinary active recording — because
  /// the OverflowBox crop path can render a black texture on Android right
  /// after a camera re-init in those specific states.
  Widget _buildRecordingPreview() {
    return ColoredBox(
      color: Colors.black,
      child: Center(
        child: CameraPreview(_camera!),
      ),
    );
  }

  /// Shown when video draft exists but camera was released for label modal.
  Widget _buildPostStopDraftShell(Color accent) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.check_circle_outline, color: accent, size: 48),
                const SizedBox(height: 16),
                Text(
                  widget.mode == CaptureMode.rt
                      ? 'Return video saved'
                      : 'Pack video saved',
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  widget.mode == CaptureMode.rt
                      ? 'Choose QC reason and scan label below'
                      : 'Scan label to finish save',
                  style: const TextStyle(color: Colors.white54, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCroppedPreview() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final availW = constraints.maxWidth;
        final availH = constraints.maxHeight;

        // Keep the same on-screen frame during recording as in photo idle.
        final effectiveCropped = _isAspectCropped;

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

        return ColoredBox(
          color: Colors.black,
          child: Stack(
            fit: StackFit.expand,
            children: [
              Center(
                child: ClipRect(
                  child: SizedBox(
                    width: vpW,
                    height: vpH,
                    child: OverflowBox(
                      minWidth: previewW,
                      maxWidth: previewW,
                      minHeight: previewH,
                      maxHeight: previewH,
                      child: CameraPreview(_camera!),
                    ),
                  ),
                ),
              ),
              if (effectiveCropped) _buildFrameGuides(vpW, vpH, availW, availH),
            ],
          ),
        );
      },
    );
  }

  /// White corner brackets on the active photo frame (letterbox stays solid black).
  Widget _buildFrameGuides(double vpW, double vpH, double availW, double availH) {
    final left = (availW - vpW) / 2;
    final top = (availH - vpH) / 2;
    const len = 26.0;
    const stroke = 2.5;
    const color = Colors.white;

    Widget corner(Alignment align) {
      return Align(
        alignment: align,
        child: SizedBox(
          width: len,
          height: len,
          child: CustomPaint(
            painter: _FrameCornerPainter(align, color, stroke),
          ),
        ),
      );
    }

    return Positioned(
      left: left,
      top: top,
      width: vpW,
      height: vpH,
      child: Stack(
        children: [
          // Ratio label moved to the bottom collapsible control
          // (_buildRatioControl) — no need to duplicate it here too.
          corner(Alignment.topLeft),
          corner(Alignment.topRight),
          corner(Alignment.bottomLeft),
          corner(Alignment.bottomRight),
        ],
      ),
    );
  }

  // ─── Top bar ─────────────────────────────────────────────────────────

  /// No-blur "floating" chrome — solid fill + border + shadow, same visual
  /// language as [RfIconButton] (no `BackdropFilter` anywhere). Replaces
  /// the old blurred `_cameraChromeBar`/`RfGlassPill`/`RfGlassContainer`
  /// panels on this screen: a shared translucent bar reads as heavy chrome
  /// over a live camera preview, so each control now floats on its own
  /// solid pill instead. Tint alpha is intentionally higher than the old
  /// glass pills' (~0.22) since there's no blur left to soften a busy
  /// moving background behind low-opacity text.
  Widget _floatingPill({
    required Widget child,
    EdgeInsetsGeometry padding = const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    Color? tint,
    Color? borderColor,
    double radius = RfRadius.button,
    VoidCallback? onTap,
  }) {
    final pill = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: tint ?? RfColors.card.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: borderColor ?? RfGlass.border()),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.25), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: child,
    );
    if (onTap == null) return pill;
    return Material(
      color: Colors.transparent,
      child: InkWell(onTap: onTap, borderRadius: BorderRadius.circular(radius), child: pill),
    );
  }

  Widget _buildTopBar(Color accent) {
    return Positioned(
      top: 0, left: 0, right: 0,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: _buildTopBarRow(accent),
      ),
    );
  }

  Widget _buildTopBarRow(Color accent) {
    return Row(
      children: [
        RfIconButton(icon: Icons.close_rounded, size: 38, onPressed: _close),
        const SizedBox(width: 6),
        _floatingPill(
          tint: accent.withValues(alpha: 0.85),
          borderColor: accent.withValues(alpha: 0.6),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          radius: 12,
          child: Text(
            widget.mode == CaptureMode.pk ? 'PK MODE' : 'RT MODE',
            style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5),
          ),
        ),
      ],
    );
  }

  /// Aspect button tap handler. Persists the choice but is a NO-OP for the
  /// preview during recording (since video is always recorded at native
  /// 16:9 by the camera plugin — see [_buildCroppedPreview] comment).
  Future<void> _onAspectTap(String label, double ratio) async {
    if (_isRecording) return;
    final normalized = CameraSettingsService.normalizeAspect(ratio);
    if ((_aspectRatio - normalized).abs() < 0.001) return;
    setState(() => _aspectRatio = normalized);
    await CameraSettingsService.setAspectDefaultForMode(widget.mode, normalized);
  }

  Widget _buildRtInstructionBanner(Color accent) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: _floatingPill(
        tint: accent.withValues(alpha: 0.85),
        borderColor: accent.withValues(alpha: 0.6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        radius: 14,
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.videocam_rounded, color: Colors.white, size: 22),
            SizedBox(width: 10),
            Flexible(
              child: Text(
                'Tap to record return video',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
                  shadows: [Shadow(color: Colors.black54, blurRadius: 2, offset: Offset(0, 1))],
                ),
              ),
            ),
          ],
        ),
      ),
    );
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
      child: _floatingPill(
        tint: accent.withValues(alpha: 0.85),
        borderColor: accent.withValues(alpha: 0.6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        radius: 14,
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
                  shadows: [Shadow(color: Colors.black54, blurRadius: 2, offset: Offset(0, 1))],
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
    if (_phase == CapturePhase.loading) return const SizedBox.shrink();

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
        const RfRecordingPulse(size: 10, color: RfColors.recording),
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

    final instructionColor = _inClaimFlow
        ? RfColors.warning
        : (widget.mode == CaptureMode.pk ? RfColors.pkAccent : RfColors.rtAccent);

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
          child: RfGlassContainer(
            margin: const EdgeInsets.symmetric(horizontal: 24),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            radius: 14,
            tint: RfGlass.fill(0.4),
            borderColor: RfGlass.border(0.2),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              if (_countdownSeconds > 0)
                Text(
                  '$_countdownSeconds',
                  style: TextStyle(
                    fontSize: 120,
                    fontWeight: FontWeight.bold,
                    color: RfColors.textPrimary,
                    height: 1,
                  ),
                ),
              if (_countdownSeconds > 0) const SizedBox(height: 12),
              Text(
                instruction,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: instructionColor.withValues(alpha: 0.95),
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  height: 1.25,
                ),
              ),
              if (_captureCountdownSec <= 0 || _inClaimFlow) ...[
                const SizedBox(height: 8),
                Text(
                  'Tap CAPTURE below',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.85),
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ]),
          ),
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
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 36),
        child: _buildBottomControlsColumn(accent),
      ),
    );
  }

  Widget _buildBottomControlsColumn(Color accent) {
    return Column(mainAxisSize: MainAxisSize.min, children: [
          // ── RT claim-flow Skip pill ─────────────────────────────────
          // Lives at the TOP of the bottom-controls column so it is never
          // obscured by the capture button. Previously rendered as an
          // absolute Positioned widget which got hidden behind the bigger
          // capture button — user reported "skip button chup raha hai".
          //
          // Design-system audit (2026-08-14): deliberately NOT migrated to
          // RfButton.secondary despite that being the documented SKIP
          // variant — this pill's white+shadow text was a proven fix for
          // legibility over the live, brightness-varying camera feed
          // (RfButton's plain white text has no shadow and would risk
          // washing out again on bright backgrounds). Haptic is fired from
          // _onSkipManualCapture() directly instead of getting it for free
          // from RfButton. Keep this exception — don't "simplify" it back.
          if (_inClaimFlow)
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: _floatingPill(
                onTap: _onSkipManualCapture,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                // White + shadow, not textSecondary grey — this pill sits
                // directly over the live, brightness-varying camera feed;
                // dim grey washes out unreadable on bright backgrounds.
                // Matches the PK/RT instruction banners' pattern.
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.skip_next_rounded, color: Colors.white, size: 18,
                        shadows: [Shadow(color: Colors.black54, blurRadius: 2, offset: Offset(0, 1))]),
                    SizedBox(width: 8),
                    Text(
                      'SKIP THIS PHOTO',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.4,
                        shadows: [Shadow(color: Colors.black54, blurRadius: 2, offset: Offset(0, 1))],
                      ),
                    ),
                  ],
                ),
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
              && _phase == CapturePhase.stopped
              && !_showCountdown
              && !_inClaimFlow)
            _buildPkInstructionBanner(accent),

          if (!_isRecording
              && widget.mode == CaptureMode.rt
              && _phase == CapturePhase.stopped
              && _session.videoPath == null
              && !_showCountdown
              && !_inClaimFlow)
            _buildRtInstructionBanner(accent),

          // Mode instructions during recording — small solid pill (not bare
          // text) so it stays legible floating directly over moving video,
          // now that there's no shared bottom-bar background behind it.
          if (_isRecording)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: _floatingPill(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                radius: 14,
                child: Text(
                  widget.mode == CaptureMode.pk
                      ? 'Pack the product. Tap STOP when done.'
                      : 'Inspect the return. Tap STOP when done.',
                  style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                  textAlign: TextAlign.center,
                ),
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
            _floatingPill(
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 8),
              borderColor: RfColors.recording.withValues(alpha: 0.6),
              radius: 18,
              child: const Text(
                'TAP TO STOP',
                style: TextStyle(
                  color: RfColors.recording,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.5,
                ),
              ),
            ),

          const SizedBox(height: 16),

          // Frame-ratio control — collapsible, Samsung-style plain-text
          // strip (see _buildRatioControl).
          _buildRatioControl(accent),

          const SizedBox(height: 10),

          // Zoom + mic — same plain-text-in-glass-pill visual language as
          // the ratio control above.
          _buildZoomMicPill(accent),
        ]);
  }

  /// Shared plain-text pill option for the ratio strip and zoom row —
  /// active option in the mode accent color, inactive in white. No
  /// per-option box/border, matching the Samsung reference screenshots.
  Widget _pillOption(String label, bool active, Color accent, VoidCallback onTap, {double fontSize = 14}) {
    return GestureDetector(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        child: Text(
          label,
          style: TextStyle(
            color: active ? accent : Colors.white,
            fontSize: fontSize,
            fontWeight: active ? FontWeight.w800 : FontWeight.w600,
          ),
        ),
      ),
    );
  }

  /// Collapsible frame-ratio control. Collapsed: a single pill showing the
  /// active ratio. Tap → expands into the 3:4 / 1:1 / 16:9 option strip;
  /// tapping an option applies it and collapses back. Locked (inert, with a
  /// lock icon) while recording — the frame can't change mid-clip since the
  /// saved video is a single file, not a per-segment crop. Previously this
  /// vanished entirely (SizedBox.shrink) during recording, which read as
  /// "frame switching is broken" rather than "frame is intentionally locked".
  Widget _buildRatioControl(Color accent) {
    if (_isRecording) {
      return _floatingPill(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        radius: 18,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.lock_outline_rounded, color: Colors.white54, size: 14),
          const SizedBox(width: 6),
          Text(_selectedAspectLabel, style: const TextStyle(color: Colors.white54, fontSize: 13, fontWeight: FontWeight.w700)),
        ]),
      );
    }

    if (!_aspectStripExpanded) {
      return _floatingPill(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        radius: 18,
        onTap: () => setState(() => _aspectStripExpanded = true),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.crop_free_rounded, color: Colors.white, size: 15),
          const SizedBox(width: 6),
          Text(_selectedAspectLabel, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700)),
        ]),
      );
    }

    void select(String label, double ratio) {
      _onAspectTap(label, ratio);
      setState(() => _aspectStripExpanded = false);
    }

    return _floatingPill(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      radius: 22,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        _pillOption('3:4', (_aspectRatio - _aspect34).abs() < 0.001, accent, () => select('3:4', _aspect34), fontSize: 15),
        _pillOption('1:1', (_aspectRatio - _aspect11).abs() < 0.001, accent, () => select('1:1', _aspect11), fontSize: 15),
        _pillOption('16:9', (_aspectRatio - _aspectFull).abs() < 0.001, accent, () => select('16:9', _aspectFull), fontSize: 15),
      ]),
    );
  }

  /// Zoom (1×/2×/3×) + mic toggle, in the same glass pill language as the
  /// ratio control. Zoom stays visible in every phase, including claim photo.
  Widget _buildZoomMicPill(Color accent) {
    return _floatingPill(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      radius: 20,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        _ZoomPillButton(label: '1×', active: _currentZoomIndex == 0, accent: accent, onTap: () => _setZoomByIndex(0)),
        _ZoomPillButton(label: '2×', active: _currentZoomIndex == 1, accent: accent, onTap: () => _setZoomByIndex(1)),
        _ZoomPillButton(label: '3×', active: _currentZoomIndex == 2, accent: accent, onTap: () => _setZoomByIndex(2)),
        const SizedBox(width: 6),
        Container(width: 1, height: 20, color: RfGlass.border(0.2)),
        const SizedBox(width: 6),
        _MicToggleButton(
          enabled: _micEnabled,
          disabled: _isCameraTransitioning,
          onTap: _isCameraTransitioning ? null : _toggleMic,
        ),
      ]),
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
                  onPressed: () async {
                    await openAppSettings();
                  },
                ),
              RfButton.secondary(
                label: 'CLOSE',
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

/// Zoom pill option (1×/2×/3×) — mirrors [_MicToggleButton]'s press/haptic
/// pattern (200ms scale-to-0.95 + selectionClick) so zoom feels consistent
/// with the rest of the camera chrome. Kept separate from the shared
/// `_pillOption` helper (used by the aspect-ratio strip too) so this
/// doesn't risk regressing that control — zoom just needed a bigger tap
/// target + haptics + motion, nothing about the ratio strip's behavior.
class _ZoomPillButton extends StatefulWidget {
  final String label;
  final bool active;
  final Color accent;
  final VoidCallback onTap;
  const _ZoomPillButton({required this.label, required this.active, required this.accent, required this.onTap});

  @override
  State<_ZoomPillButton> createState() => _ZoomPillButtonState();
}

class _ZoomPillButtonState extends State<_ZoomPillButton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: RfDuration.press);
    _scale = Tween<double>(begin: 1.0, end: 0.95)
        .animate(CurvedAnimation(parent: _ctrl, curve: RfDuration.pressCurve));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _ctrl.forward(),
      onTapUp: (_) => _ctrl.reverse(),
      onTapCancel: () => _ctrl.reverse(),
      onTap: () {
        HapticFeedback.selectionClick();
        widget.onTap();
      },
      child: ScaleTransition(
        scale: _scale,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              child: Text(
                widget.label,
                style: TextStyle(
                  color: widget.active ? widget.accent : Colors.white,
                  fontSize: 14,
                  fontWeight: widget.active ? FontWeight.w800 : FontWeight.w600,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _FrameCornerPainter extends CustomPainter {
  final Alignment align;
  final Color color;
  final double stroke;

  _FrameCornerPainter(this.align, this.color, this.stroke);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = stroke
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final w = size.width;
    final h = size.height;
    if (align == Alignment.topLeft) {
      canvas.drawLine(Offset(0, 0), Offset(w, 0), paint);
      canvas.drawLine(Offset(0, 0), Offset(0, h), paint);
    } else if (align == Alignment.topRight) {
      canvas.drawLine(Offset(0, 0), Offset(w, 0), paint);
      canvas.drawLine(Offset(w, 0), Offset(w, h), paint);
    } else if (align == Alignment.bottomLeft) {
      canvas.drawLine(Offset(0, h), Offset(w, h), paint);
      canvas.drawLine(Offset(0, 0), Offset(0, h), paint);
    } else {
      canvas.drawLine(Offset(0, h), Offset(w, h), paint);
      canvas.drawLine(Offset(w, 0), Offset(w, h), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _FrameCornerPainter old) =>
      old.align != align || old.color != color;
}

/// Mutable working state of one capture session — typed so a mistyped field
/// is a compile error, not a silent runtime null (was an untyped map).
class _LiveSession {
  String? orderId;
  String? awb;
  QCVerdict? verdict;
  String? videoPath;
  bool isDraft = false;
  DateTime? sessionStartedAt;
  DateTime? videoStartedAt;
  DateTime? videoStoppedAt;
  int? videoDurationSeconds;
}
