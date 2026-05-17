import 'dart:io';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';

class PermissionService {
  /// Request all required permissions for camera app
  static Future<Map<Permission, PermissionStatus>> requestCameraPermissions() async {
    final results = <Permission, PermissionStatus>{};

    // Camera permission (required for video/photo)
    results[Permission.camera] = await Permission.camera.request();

    // Microphone permission (for audio recording)
    results[Permission.microphone] = await Permission.microphone.request();

    // Request MANAGE_EXTERNAL_STORAGE for Android 11+ (critical for file access)
    final deviceInfo = DeviceInfoPlugin();
    final androidInfo = await deviceInfo.androidInfo;
    if (androidInfo.version.sdkInt >= 30) {
      // Android 11+ needs MANAGE_EXTERNAL_STORAGE
      results[Permission.manageExternalStorage] = await Permission.manageExternalStorage.request();
      debugPrint('MANAGE_EXTERNAL_STORAGE status: ${results[Permission.manageExternalStorage]}');
    } else {
      // Storage permission for Android 10 and below
      if (await Permission.storage.isGranted) {
        results[Permission.storage] = PermissionStatus.granted;
      } else {
        results[Permission.storage] = await Permission.storage.request();
      }
    }

    // Photos permission (for saving images on Android 13+)
    if (await Permission.photos.isGranted) {
      results[Permission.photos] = PermissionStatus.granted;
    } else {
      results[Permission.photos] = await Permission.photos.request();
    }

    // Videos permission (for saving videos on Android 13+)
    if (await Permission.videos.isGranted) {
      results[Permission.videos] = PermissionStatus.granted;
    } else {
      results[Permission.videos] = await Permission.videos.request();
    }

    return results;
  }

  /// Check if camera permission is granted
  static Future<bool> isCameraGranted() async {
    return await Permission.camera.isGranted;
  }

  /// Check if microphone permission is granted
  static Future<bool> isMicrophoneGranted() async {
    return await Permission.microphone.isGranted;
  }

  /// Check if storage/media permissions are granted
  static Future<bool> isStorageGranted() async {
    // Android 11+ needs MANAGE_EXTERNAL_STORAGE
    final deviceInfo = DeviceInfoPlugin();
    final androidInfo = await deviceInfo.androidInfo;
    if (androidInfo.version.sdkInt >= 30) {
      return await Permission.manageExternalStorage.isGranted;
    }
    // Android 13+ uses photos/videos, older uses storage
    if (await Permission.photos.isGranted || await Permission.videos.isGranted) {
      return true;
    }
    return await Permission.storage.isGranted;
  }

  /// Request storage permission only
  static Future<bool> requestStoragePermission() async {
    final deviceInfo = DeviceInfoPlugin();
    final androidInfo = await deviceInfo.androidInfo;

    // Android 11+ needs MANAGE_EXTERNAL_STORAGE
    if (androidInfo.version.sdkInt >= 30) {
      final status = await Permission.manageExternalStorage.request();
      debugPrint('requestStoragePermission: MANAGE_EXTERNAL_STORAGE = $status');
      return status.isGranted;
    }

    // Try photos/videos first (Android 13+)
    var status = await Permission.photos.request();
    if (status.isGranted) return true;

    status = await Permission.videos.request();
    if (status.isGranted) return true;

    // Fall back to storage for older Android
    status = await Permission.storage.request();
    return status.isGranted;
  }

  /// Open app settings if permissions permanently denied
  static Future<bool> openSettings() async {
    return await openAppSettings();
  }
}