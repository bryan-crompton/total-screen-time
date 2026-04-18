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
