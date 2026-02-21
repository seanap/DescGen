# Dashboard Intervals Metrics Plan

## Goal
Add Intervals.icu-powered dashboard metrics for Pace, Fitness/Fatigue, and Efficiency so the View heatmap can support richer gradient modes without degrading load performance.

## UX Target
- Keep existing year heatmap card interactions (`Total Time`, `Total Distance`, `Total Elevation`).
- Add new heatmap modes:
  - `Fit/Fat` (single control with cycle: Off -> Fitness -> Fatigue -> Off)
  - `Pace`
  - `Efficiency`
- Move `Total Activities` out of stat-buttons and into title text (example: `2025 - Total Activities 420`).
- Tighten stat-card/button spacing so six metric controls fit cleanly.

## Data Contract Additions
- Day-level aggregate entries should include optional Intervals metrics:
  - `avg_pace_mps`
  - `avg_efficiency_factor`
  - `avg_fitness`
  - `avg_fatigue`
- Payload root should expose Intervals meta:
  - `intervals.enabled`
  - `intervals.records`
  - `intervals.matched_activities`
- Payload root should include `intervals_year_type_metrics` for fast year/type averages and future stat-card values.

## Matching Strategy
- Primary match: Intervals item `strava_activity_id` to Strava activity id.
- Fallback match: ISO minute key from activity start time.
- Ignore records with no usable metrics.

## Metric Aggregation Rules
- `avg_pace_mps`: moving-time-weighted mean of pace (m/s).
- `avg_efficiency_factor`: moving-time-weighted mean.
- `avg_fitness`: arithmetic mean across matched activities.
- `avg_fatigue`: arithmetic mean across matched activities.

## Phases

### Phase A (Backend contract + aggregation)
- Add Intervals dashboard metric fetch helper.
- Enrich dashboard activities/aggregates/year-type rollups with Intervals metrics.
- Add tests for payload enrichment and matching behavior.
- Keep frontend unchanged in this phase.

### Phase B (Frontend controls + interactions)
- Add `Pace`, `Efficiency`, and cycling `Fit/Fat` controls.
- Remove `Total Activities` clickable card; move count into year title.
- Wire new metric keys into heatmap gradient mode.

### Phase C (Polish + validation)
- Tighten stat control layout and spacing.
- Cross-device validation (desktop/mobile).
- Add docs updates with metric definitions and unit behavior.

## Risks / Gotchas
- Intervals records may not include direct Strava ids for all activities.
- Pace needs consistent unit conversion handling when UI switches mi/km.
- Fitness/Fatigue are state metrics; users may misread day-level gradients without labels.

## Success Criteria
- Dashboard payload contains Intervals metric fields with deterministic behavior.
- Existing dashboard functionality remains intact when Intervals is unavailable.
- Tests cover matching and aggregation edge cases.
