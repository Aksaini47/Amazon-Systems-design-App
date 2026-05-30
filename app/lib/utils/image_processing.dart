import 'dart:io';
import 'dart:ui' as ui;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';

enum CustomOrientation { portraitUp, portraitDown, landscapeRight, landscapeLeft }

class ImageProcessingUtils {
  /// Maximum dimension (long edge) for saved photos. Resizes down if larger.
  /// 1500px is the standard for Amazon listing photos and keeps files small
  /// without sacrificing visible detail.
  static const int maxOutputDimension = 1500;

  /// Full pipeline: rotate → crop → resize → timestamp
  static Future<File> processPhoto(
    File file, {
    required CustomOrientation orientation,
    double? aspectRatio,
    bool addTimestamp = false,
    String? prefix,
  }) async {
    var result = file;

    // Rotate based on physical device orientation
    if (orientation != CustomOrientation.portraitUp) {
      result = await rotatePhoto(result, orientation);
    }

    // Crop to aspect ratio if specified
    if (aspectRatio != null) {
      result = await cropToAspectRatio(result, aspectRatio);
    }

    // Resize to max 1500px (long edge) BEFORE watermark so the watermark
    // size is calculated against the final resolution.
    result = await resizeToMax(result, maxOutputDimension);

    // Add 2-line watermark: Line 1 = order ID, Line 2 = datetime
    if (addTimestamp) {
      // prefix is in format "PK-{orderId}" or "RT-{orderId}"
      String orderId = prefix ?? '';
      if (orderId.contains('-')) {
        // Extract order ID from "PK-407-1234567-1234567" → "407-1234567-1234567"
        final parts = orderId.split('-');
        if (parts.length >= 3) {
          orderId = parts.sublist(1).join('-'); // skip mode prefix
        }
      }
      final dt = DateTime.now();
      result = await addTimestampWatermark(result, orderId, dt);
    }

    return result;
  }

  /// Rotate photo based on accelerometer-detected orientation
  static Future<File> rotatePhoto(File file, CustomOrientation orientation) async {
    final bytes = await file.readAsBytes();
    var image = img.decodeImage(bytes);
    if (image == null) return file;

    switch (orientation) {
      case CustomOrientation.landscapeRight:
        image = img.copyRotate(image, angle: -90);
        break;
      case CustomOrientation.landscapeLeft:
        image = img.copyRotate(image, angle: 90);
        break;
      case CustomOrientation.portraitDown:
        image = img.copyRotate(image, angle: 180);
        break;
      case CustomOrientation.portraitUp:
        break;
    }

    final encoded = img.encodeJpg(image, quality: 95);
    await file.writeAsBytes(encoded);
    return file;
  }

  /// Resize image so the longest edge is `maxDim` pixels (preserves aspect).
  /// No-op if image is already smaller. Writes back to the same file as JPEG.
  static Future<File> resizeToMax(File file, int maxDim) async {
    final bytes = await file.readAsBytes();
    var image = img.decodeImage(bytes);
    if (image == null) return file;

    final longest = image.width >= image.height ? image.width : image.height;
    if (longest <= maxDim) return file;  // already small enough

    if (image.width >= image.height) {
      image = img.copyResize(image, width: maxDim, interpolation: img.Interpolation.average);
    } else {
      image = img.copyResize(image, height: maxDim, interpolation: img.Interpolation.average);
    }

    final encoded = img.encodeJpg(image, quality: 92);
    await file.writeAsBytes(encoded);
    return file;
  }

  /// Center-crop to target aspect ratio (width/height)
  static Future<File> cropToAspectRatio(File file, double targetRatio) async {
    final bytes = await file.readAsBytes();
    var image = img.decodeImage(bytes);
    if (image == null) return file;

    final currentRatio = image.width / image.height;
    int cropW, cropH, offsetX, offsetY;

    if (currentRatio > targetRatio) {
      // Image is wider — crop width
      cropH = image.height;
      cropW = (cropH * targetRatio).round();
      offsetX = ((image.width - cropW) / 2).round();
      offsetY = 0;
    } else {
      // Image is taller — crop height
      cropW = image.width;
      cropH = (cropW / targetRatio).round();
      offsetX = 0;
      offsetY = ((image.height - cropH) / 2).round();
    }

    image = img.copyCrop(image, x: offsetX, y: offsetY, width: cropW, height: cropH);
    final encoded = img.encodeJpg(image, quality: 95);
    await file.writeAsBytes(encoded);
    return file;
  }

  /// Add 2-line watermark at bottom-left of image:
  ///   Line 1: order ID (e.g. "407-1234567-1234567")
  ///   Line 2: datetime (e.g. "14/05/2026 10:30:45")
  static Future<File> addTimestampWatermark(File file, String orderId, DateTime dt) async {
    final bytes = await file.readAsBytes();
    final codec = await ui.instantiateImageCodec(Uint8List.fromList(bytes));
    final frame = await codec.getNextFrame();
    final original = frame.image;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final size = Size(original.width.toDouble(), original.height.toDouble());

    // Draw original image
    canvas.drawImage(original, Offset.zero, Paint());

    // 2-line watermark text
    final line1 = 'Order id: $orderId'; // e.g. "Order id: 407-1234567-1234567"
    final line2 = DateFormat('dd/MM/yyyy HH:mm:ss').format(dt); // e.g. "14/05/2026 10:30:45"

    final baseFontSize = size.height * 0.016; // 1.6% — ~60px on 4K, ~30px on 1080p (2x previous)
    final textStyle = TextStyle(
      color: const Color.fromARGB(255, 12, 215, 19),
      fontSize: baseFontSize,
      fontWeight: FontWeight.bold,
      fontFamily: 'monospace',
      shadows: const [Shadow(offset: Offset(1, 1), blurRadius: 3, color: Colors.black)],
    );

    // Line 1: Order ID (larger, bold)
    final ts1 = TextStyle(color: textStyle.color, fontSize: baseFontSize * 1.2, fontWeight: FontWeight.bold, fontFamily: 'monospace', shadows: textStyle.shadows);
    final tp1 = TextPainter(text: TextSpan(text: line1, style: ts1), textDirection: ui.TextDirection.ltr);
    tp1.layout();

    // Line 2: Datetime (smaller)
    final ts2 = TextStyle(color: textStyle.color, fontSize: baseFontSize * 0.9, fontWeight: FontWeight.normal, fontFamily: 'monospace', shadows: textStyle.shadows);
    final tp2 = TextPainter(text: TextSpan(text: line2, style: ts2), textDirection: ui.TextDirection.ltr);
    tp2.layout();

    final totalHeight = tp1.height + tp2.height + 4; // 4px gap between lines
    final startY = size.height * 0.92 - totalHeight;
    final offset = Offset(size.width * 0.03, startY);

    tp1.paint(canvas, offset);
    tp2.paint(canvas, Offset(offset.dx, offset.dy + tp1.height + 4));

    final picture = recorder.endRecording();
    final uiImage = await picture.toImage(original.width, original.height);
    // Encode as JPEG to match .jpg file extension
    final byteData = await uiImage.toByteData(format: ui.ImageByteFormat.png);
    if (byteData != null) {
      // Convert PNG bytes to JPEG using the image package
      final pngBytes = byteData.buffer.asUint8List();
      final decodedImg = img.decodeImage(pngBytes);
      if (decodedImg != null) {
        final jpegBytes = img.encodeJpg(decodedImg, quality: 90);
        await file.writeAsBytes(jpegBytes);
      } else {
        await file.writeAsBytes(pngBytes);
      }
    }

    original.dispose();
    uiImage.dispose();
    return file;
  }

  /// Legacy single-line watermark (kept for compatibility)
  static Future<File> addTimestampWatermarkLegacy(File file, String text) async {
    final bytes = await file.readAsBytes();
    final codec = await ui.instantiateImageCodec(Uint8List.fromList(bytes));
    final frame = await codec.getNextFrame();
    final original = frame.image;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final size = Size(original.width.toDouble(), original.height.toDouble());

    canvas.drawImage(original, Offset.zero, Paint());

    final fontSize = size.height * 0.025;
    final textStyle = TextStyle(
      color: const Color.fromARGB(255, 12, 215, 19),
      fontSize: fontSize,
      fontWeight: FontWeight.bold,
      shadows: const [Shadow(offset: Offset(1, 1), blurRadius: 3, color: Colors.black)],
    );

    final textSpan = TextSpan(text: text, style: textStyle);
    final textPainter = TextPainter(text: textSpan, textDirection: ui.TextDirection.ltr);
    textPainter.layout();

    final offset = Offset(size.width * 0.03, size.height * 0.92 - textPainter.height);
    textPainter.paint(canvas, offset);

    final picture = recorder.endRecording();
    final uiImage = await picture.toImage(original.width, original.height);
    final byteData = await uiImage.toByteData(format: ui.ImageByteFormat.png);

    if (byteData != null) {
      // Convert PNG bytes to JPEG using the image package
      final pngBytes = byteData.buffer.asUint8List();
      final decodedImg = img.decodeImage(pngBytes);
      if (decodedImg != null) {
        final jpegBytes = img.encodeJpg(decodedImg, quality: 90);
        await file.writeAsBytes(jpegBytes);
      } else {
        await file.writeAsBytes(pngBytes);
      }
    }

    original.dispose();
    uiImage.dispose();
    return file;
  }

  /// Detect orientation from accelerometer values
  static CustomOrientation orientationFromAccelerometer(double x, double y, double z) {
    if (z < -8.0) return CustomOrientation.portraitDown;
    if (x > 5.0) return CustomOrientation.landscapeRight;
    if (x < -5.0) return CustomOrientation.landscapeLeft;
    return CustomOrientation.portraitUp;
  }
}
