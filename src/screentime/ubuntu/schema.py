from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid

TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_str(dt: datetime) -> str:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(timezone.utc).strftime(TIME_FMT)


def str_to_dt(s: str) -> datetime:
    return datetime.strptime(s, TIME_FMT).replace(tzinfo=timezone.utc)


@dataclass
class Interval:
    interval_id: str
    host: str
    device_type: str
    start_time: datetime
    end_time: datetime
    is_open: bool
    updated_at: datetime
    sync_status: str
    last_synced_at: Optional[datetime] = None

    @classmethod
    def new_open(cls, host: str, device_type: str, when: datetime) -> "Interval":
        return cls(
            interval_id=str(uuid.uuid4()),
            host=host,
            device_type=device_type,
            start_time=when,
            end_time=when,
            is_open=True,
            updated_at=when,
            sync_status="pending",
            last_synced_at=None,
        )

    def to_sync_payload(self) -> dict:
        return {
            "interval_id": self.interval_id,
            "start_time": dt_to_str(self.start_time),
            "end_time": dt_to_str(self.end_time),
            "is_open": self.is_open,
            "updated_at": dt_to_str(self.updated_at),
        }
