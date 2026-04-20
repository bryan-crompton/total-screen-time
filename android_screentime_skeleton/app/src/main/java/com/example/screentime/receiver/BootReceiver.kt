package com.example.screentime.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.example.screentime.data.IntervalRepository
import com.example.screentime.sync.SyncWorker
import com.example.screentime.tracker.ScreenTrackerService
import kotlinx.coroutines.runBlocking

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        val appContext = context.applicationContext

        // Close any stale open interval synchronously before starting tracking again.
        runBlocking {
            IntervalRepository(appContext).closeStaleOpenInterval()
            SyncWorker.enqueuePeriodic(appContext)
            SyncWorker.enqueueOneShot(appContext)
        }

        val serviceIntent = Intent(appContext, ScreenTrackerService::class.java)
        ContextCompat.startForegroundService(appContext, serviceIntent)
    }
}