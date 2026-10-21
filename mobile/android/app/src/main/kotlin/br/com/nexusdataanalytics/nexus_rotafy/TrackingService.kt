package br.com.nexusdataanalytics.nexus_rotafy

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.location.*
import android.os.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import java.util.concurrent.Executors

/** User-started location foreground service; credentials remain in memory only. */
class TrackingService : Service() {
    companion object { @Volatile var activeSession: String? = null }
    private val handler = Handler(Looper.getMainLooper())
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var locations: LocationManager
    private var base = ""
    private var origin = ""
    private var cookie = ""
    private var csrf = ""
    private var lastContact = 0L
    private var listener: LocationListener? = null
    private var wakeLock: PowerManager.WakeLock? = null
    @Volatile private var generation = 0
    @Volatile private var destroyed = false
    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate()
        locations = getSystemService(LOCATION_SERVICE) as LocationManager
        wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$packageName:tracking")
            .apply { setReferenceCounted(false) }
        if (Build.VERSION.SDK_INT >= 26) {
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel("rotafy_location", "Rastreamento da viagem", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) { stopSelf(); return START_NOT_STICKY }
        val session = intent.getStringExtra("session") ?: return START_NOT_STICKY
        val api = intent.getStringExtra("base") ?: return START_NOT_STICKY
        if (URI(api).scheme != "https" || !api.endsWith("/api/v1")) { stopSelf(); return START_NOT_STICKY }
        generation++
        handler.removeCallbacksAndMessages(null)
        listener?.let { locations.removeUpdates(it) }; listener = null
        activeSession = session
        base = api; origin = intent.getStringExtra("origin") ?: ""
        cookie = intent.getStringExtra("cookie") ?: ""; csrf = intent.getStringExtra("csrf") ?: ""
        lastContact = SystemClock.elapsedRealtime()
        executor.execute {
            val prefs = getSharedPreferences("tracking_positions", MODE_PRIVATE)
            val edit = prefs.edit()
            for (key in prefs.all.keys) if (key != session) edit.remove(key)
            edit.apply()
        }
        val open = packageManager.getLaunchIntentForPackage(packageName) ?: Intent(this, MainActivity::class.java)
        val pending = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, "rotafy_location") else Notification.Builder(this)
        val notification = builder.setContentTitle("Rotafy · viagem em rastreamento")
            .setContentText("Localização a cada 5 minutos. Abra o app para interromper.")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation).setOngoing(true).setContentIntent(pending).build()
        startForeground(3838, notification)
        wakeLock?.acquire(360000)
        handler.post(tick)
        return START_NOT_STICKY
    }

    private fun request(method: String, path: String, body: JSONObject? = null): Int {
        var connection: HttpURLConnection? = null
        return try {
            connection = URI(base + path).toURL().openConnection() as HttpURLConnection
            connection.requestMethod = method; connection.connectTimeout = 12000; connection.readTimeout = 15000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Cookie", cookie); connection.setRequestProperty("X-CSRF-Token", csrf)
            connection.setRequestProperty("Origin", origin)
            if (body != null) {
                connection.doOutput = true; connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            connection.responseCode
        } catch (_: Exception) { 0 } finally { connection?.disconnect() }
    }

    private val tick = object : Runnable {
        override fun run() {
            val session = activeSession ?: return
            wakeLock?.acquire(360000)
            val current = generation
            executor.execute {
                val status = request("GET", "/tracking/sessions/$session")
                if (destroyed || current != generation) return@execute
                if (status in listOf(401,402,403,404,409,423)) { handler.post { stopSelf() }; return@execute }
                if (status == 200) { lastContact = SystemClock.elapsedRealtime(); flush(session) }
                // A device offline cannot learn that an administrator revoked tracking.
                // The short lease bounds offline collection to 15 minutes.
                if (SystemClock.elapsedRealtime()-lastContact > 15*60000) { handler.post { stopSelf() }; return@execute }
                handler.post { if (!destroyed && current == generation) capture(session, current) }
            }
            handler.postDelayed(this, 300000)
        }
    }

    private fun capture(session: String, current: Int) {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) { stopSelf(); return }
        val provider = when {
            locations.isProviderEnabled(LocationManager.GPS_PROVIDER) &&
                checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED -> LocationManager.GPS_PROVIDER
            locations.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> return
        }
        listener?.let { locations.removeUpdates(it) }
        val receiver = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                locations.removeUpdates(this); listener = null
                if (destroyed || current != generation || System.currentTimeMillis()-location.time > 120000) return
                val point = JSONObject().put("id",UUID.randomUUID().toString()).put("latitude",location.latitude)
                    .put("longitude",location.longitude).put("accuracy_m",location.accuracy.toDouble())
                    .put("captured_at",SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",Locale.US).apply { timeZone=TimeZone.getTimeZone("UTC") }.format(Date(location.time)))
                executor.execute {
                    if (destroyed || current != generation) return@execute
                    val prefs = getSharedPreferences("tracking_positions",MODE_PRIVATE)
                    val queued = JSONArray(prefs.getString(session,"[]"))
                    if (queued.length() < 300) queued.put(point)
                    prefs.edit().putString(session,queued.toString()).apply()
                    flush(session)
                }
            }
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
            override fun onProviderEnabled(provider: String) {}
            override fun onProviderDisabled(provider: String) {}
        }
        listener = receiver
        try { locations.requestSingleUpdate(provider, receiver, Looper.getMainLooper()) }
        catch (_: SecurityException) { stopSelf() }
        handler.postDelayed({ if (listener === receiver) { locations.removeUpdates(receiver); listener = null } },45000)
    }

    private fun flush(session: String) {
        if (destroyed || activeSession != session) return
        val prefs = getSharedPreferences("tracking_positions",MODE_PRIVATE)
        val queued = JSONArray(prefs.getString(session,"[]"))
        if (queued.length() == 0) return
        val status = request("POST","/tracking/sessions/$session/positions",JSONObject().put("positions",queued))
        if (status in 200..299 || status in listOf(401,403,404,409,422,423)) prefs.edit().remove(session).apply()
        if (status in listOf(401,402,403,404,409,423)) handler.post { stopSelf() }
    }

    override fun onDestroy() {
        destroyed = true; generation++; val session = activeSession; activeSession = null
        handler.removeCallbacksAndMessages(null); listener?.let { locations.removeUpdates(it) }
        // A deliberate local stop also releases the server session when online.
        if (session != null) executor.execute {
            request("DELETE","/tracking/sessions/$session")
            getSharedPreferences("tracking_positions",MODE_PRIVATE).edit().remove(session).apply()
        }
        executor.shutdown(); stopForeground(STOP_FOREGROUND_REMOVE)
        if (wakeLock?.isHeld == true) wakeLock?.release()
        super.onDestroy()
    }
}
