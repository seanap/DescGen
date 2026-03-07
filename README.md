# <img src="./static/chronicle.png" alt="Chronicle icon" width="30" />hronicle

<p align="center">
<img height="318" alt="chronicle_banner_short" src="https://github.com/user-attachments/assets/110b0df9-f376-403a-95c3-a900ba14550b" />  
</p>

<p align="center">Chronicle your activity with automated Strava descriptions.</p>
<p align="center">Chronicle your activity history through heatmaps.</p>
<p align="center">Chronicle your workout sessions and send to garmin.</p>

#

This app is built for someone that likes self-hosting their own docker apps, who uses Strava but hates writing out descriptions, and who wears a Garmin watch.

## Key Features
- Auto-processes new activities.  
- Activity Profile matching,  
  - yaml Profile Builder.  
- Custom Description Templates per profile,  
  - Jinja Template Builder  
- Plan and wargame your next sessions.  
  - yaml Workout Builder  
  - Send to your garmin watch workout calendar.  

## Includes a polished local web app:
  - `View` (`/dashboard`) for long-term trends.
  - `Plan` (`/plan`) for planning your next move.
  - `Build` (`/editor`) for template editing and preview.
  - `Sources` (`/setup`) for source credentials and OAuth.
  - `Control` (`/control`) for one-click API operations.

## Screenshots
<img width="1915" height="1923" alt="Screenshot 2026-03-07 120436" src="https://github.com/user-attachments/assets/d44ccc82-9439-4a38-b034-c07406f1743e" />
<img width="2900" height="1922" alt="Screenshot 2026-02-22 231607" src="https://github.com/user-attachments/assets/35f5f8e6-4cc4-4787-9f08-c2a7687e2398" />
<img width="2006" height="1943" alt="Screenshot 2026-02-20 115619" src="https://github.com/user-attachments/assets/ec734164-a7e0-4b60-8131-9c4968b4f858" />
<img width="2399" height="926" alt="Screenshot 2026-02-20 115710" src="https://github.com/user-attachments/assets/9ef5e175-ea91-42b6-b430-faa68060493e" />
<img width="2336" height="1939" alt="Screenshot 2026-02-20 115752 REDACTED" src="https://github.com/user-attachments/assets/6a4a2e88-c7c0-4692-ac33-5251b52d753d" />


## Quick Start

#### Step 0: Install Docker Desktop for Mac
1. Watch this quick setup video: https://www.youtube.com/watch?v=agkOZr27d3Y
2. Install Docker Desktop and launch it.

#### Step 1: Open Terminal
- Open `Terminal.app`.

#### Step 2: Create a folder and clone Chronicle Project
```bash
mkdir -p ~/docker/chronicle
cd ~/docker/chronicle
git clone https://github.com/seanap/Chronicle.git
cd Chronicle
cp .env.example .env
```
#### Step 3: Start Chronicle
```bash
docker compose up -d --build
```
- Re-run the same command after pulling new code so the latest backend and frontend assets are rebuilt into the image.

#### Step 4: Open the app
```bash
http://localhost:1609
```
#### Step 5: Add your credentials in `Sources`
- Go to `Sources` and fill in your source keys/tokens.
- Source setup guide: [`docs/SOURCES_SETUP.md`](docs/SOURCES_SETUP.md)

## Using Chronicle

#### Auto-Descriptions:
-  Go to Build page >
  - Template Workshop Drawer >
    - Duplicate default Template, save-as, and load >
    - Modify Advanced Template jinja >
    - Confirm preview then `Save + Publish`
  - Profile Workshop >
    - Select Profile from dropdown >
    - Enable >
    - `Set Working`
  - Template Workshop >
    - Duplicate profile Template, save-as, and load >
    - Modify Advanced Template jinja >
    - `Save + Publish`
#### Plan
- Go to Plan page
  - Pace Workshop drawer >
    - Calcule Recent Race >
    - Set Marathon Goal
  - Type daily mileage targets >
    - Set run type to SOS to enable session workout >
    - select workout shorthand from dropdown, modify if needed
  - Workout Workshop drawer >
    - select template from dropdown >
    - modify yaml to customize, `Save`
#### View
- Go to View page >
  - Scope drawer >
    - Enable Years and Activity Types
  - Click the top Activity Type buttons to filter
  - Click the Data buttons to filter
  - Click the bottom Most Active buttons to filter

## Documentation
- API docs: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)
- Android widget companion: [`docs/ANDROID_WIDGET_COMPANION.md`](docs/ANDROID_WIDGET_COMPANION.md)
- Android widget APK downloads: [GitHub Releases](https://github.com/seanap/Chronicle/releases)
- Misery Index report: [`docs/MISERY_INDEX_REPORT.md`](docs/MISERY_INDEX_REPORT.md)

## Thanks!
Borrowed ideas, inspiration, code, and style from the following great projects:
- https://github.com/aspain/git-sweaty Dashboard inspiration
- https://github.com/yeekang-0311/garmin_planner Workout builder and Send to Garmin
- https://www.home-assistant.io/docs/configuration/templating/ Jinja Template builder inspired by HomeAssistant Templating
- https://activitystat.com/ For the auto stat description inspiration
- This project was built using the [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) with assistance from CODEX GPT5.4
