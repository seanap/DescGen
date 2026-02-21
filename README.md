# Chronicle

<p align="center">
<img src="./static/chronicle.png" alt="Chronicle icon" width="120" />
</p>

Chronicle automatically builds rich Strava activity descriptions by combining data from Strava and your connected stat sources.

## Key Features
- Auto-processes new activities on a worker heartbeat.
- Writes description templates back to Strava based on activity profile.
- Includes a polished local web app:
  - `View` (`/dashboard`) for long-term trends.
  - `Build` (`/editor`) for template editing and preview.
  - `Sources` (`/setup`) for source credentials and OAuth.
  - `Control` (`/control`) for one-click API operations.
- Supports profile-based templates (for different activity types).
- Exposes local API endpoints for automation and reruns.

## Screenshots
<img width="2387" height="1931" alt="Screenshot 2026-02-20 115406" src="https://github.com/user-attachments/assets/dc7746bf-d08b-4c40-844b-39b128888ae6" />
<img width="2006" height="1943" alt="Screenshot 2026-02-20 115619" src="https://github.com/user-attachments/assets/ec734164-a7e0-4b60-8131-9c4968b4f858" />
<img width="2399" height="926" alt="Screenshot 2026-02-20 115710" src="https://github.com/user-attachments/assets/9ef5e175-ea91-42b6-b430-faa68060493e" />
<img width="2336" height="1939" alt="Screenshot 2026-02-20 115752 REDACTED" src="https://github.com/user-attachments/assets/6a4a2e88-c7c0-4692-ac33-5251b52d753d" />



## Quick Start (macOS)

### Step 0: Install Docker Desktop for Mac
1. Watch this quick setup video: https://www.youtube.com/watch?v=agkOZr27d3Y
2. Install Docker Desktop and launch it.
3. Wait until Docker says it is running.

### Step 1: Open Terminal
- Open `Terminal.app`.

### Step 2: Create a folder and clone Chronicle Project
```bash
mkdir -p ~/docker/chronicle
cd ~/docker/chronicle
git clone https://github.com/seanap/Chronicle.git
cd Chronicle
cp .env.example .env
```

### Step 3: Start Chronicle
```bash
docker compose up -d
```

If you are upgrading from older `DescGen` / `Auto-Stat-Description` setups, verify your `.env` contains:
```bash
DOCKER_IMAGE=seanap/chronicle:latest
```

### Step 4: Open the app
```bash
http://localhost:1609
```

- Dashboard (`View`): http://localhost:1609/dashboard
- Template Editor (`Build`): http://localhost:1609/editor
- Source Setup (`Sources`): http://localhost:1609/setup
- API Control (`Control`): http://localhost:1609/control

### Step 5: Add your credentials in `Sources`
- Go to `Sources` and fill in your source keys/tokens.
- Source setup guide: [`docs/SOURCES_SETUP.md`](docs/SOURCES_SETUP.md)

## Documentation
- API docs: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)
