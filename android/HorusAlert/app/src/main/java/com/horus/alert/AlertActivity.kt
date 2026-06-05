package com.horus.alert

import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/** Full-screen alert shown for AIR ALERTs (and when an alert is tapped). */
class AlertActivity : AppCompatActivity() {

    private var ringtone: Ringtone? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Wake the screen and show over the lock screen (API 27+).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_alert)

        val id = intent.getIntExtra("id", -1)
        val title = intent.getStringExtra("title")
        val message = intent.getStringExtra("message") ?: ""
        val severity = intent.getStringExtra("severity") ?: "INFO"

        findViewById<TextView>(R.id.alertSeverity).text = severity
        findViewById<TextView>(R.id.alertTitle).text = title ?: "HORUS Alert"
        findViewById<TextView>(R.id.alertMessage).text = message
        Log.i("HORUS", "AlertActivity shown for alert #$id [$severity]")

        if (severity.equals("AIR ALERT", ignoreCase = true)) playAlarm()

        findViewById<Button>(R.id.ackButton).setOnClickListener {
            Log.i("HORUS", "user acknowledged alert #$id")
            stopAlarm()
            AlertStore.markAck(this, id)
            val server = Prefs.getServer(this)
            val token = Prefs.getDeviceToken(this)
            lifecycleScope.launch {
                try {
                    if (id >= 0 && token.isNotEmpty()) HorusApi.ack(server, token, id)
                } catch (_: Exception) {
                }
                finish()
            }
        }
    }

    private fun playAlarm() {
        try {
            val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ringtone = RingtoneManager.getRingtone(applicationContext, uri).apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) isLooping = true
                play()
            }
        } catch (_: Exception) {
        }
    }

    private fun stopAlarm() {
        try {
            ringtone?.stop()
        } catch (_: Exception) {
        }
        ringtone = null
    }

    override fun onDestroy() {
        super.onDestroy()
        stopAlarm()
    }
}
