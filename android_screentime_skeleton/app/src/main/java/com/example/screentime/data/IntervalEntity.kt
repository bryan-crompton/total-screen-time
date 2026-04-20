package com.example.screentime.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "activity_intervals")
data class IntervalEntity(
    @PrimaryKey val intervalId: String,
    val host: String,
    val deviceType: String,
    val startTime: String,
    val endTime: String,
    val isOpen: Boolean,
    val updatedAt: String,
    val syncStatus: String,
    val lastSyncedAt: String?
)
