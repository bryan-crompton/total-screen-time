# Screentime

This project contains:

- a Ubuntu 24.04 client that tracks activity intervals locally and syncs them to a server
- a FastAPI server that accepts interval batch upserts and stores them in SQLite

## Data model

Intervals are stored with these fields on both client and server:

- `interval_id: str`
- `host: str`
- `device_type: str`
- `start_time: str` in UTC `YYYY-MM-DDTHH:MM:SSZ`
- `end_time: str` in UTC `YYYY-MM-DDTHH:MM:SSZ`
- `is_open: bool`
- `updated_at: str` in UTC `YYYY-MM-DDTHH:MM:SSZ`

Client-only sync metadata:

- `sync_status: "pending" | "synced" | "error"`
- `last_synced_at: str | null`

## Install

```bash
pipx install -e .
```

## Run the server

```bash
export SCREENTIME_SERVER_DB_PATH="$HOME/screentime-server.db"
screentime-server
```

or

```bash
uvicorn screentime.server.app:app --host 0.0.0.0 --port 8000
```

## Run the Ubuntu client

```bash
export SCREENTIME_SERVER_URL="http://YOUR_SERVER_IP:8000"
screentime-ubuntu-monitor
```

## Notes

- The Ubuntu tracker uses GNOME Mutter IdleMonitor through `gdbus`.
- The client stores only active intervals.
- The sync worker runs in a separate thread with its own SQLite connection.
- On startup, any locally open interval is conservatively closed at its last known end time.
