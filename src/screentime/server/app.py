from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from screentime.server.db import (
    fetch_intervals_for_day,
    format_utc,
    get_conn,
    init_db,
    parse_utc,
)
from screentime.server.schemas import (
    BatchUpsertRequest,
    BatchUpsertResponse,
    DaySummaryResponse,
    DeviceSummary,
    IntervalOut,
    IntervalResult,
    SummaryBucket,
)

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
            from screentime.server.db import upsert_interval

            status = upsert_interval(conn, req.hostname, req.device_type, interval)
            results.append(IntervalResult(interval_id=interval.interval_id, status=status))
        return BatchUpsertResponse(results=results)
    finally:
        conn.close()


def clip_segments(rows, day_start, day_end):
    intervals: list[IntervalOut] = []
    merged_segments: list[tuple[datetime, datetime]] = []
    per_host_seconds: dict[str, int] = defaultdict(int)
    per_host_count: dict[str, int] = defaultdict(int)
    per_type_seconds: dict[str, int] = defaultdict(int)
    per_type_count: dict[str, int] = defaultdict(int)
    per_device_seconds: dict[tuple[str, str], int] = defaultdict(int)
    per_device_count: dict[tuple[str, str], int] = defaultdict(int)
    per_device_first: dict[tuple[str, str], datetime] = {}
    per_device_last: dict[tuple[str, str], datetime] = {}
    timeline_hosts: set[str] = set()

    for row in rows:
        start = max(parse_utc(row["start_time"]), day_start)
        end = min(parse_utc(row["end_time"]), day_end)
        if end <= start:
            continue

        seconds = int((end - start).total_seconds())
        host = row["host"]
        device_type = row["device_type"]
        key = (host, device_type)
        timeline_hosts.add(host)

        intervals.append(
            IntervalOut(
                interval_id=row["interval_id"],
                host=host,
                device_type=device_type,
                start_time=row["start_time"],
                end_time=row["end_time"],
                is_open=bool(row["is_open"]),
                updated_at=row["updated_at"],
                received_at=row["received_at"],
                clipped_start_time=format_utc(start),
                clipped_end_time=format_utc(end),
                duration_seconds=seconds,
            )
        )

        per_host_seconds[host] += seconds
        per_host_count[host] += 1
        per_type_seconds[device_type] += seconds
        per_type_count[device_type] += 1
        per_device_seconds[key] += seconds
        per_device_count[key] += 1
        per_device_first[key] = min(start, per_device_first.get(key, start))
        per_device_last[key] = max(end, per_device_last.get(key, end))

        if not merged_segments or start > merged_segments[-1][1]:
            merged_segments.append((start, end))
        else:
            merged_segments[-1] = (merged_segments[-1][0], max(merged_segments[-1][1], end))

    unique_total_seconds = sum(int((end - start).total_seconds()) for start, end in merged_segments)
    summed_device_seconds = sum(per_device_seconds.values())

    per_host = [
        SummaryBucket(
            key=host,
            seconds=seconds,
            hours=round(seconds / 3600, 4),
            interval_count=per_host_count[host],
        )
        for host, seconds in sorted(per_host_seconds.items(), key=lambda item: (-item[1], item[0]))
    ]
    per_device_type = [
        SummaryBucket(
            key=device_type,
            seconds=seconds,
            hours=round(seconds / 3600, 4),
            interval_count=per_type_count[device_type],
        )
        for device_type, seconds in sorted(per_type_seconds.items(), key=lambda item: (-item[1], item[0]))
    ]
    per_device = [
        DeviceSummary(
            host=host,
            device_type=device_type,
            seconds=seconds,
            hours=round(seconds / 3600, 4),
            interval_count=per_device_count[(host, device_type)],
            first_active_utc=format_utc(per_device_first[(host, device_type)]),
            last_active_utc=format_utc(per_device_last[(host, device_type)]),
        )
        for (host, device_type), seconds in sorted(
            per_device_seconds.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]

    intervals.sort(key=lambda interval: (interval.clipped_start_time, interval.clipped_end_time, interval.host))
    return (
        intervals,
        unique_total_seconds,
        summed_device_seconds,
        per_host,
        per_device_type,
        per_device,
        sorted(timeline_hosts),
    )


@app.get("/api/day", response_model=DaySummaryResponse)
def day_summary(
    day: str = Query(..., description="Local day in YYYY-MM-DD format"),
    host: str | None = Query(None),
    device_type: str | None = Query(None),
    timezone: str = Query("UTC", description="IANA timezone, e.g. America/New_York"),
) -> DaySummaryResponse:
    conn = get_conn()
    try:
        day_start, day_end, rows = fetch_intervals_for_day(
            conn,
            day,
            host=host,
            device_type=device_type,
            timezone_name=timezone,
        )
    finally:
        conn.close()

    intervals, unique_total_seconds, summed_device_seconds, per_host, per_device_type, per_device, timeline_hosts = clip_segments(
        rows, day_start, day_end
    )

    return DaySummaryResponse(
        day=day,
        timezone=timezone,
        day_start_utc=format_utc(day_start),
        day_end_utc=format_utc(day_end),
        host_filter=host,
        device_type_filter=device_type,
        interval_count=len(intervals),
        unique_total_seconds=unique_total_seconds,
        unique_total_hours=round(unique_total_seconds / 3600, 4),
        summed_device_seconds=summed_device_seconds,
        summed_device_hours=round(summed_device_seconds / 3600, 4),
        per_host=per_host,
        per_device_type=per_device_type,
        per_device=per_device,
        timeline_hosts=timeline_hosts,
        intervals=intervals,
    )


HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Screen Time Dashboard</title>
  <style>
    :root {
      --bg: #f6f7fb;
      --panel: #ffffff;
      --line: #d8ddea;
      --text: #182033;
      --muted: #667085;
      --accent: #4f46e5;
      --timeline-bg: #f8faff;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, system-ui, sans-serif; background: var(--bg); color: var(--text); }
    .wrap { max-width: 1500px; margin: 0 auto; padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 16px; }
    .title { font-size: 20px; font-weight: 700; }
    .muted { color: var(--muted); }
    .controls { display: grid; grid-template-columns: minmax(320px, 420px) 240px 240px 140px; gap: 16px; margin-bottom: 16px; }
    .card {
      background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 16px;
      box-shadow: 0 1px 2px rgba(16,24,40,.04);
    }
    label { display: block; font-size: 13px; margin-bottom: 6px; color: var(--muted); }
    input, select, button {
      width: 100%; border: 1px solid var(--line); background: white; border-radius: 10px; min-height: 42px;
      padding: 10px 12px; font: inherit;
    }
    button { background: var(--accent); color: white; border: 0; font-weight: 600; cursor: pointer; }
    .day-nav { display: grid; grid-template-columns: 46px 1fr 46px; gap: 10px; align-items: center; }
    .nav-btn {
      min-height: 42px; padding: 0; font-size: 22px; line-height: 1; display: flex; align-items: center; justify-content: center;
    }
    .nav-btn:disabled { opacity: 0.5; cursor: default; }
    .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
    .stat-value { font-size: 34px; font-weight: 800; margin: 8px 0 4px; }
    .two-col { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
    .three-col { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
    .bottom { display: grid; grid-template-columns: 1.1fr 1.4fr; gap: 16px; }
    .section-title { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
    .section-sub { font-size: 13px; color: var(--muted); margin-bottom: 12px; }

    .bars { display: grid; gap: 10px; }
    .bar-row { display: grid; grid-template-columns: 180px 1fr 72px; gap: 10px; align-items: center; }
    .bar-label { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .bar-track { height: 24px; background: #eef2ff; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; }
    .bar-value { font-size: 13px; text-align: right; color: var(--muted); }
    .bar-dot {
      display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 8px; vertical-align: middle;
      border: 1px solid rgba(24,32,51,.12);
    }

    .timeline { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
    .timeline-header, .timeline-row { display: grid; grid-template-columns: 180px 1fr; }
    .timeline-header { background: #fafbff; border-bottom: 1px solid var(--line); }
    .timeline-host, .timeline-hours { padding: 10px 12px; }
    .timeline-hours { position: relative; height: 44px; }
    .timeline-scale { display: flex; height: 100%; }
    .tick { flex: 1; position: relative; border-left: 1px solid var(--line); }
    .tick span { position: absolute; top: 2px; left: 6px; font-size: 12px; color: var(--muted); }
    .timeline-row { border-bottom: 1px solid var(--line); }
    .timeline-row:last-child { border-bottom: 0; }
    .timeline-host { font-size: 14px; font-weight: 600; display: flex; flex-direction: column; justify-content: center; gap: 3px; }
    .timeline-host small { color: var(--muted); font-weight: 500; }
    .timeline-track {
      position: relative; height: 42px; margin: 7px 12px; border-radius: 8px; background: var(--timeline-bg); overflow: hidden;
      background-image: linear-gradient(to right, transparent 0%, transparent calc(12.5% - 1px), var(--line) calc(12.5% - 1px), var(--line) 12.5%, transparent 12.5%);
      background-size: 12.5% 100%;
    }
    .segment {
      position: absolute; top: 8px; height: 26px; border-radius: 6px; border: 1px solid rgba(24,32,51,.10);
      box-shadow: inset 0 -1px 0 rgba(255,255,255,.18);
    }
    .host-chip { display: inline-flex; align-items: center; gap: 8px; }
    .host-swatch {
      width: 10px; height: 10px; border-radius: 999px; border: 1px solid rgba(24,32,51,.12); flex: 0 0 auto;
    }

    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    tr:last-child td { border-bottom: 0; }
    .empty { color: var(--muted); padding: 20px 4px; }
    .loading { opacity: 0.65; pointer-events: none; }

    @media (max-width: 1100px) {
      .controls, .stats, .two-col, .three-col, .bottom { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap" id="app">
    <div class="header">
      <div class="title">Screen Time Dashboard</div>
      <div class="muted" id="timezoneLabel">Loading timezone…</div>
    </div>

    <div class="controls">
      <div class="card">
        <label for="day">Day</label>
        <div class="day-nav">
          <button id="prevDay" class="nav-btn" type="button" aria-label="Previous day">&#8249;</button>
          <input id="day" type="date">
          <button id="nextDay" class="nav-btn" type="button" aria-label="Next day">&#8250;</button>
        </div>
      </div>
      <div class="card">
        <label for="host">Hostname</label>
        <select id="host"><option value="">All Hosts</option></select>
      </div>
      <div class="card">
        <label for="deviceType">Device Type</label>
        <select id="deviceType"><option value="">All Types</option></select>
      </div>
      <div class="card">
        <label>&nbsp;</label>
        <button id="refresh" type="button">Refresh</button>
      </div>
    </div>

    <div class="stats">
      <div class="card"><div class="muted">Unique Total</div><div class="stat-value" id="uniqueTotal">-</div><div class="muted">No double counting across devices</div></div>
      <div class="card"><div class="muted">Summed Device Time</div><div class="stat-value" id="summedTotal">-</div><div class="muted">Simple sum of device totals</div></div>
      <div class="card"><div class="muted">Active Devices</div><div class="stat-value" id="activeDevices">-</div><div class="muted">Distinct hostnames</div></div>
      <div class="card"><div class="muted">Intervals</div><div class="stat-value" id="intervalCount">-</div><div class="muted">Intervals overlapping the selected local day</div></div>
    </div>

    <div class="two-col">
      <div class="card">
        <div class="section-title">Timeline by Hostname</div>
        <div class="section-sub">Each row is one hostname. Colors stay consistent per hostname.</div>
        <div id="timeline"></div>
      </div>
      <div class="card">
        <div class="section-title">By Hostname</div>
        <div class="section-sub">Total clipped time by hostname</div>
        <div id="hostBars"></div>
      </div>
    </div>

    <div class="three-col">
      <div class="card">
        <div class="section-title">By Device Type</div>
        <div class="section-sub">Total clipped time by device type</div>
        <div id="typeBars"></div>
      </div>
      <div class="card">
        <div class="section-title">Per Device</div>
        <div class="section-sub">Each hostname with its device type</div>
        <div id="deviceBars"></div>
      </div>
      <div class="card">
        <div class="section-title">Selection</div>
        <div class="section-sub">Selected day and filters</div>
        <div id="selectionSummary" class="empty"></div>
      </div>
    </div>

    <div class="bottom">
      <div class="card">
        <div class="section-title">Per-Device Details</div>
        <div class="section-sub">Grouped by hostname</div>
        <div id="deviceTable"></div>
      </div>
      <div class="card">
        <div class="section-title">Intervals</div>
        <div class="section-sub">All intervals clipped to the selected local day</div>
        <div id="intervalTable"></div>
      </div>
    </div>
  </div>

  <script>
    const app = document.getElementById('app');
    const dayInput = document.getElementById('day');
    const hostSelect = document.getElementById('host');
    const deviceTypeSelect = document.getElementById('deviceType');
    const refreshBtn = document.getElementById('refresh');
    const prevDayBtn = document.getElementById('prevDay');
    const nextDayBtn = document.getElementById('nextDay');
    const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    document.getElementById('timezoneLabel').textContent = `Local day view: ${browserTimeZone}`;

    const HOST_PALETTE = [
      ['hsl(221 83% 55%)', 'linear-gradient(90deg, hsl(221 83% 60%), hsl(221 83% 52%))'],
      ['hsl(145 63% 42%)', 'linear-gradient(90deg, hsl(145 58% 48%), hsl(145 63% 40%))'],
      ['hsl(28 92% 50%)', 'linear-gradient(90deg, hsl(33 96% 56%), hsl(24 90% 48%))'],
      ['hsl(281 75% 58%)', 'linear-gradient(90deg, hsl(286 80% 64%), hsl(276 70% 54%))'],
      ['hsl(354 78% 57%)', 'linear-gradient(90deg, hsl(354 82% 63%), hsl(349 74% 53%))'],
      ['hsl(191 78% 42%)', 'linear-gradient(90deg, hsl(191 78% 48%), hsl(192 76% 38%))'],
      ['hsl(48 94% 46%)', 'linear-gradient(90deg, hsl(48 98% 54%), hsl(44 90% 44%))'],
      ['hsl(168 76% 36%)', 'linear-gradient(90deg, hsl(168 74% 42%), hsl(169 78% 32%))'],
      ['hsl(230 65% 60%)', 'linear-gradient(90deg, hsl(230 70% 66%), hsl(230 62% 56%))'],
      ['hsl(12 82% 57%)', 'linear-gradient(90deg, hsl(12 86% 63%), hsl(10 78% 53%))'],
    ];

    function localDateString(d = new Date()) {
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function shiftDay(dayString, offsetDays) {
      const [year, month, day] = dayString.split('-').map(Number);
      const d = new Date(year, month - 1, day);
      d.setDate(d.getDate() + offsetDays);
      return localDateString(d);
    }

    function fmtDuration(seconds) {
      const s = Math.max(0, Math.round(seconds));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      if (h > 0) return `${h}h ${m}m`;
      if (m > 0) return `${m}m ${sec}s`;
      return `${sec}s`;
    }

    function fmtLocalTime(ts) {
      return new Intl.DateTimeFormat([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: browserTimeZone,
      }).format(new Date(ts));
    }

    function fmtLocalDateTime(ts) {
      return new Intl.DateTimeFormat([], {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: browserTimeZone,
      }).format(new Date(ts));
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text == null ? '' : String(text);
      return div.innerHTML;
    }

    function hashString(text) {
      let hash = 0;
      for (let i = 0; i < text.length; i += 1) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash |= 0;
      }
      return Math.abs(hash);
    }

    function getHostColorPair(host) {
      return HOST_PALETTE[hashString(host) % HOST_PALETTE.length];
    }

    function hostDot(host) {
      const [solid] = getHostColorPair(host);
      return `<span class="host-swatch" style="background:${solid}"></span>`;
    }

    function renderBars(el, rows, labelFn, colorFn = null) {
      if (!rows.length) {
        el.innerHTML = '<div class="empty">No data</div>';
        return;
      }
      const max = Math.max(...rows.map(r => r.seconds), 1);
      el.innerHTML = `<div class="bars">${rows.map(r => {
        const fill = colorFn ? colorFn(r) : 'linear-gradient(90deg, #6366f1, #4f46e5)';
        return `
        <div class="bar-row">
          <div class="bar-label" title="${escapeHtml(labelFn(r))}">${escapeHtml(labelFn(r))}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${(r.seconds / max) * 100}%;background:${fill}"></div></div>
          <div class="bar-value">${fmtDuration(r.seconds)}</div>
        </div>`;
      }).join('')}</div>`;
    }

    function renderTimeline(data) {
      if (!data.per_device.length) {
        document.getElementById('timeline').innerHTML = '<div class="empty">No data</div>';
        return;
      }

      const byHost = new Map(data.per_device.map(d => [d.host, d]));
      const dayStart = Date.parse(data.day_start_utc);
      const dayEnd = Date.parse(data.day_end_utc);
      const rows = data.timeline_hosts.map(host => {
        const meta = byHost.get(host);
        const [solid, gradient] = getHostColorPair(host);
        const segments = data.intervals
          .filter(i => i.host === host)
          .map(i => {
            const start = Date.parse(i.clipped_start_time);
            const end = Date.parse(i.clipped_end_time);
            const left = ((start - dayStart) / (dayEnd - dayStart)) * 100;
            const width = ((end - start) / (dayEnd - dayStart)) * 100;
            return `<div class="segment" style="left:${left}%;width:${Math.max(width, 0.35)}%;background:${gradient};border-color:${solid}33" title="${escapeHtml(host)} · ${escapeHtml(i.device_type)} · ${fmtLocalTime(i.clipped_start_time)} → ${fmtLocalTime(i.clipped_end_time)}"></div>`;
          })
          .join('');

        return `
          <div class="timeline-row">
            <div class="timeline-host"><span class="host-chip">${hostDot(host)}<span>${escapeHtml(host)}</span></span><small>${escapeHtml(meta ? meta.device_type : '')}</small></div>
            <div class="timeline-track">${segments}</div>
          </div>`;
      }).join('');

      document.getElementById('timeline').innerHTML = `
        <div class="timeline">
          <div class="timeline-header">
            <div class="timeline-host muted">Hostname</div>
            <div class="timeline-hours">
              <div class="timeline-scale">
                ${['00:00','03:00','06:00','09:00','12:00','15:00','18:00','21:00'].map(t => `<div class="tick"><span>${t}</span></div>`).join('')}
              </div>
            </div>
          </div>
          ${rows}
        </div>`;
    }

    function renderDeviceTable(rows) {
      if (!rows.length) return '<div class="empty">No data</div>';
      return `<table>
        <thead><tr><th>Hostname</th><th>Type</th><th>Total</th><th>Intervals</th><th>First Active</th><th>Last Active</th></tr></thead>
        <tbody>${rows.map(r => `
          <tr>
            <td><span class="host-chip">${hostDot(r.host)}<span>${escapeHtml(r.host)}</span></span></td>
            <td>${escapeHtml(r.device_type)}</td>
            <td>${fmtDuration(r.seconds)}</td>
            <td>${r.interval_count}</td>
            <td>${r.first_active_utc ? fmtLocalTime(r.first_active_utc) : ''}</td>
            <td>${r.last_active_utc ? fmtLocalTime(r.last_active_utc) : ''}</td>
          </tr>`).join('')}</tbody>
      </table>`;
    }

    function renderIntervalTable(rows) {
      if (!rows.length) return '<div class="empty">No data</div>';
      return `<table>
        <thead><tr><th>Start</th><th>End</th><th>Hostname</th><th>Type</th><th>Duration</th></tr></thead>
        <tbody>${rows.map(r => `
          <tr>
            <td>${escapeHtml(fmtLocalDateTime(r.clipped_start_time))}</td>
            <td>${escapeHtml(fmtLocalDateTime(r.clipped_end_time))}</td>
            <td><span class="host-chip">${hostDot(r.host)}<span>${escapeHtml(r.host)}</span></span></td>
            <td>${escapeHtml(r.device_type)}</td>
            <td>${fmtDuration(r.duration_seconds)}</td>
          </tr>`).join('')}</tbody>
      </table>`;
    }

    async function fetchDay(day) {
      const params = new URLSearchParams({ day, timezone: browserTimeZone });
      const res = await fetch(`/api/day?${params.toString()}`);
      return await res.json();
    }

    async function loadSummary() {
      app.classList.add('loading');
      const params = new URLSearchParams({
        day: dayInput.value,
        timezone: browserTimeZone,
      });
      if (hostSelect.value) params.set('host', hostSelect.value);
      if (deviceTypeSelect.value) params.set('device_type', deviceTypeSelect.value);
      const res = await fetch(`/api/day?${params.toString()}`);
      const data = await res.json();

      document.getElementById('uniqueTotal').textContent = fmtDuration(data.unique_total_seconds);
      document.getElementById('summedTotal').textContent = fmtDuration(data.summed_device_seconds);
      document.getElementById('activeDevices').textContent = String(data.per_device.length);
      document.getElementById('intervalCount').textContent = String(data.interval_count);
      document.getElementById('selectionSummary').innerHTML = `
        <div><strong>Day:</strong> ${escapeHtml(data.day)}</div>
        <div><strong>Timezone:</strong> ${escapeHtml(data.timezone)}</div>
        <div><strong>Host filter:</strong> ${escapeHtml(data.host_filter || 'All Hosts')}</div>
        <div><strong>Type filter:</strong> ${escapeHtml(data.device_type_filter || 'All Types')}</div>
        <div><strong>UTC window:</strong> ${escapeHtml(data.day_start_utc)} → ${escapeHtml(data.day_end_utc)}</div>`;

      renderTimeline(data);
      renderBars(document.getElementById('hostBars'), data.per_host, r => `${r.key}`, r => getHostColorPair(r.key)[1]);
      renderBars(document.getElementById('typeBars'), data.per_device_type, r => r.key);
      renderBars(document.getElementById('deviceBars'), data.per_device, r => `${r.host} (${r.device_type})`, r => getHostColorPair(r.host)[1]);
      document.getElementById('deviceTable').innerHTML = renderDeviceTable(data.per_device);
      document.getElementById('intervalTable').innerHTML = renderIntervalTable(data.intervals);
      app.classList.remove('loading');
    }

    async function init() {
      const today = localDateString();
      dayInput.value = today;
      const data = await fetchDay(today);

      hostSelect.innerHTML = ['<option value="">All Hosts</option>']
        .concat(data.per_host.map(r => `<option value="${escapeHtml(r.key)}">${escapeHtml(r.key)}</option>`))
        .join('');

      deviceTypeSelect.innerHTML = ['<option value="">All Types</option>']
        .concat(data.per_device_type.map(r => `<option value="${escapeHtml(r.key)}">${escapeHtml(r.key)}</option>`))
        .join('');

      await loadSummary();
    }

    function changeDay(offset) {
      dayInput.value = shiftDay(dayInput.value, offset);
      loadSummary();
    }

    refreshBtn.addEventListener('click', loadSummary);
    prevDayBtn.addEventListener('click', () => changeDay(-1));
    nextDayBtn.addEventListener('click', () => changeDay(1));
    dayInput.addEventListener('change', loadSummary);
    hostSelect.addEventListener('change', loadSummary);
    deviceTypeSelect.addEventListener('change', loadSummary);
    init();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(HTML_PAGE)


def run():
    host = os.environ.get("SCREENTIME_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SCREENTIME_SERVER_PORT", "7777"))
    uvicorn.run("screentime.server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
