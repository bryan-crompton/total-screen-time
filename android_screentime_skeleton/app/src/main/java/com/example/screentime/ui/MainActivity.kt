package com.example.screentime.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.example.screentime.AppConfig
import com.example.screentime.data.IntervalRepository
import com.example.screentime.databinding.ActivityMainBinding
import com.example.screentime.sync.SyncWorker
import com.example.screentime.tracker.ScreenTrackerService
import com.example.screentime.util.DeviceInfo
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var repository: IntervalRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        repository = IntervalRepository(applicationContext)

        maybeRequestNotificationPermission()
        startTrackingService()
        SyncWorker.enqueuePeriodic(applicationContext)

        binding.serverUrlText.text = "Server URL: ${AppConfig.SERVER_URL}"
        binding.deviceLabelText.text = "Device label: ${DeviceInfo.defaultDeviceLabel()}"

        binding.startServiceButton.setOnClickListener {
            startTrackingService()
            refreshUi()
        }

        binding.stopServiceButton.setOnClickListener {
            stopService(Intent(this, ScreenTrackerService::class.java))
            refreshUi()
        }

        binding.syncNowButton.setOnClickListener {
            SyncWorker.enqueueOneShot(applicationContext)
            refreshUi()
        }
    }

    override fun onResume() {
        super.onResume()
        refreshUi()
    }

    private fun refreshUi() {
        lifecycleScope.launch {
            val pending = repository.getPendingCount()
            val open = repository.getOpenInterval()
            val lastSync = repository.getLatestSuccessfulSync()

            binding.pendingCountText.text = "Pending intervals: $pending"
            binding.openIntervalText.text = if (open == null) {
                "Open interval: none"
            } else {
                "Open interval: ${open.startTime} → ${open.endTime}"
            }
            binding.lastSyncText.text = "Last sync result: ${lastSync ?: "none yet"}"
            binding.serviceStatusText.text = "Tracker service: started by app/boot receiver"
        }
    }

    private fun startTrackingService() {
        val intent = Intent(this, ScreenTrackerService::class.java)
        ContextCompat.startForegroundService(this, intent)
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                    1001
                )
            }
        }
    }
}
