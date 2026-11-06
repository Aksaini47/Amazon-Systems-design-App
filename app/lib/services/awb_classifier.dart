/// Carrier-aware AWB classifier.
///
/// Maps a value (barcode raw text or OCR'd string) to a likely carrier by
/// validating against per-carrier regex patterns. Combined with carrier-name
/// keyword detection in OCR text (most labels print "DELHIVERY", "BLUE DART",
/// etc. above the barcode), this gives high-accuracy AWB extraction without
/// relying on raw barcode order or guessing.
///
/// Patterns sourced from:
///   1. User's real return-data analysis (Evidence_12 + Evidence_14 CSVs, Dec 2025)
///   2. Web research on each carrier's published format
///
/// Empirical from user data (most prevalent):
///   ATSPL / ATS  → 12-digit numeric (87% of forward leg, 100% of reverse leg)
///   Delhivery    → 14-digit numeric (often starts 13/14)
///   Blue Dart    → 11-digit numeric (forward), 12-digit (reverse)
///   Ecom Express → 9-10-digit numeric
///   India Post   → UPU S10 format: 2-letter prefix + 9 digits + "IN" (13 chars)
///
/// Use:
///   - `classify` — single value → best-match carrier (or null)
///   - `detectCarrierFromText` — scan OCR full text for carrier-name keywords
///   - `pickAwbFromBarcodes` — given list of barcode values + (optional) detected
///                            carrier hint, return the best AWB candidate
library;

import 'package:flutter/foundation.dart';

import '../models/capture_session.dart';
import '../utils/order_id_matcher.dart';

// ─── Save rule ──────────────────────────────────────────────────────────────

/// Minimum digits of an RT (return) AWB (Sir, 2026-10-16; the maximum was
/// dropped on 2026-10-26).
const returnAwbMinDigits = 12;

/// Couriers whose AWBs carry letters and are accepted for an RT save in their
/// EXACT format (Sir, 2026-11-06). Some are shorter than 12 (DTDC is 9).
const returnLetteredCouriers = ['India Post', 'DTDC', 'Shadowfax', 'Ekart', 'Xpressbees'];

/// An RT (return) AWB is SAVED only if it is either
///   * digits only and AT LEAST 12 long (no maximum), or
///   * the exact format of one of [returnLetteredCouriers].
///
/// A faded return label once made the app save an AWB two characters short,
/// and the office's PK/RT merge and SAFE-T claim script could not repair it.
/// The carrier patterns below could never have caught that: Trackon
/// (`[A-Z0-9]{9,14}`) and "Unknown carrier" (`\d{9,16}`) accept almost any
/// 9-16 character value, so a truncated AWB still looked valid. The 12-digit
/// floor is what stops a short numeric read; a lettered AWB has to match its
/// courier's exact shape instead (Trackon's loose pattern is NOT accepted).
/// PK keeps the open rule — its AWBs come in many carrier formats.
bool isValidReturnAwb(String awb) {
  final t = awb.trim();
  return _returnAwb.hasMatch(t) || returnLetteredCourierFor(t) != null;
}

final _returnAwb = RegExp(r'^\d{12,}$'); // keep in step with [returnAwbMinDigits]

/// Name of the lettered courier ([returnLetteredCouriers]) whose exact format
/// [awb] has, or null. Only values that contain a letter qualify — an
/// all-digit value is judged by the 12-digit rule alone.
String? returnLetteredCourierFor(String awb) {
  final t = awb.trim();
  if (!t.contains(RegExp(r'[A-Z]'))) return null;
  for (final c in CarrierPatterns.all) {
    if (returnLetteredCouriers.contains(c.name) && c.matchesValue(t)) return c.name;
  }
  return null;
}

/// The usual return AWB shape: exactly 12 digits. When a label offers both a
/// 12-digit and a longer valid code, the scan prefers this one (see the
/// `prefer` parameter of [CarrierPatterns.pickAwbFromBarcodes]).
bool isStandardReturnAwb(String awb) => _standardReturnAwb.hasMatch(awb.trim());

final _standardReturnAwb = RegExp(r'^\d{12}$');

/// Whether [awb] is acceptable for SAVING an order of [mode]. The tracking ID
/// may be left BLANK in both modes (Sir, 2026-10-28) - but once anything is
/// typed, the RT rule applies ([isValidReturnAwb]: 12+ digits, or an exact
/// lettered-courier format). PK takes any AWB, or none.
///
/// Blank is a manual-save choice only: auto-save still waits for a read AWB
/// (see the popup's `_autoSaveBlocker`), so a scan that has not found the AWB
/// yet does not save an order without one.
bool awbAllowsSave(CaptureMode mode, String awb) =>
    mode != CaptureMode.rt || awb.trim().isEmpty || isValidReturnAwb(awb);

class CarrierPattern {
  /// Display name shown to the user.
  final String name;

  /// Aliases that appear on shipping labels above the barcode. Matched
  /// case-insensitively against the OCR'd label text.
  final List<String> nameKeywords;

  /// Pattern the AWB value must match.
  final RegExp awbRegex;

  /// Minimum confidence (0-1) — used when multiple carriers match the same
  /// value (e.g., long numerics matching both Delhivery and Xpressbees).
  /// Higher = stronger preference.
  final double specificity;

  const CarrierPattern({
    required this.name,
    required this.nameKeywords,
    required this.awbRegex,
    this.specificity = 0.5,
  });

  bool matchesValue(String value) => awbRegex.hasMatch(value.trim());
}

class AwbClassification {
  final String value;
  final CarrierPattern carrier;
  final double confidence; // 0-1 — higher when carrier name also detected on label

  /// How many characters [CarrierPatterns.repairOcrToken] had to swap to make
  /// an OCR read fit its courier's format (0 = read as-is, or from a barcode).
  final int ocrFixes;

  const AwbClassification({
    required this.value,
    required this.carrier,
    required this.confidence,
    this.ocrFixes = 0,
  });
}

/// One OCR token after look-alike repair — see [CarrierPatterns.repairOcrToken].
class OcrAwbRepair {
  final String value;
  final int fixes;
  const OcrAwbRepair(this.value, this.fixes);
}

class CarrierPatterns {
  // ── Amazon Order ID — used as the EXCLUSION signal. Any value matching
  //    this pattern is NEVER an AWB; it's the order ID barcode itself.
  static final orderIdRegex = RegExp(r'^\d{3}-\d{7}-\d{7}$');

  /// Authoritative list of supported Indian carriers + a generic fallback.
  /// Ordered most-specific-first so the classifier prefers strict matches.
  static final List<CarrierPattern> all = [
    // ── India Post — UPU S10: 2 uppercase letters + 9 digits + "IN"
    //    (this is the international postal standard, very strict)
    CarrierPattern(
      name: 'India Post',
      nameKeywords: ['INDIA POST', 'INDIAPOST', 'SPEEDPOST', 'SPEED POST', 'IPSIN'],
      awbRegex: RegExp(r'^[A-Z]{2}\d{9}IN$'),
      specificity: 1.0,
    ),

    // ── Ekart (Flipkart Logistics) — 4 uppercase letters + 10 digits
    CarrierPattern(
      name: 'Ekart',
      nameKeywords: ['EKART', 'FLIPKART LOGISTICS', 'FMPP', 'FMPC'],
      awbRegex: RegExp(r'^[A-Z]{4}\d{10}$'),
      specificity: 0.95,
    ),

    // ── Shadowfax — "SF" prefix + alphanumeric (Flipkart / Meesho / Myntra)
    CarrierPattern(
      name: 'Shadowfax',
      nameKeywords: ['SHADOWFAX', 'SHADOW FAX'],
      awbRegex: RegExp(r'^SF[A-Z0-9]{6,18}$'),
      specificity: 0.9,
    ),

    // ── DTDC — 1 uppercase letter + 8 digits (mainland) — 9 chars total
    CarrierPattern(
      name: 'DTDC',
      nameKeywords: ['DTDC'],
      awbRegex: RegExp(r'^[A-Z]\d{8}$'),
      specificity: 0.9,
    ),

    // ── Xpressbees alphanumeric variant — 2 letters + 12 digits = 14 chars
    CarrierPattern(
      name: 'Xpressbees',
      nameKeywords: ['XPRESSBEES', 'XPRESS BEES', 'BUSYBEES'],
      awbRegex: RegExp(r'^[A-Z]{2}\d{12}$'),
      specificity: 0.85,
    ),

    // ── Delhivery — 12 to 15 digits, typically 13-14
    //    Stricter than ATS by length to break ties at 12 digits
    CarrierPattern(
      name: 'Delhivery',
      nameKeywords: ['DELHIVERY'],
      awbRegex: RegExp(r'^\d{13,15}$'),
      specificity: 0.75,
    ),

    // ── Blue Dart — 11-digit numeric forward, 12-digit reverse
    CarrierPattern(
      name: 'Blue Dart',
      nameKeywords: ['BLUE DART', 'BLUEDART', 'BLUE-DART', 'DHL'],
      awbRegex: RegExp(r'^\d{11}$'),
      specificity: 0.7,
    ),

    // ── Trackon — typically alphanumeric mixed
    CarrierPattern(
      name: 'Trackon',
      nameKeywords: ['TRACKON'],
      awbRegex: RegExp(r'^[A-Z0-9]{9,14}$'),
      specificity: 0.6,
    ),

    // ── FedEx India — 12, 15, or 20-22 digit numeric
    CarrierPattern(
      name: 'FedEx',
      nameKeywords: ['FEDEX', 'FED EX'],
      awbRegex: RegExp(r'^(\d{12}|\d{15}|\d{20,22})$'),
      specificity: 0.65,
    ),

    // ── ATS / ATSPL (Anjani Transport) — Amazon's most common partner
    //    in user's data. 10, 12, or 14 digit numeric.
    CarrierPattern(
      name: 'ATS',
      nameKeywords: ['ATS', 'ATSPL', 'ANJANI'],
      awbRegex: RegExp(r'^\d{10}$|^\d{12}$|^\d{14}$'),
      specificity: 0.6,
    ),

    // ── Ecom Express — 9-14 digit numeric, often shorter
    CarrierPattern(
      name: 'Ecom Express',
      nameKeywords: ['ECOM EXPRESS', 'ECOMEXPRESS', 'ECEXPRESS', 'ECXIN'],
      awbRegex: RegExp(r'^\d{9,14}$'),
      specificity: 0.55,
    ),

    // ── Generic numeric AWB fallback — accepts any 9-16 digit number that
    //    isn't an Order ID. Lowest specificity; only chosen if nothing else
    //    matches. Catches unknown carriers + carrier variants we missed.
    CarrierPattern(
      name: 'Unknown carrier',
      nameKeywords: [],
      awbRegex: RegExp(r'^\d{9,16}$'),
      specificity: 0.2,
    ),
  ];

  /// Scan free-form OCR text for a carrier-name keyword. Returns the matched
  /// carrier or null. Case-insensitive, ignores extra whitespace.
  static CarrierPattern? detectCarrierFromText(String? ocrText) {
    if (ocrText == null || ocrText.trim().isEmpty) return null;
    final upper = ocrText.toUpperCase();
    for (final c in all) {
      for (final kw in c.nameKeywords) {
        if (upper.contains(kw)) {
          debugPrint('CarrierPatterns: detected "${c.name}" via keyword "$kw"');
          return c;
        }
      }
    }
    return null;
  }

  /// Single-value classification — tries every carrier pattern, returns the
  /// most-specific match. Returns null if nothing matches OR if the value
  /// is itself an Amazon Order ID (which should never be classified as AWB).
  static CarrierPattern? classify(String value) {
    final v = value.trim();
    if (v.isEmpty) return null;
    if (isOrderIdShape(v)) return null;  // it's an Order ID, not AWB
    CarrierPattern? best;
    double bestSpec = -1;
    for (final c in all) {
      if (c.matchesValue(v) && c.specificity > bestSpec) {
        best = c;
        bestSpec = c.specificity;
      }
    }
    return best;
  }

  /// Rank bonus for a `prefer`red candidate — larger than any confidence gap.
  static const _preferBonus = 2.0;

  /// Pick the best AWB candidate from a list of barcode raw values.
  ///   [barcodeValues] — every raw barcode value detected in the frame
  ///   [hint] — optional carrier detected from label-text OCR; boosts that
  ///            carrier's confidence so its pattern wins ties
  ///   [accept] — values it rejects are never picked (RT passes
  ///            [isValidReturnAwb], so a truncated read cannot become the AWB)
  ///   [prefer] — candidates it approves outrank every other accepted one
  ///            (RT passes [isStandardReturnAwb]: a 12-digit code beats a
  ///            longer one even when the longer one scores higher)
  ///
  /// Returns the value + matched carrier + confidence, or null if no
  /// non-Order-ID barcode passes any pattern.
  static AwbClassification? pickAwbFromBarcodes(
    List<String> barcodeValues, {
    CarrierPattern? hint,
    bool Function(String value)? accept,
    bool Function(String value)? prefer,
  }) {
    AwbClassification? best;
    double bestScore = -1;
    for (final v in barcodeValues) {
      final clean = v.trim();
      if (clean.isEmpty) continue;
      if (isOrderIdShape(clean)) continue;  // skip Order ID barcodes (Amazon or website)
      if (accept != null && !accept(clean)) continue;
      final bonus = (prefer != null && prefer(clean)) ? _preferBonus : 0.0;
      // Score every carrier that matches this value
      for (final c in all) {
        if (!c.matchesValue(clean)) continue;
        // Confidence = carrier's intrinsic specificity, boosted by hint match
        double conf = c.specificity;
        if (hint != null && hint.name == c.name) conf += 0.3;
        if (conf + bonus > bestScore) {
          best = AwbClassification(value: clean, carrier: c, confidence: conf.clamp(0.0, 1.0));
          bestScore = conf + bonus;
        }
      }
    }
    if (best != null) {
      debugPrint('CarrierPatterns.pickAwbFromBarcodes: ${best.carrier.name} (conf=${best.confidence.toStringAsFixed(2)}) → ${best.value}');
    }
    return best;
  }

  /// Fallback path: scan free-form OCR text for any AWB-shaped substring
  /// (when no barcode was successfully decoded). Returns the best match
  /// or null. [accept] filters candidates as in [pickAwbFromBarcodes].
  ///
  /// A token that fits no format as read gets one more chance through
  /// [repairOcrToken] (O/0, I/1, S/5 ... swapped by position); the result
  /// carries [AwbClassification.ocrFixes] and ranks below an as-read match.
  static AwbClassification? findAwbInText(
    String ocrText, {
    CarrierPattern? hint,
    bool Function(String value)? accept,
    bool Function(String value)? prefer,
  }) {
    final upper = ocrText.toUpperCase();
    AwbClassification? best;
    double bestScore = -1;
    // Try each carrier's regex against every token in the text
    final tokens = upper.split(RegExp(r'[\s,.;:|\\/()\[\]{}"‘’]+'));
    for (final tok in tokens) {
      final raw = tok.trim();
      if (raw.length < 8 || raw.length > 22) continue;
      if (isOrderIdShape(raw)) continue;
      var clean = raw;
      var fixes = 0;
      final asRead = all.any((c) => c.matchesValue(raw)) && (accept == null || accept(raw));
      if (!asRead) {
        final repaired = repairOcrToken(raw, accept: accept);
        if (repaired == null || isOrderIdShape(repaired.value)) continue;
        clean = repaired.value;
        fixes = repaired.fixes;
      }
      final bonus = (prefer != null && prefer(clean)) ? _preferBonus : 0.0;
      for (final c in all) {
        if (!c.matchesValue(clean)) continue;
        // OCR text is less reliable than a barcode, and every repaired
        // character makes it less so.
        double conf = c.specificity * 0.85 - 0.1 * fixes;
        if (hint != null && hint.name == c.name) conf += 0.2;
        if (conf + bonus > bestScore) {
          best = AwbClassification(
            value: clean,
            carrier: c,
            confidence: conf.clamp(0.0, 1.0),
            ocrFixes: fixes,
          );
          bestScore = conf + bonus;
        }
      }
    }
    return best;
  }

  // ─── OCR look-alike repair ─────────────────────────────────────────────
  //
  // OCR confuses look-alike characters (0/O, 1/I, 5/S, 8/B ...). A courier's
  // AWB format fixes, for every POSITION, whether a letter or a digit belongs
  // there - India Post is 2 letters + 9 digits + "IN", DTDC 1 letter + 8
  // digits. So a misread character can be put back by position instead of by
  // guessing. A token is repaired only when exactly ONE result needs the
  // fewest swaps, and never with more than [_maxOcrFixes] swaps.

  static const _lookAsDigit = {
    'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1',
    'Z': '2', 'S': '5', 'G': '6', 'T': '7', 'B': '8',
  };
  static const _lookAsLetter = {
    '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '6': 'G', '7': 'T', '8': 'B',
  };
  static const _maxOcrFixes = 2;

  /// Position templates for a token of [length]: `L` letter, `D` digit,
  /// `A` letter or digit, anything else a literal character.
  static List<String> _templatesFor(int length) => [
        if (length == 13) 'LLDDDDDDDDDIN', // India Post (UPU S10)
        if (length == 9) 'LDDDDDDDD', // DTDC
        if (length == 14) 'LLLLDDDDDDDDDD', // Ekart
        if (length == 14) 'LLDDDDDDDDDDDD', // Xpressbees
        if (length >= 8 && length <= 20) 'SF${'A' * (length - 2)}', // Shadowfax
        if (length >= 9) 'D' * length, // numeric couriers
      ];

  static OcrAwbRepair? _fit(String token, String template) {
    final out = StringBuffer();
    var fixes = 0;
    for (var i = 0; i < token.length; i++) {
      final ch = token[i];
      final t = template[i];
      final isDigit = ch.codeUnitAt(0) >= 0x30 && ch.codeUnitAt(0) <= 0x39;
      final isLetter = ch.codeUnitAt(0) >= 0x41 && ch.codeUnitAt(0) <= 0x5A;
      String? put;
      if (t == 'D') {
        put = isDigit ? ch : _lookAsDigit[ch];
      } else if (t == 'L') {
        put = isLetter ? ch : _lookAsLetter[ch];
      } else if (t == 'A') {
        put = (isDigit || isLetter) ? ch : null;
      } else {
        put = ch == t ? ch : (_lookAsLetter[ch] == t ? t : null);
      }
      if (put == null) return null;
      if (put != ch) fixes++;
      out.write(put);
    }
    return OcrAwbRepair(out.toString(), fixes);
  }

  /// Repairs an OCR [token] into a courier AWB by position (see above), or
  /// returns null when nothing fits, more than [_maxOcrFixes] swaps would be
  /// needed, or two DIFFERENT values tie for the fewest swaps. [accept]
  /// filters results as in [pickAwbFromBarcodes].
  static OcrAwbRepair? repairOcrToken(String token, {bool Function(String value)? accept}) {
    final t = token.trim().toUpperCase();
    OcrAwbRepair? best;
    var tie = false;
    for (final template in _templatesFor(t.length)) {
      final r = _fit(t, template);
      if (r == null || r.fixes > _maxOcrFixes) continue;
      if (!all.any((c) => c.matchesValue(r.value))) continue;
      if (accept != null && !accept(r.value)) continue;
      if (best == null || r.fixes < best.fixes) {
        best = r;
        tie = false;
      } else if (r.fixes == best.fixes && r.value != best.value) {
        tie = true;
      }
    }
    return tie ? null : best;
  }
}
