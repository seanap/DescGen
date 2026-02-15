# Auto-Stat-Description

Turn every Strava activity into a rich, auto-generated training report.

`auto-stat-description` checks for new activities, pulls stats from your connected services, writes a detailed Strava description, and exposes the latest payload as a local JSON API for dashboards and automations.

## Key Features
- Auto-updates new Strava activities on a heartbeat (default every 5 minutes).
- Uses timezone-aware daily boundaries (`TZ`) so weekly/monthly/year summaries are stable.
- Pulls elevation totals from Smashrun and GAP pace from Strava.
- Includes optional Crono nutrition/energy-balance stats in the description.
- Quiet hours support (default: skip polling from `00:00` to `04:00`).
- Local API endpoint to read latest output and force reruns.

## Sample Output (What Your Strava Description Can Look Like)
```text
🏆 412 days in a row
🏅 Longest run in 90 days
🏅 2nd best GAP pace this month
🌤️🌡️ Misery Index: 104.3 😀 Perfect | 🏭 AQI: 22 Good
🔥 7d avg daily Energy Balance:-1131 kcal (deficit) | 🥩:182g | 🍞:216g
🌤️🚦 Training Readiness: 83 🟢 | 💗 47 | 💤 86
👟🏃 7:18/mi | 🗺️ 8.02 | 🏔️ 612' | 🕓 58:39 | 🍺 5.1
👟👣 176spm | 💼 914 kJ | ⚡ 271 W | 💓 149 | ⚙️1.03
🚄 🟢 Productive | 4.1 : 0.1 - Tempo
🚄 CTL 72 | ATL 78 | Form -6
🚄 🏋️ 72 | 💦 78 | 🗿 1.1 - Optimal 🟢
❤️‍🔥 57.2 | ♾ Endur: 7312 | 🗻 Hill: 102

7️⃣ Past 7 days:
🏃 7:44/mi | 🗺️ 41.6 | 🏔️ 3,904' | 🕓 5:21:08 | 🍺 27
📅 Past 30 days:
🏃 7:58/mi | 🗺️ 156 | 🏔️ 14,902' | 🕓 20:04:51 | 🍺 101
🌍 This Year:
🏃 8:05/mi | 🗺️ 284 | 🏔️ 24,117' | 🕓 36:40:27 | 🍺 184
```

## Misery Index v2 (Mirrored Scale)
`MI = 100 + hot_penalties - cold_penalties` (display-bounded to `[-40, 240]`)

The model is intentionally smooth (no abrupt jumps at exact temp/wind/rain thresholds).

- `<20`: `☠️⚠️ High risk (cold)`
- `20-30`: `😡 Miserable (cold)`
- `30-40`: `🥶 Oppressively cold`
- `40-50`: `😰 Very uncomfortable (cold)`
- `50-60`: `😓 Moderate uncomfortable (cold)`
- `60-70`: `😕 Mild uncomfortable (cold)`
- `70-130`: `😀 Perfect`
- `130-140`: `😕 Mild uncomfortable`
- `140-150`: `😓 Moderate uncomfortable`
- `150-160`: `😰 Very uncomfortable`
- `160-170`: `🥵 Oppressive`
- `170-180`: `😡 Miserable`
- `>=180`: `☠️⚠️ High risk`

### Contributing Factors
- Apparent temperature core:
  - Uses Heat Index when hot.
  - Uses Wind Chill when cold.
- Dew point stress:
  - High dew point adds heat strain.
  - Very low dew point adds cold/dry strain.
- Humidity extremes:
  - Very humid hot air increases stress.
  - Very dry cold air increases irritation penalty.
- Wind behavior:
  - Stagnant air on hot/humid days increases MI.
  - Cooling breeze can slightly reduce hot stress.
  - Severe wind in cold adds extra exposure penalty.
- Precipitation and snow:
  - Light drizzle is minor.
  - Heavy rain/downpour adds significant discomfort.
  - Snow/sleet/freezing conditions add strong cold penalties.
- Cloud and sun load:
  - Full sun can raise heat burden.
  - Heavy overcast can add slight cold penalty in cold weather.
- Transparency:
  - `/latest` includes `weather.misery_components` with per-factor contributions.

### Example Scenarios
These are computed with the live algorithm in this repo.

| Scenario | Temp (F) | Dew Point (F) | Humidity (%) | Wind (mph) | Conditions | MI | Bucket |
| --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| High risk cold example | 23.0 | -6.6 | 27 | 14.5 | Clear, very dry, windy | 12.0 | ☠️⚠️ High risk (cold) |
| Miserable cold example | 27.0 | 2.1 | 33 | 17.7 | Clear, dry, windy | 25.0 | 😡 Miserable (cold) |
| Oppressively cold example | 28.3 | 25.7 | 94 | 17.1 | Partly cloudy, damp, windy | 35.0 | 🥶 Oppressively cold |
| Very uncomfortable cold example | 32.4 | 6.0 | 31 | 16.8 | Clear, dry wind chill | 45.0 | 😰 Very uncomfortable (cold) |
| Moderate uncomfortable cold example | 26.9 | 0.8 | 35 | 0.9 | Overcast, cold/dry air | 55.0 | 😓 Moderate uncomfortable (cold) |
| Mild uncomfortable cold example | 37.1 | 25.9 | 65 | 13.5 | Partly cloudy, breezy | 65.0 | 😕 Mild uncomfortable (cold) |
| Perfect example | 63.0 | 49.6 | 61 | 11.9 | Clear, comfortable | 100.0 | 😀 Perfect |
| Mild uncomfortable heat example | 83.8 | 74.8 | 74 | 2.3 | Partly cloudy, muggy | 135.0 | 😕 Mild uncomfortable |
| Moderate uncomfortable heat example | 83.6 | 80.7 | 87 | 2.3 | Overcast, very humid | 145.0 | 😓 Moderate uncomfortable |
| Very uncomfortable heat example | 92.8 | 73.1 | 51 | 1.8 | Clear, hot, low breeze | 155.0 | 😰 Very uncomfortable |
| Oppressive heat example | 93.2 | 76.9 | 58 | 16.9 | Partly cloudy, oppressive heat load | 165.0 | 🥵 Oppressive |
| Miserable heat example | 89.7 | 81.9 | 76 | 6.5 | Partly cloudy, tropical humidity | 175.0 | 😡 Miserable |
| High risk heat example | 89.5 | 82.5 | 83 | 2.1 | Partly cloudy, no cooling | 190.0 | ☠️⚠️ High risk |

## Emoji + Data Source Legend
- `🏆`, `🏅`, `🏔️` totals (rolling periods): Smashrun
- `👟🏃` GAP pace, `🗺️`, `🕓`, latest activity core metrics: Strava
- `🚄`, `❤️‍🔥`, `♾`, `🗻`, `💗`, `💤`: Garmin + Intervals.icu (if enabled)
- `🌤️🌡️`, `🏭`: WeatherAPI
- `🔥`, `🥩`, `🍞`: Crono API (if enabled and values are > 0)
- `🍺`: Derived locally from activity calories

## Why Two Containers?
The compose stack runs **one image** in **two roles**:
- `auto-stat-worker`: long-running polling loop that updates Strava.
- `auto-stat-api`: lightweight API server for `/latest` and rerun endpoints.

This separation is intentional and more robust than cramming two processes into one container. It keeps restarts, logs, and health behavior cleaner while still using the same image.

## Quick Start (Docker / Dockge)
1. Create an empty stack folder.
2. Add `docker-compose.yml`:

```yaml
services:
  auto-stat-worker:
    image: seanap/auto-stat-description:latest
    container_name: auto-stat-worker
    command: ["python", "worker.py"]
    env_file:
      - .env
    volumes:
      - ./data:/app/state
    restart: unless-stopped

  auto-stat-api:
    image: seanap/auto-stat-description:latest
    container_name: auto-stat-api
    command: ["python", "api_server.py"]
    env_file:
      - .env
    volumes:
      - ./data:/app/state
    ports:
      - "1609:1609"
    restart: unless-stopped
```

3. Add `.env` in the same folder (sample below), then deploy the stack.

```dotenv
# Required: Strava
CLIENT_ID=your_strava_client_id
CLIENT_SECRET=your_strava_client_secret
REFRESH_TOKEN=your_strava_refresh_token
ACCESS_TOKEN=

# Optional providers
GARMIN_EMAIL=you@example.com
GARMIN_PASSWORD=your_garmin_password
INTERVALS_API_KEY=your_intervals_api_key
USER_ID=your_intervals_user_id
WEATHER_API_KEY=your_weatherapi_key
SMASHRUN_ACCESS_TOKEN=your_smashrun_access_token

# Crono API (enabled)
ENABLE_CRONO_API=true
CRONO_API_BASE_URL=http://192.168.1.9:8777
CRONO_API_KEY=

# Runtime
POLL_INTERVAL_SECONDS=300
LOG_LEVEL=INFO
TZ=America/New_York
STATE_DIR=state
PROCESSED_LOG_FILE=processed_activities.log
LATEST_JSON_FILE=latest_activity.json
STRAVA_TOKEN_FILE=strava_tokens.json

# Feature flags
ENABLE_GARMIN=true
ENABLE_INTERVALS=true
ENABLE_WEATHER=true
ENABLE_SMASHRUN=true
ENABLE_QUIET_HOURS=true
QUIET_HOURS_START=0
QUIET_HOURS_END=4

# API
API_PORT=1609
DOCKER_IMAGE=seanap/auto-stat-description:latest
```

4. Confirm API is alive:

```bash
curl http://localhost:1609/health
curl http://localhost:1609/latest
```

## API Endpoints
- `GET /health`
- `GET /latest`
- `POST /rerun/latest` (rerun most recent activity)
- `POST /rerun/activity/<activity_id>` (rerun specific Strava activity)
- `POST /rerun` with optional JSON body: `{ "activity_id": 1234567890 }`
- `GET /editor/schema` (available template data keys from latest run context)
- `GET /editor/template` (active template, default or custom)
- `PUT /editor/template` (save custom template)
- `POST /editor/validate` (validate a template string)
- `POST /editor/preview` (render preview from latest run context)

Editor UI:
- `GET /editor` (web UI for Simple + Advanced template editing)

Examples:
```bash
curl -X POST http://localhost:1609/rerun/latest
curl -X POST http://localhost:1609/rerun/activity/1234567890
curl -X POST http://localhost:1609/rerun -H "Content-Type: application/json" -d '{"activity_id":1234567890}'
curl http://localhost:1609/editor/schema
curl http://localhost:1609/editor/template
curl -X POST http://localhost:1609/editor/validate -H "Content-Type: application/json" -d '{"template":"{{ activity.gap_pace }} | {{ activity.distance_miles }}"}'
curl -X POST http://localhost:1609/editor/preview -H "Content-Type: application/json" -d '{"template":"{{ training.vo2 }} | {{ periods.week.distance_miles }}mi"}'
open http://localhost:1609/editor
```

## Step-by-Step API Setup

### 1) Strava (required)
1. Go to `https://www.strava.com/settings/api` and create/open your API app.
2. Set **Authorization Callback Domain** to `localhost` during setup.
3. Copy `CLIENT_ID` and `CLIENT_SECRET` into `.env`.
4. Open this URL (replace `YOUR_CLIENT_ID`):

```text
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read,activity:read_all,activity:write
```

5. Authorize the app.
6. If browser shows a localhost error page, that is expected.
7. Copy the `code=` value from the URL.
8. Exchange code for tokens:

```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=THE_CODE_FROM_URL \
  -d grant_type=authorization_code
```

9. Put response values into `.env`:
- `REFRESH_TOKEN` = `refresh_token`
- `ACCESS_TOKEN` = `access_token` (optional; refresh token is what matters long-term)

Strava gotchas:
- `invalid redirect_uri`: callback domain and URL do not match.
- Missing `code=`: authorization was denied.
- Updates fail: ensure `activity:write` scope was granted.

### 2) Intervals.icu
1. Open Intervals.icu settings.
2. In Developer/API section, copy your API key and athlete ID.
3. Set `.env` values:
- `INTERVALS_API_KEY`
- `USER_ID`

Quick test:
```bash
curl -u API_KEY:YOUR_INTERVALS_API_KEY \
  "https://intervals.icu/api/v1/athlete/YOUR_ATHLETE_ID/activities?oldest=2026-01-01"
```

### 3) Weather API
This project uses **WeatherAPI.com** (not weather.com).
1. Sign up at `https://www.weatherapi.com/signup.aspx`.
2. Copy your key from the WeatherAPI dashboard.
3. Set `.env`:
- `WEATHER_API_KEY`

Quick test:
```bash
curl "https://api.weatherapi.com/v1/current.json?key=YOUR_WEATHER_API_KEY&q=New+York&aqi=yes"
```

### 4) Smashrun
1. Open `https://api.smashrun.com/v1/documentation`.
2. Launch API Explorer and authorize.
3. Copy your bearer token.
4. Set `.env`:
- `SMASHRUN_ACCESS_TOKEN`

Quick test:
```bash
curl -H "Authorization: Bearer YOUR_SMASHRUN_ACCESS_TOKEN" \
  "https://api.smashrun.com/v1/my/stats"
```

## Polling + API Efficiency
Each heartbeat does the minimum:
1. Fetch only the latest few Strava activities.
2. Exit immediately if they are already processed.
3. Pull full downstream data only for a new (or forced) activity.

That keeps idle API usage low and supports frequent polling in homelab setups.
