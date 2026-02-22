# Plan Sheet V1 Design

## 1. Goal
Add a new Chronicle sheet/page, `Plan`, that replicates the speed and clarity of your spreadsheet workflow for planning mileage while auto-linking completed mileage from Chronicle/Strava.

Primary outcomes:
- Plan quickly with keyboard-first daily mileage entry.
- See risk/load signals at a glance with red/green/blue cues.
- Keep today centered with trailing 2 weeks + next 2 weeks visible.
- Support doubles/triples (multiple runs per day).
- Preserve simple run-type planning now, with structured workout support later.

## 2. Reverse-Engineered Spreadsheet Components
From `local/excel_schedule_template.png`, the grid is functionally:

- `Date`
- `Distance (mi)` (editable, color-coded)
- `Run Type` (dropdown)
- Weekly block metrics (merged by week):
  - `Total Weekly Mileage`
  - `Week over Week change`
  - `Long%`
- Monthly block metrics:
  - `Total Monthly Mileage`
  - `Month over Month change`
- Rolling stress/consistency metrics per day:
  - `mi / T30D avg`
  - `Cumulative Mileage (Trailing 7 Day)`
  - `T7D/P7D`
  - `Cumulative Mileage (Trailing 30 Day)`
  - `T30D/P30D`
  - `Avg. mi/day (Trailing 30-day)`
- Completion indicator (checkbox-like) for completed dates.

## 3. Metric Definitions (Plan-Compatible)
Use `effective_miles(d)` for calculations:
- Past/today: `actual_miles(d)` if available, else `planned_miles(d)`.
- Future: `planned_miles(d)`.

Definitions:
- `weekly_total(w) = sum(effective_miles(d)) for dates in week w`
- `wow_change(w) = (weekly_total(w) - weekly_total(w-1)) / weekly_total(w-1)`
- `long_run_miles(w) = max(effective_miles(d)) in week w where run_type in {Long Road, Long Moderate, Long Trail, Race}`
- `long_pct(w) = long_run_miles(w) / weekly_total(w)`
- `monthly_total(m) = sum(effective_miles(d)) in month m`
- `mom_change(m) = (monthly_total(m) - monthly_total(m-1)) / monthly_total(m-1)`
- `t7(d) = sum(effective_miles(d-6..d))`
- `t30(d) = sum(effective_miles(d-29..d))`
- `avg30(d) = t30(d) / 30`
- `mi_t30_ratio(d) = effective_miles(d) / avg30(d)`
- `t7_p7_ratio(d) = t7(d) / t7(d-7)`
- `t30_p30_ratio(d) = t30(d) / t30(d-30)`

New science-backed guardrail (add in V1):
- `session_spike_ratio = single_session_miles / longest_single_session_last_30_days`
- Highlight if `> 1.10`.

## 4. Color Rules (Red/Green/Blue)
Use user-configurable thresholds with defaults:

- `wow_change`:
  - Blue: `< 0%` (recovery/taper)
  - Green: `0% to 8%`
  - Yellow: `>8% to 12%`
  - Red: `>12%`
- `long_pct`:
  - Blue: `<20%`
  - Green: `20% to 30%`
  - Yellow: `>30% to 35%`
  - Red: `>35%`
- `mi_t30_ratio`:
  - Blue: `<0.75`
  - Green: `0.75 to 1.40`
  - Yellow: `>1.40 to 1.80`
  - Red: `>1.80`
- `t7_p7_ratio`:
  - Blue: `<0.90`
  - Green: `0.90 to 1.20`
  - Yellow: `>1.20 to 1.35`
  - Red: `>1.35`
- `session_spike_ratio`:
  - Green: `<=1.10`
  - Yellow: `>1.10 to 1.30`
  - Red: `>1.30`

Note: long-run `%` thresholds are practical coaching heuristics + your current preference, while session-spike thresholds are directly evidence-backed.

## 5. UX Plan (Low Friction First)
Default view:
- 29 rows centered on today: `today-14` to `today+14`.
- Today pinned visually.
- Weekly blocks and monthly blocks rendered with merged-style visual grouping.

Fast entry:
- Mileage cell edit, `Enter` saves and moves to next day mileage cell.
- Arrow keys navigate cells.
- `Tab` moves across editable fields (`miles`, `run_type`, optional note).

Doubles/triples:
- Day has `sessions[]` under one date.
- Quick syntax in mileage cell: `6+4` (double), `5+3+2` (triple).
- Expanded row editor for per-session run type/workout later.

Completion behavior:
- Auto-check complete when `actual_miles(d) > 0` for past dates.
- Manual override allowed (rest days, cross-training day).

## 6. Data Model (SQLite runtime DB)
Add tables:

- `plan_days`
  - `date_local` TEXT PK (`YYYY-MM-DD`)
  - `timezone` TEXT
  - `run_type` TEXT
  - `planned_total_miles` REAL
  - `actual_total_miles` REAL (derived cache)
  - `is_complete` INTEGER
  - `notes` TEXT
  - `updated_at_utc` TEXT

- `plan_sessions`
  - `session_id` TEXT PK
  - `date_local` TEXT FK -> `plan_days.date_local`
  - `ordinal` INTEGER
  - `planned_miles` REAL
  - `actual_miles` REAL
  - `run_type` TEXT
  - `workout_code` TEXT (future)
  - `source_activity_id` TEXT (Strava link)
  - `updated_at_utc` TEXT

- `plan_settings`
  - `key` TEXT PK
  - `value_json` TEXT
  - `updated_at_utc` TEXT

## 7. Backend/API Plan
New routes:
- `GET /plan` -> render `templates/plan.html`
- `GET /plan/data.json?center_date=YYYY-MM-DD&window_days=14`
- `PUT /plan/day/<date_local>` (planned miles/run type/notes/complete)
- `POST /plan/day/<date_local>/sessions`
- `PATCH /plan/session/<session_id>`
- `DELETE /plan/session/<session_id>`

Service behavior:
- Pull recent Strava activities (existing normalized paths) and map run-like activities to `actual_miles` by local date.
- Recompute all derived metrics server-side so UI is simple and deterministic.

## 8. Frontend Plan
Add:
- `templates/plan.html`
- `static/plan.js`
- `static/plan.css`
- nav item in `_app_shell_nav.html`: `Plan`

Rendering:
- Spreadsheet-style table with sticky header and week/month visual bands.
- CSS classes for state colors (`metric-good`, `metric-easy`, `metric-hard`, `metric-caution`).
- Keyboard controller for rapid entry and row-to-row Enter flow.

## 9. Integration Points
- Chronicle pipeline can emit optional template context field later:
  - `activity_planned_workout`
  - `activity_planned_run_type`
- Mapping by `activity_id` or same-day closest-start-time session.

## 10. Future Scope (Explicit)
- Structured SOS workout shorthand parser (e.g. `3x1mi@10k/2:00j`).
- Garmin workout export + calendar push (once Garmin API capability is validated).
- Plan adherence analytics: planned vs actual by week, by run type, by block.

## 11. Phased Delivery
- Phase 1: DB + API + read-only Plan table + derived metrics.
- Phase 2: Fast inline editing + keyboard nav + doubles/triples.
- Phase 3: completion auto-sync + plan-vs-actual views.
- Phase 4: workout shorthand scaffolding + description metadata emission.

## 12. Evidence Used For Defaults
- Frandsen et al., BJSM 2025: single-session spikes >10% vs longest 30-day run increase injury rate; week-to-week ratio not associated.
  - https://pubmed.ncbi.nlm.nih.gov/40623829/
- Ramskov et al., J Athl Train 2022: >10% weekly progression with pace progression did not show significant positive interaction in this cohort.
  - https://pubmed.ncbi.nlm.nih.gov/34543419/
- Rasmussen et al., Int J Sports Phys Ther 2013: for marathon prep, <30 km/week associated with higher injury risk vs 30-60 km/week.
  - https://pubmed.ncbi.nlm.nih.gov/23593549/
- Oliveira et al., Sports Med 2024 and Rosenblat et al., Sports Med 2025: intensity distribution effects vary by athlete level; supports configurable training-load heuristics over rigid single rule.
  - https://pubmed.ncbi.nlm.nih.gov/38717713/
  - https://pubmed.ncbi.nlm.nih.gov/39888556/
