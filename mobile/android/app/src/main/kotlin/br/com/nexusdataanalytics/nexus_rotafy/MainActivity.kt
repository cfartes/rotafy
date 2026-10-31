package br.com.nexusdataanalytics.nexus_rotafy

import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock

class MainActivity : FlutterFragmentActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        if (TrackingService.activeSession == null) getSharedPreferences("tracking_positions", MODE_PRIVATE).edit().clear().apply()
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "rotafy/tracking").setMethodCallHandler { call, result ->
            when (call.method) {
                "start" -> {
                    try {
                        val intent = Intent(this, TrackingService::class.java)
                        for (key in listOf("session", "base", "origin", "cookie", "csrf")) intent.putExtra(key, call.argument<String>(key))
                        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
                        val session = call.argument<String>("session")
                        val deadline = SystemClock.elapsedRealtime() + 5000
                        val handler = Handler(Looper.getMainLooper())
                        handler.post(object : Runnable {
                            override fun run() {
                                if (session != null && TrackingService.activeSession == session) {
                                    result.success(true)
                                    // Start the location service while the activity is still in the foreground.
                                    if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 3838)
                                } else if (SystemClock.elapsedRealtime() >= deadline) {
                                    stopService(Intent(this@MainActivity, TrackingService::class.java))
                                    result.error("tracking_start", "O Android não confirmou o rastreamento. Abra o app e tente assumir novamente.", null)
                                } else handler.postDelayed(this, 100)
                            }
                        })
                    } catch (e: Exception) { result.error("tracking_start", "Não foi possível iniciar. Confira a permissão de localização.", null) }
                }
                "stop" -> { stopService(Intent(this, TrackingService::class.java)); result.success(true) }
                "status" -> result.success(TrackingService.activeSession)
                else -> result.notImplemented()
            }
        }
    }
}
