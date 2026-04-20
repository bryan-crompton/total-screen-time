package com.example.screentime.tracker

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.example.screentime.data.IntervalRepository
import com.example.screentime.sync.SyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class ScreenEventReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val appContext = context.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            val repository = IntervalRepository(appContext)
            when (intent.action) {
                Intent.ACTION_SCREEN_OFF -> repository.closeOpenInterval()
                Intent.ACTION_SCREEN_ON,
                Intent.ACTION_USER_PRESENT -> repository.ensureTrackingState(
                    TrackerState.isInteractiveAndUnlocked(appContext)
                )
            }
            SyncWorker.enqueueOneShot(appContext)
        }
    }
}
