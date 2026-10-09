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
import '../services/activity_log_service.dart';
import '../utils/order_id_matcher.dart';
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

/// Digits-only, auto-inserts hyphens at positions 3 and 10 to match the
/// 3-7-7 Order ID shape while typing. Caps at 17 digits. Programmatic
/// `.text =` assignment (scan/OCR autofill) bypasses this — formatters only
/// intercept user keystrokes, so already-correct scanned values pass through
/// untouched.
class _OrderIdInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    final digits = newValue.text.replaceAll(RegExp(r'[^0-9]'), '');
    final capped = digits.length > 17 ? digits.substring(0, 17) : digits;
    final buf = StringBuffer();
    for (var i = 0; i < capped.length; i++) {
      buf.write(capped[i]);
      if ((i == 2 || i == 9) && i != capped.length - 1) buf.write('-');
    }
    final formatted = buf.toString();

    final digitsBeforeCursor = newValue.text
        .substring(0, newValue.selection.end.clamp(0, newValue.text.length))
        .replaceAll(RegExp(r'[^0-9]'), '').length;
    var cursor = 0, seen = 0;
    while (cursor < formatted.length && seen < digitsBeforeCursor) {
      if (formatted[cursor] != '-') seen++;
      cursor++;
    }
    return TextEditingValue(text: formatted, selection: TextSelection.collapsed(offset: cursor));
  }
}

/// User's choice when a scanned/typed RT Order ID is a near-match (1-3
/// digits off) of a known PK Order ID.
enum _MismatchResolution { useSuggested, keep, retake }

class _BarcodeSavePopupState extends State<BarcodeSavePopup> {
  final _orderIdController = TextEditingController();
  final _awbController = TextEditingController();
  final _orderIdRegex = RegExp(r'^\d{3}-\d{7}-\d{7}$');
  // Amazon's Order ID prefixes — every valid order id starts with one of these.
  bool _isValid = false;
  bool _prefixValid = true;

  // Live preview camera
  CameraController? _cam;
  bool _camReady = false;
  // Default zoom 1× per user request — was 2× which over-zoomed small labels
  // and lost the QR/barcode region for big shipping labels.
  int _zoomIndex = 0;
  static const _zoomLevels = [1.0, 2.0, 3.0];
  double _minZoom = 1.0;
  double _maxZoom = 8.0;

  // mobile_scanner controller — drives the live PK barcode reader, and is
  // also used for analyzeImage on captured frames in OCR mode.
  MobileScannerController? _scanner;

  // ─── Scan mode ────────────────────────────────────────────────────────
  // PK opens on the live barcode reader: the label encodes the Order ID in a
  // barcode, so reading that barcode is exact. The old path photographed the
  // WHOLE frame and let OCR hunt for a 3-7-7 anywhere in it, which is how a
  // tracking/reference number on the same label ended up in the Order ID
  // field. OCR is still one tap away for labels whose barcode is torn or
  // faded — it just is not the default any more. RT is unchanged.
  late bool _barcodeMode;
  bool _switchingMode = false;
  /// Latches once the reader has handed off to save/review, so the next
  /// detection frame — they arrive several times a second — cannot fire a
  /// second save on top of the first.
  bool _saveTriggered = false;

  bool _scanning = false;
  String? _statusMessage;
  bool _foundAwb = false;
  bool _foundOrderId = false;
  String? _detectedCarrierName;  // shown next to AWB field once classified

  // Popup-open timestamp + one-shot latch, purely for the
  // barcode_scanner_first_detection analytics event — lets Sir/Claude see
  // actual on-device time-to-first-frame instead of guessing at lag.
  DateTime? _scanOpenedAt;
  bool _firstDetectionLogged = false;

  // ─── Order ID dual-channel cross-check ─────────────────────────────────
  // Barcode decode and OCR of the printed digits are two independent reads
  // of the same Order ID (see OrderIdCrossCheck in order_id_matcher.dart).
  // Since 2026-10-05 they no longer GATE auto-save on agreeing — requiring
  // both to land in one frame meant auto-save almost never fired. They only
  // BLOCK it when they positively disagree (_orderIdConflictValue): two
  // plausible-looking candidates is the one case worth stopping for. A clean
  // agreement is still recorded here, purely so the saved-order log shows
  // whether a given save was double-confirmed or single-channel.
  //
  // Tracked as the specific STRING that was confirmed, not a bool, so any
  // edit — a fresh scan overwriting it, a manual retype — makes it stale on
  // its own without needing an explicit reset at every call site that
  // touches the field.
  String? _verifiedOrderIdValue;
  bool _orderIdChecking = false;
  String? _orderIdConflictValue;  // the disagreeing read, blocks auto-save
  String _lastOrderIdText = '';

  // Duplicate detection — populated from disk at init, compared on every
  // text-change/scan so the user gets a red banner BEFORE saving over an
  // existing order.
  Set<String> _existingOrderIds = {};
  // AWB -> the bare Order IDs it is already saved under. Keyed by owner, not a
  // flat set, because a returned parcel often travels back on its ORIGINAL
  // AWB: the PK and RT records of one order legitimately share it, and a flat
  // set flagged every such return as a duplicate and blocked its auto-save.
  final Map<String, Set<String>> _awbOwners = {};
  String? _duplicateWarning;

  // Known PK-saved order ids (bare, hyphenated) — ground truth for the RT
  // near-match mismatch check. Built from the same disk scan as the
  // duplicate-detection sets above, zero extra I/O.
  Set<String> _pkOrderIds = {};

  bool _autoLabelScan = false;
  bool _autoLabelSave = true;
  int _autoScanDelayMs = 900;
  Timer? _autoScanTimer;
  // Settings load async while the live reader may already be detecting —
  // auto-save waits for the real value instead of trusting the default.
  bool _settingsLoaded = false;
  // Last reason auto-save declined to fire, so the analytics log records a
  // reason once per change rather than once per detection frame.
  String? _lastAutoSaveBlock;

  // ── Scanner-stuck watchdog ───────────────────────────────────────────────
  // 2026-09-23: on a live device, the barcode reader occasionally never
  // produces a single detection after opening — the camera-release race this
  // screen already guards against (500ms delay before this popup opens; see
  // live_capture_screen.dart's _openBarcodePopup) isn't airtight, so this
  // catches the tail case instead of leaving Sir staring at a frozen preview
  // with no feedback and no way to recover short of backing out and redoing
  // the whole video. Every successful scan detects within ~2.5-3.5s
  // (see barcode_scanner_first_detection events), so 6s is a safe margin.
  Timer? _scanWatchdog;
  bool _scanStuck = false;

  @override
  void initState() {
    super.initState();
    _scanOpenedAt = DateTime.now();
    _orderIdController.addListener(_onTextChanged);
    _awbController.addListener(_onTextChanged);
    _scanner = MobileScannerController(
      formats: const [
        BarcodeFormat.code128,
        BarcodeFormat.code39,
        BarcodeFormat.qrCode,
        BarcodeFormat.dataMatrix,
        BarcodeFormat.pdf417,
        BarcodeFormat.ean13,
      ],
      // The Order ID barcode is printed with noticeably narrower bars than
      // the AWB barcode on the same label (verified by decoding a real label
      // at increasing render DPI: the AWB barcode decodes at the plugin's
      // default analysis resolution, the Order ID one only decodes once the
      // image is ~1.5-2x finer) — this is why AWB reads reliably while Order
      // ID does not at the same phone distance/zoom. Requesting a higher
      // camera analysis resolution resolves the narrower bars without Sir
      // needing to hold the phone closer or more zoomed in.
      cameraResolution: const Size(1920, 1080),
      // Needed so BarcodeCapture.image carries the PNG frame the barcode was
      // just decoded from — the cross-check OCR pass runs on THAT exact
      // frame, not a fresh capture, so the two channels are reading the same
      // physical moment. Only costs a bitmap encode on frames where a
      // barcode was actually found, not every frame.
      returnImage: true,
    );
    // 2026-09-23 (Sir): the continuous live barcode reader — ML Kit decoding
    // every frame at a forced 1920x1080 analysis resolution — stayed
    // perceptibly laggy even after the camera-release-race fixes above, and
    // still occasionally hung outright despite the watchdog. Reverting PK's
    // default to the same tap/auto-scan flow RT already uses: one still,
    // OCR + barcode read together, cross-checked (_crossCheckOrderId /
    // OrderIdCrossCheck below still fully applies) — same safety, lighter
    // camera load. The live reader is still one tap away via the BARCODE
    // chip below for labels whose barcode reads better that way.
    _barcodeMode = false;
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
    // In barcode mode the MobileScanner widget opens the camera itself —
    // initialising a CameraController here too would fight it for the device.
    if (!_barcodeMode) await _initCamera();
    await _loadExistingOrders();
  }

  Future<void> _loadLabelSettings() async {
    _autoLabelScan = await CameraSettingsService.getAutoLabelScanForMode(widget.mode);
    _autoLabelSave = await CameraSettingsService.getAutoLabelSave();
    _autoScanDelayMs = await CameraSettingsService.getAutoScanDelayMs();
    _settingsLoaded = true;
    unawaited(ActivityLogService.log(
      event: 'label_popup_open',
      mode: widget.mode,
      extra: {
        'auto_save': '$_autoLabelSave',
        'auto_scan': '$_autoLabelScan',
        'barcode_mode': '$_barcodeMode',
      },
    ));
  }

  void _scheduleAutoScanOnce() {
    _autoScanTimer?.cancel();
    if (!_autoLabelScan || _autoScanDone) return;
    _autoScanTimer = Timer(Duration(milliseconds: _autoScanDelayMs), () {
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
  /// and each AWB's owning orders so [_onTextChanged] can flag duplicates
  /// without per-keystroke I/O.
  Future<void> _loadExistingOrders() async {
    try {
      final orders = await LocalStorageService().listOrders();
      final ids = <String>{};
      final owners = <String, Set<String>>{};
      final pkIds = <String>{};
      for (final o in orders) {
        final id = o['orderId'] as String?;
        if (id != null && id.isNotEmpty) ids.add(id);
        final bare = o['bareOrderId'] as String?;
        if (o['mode'] == 'pk' && bare != null && bare.isNotEmpty) pkIds.add(bare);
        // meta.json may carry awb in some orders — pull from it if present
        try {
          final metaPath = o['metaPath'] as String?;
          if (metaPath != null && bare != null) {
            final raw = await File(metaPath).readAsString();
            final m = jsonDecode(raw) as Map<String, dynamic>;
            final awb = (m['awb'] as String?)?.trim();
            if (awb != null && awb.isNotEmpty) {
              owners.putIfAbsent(awb, () => <String>{}).add(bare);
            }
          }
        } catch (_) {}
      }
      if (!mounted) return;
      setState(() {
        _existingOrderIds = ids;
        _awbOwners
          ..clear()
          ..addAll(owners);
        _pkOrderIds = pkIds;
      });
      debugPrint('Duplicate scan loaded: ${ids.length} orderIds, ${owners.length} AWBs, ${pkIds.length} PK ids');
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
    // A mismatch verdict belongs to the value it was reached about; a new or
    // retyped Order ID starts clean. Scan fills assign the text BEFORE they
    // set the verdict, so this never wipes a fresh one.
    if (orderId != _lastOrderIdText) {
      _lastOrderIdText = orderId;
      if (_orderIdConflictValue != null) {
        setState(() => _orderIdConflictValue = null);
      }
    }
    String? warn;
    if (_orderIdRegex.hasMatch(orderId)) {
      final storageKey = FileNamingService.orderFolderName(orderId, widget.mode);
      if (_existingOrderIds.contains(storageKey)) {
        warn = 'Order $orderId already saved (${widget.mode.name.toUpperCase()})';
      } else if (_existingOrderIds.contains(orderId)) {
        warn = 'Order ID $orderId already in gallery';
      } else if (awb.isNotEmpty && (_awbOwners[awb]?.any((o) => o != orderId) ?? false)) {
        // Same AWB under the SAME order is normal (see _awbOwners); only
        // another order's AWB is suspicious. Judged once the Order ID is
        // known, so a half-filled form never flashes a false alarm.
        warn = 'AWB $awb already saved under a different order';
      }
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
    _scanWatchdog?.cancel();
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

  // ─── Live barcode reader (PK default) ─────────────────────────────────

  /// Detections arrive continuously while the reader is open, and values
  /// ACCUMULATE across frames instead of coming from one shot. The Order ID
  /// and AWB barcodes sit apart on an Amazon label and rarely fall inside the
  /// scan window together, so Sir can sweep the phone along the label and
  /// each one locks in as it passes. Nothing outside the window is ever
  /// considered — mobile_scanner drops those natively, in
  /// isBarcodeInScanWindow() on the Android side, so this really is a crop
  /// and not just an overlay.
  void _onBarcodesDetected(BarcodeCapture capture) {
    if (!mounted || !_barcodeMode) return;
    if (_saveTriggered || _switchingMode) return;

    final values = <String>[];
    for (final b in capture.barcodes) {
      final raw = b.rawValue?.trim();
      if (raw != null && raw.isNotEmpty) values.add(raw);
    }
    if (values.isEmpty) return;

    if (!_firstDetectionLogged && _scanOpenedAt != null) {
      _firstDetectionLogged = true;
      _scanWatchdog?.cancel();
      if (_scanStuck) setState(() => _scanStuck = false);
      final ms = DateTime.now().difference(_scanOpenedAt!).inMilliseconds;
      unawaited(ActivityLogService.log(
        event: 'barcode_scanner_first_detection',
        mode: widget.mode,
        extra: {'ms_since_open': '$ms'},
      ));
    }

    var changed = false;

    // Order ID — taken verbatim from the barcode, accepted only if it is
    // ALREADY exactly 3-7-7. No digit-guessing, no letter→digit fixups, no
    // "any 17 digits on the page" fallback: those are what put a tracking
    // number into this field in the first place. _crossCheckOrderId then
    // reads the same frame's printed digits and flags a disagreement, which
    // _maybeAutoSave treats as a block.
    if (!_orderIdRegex.hasMatch(_orderIdController.text.trim())) {
      for (final v in values) {
        if (_orderIdRegex.hasMatch(v)) {
          _orderIdController.text = v;
          _foundOrderId = true;
          changed = true;
          unawaited(_crossCheckOrderId(v, capture.image));
          break;
        }
      }
    }

    // AWB rides along on the same detections — free, since the label's AWB is
    // a barcode too. pickAwbFromBarcodes already skips Order-ID-shaped values,
    // so the two can never take each other's slot.
    if (_awbController.text.trim().isEmpty) {
      final pick = CarrierPatterns.pickAwbFromBarcodes(values);
      if (pick != null) {
        _awbController.text = pick.value;
        _detectedCarrierName = pick.carrier.name;
        _foundAwb = true;
        changed = true;
      }
    }

    if (!changed) return;
    HapticFeedback.mediumImpact();
    setState(() {
      _statusMessage = _foundOrderId && _foundAwb
          ? '✓ Order ID + AWB read'
          : _foundOrderId
              ? 'Order ID read — sweep across the AWB barcode'
              : 'AWB read — sweep across the Order ID barcode';
    });
    _maybeAutoSave('live');
  }

  /// Reads the SAME frame's printed digits and compares them with a
  /// barcode-read Order ID. Never touches the field's TEXT — only
  /// [_verifiedOrderIdValue]/[_orderIdConflictValue]; a disagreement is what
  /// makes [_maybeAutoSave] hold off.
  Future<void> _crossCheckOrderId(String barcodeValue, Uint8List? pngBytes) async {
    if (pngBytes == null) {
      // returnImage produced nothing for this frame (rare): no second read
      // to compare against, so nothing can disagree.
      _maybeAutoSave('live');
      return;
    }
    setState(() => _orderIdChecking = true);
    final ocrValue = await OcrService.extractOrderIdFromBytes(pngBytes);
    if (!mounted) return;
    // A newer detection or a manual edit may have superseded this candidate
    // while OCR ran — only apply the result to the value it was actually
    // checking.
    if (_orderIdController.text.trim() != barcodeValue) {
      setState(() => _orderIdChecking = false);
      return;
    }
    final check = OrderIdCrossCheck(barcode: barcodeValue, ocr: ocrValue);
    setState(() {
      _orderIdChecking = false;
      _orderIdConflictValue = check.conflicting ? ocrValue : null;
      if (check.confirmed) _verifiedOrderIdValue = barcodeValue;
      if (check.conflicting) {
        _statusMessage = 'Mismatch: barcode reads $barcodeValue, label text reads $ocrValue — check the label';
      }
    });
    if (check.conflicting) {
      unawaited(HapticFeedback.heavyImpact());
      unawaited(ActivityLogService.log(
        event: 'order_id_cross_check_conflict',
        mode: widget.mode,
        orderId: barcodeValue,
        extra: {'ocr_read': ocrValue ?? ''},
      ));
    }
    _maybeAutoSave('live');
  }

  // ─── Auto-save ─────────────────────────────────────────────────────────

  /// Why auto-save must NOT fire right now, or null when it may. Every
  /// scan-driven path (tap scan, auto-scan, live reader) asks this one
  /// question — the old code had three near-copies of the gate, one of which
  /// demanded barcode+OCR agreement and so almost never let a save through.
  ///
  /// Auto-save fires the moment BOTH the Order ID and the AWB are read and
  /// nothing is wrong with them: valid Order ID, no duplicate, and no
  /// positive barcode-vs-OCR disagreement.
  String? _autoSaveBlocker() {
    if (!_autoLabelSave) return 'setting_off';
    if (!_isValid) return 'order_id_invalid';
    if (_awbController.text.trim().isEmpty) return 'awb_missing';
    if (_orderIdChecking) return 'order_id_checking';
    if (_orderIdConflictValue != null) return 'order_id_conflict';
    if (_duplicateWarning != null) return 'duplicate';
    return null;
  }

  /// Saves and closes the popup if [_autoSaveBlocker] allows. [source] names
  /// the path that asked ('scan', 'auto_scan', 'live') for the analytics log.
  void _maybeAutoSave(String source) {
    if (!mounted || _saveTriggered || !_settingsLoaded) return;
    final blocker = _autoSaveBlocker();
    if (blocker != null) {
      // Nothing to say about an empty form; every other reason is worth a
      // row, once per change, so "auto-save didn't fire" is diagnosable from
      // the Firestore log instead of guessed at.
      if (blocker != 'order_id_invalid' && blocker != _lastAutoSaveBlock) {
        unawaited(ActivityLogService.log(
          event: 'auto_save_blocked',
          mode: widget.mode,
          orderId: _orderIdController.text.trim(),
          extra: {'reason': blocker, 'source': source},
        ));
      }
      _lastAutoSaveBlock = blocker;
      return;
    }
    _lastAutoSaveBlock = null;
    // Released again if _onSave declines (RT near-match dialog → Retake), so
    // one declined save cannot lock auto-save out for the rest of the popup.
    _saveTriggered = true;
    unawaited(_onSave(autoSource: source).whenComplete(() => _saveTriggered = false));
  }

  /// Hand the camera between the two readers. Only one may hold it: the
  /// MobileScanner widget opens the device itself, and CameraController would
  /// fail with "camera busy" if both were live at once. Order matters —
  /// release the old owner fully before the new one asks for the device.
  Future<void> _toggleScanMode() async {
    if (_switchingMode) return;
    _switchingMode = true;
    unawaited(HapticFeedback.selectionClick());
    _stopAutoScanLoop();
    try {
      if (!_barcodeMode) {
        final cam = _cam;
        _cam = null;
        _camReady = false;
        // Release the CameraController FIRST — same camera-device race as
        // BarcodeSavePopup's own open: mounting MobileScanner (via setState
        // below) before the old controller's dispose() completes makes it
        // fight the still-releasing hardware for the device. The `else`
        // branch below already gets this order right (await stop() before
        // setState); this branch didn't.
        await cam?.dispose();
        if (mounted) {
          setState(() {
            _barcodeMode = true;
            _statusMessage = 'Point the box at the barcode';
          });
        }
        _armScanWatchdog();
      } else {
        _scanWatchdog?.cancel();
        _scanStuck = false;
        await _scanner?.stop();
        if (mounted) {
          setState(() {
            _barcodeMode = false;
            _statusMessage = 'Text scan — tap SCAN with the label in frame';
          });
        }
        await _initCamera();
      }
    } catch (e) {
      debugPrint('scan mode switch failed: $e');
    } finally {
      _switchingMode = false;
      if (mounted) setState(() {});
    }
  }

  /// Starts (or restarts) the "has the reader detected anything yet" clock.
  /// Cancelled the moment [_onBarcodesDetected] sees its first real barcode,
  /// or when leaving barcode mode entirely.
  void _armScanWatchdog() {
    _scanWatchdog?.cancel();
    _scanWatchdog = Timer(const Duration(seconds: 6), () {
      if (!mounted || !_barcodeMode || _firstDetectionLogged) return;
      setState(() => _scanStuck = true);
      unawaited(ActivityLogService.log(event: 'barcode_scanner_stuck', mode: widget.mode));
    });
  }

  /// Stops and restarts the scanner's own camera session in place — the
  /// camera device should be long free by the time this is ever reachable
  /// (6s+ after this popup opened), so a fresh start() almost always clears
  /// whatever the initial race left stuck. "BARCODE TORN? USE TEXT SCAN"
  /// remains available underneath as a second escape hatch if it doesn't.
  Future<void> _retryScanner() async {
    unawaited(HapticFeedback.selectionClick());
    setState(() => _scanStuck = false);
    unawaited(ActivityLogService.log(event: 'barcode_scanner_retry', mode: widget.mode));
    try {
      await _scanner?.stop();
      await Future<void>.delayed(const Duration(milliseconds: 300));
      await _scanner?.start();
    } catch (e) {
      debugPrint('Scanner retry failed: $e');
    }
    if (mounted && _barcodeMode) _armScanWatchdog();
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
      // The popup may have started closing (hardware released) while the
      // shutter was firing — nothing left to analyse with.
      final scanner = _scanner;
      if (scanner == null) return;

      // Stage 1+2: barcode + OCR text on the same frame
      final results = await Future.wait([
        scanner.analyzeImage(xFile.path),
        OcrService.scanAll(xFile.path),
      ]);
      final barcodeResult = results[0] as BarcodeCapture?;
      final ocrResult = results[1] as OcrScanResult;

      // Stage 3: carrier hint from label text
      final carrierHint = CarrierPatterns.detectCarrierFromText(ocrResult.fullText);
      String? carrierName = carrierHint?.name;

      bool awbFound = _foundAwb;
      bool orderIdFound = _foundOrderId;

      // Collect every barcode raw value and find any that encodes the Order ID.
      // Assignment is deferred to Stage 6 below — barcode and OCR both read
      // this SAME frame, so whichever the Order ID turns out to be, it needs
      // the other channel's answer alongside it before either is trusted.
      final allBarcodes = barcodeResult?.barcodes ?? const <Barcode>[];
      final barcodeValues = <String>[];
      String? barcodeOrderId;
      for (final b in allBarcodes) {
        final raw = b.rawValue?.trim();
        if (raw == null || raw.isEmpty) continue;
        barcodeValues.add(raw);
        if (_orderIdRegex.hasMatch(raw)) {
          barcodeOrderId ??= raw;
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

      // Stage 6: Order ID — barcode and OCR both read this same still.
      final ocrOrderId = ocrResult.orderId;
      if (ocrOrderId != null) orderIdFound = true;
      _applyOrderIdReads(barcodeId: barcodeOrderId, ocrId: ocrOrderId);

      if (!mounted) return;
      String msg;
      // (Lock-feedback is fired by _onTextChanged() once both fields are
      //  valid — we let that path own the gating to keep manual-typing and
      //  scan-fill paths consistent.)
      final orderIdOk = _orderIdRegex.hasMatch(_orderIdController.text.trim());
      if (_orderIdConflictValue != null) {
        msg = 'Order ID mismatch — barcode and label text disagree, check the label';
      } else if (awbFound && orderIdOk) {
        msg = '✓ Locked${carrierName != null ? " · $carrierName" : ""} + Order ID';
      } else if (orderIdFound && !awbFound) {
        msg = 'Order ID found — no AWB detected, tap SCAN again';
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
      _maybeAutoSave(fromAuto ? 'auto_scan' : 'scan');
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

  /// Puts one scan's Order ID reads into the field and records whether the
  /// two channels agree. Barcode and OCR read the SAME captured still.
  ///
  /// A well-formed value already in the field is never overwritten — a rescan
  /// only re-judges it against the fresh reads, and only when at least one
  /// read is about THAT value (a read of some other order id must not
  /// silently confirm, or overwrite, what is there).
  void _applyOrderIdReads({String? barcodeId, String? ocrId}) {
    var filledNow = false;
    if (!_orderIdRegex.hasMatch(_orderIdController.text.trim())) {
      final chosen = barcodeId ?? ocrId;
      if (chosen == null) return;
      _orderIdController.text = chosen;
      filledNow = true;
    }
    final value = _orderIdController.text.trim();
    final canJudge = barcodeId != null &&
        ocrId != null &&
        (barcodeId == value || ocrId == value);
    if (!canJudge) {
      // Single-channel read: nothing to disagree with. A fresh fill drops any
      // verdict about the previous value; an existing field keeps its own.
      if (filledNow) _orderIdConflictValue = null;
      return;
    }
    final check = OrderIdCrossCheck(barcode: barcodeId, ocr: ocrId);
    _orderIdConflictValue = check.conflicting ? (barcodeId == value ? ocrId : barcodeId) : null;
    if (check.confirmed) _verifiedOrderIdValue = value;
  }

  void _validateInput() {
    final text = _orderIdController.text.trim();
    final formatOk = _orderIdRegex.hasMatch(text);
    final prefixOk = !formatOk || validOrderIdPrefixes.contains(text.substring(0, 3));
    final valid = formatOk && prefixOk;
    if (valid != _isValid || prefixOk != _prefixValid) {
      setState(() {
        _isValid = valid;
        _prefixValid = prefixOk;
      });
    }
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
      await HapticFeedback.heavyImpact();
      // Wait a beat so the double-pulse is perceptible.
      await Future<void>.delayed(const Duration(milliseconds: 90));
      await HapticFeedback.vibrate();
    } catch (e) {
      debugPrint('Lock haptic failed: $e');
    }
    try {
      await NativeCameraSound.playShutter();
    } catch (e) {
      debugPrint('Lock beep failed: $e');
    }
  }

  /// Every save path (auto-save, manual SAVE button) funnels through here —
  /// a single choke point for the RT near-match mismatch check, so it always
  /// runs "before an RT order id gets saved" regardless of how the save was
  /// triggered. [autoSource] is set only for auto-saves, for the log.
  Future<void> _onSave({String? autoSource}) async {
    if (!_isValid) return;
    var orderId = _orderIdController.text.trim();
    final awb = _awbController.text.trim();

    if (widget.mode == CaptureMode.rt) {
      final match = findNearMatch(orderId, _pkOrderIds);
      if (match != null) {
        final resolution = await _showMismatchDialog(orderId, match.candidate);
        if (!mounted) return;
        if (resolution == null || resolution == _MismatchResolution.retake) {
          // Fields stay populated so the user can correct manually or retake.
          return;
        }
        if (resolution == _MismatchResolution.useSuggested) {
          orderId = match.candidate;
          _orderIdController.text = orderId;
        }
        // .keep falls through with the originally typed orderId.
      }
    }

    // 'verified' traces whether this exact order id was independently
    // confirmed (barcode + label-text OCR agreed) before saving, or went
    // through on a single unconfirmed channel / manual entry / an RT
    // near-match override above. Whoever debugs a future PK<->RT mismatch
    // does not have to guess which case this was.
    unawaited(ActivityLogService.log(
      event: 'barcode_saved',
      mode: widget.mode,
      orderId: orderId,
      awb: awb.isEmpty ? null : awb,
      extra: {
        'verified': '${orderId == _verifiedOrderIdValue}',
        'auto_source': autoSource ?? 'manual',
      },
    ));
    await _releaseHardware();
    if (!mounted) return;
    Navigator.pop(context, {
      'orderId': orderId,
      'awb': awb.isEmpty ? null : awb,
    });
  }

  /// Flags a likely misprinted RT Order ID (1-3 digits off a known PK
  /// record). `barrierDismissible: false` + treating null (back/outside-tap)
  /// the same as Retake means this can never be silently bypassed into an
  /// unconfirmed save.
  Future<_MismatchResolution?> _showMismatchDialog(String typed, String suggested) {
    return showDialog<_MismatchResolution>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => RfGlassDialog(
        child: AlertDialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RfRadius.lg)),
          title: const Text('Order ID mismatch?', style: TextStyle(color: Colors.white)),
          content: Text(
            'You typed:\n$typed\n\nClosest packing (PK) record:\n$suggested\n\n'
            'Return labels are sometimes misprinted — pick the correct Order ID.',
            style: const TextStyle(color: RfColors.textSecondary, fontSize: 13, fontFamily: 'monospace', height: 1.4),
          ),
          actions: [
            RfButton.secondary(
              label: 'Retake',
              onPressed: () => Navigator.pop(ctx, _MismatchResolution.retake),
            ),
            RfButton.secondary(
              label: 'Keep as typed',
              onPressed: () => Navigator.pop(ctx, _MismatchResolution.keep),
            ),
            RfButton.primary(
              label: 'Use suggested ID',
              onPressed: () => Navigator.pop(ctx, _MismatchResolution.useSuggested),
            ),
          ],
        ),
      ),
    );
  }

  /// Set once [_releaseHardware] has run — the camera widgets must stop
  /// referencing the (now disposed) controllers.
  bool _hardwareReleased = false;

  /// Awaits the release of everything holding the camera, BEFORE this route
  /// hands its result back. The camera plugin's native side is one shared
  /// object: dispose() tears down whichever controller is CURRENT, not the one
  /// it was called on. A dispose left to State.dispose() runs ~300ms after the
  /// route pops — by then the capture screen can already be initialising its
  /// next controller (a QC-OK save has no photos to slow it down), and the
  /// late dispose tears THAT preview down: blank screen, yet recording still
  /// starts. Releasing here means nothing of ours is left to run late.
  Future<void> _releaseHardware() async {
    if (_hardwareReleased) return;
    _hardwareReleased = true;
    _stopAutoScanLoop();
    _scanWatchdog?.cancel();
    final cam = _cam;
    final scanner = _scanner;
    _cam = null;
    _camReady = false;
    _scanner = null;
    if (mounted) setState(() {});
    // Let the frame that drops the preview widgets finish before the
    // controllers behind them are disposed.
    await WidgetsBinding.instance.endOfFrame;
    try {
      await scanner?.dispose();
    } catch (e) {
      debugPrint('Scanner release failed: $e');
    }
    try {
      await cam?.dispose();
    } catch (e) {
      debugPrint('Camera release failed: $e');
    }
  }

  Future<void> _onCancel() async {
    await _releaseHardware();
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      // Every way out — the X, the system back gesture, a save — goes through
      // _releaseHardware first, so the popup never pops with a camera still
      // to be torn down behind its back.
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _onCancel();
      },
      child: _buildScaffold(),
    );
  }

  Widget _buildScaffold() {
    return RfGlassScaffold(
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
              onPressed: _isValid ? _onSave : null,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Stack(
          children: [
            Column(
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
                        ? RfColors.successLight
                        : RfColors.textSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ),

            const SizedBox(height: 10),

            // Controls row. The barcode reader is continuous — there is no
            // shot to take — so it shows only the escape hatch to text scan.
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: _barcodeMode
                  ? RfButton.secondary(
                      label: 'BARCODE TORN? USE TEXT SCAN',
                      icon: Icons.text_fields_rounded,
                      size: RfButtonSize.large,
                      fullWidth: true,
                      onPressed: _switchingMode ? null : _toggleScanMode,
                    )
                  : Row(children: [
                if (widget.mode == CaptureMode.pk) ...[
                  RfChip(
                    label: 'BARCODE',
                    active: false,
                    onPressed: _switchingMode ? null : _toggleScanMode,
                  ),
                  const SizedBox(width: 10),
                ],
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
                      color: RfColors.error.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: RfColors.error),
                    ),
                    child: Row(children: [
                      const Icon(Icons.warning_amber_rounded, color: RfColors.error, size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Duplicate — $_duplicateWarning',
                          style: const TextStyle(color: RfColors.error, fontSize: 12, fontWeight: FontWeight.w600),
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
                  errorText: _orderIdConflictValue != null
                      ? 'Mismatch — the label also reads $_orderIdConflictValue, check it before saving'
                      : (!_prefixValid && _orderIdController.text.trim().isNotEmpty)
                          ? 'Invalid Order ID prefix'
                          : null,
                  keyboardType: TextInputType.number,
                  inputFormatters: [_OrderIdInputFormatter()],
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
          ],
        ),
      ),
    );
  }

  /// 4:6 portrait camera box — sized to fill the Expanded slot. The camera
  /// preview IS the box (cover-cropped); no surrounding letterbox.
  Widget _buildCameraBox() {
    final locked = _foundAwb && _foundOrderId;
    final accent = locked ? RfColors.successLight : RfColors.amber;
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
                      child: _hardwareReleased
                          ? const SizedBox.expand()
                          : _barcodeMode
                          ? _buildBarcodeReader(width, height)
                          : _camReady && _cam != null
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
                        locked
                            ? '✓ LOCKED'
                            : _barcodeMode
                                ? 'BARCODE READER'
                                : 'AMAZON LABEL',
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

  /// The live reader. The scan window is a real crop, not decoration: the
  /// plugin discards every barcode whose bounding box falls outside it, so
  /// the numbers printed above and below the barcode band — tracking and
  /// reference codes, the ones OCR used to mistake for an Order ID — can no
  /// longer reach the fields at all.
  ///
  /// The band is wide and short because a label's barcodes are horizontal.
  /// Height is sized off the window's OWN width (not the camera box's height)
  /// so the box is a real rectangle on any device — the old `h * 0.44` tied
  /// the shape to the 4:6 portrait camera box and came out closer to square
  /// than to the short horizontal band a 1D barcode actually needs. A single
  /// barcode fits comfortably at this ratio; detections still accumulate
  /// across frames, so a sweep across the label catches Order ID and AWB one
  /// at a time just as well as it did with the taller window.
  Widget _buildBarcodeReader(double w, double h) {
    final winWidth = w * 0.86;
    final window = Rect.fromCenter(
      center: Offset(w / 2, h / 2),
      width: winWidth,
      height: winWidth * 0.30,
    );
    return Stack(
      fit: StackFit.expand,
      children: [
        MobileScanner(
          controller: _scanner!,
          scanWindow: window,
          onDetect: _onBarcodesDetected,
        ),
        Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(
              painter: _ScanWindowPainter(
                window: window,
                color: (_foundAwb && _foundOrderId)
                    ? RfColors.successLight
                    : RfColors.amber,
              ),
            ),
          ),
        ),
        if (_scanStuck)
          Positioned.fill(
            child: Container(
              color: Colors.black.withAlpha(200),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.camera_alt_outlined, color: Colors.white70, size: 28),
                      const SizedBox(height: 10),
                      const Text(
                        'Camera scanner stuck',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 14),
                      RfButton.primary(
                        label: 'Retry',
                        icon: Icons.refresh_rounded,
                        onPressed: _retryScanner,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  List<Widget> _cornerBrackets({Color color = RfColors.amber}) {
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
    String? errorText,
    List<TextInputFormatter>? inputFormatters,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text(label, style: const TextStyle(color: RfColors.textSecondary, fontSize: 11, fontWeight: FontWeight.w600)),
        if (detected) ...[
          const SizedBox(width: 6),
          const Icon(Icons.auto_awesome, color: RfColors.successLight, size: 10),
          const SizedBox(width: 3),
          const Text('auto', style: TextStyle(color: RfColors.successLight, fontSize: 9, fontStyle: FontStyle.italic)),
        ],
      ]),
      const SizedBox(height: 4),
      TextField(
        controller: controller,
        style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14, letterSpacing: 0.5),
        inputFormatters: inputFormatters,
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.15), fontFamily: 'monospace', fontSize: 14),
          filled: true,
          fillColor: RfColors.bg,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.border)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.border)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.rtAccent, width: 1.5)),
          errorText: errorText,
          errorMaxLines: 2,
          errorStyle: const TextStyle(color: RfColors.error, fontSize: 11),
          errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.error, width: 1.5)),
          focusedErrorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.error, width: 1.5)),
          suffixIcon: errorText == null && isValid
              ? const Icon(Icons.check_circle, color: RfColors.successLight, size: 18)
              : null,
          suffixIconConstraints: const BoxConstraints(minWidth: 28, minHeight: 28),
        ),
        keyboardType: keyboardType,
        autocorrect: false,
        textInputAction: TextInputAction.done,
      ),
    ]);
  }
}

/// Dims everything outside the scan window so it is obvious what the reader
/// is actually allowed to see. Purely cosmetic — the real filtering happens
/// natively inside mobile_scanner; this just makes the crop visible.
class _ScanWindowPainter extends CustomPainter {
  final Rect window;
  final Color color;
  const _ScanWindowPainter({required this.window, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(window, const Radius.circular(10));
    final scrim = Path.combine(
      PathOperation.difference,
      Path()..addRect(Offset.zero & size),
      Path()..addRRect(rrect),
    );
    canvas.drawPath(scrim, Paint()..color = Colors.black.withAlpha(150));
    canvas.drawRRect(
      rrect,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = color,
    );
  }

  @override
  bool shouldRepaint(_ScanWindowPainter old) =>
      old.window != window || old.color != color;
}
