# Chronicle API Documentation

Base URL (local):
- `http://localhost:1609`

Notes:
- Use `Content-Type: application/json` for `POST`/`PUT` requests with a JSON body.
- Most endpoints return JSON.
- UI pages (`/dashboard`, `/editor`, `/setup`, `/control`) return HTML.

## Health and Runtime

### GET `/health`
- Purpose: Liveness probe.
- Example:
```bash
curl http://localhost:1609/health
```

### GET `/ready`
- Purpose: Readiness probe (includes worker heartbeat checks).
- Example:
```bash
curl http://localhost:1609/ready
```

### GET `/latest`
- Purpose: Latest generated activity payload.
- Example:
```bash
curl http://localhost:1609/latest
```

### GET `/service-metrics`
- Purpose: Service-call metrics from the most recent processing cycle.
- Example:
```bash
curl http://localhost:1609/service-metrics
```

## Web Pages

### GET `/`
- Purpose: Redirects to dashboard.

### GET `/dashboard`
- Purpose: View page (heatmaps/trends UI).

### GET `/editor`
- Purpose: Build page (template editor UI).

### GET `/setup`
- Purpose: Sources page (credentials/OAuth UI).

### GET `/control`
- Purpose: Control page (GUI for API operations).

## Dashboard Data

### GET `/dashboard/data.json`
- Purpose: Dashboard JSON payload.
- Query params:
  - `force=true` (optional) to force rebuild.
- Response notes:
  - Includes stale-while-revalidate hints when serving stale cache:
    - `cache_state` (`stale` or `stale_revalidating`)
    - `revalidating` (boolean)
  - Includes Intervals metrics sections:
    - `intervals` (enabled/records/matched_activities)
    - `intervals_year_type_metrics` (year/type aggregate averages)
  - Daily `aggregates` entries may include optional metric keys:
    - `avg_pace_mps`
    - `avg_efficiency_factor`
    - `avg_fitness`
    - `avg_fatigue`
- Examples:
```bash
curl http://localhost:1609/dashboard/data.json
curl "http://localhost:1609/dashboard/data.json?force=true"
```

## Sources / Setup API

### GET `/setup/api/config`
- Purpose: Read effective setup config (secrets masked in response).
- Example:
```bash
curl http://localhost:1609/setup/api/config
```

### PUT `/setup/api/config`
- Purpose: Save setup values.
- Behavior:
  - Updates `.env` (canonical persisted config).
  - Mirrors values into runtime overrides so changes apply immediately.
- Example:
```bash
curl -X PUT http://localhost:1609/setup/api/config \
  -H "Content-Type: application/json" \
  -d '{"values":{"TIMEZONE":"America/New_York","ENABLE_WEATHER":true,"WEATHER_API_KEY":"your_key"}}'
```

### GET `/setup/api/env`
- Purpose: Render generated `.env` snippet.
- Example:
```bash
curl http://localhost:1609/setup/api/env
```

### GET `/setup/api/strava/status`
- Purpose: Strava OAuth/token status.
- Example:
```bash
curl http://localhost:1609/setup/api/strava/status
```

### POST `/setup/api/strava/oauth/start`
- Purpose: Start Strava OAuth flow (returns authorize URL).
- Optional JSON body:
  - `redirect_uri`
- Example:
```bash
curl -X POST http://localhost:1609/setup/api/strava/oauth/start \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri":"http://localhost:1609/setup/strava/callback"}'
```

### GET `/setup/strava/callback`
- Purpose: Strava OAuth callback endpoint.
- Called by Strava after authorization.

### POST `/setup/api/strava/disconnect`
- Purpose: Clear saved Strava access/refresh tokens.
- Example:
```bash
curl -X POST http://localhost:1609/setup/api/strava/disconnect
```

## Rerun API

### POST `/rerun/latest`
- Purpose: Reprocess latest activity.
- Example:
```bash
curl -X POST http://localhost:1609/rerun/latest
```

### POST `/rerun/activity/<activity_id>`
- Purpose: Reprocess a specific activity.
- Example:
```bash
curl -X POST http://localhost:1609/rerun/activity/17455368360
```

### POST `/rerun`
- Purpose: Reprocess latest, or optionally pass an activity id.
- Optional JSON body:
  - `activity_id` (integer)
- Example:
```bash
curl -X POST http://localhost:1609/rerun \
  -H "Content-Type: application/json" \
  -d '{"activity_id":17455368360}'
```

## Editor API (Profiles, Templates, Preview)

### GET `/editor/profiles`
- Purpose: List template profiles + working profile.

### PUT `/editor/profiles/<profile_id>`
- Purpose: Update profile settings (enabled/priority/etc).

### POST `/editor/profiles/working`
- Purpose: Set working profile.
- Example:
```bash
curl -X POST http://localhost:1609/editor/profiles/working \
  -H "Content-Type: application/json" \
  -d '{"profile_id":"default"}'
```

### GET `/editor/template`
- Purpose: Get active template.
- Query params:
  - `profile_id` (optional)

### PUT `/editor/template`
- Purpose: Save active template.

### GET `/editor/template/default`
- Purpose: Get factory default template.

### GET `/editor/template/versions`
- Purpose: List template versions.
- Query params:
  - `profile_id` (optional)
  - `limit` (optional)

### GET `/editor/template/version/<version_id>`
- Purpose: Fetch a specific template version.
- Query params:
  - `profile_id` (optional)

### GET `/editor/template/export`
- Purpose: Export active template bundle.
- Query params:
  - `profile_id` (optional)

### POST `/editor/template/import`
- Purpose: Import a template bundle.

### POST `/editor/template/rollback`
- Purpose: Roll back to a saved version.

### POST `/editor/validate`
- Purpose: Validate template syntax/contract.

### POST `/editor/preview`
- Purpose: Render preview from template and context.

### GET `/editor/fixtures`
- Purpose: List sample fixture names.

### GET `/editor/context/sample`
- Purpose: Return sample context payload.
- Query params:
  - `fixture` (optional)

### GET `/editor/schema`
- Purpose: Context schema for selected mode.
- Query params:
  - `context_mode` (`latest`, `sample`, `latest_or_sample`, `fixture`)

### GET `/editor/catalog`
- Purpose: Catalog of fields/groups for the editor.
- Query params:
  - `context_mode`
  - `fixture_name` (when mode is `fixture`)

### GET `/editor/snippets`
- Purpose: Snippet catalog for editor insertion.

### GET `/editor/starter-templates`
- Purpose: Starter templates.

## Editor Repository API

### GET `/editor/repository/templates`
- Purpose: List saved repository templates.

### GET `/editor/repository/template/<template_id>`
- Purpose: Get one repository template.

### PUT `/editor/repository/template/<template_id>`
- Purpose: Update repository template metadata/content.

### POST `/editor/repository/save_as`
- Purpose: Save current template as a new repository template.

### POST `/editor/repository/template/<template_id>/duplicate`
- Purpose: Duplicate an existing repository template.

### POST `/editor/repository/template/<template_id>/load`
- Purpose: Load repository template into active editor template.

### GET `/editor/repository/template/<template_id>/export`
- Purpose: Export one repository template bundle.

### POST `/editor/repository/import`
- Purpose: Import repository template bundle.

## Example Request Set

```bash
curl http://localhost:1609/health
curl http://localhost:1609/ready
curl -X POST http://localhost:1609/rerun/latest
curl -X POST http://localhost:1609/rerun/activity/17455368360
curl http://localhost:1609/dashboard/data.json
curl "http://localhost:1609/dashboard/data.json?force=true"
curl http://localhost:1609/setup/api/config
curl http://localhost:1609/editor/profiles
curl "http://localhost:1609/editor/template?profile_id=default"
```
