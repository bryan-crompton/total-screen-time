package com.example.screentime

object AppConfig {
    const val SERVER_URL = "http://192.168.1.6:7777"
    const val DEVICE_TYPE = "android"
    const val DB_NAME = "screentime_android.db"

    const val NOTIFICATION_CHANNEL_ID = "screentime_tracking"
    const val NOTIFICATION_ID = 1001

    const val SYNC_WORK_NAME = "screentime_periodic_sync"
    const val ONE_TIME_SYNC_WORK_NAME = "screentime_one_time_sync"
}
