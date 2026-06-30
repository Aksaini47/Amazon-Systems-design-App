import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:native_camera_sound/native_camera_sound.dart';
import '../models/capture_session.dart';
import '../services/awb_classifier.dart';
import '../services/camera_settings_service.dart';
import '../services/local_storage_service.dart';
import '../services/file_naming_service.dart';
import '../services/ocr_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../widgets/rf_button.dart';
import '../utils/debug_session_log.dart';
import '../utils/volume_button_service.dart';

/// Full-screen label scan — manual SCAN tap or optional auto-scan (Settings).
///
/// AWB detection logic (also documented in MainActivity DND channel comments):
///   - mobile_scanner.analyzeImage(frame) returns ALL barcodes in the image
///   - For each barcode's rawValue:
///       * if value matches `\d{3}-\d{7}-\d{7}` → goes to Order ID field
///         (this is also how labels encode the Order ID barcode)
///       * otherwise → first such barcode becomes the AWB
///   - OCR also runs on the same frame as a fallback path for Order ID
///   - Final 3-7-7 validation gate stops malformed values from saving
class BarcodeSavePopup extends StatefulWidget {
  final CaptureMode mode;
  const BarcodeSavePopup({super.key, required this.mode});
  @override
  State<BarcodeSavePopup> createState() => _BarcodeSavePopupState();
}

class _BarcodeSavePopupState extends State<BarcodeSavePopup> {
  final _orderIdController = TextEditingController();
  final _awbController = TextEditingController();
  final _orderIdRegex = RegExp(r'^\d{3}-\d{7}-\d{7}$');
  bool _isValid = false;

  // Live preview camera
  CameraController? _cam;
  bool _camReady = false;
  // Default zoom 1× per user request — was 2× which over-zoomed small labels
  // and lost the QR/barcode region for big shipping labels.
  int _zoomIndex = 0;
  static const _zoomLevels = [1.0, 2.0, 3.0];
  double _minZoom = 1.0;
  double _maxZoom = 8.0;

  // mobile_scanner controller — used only for analyzeImage on captured frames.
  MobileScannerController? _scanner;

  bool _scanning = false;
  String? _statusMessage;
  bool _foundAwb = false;
  bool _foundOrderId = false;
  String? _detectedCarrierName;  // shown next to AWB field once classified

  // Duplicate detection — populated from disk at init, compared on every
  // text-change/scan so the user gets a red banner BEFORE saving over an
  // existing order.
  Set<String> _existingOrderIds = {};
  Set<String> _existingAwbs = {};
  String? _duplicateWarning;

  bool _autoLabelScan = false;
  bool _autoLabelSave = true;
  Timer? _autoScanTimer;

  @override
  void initState() {
    super.initState();
    _orderIdController.addListener(_onTextChanged);
    _awbController.addListener(_onTextChanged);
    _scanner = MobileScannerController(
      detectionSpeed: DetectionSpeed.normal,
      facing: CameraFacing.back,
    );
    _bootstrap();
    VolumeButtonService().registerListener('barcode_popup', (event) {
      if (!mounted) return;
      if (event == 1 || event == 2) {
        _scan();
      }
    });
  }

  Future<void> _bootstrap() async {
    await _loadLabelSettings();
    await _initCamera();
    await _loadExistingOrders();
  }

  Future<void> _loadLabelSettings() async {
    _autoLabelScan = await CameraSettingsService.getAutoLabelScan();
    _autoLabelSave = await CameraSettingsService.getAutoLabelSave();
    DebugSessionLog.log(
      location: 'barcode_save_popup.dart:_loadLabelSettings',
      message: 'label settings loaded',
      hypothesisId: 'H4-settings',
      data: {
        'autoLabelScan': _autoLabelScan,
        'autoLabelSave': _autoLabelSave,
      },
    );
  }

  void _scheduleAutoScanOnce() {
    _autoScanTimer?.cancel();
    if (!_autoLabelScan || _autoScanDone) return;
    _autoScanTimer = Timer(const Duration(milliseconds: 900), () {
      if (!mounted || _scanning || _isValid || _autoScanDone) return;
      if (_cam == null || !_camReady) return;
      _scan(fromAuto: true);
    });
  }

  void _stopAutoScanLoop() {
    _autoScanTimer?.cancel();
    _autoScanTimer = null;
  }

  bool _autoScanDone = false;

  /// Read every order on disk once at popup-open. Stores the set of orderIds
  /// and AWBs so [_onTextChanged] can flag duplicates without per-keystroke I/O.
  Future<void> _loadExistingOrders() async {
    try {
      final orders = await LocalStorageService().listOrders();
      final ids = <String>{};
      final awbs = <String>{};
      for (final o in orders) {
        final id = o['orderId'] as String?;
        if (id != null && id.isNotEmpty) ids.add(id);
        // meta.json may carry awb in some orders — pull from it if present
        try {
          final metaPath = o['metaPath'] as String?;
          if (metaPath != null) {
            final raw = await File(metaPath).readAsString();
            final m = jsonDecode(raw) as Map<String, dynamic>;
            final awb = m['awb'] as String?;
            if (awb != null && awb.isNotEmpty) awbs.add(awb.trim());
          }
        } catch (_) {}
      }
      if (!mounted) return;
      setState(() {
        _existingOrderIds = ids;
        _existingAwbs = awbs;
      });
      debugPrint('Duplicate scan loaded: ${ids.length} orderIds, ${awbs.length} AWBs');
    } catch (e) {
      debugPrint('_loadExistingOrders failed: $e');
    }
  }

  // Whether we already fired the scan-lock haptic for the current
  // orderId+AWB pair. Reset when either field is cleared.
  bool _lockFeedbackFired = false;

  /// Combined text-change handler — runs validation + duplicate check.
  /// Also fires haptic+beep when BOTH fields transition to a valid state
  /// (so users typing values manually get the same lock confirmation as
  /// users who used the scanner).
  void _onTextChanged() {
    _validateInput();
    final orderId = _orderIdController.text.trim();
    final awb = _awbController.text.trim();
    String? warn;
    if (orderId.isNotEmpty && _orderIdRegex.hasMatch(orderId)) {
      final storageKey = FileNamingService.orderFolderName(orderId, widget.mode);
      if (_existingOrderIds.contains(storageKey)) {
        warn = 'Order $orderId already saved (${widget.mode.name.toUpperCase()})';
      }
    }
    if (warn == null && orderId.isNotEmpty && _existingOrderIds.contains(orderId)) {
      warn = 'Order ID $orderId already in gallery';
    } else if (awb.isNotEmpty && _existingAwbs.contains(awb)) {
      warn = 'AWB $awb already in gallery (different order ID?)';
    }
    if (warn != _duplicateWarning) {
      setState(() => _duplicateWarning = warn);
    }

    // Lock-state feedback: both fields filled + Order ID is valid 3-7-7.
    final isLocked = _isValid && awb.isNotEmpty;
    if (isLocked && !_lockFeedbackFired) {
      _lockFeedbackFired = true;
      _playLockFeedback();
    } else if (!isLocked && _lockFeedbackFired) {
      // Reset gate when user clears either field — re-locking should
      // re-fire feedback.
      _lockFeedbackFired = false;
    }
  }

  @override
  void dispose() {
    _stopAutoScanLoop();
    VolumeButtonService().unregisterListener('barcode_popup');
    _cam?.dispose();
    _scanner?.dispose();
    _orderIdController.dispose();
    _awbController.dispose();
    super.dispose();
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty || !mounted) return;
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final ctrl = CameraController(back, ResolutionPreset.high, enableAudio: false);
      await ctrl.initialize();
      if (!mounted) {
        await ctrl.dispose();
        return;
      }
      _minZoom = await ctrl.getMinZoomLevel();
      _maxZoom = await ctrl.getMaxZoomLevel();
      _cam = ctrl;
      _camReady = true;
      setState(() {});
      await _applyZoom();
      _scheduleAutoScanOnce();
    } catch (e) {
      debugPrint('Scan camera init failed: $e');
      if (mounted) setState(() => _statusMessage = 'Camera unavailable: $e');
    }
  }

  Future<void> _applyZoom() async {
    if (_cam == null || !_camReady) return;
    final target = _zoomLevels[_zoomIndex].clamp(_minZoom, _maxZoom);
    try { await _cam!.setZoomLevel(target); } catch (_) {}
  }

  void _setZoom(int idx) {
    if (idx == _zoomIndex) return;
    setState(() => _zoomIndex = idx);
    _applyZoom();
  }

  /// Manual scan — captures a still, runs barcode + OCR in parallel, then
  /// classifies via [CarrierPatterns] to assign AWB to the right carrier.
  ///
  /// Multi-stage logic:
  ///   1. Detect ALL barcodes in the frame
  ///   2. OCR full text from the same frame (returns text + order id)
  ///   3. Detect carrier NAME from the OCR text ("DELHIVERY", "BLUE DART", etc.)
  ///   4. Run [CarrierPatterns.pickAwbFromBarcodes] — picks the best AWB
  ///      candidate by validating each barcode against per-carrier regex,
  ///      boosted by the detected carrier hint
  ///   5. Fallback: if no barcode AWB found, scan OCR text for AWB-shaped
  ///      tokens via [CarrierPatterns.findAwbInText]
  ///   6. Order ID is filled from OcrService.extractOrderId (or from a
  ///      barcode whose value matches the 3-7-7 pattern)
  Future<void> _scan({bool fromAuto = false}) async {
    if (_cam == null || !_camReady || _scanning) return;
    if (fromAuto) _autoScanDone = true;
    _stopAutoScanLoop();
    setState(() {
      _scanning = true;
      _statusMessage = fromAuto ? 'Auto scanning…' : 'Scanning…';
    });

    try {
      final xFile = await _cam!.takePicture();

      // Stage 1+2: barcode + OCR text on the same frame
      final results = await Future.wait([
        _scanner!.analyzeImage(xFile.path),
        OcrService.scanAll(xFile.path),
      ]);
      final barcodeResult = results[0] as BarcodeCapture?;
      final ocrResult = results[1] as OcrScanResult;

      // Stage 3: carrier hint from label text
      final carrierHint = CarrierPatterns.detectCarrierFromText(ocrResult.fullText);
      String? carrierName = carrierHint?.name;

      bool awbFound = _foundAwb;
      bool orderIdFound = _foundOrderId;

      // Collect every barcode raw value and find any that encodes the Order ID
      final allBarcodes = barcodeResult?.barcodes ?? const <Barcode>[];
      final barcodeValues = <String>[];
      for (final b in allBarcodes) {
        final raw = b.rawValue?.trim();
        if (raw == null || raw.isEmpty) continue;
        barcodeValues.add(raw);
        if (_orderIdRegex.hasMatch(raw)) {
          if (!_orderIdRegex.hasMatch(_orderIdController.text.trim())) {
            _orderIdController.text = raw;
          }
          orderIdFound = true;
        }
      }
      debugPrint('Scan: ${barcodeValues.length} barcode(s), carrier hint=$carrierName');

      // Stage 4: pick the best AWB from barcodes (skips Order-ID-pattern ones)
      final awbPick = CarrierPatterns.pickAwbFromBarcodes(
        barcodeValues,
        hint: carrierHint,
      );
      if (awbPick != null) {
        if (_awbController.text.trim().isEmpty) {
          _awbController.text = awbPick.value;
        }
        awbFound = true;
        carrierName = awbPick.carrier.name;  // override hint with actual match
      }

      // Stage 5: fallback — find AWB in OCR text if no barcode classified
      if (!awbFound) {
        final textPick = CarrierPatterns.findAwbInText(
          ocrResult.fullText,
          hint: carrierHint,
        );
        if (textPick != null) {
          if (_awbController.text.trim().isEmpty) {
            _awbController.text = textPick.value;
          }
          awbFound = true;
          carrierName = textPick.carrier.name;
        }
      }

      // Stage 6: Order ID via OCR (fallback if no barcode encoded it)
      if (ocrResult.orderId != null && !_orderIdRegex.hasMatch(_orderIdController.text.trim())) {
        _orderIdController.text = ocrResult.orderId!;
        orderIdFound = true;
      } else if (ocrResult.orderId != null) {
        orderIdFound = true;
      }

      if (!mounted) return;
      String msg;
      // (Lock-feedback is fired by _onTextChanged() once both fields are
      //  valid — we let that path own the gating to keep manual-typing and
      //  scan-fill paths consistent.)
      if (awbFound && orderIdFound) {
        msg = '✓ Locked${carrierName != null ? " · $carrierName" : ""} + Order ID';
      } else if (orderIdFound && !awbFound) {
        msg = 'Order ID found — no AWB detected on label';
      } else if (awbFound && !orderIdFound) {
        msg = '${carrierName ?? "AWB"} found — Order ID text not detected';
      } else {
        msg = 'Nothing detected — aim closer at the label';
      }

      setState(() {
        _scanning = false;
        _statusMessage = msg;
        _foundAwb = awbFound;
        _foundOrderId = orderIdFound;
        _detectedCarrierName = carrierName;
      });
      // Re-run duplicate check after auto-fill from scan
      _onTextChanged();

      final orderId = _orderIdController.text.trim();
      final canAutoSave = _autoLabelSave &&
          _orderIdRegex.hasMatch(orderId) &&
          _duplicateWarning == null;
      if (canAutoSave) {
        // #region agent log
        DebugSessionLog.log(
          location: 'barcode_save_popup.dart:_scan',
          message: 'auto save triggered',
          hypothesisId: 'H4-settings',
          data: {'fromAuto': fromAuto, 'orderId': orderId, 'autoScanDone': _autoScanDone},
        );
        // #endregion
        _onSave();
      } else if (fromAuto) {
        DebugSessionLog.log(
          location: 'barcode_save_popup.dart:_scan',
          message: 'auto scan once complete',
          hypothesisId: 'H10-auto-once',
          data: {'orderIdFound': orderIdFound, 'awbFound': awbFound, 'isValid': _isValid},
        );
      }
    } catch (e) {
      debugPrint('Scan failed: $e');
      if (mounted) {
        setState(() {
          _scanning = false;
          _statusMessage = 'Scan failed: $e';
        });
      }
    }
  }

  void _validateInput() {
    final valid = _orderIdRegex.hasMatch(_orderIdController.text.trim());
    if (valid != _isValid) setState(() => _isValid = valid);
  }

  /// Confirms scan-lock to the user with a strong haptic pulse + an audible
  /// beep. Called once per lock transition (when both fields go from
  /// empty/partial → fully filled in a single scan).
  ///
  /// Implementation notes:
  ///   - `SystemSound.play(click)` is silent on most Android phones — replaced
  ///     with NativeCameraSound.playShutter() which actually rings the camera
  ///     shutter audio channel (bypasses media-volume mute).
  ///   - Double haptic pulse (heavy → vibrate) feels more decisive than a
  ///     single heavyImpact, which can be missed on phones with subtle
  ///     vibration motors.
  Future<void> _playLockFeedback() async {
    debugPrint('Lock feedback: firing haptic + shutter beep');
    try {
      HapticFeedback.heavyImpact();
      // Wait a beat so the double-pulse is perceptible.
      await Future.delayed(const Duration(milliseconds: 90));
      HapticFeedback.vibrate();
    } catch (e) {
      debugPrint('Lock haptic failed: $e');
    }
    try {
      await NativeCameraSound.playShutter();
    } catch (e) {
      debugPrint('Lock beep failed: $e');
    }
  }

  void _onSave() {
    if (!_isValid) return;
    Navigator.pop(context, {
      'orderId': _orderIdController.text.trim(),
      'awb': _awbController.text.trim().isEmpty ? null : _awbController.text.trim(),
    });
  }

  void _onCancel() => Navigator.pop(context, null);

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      showMeshOrbs: false,
      appBar: RfGlassAppBar(
        leadingWidth: 56,
        leading: Padding(
          padding: const EdgeInsets.only(left: 8, top: 8, bottom: 8),
          child: RfIconButton(
            icon: Icons.close_rounded,
            size: 38,
            onPressed: _onCancel,
          ),
        ),
        title: 'Save Order',
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: RfButton.primary(
              label: 'SAVE',
              icon: Icons.check_rounded,
              size: RfButtonSize.medium,
              onPressed: _isValid ? _onSave : null,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 12),

            // ── Camera = 4:6 box, large ──
            Expanded(
              flex: 5,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: _buildCameraBox(),
              ),
            ),

            const SizedBox(height: 8),

            // Status line under the box
            SizedBox(
              height: 18,
              child: Center(
                child: Text(
                  _statusMessage ?? 'Place the label inside the box, then tap SCAN',
                  style: TextStyle(
                    color: (_foundAwb && _foundOrderId)
                        ? const Color(0xFF3FB950)
                        : const Color(0xFF8B949E),
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ),

            const SizedBox(height: 10),

            // Zoom + SCAN row — all skeuomorphic with press feedback
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(children: [
                RfChip(label: '1×', active: _zoomIndex == 0, onPressed: () => _setZoom(0)),
                const SizedBox(width: 4),
                RfChip(label: '2×', active: _zoomIndex == 1, onPressed: () => _setZoom(1)),
                const SizedBox(width: 4),
                RfChip(label: '3×', active: _zoomIndex == 2, onPressed: () => _setZoom(2)),
                const SizedBox(width: 10),
                Expanded(
                  child: RfButton.primary(
                    label: _scanning ? 'SCANNING…' : 'SCAN',
                    icon: _scanning ? Icons.hourglass_top_rounded : Icons.center_focus_strong,
                    size: RfButtonSize.large,
                    fullWidth: true,
                    onPressed: _scanning ? null : _scan,
                  ),
                ),
              ]),
            ),

            const SizedBox(height: 14),

            // Fields
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                if (_duplicateWarning != null) ...[
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0x33FF7B72),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFFF7B72)),
                    ),
                    child: Row(children: [
                      const Icon(Icons.warning_amber_rounded, color: Color(0xFFFF7B72), size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Duplicate — $_duplicateWarning',
                          style: const TextStyle(color: Color(0xFFFF7B72), fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ]),
                  ),
                  const SizedBox(height: 8),
                ],
                _buildField(
                  label: 'Order ID *',
                  controller: _orderIdController,
                  hint: '407-1234567-1234567',
                  detected: _foundOrderId,
                  isValid: _isValid,
                ),
                const SizedBox(height: 8),
                _buildField(
                  label: _detectedCarrierName != null
                      ? 'AWB / Tracking — ${_detectedCarrierName!}'
                      : 'AWB / Tracking (optional)',
                  controller: _awbController,
                  hint: '1Z999AA10123456784',
                  detected: _foundAwb,
                ),
              ]),
            ),

            const SizedBox(height: 14),
          ],
        ),
      ),
    );
  }

  /// 4:6 portrait camera box — sized to fill the Expanded slot. The camera
  /// preview IS the box (cover-cropped); no surrounding letterbox.
  Widget _buildCameraBox() {
    final locked = _foundAwb && _foundOrderId;
    final accent = locked ? const Color(0xFF3FB950) : const Color(0xFFFFA657);
    return LayoutBuilder(
      builder: (context, constraints) {
        // Pick the largest 4:6 box that fits in available space
        double width, height;
        if (constraints.maxWidth * 1.5 <= constraints.maxHeight) {
          width = constraints.maxWidth;
          height = width * 1.5;
        } else {
          height = constraints.maxHeight;
          width = height / 1.5;
        }
        return Center(
          child: SizedBox(
            width: width,
            height: height,
            child: Stack(
              children: [
                Positioned.fill(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      color: Colors.black,
                      child: _camReady && _cam != null
                          ? ClipRect(
                              child: FittedBox(
                                fit: BoxFit.cover,
                                child: SizedBox(
                                  width: _cam!.value.previewSize?.height ?? 1,
                                  height: _cam!.value.previewSize?.width ?? 1,
                                  child: CameraPreview(_cam!),
                                ),
                              ),
                            )
                          : const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white38)),
                    ),
                  ),
                ),

                // Outline (changes to green when locked)
                Positioned.fill(
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 250),
                    decoration: BoxDecoration(
                      border: Border.all(color: accent, width: 2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),

                // Corner brackets
                ..._cornerBrackets(color: accent),

                // Top caption
                Positioned(
                  top: 10, left: 0, right: 0,
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(
                        color: Colors.black.withAlpha(160),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        locked ? '✓ LOCKED' : 'AMAZON LABEL',
                        style: TextStyle(color: accent, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                      ),
                    ),
                  ),
                ),

                if (_scanning)
                  const Positioned(
                    bottom: 10, right: 10,
                    child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 1.8, color: Colors.white)),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  List<Widget> _cornerBrackets({Color color = const Color(0xFFFFA657)}) {
    const length = 18.0;
    const thickness = 2.5;
    Widget corner({double? top, double? bottom, double? left, double? right, required BoxBorder border}) {
      return Positioned(
        top: top, bottom: bottom, left: left, right: right,
        child: SizedBox(
          width: length, height: length,
          child: DecoratedBox(decoration: BoxDecoration(border: border)),
        ),
      );
    }
    return [
      corner(top: 0, left: 0, border: Border(top: BorderSide(color: color, width: thickness), left: BorderSide(color: color, width: thickness))),
      corner(top: 0, right: 0, border: Border(top: BorderSide(color: color, width: thickness), right: BorderSide(color: color, width: thickness))),
      corner(bottom: 0, left: 0, border: Border(bottom: BorderSide(color: color, width: thickness), left: BorderSide(color: color, width: thickness))),
      corner(bottom: 0, right: 0, border: Border(bottom: BorderSide(color: color, width: thickness), right: BorderSide(color: color, width: thickness))),
    ];
  }

  Widget _buildField({
    required String label,
    required TextEditingController controller,
    required String hint,
    bool detected = false,
    bool isValid = false,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text(label, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, fontWeight: FontWeight.w600)),
        if (detected) ...[
          const SizedBox(width: 6),
          const Icon(Icons.auto_awesome, color: Color(0xFF3FB950), size: 10),
          const SizedBox(width: 3),
          const Text('auto', style: TextStyle(color: Color(0xFF3FB950), fontSize: 9, fontStyle: FontStyle.italic)),
        ],
      ]),
      const SizedBox(height: 4),
      TextField(
        controller: controller,
        style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14, letterSpacing: 0.5),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(color: Colors.white.withOpacity(0.15), fontFamily: 'monospace', fontSize: 14),
          filled: true,
          fillColor: RfColors.bg,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFF30363D))),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFF30363D))),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFF1F6FEB), width: 1.5)),
          suffixIcon: isValid ? const Icon(Icons.check_circle, color: Color(0xFF3FB950), size: 18) : null,
          suffixIconConstraints: const BoxConstraints(minWidth: 28, minHeight: 28),
        ),
        keyboardType: TextInputType.text,
        autocorrect: false,
        textInputAction: TextInputAction.done,
      ),
    ]);
  }
}
