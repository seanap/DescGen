# Run Nut x Everest Challenge Profile

Chronicle ships a disabled challenge profile for the May 2026 stacked running challenge:

- `Run Nut`: 300 miles of running in May.
- `Conquered Everest`: 8,848 meters / 29,029 feet of cumulative elevation gain in May.
- `Royale Hill`: custom summit counter for `34.24659,-83.96339` within a `60ft` radius.

The built-in profile id is `300-30-challenge`, and the visible profile label is `300/30 Challenge`.

## Activation

The profile is off by default so normal activity processing is unchanged.

To activate it for May:

1. Open `Build` (`/editor`).
2. Open the Profile Workshop.
3. Select `300/30 Challenge`.
4. Enable the profile.
5. Optionally set it as the working profile for preview/editing.

The profile only matches qualifying May 2026 running activities:

- `Run`
- `TrailRun`
- `VirtualRun`

It excludes strength-like activities and only matches activity dates from `2026-05-01` through `2026-05-31`, using the configured Chronicle timezone.

## Seed Template

The profile seed template leads with the challenge scoreboard:

```text
🔥 Run Nut x Everest - Day 15/31
🟢 +6.3mi | 🟢 +112'
🏃 Today: 13.2 mi | +1,420' | 🏔️ 6
📈 Total: 151.8 mi | +15,112' | 🏔️ 110
```

The lower section keeps the default streak, awards, and technical training data. It intentionally omits the default historical totals for past 7 days, past 30 days, and year-to-date.

## Pace Indicators

The second line shows whether the challenge is ahead or behind the required average pace.

Daily targets:

- Distance: `9.7mi/day`
- Elevation: `937ft/day`

The distance indicator is:

```text
May distance total - (challenge day * 9.7)
```

The elevation indicator is:

```text
May elevation total - (challenge day * 937)
```

Status colors:

- `🟢`: delta is positive.
- `🟡`: delta is `0` through `-10`.
- `🔴`: delta is below `-10`.

These values are exposed to Jinja under `challenge.pace`.

## Challenge Context Fields

The template receives a `challenge` object with these stable fields:

```text
challenge.day
challenge.days
challenge.date
challenge.start_date
challenge.end_date
challenge.days_remaining

challenge.goals.distance_miles
challenge.goals.elevation_feet
challenge.goals.elevation_meters
challenge.goals.daily_distance_miles
challenge.goals.daily_elevation_feet
challenge.goals.daily_elevation_meters

challenge.pace.daily_distance_miles
challenge.pace.daily_elevation_feet
challenge.pace.expected_distance_miles
challenge.pace.expected_elevation_feet
challenge.pace.distance_delta_miles
challenge.pace.elevation_delta_feet
challenge.pace.distance_delta_display
challenge.pace.elevation_delta_display
challenge.pace.distance_status_emoji
challenge.pace.elevation_status_emoji

challenge.today.distance_miles
challenge.today.elevation_feet
challenge.today.elevation_meters
challenge.today.run_count
challenge.today.royale_hill_summits

challenge.totals.distance_miles
challenge.totals.distance_remaining_miles
challenge.totals.distance_percent
challenge.totals.elevation_feet
challenge.totals.elevation_meters
challenge.totals.elevation_remaining_feet
challenge.totals.elevation_remaining_meters
challenge.totals.elevation_percent
challenge.totals.run_count
challenge.totals.royale_hill_summits

challenge.royale_hill.latitude
challenge.royale_hill.longitude
challenge.royale_hill.radius_feet
challenge.royale_hill.current_activity_summits
challenge.royale_hill.current_activity_source
```

## Data Sources

Distance totals are computed from Strava activity history already collected for period stats. The current processed activity is merged into that history so doubles and triples on the same local day are included.

Elevation totals are computed from Smashrun activities when Smashrun is enabled and available. This keeps the challenge elevation aligned with the source used for the badge target.

Royale Hill summits are computed from Strava `latlng` activity streams. Chronicle counts each transition from outside the summit radius to inside the `60ft` radius as one summit. If streams are unavailable, Chronicle falls back to the activity polyline when present. Per-activity summit counts are persisted in runtime state so totals remain stable after processing.

## Operational Notes

- Keep `ENABLE_SMASHRUN=true` and `SMASHRUN_ACCESS_TOKEN` configured for elevation totals.
- The Strava token must have access to activity streams for Royale Hill summit counting.
- The profile can be enabled before May, but it will not match non-May activities.
- If a run is reprocessed, Royale Hill summit counts for that activity are recalculated and replaced.
