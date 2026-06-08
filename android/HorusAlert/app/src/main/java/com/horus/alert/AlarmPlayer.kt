package com.horus.alert

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * A looping alarm sound + repeating vibration that runs until [stop] is called.
 * Driven by the foreground service so an alert keeps sounding — even with the
 * screen off or the app swiped away — until the operator acknowledges it.
 */
object AlarmPlayer {

    private var player: MediaPlayer? = null
    private var vibrator: Vibrator? = null
    private var active = false

    @Synchronized
    fun start(context: Context) {
        if (active) return            // already sounding — don't stack
        active = true

        try {
            val uri = RingtoneManager.getActualDefaultRingtoneUri(context, RingtoneManager.TYPE_ALARM)
                ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            player = MediaPlayer().apply {
                setDataSource(context, uri)
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build()
                )
                isLooping = true
                setWakeMode(context, PowerManager.PARTIAL_WAKE_LOCK)
                prepare()
                start()
            }
        } catch (e: Exception) {
            Log.w("HORUS", "alarm sound failed: ${e.message}")
        }

        startVibration(context)
        Log.i("HORUS", "alarm started")
    }

    private fun startVibration(context: Context) {
        val vib = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
        vibrator = vib
        try {
            // Repeat the waveform from index 0 until cancelled.
            vib.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 700, 500), 0))
        } catch (_: Exception) {
        }
    }

    @Synchronized
    fun stop() {
        active = false
        try { player?.stop() } catch (_: Exception) {}
        try { player?.release() } catch (_: Exception) {}
        player = null
        try { vibrator?.cancel() } catch (_: Exception) {}
        vibrator = null
        Log.i("HORUS", "alarm stopped")
    }
}
