package com.horus.alert

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Foreground service that polls HORUS for new alerts. Each unacknowledged alert
 * keeps a looping alarm + vibration going and shows a persistent (non-dismissable)
 * notification with an ACKNOWLEDGE action — the alarm only stops once every
 * alert has been acknowledged on the device.
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
        // Acknowledgement delivered from a notification action / activity / list.
        if (intent?.action == ACTION_ACK) {
            handleAck(intent.getIntExtra("id", -1))
            return START_STICKY
        }

        Prefs.setRunning(this, true)
        if (!polling) {
            polling = true
            Log.i(TAG, "service started; polling every ${POLL_MS}ms")
            scope.launch { loop() }
        }
        updateAlarmState()   // resume alarm if alerts are still unacknowledged
        return START_STICKY
    }

    private suspend fun loop() {
        while (Prefs.isRunning(this)) {
            try {
                val token = Prefs.getDeviceToken(this)
                if (token.isEmpty()) {
                    Log.w(TAG, "skip poll: device not enrolled")
                } else {
                    val alerts = HorusApi.poll(token)
                    if (alerts.isNotEmpty()) Log.i(TAG, "poll: ${alerts.size} new alert(s)")
                    for (a in alerts) {
                        Log.i(TAG, "alert #${a.id} [${a.severity}] ${a.message}")
                        AlertStore.add(this, a)
                        notifyAlert(a)
                    }
                    if (alerts.isNotEmpty()) updateAlarmState()
                }
            } catch (e: Exception) {
                val msg = e.message ?: ""
                if (msg.contains("401")) {
                    Log.i(TAG, "awaiting approval — phone not yet enabled in the dashboard")
                } else {
                    Log.w(TAG, "poll failed: $msg")
                }
            }
            delay(POLL_MS)
        }
        Log.i(TAG, "service stopping")
        polling = false
        AlarmPlayer.stop()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    /** Mark acknowledged locally + on the server, clear its notification, re-evaluate the alarm. */
    private fun handleAck(id: Int) {
        scope.launch {
            if (id >= 0) {
                AlertStore.markAck(this@AlertPollService, id)
                try {
                    val token = Prefs.getDeviceToken(this@AlertPollService)
                    if (token.isNotEmpty()) HorusApi.ack(token, id)
                } catch (e: Exception) {
                    Log.w(TAG, "ack failed: ${e.message}")
                }
                getSystemService(NotificationManager::class.java).cancel(id)
                Log.i(TAG, "ack handled for #$id")
            }
            updateAlarmState()
            // If we were only started to handle an ack (not monitoring), don't linger.
            if (!polling && !Prefs.isRunning(this@AlertPollService)) {
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
    }

    /** Alarm on while any stored alert is unacknowledged; off otherwise. */
    private fun updateAlarmState() {
        val anyPending = AlertStore.all(this).any { !it.acknowledged }
        if (anyPending) AlarmPlayer.start(this) else AlarmPlayer.stop()
    }

    private fun notifyAlert(a: AlertMsg) {
        val nm = getSystemService(NotificationManager::class.java)
        val isAir = a.severity.equals("AIR ALERT", ignoreCase = true)

        val fsIntent = Intent(this, AlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            putExtra("id", a.id)
            putExtra("title", a.title)
            putExtra("message", a.message)
            putExtra("severity", a.severity)
        }
        val fsPi = PendingIntent.getActivity(
            this, a.id, fsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val ackIntent = Intent(this, AlertPollService::class.java).apply {
            action = ACTION_ACK
            putExtra("id", a.id)
        }
        val ackPi = PendingIntent.getService(
            this, ACK_REQ_BASE + a.id, ackIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val heading = (a.title?.takeIf { it.isNotBlank() } ?: "HORUS") +
            if (isAir) " — AIR ALERT" else ""

        val builder = NotificationCompat.Builder(this, CH_ALERT)
            .setSmallIcon(R.drawable.ic_stat_alert)
            .setContentTitle(heading)
            .setContentText(a.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(a.message))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setOngoing(true)        // can't be swiped away
            .setAutoCancel(false)
            .setContentIntent(fsPi)
            .setFullScreenIntent(fsPi, true)
            .addAction(R.drawable.ic_stat_alert, "ACKNOWLEDGE", ackPi)

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
        // High importance for heads-up display, but silent: continuous audio +
        // vibration is driven by AlarmPlayer so it can persist until acknowledged.
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERT, "Defense Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                setSound(null, null)
                enableVibration(false)
                setBypassDnd(true)
            }
        )
    }

    override fun onDestroy() {
        super.onDestroy()
        AlarmPlayer.stop()
        scope.cancel()
    }

    companion object {
        const val TAG = "HORUS"
        const val POLL_MS = 4_000L
        const val SVC_NOTIF_ID = 1001
        const val CH_SVC = "svc"
        const val CH_ALERT = "alerts2"
        const val ACTION_ACK = "com.horus.alert.ACK"
        const val ACK_REQ_BASE = 100_000

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

        /** Acknowledge an alert (stops the alarm when none remain). */
        fun acknowledge(c: Context, id: Int) {
            val i = Intent(c, AlertPollService::class.java).apply {
                action = ACTION_ACK
                putExtra("id", id)
            }
            c.startService(i)
        }
    }
}
