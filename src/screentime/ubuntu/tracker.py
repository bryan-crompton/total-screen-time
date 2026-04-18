from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta

from screentime.ubuntu.schema import Interval, utc_now
from screentime.ubuntu.store import get_open_interval, upsert_interval


@dataclass
class TrackerConfig:
    host: str = socket.gethostname()
    device_type: str = "ubuntu"
    activity_threshold_s: int = 15
    poll_interval_s: int = 5
    gap_timeout_s: int = 30


def get_idle_seconds() -> float:
    try:
        out = subprocess.check_output(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Mutter.IdleMonitor",
                "--object-path",
                "/org/gnome/Mutter/IdleMonitor/Core",
                "--method",
                "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
            text=True,
        ).strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to query GNOME idle time via gdbus") from e

    # Expected output is typically like "(uint64 1234,)"
    idle_ms = int(out.split()[1].rstrip(",)"))
    return idle_ms / 1000.0


def is_active(activity_threshold_s: int) -> bool:
    return get_idle_seconds() <= activity_threshold_s


def get_last_input_time(now: datetime) -> datetime:
    return now - timedelta(seconds=get_idle_seconds())


def open_interval(conn, host: str, device_type: str, when: datetime) -> Interval:
    interval = Interval.new_open(host=host, device_type=device_type, when=when)
    upsert_interval(conn, interval)
    return interval


def extend_interval(conn, interval: Interval, new_end_time: datetime):
    if new_end_time < interval.end_time:
        return
    interval.end_time = new_end_time
    interval.updated_at = utc_now()
    interval.sync_status = "pending"
    upsert_interval(conn, interval)


def close_interval(conn, interval: Interval, close_time: datetime):
    if close_time < interval.start_time:
        close_time = interval.start_time
    if close_time < interval.end_time:
        close_time = interval.end_time

    interval.end_time = close_time
    interval.is_open = False
    interval.updated_at = utc_now()
    interval.sync_status = "pending"
    upsert_interval(conn, interval)


def close_stale_open_interval_on_startup(conn):
    interval = get_open_interval(conn)
    if interval is None:
        return

    # Conservative behavior: never assume continuity across downtime.
    interval.is_open = False
    interval.updated_at = utc_now()
    interval.sync_status = "pending"
    upsert_interval(conn, interval)
