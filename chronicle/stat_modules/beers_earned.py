from __future__ import annotations


def calculate_beers(activity: dict) -> float:
    calories = activity.get("calories")
    if not isinstance(calories, (int, float)):
        return 0.0
    return float(calories) / 150.0
