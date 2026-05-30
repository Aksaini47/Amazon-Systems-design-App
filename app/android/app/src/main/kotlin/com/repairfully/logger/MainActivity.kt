package com.repairfully.logger

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.media.MediaRecorder
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.view.KeyEvent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Volume button handler
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "volume_channel")
            .setMethodCallHandler { _, _ -> }

        // MediaScanner channel - properly scan files into MediaStore
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.repairfully.camera/media_scanner")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "scanFile" -> {
                        val path = call.argument<String>("path")
                        if (path != null) {
                            scanFileModern(path)
                            result.success(true)
                        } else {
                            result.error("INVALID_ARGUMENT", "Path is required", null)
                        }
                    }
                    "scanDirectory" -> {
                        val dir = call.argument<String>("dir")
                        if (dir != null) {
                            scanDirectoryModern(dir)
                            result.success(true)
                        } else {
                            result.error("INVALID_ARGUMENT", "Directory is required", null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }

        // Video codec info channel
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.repairfully.camera/video_codec")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isH265Supported" -> {
                        result.success(isH265HardwareEncoderSupported())
                    }
                    else -> result.notImplemented()
                }
            }

        // Do Not Disturb channel — gates notifications/ringer during recording
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.repairfully.camera/dnd")
            .setMethodCallHandler { call, result ->
                val nm = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                when (call.method) {
                    "isPermissionGranted" -> {
                        // ACCESS_NOTIFICATION_POLICY is granted at runtime via a system
                        // settings page — not via a regular runtime-permission prompt.
                        result.success(nm.isNotificationPolicyAccessGranted)
                    }
                    "openSettings" -> {
                        // Sends the user to the Do Not Disturb access page so they can
                        // toggle our app's permission. Returns immediately; permission
                        // state must be re-checked when the user returns.
                        try {
                            val intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            startActivity(intent)
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("OPEN_SETTINGS_FAILED", e.message, null)
                        }
                    }
                    "setFilter" -> {
                        // 1 = INTERRUPTION_FILTER_ALL   (normal — allow everything)
                        // 2 = INTERRUPTION_FILTER_PRIORITY (priority calls/messages only)
                        // 3 = INTERRUPTION_FILTER_NONE  (block everything, total silence)
                        val level = call.argument<Int>("level") ?: 1
                        try {
                            if (!nm.isNotificationPolicyAccessGranted) {
                                result.success(false)
                                return@setMethodCallHandler
                            }
                            nm.setInterruptionFilter(level)
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("SET_FILTER_FAILED", e.message, null)
                        }
                    }
                    "getFilter" -> {
                        try {
                            result.success(nm.currentInterruptionFilter)
                        } catch (e: Exception) {
                            result.error("GET_FILTER_FAILED", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /// Check if H.265/HEVC hardware encoder is supported
    private fun isH265HardwareEncoderSupported(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return false

        try {
            val codecList = android.media.MediaCodecList(android.media.MediaCodecList.REGULAR_CODECS)
            for (codecInfo in codecList.codecInfos) {
                if (codecInfo.isEncoder) {
                    for (mimeType in codecInfo.supportedTypes) {
                        if (mimeType.equals("video/hevc", ignoreCase = true) ||
                            mimeType.equals("video/h265", ignoreCase = true)) {
                            // Found HEVC encoder
                            return true
                        }
                    }
                }
            }
        } catch (e: Exception) {
            // Silent fail
        }
        return false
    }

    /// Modern MediaScanner using MediaScannerConnection
    /// This properly adds files to MediaStore so they appear in Files app
    private fun scanFileModern(path: String) {
        try {
            MediaScannerConnection.scanFile(
                applicationContext,
                arrayOf(path),
                arrayOf("video/*"),  // MIME type for video
                null  // completion callback
            )
        } catch (e: Exception) {
            // Fallback to deprecated broadcast if modern API fails
            try {
                val mediaScanIntent = Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE)
                mediaScanIntent.data = Uri.fromFile(java.io.File(path))
                sendBroadcast(mediaScanIntent)
            } catch (e2: Exception) {
                // Silent fail
            }
        }
    }

    /// Scan entire directory
    private fun scanDirectoryModern(dirPath: String) {
        try {
            val dir = java.io.File(dirPath)
            if (dir.exists() && dir.isDirectory) {
                val files = dir.listFiles()
                if (files != null && files.isNotEmpty()) {
                    val paths = files.map { it.absolutePath }.toTypedArray()
                    MediaScannerConnection.scanFile(
                        applicationContext,
                        paths,
                        arrayOf("video/*", "image/*"),
                        null
                    )
                }
            }
        } catch (e: Exception) {
            // Silent fail
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> {
                sendVolumeEvent(1)
                true
            }
            KeyEvent.KEYCODE_VOLUME_DOWN -> {
                sendVolumeEvent(2)
                true
            }
            else -> super.onKeyDown(keyCode, event)
        }
    }

    private fun sendVolumeEvent(volumeEventType: Int) {
        MethodChannel(flutterEngine!!.dartExecutor.binaryMessenger, "volume_channel")
            .invokeMethod("volume_button_pressed", volumeEventType)
    }
}