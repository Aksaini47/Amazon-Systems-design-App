import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import '../services/ocr_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../utils/volume_button_service.dart';

class ScanResult {
  final String orderId;
  final String? productTitle;
  final String method; // 'barcode' | 'ocr' | 'manual'

  const ScanResult({required this.orderId, this.productTitle, required this.method});
}

class ScanScreen extends StatefulWidget {
  final String videoType; // 'packing' or 'unpacking'

  const ScanScreen({super.key, required this.videoType});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> with SingleTickerProviderStateMixin {
  final _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    facing: CameraFacing.back,
  );
  bool _processing = false;
  bool _torchOn = false;
  bool _cameraDisposed = false;
  String? _error;

  late AnimationController _animCtrl;
  late Animation<double> _scanLineAnim;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2));
    _scanLineAnim = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animCtrl, curve: Curves.easeInOut),
    );
    _animCtrl.repeat(reverse: true);

    VolumeButtonService().registerListener('scan_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (_processing) return;
      if (event == 1) _scanWithOcr();
      if (event == 2) _enterManually();
    });
  }

  @override
  void dispose() {
    VolumeButtonService().unregisterListener('scan_screen');
    _animCtrl.dispose();
    if (!_cameraDisposed) _controller.dispose();
    super.dispose();
  }

  Future<void> _onBarcodeDetected(BarcodeCapture capture) async {
    if (_processing) return;
    final barcode = capture.barcodes.firstOrNull;
    if (barcode?.rawValue == null) return;

    setState(() { _processing = true; _error = null; });
    HapticFeedback.mediumImpact();
    final awb = barcode!.rawValue!;

    try {
      final order = await ApiService.getOrderByAwb(awb);
      if (order != null && mounted) {
        await _stopAndPop(ScanResult(
          orderId: order.orderId,
          productTitle: order.productTitle,
          method: 'barcode',
        ));
      } else {
        setState(() { _error = 'AWB "$awb" not found.\nTry OCR scan or enter manually.'; _processing = false; });
      }
    } catch (e) {
      setState(() { _error = 'Lookup failed. Check connection.'; _processing = false; });
    }
  }

  /// Fully release scanner camera, then pop with result
  Future<void> _stopAndPop(ScanResult result) async {
    await _controller.stop();
    _controller.dispose();
    _cameraDisposed = true;
    await Future.delayed(const Duration(milliseconds: 300));
    if (mounted) Navigator.pop(context, result);
  }

  Future<void> _scanWithOcr() async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (file == null) return;

    setState(() { _processing = true; _error = null; });
    try {
      final orderId = await OcrService.extractOrderId(file.path);
      if (orderId != null && mounted) {
        await _stopAndPop(ScanResult(orderId: orderId, method: 'ocr'));
      } else {
        setState(() { _error = 'No Amazon Order ID found.\nMake sure the label is clearly visible.'; _processing = false; });
      }
    } catch (e) {
      setState(() { _error = 'OCR failed: $e'; _processing = false; });
    }
  }

  void _enterManually() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ManualEntrySheet(),
    ).then((result) {
      if (result != null && mounted) _stopAndPop(result);
    });
  }

  void _toggleTorch() {
    _controller.toggleTorch();
    setState(() => _torchOn = !_torchOn);
  }

  @override
  Widget build(BuildContext context) {
    final isUnpacking = widget.videoType == 'unpacking';
    final accentColor = isUnpacking ? RfColors.rtAccent : RfColors.pkAccent;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Camera
          MobileScanner(
            controller: _controller,
            onDetect: _onBarcodeDetected,
          ),

          // Dark overlay with cutout
          _ScanOverlay(accentColor: accentColor, animation: _scanLineAnim),

          // Top bar
          SafeArea(
            child: RfGlassOverlay(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
                    style: IconButton.styleFrom(backgroundColor: RfColors.glassFill(0.22)),
                  ),
                  const SizedBox(width: 8),
                  RfGlassPill(
                    tint: accentColor.withValues(alpha: 0.55),
                    borderColor: accentColor.withValues(alpha: 0.45),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    radius: 20,
                    child: Text(
                      isUnpacking ? 'UNPACKING' : 'PACKING',
                      style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 0.8),
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: _toggleTorch,
                    icon: Icon(
                      _torchOn ? Icons.flash_on_rounded : Icons.flash_off_rounded,
                      color: _torchOn ? Colors.amber : Colors.white,
                    ),
                    style: IconButton.styleFrom(backgroundColor: RfColors.glassFill(0.22)),
                  ),
                ],
              ),
            ),
          ),

          // Instruction text
          Positioned(
            top: MediaQuery.of(context).size.height * 0.28,
            left: 40, right: 40,
            child: Text(
              'Point at AWB barcode on shipping label',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withOpacity(0.85),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),

          // Processing indicator
          if (_processing)
            Center(
              child: RfGlassPill(
                padding: const EdgeInsets.all(20),
                radius: RfRadius.lg,
                child: const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                    SizedBox(height: 12),
                    Text('Looking up order...', style: TextStyle(color: Colors.white70, fontSize: 13)),
                  ],
                ),
              ),
            ),

          // Error toast
          if (_error != null)
            Positioned(
              bottom: 200,
              left: 24, right: 24,
              child: RfGlassContainer(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                tint: RfColors.errorBg.withValues(alpha: 0.55),
                borderColor: RfColors.error.withValues(alpha: 0.35),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline_rounded, color: Color(0xFFFF7B72), size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(_error!, style: const TextStyle(color: Color(0xFFFF7B72), fontSize: 13)),
                    ),
                    GestureDetector(
                      onTap: () => setState(() => _error = null),
                      child: const Icon(Icons.close, color: Colors.white38, size: 18),
                    ),
                  ],
                ),
              ),
            ),

          // Bottom action bar
          Positioned(
            bottom: 0, left: 0, right: 0,
            child: RfGlassOverlay(
              tint: RfGlass.fillElevated(0.62),
              child: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 40, 24, 16),
                  child: Column(
                    children: [
                      // Action buttons row
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          _BottomAction(
                            icon: Icons.document_scanner_outlined,
                            label: 'OCR Scan',
                            onTap: _processing ? null : _scanWithOcr,
                          ),
                          _BottomAction(
                            icon: Icons.keyboard_rounded,
                            label: 'Manual',
                            onTap: _processing ? null : _enterManually,
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'or scan AWB barcode above',
                        style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Dark overlay with transparent scan window and corner markers
class _ScanOverlay extends StatelessWidget {
  final Color accentColor;
  final Animation<double> animation;

  const _ScanOverlay({required this.accentColor, required this.animation});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    const cutoutWidth = 300.0;
    const cutoutHeight = 160.0;
    final top = size.height * 0.32;
    final left = (size.width - cutoutWidth) / 2;

    return Stack(
      children: [
        // Dark overlay with hole
        ColorFiltered(
          colorFilter: ColorFilter.mode(Colors.black.withOpacity(0.55), BlendMode.srcOut),
          child: Stack(
            children: [
              Container(
                decoration: const BoxDecoration(color: Colors.black, backgroundBlendMode: BlendMode.dstOut),
              ),
              Positioned(
                top: top,
                left: left,
                child: Container(
                  width: cutoutWidth,
                  height: cutoutHeight,
                  decoration: BoxDecoration(
                    color: Colors.red, // any opaque color — gets cut out
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ],
          ),
        ),
        // Corner markers
        Positioned(
          top: top,
          left: left,
          child: CustomPaint(
            size: const Size(cutoutWidth, cutoutHeight),
            painter: _CornerPainter(color: accentColor, radius: 16, length: 28, strokeWidth: 3),
          ),
        ),
        // Animated scan line
        AnimatedBuilder(
          animation: animation,
          builder: (_, __) {
            return Positioned(
              top: top + 8 + (cutoutHeight - 16) * animation.value,
              left: left + 20,
              child: Container(
                width: cutoutWidth - 40,
                height: 2,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      accentColor.withOpacity(0.0),
                      accentColor.withOpacity(0.8),
                      accentColor.withOpacity(0.0),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}

class _CornerPainter extends CustomPainter {
  final Color color;
  final double radius;
  final double length;
  final double strokeWidth;

  _CornerPainter({required this.color, required this.radius, required this.length, required this.strokeWidth});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    // Top-left
    canvas.drawPath(
      Path()
        ..moveTo(0, radius + length)
        ..lineTo(0, radius)
        ..arcToPoint(Offset(radius, 0), radius: Radius.circular(radius))
        ..lineTo(radius + length, 0),
      paint,
    );
    // Top-right
    canvas.drawPath(
      Path()
        ..moveTo(size.width - radius - length, 0)
        ..lineTo(size.width - radius, 0)
        ..arcToPoint(Offset(size.width, radius), radius: Radius.circular(radius))
        ..lineTo(size.width, radius + length),
      paint,
    );
    // Bottom-left
    canvas.drawPath(
      Path()
        ..moveTo(0, size.height - radius - length)
        ..lineTo(0, size.height - radius)
        ..arcToPoint(Offset(radius, size.height), radius: Radius.circular(radius))
        ..lineTo(radius + length, size.height),
      paint,
    );
    // Bottom-right
    canvas.drawPath(
      Path()
        ..moveTo(size.width - radius - length, size.height)
        ..lineTo(size.width - radius, size.height)
        ..arcToPoint(Offset(size.width, size.height - radius), radius: Radius.circular(radius))
        ..lineTo(size.width, size.height - radius - length),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// Bottom action button
class _BottomAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  const _BottomAction({required this.icon, required this.label, this.onTap});

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return GestureDetector(
      onTap: onTap,
      child: Opacity(
        opacity: disabled ? 0.4 : 1.0,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.12),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white.withOpacity(0.2)),
              ),
              child: Icon(icon, color: Colors.white, size: 24),
            ),
            const SizedBox(height: 6),
            Text(label, style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 11, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

// Bottom sheet for manual entry
class _ManualEntrySheet extends StatefulWidget {
  @override
  State<_ManualEntrySheet> createState() => _ManualEntrySheetState();
}

class _ManualEntrySheetState extends State<_ManualEntrySheet> {
  final _ctrl = TextEditingController();
  final _orderIdRegex = RegExp(r'^\d{3}-\d{7}-\d{7}$');
  bool _valid = false;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(() {
      final v = _orderIdRegex.hasMatch(_ctrl.text.trim());
      if (v != _valid) setState(() => _valid = v);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: RfGlassSheet(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 36, height: 4,
                decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 20),
            const Text('Enter Order ID', style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text('Amazon format: 403-1234567-1234567', style: TextStyle(color: Color(0xFF8B949E), fontSize: 13)),
            const SizedBox(height: 16),
            TextField(
              controller: _ctrl,
              style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 18, letterSpacing: 1),
              decoration: InputDecoration(
                hintText: '403-0000000-0000000',
                hintStyle: TextStyle(color: Colors.white.withOpacity(0.15), fontFamily: 'monospace', fontSize: 18),
                filled: true,
                fillColor: RfColors.glassFill(0.12),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Color(0xFF30363D)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Color(0xFF30363D)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Color(0xFF1F6FEB), width: 1.5),
                ),
                suffixIcon: _valid
                    ? const Icon(Icons.check_circle, color: Color(0xFF3FB950))
                    : null,
              ),
              keyboardType: TextInputType.number,
              autofocus: true,
            ),
            const SizedBox(height: 20),
            SizedBox(
              height: 50,
              child: ElevatedButton(
                onPressed: _valid
                    ? () {
                        Navigator.pop(context, ScanResult(orderId: _ctrl.text.trim(), method: 'manual'));
                      }
                    : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: RfColors.navy,
                  disabledBackgroundColor: RfColors.navy.withOpacity(0.3),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Confirm', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
        ),
      ),
    );
  }
}
