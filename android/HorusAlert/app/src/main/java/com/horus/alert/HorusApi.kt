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
 * Talks to the HORUS phone-app API over plain HttpURLConnection + org.json,
 * so the app has no heavyweight HTTP/JSON dependencies.
 */
object HorusApi {

    private fun base(url: String) = url.trim().trimEnd('/')

    /** Enrol this phone; returns its device_token. */
    suspend fun register(server: String, enrolToken: String, label: String, platform: String): String =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("label", label).put("platform", platform)
            val resp = post("${base(server)}/api/alerts/register", body, mapOf("X-HORUS-ENROLL" to enrolToken))
            val token = resp.optString("device_token")
            if (token.isEmpty()) throw IOException("Server returned no device_token") else token
        }

    /** Fetch pending alerts (the server marks them delivered). */
    suspend fun poll(server: String, deviceToken: String): List<AlertMsg> =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("device_token", deviceToken)
            val resp = post("${base(server)}/api/alerts/poll", body, emptyMap())
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
    suspend fun ack(server: String, deviceToken: String, alertId: Int) =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("device_token", deviceToken).put("alert_id", alertId)
            post("${base(server)}/api/alerts/ack", body, emptyMap())
            Unit
        }

    private fun post(urlStr: String, body: JSONObject, headers: Map<String, String>): JSONObject {
        val conn = URL(urlStr).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 10_000
            conn.readTimeout = 15_000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            headers.forEach { (k, v) -> conn.setRequestProperty(k, v) }
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
