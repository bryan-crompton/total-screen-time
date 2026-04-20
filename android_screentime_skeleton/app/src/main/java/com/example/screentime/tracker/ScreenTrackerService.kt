package com.example.screentime.tracker

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.example.screentime.AppConfig
import com.example.screentime.R
import com.example.screentime.data.IntervalRepository
import com.example.screentime.sync.SyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class ScreenTrackerService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val receiver = ScreenEventReceiver()
    private var registered = false

    private var heartbeatJob: Job? = null
    private val heartbeatIntervalMs = 15_000L

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startAsForeground()
        registerScreenReceiver()

        scope.launch {
            val interactive = TrackerState.isInteractiveAndUnlocked(applicationContext)
            IntervalRepository(applicationContext).ensureTrackingState(interactive)
            if (interactive) {
                startHeartbeat()
            } else {
                stopHeartbeat()
            }
            SyncWorker.enqueuePeriodic(applicationContext)
            SyncWorker.enqueueOneShot(applicationContext)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        scope.launch {
            val interactive = TrackerState.isInteractiveAndUnlocked(applicationContext)
            IntervalRepository(applicationContext).ensureTrackingState(interactive)
            if (interactive) {
                startHeartbeat()
            } else {
                stopHeartbeat()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopHeartbeat()
        if (registered) {
            unregisterReceiver(receiver)
            registered = false
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startHeartbeat() {
        if (heartbeatJob?.isActive == true) return

        heartbeatJob = scope.launch {
            val repo = IntervalRepository(applicationContext)
            while (isActive) {
                if (TrackerState.isInteractiveAndUnlocked(applicationContext)) {
                    repo.extendOpenInterval()
                }
                delay(heartbeatIntervalMs)
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    private fun registerScreenReceiver() {
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_USER_PRESENT)
        }
        ContextCompat.registerReceiver(
            this,
            receiver,
            filter,
            ContextCompat.RECEIVER_EXPORTED
        )
        registered = true
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                AppConfig.NOTIFICATION_CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.notification_channel_description)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, AppConfig.NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_recent_history)
            .setContentTitle(getString(R.string.tracking_notification_title))
            .setContentText(getString(R.string.tracking_notification_text))
            .setOngoing(true)
            .build()
    }

    private fun startAsForeground() {
        ServiceCompat.startForeground(
            this,
            AppConfig.NOTIFICATION_ID,
            buildNotification(),
            android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        )
    }
}