# Chronicle

<img src="./static/chronicle.png" alt="Chronicle icon" width="120" />

Chronicle automatically builds rich Strava activity descriptions by combining data from Strava and your connected stat sources.

## Key Features
- Auto-processes new activities on a worker heartbeat.
- Writes generated descriptions back to Strava.
- Includes a polished local web app:
  - `View` (`/dashboard`) for long-term trends.
  - `Build` (`/editor`) for template editing and preview.
  - `Sources` (`/setup`) for source credentials and OAuth.
  - `Control` (`/control`) for one-click API operations.
- Supports profile-based templates (for different activity types).
- Exposes local API endpoints for automation and reruns.

## Screenshots
<img width="2557" height="1470" alt="editor_top" src="https://github.com/user-attachments/assets/9a1197bb-f930-4538-8ef4-4f9f4607c2af" />
<img width="2562" height="1197" alt="editor_bottom" src="https://github.com/user-attachments/assets/53655c58-965c-4518-894c-f593af91bf99" />

## Quick Start (macOS, non-technical)

### Step 0: Install Docker Desktop for Mac
1. Watch this quick setup video: https://www.youtube.com/watch?v=agkOZr27d3Y
2. Install Docker Desktop and launch it.
3. Wait until Docker says it is running.

### Step 1: Open Terminal
- On Mac: open `Terminal.app`.

### Step 2: Create a folder and clone Chronicle
```bash
mkdir -p ~/chronicle
cd ~/chronicle
git clone https://github.com/seanap/Chronicle.git
cd Chronicle
```

### Step 3: Create your `.env` from the example
```bash
cp .env.example .env
```

### Step 4: Start Chronicle
```bash
docker compose up -d
```

### Step 5: Open the app
- Dashboard (`View`): http://localhost:1609/dashboard
- Template Editor (`Build`): http://localhost:1609/editor
- Source Setup (`Sources`): http://localhost:1609/setup
- API Control (`Control`): http://localhost:1609/control

### Step 6: Add your credentials in `Sources`
- Go to `/setup` and fill in your source keys/tokens.
- Use the built-in Strava OAuth connect flow in the Strava card.

## Documentation
- API docs: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)
- Source setup guide: [`docs/SOURCES_SETUP.md`](docs/SOURCES_SETUP.md)
