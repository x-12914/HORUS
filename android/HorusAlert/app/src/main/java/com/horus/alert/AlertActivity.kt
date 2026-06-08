package com.horus.alert

import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Full-screen alert screen. The alarm sound/vibration is owned by the service
 * (so it persists regardless of this screen); acknowledging here routes to the
 * service, which stops the alarm once no unacknowledged alerts remain.
 */
class AlertActivity : AppCompatActivity() {

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

        findViewById<Button>(R.id.ackButton).setOnClickListener {
            Log.i("HORUS", "user acknowledged alert #$id")
            AlertStore.markAck(this, id)             // instant local state
            AlertPollService.acknowledge(this, id)   // server ack + stop alarm
            finish()
        }
    }
}
