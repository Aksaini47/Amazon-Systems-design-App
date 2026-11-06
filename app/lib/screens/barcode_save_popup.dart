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
import '../utils/order_id_input_formatter.dart';
import '../utils/volume_button_service.dart';

/// Full-screen label scan — manual SCAN tap or optional auto-scan (Settings).
///
/// AWB detection logic (also documented in MainActivity DND channel comments):
///   - mobile_scanner.analyzeImage(frame) returns ALL barcodes in the image
///   - For each barcode's rawValue:
///       * if value matches `\d{3}-\d{7}-\d{7}` (or the website's
///         `RF-YYMMDD-NNNN`) → goes to Order ID field
///         (this is also how labels encode the Order ID barcode)
///       * otherwise → first such barcode becomes the AWB
///   - OCR also runs on the same frame as a fallback path for Order ID
///   - Final 3-7-7 validation gate stops malformed values from saving
class BarcodeSavePopup extends StatefulWidget {
  final CaptureMode mode;

  /// Opens on the live barcode reader (the default since 2026-11-06). Widget
  /// tests pass false: the scanner plugin does not exist in a test.
  final bool startInBarcodeMode;

  const BarcodeSavePopup({super.key, required this.mode, this.startInBarcodeMode = true});
  @override
  State<BarcodeSavePopup> createState() => _BarcodeSavePopupState();
}

/// User's choice when a scanned/typed RT Order ID is a near-match (1-3
/// digits off) of a known PK Order ID.
enum _MismatchResolution { useSuggested, keep, retake }

class _BarcodeSavePopupState extends State<BarcodeSavePopup> {
  final _orderIdController = TextEditingController();
  final _awbController = TextEditingController();
  // Amazon's Order ID prefixes — every valid order id starts with one of these.
  bool _isValid = false;
  bool _prefixValid = true;
  // The AWB may be blank; a typed RT AWB must have at least 12 digits (see
  // awbAllowsSave); PK takes any. Kept as state, like _isValid, so the SAVE
  // button follows every keystroke.
  late bool _awbOk = awbAllowsSave(widget.mode, '');
  bool get _canSave => _isValid && _awbOk;
  String _lastAwbText = '';

  /// RT only: AWB candidates the scanner may pick — digits, at least 12.
  bool Function(String)? get _awbAccept => widget.mode == CaptureMode.rt ? isValidReturnAwb : null;

  /// RT only: when a label offers a 12-digit and a longer valid code, take the
  /// 12-digit one (the usual return AWB).
  bool Function(String)? get _awbPrefer => widget.mode == CaptureMode.rt ? isStandardReturnAwb : null;

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

  // An AWB that came from OCR TEXT (not a barcode) and either holds letters
  // or needed look-alike repair: shown amber, and auto-save waits for Sir's
  // SAVE tap. Cleared by a barcode read or by any manual edit of the field.
  bool _awbNeedsReview = false;
  bool _awbFromScan = false;

  static const _barcodeHint = 'Barcode: hold the strip over ONE barcode — Order ID, then AWB';

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
  // Watches the CAMERA, not the barcodes. mobile_scanner's Android side sends
  // nothing at all while no barcode is in the window, so the first version
  // (2026-09-23: "no detection within 6s = stuck") flagged a perfectly live
  // preview as stuck whenever Sir simply had not put a label under it yet —
  // and Retry "never worked" because the same 6s clock fired again (Sir,
  // 2026-11-06, screenshot with a live preview behind "Camera scanner
  // stuck"). Stuck now means the camera itself failed: start() reported an
  // error, or the session is still not running 5s after it was asked to.
  // A running camera with no barcode yet only changes the hint line.
  Timer? _scanWatchdog;
  bool _scanStuck = false;
  /// Bumped on every hard reset so the MobileScanner widget is rebuilt
  /// from scratch around the fresh controller.
  int _scannerGeneration = 0;

  static const _noBarcodeHint = 'No barcode in the strip yet — bring the label closer, or use TEXT';

  /// The live reader's controller. Tuned for speed (Sir, 2026-11-06, "barcode
  /// laggy"):
  ///  - Only the symbologies shipping labels use. ML Kit runs one detector per
  ///    requested format on every frame; dropping PDF417, DataMatrix and
  ///    EAN-13 (a retail product code, never an Order ID or AWB) cuts the work
  ///    per frame — Google's own ML Kit guidance for faster scanning.
  ///  - DetectionSpeed.unrestricted: every camera frame is analysed. The
  ///    default (normal) analyses at most one frame per 250 ms, which is the
  ///    "it sees the barcode but takes a moment" feel. CameraX's
  ///    keep-only-latest backpressure means frames never queue up, so this
  ///    costs CPU, not latency, and the reader is open only for seconds.
  ///  - 1920x1080 analysis: the Order ID barcode has narrower bars than the
  ///    AWB one and only decodes at ~1.5-2x the default resolution.
  ///  - No frame image (returnImage false): the per-frame PNG + OCR
  ///    cross-check was the 2026-09-23 lag. A decoded Code128 value carries
  ///    its own checksum, so it is trusted as read.
  MobileScannerController _newScanner() {
    return MobileScannerController(
      formats: const [
        BarcodeFormat.code128,
        BarcodeFormat.code39,
        BarcodeFormat.qrCode,
      ],
      detectionSpeed: DetectionSpeed.unrestricted,
      cameraResolution: const Size(1920, 1080),
    )..addListener(_onScannerState);
  }

  /// Camera session changes (running / error). An error is a real failure —
  /// show Retry at once; a running session clears any stuck overlay.
  void _onScannerState() {
    final state = _scanner?.value;
    if (state == null || !mounted || !_barcodeMode || _switchingMode) return;
    if (state.error != null) {
      _markScannerStuck('error_${state.error!.errorCode.name}');
    } else if (state.isRunning && _scanStuck) {
      setState(() => _scanStuck = false);
    }
  }

  void _markScannerStuck(String reason) {
    if (_scanStuck || !mounted) return;
    _scanWatchdog?.cancel();
    setState(() => _scanStuck = true);
    unawaited(ActivityLogService.log(
      event: 'barcode_scanner_stuck',
      mode: widget.mode,
      extra: {'reason': reason},
    ));
  }

  @override
  void initState() {
    super.initState();
    _scanOpenedAt = DateTime.now();
    _orderIdController.addListener(_onTextChanged);
    _awbController.addListener(_onTextChanged);
    _scanner = _newScanner();
    // Barcode reader is the DEFAULT in both PK and RT again (Sir, 2026-11-06):
    // Nimbus now prints a proper Order ID barcode, and a barcode read is exact
    // where OCR mixes up 0/O, 1/I and friends. It was switched off on
    // 2026-09-23 for lag; the per-frame PNG + OCR cross-check behind that is
    // gone (returnImage above). OCR ("TEXT") stays one tap away on the
    // switcher for torn or faded labels.
    _barcodeMode = widget.startInBarcodeMode;
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
    if (_barcodeMode) {
      if (mounted) setState(() => _statusMessage = _barcodeHint);
      _armScanWatchdog();
    } else {
      await _initCamera();
    }
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
    // The RT AWB error text counts the digits typed so far, so every AWB
    // change has to repaint — not only the ones that flip _awbOk.
    if (awb != _lastAwbText) {
      _lastAwbText = awb;
      // Sir typing in the field is the check the review flag asked for.
      if (!_awbFromScan) _awbNeedsReview = false;
      if (mounted) setState(() {});
    }
    // A mismatch verdict belongs to the value it was reached about; a new or
    // retyped Order ID starts clean. Scan fills assign the text BEFORE they
    // set the verdict, so this never wipes a fresh one.
    if (orderId != _lastOrderIdText) {
      _lastOrderIdText = orderId;
      // Repaint on every Order ID change: the "needs a real date" hint depends
      // on the text, not only on the flags _validateInput flips.
      if (mounted) {
        setState(() {
          if (_orderIdConflictValue != null) _orderIdConflictValue = null;
        });
      }
    }
    String? warn;
    if (isOrderIdShape(orderId)) {
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

    // Lock-state feedback: both fields filled + Order ID is valid 3-7-7 (+ a
    // typed RT AWB has at least 12 digits).
    final isLocked = _canSave && awb.isNotEmpty;
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

    // Order ID — taken verbatim from the barcode, accepted only if it ALREADY
    // has an order id shape (Amazon 3-7-7 or website RF-YYMMDD-NNNN). No
    // digit-guessing, no letter→digit fixups, no "any 17 digits on the page"
    // fallback: those are what put a tracking number into this field in the
    // first place.
    if (!isOrderIdShape(_orderIdController.text.trim())) {
      for (final v in values) {
        if (isOrderIdShape(v)) {
          _orderIdController.text = v;
          _orderIdConflictValue = null;
          _foundOrderId = true;
          changed = true;
          break;
        }
      }
    }

    // AWB rides along on the same detections — free, since the label's AWB is
    // a barcode too. pickAwbFromBarcodes already skips Order-ID-shaped values,
    // so the two can never take each other's slot.
    if (_awbController.text.trim().isEmpty) {
      final pick = CarrierPatterns.pickAwbFromBarcodes(values, accept: _awbAccept, prefer: _awbPrefer);
      if (pick != null) {
        _fillAwb(pick.value, needsReview: false);
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

  /// Puts a scanned AWB into the field without it counting as a manual edit.
  void _fillAwb(String value, {required bool needsReview}) {
    _awbFromScan = true;
    _awbController.text = value;
    _awbFromScan = false;
    _awbNeedsReview = needsReview;
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
    if (_awbNeedsReview) return 'awb_needs_review';
    if (!_awbOk) return 'awb_not_12_digits';
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
            _statusMessage = _barcodeHint;
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
            _statusMessage = 'Text (OCR): put the label in the box, then tap SCAN';
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

  /// Gives the camera 5 s to come up after the reader is mounted (open,
  /// switch back from TEXT, Retry). Still not running, or errored = stuck.
  /// Running but no barcode yet is normal — only the hint line changes.
  void _armScanWatchdog() {
    _scanWatchdog?.cancel();
    _scanWatchdog = Timer(const Duration(seconds: 5), () {
      if (!mounted || !_barcodeMode || _switchingMode || _hardwareReleased) return;
      final state = _scanner?.value;
      if (state == null || state.error != null || !state.isRunning) {
        _markScannerStuck(state?.error != null ? 'error' : 'not_running_5s');
        return;
      }
      if (!_firstDetectionLogged && !_foundOrderId && !_foundAwb) {
        setState(() => _statusMessage = _noBarcodeHint);
      }
    });
  }

  /// Hard reset of the live reader: the old controller is unmounted and
  /// disposed (which also stops the native camera session), and a brand-new
  /// controller + MobileScanner widget start from scratch. The old Retry only
  /// did stop()/start() on the same controller, and a start() that had hung
  /// half-way was left exactly where it was.
  Future<void> _retryScanner() async {
    if (_switchingMode || _hardwareReleased) return;
    _switchingMode = true;
    unawaited(HapticFeedback.selectionClick());
    unawaited(ActivityLogService.log(event: 'barcode_scanner_retry', mode: widget.mode));
    _scanWatchdog?.cancel();
    final old = _scanner;
    old?.removeListener(_onScannerState);
    setState(() {
      _scanStuck = false;
      _scanner = null;
      _statusMessage = 'Restarting the barcode camera…';
    });
    try {
      // Let the frame that unmounts the old reader land before its
      // controller goes away underneath it.
      await WidgetsBinding.instance.endOfFrame;
      await old?.dispose();
      await Future<void>.delayed(const Duration(milliseconds: 300));
    } catch (e) {
      debugPrint('Scanner reset failed: $e');
    } finally {
      _switchingMode = false;
    }
    if (!mounted || _hardwareReleased) return;
    setState(() {
      _scanner = _newScanner();
      _scannerGeneration++;
      _statusMessage = _barcodeHint;
    });
    if (_barcodeMode) _armScanWatchdog();
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
        if (isOrderIdShape(raw)) {
          barcodeOrderId ??= raw;
          orderIdFound = true;
        }
      }
      debugPrint('Scan: ${barcodeValues.length} barcode(s), carrier hint=$carrierName');

      // Stage 4: pick the best AWB from barcodes (skips Order-ID-pattern ones)
      final awbPick = CarrierPatterns.pickAwbFromBarcodes(
        barcodeValues,
        hint: carrierHint,
        accept: _awbAccept,
        prefer: _awbPrefer,
      );
      if (awbPick != null) {
        if (_awbController.text.trim().isEmpty) {
          _fillAwb(awbPick.value, needsReview: false);
        }
        awbFound = true;
        carrierName = awbPick.carrier.name;  // override hint with actual match
      }

      // Stage 5: fallback — find AWB in OCR text if no barcode classified
      if (!awbFound) {
        final textPick = CarrierPatterns.findAwbInText(
          ocrResult.fullText,
          hint: carrierHint,
          accept: _awbAccept,
          prefer: _awbPrefer,
        );
        if (textPick != null) {
          if (_awbController.text.trim().isEmpty) {
            // Letters or repaired look-alikes from OCR are exactly what goes
            // wrong — Sir checks those before the save.
            _fillAwb(
              textPick.value,
              needsReview: textPick.ocrFixes > 0 || textPick.value.contains(RegExp(r'[A-Z]')),
            );
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
      final orderIdOk = isOrderIdShape(_orderIdController.text.trim());
      if (_orderIdConflictValue != null) {
        msg = 'Order ID mismatch — barcode and label text disagree, check the label';
      } else if (_awbNeedsReview) {
        msg = 'AWB read from label TEXT — check it, then tap SAVE';
      } else if (awbFound && orderIdOk) {
        msg = '✓ Locked${carrierName != null ? " · $carrierName" : ""} + Order ID';
      } else if (orderIdFound && !awbFound) {
        msg = widget.mode == CaptureMode.rt
            ? 'Order ID found — no valid AWB read, tap SCAN again, type it, or SAVE without'
            : 'Order ID found — no AWB detected, tap SCAN again';
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
    if (!isOrderIdShape(_orderIdController.text.trim())) {
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
    final formatOk = isOrderIdShape(text);
    // The website id (RF-YYMMDD-NNNN) has no Amazon prefix to gate on.
    final prefixOk = !formatOk || isWebsiteOrderId(text) || validOrderIdPrefixes.contains(text.substring(0, 3));
    final valid = formatOk && prefixOk;
    final awbOk = awbAllowsSave(widget.mode, _awbController.text);
    if (valid != _isValid || prefixOk != _prefixValid || awbOk != _awbOk) {
      setState(() {
        _isValid = valid;
        _prefixValid = prefixOk;
        _awbOk = awbOk;
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
    if (!_canSave) return;
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
          title: const Text('Order ID mismatch?', style: TextStyle(color: RfColors.textPrimary)),
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
              onPressed: _canSave ? _onSave : null,
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
            // shot to take, so only TEXT (OCR) mode has zoom + SCAN. Switching
            // between the two is the floating switcher under the camera box.
            if (!_barcodeMode)
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
                  hint: '407-1234567-1234567  or  RF-261104-0004',
                  labelAction: _buildRfPrefixButton(),
                  detected: _foundOrderId,
                  isValid: _isValid,
                  errorText: _orderIdConflictValue != null
                      ? 'Mismatch — the label also reads $_orderIdConflictValue, check it before saving'
                      : (!_prefixValid && _orderIdController.text.trim().isNotEmpty)
                          ? 'Invalid Order ID prefix'
                          : _badWebsiteDate
                              ? 'Website order ID needs a real date: RF-YYMMDD-NNNN'
                              : null,
                  // English keyboard (letters for RF- ids); OrderIdInputFormatter
                  // keeps each shape strict.
                  keyboardType: TextInputType.visiblePassword,
                  inputFormatters: [OrderIdInputFormatter()],
                ),
                const SizedBox(height: 8),
                _buildAwbField(),
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

  /// Height kept free under the camera box for the mode switcher.
  static const _switcherSpace = 56.0;

  /// Camera box — sized to fill the Expanded slot. The camera preview IS the
  /// box (cover-cropped); no surrounding letterbox. Its shape follows the
  /// mode (Sir, 2026-11-06): BARCODE is a very short, full-width strip, so
  /// only one 1D barcode fits in it at a time; TEXT (OCR) is 3:4 portrait,
  /// enough of the label for the printed lines.
  Widget _buildCameraBox() {
    final locked = _foundAwb && _foundOrderId;
    final accent = locked ? RfColors.successLight : RfColors.amber;
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxH = (constraints.maxHeight - _switcherSpace).clamp(0.0, double.infinity);
        double width, height;
        if (_barcodeMode) {
          width = constraints.maxWidth;
          height = (width * 0.42).clamp(0.0, maxH);
        } else if (constraints.maxWidth * 4 / 3 <= maxH) {
          width = constraints.maxWidth;
          height = width * 4 / 3;
        } else {
          height = maxH;
          width = height * 3 / 4;
        }
        return Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(
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
                          : const Center(child: CircularProgressIndicator(strokeWidth: 2, color: RfColors.textMuted)),
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
                                ? 'BARCODE'
                                : 'TEXT (OCR)',
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
          const SizedBox(height: 10),
          _buildModeSwitcher(),
          ]),
        );
      },
    );
  }

  /// Floating BARCODE | TEXT switcher under the camera box. One tap hands the
  /// camera over (see [_toggleScanMode]); a tap on the active side does nothing.
  Widget _buildModeSwitcher() {
    Widget side(String label, IconData icon, bool barcode) {
      final active = _barcodeMode == barcode;
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: (active || _switchingMode) ? null : _toggleScanMode,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: active ? RfColors.amber.withValues(alpha: 0.9) : Colors.transparent,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 15, color: active ? Colors.black : Colors.white70),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: active ? Colors.black : Colors.white70,
                fontSize: 11.5,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.8,
              ),
            ),
          ]),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: Colors.black.withAlpha(170),
        borderRadius: BorderRadius.circular(21),
        border: Border.all(color: Colors.white24),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        side('BARCODE', Icons.view_week_rounded, true),
        side('TEXT', Icons.text_fields_rounded, false),
      ]),
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
    // The camera box itself is already the short strip, so the window is
    // that strip with a small margin.
    final window = Rect.fromLTWH(w * 0.04, h * 0.12, w * 0.92, h * 0.76);
    final scanner = _scanner;
    return Stack(
      fit: StackFit.expand,
      children: [
        if (scanner == null)
          // Between the old and the new controller during a Retry.
          const Center(child: CircularProgressIndicator(strokeWidth: 2, color: RfColors.textMuted))
        else
          MobileScanner(
            key: ValueKey('barcode_reader_$_scannerGeneration'),
            controller: scanner,
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
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  // Compact: the barcode strip is short.
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    spacing: 10,
                    runSpacing: 6,
                    children: [
                      const Text(
                        'Camera not starting',
                        style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700),
                      ),
                      RfButton.primary(
                        label: 'Retry',
                        icon: Icons.refresh_rounded,
                        onPressed: _retryScanner,
                      ),
                      RfButton.secondary(
                        label: 'TEXT',
                        icon: Icons.text_fields_rounded,
                        onPressed: _switchingMode ? null : _toggleScanMode,
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

  /// Tracking field, English keyboard, CAPITALS, letters/digits only.
  /// RT: optional, but a typed AWB needs 12+ digits or an exact lettered
  /// courier format (India Post / DTDC / Shadowfax / Ekart / Xpressbees).
  /// PK: free, optional, with the carrier the scan recognised in the label.
  Widget _buildAwbField() {
    final typed = _awbController.text.trim();
    final review = _awbNeedsReview ? 'Read from the label TEXT — check it, then tap SAVE' : null;
    if (widget.mode != CaptureMode.rt) {
      return _buildField(
        label: _detectedCarrierName != null
            ? 'AWB / Tracking — ${_detectedCarrierName!}'
            : 'AWB / Tracking (optional)',
        controller: _awbController,
        hint: '1Z999AA10123456784',
        detected: _foundAwb,
        helperText: review,
        keyboardType: TextInputType.visiblePassword,
        inputFormatters: [AwbInputFormatter()],
      );
    }
    String? error;
    if (typed.isNotEmpty && !_awbOk) {
      error = RegExp(r'^\d+$').hasMatch(typed)
          ? 'AWB must be at least 12 digits (${typed.length} entered)'
          : 'Not a known format — 12+ digits, or India Post / DTDC / Shadowfax / Ekart / Xpressbees';
    }
    final courier = returnLetteredCourierFor(typed);
    return _buildField(
      label: courier != null
          ? 'AWB / Tracking (optional) — $courier'
          : 'AWB / Tracking (optional) — 12+ digits or courier',
      controller: _awbController,
      hint: '123456789012  or  EK123456789IN',
      detected: _foundAwb,
      // A blank field is allowed, but not a "valid AWB" - no green tick for it.
      isValid: typed.isNotEmpty && _awbOk,
      errorText: error,
      helperText: error == null ? review : null,
      keyboardType: TextInputType.visiblePassword,
      inputFormatters: [AwbInputFormatter()],
    );
  }

  /// A full-length RF- id whose date part is not a real calendar date.
  bool get _badWebsiteDate {
    final t = _orderIdController.text.trim();
    return t.startsWith('RF-') && t.length == 14 && !isWebsiteOrderId(t);
  }

  /// "RF-" shortcut beside the Order ID label: the keyboard here is numeric, so
  /// the website prefix is one tap (then digits only: 261104 and 0004).
  Widget _buildRfPrefixButton() {
    return GestureDetector(
      onTap: () {
        _orderIdController.value = const TextEditingValue(
          text: 'RF-',
          selection: TextSelection.collapsed(offset: 3),
        );
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          border: Border.all(color: RfColors.border),
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Text('RF-', style: TextStyle(color: RfColors.textSecondary, fontSize: 10, fontWeight: FontWeight.w700)),
      ),
    );
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
    Widget? labelAction,
    String? helperText,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Flexible(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: RfColors.textSecondary, fontSize: 11, fontWeight: FontWeight.w600))),
        if (detected) ...[
          const SizedBox(width: 6),
          const Icon(Icons.auto_awesome, color: RfColors.successLight, size: 10),
          const SizedBox(width: 3),
          const Text('auto', style: TextStyle(color: RfColors.successLight, fontSize: 9, fontStyle: FontStyle.italic)),
        ],
        if (labelAction != null) ...[const Spacer(), labelAction],
      ]),
      const SizedBox(height: 4),
      TextField(
        controller: controller,
        style: const TextStyle(color: RfColors.textPrimary, fontFamily: 'monospace', fontSize: 14, letterSpacing: 0.5),
        inputFormatters: inputFormatters,
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.15), fontFamily: 'monospace', fontSize: 14),
          filled: true,
          fillColor: RfColors.card,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.border)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.border)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.action, width: 1.5)),
          errorText: errorText,
          errorMaxLines: 2,
          helperText: helperText,
          helperMaxLines: 2,
          helperStyle: const TextStyle(color: RfColors.amber, fontSize: 11, fontWeight: FontWeight.w600),
          errorStyle: const TextStyle(color: RfColors.error, fontSize: 11),
          errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.error, width: 1.5)),
          focusedErrorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: RfColors.error, width: 1.5)),
          suffixIcon: errorText == null && isValid
              ? const Icon(Icons.check_circle, color: RfColors.successLight, size: 18)
              : null,
          suffixIconConstraints: const BoxConstraints(minWidth: 28, minHeight: 28),
        ),
        keyboardType: keyboardType,
        textCapitalization: TextCapitalization.characters,
        enableSuggestions: false,
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
