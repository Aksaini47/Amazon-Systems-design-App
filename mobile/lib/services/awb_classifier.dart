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
///   - [classify] — single value → best-match carrier (or null)
///   - [detectCarrierFromText] — scan OCR full text for carrier-name keywords
///   - [pickAwbFromBarcodes] — given list of barcode values + (optional) detected
///                            carrier hint, return the best AWB candidate
library;

import 'package:flutter/foundation.dart';

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

  const AwbClassification({
    required this.value,
    required this.carrier,
    required this.confidence,
  });
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
    if (orderIdRegex.hasMatch(v)) return null;  // it's an Order ID, not AWB
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

  /// Pick the best AWB candidate from a list of barcode raw values.
  ///   [barcodeValues] — every raw barcode value detected in the frame
  ///   [hint] — optional carrier detected from label-text OCR; boosts that
  ///            carrier's confidence so its pattern wins ties
  ///
  /// Returns the value + matched carrier + confidence, or null if no
  /// non-Order-ID barcode passes any pattern.
  static AwbClassification? pickAwbFromBarcodes(
    List<String> barcodeValues, {
    CarrierPattern? hint,
  }) {
    AwbClassification? best;
    double bestScore = -1;
    for (final v in barcodeValues) {
      final clean = v.trim();
      if (clean.isEmpty) continue;
      if (orderIdRegex.hasMatch(clean)) continue;  // skip Order ID barcodes
      // Score every carrier that matches this value
      for (final c in all) {
        if (!c.matchesValue(clean)) continue;
        // Confidence = carrier's intrinsic specificity, boosted by hint match
        double conf = c.specificity;
        if (hint != null && hint.name == c.name) conf += 0.3;
        if (conf > bestScore) {
          best = AwbClassification(value: clean, carrier: c, confidence: conf.clamp(0.0, 1.0));
          bestScore = conf;
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
  /// or null.
  static AwbClassification? findAwbInText(String ocrText, {CarrierPattern? hint}) {
    final upper = ocrText.toUpperCase();
    AwbClassification? best;
    double bestScore = -1;
    // Try each carrier's regex against every token in the text
    final tokens = upper.split(RegExp(r'[\s,.;:|\\/()\[\]{}"‘’]+'));
    for (final tok in tokens) {
      final clean = tok.trim();
      if (clean.length < 8 || clean.length > 22) continue;
      if (orderIdRegex.hasMatch(clean)) continue;
      for (final c in all) {
        if (!c.matchesValue(clean)) continue;
        double conf = c.specificity * 0.85;  // OCR text is less reliable than barcode
        if (hint != null && hint.name == c.name) conf += 0.2;
        if (conf > bestScore) {
          best = AwbClassification(value: clean, carrier: c, confidence: conf.clamp(0.0, 1.0));
          bestScore = conf;
        }
      }
    }
    return best;
  }
}
