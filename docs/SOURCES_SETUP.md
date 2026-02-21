# Sources Setup Guide

This guide walks you through getting your credentials and connecting each source from the Chronicle `Sources` page:
- `http://localhost:1609/setup`

## Before You Start
- Chronicle is running (`docker compose up -d`).
- You can open `http://localhost:1609/setup` in your browser.
- You only need to configure the sources you actually use.

---

## Step 1: Open Sources Page
1. Open `http://localhost:1609/setup`.
2. You will see provider cards (Strava, Garmin, Intervals, Weather, Smashrun, Crono, etc.).

<img width="2336" height="1939" alt="Screenshot 2026-02-20 115752 REDACTED" src="https://github.com/user-attachments/assets/b2d7056b-6dae-4c94-b3be-2ddda7a51155" />

---

## Step 2: Strava (Required)
1. Open Strava api settings: https://www.strava.com/settings/api
2. Create `My API Application`
3. Fill app fields:
  - Application Name: anything (ex: Chronicle)
  - Category: any relevant category
  - Website: for local setup, http://localhost is fine
  - Authorization Callback Domain: this is the important one (host only)
<img width="1085" height="1156" alt="Screenshot 2026-02-20 122551 Highlighted" src="https://github.com/user-attachments/assets/a96a0d94-e466-44e2-b8d0-7cdfb19b38ee" />

4. Set callback domain based on how you open Chronicle:
  - If you use http://localhost:1609/setup -> set callback domain to localhost
5. Copy your `CLIENT_ID` and `CLIENT_SECRET`

<img width="1298" height="1884" alt="Screenshot 2026-02-20 121252 REDACTED" src="https://github.com/user-attachments/assets/e667fb1c-4922-41d4-9ad3-3a74f8cf327e" />

6. Go to Chronicle Sources `/setup` page: 
  *  Enter `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`. 
  * Click **Save Setup**. 
  * Click **Connect Strava OAuth** inside the Strava card. 
  * Approve access on Strava. 
  * You should be redirected back to /setup as connected 

<img width="705" height="939" alt="Screenshot 2026-02-20 123909 Highlighted" src="https://github.com/user-attachments/assets/f5a13bfa-da5b-462a-81e7-0de4c4f19121" />


Common issues:
- OAuth start fails: client id/secret not saved yet.
- Callback mismatch: verify your Strava app callback settings.

---

## Step 3: Garmin (Optional)
Where to get it:
- Your regular Garmin Connect account: https://connect.garmin.com/

Fields in `Sources`:
- `ENABLE_GARMIN` (toggle)
- `GARMIN_EMAIL`
- `GARMIN_PASSWORD`

Steps:
1. Enable Garmin toggle.
2. Enter your Garmin login email and password.
3. Save setup.

---

## Step 4: Intervals.icu (Optional)
Where to get it:
- Intervals: https://intervals.icu/
- API key and user id are in your Intervals account settings.

Fields in `Sources`:
- `ENABLE_INTERVALS` (toggle)
- `INTERVALS_API_KEY`
- `INTERVALS_USER_ID`

Steps:
1. Enable Intervals toggle.
2. Paste API key and user ID.
3. Save setup.

---

## Step 5: WeatherAPI (Optional)
Where to get it:
- Sign up and create a key: https://www.weatherapi.com/signup.aspx

Fields in `Sources`:
- `ENABLE_WEATHER` (toggle)
- `WEATHER_API_KEY`

Steps:
1. Enable Weather toggle.
2. Paste your WeatherAPI key.
3. Save setup.

---

## Step 6: Smashrun (Optional)
Where to get it:
- Smashrun API docs: https://api.smashrun.com/v1/documentation

Fields in `Sources`:
- `ENABLE_SMASHRUN` (toggle)
- `SMASHRUN_ACCESS_TOKEN`

Steps:
1. Enable Smashrun toggle.
2. Paste access token.
3. Save setup.

---

## Step 7: Crono API (Optional)
Where to get it:
- Project reference: https://github.com/seanap/crono-api

Fields in `Sources`:
- `ENABLE_CRONO_API` (toggle)
- `CRONO_API_BASE_URL` (example: `http://<your-ip>:8777`)
- `CRONO_API_KEY` (Only if your instance requires one)

Steps:
1. Enable Crono API toggle.
2. Enter base URL (and API key if required).
3. Save setup.

---

## Step 8: Timezone (General)
Field in `Sources`:
- `TIMEZONE`

Use an IANA timezone value. Examples:
- `America/Los_Angeles`
- `America/Denver`
- `America/Chicago`
- `America/New_York`

---

## Step 9: Save and Verify
1. Click **Save Setup**.
2. Click **Reload**.
3. Verify status chips/messages are healthy.
4. Optional verification endpoints:
```bash
curl http://localhost:1609/health
curl http://localhost:1609/ready
curl http://localhost:1609/setup/api/config
```


---

## What Gets Saved
- `.env` is the canonical saved config. If changing  `.env` manually you will need to restart the container.
- Chronicle also writes runtime setup overrides so `.env` changes apply immediately without a restart when using the `/setup`

## Troubleshooting Container Boot Errors
If you see errors like:
- `ModuleNotFoundError: No module named 'api_server'`
- `python: can't open file '/app/worker.py'`

Then your stack is likely running an older image or compose file.

Fix:
1. In `.env`, set `DOCKER_IMAGE=seanap/chronicle:latest`.
2. Ensure you are launching from this repo with `docker-compose.yml` (and remove/rename any stale `compose.yaml` in the same folder).
3. Restart:
```bash
docker compose down
docker compose pull
docker compose up -d
```
