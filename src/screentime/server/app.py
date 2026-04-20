from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from screentime.server.db import (
    DEFAULT_DB_PATH,
    get_conn,
    get_intervals_overlapping,
    init_db,
    summarize_intervals,
)
from screentime.server.schemas import (
    BatchUpsertRequest,
    BatchUpsertResponse,
    IntervalQueryResponse,
    IntervalResult,
    IntervalSummaryResponse,
)
from screentime.server.db import upsert_interval

init_db()

app = FastAPI(title="screentime-server")


DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Screen Time Dashboard</title>
  <style>
    body { font-family: sans-serif; margin: 24px; max-width: 1200px; }
    h1, h2 { margin-bottom: 8px; }
    .controls { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .controls label { display: flex; flex-direction: column; font-size: 14px; gap: 4px; }
    input, button { padding: 8px; font-size: 14px; }
    .cards { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 12px; margin: 16px 0 24px; }
    .card, .panel { border: 1px solid #ddd; border-radius: 10px; padding: 14px; background: #fff; }
    .metric { font-size: 28px; font-weight: 700; }
    .muted { color: #666; font-size: 13px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    table { border-collapse: collapse; width: 100%; font-size: 14px; }
    th, td { border-bottom: 1px solid #eee; padding: 8px; text-align: left; }
    .chart-wrap { overflow-x: auto; }
    svg text { font-size: 12px; fill: #333; }
    .error { color: #b00020; margin-top: 12px; }
    @media (max-width: 900px) {
      .controls, .cards, .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <h1>Screen Time Dashboard</h1>
  <div class="controls">
    <label>Start date<input id="startDate" type="date" /></label>
    <label>End date<input id="endDate" type="date" /></label>
    <label>Host filter<input id="host" type="text" placeholder="optional" /></label>
    <label>Device filter<input id="device" type="text" placeholder="optional" /></label>
    <label style="justify-content:flex-end;"><span>&nbsp;</span><button id="loadBtn">Load</button></label>
  </div>

  <div class="cards">
    <div class="card"><div class="muted">Unique total</div><div id="uniqueTotal" class="metric">-</div></div>
    <div class="card"><div class="muted">Intervals</div><div id="intervalCount" class="metric">-</div></div>
    <div class="card"><div class="muted">Days in range</div><div id="dayCount" class="metric">-</div></div>
    <div class="card"><div class="muted">Database path</div><div class="metric" style="font-size:14px; word-break:break-all;">__DB_PATH__</div></div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>Daily unique total</h2>
      <div id="dailyChart" class="chart-wrap"></div>
    </div>
    <div class="panel">
      <h2>Per-device total</h2>
      <div id="deviceChart" class="chart-wrap"></div>
    </div>
  </div>

  <div class="grid" style="margin-top:16px;">
    <div class="panel">
      <h2>Per-device totals</h2>
      <table id="deviceTable"><thead><tr><th>Device</th><th>Hours</th></tr></thead><tbody></tbody></table>
    </div>
    <div class="panel">
      <h2>Per-day breakdown</h2>
      <table id="dayTable"><thead><tr><th>Day</th><th>Unique hours</th><th>By device</th></tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div id="error" class="error"></div>

<script>
function hoursLabel(seconds) {
  return (seconds / 3600).toFixed(2);
}

function makeBarChart(items, labelKey, valueKey, width = 700, height = 260) {
  if (!items.length) return '<div class="muted">No data</div>';
  const padding = { top: 20, right: 20, bottom: 70, left: 60 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const maxValue = Math.max(...items.map(x => x[valueKey]), 1);
  const barWidth = innerW / items.length;
  let bars = '';
  let labels = '';
  let yTicks = '';

  for (let i = 0; i < 5; i++) {
    const frac = i / 4;
    const y = padding.top + innerH - frac * innerH;
    const value = maxValue * frac;
    yTicks += `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="#eee" />`;
    yTicks += `<text x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${hoursLabel(value)}</text>`;
  }

  items.forEach((item, idx) => {
    const v = item[valueKey];
    const h = (v / maxValue) * innerH;
    const x = padding.left + idx * barWidth + 8;
    const y = padding.top + innerH - h;
    const w = Math.max(8, barWidth - 16);
    bars += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#4f46e5" rx="4" />`;
    bars += `<text x="${x + w/2}" y="${y - 6}" text-anchor="middle">${hoursLabel(v)}</text>`;
    labels += `<text x="${x + w/2}" y="${height - 18}" text-anchor="end" transform="rotate(-35 ${x + w/2} ${height - 18})">${item[labelKey]}</text>`;
  });

  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${yTicks}${bars}${labels}</svg>`;
}

async function loadData() {
  const errorEl = document.getElementById('error');
  errorEl.textContent = '';
  const startDate = document.getElementById('startDate').value;
  const endDate = document.getElementById('endDate').value;
  const host = document.getElementById('host').value.trim();
  const device = document.getElementById('device').value.trim();

  const start = `${startDate}T00:00:00Z`;
  const endDateObj = new Date(`${endDate}T00:00:00Z`);
  endDateObj.setUTCDate(endDateObj.getUTCDate() + 1);
  const end = endDateObj.toISOString().slice(0, 19) + 'Z';

  const params = new URLSearchParams({ start, end });
  if (host) params.set('host', host);
  if (device) params.set('device_type', device);

  try {
    const resp = await fetch(`/api/summary?${params.toString()}`);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    document.getElementById('uniqueTotal').textContent = `${hoursLabel(data.total_unique_seconds)} h`;
    document.getElementById('intervalCount').textContent = data.interval_count;
    document.getElementById('dayCount').textContent = data.per_day.length;

    document.getElementById('dailyChart').innerHTML = makeBarChart(
      data.per_day.map(d => ({ label: d.day, value: d.unique_seconds })),
      'label',
      'value'
    );
    document.getElementById('deviceChart').innerHTML = makeBarChart(
      data.per_device.map(d => ({ label: d.device_type, value: d.seconds })),
      'label',
      'value',
      500,
      260
    );

    const deviceBody = document.querySelector('#deviceTable tbody');
    deviceBody.innerHTML = data.per_device
      .map(d => `<tr><td>${d.device_type}</td><td>${hoursLabel(d.seconds)}</td></tr>`)
      .join('');

    const dayBody = document.querySelector('#dayTable tbody');
    dayBody.innerHTML = data.per_day
      .map(d => {
        const deviceBits = d.devices.map(x => `${x.device_type}: ${hoursLabel(x.seconds)}h`).join(', ');
        return `<tr><td>${d.day}</td><td>${hoursLabel(d.unique_seconds)}</td><td>${deviceBits}</td></tr>`;
      })
      .join('');
  } catch (err) {
    errorEl.textContent = String(err);
  }
}

(function init() {
  const end = new Date();
  const start = new Date();
  start.setUTCDate(end.getUTCDate() - 6);
  document.getElementById('startDate').value = start.toISOString().slice(0, 10);
  document.getElementById('endDate').value = end.toISOString().slice(0, 10);
  document.getElementById('loadBtn').addEventListener('click', loadData);
  loadData();
})();
</script>
</body>
</html>
"""


def _parse_range_or_400(start: str, end: str) -> tuple[str, str]:
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="start and end must be UTC timestamps like 2026-04-20T00:00:00Z") from exc

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end must be after start")

    return start, end


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML.replace("__DB_PATH__", DEFAULT_DB_PATH))


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


@app.get("/api/intervals", response_model=IntervalQueryResponse)
def api_intervals(
    start: str = Query(..., description="UTC timestamp inclusive, e.g. 2026-04-01T00:00:00Z"),
    end: str = Query(..., description="UTC timestamp exclusive, e.g. 2026-04-08T00:00:00Z"),
    host: str | None = Query(None),
    device_type: str | None = Query(None),
    limit: int = Query(50000, ge=1, le=200000),
) -> IntervalQueryResponse:
    start, end = _parse_range_or_400(start, end)
    conn = get_conn()
    try:
        intervals = get_intervals_overlapping(conn, start, end, host=host, device_type=device_type, limit=limit)
        return IntervalQueryResponse(
            range_start=start,
            range_end=end,
            interval_count=len(intervals),
            intervals=intervals,
        )
    finally:
        conn.close()


@app.get("/api/summary", response_model=IntervalSummaryResponse)
def api_summary(
    start: str = Query(..., description="UTC timestamp inclusive, e.g. 2026-04-01T00:00:00Z"),
    end: str = Query(..., description="UTC timestamp exclusive, e.g. 2026-04-08T00:00:00Z"),
    host: str | None = Query(None),
    device_type: str | None = Query(None),
    limit: int = Query(50000, ge=1, le=200000),
) -> IntervalSummaryResponse:
    start, end = _parse_range_or_400(start, end)
    conn = get_conn()
    try:
        intervals = get_intervals_overlapping(conn, start, end, host=host, device_type=device_type, limit=limit)
        return IntervalSummaryResponse(**summarize_intervals(intervals, start, end))
    finally:
        conn.close()


@app.get("/api/default_range")
def api_default_range() -> dict[str, str]:
    today = datetime.now(timezone.utc).date()
    start_dt = datetime.combine(today - timedelta(days=6), time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return {
        "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run():
    host = os.environ.get("SCREENTIME_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SCREENTIME_SERVER_PORT", "7777"))
    uvicorn.run("screentime.server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()