from __future__ import annotations

import fcntl
import os
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from screentime.ubuntu.schema import utc_now
from screentime.ubuntu.store import create_tables, get_conn, get_open_interval
from screentime.ubuntu.sync import sync_loop
from screentime.ubuntu.tracker import (
    TrackerConfig,
    close_interval,
    close_stale_open_interval_on_startup,
    extend_interval,
    get_last_input_time,
    is_active,
    open_interval,
)


@dataclass
class Config:
    db_path: str = os.environ.get(
        "SCREENTIME_DB_PATH",
        os.path.expanduser("~/.local/share/screentime/screentime.db"),
    )
    server_url: str = os.environ.get(
        "SCREENTIME_SERVER_URL",
        "http://127.0.0.1:8000",
    )
    host: str = os.environ.get("SCREENTIME_HOST", socket.gethostname())
    device_type: str = "ubuntu"
    activity_threshold_s: int = int(os.environ.get("SCREENTIME_ACTIVITY_THRESHOLD", "15"))
    poll_interval_s: int = int(os.environ.get("SCREENTIME_POLL_INTERVAL", "5"))
    gap_timeout_s: int = int(os.environ.get("SCREENTIME_GAP_TIMEOUT", "30"))
    sync_interval_s: int = int(os.environ.get("SCREENTIME_SYNC_INTERVAL", "30"))
    lock_path: str = os.environ.get(
        "SCREENTIME_LOCK_PATH",
        os.path.expanduser("~/.local/share/screentime/screentime.lock"),
    )


def acquire_lock(lock_path: str):
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another screentime monitor instance is already running", file=sys.stderr)
        sys.exit(1)
    return fd


def run_tracker(conn, cfg: Config):
    tracker_cfg = TrackerConfig(
        host=cfg.host,
        device_type=cfg.device_type,
        activity_threshold_s=cfg.activity_threshold_s,
        poll_interval_s=cfg.poll_interval_s,
        gap_timeout_s=cfg.gap_timeout_s,
    )

    current_interval = get_open_interval(conn)
    prev_loop_time = utc_now()

    while True:
        time.sleep(tracker_cfg.poll_interval_s)
        now = utc_now()
        elapsed_s = (now - prev_loop_time).total_seconds()

        if elapsed_s > tracker_cfg.gap_timeout_s:
            if current_interval is not None:
                close_interval(conn, current_interval, current_interval.end_time)
                current_interval = None
            prev_loop_time = now
            continue

        active = is_active(tracker_cfg.activity_threshold_s)

        if active:
            last_input_time = get_last_input_time(now)
            active_bound = now

            if current_interval is None:
                current_interval = open_interval(
                    conn=conn,
                    host=tracker_cfg.host,
                    device_type=tracker_cfg.device_type,
                    when=last_input_time,
                )
            else:
                extend_interval(conn, current_interval, active_bound)

        else:
            if current_interval is not None:
                last_input_time = get_last_input_time(now)
                close_time = last_input_time
                if close_time > now:
                    close_time = now
                close_interval(conn, current_interval, close_time)
                current_interval = None

        prev_loop_time = now


def main():
    cfg = Config()
    _lock_fd = acquire_lock(cfg.lock_path)

    Path(cfg.db_path).parent.mkdir(parents=True, exist_ok=True)

    tracking_conn = get_conn(cfg.db_path)
    create_tables(tracking_conn)
    close_stale_open_interval_on_startup(tracking_conn)

    sync_thread = threading.Thread(
        target=sync_loop,
        args=(cfg.db_path, cfg.server_url, cfg.sync_interval_s),
        daemon=True,
        name="screentime-sync",
    )
    sync_thread.start()

    run_tracker(tracking_conn, cfg)


if __name__ == "__main__":
    main()
