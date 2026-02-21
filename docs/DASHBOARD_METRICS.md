# Dashboard Metrics Reference

This document defines the year-card heatmap metrics in Chronicle View (`/dashboard`).

## Metric Controls
Each year card exposes six metric controls:

1. `Total Time`
2. `Total Distance`
3. `Total Elevation`
4. `Fit/Fat`
5. `Pace`
6. `Efficiency`

Selecting a control switches the heatmap from activity-count style to gradient mode for that metric.

## Fit/Fat Cycle
`Fit/Fat` is a cycling control, not two separate buttons.

Click sequence:

1. Off -> Fitness
2. Fitness -> Fatigue
3. Fatigue -> Off

Default display when not actively selected shows average Fitness for that year card period.

## Data Sources
- `Total Time`, `Total Distance`, `Total Elevation`: Strava activity totals.
- `Pace`, `Efficiency`, `Fitness`, `Fatigue`: Intervals.icu activity metrics joined to Strava activities.

Matching strategy:

1. Primary: `strava_activity_id`
2. Fallback: start-time ISO minute match

## Math and Aggregation
All metric aggregation is performed per year-card selection and per day bucket.

### Time
- Raw field: `moving_time`
- Period total: sum of seconds.

### Distance
- Raw field: `distance`
- Period total: sum of meters.

### Elevation
- Raw field: `elevation_gain`
- Period total: sum of meters.

### Pace (`avg_pace_mps`)
- Day value: weighted mean speed (m/s) for matched activities on that day.
- Period value: moving-time-weighted mean of day values.
- Heatmap strength: higher `avg_pace_mps` -> brighter cell.

### Efficiency (`avg_efficiency_factor`)
- Day value: moving-time-weighted mean EF for matched activities on that day.
- Period value: moving-time-weighted mean of day values.

### Fitness (`avg_fitness`)
- Day value: mean fitness across matched activities that day.
- Period value: activity-count-weighted mean of day values.

### Fatigue (`avg_fatigue`)
- Day value: mean fatigue across matched activities that day.
- Period value: activity-count-weighted mean of day values.

## Units and Display
Unit toggles affect formatting only, not stored values.

### Distance unit toggle
- Imperial: miles (`mi`)
- Metric: kilometers (`km`)

### Elevation unit toggle
- Imperial: feet (`ft`)
- Metric: meters (`m`)

### Pace display
- Derived from `avg_pace_mps`.
- Imperial mode: `mm:ss/mi`
- Metric mode: `mm:ss/km`

### Efficiency/Fitness/Fatigue display
- Efficiency: fixed to 2 decimals.
- Fitness/Fatigue: rounded integer values.

## Payload Fields (Dashboard JSON)
The dashboard payload (`/dashboard/data.json`) includes:

- `intervals`
  - `enabled`
  - `records`
  - `matched_activities`
- `intervals_year_type_metrics`
  - Nested by `year` -> `type`
  - Includes optional:
    - `avg_pace_mps`
    - `avg_efficiency_factor`
    - `avg_fitness`
    - `avg_fatigue`
- Daily `aggregates` entries may also include those same optional metric keys.

## Fallback Behavior
If Intervals.icu is disabled, unavailable, or no matching records are found:

- Existing Strava metrics continue working.
- `Fit/Fat`, `Pace`, and `Efficiency` show placeholders and do not activate gradient mode.
