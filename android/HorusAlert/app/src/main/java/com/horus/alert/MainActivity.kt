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

    private lateinit var serverEt: EditText
    private lateinit var enrolEt: EditText
    private lateinit var labelEt: EditText
    private lateinit var statusTv: TextView
    private lateinit var alertsContainer: LinearLayout
    private lateinit var toggleBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        serverEt = findViewById(R.id.serverEt)
        enrolEt = findViewById(R.id.enrolEt)
        labelEt = findViewById(R.id.labelEt)
        statusTv = findViewById(R.id.statusTv)
        alertsContainer = findViewById(R.id.alertsContainer)
        toggleBtn = findViewById(R.id.toggleBtn)

        serverEt.setText(Prefs.getServer(this))
        enrolEt.setText(Prefs.getEnrolToken(this))
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

    private fun saveFields() {
        Prefs.setServer(this, serverEt.text.toString().trim())
        Prefs.setEnrolToken(this, enrolEt.text.toString().trim())
        Prefs.setLabel(this, labelEt.text.toString().trim())
    }

    private fun enrol() {
        saveFields()
        val server = Prefs.getServer(this)
        val enrol = Prefs.getEnrolToken(this)
        val label = Prefs.getLabel(this).ifEmpty { "Unnamed phone" }
        if (server.isEmpty() || enrol.isEmpty()) {
            toast("Enter server URL and enrolment token")
            return
        }
        statusTv.text = "Enrolling…"
        Log.i(TAG, "enrolling '$label' at $server")
        lifecycleScope.launch {
            try {
                val token = HorusApi.register(server, enrol, label, "android")
                Prefs.setDeviceToken(this@MainActivity, token)
                Log.i(TAG, "enrol OK; device token stored (len=${token.length})")
                toast("Enrolled successfully")
            } catch (e: Exception) {
                Log.e(TAG, "enrol failed", e)
                toast("Enrol failed: ${e.message}")
            }
            refreshStatus()
        }
    }

    private fun toggleService() {
        saveFields()
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
