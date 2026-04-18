from __future__ import annotations

import time
import requests

from screentime.ubuntu.schema import utc_now
from screentime.ubuntu.store import get_conn, get_pending_intervals, mark_error, mark_synced


def sync_once(conn, server_url: str):
    pending = get_pending_intervals(conn, limit=100)
    if not pending:
        return 0

    first = pending[0]
    payload = {
        "hostname": first.host,
        "device_type": first.device_type,
        "intervals": [interval.to_sync_payload() for interval in pending],
    }

    resp = requests.post(
        f"{server_url.rstrip('/')}/intervals/batch_upsert",
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json()

    synced_at = utc_now()
    by_id = {interval.interval_id for interval in pending}
    touched = 0

    for result in body["results"]:
        interval_id = result["interval_id"]
        status = result["status"]
        if interval_id not in by_id:
            continue
        if status in {"inserted", "updated", "ignored"}:
            mark_synced(conn, interval_id, synced_at)
        else:
            mark_error(conn, interval_id)
        touched += 1

    return touched


def sync_loop(db_path: str, server_url: str, sync_interval_s: int = 30):
    conn = get_conn(db_path)
    while True:
        try:
            sync_once(conn, server_url)
        except Exception as e:
            print(f"sync failed: {e}")
        time.sleep(sync_interval_s)
