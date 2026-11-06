import 'package:flutter/services.dart';

/// Keystroke formatter for the Order ID field. Two shapes, picked by the first
/// character, so they can never clash:
///
///  * Amazon `407-1234567-1234567` - digits only, hyphens inserted after the
///    3rd and 10th digit, capped at 17 digits.
///  * Website `RF-261104-0004` (RF + YYMMDD + 4-digit serial; Sir, 2026-11-04)
///    - starts with R or F (case-insensitive, upper-cased), hyphens inserted
///    after `RF` and after the 6th digit, capped at 6 + 4 digits.
///
/// Programmatic `.text =` assignment (scan/OCR autofill) bypasses formatters -
/// they only see user keystrokes, so already-correct scanned values pass
/// through untouched.
class OrderIdInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    final upper = newValue.text.trim().toUpperCase();
    if (upper.startsWith('R') || upper.startsWith('F')) {
      return _website(oldValue, newValue, upper);
    }
    return _amazon(newValue);
  }

  static TextEditingValue _website(TextEditingValue oldValue, TextEditingValue newValue, String upper) {
    final digits = upper.replaceAll(RegExp(r'[^0-9]'), '');
    final capped = digits.length > 10 ? digits.substring(0, 10) : digits;
    String text;
    if (capped.isEmpty) {
      // "RF-" stays while typing; one more backspace (down to "RF") clears it,
      // otherwise the auto-inserted prefix could never be deleted.
      final deleting = newValue.text.length < oldValue.text.length;
      text = (upper.length < 3 && deleting) ? '' : 'RF-';
    } else if (capped.length <= 6) {
      text = 'RF-$capped';
    } else {
      text = 'RF-${capped.substring(0, 6)}-${capped.substring(6)}';
    }
    return TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
  }

  static TextEditingValue _amazon(TextEditingValue newValue) {
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
        .replaceAll(RegExp(r'[^0-9]'), '')
        .length;
    var cursor = 0, seen = 0;
    while (cursor < formatted.length && seen < digitsBeforeCursor) {
      if (formatted[cursor] != '-') seen++;
      cursor++;
    }
    return TextEditingValue(text: formatted, selection: TextSelection.collapsed(offset: cursor));
  }
}

/// Keystroke formatter for the AWB / tracking field: CAPITALS, letters and
/// digits only (spaces, hyphens and anything else dropped), 30 characters at
/// most. Courier AWBs never contain other characters, and typed letters are
/// safe here - unlike OCR, the person typing reads the label themselves.
class AwbInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    final clean = newValue.text.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9]'), '');
    final text = clean.length > 30 ? clean.substring(0, 30) : clean;
    if (text == newValue.text) return newValue;
    return TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
  }
}
