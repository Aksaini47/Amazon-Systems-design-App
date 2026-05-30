import 'package:flutter/services.dart';

class VolumeButtonService {
  static final VolumeButtonService _instance = VolumeButtonService._internal();
  static const MethodChannel _channel = MethodChannel('volume_channel');

  factory VolumeButtonService() {
    return _instance;
  }

  VolumeButtonService._internal() {
    _channel.setMethodCallHandler(_handleMethodCall);
  }

  final Map<String, Function(int)> _listeners = {};

  void registerListener(String key, Function(int) listener) {
    _listeners[key] = listener;
  }

  void unregisterListener(String key) {
    _listeners.remove(key);
  }

  Future<void> _handleMethodCall(MethodCall call) async {
    if (call.method == 'volume_button_pressed') {
      int event = call.arguments as int;
      for (var listener in _listeners.values) {
        listener(event);
      }
    }
  }
}
