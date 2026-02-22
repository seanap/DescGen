# Module Boundaries

This document tracks intentional module seams introduced to reduce regression risk in large orchestration paths.

## Goals
- Keep orchestration flows readable.
- Isolate external-service concerns from control flow.
- Enable smaller, focused tests per seam.
- Refactor in staged slices instead of one-shot rewrites.

## Activity Pipeline
- `chronicle/activity_pipeline.py`
  - Owns cycle orchestration (`run_once`), lock/job lifecycle, and final update sequencing.
  - Should coordinate steps, not embed every external integration detail.
- `chronicle/pipeline_context_collectors.py`
  - Owns external context gathering for:
    - Smashrun (`collect_smashrun_context`)
    - Weather (`collect_weather_context`)
    - Crono (`collect_crono_context`)
  - Accepts `run_service_call` as an injected dependency so behavior stays aligned with existing retry/cache/budget controls.

## Dashboard
- `chronicle/dashboard_data.py`
  - Owns payload assembly, refresh/revalidation orchestration, and persistence lifecycle.
- `chronicle/dashboard_response_modes.py`
  - Owns response-mode projection/validation:
    - `full` (default)
    - `summary`
    - `year`
  - Keeps response-shaping logic separate from fetch/rebuild orchestration.

## Ownership Intent
- New extraction work should follow this pattern:
  1. Add a seam module with narrow responsibility.
  2. Keep existing call sites via thin adapters/wrappers.
  3. Add focused seam tests before moving to the next extraction.
