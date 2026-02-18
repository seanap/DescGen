# DescGen

Turn every Strava activity description into a rich, auto-generated training report.

`DescGen` is a dockerized application that checks for new activities, pulls stats from all of your connected services, writes a detailed Strava description, and exposes the latest payload as a local JSON API for other dashboards and automations.

I created this because I found that I kept checking 5 different sites for unique stats that they provided. I decided to just pull all of the stats that I want into one place, now I only check my Strava description and I can see everything at a glance. I found over time this gives me a fantastic snapshot of exactly where I was at in my training, what the conditions were, and what kind of load I was under.

## Key Features
- Auto-updates new Strava activities descriptions on a heartbeat (default every 5 minutes).
- Local API endpoint to read latest output and force reruns.
- Graphical Template Editor Web UI
- Different Profiles for different descriptions based on Run type.
- Export/import template bundles so you can move configs between instances and share amung the community.

## Sample Output 
### What Your Strava Description Can Look Like, you are only bound by your creativity:

```text
🏆 412 days in a row
🏅 Longest run in 90 days
🏅 2nd best GAP pace this month
🌤️🌡️ Misery Index: 14.9 😒 (hot) | 🏭 AQI: 22 Good
🌤️🔥 7d avg Deficit:-753 cal | Pre-Run: [🥩:40g 🍞:60g]
🌤️🚦 Training Readiness: 83 🟢 | 💗 47 | 💤 86
👟🏃 7:18/mi | 🗺️ 8.02 | 🏔️ 612' | 🕓 58:39 | 🍺 5.1
👟👣 176spm | 💼 914 kJ | ⚡ 271 W | 💓 149 | ⚙️1.03
🚄 🟢 Productive | 4.1 : 0.1 - Tempo
🚄 🏋️ 65 | 💦 78 | 🗿 -20% - Optimal 🟢
🚄 🏋️ 857 | 💦 901 | 🗿 1.1 - Optimal 🟢
❤️‍🔥 57.2 | ♾ Endur: 7312 | 🗻 Hill: 102

7️⃣ Past 7 days:
🏃 7:44/mi | 🗺️ 41.6 | 🏔️ 3,904' | 🕓 5:21:08 | 🍺 27
📅 Past 30 days:
🏃 7:58/mi | 🗺️ 156 | 🏔️ 14,902' | 🕓 20:04:51 | 🍺 101
🌍 This Year:
🏃 8:05/mi | 🗺️ 284 | 🏔️ 24,117' | 🕓 36:40:27 | 🍺 184
```

## Quick Start (Docker / Dockge)
1. In Dockge `+ Compose`
2. Paste the sample `docker-compose.yml`:

```yaml
services:
  auto-stat-worker:
    image: seanap/descgen:latest
    container_name: auto-stat-worker
    command: ["python", "worker.py"]
    network_mode: bridge
    env_file:
      - .env
    volumes:
      - ./data:/app/state
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import os,sys; from pathlib import Path; from storage import is_worker_healthy; state=Path(os.getenv('STATE_DIR','state')); log=state / os.getenv('PROCESSED_LOG_FILE','processed_activities.log'); age=int(os.getenv('WORKER_HEALTH_MAX_AGE_SECONDS','900')); sys.exit(0 if is_worker_healthy(log, age) else 1)\""]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 45s
    restart: unless-stopped

  auto-stat-api:
    image: seanap/descgen:latest
    container_name: auto-stat-api
    command: ["/bin/sh", "-c", "gunicorn --bind 0.0.0.0:${API_PORT:-1609} --workers ${API_WORKERS:-2} --threads ${API_THREADS:-4} --timeout ${API_TIMEOUT_SECONDS:-120} api_server:app"]
    network_mode: bridge
    env_file:
      - .env
    volumes:
      - ./data:/app/state
    ports:
      - "1609:1609"
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import os,sys,urllib.request; p=os.getenv('API_PORT','1609'); u='http://127.0.0.1:%s/ready' % p; r=urllib.request.urlopen(u, timeout=5); sys.exit(0 if getattr(r, 'status', 200) == 200 else 1)\""]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    restart: unless-stopped
```

3. Paste the `.env` values below the compose

```dotenv
# Strava
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REFRESH_TOKEN=your_strava_refresh_token
STRAVA_ACCESS_TOKEN=your_strava_access_token

# Garmin
ENABLE_GARMIN=true
GARMIN_EMAIL=you@example.com
GARMIN_PASSWORD=your_garmin_password

# Intervals.icu
ENABLE_INTERVALS=true
INTERVALS_API_KEY=your_intervals_api_key
INTERVALS_USER_ID=your_intervals_user_id
# Legacy alias still supported: USER_ID

# WeatherAPI
ENABLE_WEATHER=true
WEATHER_API_KEY=your_weatherapi_key

# Smashrun
ENABLE_SMASHRUN=true
SMASHRUN_ACCESS_TOKEN=your_smashrun_access_token

# Crono API
ENABLE_CRONO_API=false
CRONO_API_BASE_URL=http://<local_ip>:8777
CRONO_API_KEY=optional_if_using

# Quiet Hour Config
ENABLE_QUIET_HOURS=true
QUIET_HOURS_START=0
QUIET_HOURS_END=4

# DescGen Runtime
TIMEZONE=America/New_York
# Legacy alias still supported: TZ
#POLL_INTERVAL_SECONDS=300
#LOG_LEVEL=INFO
#STATE_DIR=state
#PROCESSED_LOG_FILE=processed_activities.log
#LATEST_JSON_FILE=latest_activity.json
#STRAVA_TOKEN_FILE=strava_tokens.json
#RUNTIME_DB_FILE=runtime_state.db
#WORKER_HEALTH_MAX_AGE_SECONDS=900
#RUN_LOCK_TTL_SECONDS=900
#SERVICE_RETRY_COUNT=2
#SERVICE_RETRY_BACKOFF_SECONDS=2
#SERVICE_COOLDOWN_BASE_SECONDS=60
#SERVICE_COOLDOWN_MAX_SECONDS=1800
#ENABLE_SERVICE_CALL_BUDGET=true
#MAX_OPTIONAL_SERVICE_CALLS_PER_CYCLE=10
#ENABLE_SERVICE_RESULT_CACHE=true
#SERVICE_CACHE_TTL_SECONDS=600

# API runtime
#API_WORKERS=2
#API_THREADS=4
#API_TIMEOUT_SECONDS=120
#API_PORT=1609
#DOCKER_IMAGE=seanap/descgen:latest
```

4. Confirm API is alive:

```bash
curl http://localhost:1609/health
curl http://localhost:1609/ready
```

5. Open Description Editor

```bash
http://localhost:1609/editor
```

<img width="2557" height="1470" alt="editor_top" src="https://github.com/user-attachments/assets/9a1197bb-f930-4538-8ef4-4f9f4607c2af" />
<img width="2562" height="1197" alt="editor_bottom" src="https://github.com/user-attachments/assets/53655c58-965c-4518-894c-f593af91bf99" />


## API Endpoints
<details>

<summary> Full Endpoint List </summary>

- `GET /health`
- `GET /ready`
- `GET /latest`
- `GET /service-metrics`
- `POST /rerun/latest` (rerun most recent activity)
- `POST /rerun/activity/<activity_id>` (rerun specific Strava activity)
- `POST /rerun` with optional JSON body: `{ "activity_id": 1234567890 }`
- `GET /editor/schema?context_mode=latest_or_sample` (available template data keys)
- `GET /editor/fixtures` (pinned sample fixtures for preview/testing)
- `GET /editor/profiles` (list profile workspace configuration + active working profile)
- `PUT /editor/profiles/<profile_id>` (enable/disable profile, update priority)
- `POST /editor/profiles/working` (set current editor working profile)
- `GET /editor/template` (active template for profile; optional `profile_id`)
- `GET /editor/template/default` (factory template)
- `GET /editor/template/export` (downloadable JSON bundle of active template; optional `profile_id`)
- `GET /editor/template/versions` (saved template version history; optional `profile_id`)
- `GET /editor/template/version/<version_id>` (specific saved template; optional `profile_id`)
- `GET /editor/snippets` (quick insert snippets for the web editor)
- `GET /editor/starter-templates` (curated starter layouts for quick setup)
- `GET /editor/context/sample` (sample context payload for testing)
- `PUT /editor/template` (save custom template; optional `profile_id`)
- `POST /editor/template/import` (import and publish template from bundle JSON; optional `profile_id`)
- `POST /editor/template/rollback` (rollback active template to a prior version; optional `profile_id`)
- `POST /editor/validate` (validate a template string; optional `context_mode`, `profile_id`)
- `POST /editor/preview` (render preview; optional `context_mode`, `profile_id`)

Editor UI:
- `GET /editor` (web UI with builder, snippet palette, click-to-insert fields, and preview context switcher)

</details>

<details>

<summary>Examples:</summary>

```bash
curl -X POST http://localhost:1609/rerun/latest
curl -X POST http://localhost:1609/rerun/activity/1234567890
curl -X POST http://localhost:1609/rerun -H "Content-Type: application/json" -d '{"activity_id":1234567890}'
curl "http://localhost:1609/editor/schema?context_mode=latest_or_sample"
curl http://localhost:1609/editor/fixtures
curl http://localhost:1609/editor/profiles
curl -X POST http://localhost:1609/editor/profiles/working -H "Content-Type: application/json" -d '{"profile_id":"trail"}'
curl http://localhost:1609/editor/template
curl "http://localhost:1609/editor/template?profile_id=trail"
curl http://localhost:1609/editor/template/export
curl "http://localhost:1609/editor/template/versions?profile_id=trail"
curl http://localhost:1609/editor/snippets
curl http://localhost:1609/editor/starter-templates
curl http://localhost:1609/editor/context/sample
curl http://localhost:1609/editor/context/sample?fixture=winter_grind
curl -X POST http://localhost:1609/editor/template/import -H "Content-Type: application/json" -d '{"bundle":{"template":"{{ activity.gap_pace }}","name":"Imported Template"},"author":"cli-user","context_mode":"sample","profile_id":"trail"}'
curl -X POST http://localhost:1609/editor/validate -H "Content-Type: application/json" -d '{"context_mode":"sample","profile_id":"trail","template":"{{ activity.gap_pace }} | {{ activity.distance_miles }}"}'
curl -X POST http://localhost:1609/editor/preview -H "Content-Type: application/json" -d '{"context_mode":"fixture","fixture_name":"humid_hammer","profile_id":"trail","template":"{{ training.vo2 }} | {{ periods.week.distance_miles }}mi"}'
curl -X POST http://localhost:1609/editor/template/rollback -H "Content-Type: application/json" -d '{"version_id":"vYYYYMMDDTHHMMSSffffffZ-abcdef1234","profile_id":"trail"}'
open http://localhost:1609/editor
```
</details>

# Step-by-Step API Setup

## Strava
1. Go to `https://www.strava.com/settings/api` and create/open your API app.
2. Set **Authorization Callback Domain** to `localhost` during setup.
3. Copy `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` into `.env`.
4. Open this URL (replace `YOUR_STRAVA_CLIENT_ID`):

```text
https://www.strava.com/oauth/authorize?client_id=YOUR_STRAVA_CLIENT_ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read,activity:read_all,activity:write
```

5. Authorize the app.
6. If browser shows a localhost error page, that is expected.
7. Copy the `code=` value from the URL.
8. Exchange code for tokens:

```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_STRAVA_CLIENT_ID \
  -d client_secret=YOUR_STRAVA_CLIENT_SECRET \
  -d code=THE_CODE_FROM_URL \
  -d grant_type=authorization_code
```

9. Put response values into `.env`:
- `STRAVA_REFRESH_TOKEN` = `refresh_token`
- `STRAVA_ACCESS_TOKEN` = `access_token` (optional; refresh token is what matters long-term)
  (Legacy aliases `REFRESH_TOKEN` and `ACCESS_TOKEN` are still accepted.)

Strava gotchas:
- `invalid redirect_uri`: callback domain and URL do not match.
- Missing `code=`: authorization was denied.
- Updates fail: ensure `activity:write` scope was granted.

## Intervals.icu
1. Open Intervals.icu settings.
2. In Developer/API section, copy your API key and athlete ID.
3. Set `.env` values:
- `INTERVALS_API_KEY`
- `INTERVALS_USER_ID`
  (Legacy alias `USER_ID` is still accepted.)

Quick test:
```bash
curl -u API_KEY:YOUR_INTERVALS_API_KEY \
  "https://intervals.icu/api/v1/athlete/YOUR_ATHLETE_ID/activities?oldest=2026-01-01"
```

## Weather API
1. Sign up at `https://www.weatherapi.com/signup.aspx`.
2. Copy your key from the WeatherAPI dashboard.
3. Set `.env`:
- `WEATHER_API_KEY`

Quick test:
```bash
curl "https://api.weatherapi.com/v1/current.json?key=YOUR_WEATHER_API_KEY&q=New+York&aqi=yes"
```

## Smashrun
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

## Misery Index v3 (Running-Normalized Dual-Head)
`misery.index = D(weather discomfort) + tail(R(weather hazard risk))`

<details>

<summary> Detailed Algorithm Explanation </summary>
This version is running-specific and uses two coupled heads:

- `0` is ideal.
- Higher is always more miserable.
- Discomfort (`D`) and danger risk (`R`) are modeled separately.
- `Death` (`>100`) is intended to come from true hazard regimes, not casual stacking.

Primary factors:
- Apparent thermal load (temp + heat index + wind chill blending)
- Dew point and humidity
- Wind comfort + strong-wind effort burden (`>10 mph`) with context damping
- Sun/cloud proxy
- Precipitation and snow interaction penalties

Model structure:
- `D` (discomfort): smooth convex penalties around running comfort bands.
- `R` (risk): regime-gated hazard modes (`heat`, `cold`, `cold-wet/storm`) combined with `logsumexp`.
- Final score: `D + soft risk-tail`; mild wind in already-bad weather raises discomfort but does not automatically imply emergency risk.

Severity buckets (`misery.index`):
- `0-5`: ideal
- `>5-15`: mild
- `>15-30`: moderate
- `>30-50`: high
- `>50-75`: very high
- `>75-100`: extreme
- `>100`: death

Polarity is separate from severity:
- `misery.index.polarity`: `hot`, `cold`, or `neutral`
- `misery.index.emoji`: chosen from severity + polarity
- `misery.index`: display scalar (numeric)

Template usage:
- `{{ misery.index }}`
- `{{ misery.index.emoji }}`
- `{{ misery.index.polarity }}`
- `{{ misery.index.severity }}`

### Example Scenarios
These are computed with the live algorithm in this repo.

| Scenario | Temp (F) | Dew Point (F) | Humidity (%) | Wind (mph) | Conditions | MI | Bucket |
| --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| Goldilocks target | 50.0 | 45.0 | 70 | 2.0 | Slightly cloudy, light breeze | 0.0 | 😀 Ideal |
| Wind burden example | 63.0 | 49.6 | 61 | 11.9 | Clear, windy | 14.9 | 😒 Mild (hot) |
| Cold rain/snow | 34.0 | 30.0 | 90 | 8.0 | Moderate snow | 105.2 | ☠️ Death (cold) |
| Winter grind | 24.1 | 5.0 | 43 | 16.5 | Windy, mixed precip chance | 196.4 | ☠️ Death (cold) |
| Humid hammer | 89.8 | 80.2 | 78 | 2.7 | Humid, low breeze | 187.3 | ☠️ Death (hot) |
</details>

----
##### Want to contribute? I am very open to pull requests. I only have a Garmin watch so other brand stats will need to be community added.
----
<!-- blank line -->
<a href="https://www.buymeacoffee.com/seanap" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-green.png" alt="Buy Me A Book" height="41" width="174"></a>
