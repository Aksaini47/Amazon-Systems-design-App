/// Lightweight near-match check for RT Order IDs against known PK Order IDs.
///
/// Return-shipment labels are often faded/misprinted (usually 2-3 digits).
/// PK saves are reliable (rarely wrong) — used here as ground truth. Order
/// IDs are always the same fixed-length 3-7-7 digit shape once regex-valid,
/// and print/OCR misreads are digit *substitutions*, not insertions or
/// deletions — so a plain Hamming distance (position-by-position digit
/// comparison) is both correct for this failure mode and far cheaper than
/// Levenshtein edit-distance DP.
library;

/// Every real Amazon order ID starts with one of these. Kept here rather
/// than in any one screen because both the save popup and the OCR fallback
/// gate on it — OCR in particular used to return any 3-7-7-shaped run it
/// found, so a tracking or reference number on the same label could land in
/// the Order ID field.
const validOrderIdPrefixes = {
  '171', '402', '403', '404', '405', '406', '407', '408', '409',
};

/// True when [orderId] is exactly 3-7-7 digits AND carries a real Amazon
/// prefix. Shape alone is not enough — that was the old bug.
bool isPlausibleOrderId(String orderId) {
  final t = orderId.trim();
  if (!RegExp(r'^\d{3}-\d{7}-\d{7}$').hasMatch(t)) return false;
  return validOrderIdPrefixes.contains(t.substring(0, 3));
}

// ─── Dual-channel cross-check ───────────────────────────────────────────
//
// 2026-09: a barcode-only read on a 4x6 thermal label decoded successfully
// only ~2/7 times — narrow module width at print, thermal fade, or just
// distance/angle. Every fallback attempted before this (OCR digit-fixups,
// prefix gating, a bigger scan window) improved the SHAPE of a wrong read,
// never its correctness: a misdecoded barcode still passes Code128's own
// checksum and this file's own prefix check, because those only prove the
// value LOOKS like a real order id, not that it IS the one on the label.
// One PK video saved against the wrong order id was enough to break the
// PK<->RT match on the PC side and cost a real, unfiled claim.
//
// There is no checksum digit inside an Amazon order id to verify a single
// read against, and no offline ground truth to check it against either —
// this is the FIRST capture of this order id, nothing to compare it to yet.
// The only lever left is redundancy: read the same physical barcode two
// independent ways (barcode decode, OCR of the printed digits) and only
// trust a value neither channel already agrees on. Their failure modes
// barely overlap — decode failure is bar-width/print-quality, OCR failure
// is font/glare/blur — so an identical WRONG value from both is far less
// likely than either channel alone being wrong.

/// Two-channel read of the same order id. [ocr] is null when OCR could not
/// extract a candidate from the frame at all (not the same as disagreeing).
class OrderIdCrossCheck {
  final String barcode;
  final String? ocr;
  const OrderIdCrossCheck({required this.barcode, this.ocr});

  /// Both channels read the SAME value — the only case safe to trust
  /// without a deliberate, unhurried look from Sir.
  bool get confirmed => ocr != null && ocr == barcode;

  /// OCR ran and returned something, but a DIFFERENT order id — the
  /// dangerous case: two live, plausible-looking candidates. Never guess
  /// between them; whoever is packing has to look at the actual label.
  bool get conflicting => ocr != null && ocr != barcode;

  /// OCR found nothing to compare against (blur, glare, angle) — the
  /// barcode value is the only signal there is. Treat as unconfirmed, not
  /// as failed: still worth showing, just not worth auto-saving on.
  bool get singleSource => ocr == null;
}

/// A candidate PK Order ID close to the one just entered/scanned in RT mode.
class OrderIdMatch {
  final String candidate; // full hyphenated PK order id
  final int distance;
  const OrderIdMatch(this.candidate, this.distance);
}

String? _bareDigits(String orderId) {
  final digits = orderId.replaceAll('-', '');
  return digits.length == 17 ? digits : null;
}

/// Number of digit positions that differ. Both strings must be the same
/// length (callers only compare same-length 17-digit Order IDs).
int hammingDistance(String a, String b) {
  var distance = 0;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) distance++;
  }
  return distance;
}

/// Closest PK Order ID within the "misprint band" (1-3 differing digits).
///
/// Returns null when [rtOrderId] exactly matches a known PK id (nothing to
/// flag), or when nothing is within the band (the normal/majority case —
/// most RT orders simply aren't in the PK set, or are genuinely different
/// orders, and must never be interrupted).
OrderIdMatch? findNearMatch(String rtOrderId, Set<String> pkOrderIds) {
  final rtDigits = _bareDigits(rtOrderId);
  if (rtDigits == null) return null;

  OrderIdMatch? best;
  for (final pk in pkOrderIds) {
    final pkDigits = _bareDigits(pk);
    if (pkDigits == null || pkDigits == rtDigits) continue;
    final distance = hammingDistance(rtDigits, pkDigits);
    if (distance >= 1 && distance <= 3 && (best == null || distance < best.distance)) {
      best = OrderIdMatch(pk, distance);
    }
  }
  return best;
}
