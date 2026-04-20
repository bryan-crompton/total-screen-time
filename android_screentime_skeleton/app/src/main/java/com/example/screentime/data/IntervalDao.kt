package com.example.screentime.data

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface IntervalDao {
    @Upsert
    suspend fun upsert(interval: IntervalEntity)

    @Query("""
        SELECT * FROM activity_intervals
        WHERE isOpen = 1
        ORDER BY updatedAt DESC
        LIMIT 1
    """)
    suspend fun getOpenInterval(): IntervalEntity?

    @Query("""
        SELECT * FROM activity_intervals
        WHERE isOpen = 1
        ORDER BY updatedAt DESC
    """)
    suspend fun getAllOpenIntervals(): List<IntervalEntity>

    @Query("""
        SELECT * FROM activity_intervals
        WHERE syncStatus != 'synced'
        ORDER BY updatedAt ASC
        LIMIT :limit
    """)
    suspend fun getPendingIntervals(limit: Int = 100): List<IntervalEntity>

    @Query("""
        UPDATE activity_intervals
        SET syncStatus = 'synced',
            lastSyncedAt = :syncedAt
        WHERE intervalId = :intervalId
    """)
    suspend fun markSynced(intervalId: String, syncedAt: String)

    @Query("""
        UPDATE activity_intervals
        SET syncStatus = 'error'
        WHERE intervalId = :intervalId
    """)
    suspend fun markError(intervalId: String)

    @Query("""
        SELECT COUNT(*)
        FROM activity_intervals
        WHERE syncStatus != 'synced'
    """)
    suspend fun getPendingCount(): Int

    @Query("""
        SELECT lastSyncedAt
        FROM activity_intervals
        WHERE lastSyncedAt IS NOT NULL
        ORDER BY lastSyncedAt DESC
        LIMIT 1
    """)
    suspend fun getLatestSuccessfulSync(): String?
}