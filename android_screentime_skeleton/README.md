# Screen Time Android Skeleton

This is a minimal Android client skeleton that matches the Ubuntu/server data model.

## Current design

- Tracks **screen on + unlocked** sessions
- Stores intervals locally using **Room**
- Uses a **foreground service** to keep a dynamic screen-state receiver alive
- Uses **WorkManager** for automatic background sync
- Hardcodes the sync server to:

  `http://192.168.1.6:7777`

## Important notes

- Open the app **once after install** so Android can fully initialize the app.
- The tracker service shows a persistent notification while it runs.
- A boot receiver is included to:
  - close any stale open interval after reboot
  - re-enqueue sync work
  - restart the tracker service

## Build in Android Studio

1. Open this folder in Android Studio.
2. Let Gradle sync.
3. Build and run on your Pixel device.
4. On first launch, grant notifications if prompted.
5. Verify the service notification appears.

## Sideloading

Android Studio can install directly to the device, or you can build a debug APK and use:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Server expectations

The Android client posts to:

- `GET /health`
- `POST /intervals/batch_upsert`

with interval rows containing:

- `interval_id`
- `start_time`
- `end_time`
- `is_open`
- `updated_at`

The top-level batch payload includes:

- `hostname`
- `device_type`
- `intervals`

## Current limitations

This is a skeleton, not a polished production app. It should be treated as:

- a starting point for real-device testing
- a way to validate the end-to-end data path
- a base for later settings UI and reliability improvements
