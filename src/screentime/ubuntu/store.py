from __future__ import annotations

import sqlite3
from typing import Optional

from screentime.ubuntu.schema import Interval, dt_to_str, str_to_dt


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
            sync_status TEXT NOT NULL,
            last_synced_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_intervals_sync_status
        ON activity_intervals(sync_status)
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
        CREATE INDEX IF NOT EXISTS idx_activity_intervals_open
        ON activity_intervals(is_open)
        """
    )
    conn.commit()


def row_to_interval(row: sqlite3.Row) -> Interval:
    return Interval(
        interval_id=row["interval_id"],
        host=row["host"],
        device_type=row["device_type"],
        start_time=str_to_dt(row["start_time"]),
        end_time=str_to_dt(row["end_time"]),
        is_open=bool(row["is_open"]),
        updated_at=str_to_dt(row["updated_at"]),
        sync_status=row["sync_status"],
        last_synced_at=None if row["last_synced_at"] is None else str_to_dt(row["last_synced_at"]),
    )


def upsert_interval(conn: sqlite3.Connection, interval: Interval):
    conn.execute(
        """
        INSERT INTO activity_intervals (
            interval_id, host, device_type, start_time, end_time,
            is_open, updated_at, sync_status, last_synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(interval_id) DO UPDATE SET
            host = excluded.host,
            device_type = excluded.device_type,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            is_open = excluded.is_open,
            updated_at = excluded.updated_at,
            sync_status = excluded.sync_status,
            last_synced_at = excluded.last_synced_at
        """,
        (
            interval.interval_id,
            interval.host,
            interval.device_type,
            dt_to_str(interval.start_time),
            dt_to_str(interval.end_time),
            int(interval.is_open),
            dt_to_str(interval.updated_at),
            interval.sync_status,
            None if interval.last_synced_at is None else dt_to_str(interval.last_synced_at),
        ),
    )
    conn.commit()


def get_open_interval(conn: sqlite3.Connection) -> Optional[Interval]:
    row = conn.execute(
        """
        SELECT *
        FROM activity_intervals
        WHERE is_open = 1
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    return None if row is None else row_to_interval(row)


def get_pending_intervals(conn: sqlite3.Connection, limit: int = 100) -> list[Interval]:
    rows = conn.execute(
        """
        SELECT *
        FROM activity_intervals
        WHERE sync_status != 'synced'
        ORDER BY updated_at ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row_to_interval(row) for row in rows]


def mark_synced(conn: sqlite3.Connection, interval_id: str, synced_at):
    conn.execute(
        """
        UPDATE activity_intervals
        SET sync_status = 'synced',
            last_synced_at = ?
        WHERE interval_id = ?
        """,
        (dt_to_str(synced_at), interval_id),
    )
    conn.commit()


def mark_error(conn: sqlite3.Connection, interval_id: str):
    conn.execute(
        """
        UPDATE activity_intervals
        SET sync_status = 'error'
        WHERE interval_id = ?
        """,
        (interval_id,),
    )
    conn.commit()
