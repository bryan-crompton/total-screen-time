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


class IntervalRecord(BaseModel):
    interval_id: str
    host: str
    device_type: str
    start_time: str
    end_time: str
    is_open: bool
    updated_at: str
    received_at: str
    clipped_start_time: str | None = None
    clipped_end_time: str | None = None
    clipped_seconds: int | None = None


class DeviceTotal(BaseModel):
    device_type: str
    seconds: int


class HostTotal(BaseModel):
    host: str
    seconds: int


class DaySummary(BaseModel):
    day: str
    unique_seconds: int
    devices: list[DeviceTotal]


class IntervalQueryResponse(BaseModel):
    range_start: str
    range_end: str
    interval_count: int
    intervals: list[IntervalRecord]


class IntervalSummaryResponse(BaseModel):
    range_start: str
    range_end: str
    interval_count: int
    total_unique_seconds: int
    per_device: list[DeviceTotal]
    per_host: list[HostTotal]
    per_day: list[DaySummary]
    intervals: list[IntervalRecord]