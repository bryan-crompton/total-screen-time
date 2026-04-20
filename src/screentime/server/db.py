from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = os.environ.get(
    "SCREENTIME_SERVER_DB_PATH",
    str(Path.cwd() / "screentime-server.db"),
)

TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FMT)


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, TIME_FMT).replace(tzinfo=timezone.utc)


def to_utc_str(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(TIME_FMT)


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_intervals (
            interval_id TEXT PRIMARY KEY,
            host TEXT NOT NULL,
            device_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_open INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            received_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_intervals_host_start
        ON activity_intervals(host, start_time)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_intervals_updated_at
        ON activity_intervals(updated_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_intervals_start_end
        ON activity_intervals(start_time, end_time)
        """
    )
    conn.commit()


def init_db(db_path: str | None = None):
    conn = get_conn(db_path)
    try:
        create_tables(conn)
    finally:
        conn.close()


def upsert_interval(conn: sqlite3.Connection, host: str, device_type: str, interval) -> str:
    row = conn.execute(
        "SELECT updated_at FROM activity_intervals WHERE interval_id = ?",
        (interval.interval_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO activity_intervals (
                interval_id, host, device_type, start_time, end_time,
                is_open, updated_at, received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interval.interval_id,
                host,
                device_type,
                interval.start_time,
                interval.end_time,
                int(interval.is_open),
                interval.updated_at,
                utc_now_str(),
            ),
        )
        conn.commit()
        return "inserted"

    existing_updated_at = row["updated_at"]
    if interval.updated_at > existing_updated_at:
        conn.execute(
            """
            UPDATE activity_intervals
            SET host = ?,
                device_type = ?,
                start_time = ?,
                end_time = ?,
                is_open = ?,
                updated_at = ?,
                received_at = ?
            WHERE interval_id = ?
            """,
            (
                host,
                device_type,
                interval.start_time,
                interval.end_time,
                int(interval.is_open),
                interval.updated_at,
                utc_now_str(),
                interval.interval_id,
            ),
        )
        conn.commit()
        return "updated"

    return "ignored"


def get_intervals_overlapping(
    conn: sqlite3.Connection,
    start_time: str,
    end_time: str,
    host: str | None = None,
    device_type: str | None = None,
    limit: int = 50000,
) -> list[dict[str, Any]]:
    where_clauses = ["start_time < ?", "end_time > ?"]
    params: list[Any] = [end_time, start_time]

    if host:
        where_clauses.append("host = ?")
        params.append(host)
    if device_type:
        where_clauses.append("device_type = ?")
        params.append(device_type)

    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT interval_id, host, device_type, start_time, end_time, is_open, updated_at, received_at
        FROM activity_intervals
        WHERE {' AND '.join(where_clauses)}
        ORDER BY start_time ASC, end_time ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

    return [
        {
            "interval_id": row["interval_id"],
            "host": row["host"],
            "device_type": row["device_type"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "is_open": bool(row["is_open"]),
            "updated_at": row["updated_at"],
            "received_at": row["received_at"],
        }
        for row in rows
    ]


def _split_interval_by_day(start_dt: datetime, end_dt: datetime) -> list[tuple[str, int]]:
    parts: list[tuple[str, int]] = []
    cursor = start_dt
    while cursor < end_dt:
        day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        next_day = day_start + timedelta(days=1)
        segment_end = min(end_dt, next_day)
        seconds = int((segment_end - cursor).total_seconds())
        if seconds > 0:
            parts.append((cursor.date().isoformat(), seconds))
        cursor = segment_end
    return parts


def _merge_total_seconds(ranges: list[tuple[datetime, datetime]]) -> int:
    if not ranges:
        return 0
    ranges = sorted(ranges, key=lambda pair: (pair[0], pair[1]))
    merged_seconds = 0
    cur_start, cur_end = ranges[0]
    for start_dt, end_dt in ranges[1:]:
        if start_dt <= cur_end:
            if end_dt > cur_end:
                cur_end = end_dt
        else:
            merged_seconds += int((cur_end - cur_start).total_seconds())
            cur_start, cur_end = start_dt, end_dt
    merged_seconds += int((cur_end - cur_start).total_seconds())
    return merged_seconds


def summarize_intervals(
    intervals: list[dict[str, Any]],
    range_start: str,
    range_end: str,
) -> dict[str, Any]:
    query_start_dt = parse_utc(range_start)
    query_end_dt = parse_utc(range_end)

    per_device_seconds: dict[str, int] = defaultdict(int)
    per_host_seconds: dict[str, int] = defaultdict(int)
    per_device_day_seconds: dict[tuple[str, str], int] = defaultdict(int)
    all_ranges: list[tuple[datetime, datetime]] = []
    ranges_by_day: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)

    clipped_intervals: list[dict[str, Any]] = []

    for interval in intervals:
        start_dt = max(parse_utc(interval["start_time"]), query_start_dt)
        end_dt = min(parse_utc(interval["end_time"]), query_end_dt)
        if end_dt <= start_dt:
            continue

        seconds = int((end_dt - start_dt).total_seconds())
        per_device_seconds[interval["device_type"]] += seconds
        per_host_seconds[interval["host"]] += seconds
        all_ranges.append((start_dt, end_dt))

        for day_key, day_seconds in _split_interval_by_day(start_dt, end_dt):
            per_device_day_seconds[(day_key, interval["device_type"])] += day_seconds

        cursor = start_dt
        while cursor < end_dt:
            day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
            next_day = day_start + timedelta(days=1)
            segment_end = min(end_dt, next_day)
            if segment_end > cursor:
                ranges_by_day[cursor.date().isoformat()].append((cursor, segment_end))
            cursor = segment_end

        clipped_intervals.append(
            {
                **interval,
                "clipped_start_time": to_utc_str(start_dt),
                "clipped_end_time": to_utc_str(end_dt),
                "clipped_seconds": seconds,
            }
        )

    per_device = [
        {"device_type": device_type, "seconds": seconds}
        for device_type, seconds in sorted(per_device_seconds.items())
    ]
    per_host = [
        {"host": host, "seconds": seconds}
        for host, seconds in sorted(per_host_seconds.items())
    ]

    all_days = sorted(
        {
            *[day for day, _ in per_device_day_seconds.keys()],
            *ranges_by_day.keys(),
        }
    )

    per_day = []
    for day in all_days:
        unique_seconds = _merge_total_seconds(ranges_by_day.get(day, []))
        device_breakdown = [
            {"device_type": device_type, "seconds": seconds}
            for (day_key, device_type), seconds in sorted(per_device_day_seconds.items())
            if day_key == day
        ]
        per_day.append(
            {
                "day": day,
                "unique_seconds": unique_seconds,
                "devices": device_breakdown,
            }
        )

    return {
        "range_start": range_start,
        "range_end": range_end,
        "interval_count": len(clipped_intervals),
        "total_unique_seconds": _merge_total_seconds(all_ranges),
        "per_device": per_device,
        "per_host": per_host,
        "per_day": per_day,
        "intervals": clipped_intervals,
    }