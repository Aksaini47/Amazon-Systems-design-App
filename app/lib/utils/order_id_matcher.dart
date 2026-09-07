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
