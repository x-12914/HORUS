package com.horus.alert

import android.content.Context

/** Small SharedPreferences wrapper for config + state. */
object Prefs {
    private const val FILE = "horus_prefs"
    private fun sp(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun getLabel(c: Context): String = sp(c).getString("label", "") ?: ""
    fun setLabel(c: Context, v: String) = sp(c).edit().putString("label", v).apply()

    // The device token is the stable device id (set at enrolment).
    fun getDeviceToken(c: Context): String = sp(c).getString("device_token", "") ?: ""
    fun setDeviceToken(c: Context, v: String) = sp(c).edit().putString("device_token", v).apply()

    fun isRunning(c: Context): Boolean = sp(c).getBoolean("running", false)
    fun setRunning(c: Context, v: Boolean) = sp(c).edit().putBoolean("running", v).apply()
}
