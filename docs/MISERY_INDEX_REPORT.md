# Misery Index Running Normalization Report

This document is the canonical technical breakdown of Chronicle's Misery Index implementation.
It is based on:
- `local/MISERY_INDEX_RUNNING_NORMALIZATION_REPORT.local.md`
- `chronicle/stat_modules/misery_index.py`
- `tests/test_misery_index.py`

Last reviewed: 2026-02-21

## 1. Severity Buckets and Emoji Mapping

Chronicle separates two concepts:
- **Severity**: how bad conditions are (`misery.index.value`)
- **Polarity**: whether misery is mainly hot-driven or cold-driven (`misery.index.polarity`)

Severity thresholds:

| Misery Index | Severity |
| --- | --- |
| `<= 5` | `ideal` |
| `> 5` to `<= 15` | `mild` |
| `> 15` to `<= 30` | `moderate` |
| `> 30` to `<= 50` | `high` |
| `> 50` to `<= 75` | `very_high` |
| `> 75` to `<= 100` | `extreme` |
| `> 100` | `death` |

Implemented in: `chronicle/stat_modules/misery_index.py` (`get_misery_index_severity`).

Emoji mapping depends on severity plus polarity:

| Severity | Neutral | Hot Polarity | Cold Polarity |
| --- | --- | --- | --- |
| `ideal` | `😀` | `😀` | `😀` |
| `mild` | `😒` | `😒` | `😒` |
| `moderate` | `😓` | `😓` | `😓` |
| `high` | `😭` | `😭` | `😭` |
| `very_high` | `😰` | `🥵` | `😰` |
| `extreme` | `😡` | `😡` | `🥶` |
| `death` | `☠️` | `☠️` | `☠️` |

Implemented in: `chronicle/stat_modules/misery_index.py` (`get_misery_index_emoji`, `get_misery_index_description`).

Why ideal is short (`0-5`):
- The model is intentionally strict: "ideal" means near Goldilocks conditions, not merely acceptable.
- This is reinforced by tests requiring a true neutral profile to map to `0.0`.
- See `tests/test_misery_index.py` (`test_goldilocks_profile_scores_neutral_center`).

## 2. Research Basis and Design Intent

The design target is running-specific environmental burden, not a generic weather comfort score.

Research themes used when shaping the model (from local report and listed sources):

1. Temperature is primary for endurance performance.
- Marathon and endurance studies consistently show performance drops outside a relatively narrow optimal thermal band.
- This motivated making thermal terms the strongest contributors.

2. Apparent temperature matters by regime.
- Heat Index and Wind Chill are both standard but valid in different conditions.
- Chronicle blends ambient, heat-index-like, and wind-chill-like signals into a running-oriented apparent temperature.

3. Wind has two effects.
- Wind can increase effort cost (aero drag / mechanical burden), and can change thermal strain depending on hot vs cold context.
- Chronicle models both baseline wind discomfort and a separate stronger-wind effort term.

4. Humidity and dew point interact with heat.
- Moisture burden is not only RH; dew point carries strong signal for muggy/hot stress.
- Chronicle uses dew and RH plus heat-humidity interaction terms.

5. Rain and snow effects are contextual.
- Cold wet + wind can be substantially worse than dry cold.
- Chronicle has cold-rain amplification and snow/frozen-precip logic.

6. Solar load is proxied conservatively.
- Cloud and day/night are used as practical proxies due available data, with moderate weighting.

## 3. Math and Functions (Detailed)

This section describes the implemented math in `calculate_misery_index_components`.

### 3.1 Helper primitives

- Clamp:
  - `clamp(x, lo, hi) = min(max(x, lo), hi)`
- Smoothstep:
  - `t = clamp((x - e0)/(e1 - e0), 0, 1)`
  - `smoothstep = t^2 * (3 - 2t)`
- Positive hinge:
  - `hinge_plus(x, e, s) = max(0, (x - e)/s)`
- Negative hinge:
  - `hinge_minus(x, e, s) = max(0, (e - x)/s)`
- Saturating transform:
  - `sat(v, s) = v / (v + s)` for `v > 0`, else `0`
- Banded penalty:
  - `low = w_low * hinge_minus(x, L, s_low)^2`
  - `high = w_high * hinge_plus(x, U, s_high)^2`
  - `band_penalty = low + high`
- Numerically stable risk helpers:
  - `softplus(z) = ln(1 + exp(z))` (with stable guards)
  - `logsumexp(z_i) = z_max + ln(sum(exp(z_i - z_max)))`

### 3.2 Thermal driver and running normalization

Inputs:
- `temp` (ambient), `dew`, `rh`, `wind`, and optional weather context.

Derived:
- `hi` = heat index estimate (or provided value)
- `wc` = wind chill estimate (or provided value)

Running-normalized apparent temperature:

1. Hot weight:
- `w_hot = smoothstep(max(temp, hi), 78, 90)`

2. Cold weight:
- `w_cold = 0.4 * smoothstep(52 - temp, 0, 14) * smoothstep(wind, 2.5, 6.5)`

3. Normalize hot/cold blend if sum > 1:
- `w_hot = w_hot / (w_hot + w_cold)`
- `w_cold = w_cold / (w_hot + w_cold)` (same original denominator)

4. Neutral weight:
- `w_neutral = max(0, 1 - w_hot - w_cold)`

5. Apparent running temperature:
- `apparent = w_neutral*temp + w_hot*hi + w_cold*wc`

### 3.3 Discomfort head (broad additive burden)

Core penalties:
- `temp_points = band_penalty(apparent, L=50, U=55, scales 10/12, weights 1.0/1.2)`
- `dew_points = band_penalty(dew, L=30, U=55, scales 20/12, weights 0.2/0.75)`
- `rh_points = band_penalty(rh, L=30, U=70, scales 25/20, weights 0.1/0.2)`

Interactions:
- `heat_humidity_points` includes:
  - strong term on `apparent > 70` and `dew > 58`
  - secondary term on `apparent > 75` and `rh > 65`
- `stagnant_hot_points` rises when wind is very low and apparent is high.

Wind burden:
- Base wind band around `IDEAL_WIND_LOW_MPH=1.5` to `IDEAL_WIND_HIGH_MPH=5.0`
- Additional `strong_wind_effort_points` for stronger winds
- Additional `breeze_drag_points`
- Additional `wind_cold_exposure_points` when strong wind intersects cold apparent conditions

Day/cloud:
- Daytime solar hot contribution grows with lower cloud.
- Cold overcast contribution grows in cold + cloudy daytime states.

Precipitation:
- Rain signal from observed precip and fallback chance logic
- Snow signal from chance + condition-text + boolean flags
- Separate terms:
  - `rain_hot_points`
  - `rain_cold_points`
  - `rain_temperate_points`
  - `cold_rain_extra`
  - `rain_hint_points`
  - `snow_points`

Aggregate raw discomfort:
- `discomfort_raw = sum(all discomfort penalties)`

Scaled discomfort score:
- if `discomfort_raw <= 20`:
  - `discomfort_score = 4.0 * discomfort_raw`
- else compressed tail:
  - `discomfort_score = 4.0 * (20 + 0.45*(discomfort_raw - 20))`

This keeps normal ranges expressive while preventing unbounded blow-up.

### 3.4 Risk head (physiologic hazard regimes)

A second path models dangerous regimes, distinct from normal discomfort.

Gates:
- `heat_gate = smoothstep(apparent, 82, 98)`
- `cold_gate = smoothstep(45 - apparent, 0, 20)`

Modes:
- `heat_mode`: activates from high heat index, high dew, high RH, stagnant air, and sun load.
- `cold_mode`: activates from wind chill, low ambient/dew, and stronger wind.
- `cold_wet_mode`: activates with wet load under cold and wind.
- `storm_mode`: explicit boosts for freezing mix / blizzard-like combinations.

Mode aggregation:
- `risk_raw = logsumexp([heat_mode, cold_mode, cold_wet_mode, storm_mode])`

Risk tail conversion:
- `risk_tail_activation = softplus((risk_raw - 8.1)/1.5) - softplus((2.5 - 8.1)/1.5)`
- `risk_tail_points = 12.5 * max(0, risk_tail_activation)`

Final score:
- `raw_score = discomfort_score + risk_tail_points`
- `score = max(0, raw_score)` then rounded for output

### 3.5 Polarity from additive loads (no cancellation)

Severity score never subtracts hot from cold.

Instead, hot and cold directional loads are computed separately:
- `hot_points = sum(hot-side contributors) + 0.20*heat_mode`
- `cold_points = sum(cold-side contributors) + 0.20*(cold_mode + cold_wet_mode + storm_mode)`

Polarity rule:
- `delta = hot_points - cold_points`
- hot if `delta > 0.35`
- cold if `delta < -0.35`
- else neutral

This preserves additive severity while still allowing a meaningful "hot vs cold" emoji.

## 4. Calibration and Validation

### 4.1 Calibration intent

The model is tuned so:
- near-Goldilocks weather maps near zero,
- common "not great" days land in mild/moderate/high,
- severe weather is pushed by risk tail into extreme/death.

### 4.2 Test-backed behavioral invariants

Current tests enforce key properties:

1. Bucket mapping is stable.
- `tests/test_misery_index.py` (`test_misery_buckets`)

2. True Goldilocks maps to exactly `0.0`.
- `tests/test_misery_index.py` (`test_goldilocks_profile_scores_neutral_center`)

3. No sharp discontinuities around thermal boundaries.
- `tests/test_misery_index.py` (`test_no_large_jump_at_thermal_transition_edges`)

4. No major jump at precipitation thresholds.
- `tests/test_misery_index.py` (`test_no_large_jump_at_precip_thresholds`)

5. Wind outside ideal band increases burden.
- `tests/test_misery_index.py` (`test_wind_outside_ideal_band_reduces_score`)

6. Strong wind alone can be severe but not necessarily death.
- `tests/test_misery_index.py` (`test_strong_wind_alone_stays_below_death_threshold`)

7. True heat hazards cross death threshold.
- `tests/test_misery_index.py` (`test_true_heat_hazard_crosses_death_threshold`)

8. Cold wet hazards can be extreme without always crossing death.
- `tests/test_misery_index.py` (`test_true_cold_wet_hazard_stays_extreme_below_death`)

## 5. Limitations

1. Wind direction vs route direction is not modeled.
- Available weather wind is ambient; headwind/tailwind specificity is missing.

2. Cloud is only a proxy for solar radiation.
- No direct radiation sensor in this pipeline.

3. Microclimate mismatch is unavoidable.
- Weather station values may differ from exact route conditions.

4. Individual physiology varies.
- Heat/cold tolerance, acclimation, clothing, hydration, and pace strategy are user-specific.

5. Event type differences.
- The model is running-oriented and may be less ideal for non-running activities.

## 6. Sources

### 6.1 Project-local sources

- Implementation: `chronicle/stat_modules/misery_index.py`
- Behavioral tests: `tests/test_misery_index.py`
- Research planning note: `local/MISERY_INDEX_RUNNING_NORMALIZATION_REPORT.local.md`

### 6.2 External references listed in the local research report

1. https://pubmed.ncbi.nlm.nih.gov/17473775/
2. https://pubmed.ncbi.nlm.nih.gov/22649525/
3. https://pubmed.ncbi.nlm.nih.gov/34652333/
4. https://pmc.ncbi.nlm.nih.gov/articles/PMC8677617/
5. https://pubmed.ncbi.nlm.nih.gov/39413062/
6. https://www.weather.gov/safety/cold-wind-chill-chart
7. https://www.wpc.ncep.noaa.gov/heat_index/hi_equation.html
8. https://pubmed.ncbi.nlm.nih.gov/7380693/
9. https://pubmed.ncbi.nlm.nih.gov/26842928/
10. https://pubmed.ncbi.nlm.nih.gov/30471385/
11. https://pubmed.ncbi.nlm.nih.gov/33245998/
12. https://pubmed.ncbi.nlm.nih.gov/31694361/
13. https://pubmed.ncbi.nlm.nih.gov/39225023/
14. https://pubmed.ncbi.nlm.nih.gov/40107869/
15. https://pubmed.ncbi.nlm.nih.gov/37372087/
16. https://pubmed.ncbi.nlm.nih.gov/17986912/

## 7. Potential Improvements

1. Personal calibration mode.
- Fit coefficients per user using historical pace-vs-weather residuals.

2. Route-aware wind model.
- Add bearing/segment analysis to separate headwind/tailwind/crosswind burden.

3. Better solar modeling.
- Incorporate direct shortwave radiation if available.

4. Hierarchical model by activity type.
- Distinct coefficients for easy runs, workouts, races, and walking.

5. Reliability envelopes.
- Surface confidence/uncertainty based on missing fields or weak signals.

6. Smoother presentation bands.
- Keep numeric score unchanged but optionally widen user-facing label bands.

7. Explainability in UI.
- Render top contributing components directly in the weather line or tooltip.
