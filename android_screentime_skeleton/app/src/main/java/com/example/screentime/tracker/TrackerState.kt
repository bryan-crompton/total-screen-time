package com.example.screentime.tracker

import android.app.KeyguardManager
import android.content.Context
import android.os.PowerManager

object TrackerState {
    fun isInteractiveAndUnlocked(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val keyguardManager = context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        return powerManager.isInteractive && !keyguardManager.isDeviceLocked
    }
}
