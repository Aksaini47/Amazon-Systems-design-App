import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';
import '../config/app_config.dart';

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

    if (addTimestamp) {
      result = await addTimestampWatermark(result, DateTime.now());
    }

    if (AppConfig.isDemo) {
      result = await addDemoWatermark(result);
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

  /// Add a single-line date/time watermark at bottom-left of image, e.g.
  /// "14/05/2026 10:30:45". Order ID is deliberately NOT printed here — it
  /// comes from OCR on a shipping label, which can misread a faded label,
  /// and a wrong ID burned into the evidence photo can't be corrected later
  /// (no clean pre-watermark copy is kept). The date/time has no such risk,
  /// so only it gets stamped onto the pixels; the order ID lives solely in
  /// meta.json, where it's editable (see LocalStorageService.updateOrderMetadata).
  static Future<File> addTimestampWatermark(File file, DateTime dt) async {
    final bytes = await file.readAsBytes();
    final codec = await ui.instantiateImageCodec(Uint8List.fromList(bytes));
    final frame = await codec.getNextFrame();
    final original = frame.image;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final size = Size(original.width.toDouble(), original.height.toDouble());

    // Draw original image
    canvas.drawImage(original, Offset.zero, Paint());

    final text = DateFormat('dd/MM/yyyy HH:mm:ss').format(dt); // e.g. "14/05/2026 10:30:45"

    final fontSize = size.height * 0.018;
    final textStyle = TextStyle(
      color: const Color.fromARGB(255, 12, 215, 19),
      fontSize: fontSize,
      fontWeight: FontWeight.bold,
      fontFamily: 'monospace',
      shadows: const [Shadow(offset: Offset(1, 1), blurRadius: 3)],
    );

    final tp = TextPainter(text: TextSpan(text: text, style: textStyle), textDirection: ui.TextDirection.ltr);
    tp.layout();

    final offset = Offset(size.width * 0.03, size.height * 0.92 - tp.height);
    tp.paint(canvas, offset);

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

  /// Tiled, rotated "DEMO" watermark across the full frame — burned into
  /// every evidence photo in the demo build so a file pulled straight off
  /// the device (bypassing the app entirely) still can't be used for a real
  /// SAFE-T claim. Deliberately tiled rather than one line/band: a single
  /// band is trivially cropped out of a photo, a full tile is not.
  ///
  /// Kept as its own function rather than a bool param on
  /// [addTimestampWatermark] — the two watermarks have unrelated rationales
  /// (evidence integrity vs. demo licensing), and coupling them risked the
  /// demo stamp silently inheriting the user-facing "Photo timestamp"
  /// setting toggle. Called unconditionally from [processPhoto] when
  /// [AppConfig.isDemo] is true, regardless of that setting.
  static Future<File> addDemoWatermark(File file) async {
    final bytes = await file.readAsBytes();
    final codec = await ui.instantiateImageCodec(Uint8List.fromList(bytes));
    final frame = await codec.getNextFrame();
    final original = frame.image;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final size = Size(original.width.toDouble(), original.height.toDouble());

    canvas.drawImage(original, Offset.zero, Paint());

    const text = 'DEMO';
    final textStyle = TextStyle(
      color: Colors.white.withValues(alpha: 0.34),
      fontSize: size.width * 0.11,
      fontWeight: FontWeight.w800,
      letterSpacing: 2,
    );
    final tp = TextPainter(
      text: TextSpan(text: text, style: textStyle),
      textDirection: ui.TextDirection.ltr,
    )..layout();

    // Rotate the whole tile grid ~-28° around the image center, then paint
    // "DEMO" repeatedly on a grid wide/tall enough to still cover every
    // corner once rotated (hence the generous overflow margin below).
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(-28 * math.pi / 180);
    canvas.translate(-size.width / 2, -size.height / 2);

    final stepX = tp.width * 1.8;
    final stepY = tp.height * 3.0;
    final overflow = size.width + size.height;
    for (double y = -overflow; y < size.height + overflow; y += stepY) {
      for (double x = -overflow; x < size.width + overflow; x += stepX) {
        tp.paint(canvas, Offset(x, y));
      }
    }
    canvas.restore();

    final picture = recorder.endRecording();
    final uiImage = await picture.toImage(original.width, original.height);
    final byteData = await uiImage.toByteData(format: ui.ImageByteFormat.png);
    if (byteData != null) {
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
