package com.horus.alert

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "HORUS"

/** One alert as received from the server. */
data class AlertMsg(
    val id: Int,
    val title: String?,
    val message: String,
    val severity: String,
    val sent: String
)

/**
 * Talks to the HORUS phone-app API. The server URL is fixed (Config.SERVER) and
 * the phone identifies itself with its device id — no token to type. A freshly
 * enrolled phone is PENDING until an operator approves it in the dashboard.
 */
object HorusApi {

    private val base = Config.SERVER.trim().trimEnd('/')

    /** Self-enrol this phone. Returns true if it is PENDING approval. */
    suspend fun register(deviceToken: String, label: String, platform: String): Boolean =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("device_token", deviceToken)
                .put("label", label)
                .put("platform", platform)
            val resp = post("$base/api/alerts/register", body)
            resp.optBoolean("pending", false)
        }

    /** Fetch pending alerts (the server marks them delivered). */
    suspend fun poll(deviceToken: String): List<AlertMsg> =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("device_token", deviceToken)
            val resp = post("$base/api/alerts/poll", body)
            val arr = resp.optJSONArray("alerts") ?: JSONArray()
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                AlertMsg(
                    id = o.getInt("id"),
                    title = o.optString("title").ifEmpty { null },
                    message = o.optString("message"),
                    severity = o.optString("severity", "INFO"),
                    sent = o.optString("sent")
                )
            }
        }

    /** Acknowledge an alert for this phone. */
    suspend fun ack(deviceToken: String, alertId: Int) =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("device_token", deviceToken).put("alert_id", alertId)
            post("$base/api/alerts/ack", body)
            Unit
        }

    private fun post(urlStr: String, body: JSONObject): JSONObject {
        val conn = URL(urlStr).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 10_000
            conn.readTimeout = 15_000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            Log.d(TAG, "POST $urlStr -> $code")
            if (code !in 200..299) throw IOException("HTTP $code: $text")
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }
}
