package br.com.nexusdataanalytics.nexus_rotafy

import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.content.Intent
import android.os.Build

class MainActivity : FlutterFragmentActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        if (TrackingService.activeSession == null) getSharedPreferences("tracking_positions", MODE_PRIVATE).edit().clear().apply()
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "rotafy/tracking").setMethodCallHandler { call, result ->
            when (call.method) {
                "start" -> {
                    try {
                        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 3838)
                        val intent = Intent(this, TrackingService::class.java)
                        for (key in listOf("session", "base", "origin", "cookie", "csrf")) intent.putExtra(key, call.argument<String>(key))
                        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
                        result.success(true)
                    } catch (e: Exception) { result.error("tracking_start", "Não foi possível iniciar. Confira a permissão de localização.", null) }
                }
                "stop" -> { stopService(Intent(this, TrackingService::class.java)); result.success(true) }
                "status" -> result.success(TrackingService.activeSession)
                else -> result.notImplemented()
            }
        }
    }
}
