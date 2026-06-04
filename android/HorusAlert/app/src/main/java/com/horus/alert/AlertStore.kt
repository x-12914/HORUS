package com.horus.alert

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** A received alert persisted locally, plus its acknowledged flag. */
data class StoredAlert(
    val id: Int,
    val title: String?,
    val message: String,
    val severity: String,
    val sent: String,
    val acknowledged: Boolean
)

/** Persists the most recent received alerts in SharedPreferences as JSON. */
object AlertStore {
    private const val FILE = "horus_alerts"
    private const val KEY = "list"
    private const val MAX = 50

    private fun sp(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun all(c: Context): List<StoredAlert> {
        val arr = JSONArray(sp(c).getString(KEY, "[]"))
        val out = ArrayList<StoredAlert>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            out.add(
                StoredAlert(
                    o.getInt("id"),
                    if (o.isNull("title")) null else o.optString("title"),
                    o.optString("message"),
                    o.optString("severity"),
                    o.optString("sent"),
                    o.optBoolean("acknowledged", false)
                )
            )
        }
        return out.sortedByDescending { it.id }
    }

    fun add(c: Context, a: AlertMsg) {
        val list = all(c).toMutableList()
        if (list.any { it.id == a.id }) return
        list.add(StoredAlert(a.id, a.title, a.message, a.severity, a.sent, false))
        save(c, list.sortedByDescending { it.id }.take(MAX))
    }

    fun markAck(c: Context, id: Int) {
        save(c, all(c).map { if (it.id == id) it.copy(acknowledged = true) else it })
    }

    private fun save(c: Context, list: List<StoredAlert>) {
        val arr = JSONArray()
        list.forEach {
            arr.put(
                JSONObject()
                    .put("id", it.id)
                    .put("title", it.title ?: JSONObject.NULL)
                    .put("message", it.message)
                    .put("severity", it.severity)
                    .put("sent", it.sent)
                    .put("acknowledged", it.acknowledged)
            )
        }
        sp(c).edit().putString(KEY, arr.toString()).apply()
    }
}
