# Android Widget Companion

This repo includes a standalone Android companion app under `android/` that powers home-screen widgets backed by Chronicle plan data.

![widget](https://github.com/user-attachments/assets/7132c09c-7db5-412a-9932-f2413133321a)


## What It Does
- Fetches `GET /plan/today.json` to get today's Planned Run.
- Backend Schedules a WorkManager background sync every **61 minutes**.
- Supports on-demand refresh from widget/action tap.
- Provides two widget types:
  1. `1x1` miles-only tile (Chronicle icon background + large miles text).
  2. Resizable today-detail widget (miles, run type, workout shorthand if present).
- Tapping widget content opens Chronicle `/plan`.

## Chronicle API Contract
`GET /plan/today.json` provides:

```json
{
  "date_local": "2026-02-22",
  "run_type": "Easy",
  "miles": 7.0,
  "workout_shorthand": "2E + 20T + 2E"
}
```

`workout_shorthand` is dependant on `SOS` run type.

## Configure Base URL
The launcher app (`Chronicle Widget`) contains a simple base URL setting.
- Set Chronicle's LAN URL ex. `http://192.168.1.90:8080`
- Save, then tap **Refresh Widgets Now**.

## Notes
- WorkManager enforces a minimum interval; 61 minutes is honored.
- If network fetch fails, widget falls back to last cached payload.

## APK Distribution
- APK binaries are distributed through **GitHub Releases**, not committed in source control.
- Release workflow: `.github/workflows/android-widget-release.yml`.
- Trigger options:
  - Push a tag like `android-widget-v0.2.0`.
  - Or run the workflow manually (`workflow_dispatch`) and provide `release_tag`.
- Release asset output name format: `chronicle-widget-<tag>.apk`.
