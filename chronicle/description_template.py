from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import yaml

from jinja2 import StrictUndefined, TemplateError, meta, pass_context
from jinja2.sandbox import SandboxedEnvironment

from .config import Settings
from .numeric_utils import as_float as _shared_as_float


class _DisplayValueMapping(dict):
    def __str__(self) -> str:
        value = self.get("value")
        if isinstance(value, (int, float)):
            return f"{float(value):.1f}"
        if value is None:
            return "N/A"
        return str(value)

    __repr__ = __str__


DEFAULT_DESCRIPTION_TEMPLATE = """🏆 {{ streak_days }} days in a row
{% for notable in notables %}🏅 {{ notable }}
{% endfor %}{% for achievement in achievements %}🏅 {{ achievement }}
{% endfor %}{% for segment_notable in segment_notables | default([]) %}🥇 {{ segment_notable }}
{% endfor %}{% for badge in badges | default([]) %}🎖️ {{ badge }}
{% endfor %}🌤️🌡️ Misery Index: {{ misery.index }} {{ misery.index.emoji }}{% if misery.index.polarity in ['hot', 'cold'] %} ({{ misery.index.polarity }}){% endif %} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}
{% if crono.average_net_kcal_per_day is defined and crono.average_net_kcal_per_day is not none %}🔥 7d avg daily Energy Balance:{{ "%+.0f"|format(crono.average_net_kcal_per_day) }} kcal{% if crono.average_status %} ({{ crono.average_status }}){% endif %}{% if crono.protein_g and crono.protein_g > 0 %} | 🥩:{{ crono.protein_g|round|int }}g{% endif %}{% if crono.carbs_g and crono.carbs_g > 0 %} | 🍞:{{ crono.carbs_g|round|int }}g{% endif %}
{% elif crono.line %}{{ crono.line }}
{% endif %}🌤️🚦 Training Readiness: {{ training.readiness_score }} {{ training.readiness_emoji }} | 💗 {{ training.resting_hr }} | 💤 {{ training.sleep_score }}
👟🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }} | 🍺 {{ activity.beers }}
👟👣 {{ activity.cadence_spm }}spm | 💼 {{ activity.work }} | ⚡ {{ activity.norm_power }} | 💓 {{ activity.average_hr }} | ⚙️{{ activity.efficiency }}
🚄 {{ training.status_emoji }} {{ training.status_key }} | {{ training.aerobic_te }} : {{ training.anaerobic_te }} - {{ training.te_label }}
🚄 {{ intervals.summary }}
🚄 🏋️ {{ intervals.fitness }} | 💦 {{ intervals.fatigue }} | 🎯 {{ intervals.load }} | 📈 {{ intervals.ramp_display }} | 🗿 {{ intervals.form_percent_display }} - {{ intervals.form_class }} {{ intervals.form_class_emoji }}
❤️‍🔥 {{ training.vo2 }} | ♾ Endur: {{ training.endurance_score }} | 🗻 Hill: {{ training.hill_score }}

7️⃣ Past 7 days:
🏃 {{ periods.week.gap }} | 🗺️ {{ periods.week.distance_miles }} | 🏔️ {{ periods.week.elevation_feet }}' | 🕓 {{ periods.week.duration }} | 🍺 {{ periods.week.beers }}
📅 Past 30 days:
🏃 {{ periods.month.gap }} | 🗺️ {{ periods.month.distance_miles }} | 🏔️ {{ periods.month.elevation_feet }}' | 🕓 {{ periods.month.duration }} | 🍺 {{ periods.month.beers }}
🌍 This Year:
🏃 {{ periods.year.gap }} | 🗺️ {{ periods.year.distance_miles }} | 🏔️ {{ periods.year.elevation_feet }}' | 🕓 {{ periods.year.duration }} | 🍺 {{ periods.year.beers }}"""

MAX_TEMPLATE_CHARS = 16000
FORBIDDEN_TEMPLATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"{%\s*(import|from|include|extends|macro|call)\b", re.IGNORECASE), "Template uses unsupported Jinja control tag."),
    (re.compile(r"\b__\w+\b"), "Template references dunder-style attributes, which are not allowed."),
]


EDITOR_SNIPPETS: list[dict[str, str]] = [
    {
        "id": "if-block",
        "category": "logic",
        "label": "If Present Block",
        "template": "{% if value %}\n{{ value }}\n{% endif %}",
        "description": "Render a line only when a value exists.",
    },
    {
        "id": "for-loop",
        "category": "logic",
        "label": "Simple For Loop",
        "template": "{% for item in items %}\n- {{ item }}\n{% endfor %}",
        "description": "Loop over a list.",
    },
    {
        "id": "default-filter",
        "category": "filters",
        "label": "Default Fallback",
        "template": "{{ value | default('N/A') }}",
        "description": "Provide a fallback when a value is missing.",
    },
    {
        "id": "round-filter",
        "category": "filters",
        "label": "Round Number",
        "template": "{{ value | round(1) }}",
        "description": "Round to one decimal place.",
    },
    {
        "id": "join-filter",
        "category": "filters",
        "label": "Join List",
        "template": "{{ items | join(', ') }}",
        "description": "Join list items into one line.",
    },
    {
        "id": "line-break",
        "category": "layout",
        "label": "Blank Line",
        "template": "\n",
        "description": "Insert an empty line.",
    },
]


STARTER_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "minimal-core",
        "label": "Minimal Core",
        "description": "Short and clean: weather + latest activity + 7-day summary.",
        "template": """🌤️ MI {{ misery.index }} {{ misery.index.emoji }} | AQI {{ weather.aqi }}
👟 {{ activity.gap_pace }} | {{ activity.distance_miles }}mi | {{ activity.time }} | {{ activity.elevation_feet }}'
7️⃣ {{ periods.week.gap }} | {{ periods.week.distance_miles }}mi | {{ periods.week.duration }} | 🍺 {{ periods.week.beers }}""",
    },
    {
        "id": "race-day",
        "label": "Race Day",
        "description": "Spotlight the latest effort with readiness, pace, power, and effort context.",
        "template": """🏆 {{ streak_days }} days in a row
🌤️🚦 Readiness {{ training.readiness_score }} {{ training.readiness_emoji }} | RHR {{ training.resting_hr }} | Sleep {{ training.sleep_score }}
👟🏃 {{ activity.gap_pace }} | {{ activity.distance_miles }} | {{ activity.time }} | 🏔️ {{ activity.elevation_feet }}' | 🍺 {{ activity.beers }}
👟👣 {{ activity.cadence_spm }}spm | ⚡ {{ activity.norm_power }} | 💓 {{ activity.average_hr }} | ⚙️ {{ activity.efficiency }}
🚄 {{ training.status_emoji }} {{ training.status_key }} | TE {{ training.aerobic_te }} : {{ training.anaerobic_te }} ({{ training.te_label }})""",
    },
    {
        "id": "weather-watch",
        "label": "Weather Watch",
        "description": "Lead with conditions and keep training context concise.",
        "template": """🌤️🌡️ Misery Index: {{ misery.index }} {{ misery.index.emoji }}{% if misery.index.polarity in ['hot', 'cold'] %} ({{ misery.index.polarity }}){% endif %} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}
{% if weather.details is defined %}Temp {{ weather.details.temperature_f }}F | Dew {{ weather.details.dew_point_f }}F | Wind {{ weather.details.wind_mph }}mph | {{ weather.details.condition_text }}{% endif %}
👟 {{ activity.gap_pace }} | {{ activity.distance_miles }}mi | {{ activity.time }} | 🏔️ {{ activity.elevation_feet }}'
📅 30d {{ periods.month.gap }} | {{ periods.month.distance_miles }}mi | {{ periods.month.duration }}""",
    },
    {
        "id": "full-data-rich",
        "label": "Full Data Rich",
        "description": "High-detail report with nutrition and rolling summaries.",
        "template": DEFAULT_DESCRIPTION_TEMPLATE,
    },
]


SAMPLE_TEMPLATE_CONTEXT: dict[str, Any] = {
    "streak_days": 412,
    "notables": [
        "Longest run in 90 days",
        "2nd best GAP pace this month",
    ],
    "achievements": [],
    "badges": [
        "Strava PR: River Path Sprint (1:18)",
        "Garmin: Run Streak 400 (L1)",
        "Smashrun: 1,000 Mile Month Club",
    ],
    "strava_badges": [
        "Strava PR: River Path Sprint (1:18)",
    ],
    "garmin_badges": [
        "Garmin: Run Streak 400 (L1)",
    ],
    "activity_badges": [
        "February Weekend 10K",
    ],
    "smashrun_badges": [
        "Smashrun: 1,000 Mile Month Club",
    ],
    "smashrun_activity_badges": [
        "Two by 365 by 10k",
    ],
    "segment_notables": [
        "Strava PR: River Path Sprint (1:18)",
        "Strava 2nd: Bridge Climb (2:42)",
    ],
    "strava_segment_notables": [
        "Strava PR: River Path Sprint (1:18)",
        "Strava 2nd: Bridge Climb (2:42)",
    ],
    "garmin_segment_notables": [],
    "crono": {
        "line": "🔥 7d avg daily Energy Balance:-1131 kcal (deficit) | 🥩:182g | 🍞:216g",
        "date": "2026-02-15",
        "average_net_kcal_per_day": -1131.0,
        "average_status": "deficit",
        "protein_g": 182.0,
        "carbs_g": 216.0,
    },
    "misery": {
        "index": {
            "value": 14.9,
            "emoji": "😒",
            "polarity": "hot",
            "severity": "mild",
            "description": "😒 Mild (hot)",
            "hot_load": 0.54,
            "cold_load": 0.0,
            "delta": 0.54,
        },
        "emoji": "😒",
        "polarity": "hot",
        "severity": "mild",
        "description": "😒 Mild (hot)",
    },
    "weather": {
        "misery_index": 14.9,
        "misery_description": "😒 Mild (hot)",
        "aqi": 22,
        "aqi_description": " Good",
        "temp_f": "63.0F",
        "dewpoint_f": "49.6F",
        "humidity_pct": 61,
        "wind_mph": "11.9 mph",
        "cloud_pct": 18,
        "precip_in": "0.00in",
        "chance_rain_pct": 4,
        "chance_snow_pct": 0,
        "condition": "Clear",
        "is_day": True,
        "heatindex_f": "63.0F",
        "windchill_f": "63.0F",
        "tz_id": "America/New_York",
        "apparent_temp_f": "63.0F",
        "details": {
            "temp_f": 63.0,
            "dewpoint_f": 49.6,
            "humidity": 61,
            "wind_mph": 11.9,
            "cloud": 18,
            "precip_in": 0.0,
            "chance_of_rain": 4.0,
            "chance_of_snow": 0.0,
            "is_day": True,
            "heatindex_f": 63.0,
            "windchill_f": 63.0,
            "tz_id": "America/New_York",
            "condition_text": "Clear",
        },
        "components": {
            "score": 104.3,
            "apparent_temp_f": 63.0,
            "component_thermal_hot": 1.2,
            "component_thermal_cold": 0.0,
            "component_dew_hot": 0.0,
            "component_dew_cold": 0.0,
            "component_humidity_hot": 0.5,
            "component_dryness_cold": 0.0,
            "component_stagnant_hot": 0.0,
            "component_hot_breeze_relief": 0.2,
            "component_gale_cold": 0.0,
            "component_rain_hot": 0.0,
            "component_rain_cold": 0.0,
            "component_cold_rain_extra": 0.0,
            "component_rain_hint": 0.0,
            "component_snow": 0.0,
            "component_sun_hot": 1.8,
            "component_cloud_hot_relief": 0.3,
            "component_cloud_cold": 0.0,
        },
    },
    "training": {
        "readiness_score": 83,
        "readiness_emoji": "🟢",
        "readiness_level": "HIGH",
        "readiness_feedback": "Recovering well. Keep building.",
        "recovery_time_hours": 9.5,
        "readiness_factors": {
            "sleep_score_factor_pct": 82,
            "sleep_history_factor_pct": 77,
            "hrv_factor_pct": 69,
            "stress_history_factor_pct": 74,
            "acwr_factor_pct": 88,
            "recovery_time_factor_pct": 71,
        },
        "resting_hr": 47,
        "sleep_score": 86,
        "status_emoji": "🟢",
        "status_key": "Productive",
        "aerobic_te": 4.1,
        "anaerobic_te": 0.1,
        "te_label": "Tempo",
        "chronic_load": 72,
        "acute_load": 78,
        "load_ratio": 1.1,
        "acwr_status": "Optimal",
        "acwr_status_emoji": "🟢",
        "acwr_percent": 112,
        "daily_acwr_ratio": 1.12,
        "load_tunnel_min": 60,
        "load_tunnel_max": 92,
        "weekly_training_load": 568,
        "fitness_trend": "IMPROVING",
        "load_level_trend": "WITHIN_RANGE",
        "vo2": 57.2,
        "endurance_score": 7312,
        "hill_score": 102,
        "fitness_age": "34 yr",
        "fitness_age_details": {
            "fitness_age": 34,
            "chronological_age": 40,
            "achievable_fitness_age": 32,
            "previous_fitness_age": 35,
            "body_fat_pct": 14.8,
            "rhr": 47,
            "vigorous_days_avg": 4.7,
            "vigorous_minutes_avg": 271,
        },
    },
    "activity": {
        "id": 1234567890,
        "name": "Morning Run",
        "type": "Run",
        "sport_type": "Run",
        "workout_type": 0,
        "commute": False,
        "trainer": False,
        "has_gps": True,
        "start_latlng": [40.7127, -74.0059],
        "gap_pace": "7:18/mi",
        "average_pace": "7:24/mi",
        "distance_miles": "8.02",
        "elevation_feet": 612,
        "elev_high_feet": 742,
        "elev_low_feet": 411,
        "time": "58:39",
        "moving_time": "58:39",
        "elapsed_time": "1:02:04",
        "beers": "5.1",
        "calories": 761,
        "average_speed_mph": "8.1 mph",
        "max_speed_mph": "12.2 mph",
        "average_temp_f": "63.0F",
        "start_local": "2026-02-15 06:42 AM",
        "start_utc": "2026-02-15 11:42:00 UTC",
        "cadence_spm": 176,
        "work": "914 kJ",
        "norm_power": "271 W",
        "norm_power_source": "intervals",
        "average_hr": 149,
        "max_hr": 173,
        "efficiency": "1.03",
        "treadmill_incline_percent": 15,
        "treadmill_elevation_feet_15pct": 6353,
        "social": {
            "kudos": 12,
            "comments": 3,
            "achievements": 5,
        },
        "segment_notables": [
            "Strava PR: River Path Sprint (1:18)",
            "Strava 2nd: Bridge Climb (2:42)",
        ],
    },
    "intervals": {
        "summary": "CTL 72 | ATL 78 | Form -6",
        "ctl": 72,
        "atl": 78,
        "fitness": 72,
        "fatigue": 78,
        "training_load": 126,
        "load": 126,
        "ramp": -3.6,
        "ramp_display": "-3.6",
        "form_percent": -8,
        "form_percent_display": "-8%",
        "form_class": "Grey Zone",
        "form_class_emoji": "⛔",
        "strain_score": 142,
        "pace_load": 57,
        "hr_load": 61,
        "power_load": 58,
        "avg_pace": "7:26/mi",
        "avg_speed_mph": "8.1 mph",
        "max_speed_mph": "12.0 mph",
        "distance_miles": "8.02 mi",
        "moving_time": "58:39",
        "elapsed_time": "1:02:04",
        "average_hr": 149,
        "max_hr": 173,
        "elevation_gain_feet": 612,
        "elevation_loss_feet": 607,
        "average_temp_f": "63.0F",
        "max_temp_f": "66.2F",
        "min_temp_f": "58.8F",
        "zone_summary": "Z1 5m 12s | Z2 19m 03s | Z3 25m 41s",
        "hr_zone_summary": "Z1 4m 15s | Z2 21m 30s | Z3 22m 54s",
        "pace_zone_summary": "Z1 8m 10s | Z2 26m 48s | Z3 17m 57s",
        "gap_zone_summary": "Z1 9m 05s | Z2 24m 49s | Z3 16m 21s",
    },
    "periods": {
        "week": {
            "gap": "7:44/mi",
            "distance_miles": "41.6",
            "elevation_feet": 3904,
            "duration": "5:21:08",
            "beers": "27",
            "calories": 4050,
            "run_count": 6,
        },
        "month": {
            "gap": "7:58/mi",
            "distance_miles": "156",
            "elevation_feet": 14902,
            "duration": "20:04:51",
            "beers": "101",
            "calories": 15135,
            "run_count": 24,
        },
        "year": {
            "gap": "8:05/mi",
            "distance_miles": "284",
            "elevation_feet": 24117,
            "duration": "36:40:27",
            "beers": "184",
            "calories": 27680,
            "run_count": 43,
        },
    },
    "garmin": {
        "badges": [
            "Garmin: Run Streak 400 (L1)",
        ],
        "activity_badges": [
            "February Weekend 10K",
        ],
        "segment_notables": [],
        "last_activity": {
            "activity_id": 21939412525,
            "activity_name": "Morning Run",
            "activity_type": "running",
            "start_local": "2026-02-15 06:42:00",
            "distance_miles": "8.02 mi",
            "duration": "58:39",
            "moving_time": "58:10",
            "elapsed_time": "1:02:04",
            "average_pace": "7:24/mi",
            "average_speed_mph": "8.1 mph",
            "max_speed_mph": "12.2 mph",
            "gap_pace": "7:18/mi",
            "elevation_gain_feet": 612,
            "elevation_loss_feet": 607,
            "avg_elevation_feet": 512,
            "max_elevation_feet": 742,
            "min_elevation_feet": 411,
            "average_hr": 149,
            "max_hr": 173,
            "avg_power_w": 262,
            "norm_power_w": 271,
            "max_power_w": 487,
            "avg_ground_contact_time_ms": 238,
            "avg_vertical_ratio_pct": "7.9%",
            "avg_vertical_oscillation_mm": 85,
            "avg_stride_length_m": "1.20 m",
            "avg_respiration_rate": "34.2 brpm",
            "max_respiration_rate": "47.8 brpm",
            "steps": 10341,
            "lap_count": 8,
            "hr_zone_summary": "Z1 6:12 | Z2 18:44 | Z3 24:01",
            "power_zone_summary": "Z1 4:58 | Z2 20:44 | Z3 19:39",
            "is_pr": False,
        },
        "readiness": {
            "score": 83,
            "level": "HIGH",
            "emoji": "🟢",
            "sleep_score": 86,
            "feedback": "Recovering well. Keep building.",
            "recovery_time_hours": 9.5,
            "factors": {
                "sleep_score_factor_pct": 82,
                "sleep_history_factor_pct": 77,
                "hrv_factor_pct": 69,
                "stress_history_factor_pct": 74,
                "acwr_factor_pct": 88,
                "recovery_time_factor_pct": 71,
            },
        },
        "status": {
            "key": "Productive",
            "emoji": "🟢",
            "fitness_trend": "IMPROVING",
            "load_level_trend": "WITHIN_RANGE",
            "weekly_training_load": 568,
            "load_tunnel_min": 60,
            "load_tunnel_max": 92,
            "daily_acwr_ratio": 1.12,
            "acwr_percent": 112,
        },
        "fitness_age": {
            "fitness_age": 34,
            "chronological_age": 40,
            "achievable_fitness_age": 32,
            "previous_fitness_age": 35,
            "body_fat_pct": 14.8,
            "rhr": 47,
            "vigorous_days_avg": 4.7,
            "vigorous_minutes_avg": 271,
        },
    },
    "smashrun": {
        "badges": [
            "Smashrun: 1,000 Mile Month Club",
        ],
        "activity_badges": [
            "Two by 365 by 10k",
        ],
        "latest_activity": {
            "activity_id": 99887766,
            "activity_type": "Run",
            "start_local": "2026-02-15 06:42 AM",
            "distance_miles": "8.02",
            "duration": "58:39",
            "pace": "7:18",
            "calories": 761,
            "elevation_gain_feet": 612,
            "elevation_loss_feet": 607,
            "elevation_ascent_feet": 612,
            "elevation_descent_feet": 607,
            "elevation_max_feet": 742,
            "elevation_min_feet": 411,
            "average_hr": 149,
            "max_hr": 173,
            "cadence_average": 176,
            "cadence_max": 188,
            "temperature_f": "63.0F",
            "apparent_temp_f": "63.0F",
            "wind_chill_f": "63.0F",
            "humidity_pct": "61%",
            "wind_mph": "11.9 mph",
            "weather_type": "Clear",
            "terrain": "Road",
            "is_race": False,
            "is_treadmill": False,
            "how_felt": "Strong",
            "source": "Garmin",
        },
        "stats": {
            "run_count": 1432,
            "longest_streak": 412,
            "longest_streak_date": "2025-10-11",
            "average_days_run_per_week": "5.6",
            "total_distance": "10044.3",
            "average_run_length": "7.02",
            "average_distance_per_day": "5.62",
            "average_speed": "7.35",
            "average_pace": "8:09",
            "longest_run": "22.2",
            "longest_run_when": "2025-11-16",
            "longest_break_between_runs_days": 3,
            "longest_break_between_runs_date": "2025-02-03",
            "most_often_run_day": "Sunday",
            "least_often_run_day": "Thursday",
        },
    },
    "profile": {
        "id": "default",
        "label": "Default",
        "reasons": ["fallback"],
    },
    "raw": {
        "activity": {"id": 1234567890},
        "training": {
            "garmin_badges_raw": [
                {
                    "badgeName": "February Weekend 10K",
                    "badgeAssocType": "activityId",
                    "badgeAssocDataId": "21939412525",
                }
            ]
        },
        "intervals": {},
        "week": {},
        "month": {},
        "year": {},
        "weather": {},
        "smashrun": {},
        "garmin_period_fallback": {},
    },
}


def _build_sample_fixtures() -> dict[str, dict[str, Any]]:
    default_ctx = deepcopy(SAMPLE_TEMPLATE_CONTEXT)

    winter_ctx = deepcopy(default_ctx)
    winter_ctx["weather"]["misery_index"] = 196.4
    winter_ctx["weather"]["misery_description"] = "☠️ Death (cold)"
    winter_ctx["misery"]["index"]["value"] = 196.4
    winter_ctx["misery"]["index"]["emoji"] = "☠️"
    winter_ctx["misery"]["index"]["polarity"] = "cold"
    winter_ctx["misery"]["index"]["severity"] = "death"
    winter_ctx["misery"]["index"]["description"] = "☠️ Death (cold)"
    winter_ctx["misery"]["emoji"] = "☠️"
    winter_ctx["misery"]["polarity"] = "cold"
    winter_ctx["misery"]["severity"] = "death"
    winter_ctx["misery"]["description"] = "☠️ Death (cold)"
    winter_ctx["weather"]["aqi"] = 11
    winter_ctx["weather"]["temp_f"] = "24.1F"
    winter_ctx["weather"]["dewpoint_f"] = "5.0F"
    winter_ctx["weather"]["humidity_pct"] = 43
    winter_ctx["weather"]["wind_mph"] = "16.5 mph"
    winter_ctx["weather"]["cloud_pct"] = 82
    winter_ctx["weather"]["precip_in"] = "0.02in"
    winter_ctx["weather"]["chance_rain_pct"] = 22
    winter_ctx["weather"]["chance_snow_pct"] = 45
    winter_ctx["weather"]["condition"] = "Windy"
    winter_ctx["weather"]["heatindex_f"] = "24.1F"
    winter_ctx["weather"]["windchill_f"] = "15.9F"
    winter_ctx["weather"]["apparent_temp_f"] = "15.9F"
    winter_ctx["weather"]["details"] = {
        "temp_f": 24.1,
        "dewpoint_f": 5.0,
        "humidity": 43,
        "wind_mph": 16.5,
        "cloud": 82,
        "precip_in": 0.02,
        "chance_of_rain": 22.0,
        "chance_of_snow": 45.0,
        "is_day": True,
        "heatindex_f": 24.1,
        "windchill_f": 15.9,
        "tz_id": "America/New_York",
        "condition_text": "Windy",
    }
    winter_ctx["activity"]["gap_pace"] = "8:42/mi"
    winter_ctx["activity"]["distance_miles"] = "6.10"
    winter_ctx["activity"]["elevation_feet"] = 441
    winter_ctx["activity"]["time"] = "53:03"
    winter_ctx["activity"]["beers"] = "3.1"
    winter_ctx["crono"]["average_net_kcal_per_day"] = -842.0
    winter_ctx["crono"]["average_status"] = "deficit"
    winter_ctx["crono"]["protein_g"] = 169.0
    winter_ctx["crono"]["carbs_g"] = 153.0

    humid_ctx = deepcopy(default_ctx)
    humid_ctx["weather"]["misery_index"] = 187.3
    humid_ctx["weather"]["misery_description"] = "☠️ Death (hot)"
    humid_ctx["misery"]["index"]["value"] = 187.3
    humid_ctx["misery"]["index"]["emoji"] = "☠️"
    humid_ctx["misery"]["index"]["polarity"] = "hot"
    humid_ctx["misery"]["index"]["severity"] = "death"
    humid_ctx["misery"]["index"]["description"] = "☠️ Death (hot)"
    humid_ctx["misery"]["emoji"] = "☠️"
    humid_ctx["misery"]["polarity"] = "hot"
    humid_ctx["misery"]["severity"] = "death"
    humid_ctx["misery"]["description"] = "☠️ Death (hot)"
    humid_ctx["weather"]["aqi"] = 67
    humid_ctx["weather"]["temp_f"] = "89.8F"
    humid_ctx["weather"]["dewpoint_f"] = "80.2F"
    humid_ctx["weather"]["humidity_pct"] = 78
    humid_ctx["weather"]["wind_mph"] = "2.7 mph"
    humid_ctx["weather"]["cloud_pct"] = 20
    humid_ctx["weather"]["precip_in"] = "0.00in"
    humid_ctx["weather"]["chance_rain_pct"] = 18
    humid_ctx["weather"]["chance_snow_pct"] = 0
    humid_ctx["weather"]["condition"] = "Humid"
    humid_ctx["weather"]["heatindex_f"] = "101.3F"
    humid_ctx["weather"]["windchill_f"] = "89.8F"
    humid_ctx["weather"]["apparent_temp_f"] = "101.3F"
    humid_ctx["weather"]["details"] = {
        "temp_f": 89.8,
        "dewpoint_f": 80.2,
        "humidity": 78,
        "wind_mph": 2.7,
        "cloud": 20,
        "precip_in": 0.0,
        "chance_of_rain": 18.0,
        "chance_of_snow": 0.0,
        "is_day": True,
        "heatindex_f": 101.3,
        "windchill_f": 89.8,
        "tz_id": "America/New_York",
        "condition_text": "Humid",
    }
    humid_ctx["activity"]["gap_pace"] = "8:31/mi"
    humid_ctx["activity"]["distance_miles"] = "9.28"
    humid_ctx["activity"]["elevation_feet"] = 518
    humid_ctx["activity"]["time"] = "1:19:16"
    humid_ctx["activity"]["beers"] = "6.7"
    humid_ctx["crono"]["average_net_kcal_per_day"] = 204.0
    humid_ctx["crono"]["average_status"] = "surplus"
    humid_ctx["crono"]["protein_g"] = 132.0
    humid_ctx["crono"]["carbs_g"] = 301.0

    strength_ctx = deepcopy(default_ctx)
    strength_ctx["profile"] = {
        "id": "strength_training",
        "label": "Strength Training",
        "reasons": ["garmin activity indicates strength"],
    }
    strength_ctx["activity"].update(
        {
            "name": "Strength Workout",
            "type": "Workout",
            "sport_type": "Workout",
            "trainer": True,
            "has_gps": False,
            "start_latlng": [],
            "distance_miles": "0.00",
            "elevation_feet": 0,
            "time": "45:12",
            "moving_time": "43:08",
            "elapsed_time": "45:12",
            "beers": "2.2",
            "average_speed_mph": "N/A",
            "max_speed_mph": "N/A",
            "cadence_spm": "N/A",
            "work": "N/A",
            "norm_power": "N/A",
            "norm_power_source": "none",
            "average_hr": "N/A",
            "max_hr": "N/A",
            "efficiency": "N/A",
        }
    )
    strength_ctx["garmin"]["segment_notables"] = []
    strength_ctx["segment_notables"] = []
    strength_ctx["strava_segment_notables"] = []
    strength_ctx["badges"] = []
    strength_ctx["strava_badges"] = []
    strength_ctx["garmin_badges"] = []
    strength_ctx["activity_badges"] = []
    strength_ctx["smashrun_badges"] = []
    strength_ctx["smashrun_activity_badges"] = []
    strength_ctx["smashrun"]["badges"] = []
    strength_ctx["smashrun"]["activity_badges"] = []
    strength_ctx["garmin"]["activity_badges"] = []
    strength_ctx["smashrun"]["latest_activity"] = {}
    strength_ctx["smashrun"]["stats"] = {}

    strength_garmin_last = {
        "activity_name": "Strength",
        "activity_type": "strength_training",
        "start_local": "2026-02-16 07:01:00",
        "distance_miles": "0.00 mi",
        "duration": "45:12",
        "moving_time": "43:08",
        "elapsed_time": "45:12",
        "average_pace": "N/A",
        "average_speed_mph": "N/A",
        "max_speed_mph": "N/A",
        "gap_pace": "N/A",
        "elevation_gain_feet": 0,
        "elevation_loss_feet": 0,
        "avg_elevation_feet": 0,
        "max_elevation_feet": 0,
        "min_elevation_feet": 0,
        "average_hr": "N/A",
        "max_hr": "N/A",
        "avg_power_w": "N/A",
        "norm_power_w": "N/A",
        "max_power_w": "N/A",
        "avg_ground_contact_time_ms": "N/A",
        "avg_vertical_ratio_pct": "N/A",
        "avg_vertical_oscillation_mm": "N/A",
        "avg_stride_length_m": "N/A",
        "avg_respiration_rate": "N/A",
        "max_respiration_rate": "N/A",
        "steps": "N/A",
        "lap_count": "N/A",
        "total_sets": 18,
        "active_sets": 16,
        "total_reps": 142,
        "max_weight": 205.0,
        "strength_summary_sets": [
            {
                "category": "PRESS",
                "sub_category": "BENCH_PRESS",
                "sets": 5,
                "reps": 35,
                "max_weight": 205.0,
                "duration_seconds": 686,
            },
            {
                "category": "SQUAT",
                "sub_category": "BACK_SQUAT",
                "sets": 6,
                "reps": 42,
                "max_weight": 185.0,
                "duration_seconds": 742,
            },
            {
                "category": "ROW",
                "sub_category": "SEATED_CABLE_ROW",
                "sets": 5,
                "reps": 45,
                "max_weight": 130.0,
                "duration_seconds": 521,
            },
        ],
        "exercise_sets": [
            {
                "set_type": "ACTIVE",
                "reps": 8,
                "weight": 185.0,
                "duration_seconds": 42,
                "exercise_names": ["BACK_SQUAT"],
            },
            {
                "set_type": "ACTIVE",
                "reps": 8,
                "weight": 195.0,
                "duration_seconds": 43,
                "exercise_names": ["BACK_SQUAT"],
            },
            {
                "set_type": "ACTIVE",
                "reps": 7,
                "weight": 205.0,
                "duration_seconds": 39,
                "exercise_names": ["BENCH_PRESS"],
            },
            {
                "set_type": "ACTIVE",
                "reps": 10,
                "weight": 130.0,
                "duration_seconds": 46,
                "exercise_names": ["SEATED_CABLE_ROW"],
            },
            {
                "set_type": "REST",
                "reps": "N/A",
                "weight": "N/A",
                "duration_seconds": 75,
                "exercise_names": [],
            },
        ],
        "hr_zone_summary": "N/A",
        "power_zone_summary": "N/A",
        "is_pr": False,
    }
    strength_ctx["garmin"]["last_activity"] = deepcopy(strength_garmin_last)
    strength_ctx["raw"]["activity"] = {
        "id": 9999990001,
        "name": "Strength",
        "type": "Workout",
        "sport_type": "Workout",
        "distance": 0.0,
        "moving_time": 2588,
        "elapsed_time": 2712,
        "trainer": True,
        "start_latlng": [],
    }
    strength_ctx["raw"]["training"] = {
        "garmin_last_activity": deepcopy(strength_garmin_last),
        "_garmin_activity_aligned": True,
    }

    return {
        "default": {
            "name": "default",
            "label": "Default",
            "description": "Balanced weather and training context.",
            "context": default_ctx,
        },
        "winter_grind": {
            "name": "winter_grind",
            "label": "Winter Grind",
            "description": "Cold and windy run profile for edge-case formatting.",
            "context": winter_ctx,
        },
        "humid_hammer": {
            "name": "humid_hammer",
            "label": "Humid Hammer",
            "description": "Hot + humid profile for heat-stress rendering checks.",
            "context": humid_ctx,
        },
        "strength_training": {
            "name": "strength_training",
            "label": "Strength Training",
            "description": "Strength workout payload with Garmin set/rep fields populated.",
            "context": strength_ctx,
        },
    }


SAMPLE_TEMPLATE_FIXTURES = _build_sample_fixtures()

DEFAULT_PROFILE_ID = "default"
PROFILE_CONFIG_VERSION = 1

PROFILE_BUILTINS: list[dict[str, Any]] = [
    {
        "profile_id": "default",
        "label": "Default",
        "enabled": True,
        "locked": True,
        "priority": 0,
        "criteria": {"kind": "fallback", "description": "Fallback profile when no enabled rule matches."},
    },
    {
        "profile_id": "incline_treadmill",
        "label": "Incline Treadmill",
        "enabled": True,
        "locked": False,
        "priority": 110,
        "criteria": {
            "kind": "activity",
            "description": "Custom Garmin treadmill sessions named as incline treadmill activities.",
        },
    },
    {
        "profile_id": "treadmill",
        "label": "Treadmill",
        "enabled": True,
        "locked": False,
        "priority": 100,
        "criteria": {"kind": "activity", "description": "Standard treadmill sessions (trainer/VirtualRun with missing GPS)."},
    },
    {
        "profile_id": "race",
        "label": "Race",
        "enabled": True,
        "locked": False,
        "priority": 90,
        "criteria": {"kind": "activity", "description": "Strava race/workout tags or race keywords."},
    },
    {
        "profile_id": "commute",
        "label": "Commute",
        "enabled": True,
        "locked": False,
        "priority": 80,
        "criteria": {"kind": "activity", "description": "Strava commute flag."},
    },
    {
        "profile_id": "onewheel",
        "label": "Onewheel",
        "enabled": True,
        "locked": False,
        "priority": 79,
        "criteria": {
            "kind": "activity",
            "description": "Garmin VESCDash-backed Onewheel/EUC activities.",
        },
    },
    {
        "profile_id": "walk",
        "label": "Walk",
        "enabled": True,
        "locked": False,
        "priority": 78,
        "criteria": {"kind": "activity", "description": "Outdoor Strava Walk activities with GPS and trainer disabled."},
    },
    {
        "profile_id": "strength_training",
        "label": "Strength Training",
        "enabled": True,
        "locked": False,
        "priority": 75,
        "criteria": {"kind": "activity", "description": "Strava sport type WeightTraining / Weight Training."},
    },
    {
        "profile_id": "trail",
        "label": "Trail",
        "enabled": True,
        "locked": False,
        "priority": 70,
        "criteria": {"kind": "activity", "description": "Trail run tags or high elevation-density heuristics."},
    },
    {
        "profile_id": "long_run",
        "label": "Long Run",
        "enabled": True,
        "locked": False,
        "priority": 60,
        "criteria": {"kind": "activity", "description": "Long run workout tag or distance threshold."},
    },
    {
        "profile_id": "pet",
        "label": "Pet",
        "enabled": False,
        "locked": False,
        "priority": 50,
        "criteria": {"kind": "activity", "description": "Pet/dog keywords in activity title/notes."},
    },
    {
        "profile_id": "away",
        "label": "Away",
        "enabled": False,
        "locked": False,
        "priority": 40,
        "criteria": {"kind": "location", "description": "Outside home geofence when GPS is available."},
    },
    {
        "profile_id": "home",
        "label": "Home",
        "enabled": False,
        "locked": False,
        "priority": 30,
        "criteria": {"kind": "location", "description": "Inside home geofence when GPS is available."},
    },
]

PROFILE_TEMPLATE_DEFAULTS: dict[str, str] = {
    "default": DEFAULT_DESCRIPTION_TEMPLATE,
    "incline_treadmill": """∠ Incline: 15%
{% set distance_m = raw.activity.distance | default(0) | float %}
{% set moving_s = raw.activity.moving_time | default(raw.activity.elapsed_time | default(0)) | float %}
{% set mph = ((distance_m / 1609.34) / (moving_s / 3600.0)) if moving_s > 0 else 0.0 %}
⏲ Avg Speed: {{ '%.1f' | format(mph) }}mph
🗻 {{ activity.treadmill_elevation_feet_15pct | default('N/A') }}' Treadmill Elevation
🍺 {{ activity.beers }}""",
    "treadmill": """🏠 Treadmill Session
🕓 {{ activity.time }} | 🗺️ {{ activity.distance_miles }} mi
🏃 {{ activity.gap_pace }} | 🚄 {{ activity.average_speed_mph }} | 💓 {{ activity.average_hr }}
🍺 {{ activity.beers }}""",
    "race": """🏁 Race Day
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🕓 {{ activity.time }} | 💓 {{ activity.average_hr }}
🚄 {{ intervals.summary }}""",
    "commute": """🚲 Commute Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🕓 {{ activity.time }}
🌤️ MI {{ misery.index }} {{ misery.index.emoji }}""",
    "onewheel": """{% set garmin = raw.training.garmin_last_activity if raw is defined and raw.training is defined and raw.training.garmin_last_activity is defined and raw.training.garmin_last_activity else {} %}
{% set vesc = garmin.vescdash if garmin and garmin.vescdash is defined and garmin.vescdash else {} %}
🛞 Onewheel
🏷️ {{ activity.name }} | Garmin {{ garmin.activity_type | default('N/A') }}
🕓 {{ garmin.moving_time | default(activity.time) }} | 🗺️ {{ garmin.distance_miles | default(activity.distance_miles) }} | 🚄 {{ garmin.average_speed_mph | default(activity.average_speed_mph) }} | ⚡ Max {{ garmin.max_speed_mph | default('N/A') }}
💓 {{ garmin.average_hr | default(activity.average_hr) }} avg | {{ garmin.max_hr | default('N/A') }} max | 🔥 {{ garmin.calories | default('N/A') }} cal | 💧 {{ garmin.water_estimated | default('N/A') }} ml
🗻 +{{ garmin.elevation_gain_feet | default('N/A') }}' / -{{ garmin.elevation_loss_feet | default('N/A') }}' | Avg {{ garmin.avg_elevation_feet | default('N/A') }}' | Load {{ garmin.activity_training_load | default('N/A') }}
🔌 VESCDash {{ vesc.profile_name | default('N/A') }}{% for app_id in garmin.connectiq_app_ids | default([]) %} {{ app_id }}{% endfor %}
🧭 Trip {{ vesc.trip_distance_miles | default('N/A') }} | Avg {{ vesc.average_speed_mph | default('N/A') }} | Max {{ vesc.max_speed_mph | default('N/A') }}
⚡ Avg {{ vesc.average_power_w | default('N/A') }} | Max {{ vesc.max_power_w | default('N/A') }} | Max PWM {{ vesc.max_pwm_pct | default('N/A') }}
🔌 Avg Current {{ vesc.average_current_a | default('N/A') }} | Max Current {{ vesc.max_current_a | default('N/A') }} | Running {{ vesc.running_time_s | default('N/A') }}
🔋 {{ vesc.min_battery_pct | default('N/A') }} → {{ vesc.max_battery_pct | default('N/A') }} | {{ vesc.min_voltage_v | default('N/A') }} → {{ vesc.max_voltage_v | default('N/A') }}
🌡️ {{ vesc.min_temperature_f | default('N/A') }} → {{ vesc.max_temperature_f | default('N/A') }} | Current {{ vesc.current_temperature_f | default('N/A') }}
🪫 Current {{ vesc.current_current_a | default('N/A') }} | Voltage {{ vesc.current_voltage_v | default('N/A') }} | Power {{ vesc.current_power_w | default('N/A') }}""",
    "walk": """{% set garmin = raw.training.garmin_last_activity if raw is defined and raw.training is defined and raw.training.garmin_last_activity is defined and raw.training.garmin_last_activity else {} %}
{% set garmin_steps = garmin.steps if garmin and garmin.steps is defined and garmin.steps != 'N/A' else none %}
{% set est_steps = none %}
{% if raw is defined and raw.activity is defined and activity.cadence_spm is number and raw.activity.moving_time is defined %}
{% set est_steps = ((activity.cadence_spm | float) * ((raw.activity.moving_time | float) / 60.0)) | round | int %}
{% endif %}
{% set step_count = garmin_steps if garmin_steps is not none else est_steps %}
🌤️🌡️ Misery Index: {{ misery.index }} {{ misery.index.emoji }}{% if misery.index.polarity in ['hot', 'cold'] %} ({{ misery.index.polarity }}){% endif %} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}
🚶 {{ activity.distance_miles }} mi | 🕓 {{ activity.time }} | 🚄 {{ activity.average_speed_mph }} | 🌤️ {{ weather.condition }}
👣 Steps: {{ step_count if step_count is not none else 'N/A' }}{% if garmin_steps is none and step_count is not none %} (est){% endif %} | 🍺 {{ activity.beers }}""",
    "strength_training": """{% set garmin = raw.training.garmin_last_activity if raw is defined and raw.training is defined and raw.training.garmin_last_activity is defined and raw.training.garmin_last_activity else {} %}

📦 Volume
Sets: {{ garmin.total_sets | default(raw.activity.set_count | default(raw.activity.sets | default(raw.activity.setCount | default('N/A')))) }} (Active: {{ garmin.active_sets | default('N/A') }})
Reps: {{ garmin.total_reps | default(raw.activity.rep_count | default(raw.activity.reps | default(raw.activity.repCount | default('N/A')))) }}
Rep Weight (max): {{ garmin.max_weight | default(raw.activity.rep_weight | default(raw.activity.weight | default(raw.activity.weight_kg | default(raw.activity.weight_lbs | default(raw.activity.weight_lb | default('N/A')))))) }}

{% set summary_sets = garmin.strength_summary_sets | default([]) %}
{% if summary_sets %}
📊 Exercise Summary
{% for row in summary_sets -%}
{% set summary_name = row.sub_category | default('') %}
{% set summary_group = row.category | default('') %}
{% if not summary_name or (summary_name | lower) in ['n/a', 'na', 'none', 'unknown', 'null'] %}
{% set summary_name = summary_group %}
{% endif %}
{% if not summary_name or (summary_name | lower) in ['n/a', 'na', 'none', 'unknown', 'null'] %}
{% set summary_name = 'Unknown' %}
{% endif %}
• {{ summary_name | replace('_', ' ') | title }}{% if summary_group and (summary_group | lower) != (summary_name | lower) and (summary_group | lower) not in ['n/a', 'na', 'none', 'unknown', 'null'] %} ({{ summary_group | replace('_', ' ') | title }}){% endif %} - {{ row.sets | default('N/A') }} set(s), {{ row.reps | default('N/A') }} rep(s), max {{ row.max_weight | default('N/A') }}{% if row.duration_seconds is defined and row.duration_seconds != 'N/A' %}, {{ row.duration_seconds }}s{% endif %}
{% endfor %}
{% endif %}

{% set exercise_sets = garmin.exercise_sets | default([]) %}
{% if exercise_sets %}
📋 Set By Set
{% for row in exercise_sets -%}
• {{ loop.index }}. {{ row.set_type | default('N/A') }}{% if row.exercise_names %} - {{ row.exercise_names | join(', ') | replace('_', ' ') | title }}{% endif %} | reps {{ row.reps | default('N/A') }} | weight {{ row.weight_display | default(row.weight | default('N/A')) }} | {{ row.duration_seconds | default('N/A') }}s
{% endfor %}
{% endif %}""",
    "trail": """🌲 Trail Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }}
🚄 {{ intervals.summary }}""",
    "long_run": """🧱 Long Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🕓 {{ activity.time }} | 🍺 {{ activity.beers }}
7️⃣ {{ periods.week.gap }} | {{ periods.week.distance_miles }} mi | {{ periods.week.duration }}""",
    "pet": """🐕 Pet Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🕓 {{ activity.time }}
❤️ Fun miles count too.""",
    "away": """🧳 Away Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }}
🌤️ {{ weather.condition }} | MI {{ misery.index }} {{ misery.index.emoji }}""",
    "home": """🏡 Home Run
🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} mi | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }}
7️⃣ {{ periods.week.gap }} | {{ periods.week.distance_miles }} mi | {{ periods.week.duration }}""",
}


def _as_float(value: Any) -> float | None:
    return _shared_as_float(value)


def _icu_calc_form_value(fitness: Any, fatigue: Any) -> int | None:
    fitness_value = _as_float(fitness)
    fatigue_value = _as_float(fatigue)
    if fitness_value is None or fatigue_value is None or fitness_value == 0:
        return None
    return int(round(((fitness_value - fatigue_value) / fitness_value) * 100.0))


@pass_context
def icu_calc_form(context: Any, fitness: Any | None = None, fatigue: Any | None = None) -> int | str:
    if fitness is None or fatigue is None:
        intervals = context.get("intervals", {}) if isinstance(context, dict) else {}
        if fitness is None:
            fitness = intervals.get("fitness")
        if fatigue is None:
            fatigue = intervals.get("fatigue")
    form_value = _icu_calc_form_value(fitness, fatigue)
    if form_value is None:
        return "N/A"
    return form_value


def _icu_class_from_form(
    form_percent: Any,
    transition_label: str = "Transition",
    fresh_label: str = "Fresh",
    grey_zone_label: str = "Grey Zone",
    optimal_label: str = "Optimal",
    high_risk_label: str = "High Risk",
) -> str:
    form_value = _as_float(form_percent)
    if form_value is None:
        return "N/A"
    if form_value < -30:
        return high_risk_label
    if form_value <= -10:
        return optimal_label
    if form_value <= 5:
        return grey_zone_label
    if form_value <= 20:
        return fresh_label
    return transition_label


def _icu_emoji_from_form(form_percent: Any) -> str:
    form_value = _as_float(form_percent)
    if form_value is None:
        return "⚪"
    if form_value < -30:
        return "⚠️"
    if form_value <= -10:
        return "🦾"
    if form_value <= 5:
        return "⛔"
    if form_value <= 20:
        return "🏁"
    return "❄️"


@pass_context
def icu_form_class(
    context: Any,
    form_percent: Any | None = None,
    transition_label: str = "Transition",
    fresh_label: str = "Fresh",
    grey_zone_label: str = "Grey Zone",
    optimal_label: str = "Optimal",
    high_risk_label: str = "High Risk",
) -> str:
    if form_percent is not None and _as_float(form_percent) is None:
        labels = [
            str(form_percent),
            str(transition_label),
            str(fresh_label),
            str(grey_zone_label),
            str(optimal_label),
        ]
        transition_label, fresh_label, grey_zone_label, optimal_label, high_risk_label = labels
        form_percent = None

    if form_percent is None:
        intervals = context.get("intervals", {}) if isinstance(context, dict) else {}
        form_percent = intervals.get("form_percent")
    return _icu_class_from_form(
        form_percent,
        transition_label=transition_label,
        fresh_label=fresh_label,
        grey_zone_label=grey_zone_label,
        optimal_label=optimal_label,
        high_risk_label=high_risk_label,
    )


@pass_context
def icu_form_emoji(context: Any, form_percent: Any | None = None) -> str:
    if form_percent is None:
        intervals = context.get("intervals", {}) if isinstance(context, dict) else {}
        form_percent = intervals.get("form_percent")
    return _icu_emoji_from_form(form_percent)


def normalize_template_context(context: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(context)

    intervals = normalized.get("intervals")
    if isinstance(intervals, dict):
        training = normalized.get("training")
        activity = normalized.get("activity")

        if "fitness" not in intervals:
            intervals["fitness"] = intervals.get(
                "ctl",
                training.get("chronic_load", "N/A") if isinstance(training, dict) else "N/A",
            )
        if "fatigue" not in intervals:
            intervals["fatigue"] = intervals.get(
                "atl",
                training.get("acute_load", "N/A") if isinstance(training, dict) else "N/A",
            )
        if "load" not in intervals:
            intervals["load"] = intervals.get("training_load", "N/A")
        if "ramp_display" not in intervals:
            ramp_value = intervals.get("ramp")
            intervals["ramp_display"] = str(ramp_value) if ramp_value is not None else "N/A"

        if "form_percent" not in intervals:
            form_percent = _icu_calc_form_value(intervals.get("fitness"), intervals.get("fatigue"))
            intervals["form_percent"] = form_percent if form_percent is not None else "N/A"
        if "form_percent_display" not in intervals:
            form_value = _as_float(intervals.get("form_percent"))
            intervals["form_percent_display"] = f"{int(round(form_value))}%" if form_value is not None else "N/A"
        if "form_class" not in intervals:
            intervals["form_class"] = _icu_class_from_form(intervals.get("form_percent"))
        if "form_class_emoji" not in intervals:
            intervals["form_class_emoji"] = _icu_emoji_from_form(intervals.get("form_percent"))

        if isinstance(activity, dict):
            for key in (
                "fitness",
                "fatigue",
                "load",
                "ramp",
                "ramp_display",
                "form_percent",
                "form_percent_display",
                "form_class",
                "form_class_emoji",
            ):
                if key not in activity and key in intervals:
                    activity[key] = intervals[key]

    misery = normalized.get("misery")
    weather = normalized.get("weather")
    if not isinstance(misery, dict):
        misery = {}
        normalized["misery"] = misery

    if "index" not in misery and isinstance(weather, dict):
        weather_misery = weather.get("misery_index")
        weather_desc = weather.get("misery_description")
        emoji = "N/A"
        if isinstance(weather_desc, str) and weather_desc.strip():
            emoji = weather_desc.strip().split(" ", 1)[0]
        misery["index"] = {
            "value": weather_misery if isinstance(weather_misery, (int, float)) else "N/A",
            "emoji": emoji,
            "polarity": "neutral",
            "severity": "unknown",
            "description": weather_desc if isinstance(weather_desc, str) else "",
            "hot_load": "N/A",
            "cold_load": "N/A",
            "delta": "N/A",
        }
        misery["emoji"] = emoji
        misery["polarity"] = "neutral"
        misery["severity"] = "unknown"
        misery["description"] = weather_desc if isinstance(weather_desc, str) else ""

    index_payload = misery.get("index")
    if isinstance(index_payload, dict) and not isinstance(index_payload, _DisplayValueMapping):
        misery["index"] = _DisplayValueMapping(index_payload)

    return normalized


def _template_environment() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
        undefined=StrictUndefined,
    )
    env.globals["icu_calc_form"] = icu_calc_form
    env.globals["icu_form_class"] = icu_form_class
    env.globals["icu_form_emoji"] = icu_form_emoji
    return env


def _normalize_template_text(template_text: str) -> str:
    return template_text.replace("\r\n", "\n").strip("\n")


def _normalize_rendered_text(rendered: str) -> str:
    lines = [line.rstrip() for line in rendered.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def get_default_template() -> str:
    return DEFAULT_DESCRIPTION_TEMPLATE


def get_editor_snippets() -> list[dict[str, str]]:
    return deepcopy(EDITOR_SNIPPETS)


def get_starter_templates() -> list[dict[str, str]]:
    templates = deepcopy(STARTER_TEMPLATES)
    templates.sort(key=lambda item: str(item.get("label") or item.get("id") or ""))
    return templates


def list_sample_template_fixtures() -> list[dict[str, str]]:
    fixtures: list[dict[str, str]] = []
    for fixture in SAMPLE_TEMPLATE_FIXTURES.values():
        fixtures.append(
            {
                "name": str(fixture["name"]),
                "label": str(fixture["label"]),
                "description": str(fixture["description"]),
            }
        )
    fixtures.sort(key=lambda item: item["name"])
    return fixtures


def get_sample_template_context(fixture_name: str | None = None) -> dict[str, Any]:
    key = (fixture_name or "default").strip().lower()
    fixture = SAMPLE_TEMPLATE_FIXTURES.get(key) or SAMPLE_TEMPLATE_FIXTURES["default"]
    return deepcopy(fixture["context"])


def _template_path(settings: Settings) -> Path:
    return settings.description_template_file


def _template_meta_path(settings: Settings) -> Path:
    return _template_path(settings).with_suffix(".meta.json")


def _template_versions_dir(settings: Settings) -> Path:
    return _template_path(settings).parent / "template_versions"


def _template_repository_dir(settings: Settings) -> Path:
    return _template_path(settings).parent / "template_repository"


def _normalize_template_id(raw_id: str | None) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw_id or "").strip().lower()).strip("-")
    return value


def _normalize_profile_id(raw_id: str | None) -> str:
    return _normalize_template_id(raw_id)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return default


def _parse_profile_import_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        integer = int(value)
        if integer in {0, 1}:
            return bool(integer)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError("value must be a boolean.")


def _template_profiles_path(settings: Settings) -> Path:
    return _template_path(settings).parent / "template_profiles.json"


def _profile_rules_dir(settings: Settings) -> Path:
    return _template_path(settings).parent / "profile_rules"


def _profile_rule_path(settings: Settings, profile_id: str) -> Path:
    safe = _normalize_profile_id(profile_id)
    if not safe:
        raise ValueError("profile_id is required.")
    return _profile_rules_dir(settings) / f"{safe}.yaml"


def _profile_rules_state_path(settings: Settings) -> Path:
    return _profile_rules_dir(settings) / "_workshop_state.yaml"


def _template_profiles_templates_dir(settings: Settings) -> Path:
    return _template_path(settings).parent / "template_profiles"


def _template_profile_template_path(settings: Settings, profile_id: str) -> Path:
    safe = _normalize_profile_id(profile_id)
    if not safe:
        raise ValueError("profile_id is required.")
    return _template_profiles_templates_dir(settings) / f"{safe}.j2"


def _template_profile_meta_path(settings: Settings, profile_id: str) -> Path:
    safe = _normalize_profile_id(profile_id)
    if not safe:
        raise ValueError("profile_id is required.")
    return _template_profiles_templates_dir(settings) / f"{safe}.meta.json"


def _template_profile_versions_dir(settings: Settings, profile_id: str) -> Path:
    safe = _normalize_profile_id(profile_id)
    if not safe:
        raise ValueError("profile_id is required.")
    return _template_path(settings).parent / "template_profile_versions" / safe


def _profile_template_metadata_defaults(label: str) -> dict[str, Any]:
    return {
        "name": f"{label} Template",
        "current_version": None,
        "updated_at_utc": None,
        "updated_by": "system",
        "source": "profile-default",
    }


def _settings_profile_long_run_miles(settings: Settings | None) -> float:
    value = _shared_as_float(getattr(settings, "profile_long_run_miles", None)) if settings is not None else None
    return value if value is not None and value > 0 else 10.0


def _settings_profile_trail_gain_per_mile_ft(settings: Settings | None) -> float:
    value = _shared_as_float(getattr(settings, "profile_trail_gain_per_mile_ft", None)) if settings is not None else None
    return value if value is not None and value > 0 else 220.0


def _settings_home_geofence(settings: Settings | None, *, mode: str) -> dict[str, Any] | None:
    if settings is None:
        return None
    latitude = _shared_as_float(getattr(settings, "home_latitude", None))
    longitude = _shared_as_float(getattr(settings, "home_longitude", None))
    radius_miles = _shared_as_float(getattr(settings, "home_radius_miles", None))
    if latitude is None or longitude is None:
        return None
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_miles": radius_miles if radius_miles is not None and radius_miles > 0 else 10.0,
        "mode": mode,
    }


def _profile_builtin_criteria(settings: Settings | None, profile_id: str) -> dict[str, Any]:
    normalized = _normalize_profile_id(profile_id)
    if normalized == DEFAULT_PROFILE_ID:
        return {
            "kind": "fallback",
            "description": "Fallback profile when no enabled rule matches.",
        }
    if normalized == "incline_treadmill":
        return {
            "kind": "activity",
            "description": "Incline treadmill sessions named in Strava or Garmin activity context.",
            "all_of": [
                {"none_of": [{"strength_like": True}]},
                {
                    "any_of": [
                        {"name_contains_any": ["treadmill incline", "incline treadmill"]},
                        {"garmin_activity_type_in": ["treadmillincline", "inclinetreadmill"]},
                    ]
                },
            ],
        }
    if normalized == "treadmill":
        return {
            "kind": "activity",
            "description": "Standard treadmill sessions (trainer/VirtualRun with missing GPS).",
            "all_of": [
                {"none_of": [{"strength_like": True}]},
                {"treadmill": True},
                {
                    "any_of": [
                        {"sport_type": ["virtualrun"]},
                        {"strava_tags_any": ["treadmill"]},
                        {"text_contains_any": ["treadmill"]},
                        {"distance_miles_min": 0.25},
                        {"moving_time_seconds_min": 600},
                    ]
                },
            ],
        }
    if normalized == "race":
        return {
            "kind": "activity",
            "description": "Strava race/workout tags or race keywords.",
            "any_of": [
                {"workout_type": 1},
                {"strava_tags_any": ["race"]},
                {"text_contains_any": [" race", "5k", "10k", "half", "marathon", "ultra"]},
            ],
        }
    if normalized == "commute":
        return {
            "kind": "activity",
            "description": "Strava commute-tagged activities.",
            "any_of": [
                {"commute": True},
                {"strava_tags_any": ["commute"]},
            ],
        }
    if normalized == "onewheel":
        return {
            "kind": "activity",
            "description": "Garmin VESCDash-backed Onewheel/EUC activities.",
            "any_of": [
                {
                    "all_of": [
                        {"garmin_activity_type_in": ["other"]},
                        {
                            "garmin_connectiq_app_ids_any": [
                                "0432631a-d5e3-4272-a072-fa8c7e24c483",
                            ]
                        },
                    ]
                },
                {"text_contains_any": ["onewheel", "euc", "electric unicycle"]},
            ],
        }
    if normalized == "walk":
        return {
            "kind": "activity",
            "description": "Outdoor Strava Walk activities with GPS and trainer disabled.",
            "all_of": [
                {"sport_type": ["walk"]},
                {"has_gps": True},
                {"trainer": False},
                {"none_of": [{"strength_like": True}]},
            ],
        }
    if normalized == "strength_training":
        return {
            "kind": "activity",
            "description": "Strength workout activities from Strava or Garmin.",
            "any_of": [
                {"garmin_activity_type_in": ["strength", "strengthtraining", "weighttraining", "weightlifting", "strengthworkout"]},
                {"sport_type": ["weighttraining", "weight training", "workout"]},
                {"strength_like": True},
            ],
        }
    if normalized == "trail":
        return {
            "kind": "activity",
            "description": "Trail run tags or high elevation-density heuristics.",
            "any_of": [
                {"sport_type": ["trailrun"]},
                {"gain_per_mile_ft_min": _settings_profile_trail_gain_per_mile_ft(settings)},
            ],
        }
    if normalized == "long_run":
        return {
            "kind": "activity",
            "description": "Long run workout tag or distance threshold.",
            "any_of": [
                {"workout_type": 2},
                {"strava_tags_any": ["long_run"]},
                {"distance_miles_min": _settings_profile_long_run_miles(settings)},
            ],
        }
    if normalized == "pet":
        return {
            "kind": "activity",
            "description": "Pet/dog keywords in activity title or notes.",
            "text_contains_any": ["dog", "with dog", "canicross", "🐕"],
        }
    if normalized == "away":
        criteria = {
            "kind": "location",
            "description": "Outside home geofence when GPS is available.",
        }
        geofence = _settings_home_geofence(settings, mode="outside")
        if geofence is not None:
            criteria["start_geofence"] = geofence
        return criteria
    if normalized == "home":
        criteria = {
            "kind": "location",
            "description": "Inside home geofence when GPS is available.",
        }
        geofence = _settings_home_geofence(settings, mode="within")
        if geofence is not None:
            criteria["start_geofence"] = geofence
        return criteria
    return {"kind": "activity", "description": f"{normalized.title()} profile"}


def _profile_builtin_map(settings: Settings | None = None) -> dict[str, dict[str, Any]]:
    builtins: dict[str, dict[str, Any]] = {}
    for profile in PROFILE_BUILTINS:
        profile_id = _normalize_profile_id(profile.get("profile_id"))
        if not profile_id:
            continue
        record = deepcopy(profile)
        record["profile_id"] = profile_id
        record["criteria"] = deepcopy(_profile_builtin_criteria(settings, profile_id))
        record["label"] = str(profile.get("label") or profile_id.title())
        record["enabled"] = _coerce_bool(profile.get("enabled"), default=True)
        record["locked"] = _coerce_bool(profile.get("locked"), default=False)
        try:
            record["priority"] = int(profile.get("priority", 0))
        except (TypeError, ValueError):
            record["priority"] = 0
        builtins[profile_id] = record
    if DEFAULT_PROFILE_ID not in builtins:
        builtins[DEFAULT_PROFILE_ID] = {
            "profile_id": DEFAULT_PROFILE_ID,
            "label": "Default",
            "enabled": True,
            "locked": True,
            "priority": 0,
            "criteria": _profile_builtin_criteria(settings, DEFAULT_PROFILE_ID),
        }
    return builtins


_PROFILE_RULE_META_KEYS = {
    "kind",
    "description",
    "label",
    "name",
    "version",
    "notes",
}
_PROFILE_RULE_STRING_LIST_KEYS = {
    "sport_type",
    "text_contains",
    "text_contains_any",
    "name_contains",
    "name_contains_any",
    "text_not_contains",
    "name_not_contains",
    "external_id_contains",
    "device_name_contains",
    "strava_tags_any",
    "strava_tags_all",
    "day_of_week_in",
    "garmin_activity_type_in",
}
_PROFILE_RULE_BOOL_KEYS = {
    "trainer",
    "commute",
    "has_gps",
    "treadmill",
    "strength_like",
}
_PROFILE_RULE_NUMERIC_KEYS = {
    "distance_miles_min",
    "distance_miles_max",
    "moving_time_seconds_min",
    "moving_time_seconds_max",
    "moving_time_minutes_min",
    "moving_time_minutes_max",
    "gain_per_mile_ft_min",
    "gain_per_mile_ft_max",
    "home_distance_miles_min",
    "home_distance_miles_max",
}
_PROFILE_RULE_TIME_KEYS = {
    "time_of_day_after",
    "time_of_day_before",
}
_PROFILE_RULE_COMPOUND_KEYS = {
    "all_of",
    "any_of",
    "none_of",
}
_PROFILE_TOP_LEVEL_KEYS = {
    "profile_id",
    "label",
    "priority",
    "criteria",
    "enabled",
}


def _criteria_time_value_is_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    parts = text.split(":")
    if len(parts) != 2:
        return False
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _normalize_profile_rule_string(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string.")
    return text


def _normalize_profile_rule_string_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        raise ValueError(f"{field} must be a string or list of strings.")
    normalized: list[str] = []
    for item in items:
        normalized.append(_normalize_profile_rule_string(item, field=field))
    if not normalized:
        raise ValueError(f"{field} must include at least one value.")
    return normalized


def _normalize_profile_rule_number(value: Any, *, field: str) -> float:
    number = _shared_as_float(value)
    if number is None:
        raise ValueError(f"{field} must be numeric.")
    return float(number)


def _criteria_has_executable_rules(criteria: dict[str, Any] | None) -> bool:
    if not isinstance(criteria, dict):
        return False
    for key, value in criteria.items():
        if key in _PROFILE_RULE_META_KEYS:
            continue
        if key in _PROFILE_RULE_COMPOUND_KEYS:
            if isinstance(value, dict):
                if _criteria_has_executable_rules(value):
                    return True
                continue
            if isinstance(value, (list, tuple)):
                if any(_criteria_has_executable_rules(item) for item in value if isinstance(item, dict)):
                    return True
                continue
        return True
    return False


def validate_template_profile_criteria(
    raw_criteria: Any,
    *,
    require_executable: bool,
    field: str = "criteria",
) -> dict[str, Any]:
    if raw_criteria is None:
        criteria: dict[str, Any] = {}
    elif isinstance(raw_criteria, dict):
        criteria = raw_criteria
    else:
        raise ValueError(f"{field} must be an object.")

    normalized: dict[str, Any] = {}
    for key, value in criteria.items():
        if key in _PROFILE_RULE_META_KEYS:
            if value is None:
                continue
            normalized[key] = _normalize_profile_rule_string(value, field=f"{field}.{key}")
            continue

        child_field = f"{field}.{key}"
        if key in _PROFILE_RULE_COMPOUND_KEYS:
            if isinstance(value, dict):
                normalized[key] = [validate_template_profile_criteria(value, require_executable=True, field=child_field)]
                continue
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"{child_field} must be a rule object or list of rule objects.")
            clauses: list[dict[str, Any]] = []
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    raise ValueError(f"{child_field}[{index}] must be an object.")
                clauses.append(
                    validate_template_profile_criteria(
                        item,
                        require_executable=True,
                        field=f"{child_field}[{index}]",
                    )
                )
            if not clauses:
                raise ValueError(f"{child_field} must include at least one rule.")
            normalized[key] = clauses
            continue

        if key in _PROFILE_RULE_STRING_LIST_KEYS:
            normalized[key] = _normalize_profile_rule_string_list(value, field=child_field)
            continue

        if key in _PROFILE_RULE_BOOL_KEYS:
            try:
                normalized[key] = _parse_profile_import_bool(value)
            except ValueError as exc:
                raise ValueError(f"{child_field} must be a boolean.") from exc
            continue

        if key in _PROFILE_RULE_NUMERIC_KEYS:
            normalized[key] = _normalize_profile_rule_number(value, field=child_field)
            continue

        if key == "workout_type":
            try:
                normalized[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{child_field} must be an integer.") from exc
            continue

        if key in _PROFILE_RULE_TIME_KEYS:
            if not _criteria_time_value_is_valid(value):
                raise ValueError(f"{child_field} must use HH:MM 24-hour time.")
            normalized[key] = str(value).strip()
            continue

        if key == "start_geofence":
            if not isinstance(value, dict):
                raise ValueError(f"{child_field} must be an object.")
            latitude = _shared_as_float(value.get("latitude"))
            longitude = _shared_as_float(value.get("longitude"))
            radius_miles = _shared_as_float(value.get("radius_miles"))
            mode = str(value.get("mode") or "within").strip().lower()
            if latitude is None or longitude is None:
                raise ValueError(f"{child_field} requires latitude and longitude.")
            if radius_miles is None or radius_miles < 0:
                raise ValueError(f"{child_field}.radius_miles must be >= 0.")
            if mode not in {"within", "outside"}:
                raise ValueError(f"{child_field}.mode must be 'within' or 'outside'.")
            normalized[key] = {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "radius_miles": float(radius_miles),
                "mode": mode,
            }
            continue

        raise ValueError(f"Unsupported criteria key: {child_field}")

    if require_executable and not _criteria_has_executable_rules(normalized):
        raise ValueError(f"{field} must include at least one executable rule.")
    return normalized


def _profile_invalid_record_shape(profile_id: str, *, source_path: str, load_error: str) -> dict[str, Any]:
    normalized_id = _normalize_profile_id(profile_id) or "invalid-profile"
    return {
        "profile_id": normalized_id,
        "label": normalized_id.replace("-", " ").title(),
        "enabled": False,
        "locked": False,
        "priority": 0,
        "criteria": {},
        "invalid": True,
        "load_error": load_error,
        "source_path": source_path,
        "storage_format": "yaml",
    }


def _profile_record_shape(record: dict[str, Any], builtin: dict[str, Any]) -> dict[str, Any]:
    shaped = deepcopy(builtin)
    shaped["label"] = str(record.get("label") or builtin.get("label") or shaped["profile_id"])
    shaped["enabled"] = _coerce_bool(record.get("enabled"), default=_coerce_bool(builtin.get("enabled"), default=True))
    shaped["locked"] = _coerce_bool(builtin.get("locked"), default=False)
    try:
        shaped["priority"] = int(record.get("priority", builtin.get("priority", 0)))
    except (TypeError, ValueError):
        shaped["priority"] = int(builtin.get("priority", 0))
    criteria_raw = record.get("criteria")
    shaped["criteria"] = deepcopy(criteria_raw if isinstance(criteria_raw, dict) else builtin.get("criteria", {}))
    if shaped["profile_id"] == DEFAULT_PROFILE_ID:
        shaped["enabled"] = True
        shaped["locked"] = True
        shaped["priority"] = 0
    return shaped


def _custom_profile_record_shape(record: dict[str, Any], profile_id: str) -> dict[str, Any]:
    try:
        priority = int(record.get("priority", 0))
    except (TypeError, ValueError):
        priority = 0
    criteria_raw = record.get("criteria")
    return {
        "profile_id": profile_id,
        "label": str(record.get("label") or profile_id.title()),
        "enabled": _coerce_bool(record.get("enabled"), default=True),
        "locked": False,
        "priority": priority,
        "criteria": deepcopy(criteria_raw if isinstance(criteria_raw, dict) else {}),
    }


def _profile_record_for_yaml(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": str(record.get("profile_id") or DEFAULT_PROFILE_ID),
        "label": str(record.get("label") or record.get("profile_id") or DEFAULT_PROFILE_ID.title()),
        "priority": int(record.get("priority", 0)),
        "criteria": deepcopy(record.get("criteria") if isinstance(record.get("criteria"), dict) else {}),
    }


def _load_template_profiles_from_json(settings: Settings) -> dict[str, Any] | None:
    payload = _read_json_file(_template_profiles_path(settings))
    if not isinstance(payload, dict):
        return None
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list):
        return None
    builtins = _profile_builtin_map(settings)
    shaped_profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue
        profile_id = _normalize_profile_id(item.get("profile_id"))
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        if profile_id in builtins:
            shaped_profiles.append(_profile_record_shape({"enabled": item.get("enabled")}, builtins[profile_id]))
        else:
            shaped_profiles.append(_custom_profile_record_shape(item, profile_id))

    for profile_id, builtin in builtins.items():
        if profile_id in seen:
            continue
        shaped_profiles.append(_profile_record_shape({}, builtin))

    working = _normalize_profile_id(payload.get("working_profile_id"))
    valid_ids = {profile["profile_id"] for profile in shaped_profiles if profile.get("enabled")}
    if not working or working not in valid_ids:
        working = DEFAULT_PROFILE_ID

    return {
        "version": PROFILE_CONFIG_VERSION,
        "working_profile_id": working,
        "profiles": shaped_profiles,
    }


def _load_template_profiles_from_yaml(settings: Settings) -> dict[str, Any] | None:
    rules_dir = _profile_rules_dir(settings)
    if not rules_dir.exists():
        return None
    raw_paths = sorted(
        path
        for path in rules_dir.glob("*.yaml")
        if path.name != _profile_rules_state_path(settings).name
    )
    if not raw_paths:
        return None

    builtins = _profile_builtin_map(settings)
    state_payload = _read_yaml_file(_profile_rules_state_path(settings)) or {}
    state_enabled = state_payload.get("profile_enabled")
    enabled_overrides = state_enabled if isinstance(state_enabled, dict) else {}
    shaped_profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in raw_paths:
        profile_id = _normalize_profile_id(path.stem)
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        if profile_id in builtins:
            shaped_profiles.append(
                _profile_record_shape(
                    {"enabled": enabled_overrides.get(profile_id, builtins[profile_id].get("enabled"))},
                    builtins[profile_id],
                )
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
            payload = yaml.safe_load(text)
        except (OSError, yaml.YAMLError) as exc:
            shaped_profiles.append(
                _profile_invalid_record_shape(
                    profile_id,
                    source_path=str(path),
                    load_error=f"Invalid profile YAML: {exc}",
                )
            )
            continue
        if not isinstance(payload, dict):
            shaped_profiles.append(
                _profile_invalid_record_shape(
                    profile_id,
                    source_path=str(path),
                    load_error="Profile YAML must be an object.",
                )
            )
            continue
        try:
            normalized_payload = {
                "profile_id": profile_id,
                "label": str(payload.get("label") or profile_id.title()),
                "enabled": _parse_profile_import_bool(enabled_overrides.get(profile_id, payload.get("enabled", True))),
                "locked": False,
                "priority": int(payload.get("priority", 0)),
                "criteria": validate_template_profile_criteria(
                    payload.get("criteria"),
                    require_executable=profile_id != DEFAULT_PROFILE_ID,
                    field=f"profile_rules.{profile_id}.criteria",
                ),
            }
        except ValueError as exc:
            shaped_profiles.append(
                _profile_invalid_record_shape(
                    profile_id,
                    source_path=str(path),
                    load_error=str(exc),
                )
            )
            continue
        shaped_profiles.append(_custom_profile_record_shape(normalized_payload, profile_id))

    for profile_id, builtin in builtins.items():
        if profile_id in seen:
            continue
        shaped_profiles.append(
            _profile_record_shape(
                {"enabled": enabled_overrides.get(profile_id, builtin.get("enabled"))},
                builtin,
            )
        )

    working = _normalize_profile_id(state_payload.get("working_profile_id"))
    valid_ids = {profile["profile_id"] for profile in shaped_profiles if profile.get("enabled")}
    if not working or working not in valid_ids:
        working = DEFAULT_PROFILE_ID

    return {
        "version": PROFILE_CONFIG_VERSION,
        "working_profile_id": working,
        "profiles": shaped_profiles,
    }


def _load_template_profiles(settings: Settings) -> dict[str, Any] | None:
    from_yaml = _load_template_profiles_from_yaml(settings)
    if from_yaml is not None:
        return from_yaml
    return _load_template_profiles_from_json(settings)


def _save_template_profiles_json_mirror(settings: Settings, config: dict[str, Any]) -> None:
    payload = {
        "version": PROFILE_CONFIG_VERSION,
        "working_profile_id": str(config.get("working_profile_id") or DEFAULT_PROFILE_ID),
        "profiles": deepcopy(config.get("profiles") if isinstance(config.get("profiles"), list) else []),
    }
    _write_json_file(_template_profiles_path(settings), payload)


def _save_template_profiles(settings: Settings, config: dict[str, Any]) -> None:
    profiles = deepcopy(config.get("profiles") if isinstance(config.get("profiles"), list) else [])
    valid_ids: set[str] = set()
    enabled_map: dict[str, bool] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = _normalize_profile_id(profile.get("profile_id"))
        if not profile_id:
            continue
        valid_ids.add(profile_id)
        enabled_map[profile_id] = _coerce_bool(profile.get("enabled"), default=True)
        _write_yaml_file(_profile_rule_path(settings, profile_id), _profile_record_for_yaml(profile))

    rules_dir = _profile_rules_dir(settings)
    if rules_dir.exists():
        for path in rules_dir.glob("*.yaml"):
            if path.name == _profile_rules_state_path(settings).name:
                continue
            if path.stem not in valid_ids:
                path.unlink(missing_ok=True)

    _write_yaml_file(
        _profile_rules_state_path(settings),
        {
            "version": PROFILE_CONFIG_VERSION,
            "working_profile_id": str(config.get("working_profile_id") or DEFAULT_PROFILE_ID),
            "profile_enabled": enabled_map,
        },
    )
    _save_template_profiles_json_mirror(settings, config)


def _profile_template_seed(profile_id: str) -> str:
    template = PROFILE_TEMPLATE_DEFAULTS.get(profile_id, get_default_template())
    return _normalize_template_text(template)


def _ensure_template_profiles(settings: Settings) -> dict[str, Any]:
    config = _load_template_profiles(settings)
    if config is None:
        builtins = _profile_builtin_map(settings)
        config = {
            "version": PROFILE_CONFIG_VERSION,
            "working_profile_id": DEFAULT_PROFILE_ID,
            "profiles": [_profile_record_shape({}, builtins[profile_id]) for profile_id in builtins],
        }
        _save_template_profiles(settings, config)
    elif _load_template_profiles_from_yaml(settings) is None:
        _save_template_profiles(settings, config)

    for profile in config["profiles"]:
        profile_id = str(profile["profile_id"])
        if profile_id == DEFAULT_PROFILE_ID or bool(profile.get("invalid")):
            continue
        template_path = _template_profile_template_path(settings, profile_id)
        if not template_path.exists():
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(_profile_template_seed(profile_id) + "\n", encoding="utf-8")

        meta_path = _template_profile_meta_path(settings, profile_id)
        if not meta_path.exists():
            defaults = _profile_template_metadata_defaults(str(profile.get("label") or profile_id.title()))
            _write_json_file(meta_path, defaults)

    return config


def list_template_profiles(settings: Settings) -> list[dict[str, Any]]:
    config = _ensure_template_profiles(settings)
    builtin_ids = set(_profile_builtin_map(settings).keys())
    rows: list[dict[str, Any]] = []
    for profile in config["profiles"]:
        profile_id = str(profile.get("profile_id") or DEFAULT_PROFILE_ID)
        meta = _load_template_metadata(settings, profile_id=profile_id)
        rows.append(
            {
                "profile_id": profile_id,
                "label": str(profile.get("label") or profile_id.title()),
                "enabled": _coerce_bool(profile.get("enabled"), default=True),
                "locked": _coerce_bool(profile.get("locked"), default=False),
                "priority": int(profile.get("priority", 0)),
                "criteria": deepcopy(profile.get("criteria") if isinstance(profile.get("criteria"), dict) else {}),
                "template_name": str(meta.get("name") or f"{profile_id.title()} Template"),
                "current_version": meta.get("current_version"),
                "updated_at_utc": meta.get("updated_at_utc"),
                "updated_by": meta.get("updated_by"),
                "source": meta.get("source"),
                "is_builtin": profile_id in builtin_ids,
                "source_path": str(profile.get("source_path") or _profile_rule_path(settings, profile_id)),
                "storage_format": "yaml",
                "invalid": bool(profile.get("invalid")),
                "load_error": str(profile.get("load_error") or ""),
            }
        )
    rows.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("label") or "").lower()))
    return rows


def get_template_profile(settings: Settings, profile_id: str) -> dict[str, Any] | None:
    target = _normalize_profile_id(profile_id)
    if not target:
        return None
    for profile in list_template_profiles(settings):
        if str(profile.get("profile_id")) == target:
            return profile
    return None


def get_working_template_profile(settings: Settings) -> dict[str, Any]:
    config = _ensure_template_profiles(settings)
    working = str(config.get("working_profile_id") or DEFAULT_PROFILE_ID)
    profile = get_template_profile(settings, working)
    if profile is None:
        profile = get_template_profile(settings, DEFAULT_PROFILE_ID)
    if profile is None:
        raise ValueError("Default profile is missing from template profile configuration.")
    return profile


def set_working_template_profile(settings: Settings, profile_id: str) -> dict[str, Any]:
    target = _normalize_profile_id(profile_id)
    if not target:
        raise ValueError("profile_id is required.")
    config = _ensure_template_profiles(settings)
    indexed = {str(item.get("profile_id")): item for item in config["profiles"]}
    profile = indexed.get(target)
    if profile is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    if not bool(profile.get("enabled")):
        raise ValueError(f"Profile is disabled: {target}")
    config["working_profile_id"] = target
    _save_template_profiles(settings, config)
    updated = get_template_profile(settings, target)
    if updated is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    return updated


def create_template_profile(
    settings: Settings,
    profile_id: str,
    *,
    label: str | None = None,
    criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = _normalize_profile_id(profile_id)
    if not target:
        raise ValueError("profile_id is required.")
    if get_template_profile(settings, target) is not None:
        raise ValueError(f"profile_id already exists: {target}")

    if label is None:
        normalized_label = target.title()
    else:
        normalized_label = str(label).strip()
        if not normalized_label:
            raise ValueError("label is required.")

    normalized_criteria = validate_template_profile_criteria(
        criteria,
        require_executable=True,
        field="criteria",
    )

    config = _ensure_template_profiles(settings)
    config["profiles"].append(
        {
            "profile_id": target,
            "label": normalized_label,
            "enabled": True,
            "locked": False,
            "priority": 0,
            "criteria": normalized_criteria,
        }
    )
    _save_template_profiles(settings, config)
    _ensure_template_profiles(settings)
    created = get_template_profile(settings, target)
    if created is None:
        raise ValueError(f"Unknown profile_id: {target}")
    return created


def update_template_profile(
    settings: Settings,
    profile_id: str,
    *,
    enabled: bool | None = None,
    priority: int | None = None,
    label: str | None = None,
    criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = _normalize_profile_id(profile_id)
    if not target:
        raise ValueError("profile_id is required.")
    config = _ensure_template_profiles(settings)
    found = None
    for item in config["profiles"]:
        if str(item.get("profile_id")) == target:
            found = item
            break
    if found is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    is_builtin = target in _profile_builtin_map(settings)

    parsed_label: str | None = None
    if label is not None:
        parsed_label = str(label).strip()
        if not parsed_label:
            raise ValueError("label is required.")
    parsed_criteria: dict[str, Any] | None = None
    if criteria is not None:
        parsed_criteria = validate_template_profile_criteria(
            criteria,
            require_executable=True,
            field="criteria",
        )

    locked = bool(found.get("locked"))
    if is_builtin and (parsed_label is not None or parsed_criteria is not None or priority is not None):
        raise ValueError("Builtin profiles are immutable. Duplicate the profile to customize it.")
    if parsed_label is not None:
        if locked:
            raise ValueError("Default profile cannot be renamed.")
        found["label"] = parsed_label
    if parsed_criteria is not None:
        if locked:
            raise ValueError("Default profile criteria cannot be edited.")
        found["criteria"] = deepcopy(parsed_criteria)
    if enabled is not None:
        if locked and not bool(enabled):
            raise ValueError("Default profile cannot be disabled.")
        found["enabled"] = bool(enabled)
    if priority is not None:
        if locked:
            found["priority"] = 0
        else:
            found["priority"] = int(priority)

    if not bool(found.get("enabled")) and str(config.get("working_profile_id")) == target:
        config["working_profile_id"] = DEFAULT_PROFILE_ID

    _save_template_profiles(settings, config)
    updated = get_template_profile(settings, target)
    if updated is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    return updated


def _parse_profile_yaml_text(yaml_text: str) -> dict[str, Any]:
    text = str(yaml_text or "").strip()
    if not text:
        raise ValueError("yaml_text is required.")
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Profile YAML must be an object.")
    return payload


def parse_template_profile_yaml_document(
    yaml_text: str,
    *,
    profile_id: str | None = None,
    profile_name: str | None = None,
) -> dict[str, Any]:
    payload = _parse_profile_yaml_text(yaml_text)
    extra_keys = sorted(key for key in payload.keys() if key not in _PROFILE_TOP_LEVEL_KEYS)
    if extra_keys:
        raise ValueError(f"Unsupported top-level profile keys: {', '.join(extra_keys)}")
    target = _normalize_profile_id(payload.get("profile_id") or profile_id or profile_name)
    if not target:
        raise ValueError("profile_id is required in YAML or profile_name.")
    label_raw = payload.get("label")
    label = str(label_raw).strip() if isinstance(label_raw, str) and label_raw.strip() else target.title()
    try:
        priority = int(payload.get("priority", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("priority must be an integer.") from exc
    if "enabled" in payload:
        _parse_profile_import_bool(payload.get("enabled", True))
    criteria = validate_template_profile_criteria(
        payload.get("criteria"),
        require_executable=target != DEFAULT_PROFILE_ID,
        field="criteria",
    )
    return {
        "profile_id": target,
        "label": label,
        "priority": priority,
        "criteria": deepcopy(criteria),
    }


def get_template_profile_document(settings: Settings, profile_id: str) -> dict[str, Any]:
    profile = get_template_profile(settings, profile_id)
    if profile is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    target = str(profile.get("profile_id") or DEFAULT_PROFILE_ID)
    path = _profile_rule_path(settings, target)
    if bool(profile.get("is_builtin")):
        yaml_text = yaml.safe_dump(_profile_record_for_yaml(profile), sort_keys=False, allow_unicode=True)
    elif bool(profile.get("invalid")):
        yaml_text = path.read_text(encoding="utf-8") if path.exists() else ""
    else:
        normalized_payload = _profile_record_for_yaml(profile)
        yaml_text = yaml.safe_dump(normalized_payload, sort_keys=False, allow_unicode=True)
        if not path.exists() or path.read_text(encoding="utf-8") != yaml_text:
            _write_yaml_file(path, normalized_payload)
    return {
        "profile": profile,
        "yaml_text": yaml_text,
        "source_path": str(path),
        "read_only": bool(profile.get("is_builtin")),
        "storage_format": "yaml",
        "invalid": bool(profile.get("invalid")),
        "load_error": str(profile.get("load_error") or ""),
    }


def create_template_profile_from_yaml(
    settings: Settings,
    *,
    yaml_text: str,
    profile_name: str | None = None,
) -> dict[str, Any]:
    payload = parse_template_profile_yaml_document(yaml_text, profile_name=profile_name)
    requested_id = str(payload.get("profile_id") or "")
    created = create_template_profile(
        settings,
        requested_id,
        label=str(payload.get("label") or requested_id.title()),
        criteria=payload.get("criteria") if isinstance(payload.get("criteria"), dict) else {},
    )
    priority = int(payload.get("priority", 0) or 0)
    if priority != 0:
        created = update_template_profile(settings, requested_id, priority=priority)
    return get_template_profile_document(settings, requested_id)


def save_template_profile_yaml(settings: Settings, profile_id: str, *, yaml_text: str) -> dict[str, Any]:
    existing = get_template_profile(settings, profile_id)
    if existing is None:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    if bool(existing.get("is_builtin")):
        raise ValueError("Builtin profiles are read-only in the YAML workshop. Duplicate the profile to customize it.")

    payload = parse_template_profile_yaml_document(yaml_text, profile_id=profile_id)
    target = _normalize_profile_id(payload.get("profile_id") or profile_id)
    if target != _normalize_profile_id(profile_id):
        raise ValueError("profile_id in YAML must match the selected profile.")

    update_template_profile(
        settings,
        target,
        priority=int(payload.get("priority", 0) or 0),
        label=str(payload.get("label") or target.title()),
        criteria=payload.get("criteria") if isinstance(payload.get("criteria"), dict) else {},
    )
    return get_template_profile_document(settings, target)


def export_template_profiles_bundle(
    settings: Settings,
    *,
    profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    profiles = list_template_profiles(settings)
    selected_ids: list[str] = []
    selected_set: set[str] = set()
    if profile_ids is not None:
        for raw_id in profile_ids:
            normalized = _normalize_profile_id(raw_id)
            if not normalized or normalized in selected_set:
                continue
            selected_set.add(normalized)
            selected_ids.append(normalized)
        if selected_ids:
            available_ids = {str(item.get("profile_id")) for item in profiles}
            missing = [profile_id for profile_id in selected_ids if profile_id not in available_ids]
            if missing:
                raise ValueError(f"Unknown profile_id: {missing[0]}")

    exported_profiles: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id") or "")
        if selected_ids and profile_id not in selected_set:
            continue
        exported_profiles.append(
            {
                "profile_id": profile_id,
                "label": str(profile.get("label") or profile_id.title()),
                "enabled": bool(profile.get("enabled")),
                "locked": bool(profile.get("locked")),
                "priority": int(profile.get("priority", 0)),
                "criteria": deepcopy(profile.get("criteria") if isinstance(profile.get("criteria"), dict) else {}),
            }
        )

    if not exported_profiles:
        raise ValueError("No profiles matched the selected export filter.")

    return {
        "bundle_version": 1,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "working_profile_id": str(get_working_template_profile(settings).get("profile_id") or DEFAULT_PROFILE_ID),
        "profiles": exported_profiles,
    }


def import_template_profiles_bundle(
    settings: Settings,
    *,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be a JSON object.")

    raw_profiles = bundle.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValueError("bundle.profiles must be a non-empty array.")

    config = _ensure_template_profiles(settings)
    next_profiles = deepcopy(config.get("profiles") if isinstance(config.get("profiles"), list) else [])
    index: dict[str, dict[str, Any]] = {}
    for item in next_profiles:
        if not isinstance(item, dict):
            continue
        profile_id = _normalize_profile_id(item.get("profile_id"))
        if not profile_id:
            continue
        index[profile_id] = item

    imported_profile_ids: list[str] = []
    errors: list[str] = []
    builtin_ids = set(_profile_builtin_map(settings).keys())

    for idx, entry in enumerate(raw_profiles):
        if not isinstance(entry, dict):
            errors.append(f"profiles[{idx}] must be an object.")
            continue

        profile_id = _normalize_profile_id(entry.get("profile_id"))
        if not profile_id:
            errors.append(f"profiles[{idx}].profile_id is required.")
            continue
        if profile_id in builtin_ids:
            errors.append(f"{profile_id} is builtin and cannot be imported.")
            continue

        label_raw = entry.get("label")
        label = str(label_raw).strip() if label_raw is not None else profile_id.title()
        if not label:
            errors.append(f"{profile_id}.label is required.")
            continue

        criteria_raw = entry.get("criteria")
        try:
            criteria = validate_template_profile_criteria(
                criteria_raw,
                require_executable=True,
                field=f"{profile_id}.criteria",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        try:
            enabled = _parse_profile_import_bool(entry.get("enabled", True))
        except ValueError:
            errors.append(f"{profile_id}.enabled must be a boolean.")
            continue

        try:
            priority = int(entry.get("priority", 0))
        except (TypeError, ValueError):
            errors.append(f"{profile_id}.priority must be an integer.")
            continue

        existing = index.get(profile_id)
        if existing is not None:
            if bool(existing.get("locked")) or profile_id in builtin_ids:
                errors.append(f"{profile_id} is locked and cannot be imported.")
                continue
            existing["label"] = label
            existing["enabled"] = enabled
            existing["priority"] = priority
            existing["criteria"] = criteria
        else:
            created = {
                "profile_id": profile_id,
                "label": label,
                "enabled": enabled,
                "locked": False,
                "priority": priority,
                "criteria": criteria,
            }
            next_profiles.append(created)
            index[profile_id] = created
        imported_profile_ids.append(profile_id)

    if not imported_profile_ids and errors:
        raise ValueError(errors[0])
    if not imported_profile_ids and not errors:
        raise ValueError("No importable profiles found in bundle.")

    next_working_profile_id = _normalize_profile_id(config.get("working_profile_id")) or DEFAULT_PROFILE_ID
    requested_working = _normalize_profile_id(bundle.get("working_profile_id"))
    if requested_working and requested_working in index and bool(index[requested_working].get("enabled")):
        next_working_profile_id = requested_working
    if next_working_profile_id not in index or not bool(index[next_working_profile_id].get("enabled")):
        next_working_profile_id = DEFAULT_PROFILE_ID

    _save_template_profiles(
        settings,
        {
            "version": PROFILE_CONFIG_VERSION,
            "working_profile_id": next_working_profile_id,
            "profiles": next_profiles,
        },
    )
    _ensure_template_profiles(settings)
    return {
        "imported_profile_ids": imported_profile_ids,
        "errors": errors,
        "working_profile_id": next_working_profile_id,
    }


def _template_path_for_profile(settings: Settings, profile_id: str) -> Path:
    normalized = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    if normalized == DEFAULT_PROFILE_ID:
        return _template_path(settings)
    return _template_profile_template_path(settings, normalized)


def _template_hash(template_text: str) -> str:
    normalized = _normalize_template_text(template_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _template_meta_path_for_profile(settings: Settings, profile_id: str) -> Path:
    normalized = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    if normalized == DEFAULT_PROFILE_ID:
        return _template_meta_path(settings)
    return _template_profile_meta_path(settings, normalized)


def _template_versions_dir_for_profile(settings: Settings, profile_id: str) -> Path:
    normalized = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    if normalized == DEFAULT_PROFILE_ID:
        return _template_versions_dir(settings)
    return _template_profile_versions_dir(settings, normalized)


def _template_repository_builtin_records(settings: Settings | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "template_id": "builtin-default",
            "name": "Default - Full Data Rich",
            "author": "system",
            "description": "Project default template (full data rich layout).",
            "template": get_default_template(),
            "source": "builtin-default",
            "created_at_utc": None,
            "updated_at_utc": None,
            "is_builtin": True,
            "can_overwrite": False,
        }
    ]
    for starter in get_starter_templates():
        starter_id = _normalize_template_id(starter.get("id"))
        if not starter_id:
            continue
        records.append(
            {
                "template_id": f"starter-{starter_id}",
                "name": str(starter.get("label") or starter_id),
                "author": "system",
                "description": str(starter.get("description") or ""),
                "template": _normalize_template_text(str(starter.get("template") or "")),
                "source": f"builtin-starter:{starter_id}",
                "created_at_utc": None,
                "updated_at_utc": None,
                "is_builtin": True,
                "can_overwrite": False,
            }
        )
    profile_builtins = sorted(
        _profile_builtin_map(settings).values(),
        key=lambda item: (
            -int(item.get("priority", 0)),
            str(item.get("label") or item.get("profile_id") or "").lower(),
        ),
    )
    for profile in profile_builtins:
        profile_id = _normalize_profile_id(profile.get("profile_id"))
        if not profile_id or profile_id == DEFAULT_PROFILE_ID:
            continue
        label = str(profile.get("label") or profile_id.title())
        records.append(
            {
                "template_id": f"profile-default-{profile_id}",
                "name": f"Profile Default - {label}",
                "author": "system",
                "description": f"Default template seed for the {label} profile.",
                "template": _normalize_template_text(_profile_template_seed(profile_id)),
                "source": f"builtin-profile-default:{profile_id}",
                "created_at_utc": None,
                "updated_at_utc": None,
                "is_builtin": True,
                "can_overwrite": False,
            }
        )
    return records


def _template_repository_record_shape(
    record: dict[str, Any] | None,
    *,
    fallback_id: str | None = None,
    default_source: str = "repository",
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None

    template_text = record.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        return None

    raw_id = record.get("template_id")
    if raw_id is None:
        raw_id = record.get("id")
    if raw_id is None:
        raw_id = fallback_id
    template_id = _normalize_template_id(str(raw_id or ""))
    if not template_id:
        return None

    name = str(record.get("name") or "Untitled Template").strip() or "Untitled Template"
    author = str(record.get("author") or "unknown").strip() or "unknown"
    description_raw = record.get("description")
    description = str(description_raw).strip() if description_raw is not None else ""
    source = str(record.get("source") or default_source).strip() or default_source
    created_at_utc = record.get("created_at_utc")
    updated_at_utc = record.get("updated_at_utc")
    is_builtin = bool(record.get("is_builtin"))

    return {
        "template_id": template_id,
        "name": name,
        "author": author,
        "description": description,
        "template": _normalize_template_text(template_text),
        "source": source,
        "created_at_utc": created_at_utc if isinstance(created_at_utc, str) else None,
        "updated_at_utc": updated_at_utc if isinstance(updated_at_utc, str) else None,
        "is_builtin": is_builtin,
        "can_overwrite": not is_builtin,
    }


def _template_repository_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_id": record["template_id"],
        "name": record["name"],
        "author": record["author"],
        "description": record["description"],
        "source": record["source"],
        "created_at_utc": record["created_at_utc"],
        "updated_at_utc": record["updated_at_utc"],
        "is_builtin": record["is_builtin"],
        "can_overwrite": record["can_overwrite"],
        "template_chars": len(str(record.get("template") or "")),
    }


def _template_repository_path(settings: Settings, template_id: str) -> Path:
    safe_id = _normalize_template_id(template_id)
    if not safe_id:
        raise ValueError("template_id is required.")
    return _template_repository_dir(settings) / f"{safe_id}.json"


def _new_template_repository_id(name: str, template_text: str) -> str:
    slug = _normalize_template_id(name) or "template"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256((name + "\n" + template_text).encode("utf-8")).hexdigest()[:8]
    return f"tpl-{slug[:40]}-{stamp}-{digest}".lower()


def list_template_repository_templates(settings: Settings) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for builtin in _template_repository_builtin_records(settings):
        records[builtin["template_id"]] = builtin

    repo_dir = _template_repository_dir(settings)
    if repo_dir.exists():
        for path in sorted(repo_dir.glob("*.json")):
            loaded = _template_repository_record_shape(_read_json_file(path), fallback_id=path.stem)
            if not loaded:
                continue
            records[loaded["template_id"]] = loaded

    ordered = sorted(
        records.values(),
        key=lambda item: (
            0 if item.get("is_builtin") else 1,
            str(item.get("name") or "").lower(),
            str(item.get("template_id") or ""),
        ),
    )
    return [_template_repository_summary(item) for item in ordered]


def get_template_repository_template(settings: Settings, template_id: str) -> dict[str, Any] | None:
    normalized_id = _normalize_template_id(template_id)
    if not normalized_id:
        return None

    for builtin in _template_repository_builtin_records(settings):
        if builtin["template_id"] == normalized_id:
            return deepcopy(builtin)

    loaded = _template_repository_record_shape(
        _read_json_file(_template_repository_path(settings, normalized_id)),
        fallback_id=normalized_id,
    )
    if loaded is None:
        return None
    return loaded


def create_template_repository_template(
    settings: Settings,
    *,
    template_text: str,
    name: str | None,
    author: str | None,
    description: str | None = None,
    source: str = "editor-save-as",
) -> dict[str, Any]:
    normalized = _normalize_template_text(template_text)
    if not normalized:
        raise ValueError("template_text must not be empty.")

    base_name = str(name or "Untitled Template").strip() or "Untitled Template"
    base_author = str(author or "unknown").strip() or "unknown"
    now_iso = datetime.now(timezone.utc).isoformat()
    template_id = _new_template_repository_id(base_name, normalized)
    path = _template_repository_path(settings, template_id)
    while path.exists():
        template_id = _new_template_repository_id(base_name, normalized + now_iso)
        path = _template_repository_path(settings, template_id)

    record = {
        "template_id": template_id,
        "name": base_name,
        "author": base_author,
        "description": str(description or "").strip(),
        "template": normalized,
        "source": str(source or "editor-save-as").strip() or "editor-save-as",
        "created_at_utc": now_iso,
        "updated_at_utc": now_iso,
        "is_builtin": False,
        "can_overwrite": True,
    }
    _write_json_file(path, record)
    return record


def update_template_repository_template(
    settings: Settings,
    *,
    template_id: str,
    template_text: str | None = None,
    name: str | None = None,
    author: str | None = None,
    description: str | None = None,
    source: str = "editor-save",
) -> dict[str, Any]:
    current = get_template_repository_template(settings, template_id)
    if not current:
        raise ValueError(f"Unknown template_id: {template_id}")
    if current.get("is_builtin"):
        raise ValueError("Built-in templates cannot be overwritten. Use Save As instead.")

    normalized_template = (
        _normalize_template_text(template_text)
        if template_text is not None
        else str(current.get("template") or "")
    )
    if not normalized_template:
        raise ValueError("template_text must not be empty.")

    updated = {
        "template_id": str(current["template_id"]),
        "name": (
            str(name).strip()
            if name is not None
            else str(current.get("name") or "Untitled Template")
        )
        or "Untitled Template",
        "author": (
            str(author).strip()
            if author is not None
            else str(current.get("author") or "unknown")
        )
        or "unknown",
        "description": (
            str(description).strip()
            if description is not None
            else str(current.get("description") or "")
        ),
        "template": normalized_template,
        "source": str(source or current.get("source") or "editor-save").strip()
        or "editor-save",
        "created_at_utc": current.get("created_at_utc"),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "is_builtin": False,
        "can_overwrite": True,
    }
    _write_json_file(_template_repository_path(settings, updated["template_id"]), updated)
    return updated


def duplicate_template_repository_template(
    settings: Settings,
    *,
    template_id: str,
    name: str | None = None,
    author: str | None = None,
    source: str = "editor-duplicate",
) -> dict[str, Any]:
    base = get_template_repository_template(settings, template_id)
    if not base:
        raise ValueError(f"Unknown template_id: {template_id}")
    duplicate_name = str(name or f"{base['name']} Copy").strip() or f"{base['name']} Copy"
    duplicate_author = str(author or base.get("author") or "unknown").strip() or "unknown"
    return create_template_repository_template(
        settings,
        template_text=str(base.get("template") or ""),
        name=duplicate_name,
        author=duplicate_author,
        description=str(base.get("description") or ""),
        source=source,
    )


def export_template_repository_bundle(
    settings: Settings,
    *,
    template_id: str,
    include_versions: bool = False,
    versions_limit: int = 30,
) -> dict[str, Any]:
    record = get_template_repository_template(settings, template_id)
    if not record:
        raise ValueError(f"Unknown template_id: {template_id}")

    payload: dict[str, Any] = {
        "bundle_version": 2,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "template_id": record.get("template_id"),
        "template": record.get("template"),
        "name": record.get("name"),
        "author": record.get("author"),
        "description": record.get("description"),
        "source": record.get("source"),
        "is_builtin": bool(record.get("is_builtin")),
        "metadata": {
            "updated_by": record.get("author"),
            "updated_at_utc": record.get("updated_at_utc"),
            "source": record.get("source"),
        },
    }
    if include_versions:
        payload["versions"] = list_template_versions(
            settings,
            limit=max(1, min(200, int(versions_limit))),
        )
    return payload


def import_template_repository_bundle(
    settings: Settings,
    *,
    bundle: dict[str, Any],
    author: str | None = None,
    source: str = "editor-import",
    name: str | None = None,
) -> dict[str, Any]:
    template_text = bundle.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        raise ValueError("bundle.template must be a non-empty string.")

    metadata = bundle.get("metadata")
    metadata_author = None
    if isinstance(metadata, dict):
        metadata_author = metadata.get("updated_by")

    resolved_name = str(
        name
        or bundle.get("name")
        or bundle.get("template_name")
        or "Imported Template"
    )
    resolved_author = str(author or bundle.get("author") or metadata_author or "unknown")
    resolved_description = str(bundle.get("description") or "")
    imported = create_template_repository_template(
        settings,
        template_text=template_text,
        name=resolved_name,
        author=resolved_author,
        description=resolved_description,
        source=source,
    )
    return imported


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _read_yaml_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _write_yaml_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _new_version_id(template_text: str) -> str:
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:10]
    return f"v{now.strftime('%Y%m%dT%H%M%S%fZ')}-{digest}"


def _template_metadata_defaults() -> dict[str, Any]:
    return {
        "name": "Chronicle Template",
        "current_version": None,
        "updated_at_utc": None,
        "updated_by": "system",
        "source": "default",
    }


def _load_template_metadata(settings: Settings, *, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    normalized_profile_id = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    data = _read_json_file(_template_meta_path_for_profile(settings, normalized_profile_id))
    if data is None:
        label = str(
            _profile_builtin_map(settings).get(normalized_profile_id, {}).get("label")
            or normalized_profile_id.title()
        )
        return _profile_template_metadata_defaults(label)
    defaults = _template_metadata_defaults()
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return defaults


def _save_template_metadata(
    settings: Settings,
    metadata: dict[str, Any],
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> None:
    merged = _template_metadata_defaults()
    merged.update({k: v for k, v in metadata.items() if k in merged})
    _write_json_file(_template_meta_path_for_profile(settings, profile_id), merged)


def _build_template_version_record(
    *,
    template_text: str,
    name: str,
    author: str,
    source: str,
    notes: str | None,
    operation: str,
    rolled_back_from: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_template_text(template_text)
    now_iso = datetime.now(timezone.utc).isoformat()
    version_id = _new_version_id(normalized)
    return {
        "version_id": version_id,
        "name": name.strip() or "Chronicle Template",
        "author": author.strip() or "unknown",
        "source": source.strip() or "editor",
        "operation": operation,
        "notes": (notes or "").strip() or None,
        "rolled_back_from": rolled_back_from,
        "created_at_utc": now_iso,
        "template_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "template": normalized,
    }


def _store_template_version(
    settings: Settings,
    record: dict[str, Any],
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> None:
    versions_dir = _template_versions_dir_for_profile(settings, profile_id)
    version_id = str(record.get("version_id") or "").strip()
    if not version_id:
        raise ValueError("Template version record missing version_id.")
    version_path = versions_dir / f"{version_id}.json"
    _write_json_file(version_path, record)


def get_template_version(
    settings: Settings,
    version_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> dict[str, Any] | None:
    _ensure_template_profiles(settings)
    version_key = version_id.strip()
    if not version_key:
        return None
    version_path = _template_versions_dir_for_profile(settings, profile_id) / f"{version_key}.json"
    return _read_json_file(version_path)


def list_template_versions(
    settings: Settings,
    limit: int = 50,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> list[dict[str, Any]]:
    _ensure_template_profiles(settings)
    versions_dir = _template_versions_dir_for_profile(settings, profile_id)
    if not versions_dir.exists():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(versions_dir.glob("*.json"), reverse=True):
        record = _read_json_file(path)
        if not record:
            continue
        records.append(
            {
                "version_id": record.get("version_id"),
                "name": record.get("name"),
                "author": record.get("author"),
                "source": record.get("source"),
                "operation": record.get("operation"),
                "notes": record.get("notes"),
                "rolled_back_from": record.get("rolled_back_from"),
                "created_at_utc": record.get("created_at_utc"),
                "template_sha256": record.get("template_sha256"),
            }
        )
        if len(records) >= max(1, int(limit)):
            break
    return records


def rollback_template_version(
    settings: Settings,
    *,
    version_id: str,
    author: str = "unknown",
    source: str = "rollback",
    notes: str | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> dict[str, Any]:
    record = get_template_version(settings, version_id, profile_id=profile_id)
    if not record:
        raise ValueError(f"Unknown template version: {version_id}")

    template_text = record.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        raise ValueError("Selected template version has no template body.")

    current = get_active_template(settings, profile_id=profile_id)
    rollback_name = str(record.get("name") or current.get("name") or "Chronicle Template")
    saved = save_active_template(
        settings,
        template_text,
        name=rollback_name,
        author=author,
        source=source,
        notes=notes or f"Rollback to {version_id}",
        operation="rollback",
        rolled_back_from=version_id,
        profile_id=profile_id,
    )
    return saved


def get_active_template(settings: Settings, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    config = _ensure_template_profiles(settings)
    normalized_profile_id = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    valid_ids = {str(item.get("profile_id")) for item in config.get("profiles", [])}
    if normalized_profile_id not in valid_ids:
        normalized_profile_id = DEFAULT_PROFILE_ID
    profile = get_template_profile(settings, normalized_profile_id)
    path = _template_path_for_profile(settings, normalized_profile_id)
    metadata = _load_template_metadata(settings, profile_id=normalized_profile_id)
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            normalized_text = _normalize_template_text(text)
            return {
                "template": normalized_text,
                "is_custom": True,
                "path": str(path),
                "profile_id": normalized_profile_id,
                "profile_label": str(profile.get("label") or normalized_profile_id.title()) if profile else normalized_profile_id.title(),
                "template_hash": _template_hash(normalized_text),
                "name": metadata.get("name"),
                "current_version": metadata.get("current_version"),
                "updated_at_utc": metadata.get("updated_at_utc"),
                "updated_by": metadata.get("updated_by"),
                "source": metadata.get("source"),
                "metadata": metadata,
            }
    default_meta = _template_metadata_defaults()
    seeded_template = _profile_template_seed(normalized_profile_id)
    return {
        "template": seeded_template,
        "is_custom": False,
        "path": str(path),
        "profile_id": normalized_profile_id,
        "profile_label": str(profile.get("label") or normalized_profile_id.title()) if profile else normalized_profile_id.title(),
        "template_hash": _template_hash(seeded_template),
        "name": default_meta["name"],
        "current_version": None,
        "updated_at_utc": None,
        "updated_by": default_meta["updated_by"],
        "source": default_meta["source"],
        "metadata": default_meta,
    }


def save_active_template(
    settings: Settings,
    template_text: str,
    *,
    name: str | None = None,
    author: str = "unknown",
    source: str = "editor",
    notes: str | None = None,
    operation: str = "save",
    rolled_back_from: str | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> dict[str, Any]:
    config = _ensure_template_profiles(settings)
    normalized_profile_id = _normalize_profile_id(profile_id) or DEFAULT_PROFILE_ID
    valid_ids = {str(item.get("profile_id")) for item in config.get("profiles", [])}
    if normalized_profile_id not in valid_ids:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    path = _template_path_for_profile(settings, normalized_profile_id)
    normalized = _normalize_template_text(template_text)
    if not normalized:
        raise ValueError("template_text must not be empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized + "\n", encoding="utf-8")

    current = get_active_template(settings, profile_id=normalized_profile_id)
    record = _build_template_version_record(
        template_text=normalized,
        name=name or str(current.get("name") or "Chronicle Template"),
        author=author,
        source=source,
        notes=notes,
        operation=operation,
        rolled_back_from=rolled_back_from,
    )
    _store_template_version(settings, record, profile_id=normalized_profile_id)

    metadata = _template_metadata_defaults()
    metadata.update(
        {
            "name": record["name"],
            "current_version": record["version_id"],
            "updated_at_utc": record["created_at_utc"],
            "updated_by": record["author"],
            "source": record["source"],
        }
    )
    _save_template_metadata(settings, metadata, profile_id=normalized_profile_id)

    active = get_active_template(settings, profile_id=normalized_profile_id)
    active["saved_version"] = record["version_id"]
    return active


def _lint_template_text(template_text: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    if len(template_text) > MAX_TEMPLATE_CHARS:
        errors.append(
            f"Template is too large ({len(template_text)} chars). Max allowed: {MAX_TEMPLATE_CHARS}."
        )

    for pattern, message in FORBIDDEN_TEMPLATE_PATTERNS:
        if pattern.search(template_text):
            errors.append(message)

    if "raw." in template_text:
        warnings.append("Template uses raw payload fields; prefer curated fields for stability.")

    long_line_count = 0
    for line in template_text.splitlines():
        if len(line) > 240:
            long_line_count += 1
    if long_line_count:
        warnings.append(f"Template has {long_line_count} long line(s) over 240 chars.")

    return warnings, errors


def validate_template_text(template_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    env = _template_environment()
    template_text = _normalize_template_text(template_text)
    if context is not None:
        context = normalize_template_context(context)

    errors: list[str] = []
    warnings: list[str] = []
    undeclared: list[str] = []
    lint_warnings, lint_errors = _lint_template_text(template_text)
    warnings.extend(lint_warnings)
    errors.extend(lint_errors)

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "undeclared_variables": undeclared,
        }

    try:
        ast = env.parse(template_text)
        undeclared = sorted(meta.find_undeclared_variables(ast))
    except TemplateError as exc:
        return {
            "valid": False,
            "errors": [str(exc)],
            "warnings": warnings,
            "undeclared_variables": undeclared,
        }

    if context is not None:
        unknown_top_level = sorted(
            var for var in undeclared if var not in set(context.keys())
        )
        if unknown_top_level:
            warnings.append(
                "Template references top-level variables not present in context: "
                + ", ".join(unknown_top_level)
            )

        try:
            rendered = env.from_string(template_text).render(context)
            _normalize_rendered_text(rendered)
        except TemplateError as exc:
            errors.append(str(exc))
    else:
        warnings.append("No render context was provided for runtime validation.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "undeclared_variables": undeclared,
    }


def render_template_text(template_text: str, context: dict[str, Any]) -> dict[str, Any]:
    env = _template_environment()
    template_text = _normalize_template_text(template_text)
    context = normalize_template_context(context)
    try:
        template = env.from_string(template_text)
        rendered = template.render(context)
    except TemplateError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "description": None,
        }

    return {
        "ok": True,
        "error": None,
        "description": _normalize_rendered_text(rendered),
    }


def render_with_active_template(
    settings: Settings,
    context: dict[str, Any],
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    allow_seed_fallback: bool = True,
) -> dict[str, Any]:
    active = get_active_template(settings, profile_id=profile_id)
    active_profile_id = str(active.get("profile_id") or DEFAULT_PROFILE_ID)
    render_result = render_template_text(active["template"], context)
    render_result["is_custom_template"] = active["is_custom"]
    render_result["template_path"] = active["path"]
    render_result["profile_id"] = active_profile_id
    render_result["profile_label"] = active.get("profile_label")
    render_result["template_hash"] = active.get("template_hash")
    render_result["template_version"] = active.get("current_version")
    render_result["template_name"] = active.get("name")
    render_result["template_updated_at_utc"] = active.get("updated_at_utc")

    if render_result["ok"]:
        render_result["fallback_used"] = False
        return render_result

    if active["is_custom"] and allow_seed_fallback:
        fallback_result = render_template_text(_profile_template_seed(active_profile_id), context)
        fallback_result["is_custom_template"] = active["is_custom"]
        fallback_result["template_path"] = active["path"]
        fallback_result["profile_id"] = active_profile_id
        fallback_result["profile_label"] = active.get("profile_label")
        fallback_result["template_hash"] = active.get("template_hash")
        fallback_result["template_version"] = active.get("current_version")
        fallback_result["template_name"] = active.get("name")
        fallback_result["template_updated_at_utc"] = active.get("updated_at_utc")
        fallback_result["fallback_used"] = fallback_result["ok"]
        fallback_result["fallback_reason"] = render_result["error"]
        return fallback_result

    render_result["fallback_used"] = False
    return render_result


def _sample_value(value: Any) -> Any:
    if isinstance(value, dict):
        return "{...}"
    if isinstance(value, list):
        if not value:
            return []
        return value[:3]
    return value


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return type(value).__name__


_GROUP_SOURCE_MAP: dict[str, tuple[str, str]] = {
    "achievements": ("Intervals.icu", "Achievement badges from Intervals activity payload."),
    "activity": ("Strava", "Latest activity metrics. Elevation can be overridden by Smashrun."),
    "activity_badges": ("Garmin", "Garmin badges filtered to the current activity when linkage metadata is available."),
    "badges": ("Mixed", "Badge-style highlights from Strava, Garmin, and Smashrun."),
    "crono": ("crono-api", "Local nutrition/energy balance API values."),
    "garmin": ("Garmin", "Garmin-focused readiness, status, and run-dynamics metrics."),
    "garmin_badges": ("Garmin", "Earned Garmin badges when available."),
    "garmin_segment_notables": ("Garmin", "Garmin segment medal highlights (PR/2nd/3rd) when available."),
    "intervals": ("Intervals.icu", "Intervals.icu rollup metrics."),
    "notables": ("Smashrun", "Smashrun notable badges for latest run."),
    "periods": ("Strava+Smashrun+Garmin", "Aggregated rolling summaries by period."),
    "raw": ("Mixed", "Raw and derived payloads from all enabled services."),
    "segment_notables": ("Strava+Garmin", "Segment medals and PR highlights for latest activity."),
    "smashrun": ("Smashrun", "Smashrun latest activity and historical stats."),
    "smashrun_activity_badges": ("Smashrun", "Smashrun badges linked to the current activity when linkage metadata is available."),
    "smashrun_badges": ("Smashrun", "Earned Smashrun badges."),
    "streak_days": ("Smashrun", "Current run streak length from Smashrun."),
    "strava_badges": ("Strava", "Strava achievement badges from latest activity detail."),
    "strava_segment_notables": ("Strava", "Strava segment medals (PR/2nd/3rd) for latest activity."),
    "training": ("Garmin+Strava", "Garmin metrics with Strava fallback for missing HR/cadence."),
    "weather": ("Weather.com", "Weather + AQI conditions for activity time."),
}


_SOURCE_COST_TIER_MAP: dict[str, str] = {
    "Derived": "free",
    "Unknown": "medium",
    "Mixed": "medium",
    "Strava": "low",
    "Garmin": "medium",
    "Smashrun": "low",
    "Intervals.icu": "low",
    "Weather.com": "low",
    "crono-api": "low",
    "Strava+Garmin": "medium",
    "Strava+Garmin+Smashrun": "medium",
    "Garmin+Strava": "medium",
    "Strava+Smashrun+Garmin": "medium",
}


_GROUP_FRESHNESS_MAP: dict[str, str] = {
    "activity": "activity",
    "activity_badges": "activity",
    "achievements": "activity",
    "badges": "activity",
    "intervals": "activity",
    "weather": "activity",
    "notables": "activity",
    "segment_notables": "activity",
    "strava_segment_notables": "activity",
    "garmin_segment_notables": "activity",
    "strava_badges": "activity",
    "garmin_badges": "daily",
    "smashrun_activity_badges": "activity",
    "smashrun_badges": "rolling",
    "streak_days": "daily",
    "training": "daily",
    "garmin": "daily",
    "crono": "daily",
    "smashrun": "rolling",
    "periods": "rolling",
    "raw": "activity",
}


_FIELD_CATALOG_EXACT_MAP: dict[str, dict[str, Any]] = {
    "badges": {
        "source": "Strava+Garmin+Smashrun",
        "source_note": "Combined badge highlights from all enabled providers.",
        "label": "All Badges",
        "description": "Merged badge list from Strava, Garmin, and Smashrun.",
        "tags": ["badges", "highlights", "activity"],
        "metric_key": "all_badges",
    },
    "segment_notables": {
        "source": "Strava+Garmin",
        "source_note": "Segment medal highlights (PR/2nd/3rd) from latest activity context.",
        "label": "All Segment Notables",
        "description": "Merged segment medals from Strava and Garmin.",
        "tags": ["segments", "medals", "activity"],
        "metric_key": "all_segment_notables",
    },
    "strava_badges": {
        "source": "Strava",
        "source_note": "Achievement badges extracted from Strava activity detail payload.",
        "label": "Strava Badges",
        "description": "Strava badge highlights from latest activity.",
        "tags": ["strava", "badges", "activity"],
        "metric_key": "strava_badges",
    },
    "garmin_badges": {
        "source": "Garmin",
        "source_note": "Earned badges from Garmin badge endpoints when available.",
        "label": "Garmin Badges",
        "description": "Garmin badge highlights.",
        "tags": ["garmin", "badges", "activity"],
        "metric_key": "garmin_badges",
    },
    "activity_badges": {
        "source": "Garmin",
        "source_note": "Garmin badges filtered to current activity by badgeAssocType/activityId linkage.",
        "label": "Activity Garmin Badges",
        "description": "Garmin badge names earned by this activity only.",
        "tags": ["garmin", "badges", "activity"],
        "metric_key": "garmin_activity_badges",
    },
    "smashrun_badges": {
        "source": "Smashrun",
        "source_note": "Earned badges from Smashrun badge endpoints.",
        "label": "Smashrun Badges",
        "description": "Smashrun badge highlights.",
        "tags": ["smashrun", "badges", "activity"],
        "metric_key": "smashrun_badges",
    },
    "smashrun_activity_badges": {
        "source": "Smashrun",
        "source_note": "Smashrun badges filtered to current activity by activity-id linkage keys.",
        "label": "Activity Smashrun Badges",
        "description": "Smashrun badge names earned by this activity only.",
        "tags": ["smashrun", "badges", "activity"],
        "metric_key": "smashrun_activity_badges",
    },
    "strava_segment_notables": {
        "source": "Strava",
        "source_note": "Segment medal finishes using Strava personal rank (pr_rank).",
        "label": "Strava Segment Medals",
        "description": "Strava segment PR/2nd/3rd highlights.",
        "tags": ["strava", "segments", "medals"],
        "metric_key": "strava_segment_notables",
    },
    "garmin_segment_notables": {
        "source": "Garmin",
        "source_note": "Segment medal finishes from Garmin segment payloads when present.",
        "label": "Garmin Segment Medals",
        "description": "Garmin segment PR/2nd/3rd highlights.",
        "tags": ["garmin", "segments", "medals"],
        "metric_key": "garmin_segment_notables",
    },
    "activity.elevation_feet": {
        "source": "Smashrun",
        "source_note": "Per-activity elevation from Smashrun; Strava fallback.",
        "label": "Elevation Gain",
        "description": "Latest activity elevation in feet.",
        "tags": ["elevation", "activity", "core"],
        "metric_key": "activity_elevation_feet",
        "alternatives": ["raw.activity.total_elevation_gain"],
    },
    "activity.gap_pace": {
        "source": "Strava+Garmin",
        "source_note": "Strava GAP pace when available; Garmin/average-speed fallback.",
        "label": "GAP Pace",
        "description": "Grade-adjusted pace for latest activity.",
        "tags": ["pace", "activity", "core"],
        "metric_key": "activity_gap_pace",
        "alternatives": ["raw.activity.average_grade_adjusted_speed", "raw.activity.average_speed"],
    },
    "activity.distance_miles": {
        "label": "Distance (mi)",
        "description": "Latest activity distance in miles.",
        "tags": ["distance", "activity", "core"],
        "metric_key": "activity_distance_miles",
    },
    "activity.time": {
        "label": "Moving Time",
        "description": "Latest activity moving time string.",
        "tags": ["time", "activity", "core"],
        "metric_key": "activity_time",
    },
    "activity.beers": {
        "source": "Strava",
        "source_note": "Calories from Strava converted to beers.",
        "label": "Beers Earned",
        "description": "Calories converted into beer-equivalent units.",
        "tags": ["calories", "activity", "derived"],
        "metric_key": "activity_beers",
    },
    "activity.average_pace": {
        "source": "Strava",
        "source_note": "Pace derived from Strava average speed.",
        "label": "Average Pace",
        "description": "Latest activity average pace in min/mi.",
        "tags": ["pace", "activity", "core"],
        "metric_key": "activity_average_pace",
    },
    "activity.average_speed_mph": {
        "source": "Strava",
        "source_note": "Average speed converted to mph.",
        "label": "Average Speed (mph)",
        "description": "Latest activity average speed in mph.",
        "tags": ["speed", "activity"],
        "metric_key": "activity_average_speed_mph",
    },
    "activity.max_speed_mph": {
        "source": "Strava",
        "source_note": "Max speed converted to mph.",
        "label": "Max Speed (mph)",
        "description": "Latest activity max speed in mph.",
        "tags": ["speed", "activity"],
        "metric_key": "activity_max_speed_mph",
    },
    "activity.elapsed_time": {
        "source": "Strava",
        "source_note": "Elapsed time normalized to H:MM:SS.",
        "label": "Elapsed Time",
        "description": "Latest activity elapsed duration.",
        "tags": ["time", "activity"],
        "metric_key": "activity_elapsed_time",
    },
    "activity.moving_time": {
        "source": "Strava",
        "source_note": "Moving time normalized to H:MM:SS.",
        "label": "Moving Time",
        "description": "Latest activity moving duration.",
        "tags": ["time", "activity", "core"],
        "metric_key": "activity_moving_time",
    },
    "activity.calories": {
        "source": "Strava",
        "source_note": "Calories from Strava latest activity.",
        "label": "Calories",
        "description": "Latest activity calories.",
        "tags": ["calories", "activity"],
        "metric_key": "activity_calories",
    },
    "activity.elev_high_feet": {
        "source": "Strava",
        "source_note": "High elevation converted to feet.",
        "label": "Elevation High",
        "description": "Highest activity elevation point in feet.",
        "tags": ["elevation", "activity"],
        "metric_key": "activity_elev_high_feet",
    },
    "activity.elev_low_feet": {
        "source": "Strava",
        "source_note": "Low elevation converted to feet.",
        "label": "Elevation Low",
        "description": "Lowest activity elevation point in feet.",
        "tags": ["elevation", "activity"],
        "metric_key": "activity_elev_low_feet",
    },
    "activity.average_temp_f": {
        "source": "Strava",
        "source_note": "Average recorded activity temperature.",
        "label": "Activity Temp",
        "description": "Average activity temperature in Fahrenheit.",
        "tags": ["temperature", "activity", "weather"],
        "metric_key": "activity_average_temp_f",
    },
    "activity.max_hr": {
        "source": "Strava+Garmin",
        "source_note": "Maximum heart rate from activity detail.",
        "label": "Max Heart Rate",
        "description": "Maximum heart rate for latest activity.",
        "tags": ["heart_rate", "activity"],
        "metric_key": "activity_max_hr",
    },
    "activity.start_local": {
        "source": "Strava",
        "source_note": "Localized start timestamp.",
        "label": "Start (Local)",
        "description": "Local start time for latest activity.",
        "tags": ["time", "activity", "metadata"],
        "metric_key": "activity_start_local",
    },
    "activity.start_utc": {
        "source": "Strava",
        "source_note": "UTC start timestamp.",
        "label": "Start (UTC)",
        "description": "UTC start time for latest activity.",
        "tags": ["time", "activity", "metadata"],
        "metric_key": "activity_start_utc",
    },
    "activity.social.kudos": {
        "source": "Strava",
        "source_note": "Strava social counters from activity detail.",
        "label": "Kudos Count",
        "description": "Number of kudos on this activity.",
        "tags": ["social", "activity", "metadata"],
        "metric_key": "activity_social_kudos",
    },
    "activity.social.comments": {
        "source": "Strava",
        "source_note": "Strava social counters from activity detail.",
        "label": "Comment Count",
        "description": "Number of comments on this activity.",
        "tags": ["social", "activity", "metadata"],
        "metric_key": "activity_social_comments",
    },
    "activity.social.achievements": {
        "source": "Strava",
        "source_note": "Strava social counters from activity detail.",
        "label": "Achievement Count",
        "description": "Number of segment achievements on this activity.",
        "tags": ["social", "activity", "metadata"],
        "metric_key": "activity_social_achievements",
    },
    "activity.segment_notables": {
        "source": "Strava",
        "source_note": "Segment medal finishes filtered to PR/2nd/3rd on latest activity.",
        "label": "Activity Segment Medals",
        "description": "Medal-worthy segment efforts for this activity.",
        "tags": ["activity", "segments", "medals"],
        "metric_key": "activity_segment_notables",
    },
    "weather.misery_index": {
        "label": "Misery Index",
        "description": "Running-normalized additive misery index (0 is ideal, higher is worse).",
        "tags": ["weather", "mi", "risk"],
        "metric_key": "weather_misery_index",
    },
    "misery.index": {
        "label": "Misery Index Object",
        "description": "Display-friendly misery index object. String form is numeric value.",
        "tags": ["weather", "mi", "object"],
        "metric_key": "misery_index_object",
    },
    "misery.index.value": {
        "label": "Misery Index Value",
        "description": "Running-normalized additive misery index where 0 is ideal.",
        "tags": ["weather", "mi", "severity"],
        "metric_key": "misery_index_value",
    },
    "misery.index.emoji": {
        "label": "Misery Emoji",
        "description": "Emoji selected from polarity and severity.",
        "tags": ["weather", "mi", "emoji"],
        "metric_key": "misery_index_emoji",
    },
    "misery.index.polarity": {
        "label": "Misery Polarity",
        "description": "Dominant thermal direction: hot, cold, or neutral.",
        "tags": ["weather", "mi", "polarity"],
        "metric_key": "misery_index_polarity",
    },
    "misery.index.severity": {
        "label": "Misery Severity",
        "description": "Severity bucket derived from misery index value.",
        "tags": ["weather", "mi", "severity"],
        "metric_key": "misery_index_severity",
    },
    "misery.index.description": {
        "label": "Misery Description",
        "description": "Human-readable misery summary.",
        "tags": ["weather", "mi", "summary"],
        "metric_key": "misery_index_description",
    },
    "weather.aqi": {
        "label": "AQI",
        "description": "Air Quality Index at activity time.",
        "tags": ["weather", "aqi", "air"],
        "metric_key": "weather_aqi",
    },
    "weather.temp_f": {
        "source": "Weather.com",
        "source_note": "Hourly weather at activity start.",
        "label": "Temperature",
        "description": "Temperature at activity time (F).",
        "tags": ["weather", "temperature", "core"],
        "metric_key": "weather_temp_f",
    },
    "weather.dewpoint_f": {
        "source": "Weather.com",
        "source_note": "Hourly weather at activity start.",
        "label": "Dew Point",
        "description": "Dew point at activity time (F).",
        "tags": ["weather", "temperature", "humidity"],
        "metric_key": "weather_dewpoint_f",
    },
    "weather.humidity_pct": {
        "source": "Weather.com",
        "source_note": "Hourly weather at activity start.",
        "label": "Humidity",
        "description": "Relative humidity percentage.",
        "tags": ["weather", "humidity", "core"],
        "metric_key": "weather_humidity_pct",
    },
    "weather.wind_mph": {
        "source": "Weather.com",
        "source_note": "Hourly weather at activity start.",
        "label": "Wind Speed",
        "description": "Wind speed in mph.",
        "tags": ["weather", "wind", "core"],
        "metric_key": "weather_wind_mph",
    },
    "weather.condition": {
        "source": "Weather.com",
        "source_note": "Hourly weather condition text.",
        "label": "Condition",
        "description": "Condition summary at activity time.",
        "tags": ["weather", "condition", "core"],
        "metric_key": "weather_condition",
    },
    "weather.apparent_temp_f": {
        "source": "Weather.com",
        "source_note": "Apparent temperature from MI model components.",
        "label": "Apparent Temp",
        "description": "Apparent temperature perceived by runner (F).",
        "tags": ["weather", "temperature", "mi"],
        "metric_key": "weather_apparent_temp_f",
    },
    "crono.line": {
        "source": "crono-api",
        "source_note": "Legacy preformatted line for backward compatibility.",
        "label": "Legacy Crono Line",
        "description": "Preformatted Crono line retained for old templates.",
        "tags": ["nutrition", "legacy"],
        "metric_key": "crono_line",
    },
    "crono.average_net_kcal_per_day": {
        "source": "crono-api",
        "source_note": "Trailing completed-day average net calories.",
        "label": "7d Avg Net kcal/day",
        "description": "Average daily energy balance over trailing complete days.",
        "tags": ["nutrition", "energy", "trend"],
        "metric_key": "crono_energy_balance",
    },
    "crono.average_status": {
        "source": "crono-api",
        "source_note": "Energy trend label (deficit/surplus).",
        "label": "Energy Balance Status",
        "description": "Deficit or surplus status from Crono.",
        "tags": ["nutrition", "energy", "trend"],
        "metric_key": "crono_energy_status",
    },
    "crono.protein_g": {
        "source": "crono-api",
        "source_note": "Protein grams for activity day.",
        "label": "Protein (g)",
        "description": "Daily protein grams for the activity date.",
        "tags": ["nutrition", "protein", "macros"],
        "metric_key": "crono_protein_g",
    },
    "crono.carbs_g": {
        "source": "crono-api",
        "source_note": "Carb grams for activity day.",
        "label": "Carbs (g)",
        "description": "Daily carbohydrate grams for the activity date.",
        "tags": ["nutrition", "carbs", "macros"],
        "metric_key": "crono_carbs_g",
    },
    "periods.week.elevation_feet": {
        "source": "Smashrun",
        "source_note": "7-day elevation total from Smashrun.",
        "label": "7d Elevation",
        "description": "Trailing 7-day elevation gain in feet.",
        "tags": ["summary", "week", "elevation"],
        "metric_key": "week_elevation_feet",
        "alternatives": ["raw.week.elevation"],
    },
    "periods.month.elevation_feet": {
        "source": "Smashrun",
        "source_note": "30-day elevation total from Smashrun.",
        "label": "30d Elevation",
        "description": "Trailing 30-day elevation gain in feet.",
        "tags": ["summary", "month", "elevation"],
        "metric_key": "month_elevation_feet",
        "alternatives": ["raw.month.elevation"],
    },
    "periods.year.elevation_feet": {
        "source": "Smashrun",
        "source_note": "YTD elevation total from Smashrun.",
        "label": "YTD Elevation",
        "description": "Year-to-date elevation gain in feet.",
        "tags": ["summary", "year", "elevation"],
        "metric_key": "year_elevation_feet",
        "alternatives": ["raw.year.elevation"],
    },
    "periods.week.gap": {
        "source": "Strava+Garmin",
        "source_note": "Average GAP from Strava runs; Garmin fallback.",
        "label": "7d GAP",
        "description": "Trailing 7-day average GAP pace.",
        "tags": ["summary", "week", "pace"],
        "metric_key": "week_gap",
    },
    "periods.month.gap": {
        "source": "Strava+Garmin",
        "source_note": "Average GAP from Strava runs; Garmin fallback.",
        "label": "30d GAP",
        "description": "Trailing 30-day average GAP pace.",
        "tags": ["summary", "month", "pace"],
        "metric_key": "month_gap",
    },
    "periods.year.gap": {
        "source": "Strava+Garmin",
        "source_note": "Average GAP from Strava runs; Garmin fallback.",
        "label": "YTD GAP",
        "description": "Year-to-date average GAP pace.",
        "tags": ["summary", "year", "pace"],
        "metric_key": "year_gap",
    },
    "periods.week.beers": {
        "source": "Strava+Garmin",
        "source_note": "Calories-derived beers from Strava; Garmin fallback.",
        "label": "7d Beers",
        "description": "Trailing 7-day calorie-equivalent beers.",
        "tags": ["summary", "week", "calories"],
        "metric_key": "week_beers",
    },
    "periods.month.beers": {
        "source": "Strava+Garmin",
        "source_note": "Calories-derived beers from Strava; Garmin fallback.",
        "label": "30d Beers",
        "description": "Trailing 30-day calorie-equivalent beers.",
        "tags": ["summary", "month", "calories"],
        "metric_key": "month_beers",
    },
    "periods.year.beers": {
        "source": "Strava+Garmin",
        "source_note": "Calories-derived beers from Strava; Garmin fallback.",
        "label": "YTD Beers",
        "description": "Year-to-date calorie-equivalent beers.",
        "tags": ["summary", "year", "calories"],
        "metric_key": "year_beers",
    },
    "intervals.training_load": {
        "source": "Intervals.icu",
        "source_note": "Load and strain values from Intervals detail payload.",
        "label": "Training Load",
        "description": "Intervals training load score.",
        "tags": ["intervals", "load", "training"],
        "metric_key": "intervals_training_load",
    },
    "intervals.fitness": {
        "source": "Intervals.icu",
        "source_note": "Fitness (CTL) from Intervals activity detail payload.",
        "label": "Intervals Fitness",
        "description": "Intervals CTL fitness value.",
        "tags": ["intervals", "fitness", "load"],
        "metric_key": "intervals_fitness",
    },
    "intervals.fatigue": {
        "source": "Intervals.icu",
        "source_note": "Fatigue (ATL) from Intervals activity detail payload.",
        "label": "Intervals Fatigue",
        "description": "Intervals ATL fatigue value.",
        "tags": ["intervals", "fatigue", "load"],
        "metric_key": "intervals_fatigue",
    },
    "intervals.load": {
        "source": "Intervals.icu",
        "source_note": "Primary load score from Intervals activity detail payload.",
        "label": "Intervals Load",
        "description": "Intervals load score (alias of training load).",
        "tags": ["intervals", "load", "training"],
        "metric_key": "intervals_load",
    },
    "intervals.ramp": {
        "source": "Intervals.icu",
        "source_note": "Ramp rate value from Intervals activity detail payload when available.",
        "label": "Intervals Ramp",
        "description": "Intervals ramp-rate metric for load trend.",
        "tags": ["intervals", "load", "trend"],
        "metric_key": "intervals_ramp",
    },
    "intervals.form_percent": {
        "source": "Derived",
        "source_note": "Computed as ((fitness - fatigue) / fitness) * 100.",
        "label": "Intervals Form %",
        "description": "Calculated Intervals form percentage.",
        "tags": ["intervals", "form", "derived"],
        "metric_key": "intervals_form_percent",
    },
    "intervals.form_class": {
        "source": "Derived",
        "source_note": "Classified from Intervals form thresholds.",
        "label": "Intervals Form Class",
        "description": "Form class bucket from Intervals form percentage.",
        "tags": ["intervals", "form", "derived"],
        "metric_key": "intervals_form_class",
    },
    "intervals.strain_score": {
        "source": "Intervals.icu",
        "source_note": "Load and strain values from Intervals detail payload.",
        "label": "Strain Score",
        "description": "Intervals strain score.",
        "tags": ["intervals", "load", "training"],
        "metric_key": "intervals_strain_score",
    },
    "intervals.avg_pace": {
        "source": "Intervals.icu",
        "source_note": "Average pace derived from Intervals activity speed.",
        "label": "Intervals Avg Pace",
        "description": "Average pace from Intervals activity detail.",
        "tags": ["intervals", "pace", "activity"],
        "metric_key": "intervals_avg_pace",
    },
    "intervals.avg_speed_mph": {
        "source": "Intervals.icu",
        "source_note": "Average speed converted to mph.",
        "label": "Intervals Avg Speed",
        "description": "Average speed from Intervals activity detail.",
        "tags": ["intervals", "speed", "activity"],
        "metric_key": "intervals_avg_speed_mph",
    },
    "intervals.distance_miles": {
        "source": "Intervals.icu",
        "source_note": "Distance converted to miles.",
        "label": "Intervals Distance",
        "description": "Distance from Intervals activity detail.",
        "tags": ["intervals", "distance", "activity"],
        "metric_key": "intervals_distance_miles",
    },
    "intervals.moving_time": {
        "source": "Intervals.icu",
        "source_note": "Moving duration normalized to H:MM:SS.",
        "label": "Intervals Moving Time",
        "description": "Moving duration from Intervals activity detail.",
        "tags": ["intervals", "time", "activity"],
        "metric_key": "intervals_moving_time",
    },
    "intervals.zone_summary": {
        "source": "Intervals.icu",
        "source_note": "Time-in-zone summary from Intervals zone arrays.",
        "label": "Intervals Zone Summary",
        "description": "Condensed time spent per power zone.",
        "tags": ["intervals", "zones", "training"],
        "metric_key": "intervals_zone_summary",
    },
    "training.fitness_age": {
        "source": "Garmin",
        "source_note": "Fitness age from Garmin fitness-age endpoint.",
        "label": "Fitness Age",
        "description": "Garmin fitness age estimate.",
        "tags": ["training", "wellness", "garmin"],
        "metric_key": "training_fitness_age",
    },
    "periods.week.run_count": {
        "source": "Strava",
        "source_note": "Run count included in trailing 7-day summary window.",
        "label": "7d Run Count",
        "description": "Number of runs in the trailing 7-day summary.",
        "tags": ["summary", "week", "volume"],
        "metric_key": "week_run_count",
    },
    "periods.month.run_count": {
        "source": "Strava",
        "source_note": "Run count included in trailing 30-day summary window.",
        "label": "30d Run Count",
        "description": "Number of runs in the trailing 30-day summary.",
        "tags": ["summary", "month", "volume"],
        "metric_key": "month_run_count",
    },
    "periods.year.run_count": {
        "source": "Strava",
        "source_note": "Run count included in year-to-date summary window.",
        "label": "YTD Run Count",
        "description": "Number of runs in the year-to-date summary.",
        "tags": ["summary", "year", "volume"],
        "metric_key": "year_run_count",
    },
    "periods.week.calories": {
        "source": "Strava+Garmin",
        "source_note": "Calories from Strava runs; Garmin fallback may influence beers.",
        "label": "7d Calories",
        "description": "Trailing 7-day run calories.",
        "tags": ["summary", "week", "calories"],
        "metric_key": "week_calories",
    },
    "periods.month.calories": {
        "source": "Strava+Garmin",
        "source_note": "Calories from Strava runs; Garmin fallback may influence beers.",
        "label": "30d Calories",
        "description": "Trailing 30-day run calories.",
        "tags": ["summary", "month", "calories"],
        "metric_key": "month_calories",
    },
    "periods.year.calories": {
        "source": "Strava+Garmin",
        "source_note": "Calories from Strava runs; Garmin fallback may influence beers.",
        "label": "YTD Calories",
        "description": "Year-to-date run calories.",
        "tags": ["summary", "year", "calories"],
        "metric_key": "year_calories",
    },
    "smashrun.latest_activity.distance_miles": {
        "source": "Smashrun",
        "source_note": "Matched activity distance normalized from Smashrun record.",
        "label": "Smashrun Distance",
        "description": "Latest matched Smashrun activity distance in miles.",
        "tags": ["smashrun", "activity", "distance"],
        "metric_key": "smashrun_latest_distance",
    },
    "smashrun.latest_activity.pace": {
        "source": "Smashrun",
        "source_note": "Pace derived from Smashrun duration and distance.",
        "label": "Smashrun Pace",
        "description": "Latest matched Smashrun activity pace.",
        "tags": ["smashrun", "activity", "pace"],
        "metric_key": "smashrun_latest_pace",
    },
    "smashrun.latest_activity.elevation_gain_feet": {
        "source": "Smashrun",
        "source_note": "Elevation gain from Smashrun latest matched activity.",
        "label": "Smashrun Elevation Gain",
        "description": "Latest matched Smashrun activity elevation gain in feet.",
        "tags": ["smashrun", "activity", "elevation"],
        "metric_key": "smashrun_latest_elevation",
    },
    "smashrun.latest_activity.average_hr": {
        "source": "Smashrun",
        "source_note": "Heart rate metrics from Smashrun latest matched activity.",
        "label": "Smashrun Avg HR",
        "description": "Average heart rate from latest matched Smashrun activity.",
        "tags": ["smashrun", "activity", "heart_rate"],
        "metric_key": "smashrun_latest_avg_hr",
    },
    "smashrun.stats.run_count": {
        "source": "Smashrun",
        "source_note": "Historical run count from Smashrun stats endpoint.",
        "label": "Smashrun Run Count",
        "description": "All-time run count from Smashrun stats.",
        "tags": ["smashrun", "stats", "volume"],
        "metric_key": "smashrun_run_count",
    },
    "smashrun.stats.total_distance": {
        "source": "Smashrun",
        "source_note": "Historical total distance from Smashrun stats endpoint.",
        "label": "Smashrun Total Distance",
        "description": "Total distance from Smashrun stats endpoint.",
        "tags": ["smashrun", "stats", "distance"],
        "metric_key": "smashrun_total_distance",
    },
    "smashrun.stats.average_pace": {
        "source": "Smashrun",
        "source_note": "Average pace from Smashrun stats endpoint.",
        "label": "Smashrun Avg Pace",
        "description": "Average pace from Smashrun stats.",
        "tags": ["smashrun", "stats", "pace"],
        "metric_key": "smashrun_average_pace",
    },
    "smashrun.stats.longest_streak": {
        "source": "Smashrun",
        "source_note": "Longest streak from Smashrun stats endpoint.",
        "label": "Smashrun Longest Streak",
        "description": "Longest streak days from Smashrun stats.",
        "tags": ["smashrun", "stats", "streak"],
        "metric_key": "smashrun_longest_streak",
    },
    "smashrun.badges": {
        "source": "Smashrun",
        "source_note": "Badge highlights from Smashrun badge endpoints.",
        "label": "Smashrun Badge List",
        "description": "Smashrun earned badge lines.",
        "tags": ["smashrun", "badges", "activity"],
        "metric_key": "smashrun_badges_list",
    },
    "smashrun.activity_badges": {
        "source": "Smashrun",
        "source_note": "Smashrun badge names linked to the current activity id.",
        "label": "Smashrun Activity Badge List",
        "description": "Smashrun badges earned by the latest processed activity.",
        "tags": ["smashrun", "badges", "activity"],
        "metric_key": "smashrun_activity_badges_list",
    },
    "garmin.last_activity.gap_pace": {
        "source": "Garmin",
        "source_note": "Garmin last-activity grade-adjusted pace.",
        "label": "Garmin GAP Pace",
        "description": "Garmin-reported last activity GAP pace.",
        "tags": ["garmin", "activity", "pace"],
        "metric_key": "garmin_last_gap_pace",
    },
    "garmin.badges": {
        "source": "Garmin",
        "source_note": "Badge highlights from Garmin earned-badge endpoints.",
        "label": "Garmin Badge List",
        "description": "Garmin earned badge lines.",
        "tags": ["garmin", "badges", "activity"],
        "metric_key": "garmin_badges_list",
    },
    "garmin.activity_badges": {
        "source": "Garmin",
        "source_note": "Garmin badge names linked to the current activity id.",
        "label": "Garmin Activity Badge List",
        "description": "Garmin badges earned by the latest processed activity.",
        "tags": ["garmin", "badges", "activity"],
        "metric_key": "garmin_activity_badges_list",
    },
    "garmin.segment_notables": {
        "source": "Garmin",
        "source_note": "Segment medal finishes from Garmin payloads when present.",
        "label": "Garmin Segment Medals",
        "description": "Garmin PR/2nd/3rd segment lines.",
        "tags": ["garmin", "segments", "medals"],
        "metric_key": "garmin_segment_notables_list",
    },
    "garmin.last_activity.hr_zone_summary": {
        "source": "Garmin",
        "source_note": "Garmin last-activity heart-rate time-in-zone summary.",
        "label": "Garmin HR Zones",
        "description": "Garmin heart-rate zone time summary.",
        "tags": ["garmin", "activity", "heart_rate", "zones"],
        "metric_key": "garmin_last_hr_zones",
    },
    "garmin.last_activity.power_zone_summary": {
        "source": "Garmin",
        "source_note": "Garmin last-activity power time-in-zone summary.",
        "label": "Garmin Power Zones",
        "description": "Garmin power zone time summary.",
        "tags": ["garmin", "activity", "power", "zones"],
        "metric_key": "garmin_last_power_zones",
    },
    "garmin.last_activity.avg_ground_contact_time_ms": {
        "source": "Garmin",
        "source_note": "Run dynamics from Garmin last-activity payload.",
        "label": "Garmin GCT",
        "description": "Average ground contact time (ms) from Garmin.",
        "tags": ["garmin", "activity", "run_dynamics"],
        "metric_key": "garmin_last_gct",
    },
    "garmin.last_activity.avg_vertical_ratio_pct": {
        "source": "Garmin",
        "source_note": "Run dynamics from Garmin last-activity payload.",
        "label": "Garmin Vertical Ratio",
        "description": "Average vertical ratio from Garmin.",
        "tags": ["garmin", "activity", "run_dynamics"],
        "metric_key": "garmin_last_vertical_ratio",
    },
    "garmin.readiness.recovery_time_hours": {
        "source": "Garmin",
        "source_note": "Recovery estimate from Garmin training readiness payload.",
        "label": "Garmin Recovery Hours",
        "description": "Recovery-time estimate in hours.",
        "tags": ["garmin", "readiness", "recovery"],
        "metric_key": "garmin_recovery_hours",
    },
    "garmin.readiness.factors.sleep_score_factor_pct": {
        "source": "Garmin",
        "source_note": "Readiness factor percentages from Garmin readiness payload.",
        "label": "Readiness Sleep Score %",
        "description": "Sleep-score contribution to readiness.",
        "tags": ["garmin", "readiness", "factors", "sleep"],
        "metric_key": "garmin_readiness_sleep_score_factor",
    },
    "garmin.readiness.factors.hrv_factor_pct": {
        "source": "Garmin",
        "source_note": "Readiness factor percentages from Garmin readiness payload.",
        "label": "Readiness HRV %",
        "description": "HRV contribution to readiness.",
        "tags": ["garmin", "readiness", "factors", "hrv"],
        "metric_key": "garmin_readiness_hrv_factor",
    },
    "garmin.status.weekly_training_load": {
        "source": "Garmin",
        "source_note": "Weekly load trend from Garmin training status payload.",
        "label": "Garmin Weekly Load",
        "description": "Weekly training load from Garmin.",
        "tags": ["garmin", "status", "load"],
        "metric_key": "garmin_weekly_load",
    },
    "garmin.status.daily_acwr_ratio": {
        "source": "Garmin",
        "source_note": "ACWR ratio from Garmin training status payload.",
        "label": "Garmin Daily ACWR",
        "description": "Daily acute/chronic workload ratio from Garmin.",
        "tags": ["garmin", "status", "acwr", "load"],
        "metric_key": "garmin_daily_acwr_ratio",
    },
    "garmin.fitness_age.fitness_age": {
        "source": "Garmin",
        "source_note": "Fitness-age summary details from Garmin fitness-age payload.",
        "label": "Garmin Fitness Age",
        "description": "Numeric Garmin fitness age value.",
        "tags": ["garmin", "fitness_age", "wellness"],
        "metric_key": "garmin_fitness_age",
    },
    "garmin.fitness_age.chronological_age": {
        "source": "Garmin",
        "source_note": "Fitness-age summary details from Garmin fitness-age payload.",
        "label": "Chronological Age",
        "description": "Chronological age from Garmin fitness-age payload.",
        "tags": ["garmin", "fitness_age", "wellness"],
        "metric_key": "garmin_chronological_age",
    },
}


_FIELD_CATALOG_PREFIX_MAP: list[tuple[str, dict[str, Any]]] = [
    ("raw.activity.", {"source": "Strava", "source_note": "Raw activity detail payload.", "tags": ["raw", "strava"]}),
    ("raw.training.", {"source": "Garmin", "source_note": "Raw Garmin-derived training payload.", "tags": ["raw", "garmin"]}),
    ("raw.intervals.", {"source": "Intervals.icu", "source_note": "Raw Intervals payload.", "tags": ["raw", "intervals"]}),
    ("raw.weather.", {"source": "Weather.com", "source_note": "Raw weather payload.", "tags": ["raw", "weather"]}),
    ("raw.smashrun.", {"source": "Smashrun", "source_note": "Raw Smashrun payloads.", "tags": ["raw", "smashrun"]}),
    ("raw.garmin_period_fallback.", {"source": "Garmin", "source_note": "Garmin period fallback summary payload.", "tags": ["raw", "garmin", "summary"]}),
    ("raw.week.", {"source": "Derived", "source_note": "Computed 7-day aggregate from source activities.", "tags": ["raw", "summary", "week"]}),
    ("raw.month.", {"source": "Derived", "source_note": "Computed 30-day aggregate from source activities.", "tags": ["raw", "summary", "month"]}),
    ("raw.year.", {"source": "Derived", "source_note": "Computed YTD aggregate from source activities.", "tags": ["raw", "summary", "year"]}),
    ("misery.", {"source": "Derived", "source_note": "Running-normalized misery index object and polarity metadata.", "tags": ["weather", "mi"]}),
    ("weather.details.", {"source": "Weather.com", "source_note": "Detailed weather conditions for activity time.", "tags": ["weather", "details"]}),
    ("weather.components.", {"source": "Weather.com", "source_note": "Misery index component breakdown.", "tags": ["weather", "mi", "components"]}),
    ("intervals.", {"source": "Intervals.icu", "source_note": "Intervals.icu activity detail and rollup metrics.", "tags": ["intervals"]}),
    ("garmin.", {"source": "Garmin", "source_note": "Garmin-derived structured context fields.", "tags": ["garmin"]}),
    ("smashrun.", {"source": "Smashrun", "source_note": "Smashrun structured context fields.", "tags": ["smashrun"]}),
]


_CATALOG_HELPER_TRANSFORMS: list[dict[str, str]] = [
    {"id": "raw", "label": "Raw", "template": "{{ {path} }}"},
    {"id": "default", "label": "Default N/A", "template": "{{ {path} | default('N/A') }}"},
    {"id": "round1", "label": "Round 1", "template": "{{ {path} | round(1) }}"},
    {"id": "int", "label": "Int", "template": "{{ {path} | int }}"},
    {"id": "if_present", "label": "If Present", "template": "{% if {path} %}{{ {path} }}{% endif %}"},
    {"id": "icu_calc_form", "label": "ICU Form %", "template": "{{ icu_calc_form(intervals.fitness, intervals.fatigue) }}"},
    {"id": "icu_form_class", "label": "ICU Form Class", "template": "{{ icu_form_class(intervals.form_percent) }}"},
]


def _default_label_for_path(path: str) -> str:
    leaf = path.split(".")[-1].split("]")[-1].replace("_", " ").strip()
    if not leaf:
        leaf = path.replace("_", " ")
    return leaf.title()


def _infer_units_for_path(path: str, value_type: str) -> str | None:
    path_l = path.lower()
    if path_l.endswith("_miles") or ".distance_miles" in path_l:
        return "mi"
    if path_l.endswith("_feet") or ".elevation_" in path_l:
        return "ft"
    if path_l.endswith("_mph"):
        return "mph"
    if path_l.endswith("_pace") or ".pace" in path_l:
        return "min/mi"
    if path_l.endswith("_pct") or "percent" in path_l:
        return "%"
    if path_l.endswith("_f") or "temp_f" in path_l or "dewpoint_f" in path_l:
        return "F"
    if path_l.endswith(".calories") or path_l.endswith("_calories"):
        return "kcal"
    if path_l.endswith("_g"):
        return "g"
    if path_l.endswith(".average_hr") or path_l.endswith(".max_hr") or path_l.endswith(".resting_hr") or path_l.endswith(".rhr"):
        return "bpm"
    if "cadence" in path_l:
        return "spm"
    if "power" in path_l and (path_l.endswith("_w") or ".norm_power" in path_l or ".avg_power" in path_l or ".max_power" in path_l):
        return "W"
    if "time" in path_l or "duration" in path_l:
        if value_type in {"str", "int", "float"}:
            return "h:mm:ss"
    if path_l.endswith("vo2") or "vo2" in path_l:
        return "ml/kg/min"
    return None


def _infer_freshness(path: str) -> str:
    top_key = path.split(".", 1)[0].split("[", 1)[0]
    if path.startswith("smashrun.latest_activity.") or path.startswith("garmin.last_activity."):
        return "activity"
    if path.startswith("smashrun.stats.") or path.startswith("periods.") or path.startswith("raw.week.") or path.startswith("raw.month.") or path.startswith("raw.year."):
        return "rolling"
    if path.startswith("garmin.readiness.") or path.startswith("garmin.status.") or path.startswith("garmin.fitness_age."):
        return "daily"
    return _GROUP_FRESHNESS_MAP.get(top_key, "activity")


def _field_metadata_for_path(path: str) -> dict[str, Any]:
    exact = _FIELD_CATALOG_EXACT_MAP.get(path)
    if exact is not None:
        meta = deepcopy(exact)
        meta["curated"] = True
    else:
        meta = {}
        for prefix, prefix_meta in _FIELD_CATALOG_PREFIX_MAP:
            if path.startswith(prefix):
                meta.update(deepcopy(prefix_meta))
                break

        top_key = path.split(".", 1)[0].split("[", 1)[0]
        default_source, default_note = _GROUP_SOURCE_MAP.get(
            top_key, ("Unknown", "No source mapping available.")
        )
        meta.setdefault("source", default_source)
        meta.setdefault("source_note", default_note)
        meta["curated"] = bool(meta.get("curated", False))

    meta.setdefault("label", _default_label_for_path(path))
    meta.setdefault("description", meta.get("source_note") or "Catalog field.")
    tags = meta.get("tags")
    if not isinstance(tags, list):
        tags = []
    top_key = path.split(".", 1)[0].split("[", 1)[0]
    if top_key not in tags:
        tags.append(top_key)
    meta["tags"] = sorted({str(tag).strip() for tag in tags if str(tag).strip()})
    alternatives = meta.get("alternatives")
    if not isinstance(alternatives, list):
        alternatives = []
    meta["alternatives"] = [str(item) for item in alternatives if str(item).strip()]
    metric_key = meta.get("metric_key")
    if metric_key is None:
        meta["metric_key"] = None
    else:
        metric_text = str(metric_key).strip()
        meta["metric_key"] = metric_text or None
    source_text = str(meta.get("source") or "Unknown").strip() or "Unknown"
    cost_tier = str(meta.get("cost_tier") or "").strip().lower()
    if cost_tier not in {"free", "low", "medium", "high"}:
        cost_tier = _SOURCE_COST_TIER_MAP.get(source_text, "medium")
    meta["cost_tier"] = cost_tier

    stability = str(meta.get("stability") or "").strip().lower()
    if stability not in {"stable", "medium", "experimental"}:
        if path.startswith("raw."):
            stability = "experimental"
        elif bool(meta.get("curated")):
            stability = "stable"
        else:
            stability = "medium"
    meta["stability"] = stability

    freshness = str(meta.get("freshness") or "").strip().lower()
    if freshness not in {"activity", "daily", "rolling"}:
        freshness = _infer_freshness(path)
    meta["freshness"] = freshness
    return meta


def _collect_schema_fields(path_prefix: str, value: Any, fields: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in sorted(value.items()):
            next_path = f"{path_prefix}.{key}" if path_prefix else key
            _collect_schema_fields(next_path, nested, fields)
        return

    if isinstance(value, list):
        meta = _field_metadata_for_path(path_prefix)
        value_type = _type_name(value)
        units = meta.get("units")
        if units is None:
            units = _infer_units_for_path(path_prefix, value_type)
        fields.append(
            {
                "path": path_prefix,
                "type": value_type,
                "sample": _sample_value(value),
                "source": meta.get("source"),
                "source_note": meta.get("source_note"),
                "label": meta.get("label"),
                "description": meta.get("description"),
                "tags": meta.get("tags"),
                "metric_key": meta.get("metric_key"),
                "alternatives": meta.get("alternatives"),
                "curated": bool(meta.get("curated")),
                "stability": meta.get("stability"),
                "cost_tier": meta.get("cost_tier"),
                "freshness": meta.get("freshness"),
                "units": units,
            }
        )
        if value and isinstance(value[0], dict):
            for key, nested in sorted(value[0].items()):
                _collect_schema_fields(f"{path_prefix}[0].{key}", nested, fields)
        return

    meta = _field_metadata_for_path(path_prefix)
    value_type = _type_name(value)
    units = meta.get("units")
    if units is None:
        units = _infer_units_for_path(path_prefix, value_type)
    fields.append(
        {
            "path": path_prefix,
            "type": value_type,
            "sample": _sample_value(value),
            "source": meta.get("source"),
            "source_note": meta.get("source_note"),
            "label": meta.get("label"),
            "description": meta.get("description"),
            "tags": meta.get("tags"),
            "metric_key": meta.get("metric_key"),
            "alternatives": meta.get("alternatives"),
            "curated": bool(meta.get("curated")),
            "stability": meta.get("stability"),
            "cost_tier": meta.get("cost_tier"),
            "freshness": meta.get("freshness"),
            "units": units,
        }
    )


def build_context_schema(context: dict[str, Any]) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    total_fields = 0
    source_values: set[str] = set()
    type_values: set[str] = set()
    tag_values: set[str] = set()
    metric_values: set[str] = set()
    stability_values: set[str] = set()
    cost_tier_values: set[str] = set()
    freshness_values: set[str] = set()
    units_values: set[str] = set()
    metric_path_map: dict[str, list[dict[str, str]]] = {}

    for top_key in sorted(context.keys()):
        value = context[top_key]
        fields: list[dict[str, Any]] = []
        if isinstance(value, dict):
            for key, nested in sorted(value.items()):
                _collect_schema_fields(f"{top_key}.{key}", nested, fields)
        else:
            _collect_schema_fields(top_key, value, fields)

        total_fields += len(fields)
        group_source, group_source_note = _GROUP_SOURCE_MAP.get(
            top_key, ("Unknown", "No source mapping available.")
        )
        for field in fields:
            source = str(field.get("source") or "").strip()
            if source:
                source_values.add(source)
            value_type = str(field.get("type") or "").strip()
            if value_type:
                type_values.add(value_type)
            tags = field.get("tags")
            if isinstance(tags, list):
                for tag in tags:
                    tag_text = str(tag).strip()
                    if tag_text:
                        tag_values.add(tag_text)
            metric_key = field.get("metric_key")
            if isinstance(metric_key, str) and metric_key.strip():
                metric_text = metric_key.strip()
                metric_values.add(metric_text)
                metric_path_map.setdefault(metric_text, []).append(
                    {
                        "path": str(field.get("path") or ""),
                        "source": source or "Unknown",
                    }
                )
            stability = str(field.get("stability") or "").strip()
            if stability:
                stability_values.add(stability)
            cost_tier = str(field.get("cost_tier") or "").strip()
            if cost_tier:
                cost_tier_values.add(cost_tier)
            freshness = str(field.get("freshness") or "").strip()
            if freshness:
                freshness_values.add(freshness)
            units = field.get("units")
            if isinstance(units, str) and units.strip():
                units_values.add(units.strip())

        groups.append(
            {
                "group": top_key,
                "field_count": len(fields),
                "source": group_source,
                "source_note": group_source_note,
                "fields": fields,
            }
        )

    overlaps: list[dict[str, Any]] = []
    for metric_key in sorted(metric_path_map.keys()):
        entries = metric_path_map[metric_key]
        unique_paths = {entry["path"] for entry in entries if entry["path"]}
        if len(unique_paths) <= 1:
            continue
        overlaps.append(
            {
                "metric_key": metric_key,
                "paths": sorted(unique_paths),
                "sources": sorted({entry["source"] for entry in entries}),
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "group_count": len(groups),
        "field_count": total_fields,
        "groups": groups,
        "facets": {
            "groups": sorted(str(group["group"]) for group in groups),
            "sources": sorted(source_values),
            "types": sorted(type_values),
            "tags": sorted(tag_values),
            "metric_keys": sorted(metric_values),
            "stability": sorted(stability_values),
            "cost_tiers": sorted(cost_tier_values),
            "freshness": sorted(freshness_values),
            "units": sorted(units_values),
        },
        "overlaps": overlaps,
        "helper_transforms": deepcopy(_CATALOG_HELPER_TRANSFORMS),
    }
