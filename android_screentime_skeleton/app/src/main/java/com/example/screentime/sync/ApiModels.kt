package com.example.screentime.sync

data class IntervalPayload(
    val interval_id: String,
    val start_time: String,
    val end_time: String,
    val is_open: Boolean,
    val updated_at: String
)

data class BatchUpsertPayload(
    val hostname: String,
    val device_type: String,
    val intervals: List<IntervalPayload>
)
