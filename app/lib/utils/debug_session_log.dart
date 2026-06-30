import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// Debug-mode NDJSON logger for session f04664.
/// POSTs to the Cursor debug ingest server (works with `adb reverse tcp:7555 tcp:7555`).
class DebugSessionLog {
  DebugSessionLog._();

  static const _endpoint =
      'http://127.0.0.1:7555/ingest/27f1af60-e4d6-4a4b-918a-8581d9a2b8c8';
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
    final line = jsonEncode(payload);
    debugPrint('[DBG-f04664] $line');
    // #region agent log
    http
        .post(
          Uri.parse(_endpoint),
          headers: {
            'Content-Type': 'application/json',
            'X-Debug-Session-Id': _sessionId,
          },
          body: line,
        )
        .catchError((_) => http.Response('', 500));
    // #endregion
  }
}
