# Chronicle API Documentation

Base URL (local):
- `http://localhost:1609`

Notes:
- Use `Content-Type: application/json` for `POST`/`PUT` requests with a JSON body.
- Most endpoints return JSON.
- UI pages (`/dashboard`, `/plan`, `/editor`, `/setup`, `/control`) return HTML.

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

### GET `/sources`
- Purpose: Canonical Sources journey route.

### GET `/build`
- Purpose: Canonical Build journey route.

### GET `/view`
- Purpose: Canonical View journey route.

## Dashboard Data

### GET `/dashboard/data.json`
- Purpose: Dashboard JSON payload.
- Query params:
  - `force=true` (optional) to force rebuild.
  - `mode=full|summary|year` (optional, default `full`)
  - `year=YYYY` (required when `mode=year`)
- Response notes:
  - `mode=summary` omits the `activities` array and returns `activity_count` to reduce payload size.
  - `mode=year` scopes `aggregates`, `intervals_year_type_metrics`, `activities`, and `types` to one year.
  - Invalid `mode`/`year` values return `400`.
  - Includes stale-while-revalidate hints when serving stale cache:
    - `cache_state` (`stale` or `stale_revalidating`)
    - `revalidating` (boolean)
  - Includes Intervals metrics sections:
    - `intervals` (enabled/records/matched_activities)
    - `intervals_year_type_metrics` (year/type aggregate averages)
  - `type_meta` is the canonical source for activity-type labels/accents used by frontend rendering.
  - Daily `aggregates` entries may include optional metric keys:
    - `avg_pace_mps`
    - `avg_efficiency_factor`
    - `avg_fitness`
    - `avg_fatigue`
- Examples:
```bash
curl http://localhost:1609/dashboard/data.json
curl "http://localhost:1609/dashboard/data.json?force=true"
curl "http://localhost:1609/dashboard/data.json?mode=summary"
curl "http://localhost:1609/dashboard/data.json?mode=year&year=2026"
```

## Plan Data

### GET `/plan/data.json`
- Purpose: Plan sheet payload (rows + weekly/monthly/trailing metrics).
- Query params:
  - `center_date=YYYY-MM-DD` (optional, defaults to today in configured timezone)
  - `window_days` (optional, clamped to `7..56`, default `14`)
- Response notes:
  - Includes `run_type_options`, `summary`, and `rows`.
  - `rows` include editable fields (`planned_input`, `run_type`, `is_complete`, `notes`) and computed metrics.
  - Invalid `center_date` returns `400`.
- Examples:
```bash
curl http://localhost:1609/plan/data.json
curl "http://localhost:1609/plan/data.json?center_date=2026-02-22&window_days=14"
```

### GET `/plan/today.json`
- Purpose: Lightweight payload for today's planned run only (widget/mobile companion usage).
- Response fields:
  - `date_local`: `YYYY-MM-DD`
  - `run_type`: string
  - `miles`: number (sum of planned sessions for today, or `planned_total_miles` fallback)
  - `workout_shorthand`: optional string (included when present, typically for `SOS`)
- Example:
```bash
curl http://localhost:1609/plan/today.json
```

### PUT `/plan/day/<date_local>`
- Purpose: Upsert one plan day and optional sessions.
- Path param:
  - `date_local` in `YYYY-MM-DD` format.
- Accepted JSON fields:
  - `distance`: string (`"6"`, `"6.5"`, `"6+4"`).
  - `planned_total_miles`: number or distance string.
  - `sessions`: array of numbers/objects (replaces all sessions for the day).
  - `run_type`: string.
  - `notes`: string.
  - `is_complete`: `true`, `false`, or `null` (`null` resets to auto mode).
- Response notes:
  - Returns saved `planned_total_miles`, normalized `distance_saved`, `session_count`, `sessions`, and effective completion state.
- Examples:
```bash
curl -X PUT http://localhost:1609/plan/day/2026-02-22 \
  -H "Content-Type: application/json" \
  -d '{"distance":"6+4","run_type":"Easy","is_complete":false}'

curl -X PUT http://localhost:1609/plan/day/2026-02-23 \
  -H "Content-Type: application/json" \
  -d '{"sessions":[6,4],"run_type":"SOS","is_complete":null}'
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

### GET `/editor/assistant/status`
- Purpose: Report whether the local Codex-backed editor assistant is available on this machine.

### POST `/editor/assistant/customize`
- Purpose: Send a customization request plus the current template to the local Codex CLI and receive paste-ready text back.
- Body:
```json
{
  "request": "Make the readiness line shorter.",
  "template": "Current Jinja template text",
  "context_mode": "sample",
  "fixture_name": "default",
  "profile_id": "default",
  "preview_text": "Optional current preview text",
  "selected_text": "Optional selected text from the editor"
}
```

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

## Agent Control API

These endpoints expose stable, resource-oriented APIs for remote Codex companions and future agent tooling. They are intentionally draft-oriented instead of allowing unrestricted direct writes.

Auth model:

- local requests can use the API without keys when `ENABLE_AGENT_CONTROL_API` is false and the caller is local
- remote read access uses `X-Chronicle-Agent-Key: <AGENT_CONTROL_READ_API_KEY>`
- remote apply access uses `X-Chronicle-Agent-Key: <AGENT_CONTROL_WRITE_API_KEY>`

### GET `/agent-control/handshake`
- Purpose: Protocol/version handshake plus assistant/provider summary.

### GET `/agent-control/capabilities`
- Purpose: Return supported resources and task names.

### GET `/agent-control/templates/active`
- Purpose: Get the active template and current base version.
- Query params:
  - `profile_id` (optional)

### GET `/agent-control/profiles`
- Purpose: List profiles and working profile.

### GET `/agent-control/profiles/<profile_id>`
- Purpose: Get one profile document and base version.

### GET `/agent-control/workouts`
- Purpose: List workout definitions.

### GET `/agent-control/workouts/<workout_id>`
- Purpose: Get one workout document and base version.

### GET `/agent-control/plans/week`
- Purpose: Return one plan week plus its base version.
- Query params:
  - `week_start_local` (optional, defaults to the next local week start)

### GET `/agent-control/plans/next-week-context`
- Purpose: Return focused planning context for `plan-next-week` tasks.
- Query params:
  - `week_start_local` (optional)

### GET `/agent-control/drafts`
- Purpose: List durable drafts.
- Query params:
  - `resource_kind` (optional)

### POST `/agent-control/drafts`
- Purpose: Create a durable draft and optionally validate it immediately.
- Body fields:
  - `resource_kind`: `template|profile|workout|plan_week`
  - `payload`: resource payload object
  - `title` (optional)
  - `base_version` (optional)
  - `metadata` (optional object)
  - `validate` (optional, default `true`)

### GET `/agent-control/drafts/<draft_id>`
- Purpose: Get one durable draft.

### PUT `/agent-control/drafts/<draft_id>`
- Purpose: Update a draft payload/title/metadata before validation/apply.

### POST `/agent-control/drafts/<draft_id>/validate`
- Purpose: Validate a draft and store the validation result.

### POST `/agent-control/drafts/<draft_id>/apply`
- Purpose: Dry-run or apply a validated draft through Chronicle’s live save paths.
- Body fields:
  - `dry_run` (optional boolean)
  - `expected_version` (optional optimistic-lock version)

### GET `/agent-control/jobs`
- Purpose: List durable jobs.
- Query params:
  - `task_kind` (optional)

### GET `/agent-control/jobs/<job_id>`
- Purpose: Get one durable job.

### GET `/agent-control/audit`
- Purpose: Return recent audit events.
- Query params:
  - `limit` (optional, default `100`, max `500`)

## Agent Task API

These endpoints create Codex-backed jobs that return reviewable drafts instead of applying changes immediately.

### POST `/agent/tasks/plan-next-week`
- Purpose: Ask the configured Codex provider to draft the next week’s plan.
- Body fields:
  - `request` (required)
  - `week_start_local` (optional)
  - `source` (optional)

Response notes:

- creates a durable `job`
- creates a `plan_week` draft
- returns `awaiting_approval` when the draft is ready for review

### POST `/agent/tasks/bundle-create`
- Purpose: Ask the configured Codex provider to draft a related bundle of profile/template/workout assets.
- Body fields:
  - `request` (required)
  - `profile_id` (optional target profile id)
  - `workout_id` (optional target workout id)
  - `source` (optional)

Response notes:

- creates a durable `job`
- may create multiple drafts
- template drafts targeting a not-yet-applied profile are allowed, but publishing still requires the profile to exist first

## Example Request Set

```bash
curl http://localhost:1609/health
curl http://localhost:1609/ready
curl -X POST http://localhost:1609/rerun/latest
curl -X POST http://localhost:1609/rerun/activity/17455368360
curl http://localhost:1609/dashboard/data.json
curl "http://localhost:1609/plan/data.json?center_date=2026-02-22&window_days=14"
curl -X PUT http://localhost:1609/plan/day/2026-02-22 -H "Content-Type: application/json" -d '{"distance":"6+4","run_type":"Easy"}'
curl "http://localhost:1609/dashboard/data.json?force=true"
curl http://localhost:1609/setup/api/config
curl http://localhost:1609/editor/profiles
curl "http://localhost:1609/editor/template?profile_id=default"
```
