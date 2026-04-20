package com.example.screentime.data

import android.content.Context
import com.example.screentime.AppConfig
import com.example.screentime.util.DeviceInfo
import com.example.screentime.util.TimeUtils
import java.util.UUID
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class IntervalRepository(context: Context) {
    private val dao = AppDatabase.get(context).intervalDao()

    companion object {
        private val stateMutex = Mutex()
    }

    suspend fun openInterval(nowUtc: String = TimeUtils.nowUtcString()): IntervalEntity {
        val interval = IntervalEntity(
            intervalId = UUID.randomUUID().toString(),
            host = DeviceInfo.defaultDeviceLabel(),
            deviceType = AppConfig.DEVICE_TYPE,
            startTime = nowUtc,
            endTime = nowUtc,
            isOpen = true,
            updatedAt = nowUtc,
            syncStatus = "pending",
            lastSyncedAt = null
        )
        dao.upsert(interval)
        return interval
    }

    suspend fun extendOpenInterval(nowUtc: String = TimeUtils.nowUtcString()) {
        stateMutex.withLock {
            val openIntervals = dao.getAllOpenIntervals()
            if (openIntervals.isEmpty()) return

            val newest = openIntervals.first()

            // Close any extras if corruption already exists.
            for (interval in openIntervals.drop(1)) {
                val closed = interval.copy(
                    isOpen = false,
                    updatedAt = nowUtc,
                    syncStatus = "pending",
                    lastSyncedAt = interval.lastSyncedAt
                )
                dao.upsert(closed)
            }

            val updated = newest.copy(
                endTime = nowUtc,
                updatedAt = nowUtc,
                syncStatus = "pending",
                lastSyncedAt = newest.lastSyncedAt
            )
            dao.upsert(updated)
        }
    }

    suspend fun closeOpenInterval(nowUtc: String = TimeUtils.nowUtcString()) {
        stateMutex.withLock {
            val openIntervals = dao.getAllOpenIntervals()
            for (current in openIntervals) {
                val updated = current.copy(
                    endTime = nowUtc,
                    isOpen = false,
                    updatedAt = nowUtc,
                    syncStatus = "pending",
                    lastSyncedAt = current.lastSyncedAt
                )
                dao.upsert(updated)
            }
        }
    }

    suspend fun closeStaleOpenInterval() {
        stateMutex.withLock {
            val nowUtc = TimeUtils.nowUtcString()
            val openIntervals = dao.getAllOpenIntervals()
            for (current in openIntervals) {
                val updated = current.copy(
                    isOpen = false,
                    updatedAt = nowUtc,
                    syncStatus = "pending",
                    lastSyncedAt = current.lastSyncedAt
                )
                dao.upsert(updated)
            }
        }
    }

    suspend fun ensureTrackingState(isInteractiveAndUnlocked: Boolean) {
        stateMutex.withLock {
            val nowUtc = TimeUtils.nowUtcString()
            val openIntervals = dao.getAllOpenIntervals()

            if (isInteractiveAndUnlocked) {
                when {
                    openIntervals.isEmpty() -> {
                        openInterval(nowUtc)
                    }
                    else -> {
                        val newest = openIntervals.first()

                        // Heal duplicates by closing all but the newest.
                        for (interval in openIntervals.drop(1)) {
                            val closed = interval.copy(
                                isOpen = false,
                                updatedAt = nowUtc,
                                syncStatus = "pending",
                                lastSyncedAt = interval.lastSyncedAt
                            )
                            dao.upsert(closed)
                        }

                        val updated = newest.copy(
                            endTime = nowUtc,
                            updatedAt = nowUtc,
                            syncStatus = "pending",
                            lastSyncedAt = newest.lastSyncedAt
                        )
                        dao.upsert(updated)
                    }
                }
            } else {
                for (current in openIntervals) {
                    val updated = current.copy(
                        endTime = nowUtc,
                        isOpen = false,
                        updatedAt = nowUtc,
                        syncStatus = "pending",
                        lastSyncedAt = current.lastSyncedAt
                    )
                    dao.upsert(updated)
                }
            }
        }
    }

    suspend fun getPendingIntervals(limit: Int = 100): List<IntervalEntity> =
        dao.getPendingIntervals(limit)

    suspend fun markSynced(intervalId: String, syncedAt: String) =
        dao.markSynced(intervalId, syncedAt)

    suspend fun markError(intervalId: String) =
        dao.markError(intervalId)

    suspend fun getPendingCount(): Int =
        dao.getPendingCount()

    suspend fun getOpenInterval(): IntervalEntity? =
        dao.getOpenInterval()

    suspend fun getLatestSuccessfulSync(): String? =
        dao.getLatestSuccessfulSync()
}