package com.example.screentime.sync

import com.example.screentime.AppConfig
import com.example.screentime.data.IntervalEntity
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class SyncClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    fun syncIntervals(intervals: List<IntervalEntity>): List<Pair<String, String>> {
        if (intervals.isEmpty()) return emptyList()

        val first = intervals.first()
        val payload = JSONObject().apply {
            put("hostname", first.host)
            put("device_type", first.deviceType)
            put(
                "intervals",
                JSONArray().apply {
                    intervals.forEach { interval ->
                        put(
                            JSONObject().apply {
                                put("interval_id", interval.intervalId)
                                put("start_time", interval.startTime)
                                put("end_time", interval.endTime)
                                put("is_open", interval.isOpen)
                                put("updated_at", interval.updatedAt)
                            }
                        )
                    }
                }
            )
        }

        val request = Request.Builder()
            .url("${AppConfig.SERVER_URL}/intervals/batch_upsert")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                error("Sync failed: HTTP ${response.code}")
            }
            val bodyText = response.body?.string().orEmpty()
            val body = JSONObject(bodyText)
            val results = body.getJSONArray("results")
            return buildList {
                for (i in 0 until results.length()) {
                    val obj = results.getJSONObject(i)
                    add(obj.getString("interval_id") to obj.getString("status"))
                }
            }
        }
    }
}
