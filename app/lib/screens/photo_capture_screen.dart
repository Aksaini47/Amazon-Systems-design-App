import 'dart:async';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:native_camera_sound/native_camera_sound.dart';
import '../services/camera_settings_service.dart';
import '../theme/rf_colors.dart';
import '../utils/volume_button_service.dart';
import '../widgets/rf_button.dart';

/// Opens the app's own camera for ONE photo and returns it, or null when
/// cancelled. Used by "Replace photo" and by capturing a missing photo on a
/// draft, so the shot is taken with the same camera, look and settings as the
/// rest of the app instead of handing over to the phone's camera app (which
/// also left the app in the background, behind another app's UI).
///
/// [title] names what is being shot ("Product front").
Future<XFile?> captureInAppPhoto(BuildContext context, {required String title}) {
  return Navigator.of(context).push<XFile>(
    MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) => PhotoCaptureScreen(title: title),
    ),
  );
}

class PhotoCaptureScreen extends StatefulWidget {
  final String title;
  const PhotoCaptureScreen({super.key, required this.title});

  @override
  State<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends State<PhotoCaptureScreen> with WidgetsBindingObserver {
  static const _volumeKey = 'photo_capture_screen';

  CameraController? _cam;
  bool _ready = false;
  String? _error;
  int _initGen = 0;

  XFile? _shot;
  bool _capturing = false;
  bool _soundEnabled = true;

  FlashMode _flash = FlashMode.off;

  double _minZoom = 1.0;
  double _maxZoom = 1.0;
  double _zoom = 1.0;
  double _zoomAtScaleStart = 1.0;

  Offset? _focusAt;
  Timer? _focusTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // The photo is processed as portrait-up on save (see savePhoto), so shoot
    // portrait with the capture orientation pinned, like the capture screen.
    SystemChrome.setPreferredOrientations(const [DeviceOrientation.portraitUp]);
    VolumeButtonService().registerListener(_volumeKey, (event) {
      if (!mounted || !(ModalRoute.of(context)?.isCurrent ?? false)) return;
      if (event == 1 || event == 2) unawaited(_shoot());
    });
    unawaited(_init());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    VolumeButtonService().unregisterListener(_volumeKey);
    _focusTimer?.cancel();
    final cam = _cam;
    _cam = null;
    unawaited(cam?.dispose());
    // A shot that was never used is a stray temp file.
    _discardShot();
    // Restore what the rest of the app expects (see live_capture_screen).
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // The camera must be released when the app is not in front (standard
    // camera-plugin lifecycle) and taken again on return.
    if (state == AppLifecycleState.inactive) {
      _initGen++; // a start still in flight is now out of date
      final cam = _cam;
      if (cam == null) return;
      _cam = null;
      if (mounted) setState(() => _ready = false);
      unawaited(cam.dispose());
    } else if (state == AppLifecycleState.resumed && _cam == null && _shot == null) {
      unawaited(_init());
    }
  }

  Future<void> _init() async {
    // Every start gets a number; a start that is no longer the latest (the app
    // was backgrounded, or Retry was tapped) drops out quietly instead of
    // fighting the newer one over the camera.
    final gen = ++_initGen;
    bool stale() => !mounted || gen != _initGen;
    if (mounted) setState(() { _error = null; _ready = false; });
    CameraController? controller;
    try {
      _soundEnabled = await CameraSettingsService.getSound();
      final preset = await CameraSettingsService.getResolution();
      final cameras = await availableCameras();
      if (stale()) return;
      if (cameras.isEmpty) {
        _fail('No camera found on this phone.');
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      controller = CameraController(back, preset, enableAudio: false);
      _cam = controller;
      await controller.initialize();
      if (stale() || _cam != controller) {
        if (_cam == controller) _cam = null;
        await controller.dispose();
        return;
      }
      try {
        await controller.lockCaptureOrientation(DeviceOrientation.portraitUp);
      } catch (e) {
        debugPrint('lockCaptureOrientation skipped (non-fatal): $e');
      }
      final minZ = await controller.getMinZoomLevel();
      final maxZ = await controller.getMaxZoomLevel();
      try {
        await controller.setFlashMode(_flash);
      } catch (e) {
        debugPrint('setFlashMode skipped (non-fatal): $e');
      }
      if (stale() || _cam != controller) {
        if (_cam == controller) _cam = null;
        await controller.dispose();
        return;
      }
      setState(() {
        _minZoom = minZ;
        _maxZoom = maxZ < minZ ? minZ : maxZ.clamp(minZ, 8.0);
        _zoom = minZ;
        _ready = true;
      });
    } on CameraException catch (e) {
      debugPrint('Photo camera init failed: $e');
      if (stale()) return;
      final denied = e.code.toLowerCase().contains('denied');
      _fail(denied
          ? 'Camera permission is off. Allow it for RF Logger in the phone settings.'
          : 'Camera busy — tap Retry.');
    } catch (e) {
      debugPrint('Photo camera init failed: $e');
      if (stale()) return;
      _fail('Camera error: $e');
    }
  }

  void _fail(String message) {
    final cam = _cam;
    _cam = null;
    unawaited(cam?.dispose());
    if (mounted) setState(() { _error = message; _ready = false; });
  }

  // ── Shooting ────────────────────────────────────────────────────────────

  Future<void> _shoot() async {
    final cam = _cam;
    if (cam == null || !_ready || _capturing || _shot != null) return;
    setState(() => _capturing = true);
    unawaited(HapticFeedback.mediumImpact());
    if (_soundEnabled) unawaited(_playShutter());
    try {
      final shot = await cam.takePicture();
      // Freeze the preview on the moment of the shot while it is reviewed.
      try {
        await cam.pausePreview();
      } catch (_) {}
      if (!mounted) {
        await _deleteQuietly(shot.path);
        return;
      }
      setState(() {
        _shot = shot;
        _capturing = false;
      });
    } catch (e) {
      debugPrint('takePicture failed: $e');
      if (!mounted) return;
      setState(() => _capturing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not take the photo — try again')),
      );
    }
  }

  Future<void> _playShutter() async {
    try {
      await NativeCameraSound.playShutter();
    } catch (_) {}
  }

  Future<void> _deleteQuietly(String path) async {
    try {
      await File(path).delete();
    } catch (_) {}
  }

  void _discardShot() {
    final shot = _shot;
    _shot = null;
    if (shot != null) unawaited(_deleteQuietly(shot.path));
  }

  Future<void> _retake() async {
    final cam = _cam;
    _discardShot();
    try {
      await cam?.resumePreview();
    } catch (e) {
      debugPrint('resumePreview failed: $e');
    }
    if (mounted) setState(() {});
  }

  void _usePhoto() {
    final shot = _shot;
    if (shot == null) return;
    // Handed to the caller, who now owns the file.
    _shot = null;
    Navigator.of(context).pop(shot);
  }

  // ── Flash / zoom / focus ────────────────────────────────────────────────

  Future<void> _cycleFlash() async {
    final next = switch (_flash) {
      FlashMode.off => FlashMode.auto,
      FlashMode.auto => FlashMode.torch,
      _ => FlashMode.off,
    };
    setState(() => _flash = next);
    try {
      await _cam?.setFlashMode(next);
    } catch (e) {
      debugPrint('setFlashMode failed: $e');
    }
  }

  IconData get _flashIcon => switch (_flash) {
        FlashMode.off => Icons.flash_off_rounded,
        FlashMode.auto => Icons.flash_auto_rounded,
        _ => Icons.flash_on_rounded,
      };

  String get _flashLabel => switch (_flash) {
        FlashMode.off => 'Flash off',
        FlashMode.auto => 'Flash auto',
        _ => 'Torch on',
      };

  void _applyZoom(double z) {
    final target = z.clamp(_minZoom, _maxZoom);
    if ((target - _zoom).abs() < 0.01) return;
    setState(() => _zoom = target);
    unawaited(_setZoom(target));
  }

  Future<void> _setZoom(double level) async {
    try {
      await _cam?.setZoomLevel(level);
    } catch (e) {
      debugPrint('setZoomLevel failed: $e');
    }
  }

  Future<void> _focusTo(Offset local, Size box) async {
    final cam = _cam;
    if (cam == null || !_ready || box.isEmpty) return;
    setState(() => _focusAt = local);
    _focusTimer?.cancel();
    _focusTimer = Timer(const Duration(milliseconds: 1100), () {
      if (mounted) setState(() => _focusAt = null);
    });
    final p = Offset(
      (local.dx / box.width).clamp(0.0, 1.0),
      (local.dy / box.height).clamp(0.0, 1.0),
    );
    try {
      await cam.setFocusPoint(p);
      await cam.setExposurePoint(p);
    } catch (e) {
      debugPrint('Focus point not supported: $e');
    }
  }

  // ── Build ───────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final reviewing = _shot != null;
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            _buildTopBar(reviewing),
            Expanded(child: Center(child: _buildViewfinder(reviewing))),
            _buildBottomBar(reviewing),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar(bool reviewing) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: Row(
        children: [
          RfIconButton(
            icon: Icons.close_rounded,
            tooltip: 'Cancel',
            size: 48,
            onPressed: () => Navigator.of(context).maybePop(),
          ),
          Expanded(
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white12,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  reviewing ? 'Check the photo' : widget.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: RfColors.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ),
          // Keeps the title centred when there is no flash button.
          if (reviewing || !_ready)
            const SizedBox(width: 48)
          else
            RfIconButton(
              icon: _flashIcon,
              tooltip: _flashLabel,
              size: 48,
              color: _flash == FlashMode.off ? RfColors.textPrimary : RfColors.amber,
              onPressed: _cycleFlash,
            ),
        ],
      ),
    );
  }

  Widget _buildViewfinder(bool reviewing) {
    if (_error != null) return _buildError();
    final cam = _cam;
    if (!_ready || cam == null || !cam.value.isInitialized) {
      return const CircularProgressIndicator(strokeWidth: 2, color: RfColors.textMuted);
    }

    // The saved photo is the full 3:4 sensor frame, so the viewfinder shows
    // exactly 3:4 — what is on screen is what gets saved, nothing cropped off.
    return LayoutBuilder(builder: (context, constraints) {
      var w = constraints.maxWidth;
      var h = w * 4 / 3;
      if (h > constraints.maxHeight) {
        h = constraints.maxHeight;
        w = h * 3 / 4;
      }
      final box = Size(w, h);
      final preview = cam.value.previewSize;
      return SizedBox(
        width: w,
        height: h,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (reviewing)
                Image.file(
                  File(_shot!.path),
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) =>
                      const Center(child: Icon(Icons.broken_image, color: Colors.white24, size: 48)),
                )
              else
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapUp: (d) => _focusTo(d.localPosition, box),
                  onScaleStart: (_) => _zoomAtScaleStart = _zoom,
                  onScaleUpdate: (d) {
                    if (d.pointerCount > 1) _applyZoom(_zoomAtScaleStart * d.scale);
                  },
                  child: ClipRect(
                    child: FittedBox(
                      fit: BoxFit.cover,
                      child: SizedBox(
                        width: preview?.height ?? 1,
                        height: preview?.width ?? 1,
                        child: CameraPreview(cam),
                      ),
                    ),
                  ),
                ),
              if (!reviewing && _focusAt != null)
                Positioned(
                  left: _focusAt!.dx - 30,
                  top: _focusAt!.dy - 30,
                  child: IgnorePointer(
                    child: Container(
                      width: 60,
                      height: 60,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: RfColors.amber, width: 2),
                      ),
                    ),
                  ),
                ),
              if (!reviewing && _maxZoom > _minZoom && (_zoom - _minZoom) > 0.05)
                Positioned(
                  bottom: 10,
                  left: 0,
                  right: 0,
                  child: IgnorePointer(
                    child: Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          '${_zoom.toStringAsFixed(1)}×',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              Positioned.fill(
                child: IgnorePointer(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: reviewing ? RfColors.successLight : RfColors.amber,
                        width: 2,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    });
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.no_photography_outlined, color: RfColors.textMuted, size: 48),
          const SizedBox(height: 12),
          Text(
            _error!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: RfColors.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: 16),
          RfButton.primary(label: 'Retry', icon: Icons.refresh_rounded, onPressed: _init),
        ],
      ),
    );
  }

  Widget _buildBottomBar(bool reviewing) {
    if (reviewing) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Row(
          children: [
            Expanded(
              child: RfButton.secondary(
                label: 'Retake',
                icon: Icons.refresh_rounded,
                onPressed: _retake,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: RfButton.primary(
                label: 'Use photo',
                icon: Icons.check_rounded,
                onPressed: _usePhoto,
              ),
            ),
          ],
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
      child: Center(child: _Shutter(busy: _capturing, enabled: _ready, onPressed: _shoot)),
    );
  }
}

/// Big round shutter. A 76 dp target; the ring pulses in while the shot is
/// being taken so a second tap is not mistaken for a miss.
class _Shutter extends StatelessWidget {
  final bool busy;
  final bool enabled;
  final VoidCallback onPressed;
  const _Shutter({required this.busy, required this.enabled, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Take photo',
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: enabled && !busy ? onPressed : null,
        child: AnimatedOpacity(
          opacity: enabled ? 1 : 0.4,
          duration: const Duration(milliseconds: 150),
          child: Container(
            width: 76,
            height: 76,
            padding: const EdgeInsets.all(5),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 4),
            ),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 120),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: busy ? RfColors.amber : Colors.white,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
