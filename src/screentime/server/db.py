from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = os.environ.get(
    "SCREENTIME_SERVER_DB_PATH",
    str(Path.cwd() / "screentime-server.db"),
)


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
