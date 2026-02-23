# Android Widget Companion

This repo includes a standalone Android companion app under `android/` that powers home-screen widgets backed by Chronicle plan data.

## What It Does
- Fetches `GET /plan/today.json`.
- Schedules a WorkManager background sync every **61 minutes**.
- Supports on-demand refresh from widget/action tap.
- Provides two widget types:
  1. `1x1` miles-only tile (Chronicle icon background + large miles text).
  2. Resizable today-detail widget (miles, run type, workout shorthand if present).
- Tapping widget content opens Chronicle `/plan`.

## Chronicle API Contract
The widget app expects:

```json
{
  "date_local": "2026-02-22",
  "run_type": "Easy",
  "miles": 7.0,
  "workout_shorthand": "2E + 20T + 2E"
}
```

`workout_shorthand` is optional.

## Build / Install
1. Open `android/` in Android Studio (Giraffe+ recommended).
2. Let Gradle sync and install required SDK components.
3. Connect a device/emulator and run the `app` module.
4. Add either Chronicle widget from the home-screen widget picker.

## Configure Base URL
The launcher app (`Chronicle Widget`) contains a simple base URL setting.
- Example LAN URL: `http://192.168.1.9:8777`
- Emulator default remains `http://10.0.2.2:8777`

Save, then tap **Refresh Widgets Now**.

## Notes
- WorkManager enforces a minimum interval; 61 minutes is honored.
- Widget update period is `0`; refreshes are fully worker-driven.
- If network fetch fails, widget falls back to last cached payload.
