package com.horus.alert

import android.content.Context

/** Small SharedPreferences wrapper for config + state. */
object Prefs {
    private const val FILE = "horus_prefs"
    private fun sp(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun getServer(c: Context): String = sp(c).getString("server", "") ?: ""
    fun setServer(c: Context, v: String) = sp(c).edit().putString("server", v).apply()

    fun getEnrolToken(c: Context): String = sp(c).getString("enrol", "") ?: ""
    fun setEnrolToken(c: Context, v: String) = sp(c).edit().putString("enrol", v).apply()

    fun getLabel(c: Context): String = sp(c).getString("label", "") ?: ""
    fun setLabel(c: Context, v: String) = sp(c).edit().putString("label", v).apply()

    fun getDeviceToken(c: Context): String = sp(c).getString("device_token", "") ?: ""
    fun setDeviceToken(c: Context, v: String) = sp(c).edit().putString("device_token", v).apply()

    fun isRunning(c: Context): Boolean = sp(c).getBoolean("running", false)
    fun setRunning(c: Context, v: Boolean) = sp(c).edit().putBoolean("running", v).apply()
}
