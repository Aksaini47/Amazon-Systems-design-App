import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import 'package:video_compress/video_compress.dart';
import 'package:retry/retry.dart';

/// Central API client for the RepairFully backend.
/// All network calls go through this class.
class ApiService {
  static const _baseUrlKey = 'backend_url';
  static const _defaultUrl = 'http://192.168.1.100:3001';

  // ─── Video Compression ───────────────────────────────────────────────────

  /// Compresses video to 720p, optionally using H.265 if available.
  /// Note: video_compress doesn't expose codec selection — this uses H.264 (AVC)
  /// which is the standard on Android. For H.265/HEVC, a platform channel or
  /// FFmpegKit integration would be needed. Spec target is H.265 per mahika_capture_specs.
  static Future<File> _compressVideo(File file) async {
    // Try H.265 via video_compress (device may not support it)
    MediaInfo? mediaInfo;
    try {
      mediaInfo = await VideoCompress.compressVideo(
        file.path,
        quality: VideoQuality.MediumQuality, // 720p
        deleteOrigin: false,
        includeAudio: false,
      );
    } catch (e) {
      debugPrint('Video compression failed: $e');
    }

    if (mediaInfo != null && mediaInfo.file != null) {
      debugPrint('Video compressed: ${mediaInfo.file!.path} (original: ${file.path})');
      return mediaInfo.file!;
    }

    // Fallback: return original if compression fails
    debugPrint('Compression fallback - returning original file');
    return file;
  }

  // ─── URL Management ──────────────────────────────────────────────────────

  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getString(_baseUrlKey) ?? _defaultUrl)
        .trimRight()
        .replaceAll(RegExp(r'/$'), '');
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, url.trim());
  }

  // ─── Orders ──────────────────────────────────────────────────────────────

  /// Upsert an order on the backend. Idempotent (UPSERT on order_id).
  /// Required before any video/image upload — the backend rejects uploads if
  /// the order is not present in the orders table.
  static Future<void> upsertOrder({
    required String orderId,
    String? productTitle,
    String? awbNumber,
    String? carrier,
  }) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/orders');
    final res = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'order_id': orderId,
            if (productTitle != null) 'product_title': productTitle,
            if (awbNumber != null) 'awb_number': awbNumber,
            if (carrier != null) 'carrier': carrier,
          }),
        )
        .timeout(const Duration(seconds: 15));
    // Accept any 2xx (Express may return 201 Created on upsert insert vs
    // 200 OK on update — the original `!= 200` check rejected valid 201s
    // and re-queued orders that had actually persisted server-side.)
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('upsertOrder failed ${res.statusCode}: ${res.body}');
    }
  }

  /// Look up an order by AWB barcode number. Returns null if not found.
  static Future<Order?> getOrderByAwb(String awb) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/orders/by-awb/${Uri.encodeComponent(awb)}');
    final res = await http.get(uri).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) return Order.fromJson(jsonDecode(res.body));
    if (res.statusCode == 404) return null;
    throw Exception('Server error ${res.statusCode}');
  }

  // ─── Videos ──────────────────────────────────────────────────────────────

  /// Fetch paginated list of all recorded videos, newest first.
  static Future<List<Video>> getVideos({int limit = 100, int offset = 0}) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/videos?limit=$limit&offset=$offset');
    final res = await http.get(uri).timeout(const Duration(seconds: 10));
    if (res.statusCode != 200) throw Exception('Server error ${res.statusCode}');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final list = data['videos'] as List<dynamic>? ?? [];
    return list.map((v) => Video.fromJson(v as Map<String, dynamic>)).toList();
  }

  /// Upload a video file (FBM order or FBA shipment box).
  static Future<Map<String, dynamic>> uploadVideo({
    String? orderId,
    String? fbaShipmentId,
    int? fbaBoxNumber,
    required String type,
    required File videoFile,
    double? durationSeconds,
    String? recordedAt,
  }) async {
    assert(orderId != null || fbaShipmentId != null, 'Provide orderId or fbaShipmentId');
    
    // 1. Compress before upload
    final File compressedFile = await _compressVideo(videoFile);
    
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/videos/upload');

    // 2. Upload with retry logic
    return retry(
      () async {
        final request = http.MultipartRequest('POST', uri);
        if (orderId != null) request.fields['order_id'] = orderId;
        if (fbaShipmentId != null) request.fields['fba_shipment_id'] = fbaShipmentId;
        if (fbaBoxNumber != null) request.fields['fba_box_number'] = fbaBoxNumber.toString();
        request.fields['type'] = type;
        if (durationSeconds != null) request.fields['duration_seconds'] = durationSeconds.toString();
        if (recordedAt != null) request.fields['recorded_at'] = recordedAt;
        
        request.files.add(await http.MultipartFile.fromPath('video', compressedFile.path));

        final response = await request.send().timeout(const Duration(minutes: 5));
        final body = await response.stream.bytesToString();
        
        if (response.statusCode == 200) {
          // Cleanup compressed temp file if it's different from original
          if (compressedFile.path != videoFile.path) {
            try { await compressedFile.delete(); } catch (_) {}
          }
          return jsonDecode(body);
        }
        
        throw Exception('Upload failed ${response.statusCode}: $body');
      },
      retryIf: (e) => e is SocketException || e is http.ClientException,
      maxAttempts: 3,
    );
  }

  // ─── FBA Shipments ───────────────────────────────────────────────────────

  /// Fetch all FBA inbound shipments.
  static Future<List<FbaShipment>> getFbaShipments() async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/fba-shipments?limit=100');
    final res = await http.get(uri).timeout(const Duration(seconds: 10));
    if (res.statusCode != 200) throw Exception('Failed to fetch FBA shipments ${res.statusCode}');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final list = data['shipments'] as List<dynamic>? ?? [];
    return list.map((s) => FbaShipment.fromJson(s as Map<String, dynamic>)).toList();
  }

  // ─── Images ──────────────────────────────────────────────────────────────

  /// Upload a photo linked to an order.
  static Future<Map<String, dynamic>> uploadImage({
    required String orderId,
    required File imageFile,
  }) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base/api/images/upload');

    return retry(
      () async {
        final request = http.MultipartRequest('POST', uri);
        request.fields['order_id'] = orderId;
        request.fields['captured_at'] = DateTime.now().toIso8601String();
        request.files.add(await http.MultipartFile.fromPath('image', imageFile.path));

        final response = await request.send().timeout(const Duration(minutes: 2));
        final body = await response.stream.bytesToString();
        if (response.statusCode == 200) return jsonDecode(body);
        throw Exception('Image upload failed ${response.statusCode}: $body');
      },
      retryIf: (e) => e is SocketException || e is http.ClientException,
      maxAttempts: 3,
    );
  }

  // ─── Health ──────────────────────────────────────────────────────────────

  /// Health check — returns true if backend is reachable.
  static Future<bool> ping() async {
    try {
      final base = await getBaseUrl();
      final res = await http.get(Uri.parse('$base/api/health'))
          .timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Fetch backend config — storage path, port, available IPs.
  /// Returns null if backend offline or doesn't expose /api/config.
  static Future<Map<String, dynamic>?> getConfig() async {
    try {
      final base = await getBaseUrl();
      final res = await http.get(Uri.parse('$base/api/config'))
          .timeout(const Duration(seconds: 5));
      if (res.statusCode != 200) return null;
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }
}

