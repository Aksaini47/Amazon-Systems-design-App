import 'dart:convert';

import 'package:flutter/foundation.dart';

/// Debug-mode NDJSON logger — console only (no network).
class DebugSessionLog {
  DebugSessionLog._();

  static const _sessionId = 'f04664';

  static void log({
    required String location,
    required String message,
    required String hypothesisId,
    Map<String, dynamic>? data,
    String runId = 'pre-fix',
  }) {
    final payload = <String, dynamic>{
      'sessionId': _sessionId,
      'runId': runId,
      'hypothesisId': hypothesisId,
      'location': location,
      'message': message,
      'data': data ?? const <String, dynamic>{},
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    };
    debugPrint('[DBG-$_sessionId] ${jsonEncode(payload)}');
  }
}
