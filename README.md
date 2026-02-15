# Auto-Stat-Description
Automatically updates the description of your latest Strava activity with stats pulled from Strava, Smashrun, Garmin, Intervals.icu, and WeatherAPI.

This repo is now designed to run cleanly on a Docker server with a worker loop and a local JSON API endpoint.

## What Changed
- Credentials are read from environment variables (`.env`) instead of hardcoded values.
- Heartbeat polling is optimized for 5-minute intervals (`POLL_INTERVAL_SECONDS=300` default).
- Quiet hours can pause polling between midnight and 4 AM local time.
- Local JSON endpoint added for dashboards (`/latest`).
- Stat source rules updated:
- Elevation stats are sourced from Smashrun.
- GAP pace stats are sourced from Strava activity data.
- 7-day / 30-day / year summaries use local calendar-day boundaries from `TZ`.

## Data Sources
- Smashrun:
  - Longest streak
  - Notables
  - Elevation totals (latest activity, 7d, 30d, YTD)
- Strava:
  - Latest activity detection and description update
  - GAP pace values (latest + trailing periods)
  - Distance/time/calories for trailing stats
- Garmin:
  - VO2max, training status, training readiness, resting HR, endurance/hill score
- Intervals.icu:
  - CTL/ATL/Form summary
  - Latest achievements, NP, work, efficiency
- WeatherAPI:
  - Misery index
  - AQI
- Crono API:
  - Activity-day protein and carbs
  - 7-day average daily energy balance (deficit/surplus)

## Runtime Model
- `worker.py`: polls Strava on interval and updates description only when a new activity appears.
- `api_server.py`: serves the latest generated payload from `state/latest_activity.json`.

## API Endpoints
- `GET /health`
- `GET /latest`
- `POST /rerun/latest` (force rerun on latest Strava activity)
- `POST /rerun/activity/<activity_id>` (force rerun on a specific Strava activity)
- `POST /rerun` with optional JSON body `{ "activity_id": 123456789 }`

Example:
```bash
curl http://localhost:8080/latest
```

Rerun examples:
```bash
curl -X POST http://localhost:8080/rerun/latest
curl -X POST http://localhost:8080/rerun/activity/1234567890
curl -X POST http://localhost:8080/rerun \
  -H "Content-Type: application/json" \
  -d '{"activity_id":1234567890}'
```

## Docker Compose (Dockge Friendly)
1. Copy `.env.example` to `.env` and fill values.
2. Use this stack as-is in Dockge:

```yaml
services:
  auto-stat-worker:
    image: yourdockerhubusername/auto-stat-description:latest
    command: ["python", "worker.py"]
    env_file: [.env]
    volumes:
      - ./data:/app/state
    restart: unless-stopped

  auto-stat-api:
    image: yourdockerhubusername/auto-stat-description:latest
    command: ["python", "api_server.py"]
    env_file: [.env]
    volumes:
      - ./data:/app/state
    ports:
      - "8080:8080"
    restart: unless-stopped
```

A ready-to-use file is also included at `docker-compose.yml`.

## Build and Push to Docker Hub
```bash
docker build -t yourdockerhubusername/auto-stat-description:latest .
docker push yourdockerhubusername/auto-stat-description:latest
```

If you want version tags:
```bash
docker tag yourdockerhubusername/auto-stat-description:latest yourdockerhubusername/auto-stat-description:v1.0.0
docker push yourdockerhubusername/auto-stat-description:v1.0.0
```

## Environment Variables
Use `.env.example` as the template. Required keys:
- `CLIENT_ID`
- `CLIENT_SECRET`
- `REFRESH_TOKEN`

Optional integrations can be disabled with flags:
- `ENABLE_GARMIN`
- `ENABLE_INTERVALS`
- `ENABLE_WEATHER`
- `ENABLE_SMASHRUN`
- `ENABLE_CRONO_API`
- `ENABLE_QUIET_HOURS`

Crono integration settings:
- `CRONO_API_BASE_URL` (example: `http://192.168.1.9:8777`)
- `CRONO_API_KEY` (optional if your crono-api allows no key)

Token cache file (written automatically):
- `STRAVA_TOKEN_FILE` (default `strava_tokens.json` under state dir)

Quiet hours settings:
- `QUIET_HOURS_START` (0-23, default `0`)
- `QUIET_HOURS_END` (0-23, default `4`)
- `TZ` controls local-time interpretation (for example, `America/New_York`)

## Step-by-Step API Key Setup (Beginner Friendly)
This section is written for first-time users. If you only do one thing first, do this:
1. Copy `.env.example` to `.env`.
2. Fill values provider by provider using the steps below.

### 1) Strava (most confusing, do this carefully)
1. Log in to Strava and open your API app page: `https://www.strava.com/settings/api`.
2. Create an app if you do not already have one.
3. On the app page, set `Authorization Callback Domain` to `localhost` while setting up.
4. Copy these values into `.env`:
- `CLIENT_ID`
- `CLIENT_SECRET`
5. Open this URL in a browser (replace `YOUR_CLIENT_ID`):

```text
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read,activity:read_all,activity:write
```

6. Click `Authorize`.
7. Browser may show a localhost error page. That is expected. Copy the `code` value from the URL.
8. Exchange `code` for tokens:

```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=THE_CODE_FROM_URL \
  -d grant_type=authorization_code
```

9. Put these into `.env`:
- `REFRESH_TOKEN` = `refresh_token` from the response
- `ACCESS_TOKEN` = `access_token` from the response (optional but useful)

Strava troubleshooting:
- `invalid redirect_uri` means callback domain and redirect URL do not match. Use `localhost`.
- If you do not see `code=` in the URL, authorization was denied.
- If activity updates fail, confirm scope included `activity:write`.
- Strava refresh tokens can rotate; this app stores latest token values in your state folder (`STRAVA_TOKEN_FILE`).

### 2) Intervals.icu
1. Log in to Intervals.icu.
2. Open Settings and scroll to `Developer Settings` near the bottom.
3. Copy your API key and athlete ID.
4. Put into `.env`:
- `INTERVALS_API_KEY`
- `USER_ID`

Quick test:

```bash
curl -u API_KEY:YOUR_INTERVALS_API_KEY \
  "https://intervals.icu/api/v1/athlete/YOUR_ATHLETE_ID/activities?oldest=2026-01-01"
```

Note: For many endpoints, Intervals.icu allows athlete id `0` to mean “the athlete associated with this API key”.

### 3) Weather API (this project uses WeatherAPI.com, not weather.com)
1. Sign up: `https://www.weatherapi.com/signup.aspx`
2. After login, copy your API key from your WeatherAPI account/dashboard.
3. Put into `.env`:
- `WEATHER_API_KEY`

Quick test:

```bash
curl "https://api.weatherapi.com/v1/current.json?key=YOUR_WEATHER_API_KEY&q=New+York&aqi=yes"
```

### 4) Smashrun
For personal use, the fastest path is user-level auth token:
1. Open Smashrun API docs: `https://api.smashrun.com/v1/documentation`
2. Open `API Explorer`.
3. Enter `client` as the client id and connect.
4. Copy the bearer access token.
5. Put into `.env`:
- `SMASHRUN_ACCESS_TOKEN`

Quick test:

```bash
curl -H "Authorization: Bearer YOUR_SMASHRUN_ACCESS_TOKEN" \
  "https://api.smashrun.com/v1/my/stats"
```

Smashrun note:
- User-level tokens are rate-limited and reauthentication is periodically required.

### Provider-to-ENV mapping recap
- Strava: `CLIENT_ID`, `CLIENT_SECRET`, `REFRESH_TOKEN`, `ACCESS_TOKEN`
- Intervals.icu: `INTERVALS_API_KEY`, `USER_ID`
- WeatherAPI.com: `WEATHER_API_KEY`
- Smashrun: `SMASHRUN_ACCESS_TOKEN`
- Crono API: `ENABLE_CRONO_API`, `CRONO_API_BASE_URL`, `CRONO_API_KEY`

## Polling and API Usage
The worker minimizes calls by doing this each cycle:
1. `GET /athlete/activities?per_page=5`
2. Pick the first unprocessed activity from that short list.
3. Exit immediately if all of those are already processed.
4. Only for an unprocessed activity, fetch full details and secondary provider stats.

This keeps idle-cycle API usage low enough for a 5-minute heartbeat in a homelab setup.

## Local Dev
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main_strava_update.py --force
python api_server.py
```

## Notes
- Never commit your real `.env` file.
- Rotate any API keys/tokens if they were ever committed or shared.

## CI/CD
A GitHub Actions workflow is included at `.github/workflows/ci-cd.yml`:
- Runs unit tests on PRs and pushes to `main`.
- Builds and pushes Docker images to `seanap/auto-stat-description` on push events.

Required GitHub repository secrets:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
