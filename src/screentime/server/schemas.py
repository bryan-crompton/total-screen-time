from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntervalIn(BaseModel):
    interval_id: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str = Field(min_length=1)
    is_open: bool
    updated_at: str = Field(min_length=1)


class BatchUpsertRequest(BaseModel):
    hostname: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    intervals: list[IntervalIn]


class IntervalResult(BaseModel):
    interval_id: str
    status: Literal["inserted", "updated", "ignored"]


class BatchUpsertResponse(BaseModel):
    results: list[IntervalResult]


class IntervalOut(BaseModel):
    interval_id: str
    host: str
    device_type: str
    start_time: str
    end_time: str
    is_open: bool
    updated_at: str
    received_at: str
    clipped_start_time: str
    clipped_end_time: str
    duration_seconds: int


class SummaryBucket(BaseModel):
    key: str
    seconds: int
    hours: float
    interval_count: int = 0


class DeviceSummary(BaseModel):
    host: str
    device_type: str
    seconds: int
    hours: float
    interval_count: int
    first_active_utc: str | None = None
    last_active_utc: str | None = None


class DaySummaryResponse(BaseModel):
    day: str
    timezone: str = "UTC"
    day_start_utc: str
    day_end_utc: str
    host_filter: str | None = None
    device_type_filter: str | None = None
    interval_count: int
    unique_total_seconds: int
    unique_total_hours: float
    summed_device_seconds: int
    summed_device_hours: float
    per_host: list[SummaryBucket]
    per_device_type: list[SummaryBucket]
    per_device: list[DeviceSummary]
    timeline_hosts: list[str]
    intervals: list[IntervalOut]
