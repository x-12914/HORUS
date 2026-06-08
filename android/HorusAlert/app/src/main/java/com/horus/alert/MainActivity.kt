package com.horus.alert

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var labelEt: EditText
    private lateinit var statusTv: TextView
    private lateinit var alertsContainer: LinearLayout
    private lateinit var toggleBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        labelEt = findViewById(R.id.labelEt)
        statusTv = findViewById(R.id.statusTv)
        alertsContainer = findViewById(R.id.alertsContainer)
        toggleBtn = findViewById(R.id.toggleBtn)

        findViewById<TextView>(R.id.serverTv).text = Config.SERVER
        findViewById<TextView>(R.id.deviceTv).text = DeviceId.get(this)
        labelEt.setText(Prefs.getLabel(this))

        findViewById<Button>(R.id.enrolBtn).setOnClickListener { enrol() }
        toggleBtn.setOnClickListener { toggleService() }

        requestNotifPermission()
    }

    override fun onResume() {
        super.onResume()
        renderAlerts()
        refreshStatus()
    }

    private fun enrol() {
        val label = labelEt.text.toString().trim().ifEmpty { "Unnamed phone" }
        Prefs.setLabel(this, label)
        val deviceToken = DeviceId.get(this)
        Prefs.setDeviceToken(this, deviceToken)

        statusTv.text = "Enrolling…"
        Log.i(TAG, "enrolling '$label' as $deviceToken")
        lifecycleScope.launch {
            try {
                val pending = HorusApi.register(deviceToken, label, "android")
                Log.i(TAG, "enrol OK; pending=$pending")
                toast(if (pending) "Enrolled — awaiting operator approval" else "Enrolled & active")
            } catch (e: Exception) {
                Log.e(TAG, "enrol failed", e)
                toast("Enrol failed: ${e.message}")
            }
            refreshStatus()
        }
    }

    private fun toggleService() {
        if (Prefs.isRunning(this)) {
            AlertPollService.stop(this)
            Log.i(TAG, "monitoring stopped by user")
            toast("Monitoring stopped")
        } else {
            if (Prefs.getDeviceToken(this).isEmpty()) {
                toast("Enrol this phone first")
                return
            }
            AlertPollService.start(this)
            Log.i(TAG, "monitoring started by user")
            toast("Monitoring started")
        }
        toggleBtn.postDelayed({ refreshStatus() }, 300)
    }

    private fun refreshStatus() {
        val enrolled = Prefs.getDeviceToken(this).isNotEmpty()
        val running = Prefs.isRunning(this)
        statusTv.text = (if (enrolled) "Enrolled ✓" else "Not enrolled") +
            "  ·  " + (if (running) "Monitoring" else "Stopped")
        toggleBtn.text = if (running) "STOP MONITORING" else "START MONITORING"
    }

    private fun renderAlerts() {
        alertsContainer.removeAllViews()
        val alerts = AlertStore.all(this)
        if (alerts.isEmpty()) {
            val tv = TextView(this)
            tv.text = "No alerts received yet."
            alertsContainer.addView(tv)
            return
        }
        for (a in alerts) {
            val card = layoutInflater.inflate(R.layout.item_alert, alertsContainer, false)
            card.findViewById<TextView>(R.id.itemSeverity).text = a.severity
            card.findViewById<TextView>(R.id.itemTitle).text = a.title ?: "HORUS Alert"
            card.findViewById<TextView>(R.id.itemMessage).text = a.message
            val ackBtn = card.findViewById<Button>(R.id.itemAck)
            if (a.acknowledged) {
                ackBtn.text = "ACKNOWLEDGED"
                ackBtn.isEnabled = false
            }
            ackBtn.setOnClickListener {
                AlertStore.markAck(this, a.id)            // instant local state
                AlertPollService.acknowledge(this, a.id)  // server ack + stop alarm
                renderAlerts()
            }
            alertsContainer.addView(card)
        }
    }

    private fun requestNotifPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    companion object {
        private const val TAG = "HORUS"
    }
}
