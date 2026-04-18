from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from screentime.server.db import DEFAULT_DB_PATH, get_conn, init_db, upsert_interval
from screentime.server.schemas import BatchUpsertRequest, BatchUpsertResponse, IntervalResult

init_db()

app = FastAPI(title="screentime-server")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/intervals/batch_upsert", response_model=BatchUpsertResponse)
def batch_upsert(req: BatchUpsertRequest) -> BatchUpsertResponse:
    conn = get_conn()
    try:
        results = []
        for interval in req.intervals:
            status = upsert_interval(conn, req.hostname, req.device_type, interval)
            results.append(IntervalResult(interval_id=interval.interval_id, status=status))
        return BatchUpsertResponse(results=results)
    finally:
        conn.close()


def run():
    host = os.environ.get("SCREENTIME_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SCREENTIME_SERVER_PORT", "8000"))
    uvicorn.run("screentime.server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
