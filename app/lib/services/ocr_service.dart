import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

/// Amazon Order ID extraction — "nuclear" multi-stage pipeline.
///
/// Final pattern: `xxx-xxxxxxx-xxxxxxx` (3-7-7 numeric digits).
///
/// Pipeline stages, applied in order, returning the first match:
///   1. Strict regex on raw OCR text per-block, then full-text.
///   2. Apply digit-confusion fixes (O→0, I→1, l→1, S→5, Z→2, B→8, G→6, D→0,
///      Q→0, T→7) and retry strict regex.
///   3. Loose regex allowing space / underscore / em-dash separators
///      instead of hyphens — handles "407 1234567 1234567".
///   4. Tight regex on 17 consecutive digits (no separators) — auto-format
///      to 3-7-7.
///   5. Keyword-context search: locate "Order ID", "Order #", "Order no.",
///      etc., and re-run stages 1-4 on the text following the keyword.
///
/// Returns null if no candidate passes the 3-7-7 numeric check.
class OcrService {
  static final _recognizer = TextRecognizer(script: TextRecognitionScript.latin);

  // ─── Patterns ─────────────────────────────────────────────────────────

  /// Strict — hyphenated 3-7-7 with word boundaries.
  static final _strict = RegExp(r'\b(\d{3}-\d{7}-\d{7})\b');

  /// Loose — any of [space, hyphen, underscore, em-dash] as separator.
  /// Captures the three numeric groups so we can rejoin with hyphens.
  static final _loose = RegExp(r'(\d{3})[\s\-_–—]+(\d{7})[\s\-_–—]+(\d{7})');

  /// Tight — exactly 17 consecutive digits at a word boundary.
  static final _tight = RegExp(r'\b(\d{17})\b');

  /// Keyword detector — "order id", "order no", "order #", "order:", etc.
  /// Captures the rest of the line after the keyword for downstream extraction.
  static final _keyword = RegExp(
    r'(?:order\s*(?:id|no\.?|number|#)?)\s*[:\.\-#]?\s*([^\r\n]{0,80})',
    caseSensitive: false,
  );

  // ─── Digit-confusion fix ──────────────────────────────────────────────

  /// Translate common OCR letter→digit confusions. Only applied transiently
  /// to candidate strings for pattern-matching — never mutates user-facing text.
  static String _digitize(String s) {
    final buf = StringBuffer();
    for (final c in s.codeUnits) {
      switch (c) {
        case 0x4F: case 0x6F: case 0x44: case 0x51: buf.writeCharCode(0x30); break;       // O, o, D, Q → 0
        case 0x49: case 0x69: case 0x6C: case 0x7C: buf.writeCharCode(0x31); break;       // I, i, l, | → 1
        case 0x5A: case 0x7A: buf.writeCharCode(0x32); break;                              // Z, z → 2
        case 0x53: case 0x73: buf.writeCharCode(0x35); break;                              // S, s → 5
        case 0x47: buf.writeCharCode(0x36); break;                                         // G → 6
        case 0x54: buf.writeCharCode(0x37); break;                                         // T → 7
        case 0x42: buf.writeCharCode(0x38); break;                                         // B → 8
        default: buf.writeCharCode(c);
      }
    }
    return buf.toString();
  }

  // ─── Single-candidate extraction ──────────────────────────────────────

  /// Run stages 1-4 on one text candidate. Returns the formatted order ID
  /// or null. Never returns malformed strings — every return goes through
  /// the strict 3-7-7 final check.
  static String? _extractFrom(String text) {
    if (text.isEmpty) return null;

    // Stage 1: strict on raw
    final m1 = _strict.firstMatch(text);
    if (m1 != null) return _validate(m1.group(1));

    // Stage 2: strict on digit-fixed
    final fixed = _digitize(text);
    final m2 = _strict.firstMatch(fixed);
    if (m2 != null) return _validate(m2.group(1));

    // Stage 3: loose with non-hyphen separators
    final m3 = _loose.firstMatch(text) ?? _loose.firstMatch(fixed);
    if (m3 != null) {
      return _validate('${m3.group(1)}-${m3.group(2)}-${m3.group(3)}');
    }

    // Stage 4: tight 17-digit sequence
    final m4 = _tight.firstMatch(text) ?? _tight.firstMatch(fixed);
    if (m4 != null) {
      final d = m4.group(1)!;
      return _validate('${d.substring(0, 3)}-${d.substring(3, 10)}-${d.substring(10, 17)}');
    }

    return null;
  }

  /// Final gate — only return a candidate if it's exactly 3-7-7 numerics.
  /// Defends against any earlier stage producing a malformed string.
  static String? _validate(String? candidate) {
    if (candidate == null) return null;
    final clean = candidate.trim();
    if (RegExp(r'^\d{3}-\d{7}-\d{7}$').hasMatch(clean)) return clean;
    return null;
  }

  // ─── Public API ───────────────────────────────────────────────────────

  /// Extract Amazon Order ID from an image. Returns the formatted ID
  /// (e.g. "407-1234567-1234567") or null if no valid candidate found.
  static Future<String?> extractOrderId(String imagePath) async {
    final scan = await scanAll(imagePath);
    return scan.orderId;
  }

  /// Combined scan: returns the Order ID AND the full recognized text in one
  /// pass. The caller can use [fullText] to detect courier-name keywords
  /// (DELHIVERY / BLUE DART / etc.) and feed [CarrierPatterns.findAwbInText]
  /// as a fallback when no barcode is decoded.
  static Future<OcrScanResult> scanAll(String imagePath) async {
    final inputImage = InputImage.fromFilePath(imagePath);
    final recognized = await _recognizer.processImage(inputImage);
    return OcrScanResult(
      orderId: _findOrderId(recognized),
      fullText: recognized.text,
    );
  }

  static String? _findOrderId(RecognizedText recognized) {
    // Per-block extraction — labels often have order ID isolated in its own block
    for (final block in recognized.blocks) {
      final r = _extractFrom(block.text);
      if (r != null) return r;
    }
    // Full-text fallback — handles cases where the order ID spans block boundaries
    final full = _extractFrom(recognized.text);
    if (full != null) return full;
    // Keyword-context — anchor on "Order ID", "Order #" etc., then search the
    // text that follows. Useful when the ID is far from natural word boundaries.
    final keywordMatches = _keyword.allMatches(recognized.text);
    for (final km in keywordMatches) {
      final after = km.group(1) ?? '';
      final r = _extractFrom(after);
      if (r != null) return r;
    }
    return null;
  }

  static void dispose() => _recognizer.close();
}

class OcrScanResult {
  final String? orderId;
  final String fullText;
  const OcrScanResult({required this.orderId, required this.fullText});
}
