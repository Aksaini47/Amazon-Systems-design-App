import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import 'package:native_camera_sound/native_camera_sound.dart';
import 'package:sensors_plus/sensors_plus.dart';
import '../services/api_service.dart';
import '../theme/rf_colors.dart';
import '../services/camera_settings_service.dart';
import '../utils/volume_button_service.dart';
import '../utils/image_processing.dart';

class RecordScreen extends StatefulWidget {
  final String videoType;
  final String? orderId;
  final String? productTitle;
  final String? fbaShipmentId;
  final int? fbaBoxNumber;

  const RecordScreen({
    super.key,
    required this.videoType,
    this.orderId,
    this.productTitle,
    this.fbaShipmentId,
    this.fbaBoxNumber,
  });

  @override
  State<RecordScreen> createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> with TickerProviderStateMixin {
  // Camera
  CameraController? _camera;
  List<CameraDescription> _cameras = [];
  bool _cameraReady = false;
  bool _isFront = false;

  // Recording state
  bool _recording = false;
  bool _isPaused = false;
  bool _uploading = false;
  bool _videoMode = true;

  // Settings
  ResolutionPreset _resolution = ResolutionPreset.veryHigh;
  int _fps = 30;
  bool _micEnabled = true;
  bool _soundEnabled = true;
  bool _timestampImage = false;
  bool _aspectEnabled = false;
  String? _prefix;
  bool _flashOn = false;

  // Zoom
  double _zoom = 0;
  double _minZoom = 1.0;
  double _maxZoom = 8.0;

  // Focus
  bool _showFocus = false;
  double _focusX = 0, _focusY = 0;

  // Orientation
  StreamSubscription<AccelerometerEvent>? _accelSub;
  CustomOrientation _orientation = CustomOrientation.portraitUp;
  double _orientTurns = 0;

  // Timer
  final _stopwatch = Stopwatch();
  Timer? _timerTick;

  // Order
  late String? _orderId;
  late String? _productTitle;
  bool get _isFbaMode => widget.fbaShipmentId != null;

  // Animations
  late AnimationController _focusAnimCtrl;
  late Animation<double> _focusAnim;
  late AnimationController _pulseCtrl;

  @override
  void initState() {
    super.initState();
    _orderId = widget.orderId;
    _productTitle = widget.productTitle;

    _focusAnimCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 600));
    _focusAnim = Tween(begin: 1.2, end: 0.9).animate(CurvedAnimation(parent: _focusAnimCtrl, curve: Curves.easeOut));
    _pulseCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))..repeat(reverse: true);

    _loadSettings();
    _setupAccelerometer();
    _setupVolumeButtons();
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp, DeviceOrientation.portraitDown]);
  }

  Future<void> _loadSettings() async {
    _resolution = await CameraSettingsService.getResolution();
    _fps = await CameraSettingsService.getFps();
    _micEnabled = await CameraSettingsService.getAudio();
    _soundEnabled = await CameraSettingsService.getSound();
    _timestampImage = await CameraSettingsService.getTimestampImage();
    _aspectEnabled = await CameraSettingsService.getAspectEnabled();
    _prefix = await CameraSettingsService.getPrefixOption();
    if (mounted) setState(() {});
    _initCamera();
  }

  void _setupAccelerometer() {
    _accelSub = accelerometerEventStream(samplingPeriod: SensorInterval.normalInterval).listen((e) {
      final orient = ImageProcessingUtils.orientationFromAccelerometer(e.x, e.y, e.z);
      double turns = 0;
      switch (orient) {
        case CustomOrientation.portraitDown: turns = 2; break;
        case CustomOrientation.landscapeRight: turns = 1; break;
        case CustomOrientation.landscapeLeft: turns = -1; break;
        case CustomOrientation.portraitUp: turns = 0; break;
      }
      if (_orientation != orient) {
        setState(() { _orientation = orient; _orientTurns = turns; });
      }
    });
  }

  void _setupVolumeButtons() {
    VolumeButtonService().registerListener('record_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (_uploading) return;

      if (event == 1) {
        if (_videoMode) _toggleRecording(); else _capturePhoto();
      } else if (event == 2) {
        if (_recording) _togglePause(); else setState(() => _videoMode = !_videoMode);
      }
    });
  }

  Future<void> _initCamera() async {
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;
    _cameras = await availableCameras();
    if (_cameras.isEmpty) return;

    final cam = _isFront
        ? _cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.front, orElse: () => _cameras.first)
        : _cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => _cameras.first);

    _camera = CameraController(cam, _resolution, enableAudio: _micEnabled, fps: _fps);

    try {
      await _camera!.initialize();
      _minZoom = await _camera!.getMinZoomLevel();
      _maxZoom = await _camera!.getMaxZoomLevel();
      if (mounted) setState(() => _cameraReady = true);
    } catch (e) {
      debugPrint('Camera init error: $e — retrying...');
      await _camera?.dispose();
      await Future.delayed(const Duration(milliseconds: 1500));
      if (!mounted) return;
      _camera = CameraController(cam, _resolution, enableAudio: _micEnabled, fps: _fps);
      try {
        await _camera!.initialize();
        _minZoom = await _camera!.getMinZoomLevel();
        _maxZoom = await _camera!.getMaxZoomLevel();
        if (mounted) setState(() => _cameraReady = true);
      } catch (_) {
        debugPrint('Camera retry also failed');
      }
    }
  }

  @override
  void dispose() {
    _timerTick?.cancel();
    _accelSub?.cancel();
    _focusAnimCtrl.dispose();
    _pulseCtrl.dispose();
    _camera?.dispose();
    VolumeButtonService().unregisterListener('record_screen');
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    super.dispose();
  }

  // ─── Recording ──────────────────────────────────────────────────────────

  String get _elapsedLabel {
    final s = _stopwatch.elapsed.inSeconds;
    return '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';
  }

  Future<void> _toggleRecording() async {
    if (!_isFbaMode && _orderId == null) { _showSnack('Scan order first'); return; }

    if (_recording) {
      _timerTick?.cancel();
      _stopwatch.stop();
      if (_soundEnabled) NativeCameraSound.playStopRecord();
      setState(() { _recording = false; _isPaused = false; });
      final file = await _camera!.stopVideoRecording();
      await _uploadVideo(file.path);
    } else {
      if (_soundEnabled) NativeCameraSound.playStartRecord();
      await _camera!.startVideoRecording();
      _stopwatch.reset();
      _stopwatch.start();
      _timerTick = Timer.periodic(const Duration(seconds: 1), (_) { if (mounted) setState(() {}); });
      setState(() => _recording = true);
    }
  }

  Future<void> _togglePause() async {
    if (!_recording) return;
    if (_isPaused) {
      await _camera!.resumeVideoRecording();
      _stopwatch.start();
      if (_soundEnabled) NativeCameraSound.playStartRecord();
      setState(() => _isPaused = false);
    } else {
      await _camera!.pauseVideoRecording();
      _stopwatch.stop();
      if (_soundEnabled) NativeCameraSound.playStopRecord();
      setState(() => _isPaused = true);
    }
  }

  // ─── Photo ──────────────────────────────────────────────────────────────

  Future<void> _capturePhoto() async {
    if (!_cameraReady || _camera == null || _orderId == null) return;
    if (_soundEnabled) NativeCameraSound.playShutter();
    try {
      final xFile = await _camera!.takePicture();
      setState(() => _uploading = true);
      var file = File(xFile.path);
      file = await ImageProcessingUtils.processPhoto(file, orientation: _orientation, addTimestamp: _timestampImage, prefix: _prefix);
      await ApiService.uploadImage(orderId: _orderId!, imageFile: file);
      if (mounted) _showSnack('Photo uploaded');
    } catch (e) {
      _showSnack('Photo failed: $e');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  // ─── Camera Controls ────────────────────────────────────────────────────

  Future<void> _switchCamera() async {
    if (_recording) return;
    setState(() { _cameraReady = false; _isFront = !_isFront; });
    await _camera?.dispose();
    await _initCamera();
  }

  void _toggleFlash() {
    if (_camera == null || !_cameraReady) return;
    _flashOn = !_flashOn;
    _camera!.setFlashMode(_flashOn ? FlashMode.torch : FlashMode.off);
    setState(() {});
  }

  void _toggleMic() async {
    if (_recording) return;
    _micEnabled = !_micEnabled;
    await CameraSettingsService.setAudio(_micEnabled);
    setState(() { _cameraReady = false; });
    await _camera?.dispose();
    await _initCamera();
  }

  void _onZoomChanged(double val) {
    _zoom = val;
    final level = _minZoom + (_maxZoom - _minZoom) * val;
    _camera?.setZoomLevel(level);
    setState(() {});
  }

  void _onTapFocus(TapUpDetails details) async {
    if (_camera == null || !_cameraReady) return;
    final renderBox = context.findRenderObject() as RenderBox?;
    if (renderBox == null) return;

    try {
      // Approximate focus point (normalize to 0-1)
      final size = renderBox.size;
      final x = details.localPosition.dx / size.width;
      final y = details.localPosition.dy / size.height;
      await _camera!.setFocusPoint(Offset(x.clamp(0, 1), y.clamp(0, 1)));
      await _camera!.setExposurePoint(Offset(x.clamp(0, 1), y.clamp(0, 1)));
    } catch (_) {}

    setState(() { _showFocus = true; _focusX = details.localPosition.dx; _focusY = details.localPosition.dy; });
    _focusAnimCtrl.forward(from: 0);
    Future.delayed(const Duration(seconds: 2), () { if (mounted) setState(() => _showFocus = false); });
  }

  // ─── Upload ─────────────────────────────────────────────────────────────

  Future<void> _uploadVideo(String path) async {
    setState(() => _uploading = true);
    try {
      await ApiService.uploadVideo(
        orderId: _isFbaMode ? null : _orderId,
        fbaShipmentId: widget.fbaShipmentId,
        fbaBoxNumber: widget.fbaBoxNumber,
        type: widget.videoType,
        videoFile: File(path),
        durationSeconds: _stopwatch.elapsed.inMilliseconds / 1000,
        recordedAt: DateTime.now().toIso8601String(),
      );
      if (mounted) { _showSnack('Video uploaded successfully'); Navigator.pop(context); }
    } catch (e) {
      _showSnack('Upload failed: $e');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating, backgroundColor: RfColors.card));
  }

  String get _zoomLabel {
    final level = _minZoom + (_maxZoom - _minZoom) * _zoom;
    return '${level.toStringAsFixed(1)}x';
  }

  // ─── UI ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    if (_camera == null || !_cameraReady) {
      return const Scaffold(backgroundColor: Colors.black, body: Center(child: CircularProgressIndicator(color: Colors.white38)));
    }

    final isPacking = widget.videoType == 'packing';
    final accent = isPacking ? RfColors.pkAccent : RfColors.rtAccent;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            // ── Top controls row ──
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Row(
                children: [
                  _iconBtn(Icons.arrow_back_rounded, () => Navigator.pop(context)),
                  const SizedBox(width: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: accent.withAlpha(200), borderRadius: BorderRadius.circular(14)),
                    child: Text(isPacking ? 'PACKING' : 'UNPACKING', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5)),
                  ),
                  if (_recording) ...[
                    const SizedBox(width: 6),
                    AnimatedBuilder(
                      animation: _pulseCtrl,
                      builder: (_, __) => Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(color: Colors.red.withAlpha(180 + (_pulseCtrl.value * 75).toInt()), borderRadius: BorderRadius.circular(14)),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          Container(width: 6, height: 6, decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle)),
                          const SizedBox(width: 4),
                          Text(_isPaused ? 'PAUSED' : _elapsedLabel, style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
                        ]),
                      ),
                    ),
                  ],
                  const Spacer(),
                  AnimatedRotation(
                    turns: _orientTurns / 4,
                    duration: const Duration(milliseconds: 300),
                    child: Row(children: [
                      if (_videoMode) _iconBtn(_micEnabled ? Icons.mic_rounded : Icons.mic_off_rounded, _toggleMic, color: _micEnabled ? Colors.white : Colors.red.shade300),
                      _iconBtn(_flashOn ? Icons.flash_on_rounded : Icons.flash_off_rounded, _toggleFlash, color: _flashOn ? Colors.amber : Colors.white),
                      _iconBtn(Icons.cameraswitch_rounded, _switchCamera),
                    ]),
                  ),
                ],
              ),
            ),

            // ── Camera preview (expands to fill available space) ──
            Expanded(
              child: Stack(
                alignment: Alignment.bottomCenter,
                children: [
                  // Camera preview — direct, no wrapping (CameraPreview has internal AspectRatio)
                  GestureDetector(
                    onTapUp: _onTapFocus,
                    child: CameraPreview(_camera!),
                  ),

                  // Focus ring
                  if (_showFocus)
                    Positioned(
                      left: _focusX - 28, top: _focusY - 28,
                      child: AnimatedBuilder(
                        animation: _focusAnim,
                        builder: (_, __) => Transform.scale(
                          scale: _focusAnim.value,
                          child: Container(width: 56, height: 56, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: accent, width: 2))),
                        ),
                      ),
                    ),

                  // Order info overlay (top of preview area)
                  if (_orderId != null || _isFbaMode)
                    Positioned(
                      top: 4, left: 12, right: 12,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(color: Colors.black.withAlpha(170), borderRadius: BorderRadius.circular(8)),
                        child: _isFbaMode
                          ? Row(children: [
                              Text(widget.fbaShipmentId!, style: const TextStyle(color: Color(0xFF58A6FF), fontFamily: 'monospace', fontSize: 12, fontWeight: FontWeight.bold)),
                              if (widget.fbaBoxNumber != null) Text('  Box ${widget.fbaBoxNumber}', style: const TextStyle(color: Colors.white70, fontSize: 11)),
                            ])
                          : Row(children: [
                              Expanded(child: Text(_orderId!, style: const TextStyle(color: Color(0xFF58A6FF), fontFamily: 'monospace', fontSize: 12, fontWeight: FontWeight.bold))),
                              if (_productTitle != null) Expanded(child: Text(_productTitle!, style: const TextStyle(color: Colors.white70, fontSize: 11), textAlign: TextAlign.right, maxLines: 1, overflow: TextOverflow.ellipsis)),
                            ]),
                      ),
                    ),

                  // Upload indicator
                  if (_uploading)
                    Positioned(
                      bottom: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        decoration: BoxDecoration(color: RfColors.card, borderRadius: BorderRadius.circular(20)),
                        child: const Row(mainAxisSize: MainAxisSize.min, children: [
                          SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                          SizedBox(width: 8),
                          Text('Uploading...', style: TextStyle(color: Colors.white70, fontSize: 12)),
                        ]),
                      ),
                    ),
                ],
              ),
            ),

            // ── Bottom controls ──
            Container(
              color: Colors.black,
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
              child: Column(
                children: [
                  // Zoom slider
                  Row(
                    children: [
                      const Icon(Icons.zoom_out, color: Colors.white38, size: 16),
                      Expanded(
                        child: SliderTheme(
                          data: SliderThemeData(
                            trackHeight: 2,
                            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                            activeTrackColor: accent,
                            inactiveTrackColor: Colors.white24,
                            thumbColor: Colors.white,
                            overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
                          ),
                          child: Slider(value: _zoom, onChanged: _onZoomChanged),
                        ),
                      ),
                      const Icon(Icons.zoom_in, color: Colors.white38, size: 16),
                      const SizedBox(width: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                        decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(6)),
                        child: Text(_zoomLabel, style: const TextStyle(color: Colors.white70, fontSize: 10, fontFamily: 'monospace')),
                      ),
                    ],
                  ),

                  const SizedBox(height: 8),

                  // Video/Photo mode toggle
                  if (!_recording)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Container(
                        padding: const EdgeInsets.all(3),
                        decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(20)),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          _modeChip('Video', _videoMode, accent, () => setState(() => _videoMode = true)),
                          _modeChip('Photo', !_videoMode, accent, () => setState(() => _videoMode = false)),
                        ]),
                      ),
                    ),

                  // Main controls row
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      // Left: Pause/Resume
                      SizedBox(
                        width: 56,
                        child: _recording
                            ? GestureDetector(
                                onTap: _togglePause,
                                child: Container(
                                  width: 48, height: 48,
                                  decoration: BoxDecoration(color: _isPaused ? Colors.amber.withAlpha(50) : Colors.white12, shape: BoxShape.circle),
                                  child: Icon(_isPaused ? Icons.play_arrow_rounded : Icons.pause_rounded, color: _isPaused ? Colors.amber : Colors.white, size: 24),
                                ),
                              )
                            : const SizedBox.shrink(),
                      ),

                      // Center: main capture button
                      GestureDetector(
                        onTap: _uploading ? null : (_videoMode ? _toggleRecording : _capturePhoto),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          width: 72, height: 72,
                          decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3.5)),
                          child: Center(
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              width: _recording ? 26 : 56,
                              height: _recording ? 26 : 56,
                              decoration: BoxDecoration(
                                color: _videoMode ? Colors.red : Colors.white,
                                borderRadius: BorderRadius.circular(_recording ? 6 : 28),
                              ),
                            ),
                          ),
                        ),
                      ),

                      // Right: camera switch
                      const SizedBox(width: 56),
                    ],
                  ),

                  const SizedBox(height: 4),
                  Text(
                    _recording ? (_isPaused ? 'PAUSED  $_elapsedLabel' : 'REC  $_elapsedLabel') : (_videoMode ? 'Tap to record' : 'Tap to capture'),
                    style: TextStyle(
                      color: _recording ? (_isPaused ? Colors.amber.shade200 : Colors.red.shade300) : Colors.white54,
                      fontSize: 11, fontWeight: _recording ? FontWeight.bold : FontWeight.normal,
                      fontFamily: _recording ? 'monospace' : null,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Helpers ────────────────────────────────────────────────────────────

  Widget _iconBtn(IconData icon, VoidCallback onTap, {Color color = Colors.white}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 2),
        padding: const EdgeInsets.all(7),
        decoration: BoxDecoration(color: Colors.black38, borderRadius: BorderRadius.circular(8)),
        child: Icon(icon, color: color, size: 20),
      ),
    );
  }

  Widget _modeChip(String label, bool active, Color accent, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
        decoration: BoxDecoration(color: active ? accent : Colors.transparent, borderRadius: BorderRadius.circular(16)),
        child: Text(label, style: TextStyle(color: active ? Colors.white : Colors.white54, fontSize: 12, fontWeight: active ? FontWeight.w600 : FontWeight.normal)),
      ),
    );
  }
}
