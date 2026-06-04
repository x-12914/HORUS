package com.horus.alert

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Foreground service that polls HORUS for new alerts every few seconds and
 * raises a high-priority notification (full-screen + alarm for AIR ALERT).
 */
class AlertPollService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var polling = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
        startForeground(SVC_NOTIF_ID, serviceNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Prefs.setRunning(this, true)
        if (!polling) {
            polling = true
            scope.launch { loop() }
        }
        return START_STICKY
    }

    private suspend fun loop() {
        while (Prefs.isRunning(this)) {
            try {
                val server = Prefs.getServer(this)
                val token = Prefs.getDeviceToken(this)
                if (server.isNotEmpty() && token.isNotEmpty()) {
                    for (a in HorusApi.poll(server, token)) {
                        AlertStore.add(this, a)
                        notifyAlert(a)
                    }
                }
            } catch (_: Exception) {
                // Transient network error — ignore and retry next cycle.
            }
            delay(POLL_MS)
        }
        polling = false
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun notifyAlert(a: AlertMsg) {
        val isAir = a.severity.equals("AIR ALERT", ignoreCase = true)
        val nm = getSystemService(NotificationManager::class.java)

        val tapIntent = Intent(this, AlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            putExtra("id", a.id)
            putExtra("title", a.title)
            putExtra("message", a.message)
            putExtra("severity", a.severity)
        }
        val pi = PendingIntent.getActivity(
            this, a.id, tapIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val heading = (a.title?.takeIf { it.isNotBlank() } ?: "HORUS") +
            if (isAir) " — AIR ALERT" else ""

        val builder = NotificationCompat.Builder(this, if (isAir) CH_AIR else CH_ALERT)
            .setSmallIcon(R.drawable.ic_stat_alert)
            .setContentTitle(heading)
            .setContentText(a.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(a.message))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pi)

        if (isAir) builder.setFullScreenIntent(pi, true)
        nm.notify(a.id, builder.build())
    }

    private fun serviceNotification(): Notification =
        NotificationCompat.Builder(this, CH_SVC)
            .setSmallIcon(R.drawable.ic_stat_alert)
            .setContentTitle("HORUS Alert active")
            .setContentText("Monitoring for alerts")
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

    private fun createChannels() {
        val nm = getSystemService(NotificationManager::class.java)

        nm.createNotificationChannel(
            NotificationChannel(CH_SVC, "Service", NotificationManager.IMPORTANCE_LOW)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERT, "Alerts", NotificationManager.IMPORTANCE_HIGH)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_AIR, "Air Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                setSound(
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                    Notification.AUDIO_ATTRIBUTES_DEFAULT
                )
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 600, 300, 600, 300, 600)
                setBypassDnd(true)
            }
        )
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }

    companion object {
        const val POLL_MS = 4_000L
        const val SVC_NOTIF_ID = 1001
        const val CH_SVC = "svc"
        const val CH_ALERT = "alerts"
        const val CH_AIR = "airalert"

        fun start(c: Context) {
            val i = Intent(c, AlertPollService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                c.startForegroundService(i)
            } else {
                c.startService(i)
            }
        }

        fun stop(c: Context) {
            Prefs.setRunning(c, false)
            c.stopService(Intent(c, AlertPollService::class.java))
        }
    }
}
