package com.horus.alert

import android.content.Context
import android.provider.Settings
import java.util.UUID

/**
 * Stable per-device identifier used as this phone's device token, so the app
 * identifies itself automatically with no token to type. Uses the Android ID;
 * falls back to a persisted random UUID if it is unavailable.
 */
object DeviceId {
    private const val BAD_ANDROID_ID = "9774d56d682e549c" // known buggy value on some old devices

    fun get(context: Context): String {
        val android = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ANDROID_ID
        )
        if (!android.isNullOrBlank() && android != BAD_ANDROID_ID) {
            return "android-$android"
        }
        // Fallback: generate once and persist.
        val sp = context.getSharedPreferences("horus_prefs", Context.MODE_PRIVATE)
        var fallback = sp.getString("fallback_id", null)
        if (fallback == null) {
            fallback = "uuid-" + UUID.randomUUID().toString()
            sp.edit().putString("fallback_id", fallback).apply()
        }
        return fallback
    }
}
