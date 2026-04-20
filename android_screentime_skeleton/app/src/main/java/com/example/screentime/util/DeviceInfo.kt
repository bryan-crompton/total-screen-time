package com.example.screentime.util

import android.os.Build

object DeviceInfo {
    fun defaultDeviceLabel(): String {
        val manufacturer = Build.MANUFACTURER ?: "android"
        val model = Build.MODEL ?: "device"
        return (manufacturer + "-" + model)
            .lowercase()
            .replace("""\s+""".toRegex(), "-")
    }
}