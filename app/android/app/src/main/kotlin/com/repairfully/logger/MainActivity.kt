package com.repairfully.logger

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.media.MediaScannerConnection
import android.net.Uri
import android.provider.MediaStore
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
                    "deleteFile" -> {
                        val path = call.argument<String>("path")
                        if (path != null) {
                            val removed = deleteFromMediaStore(path)
                            result.success(removed)
                        } else {
                            result.error("INVALID_ARGUMENT", "Path is required", null)
                        }
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

        // Device ID channel — demo-trial anchor (see lib/services/trial_service.dart).
        // Settings.Secure.ANDROID_ID is scoped per app-signing-key + user + device
        // and survives app uninstall/reinstall (unlike SharedPreferences), which is
        // the whole point of using it as the trial anchor. device_info_plus does NOT
        // expose this — its `id` field returns Build.ID (the OS firmware build,
        // identical across every device on that build) since androidId was dropped
        // from that package in v4.0.0. Hence a dedicated channel here.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.repairfully.camera/device_id")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getAndroidId" -> {
                        val id = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
                        result.success(id)
                    }
                    else -> result.notImplemented()
                }
            }
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

    /// Remove a file from MediaStore so the Files/Gallery index stops listing it.
    private fun deleteFromMediaStore(path: String): Boolean {
        val file = java.io.File(path)
        var removedFromStore = false
        try {
            val resolver = applicationContext.contentResolver
            val collections = listOf(
                MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                MediaStore.Files.getContentUri("external"),
            )
            for (collection in collections) {
                val deleted = resolver.delete(
                    collection,
                    MediaStore.MediaColumns.DATA + "=?",
                    arrayOf(path),
                )
                if (deleted > 0) removedFromStore = true
            }
        } catch (e: Exception) {
            // Fall through — still try to delete the on-disk file below.
        }
        return try {
            if (file.exists()) file.delete() || removedFromStore else removedFromStore
        } catch (e: Exception) {
            removedFromStore
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> {
                // Android re-fires onKeyDown repeatedly while a key is HELD
                // (key-repeat) — event.repeatCount > 0 on those repeats.
                // Forwarding every repeat let one physical long-press send
                // multiple stop-recording events to Dart (see
                // live_capture_screen.dart's _stoppingRecording guard for
                // the other half of this fix). Only forward the initial
                // press; still consume every repeat (return true) so the
                // system volume UI doesn't reappear mid-recording.
                if (event.repeatCount == 0) sendVolumeEvent(1)
                true
            }
            KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event.repeatCount == 0) sendVolumeEvent(2)
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