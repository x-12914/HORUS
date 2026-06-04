package com.horus.alert

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restart monitoring after a reboot if it was active. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED && Prefs.isRunning(context)) {
            AlertPollService.start(context)
        }
    }
}
