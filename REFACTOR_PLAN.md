# Refactor Plan

## Phase 1: Stabilize Runtime (Completed)
- Centralize configuration in `config.py`.
- Remove hardcoded credentials from runtime code.
- Consolidate Strava token refresh and API requests in `strava_utils.py`.
- Add state persistence (`storage.py`) for processed IDs and latest payload.
- Move heartbeat runner to `worker.py`.
- Add local JSON API in `api_server.py`.

## Phase 2: Data Correctness and API Efficiency
- Add provider response snapshots for 3-5 real activities and verify field mappings for:
  - Smashrun elevation keys.
  - Strava GAP fields (`average_grade_adjusted_speed` vs fallback behavior).
- Add lightweight structured logs for each provider call and response status.
- Add retry/backoff for transient HTTP 429/5xx responses.
- Add per-provider timeout and failure budget so one provider failure does not block all updates.

## Phase 3: Test Coverage
- Add unit tests for:
  - Pace/elevation/time formatting.
  - Period summarization logic.
  - Description rendering with missing data.
  - Token cache read/write behavior.
- Add integration tests with mocked API responses for Strava/Smashrun/Intervals/Weather.

## Phase 4: Packaging and Release
- Add GitHub Actions workflow:
  - Run tests/lint.
  - Build Docker image.
  - Push tags to Docker Hub.
- Add semantic version tags and release notes.

## Phase 5: Optional Enhancements
- Add webhook mode (Strava activity webhook) to replace poll loop where possible.
- Add `/metrics` endpoint for Prometheus-style monitoring.
- Add dashboard-specific compact payload endpoint (`/latest/summary`).
