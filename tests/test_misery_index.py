import unittest

from stat_modules.misery_index import (
    calculate_misery_index,
    calculate_misery_index_components,
    get_aqi_description,
    get_misery_index_description,
)


class TestMiseryIndex(unittest.TestCase):
    def test_misery_buckets(self) -> None:
        self.assertEqual(get_misery_index_description(10), "☠️⚠️ High risk (cold)")
        self.assertEqual(get_misery_index_description(35), "🥶 Oppressively cold")
        self.assertEqual(get_misery_index_description(65), "😕 Mild uncomfortable (cold)")
        self.assertEqual(get_misery_index_description(95), "😀 Perfect")
        self.assertEqual(get_misery_index_description(135), "😕 Mild uncomfortable")
        self.assertEqual(get_misery_index_description(145), "😓 Moderate uncomfortable")
        self.assertEqual(get_misery_index_description(155), "😰 Very uncomfortable")
        self.assertEqual(get_misery_index_description(165), "🥵 Oppressive")
        self.assertEqual(get_misery_index_description(175), "😡 Miserable")
        self.assertEqual(get_misery_index_description(185), "☠️⚠️ High risk")

    def test_cold_dry_windy_is_low_score(self) -> None:
        score = calculate_misery_index(
            temp_f=22,
            dew_point_f=8,
            humidity=45,
            wind_speed_mph=18,
            cloud_cover_pct=85,
            precip_in=0.0,
            is_day=True,
            condition_text="Overcast",
        )
        self.assertLess(score, 50)

    def test_hot_humid_stagnant_is_high_score(self) -> None:
        score = calculate_misery_index(
            temp_f=92,
            dew_point_f=75,
            humidity=78,
            wind_speed_mph=1.0,
            cloud_cover_pct=5,
            precip_in=0.0,
            is_day=True,
            condition_text="Sunny",
        )
        self.assertGreater(score, 180)

    def test_rain_and_snow_push_colder_side(self) -> None:
        score = calculate_misery_index(
            temp_f=34,
            dew_point_f=30,
            humidity=90,
            wind_speed_mph=8,
            cloud_cover_pct=95,
            precip_in=0.12,
            is_day=True,
            chance_of_snow=80,
            condition_text="Moderate snow",
        )
        self.assertLess(score, 40)

    def test_no_large_jump_at_thermal_transition_edges(self) -> None:
        around_50 = [
            calculate_misery_index(
                temp_f=t,
                dew_point_f=45,
                humidity=50,
                wind_speed_mph=5,
                cloud_cover_pct=50,
                precip_in=0.0,
                is_day=True,
            )
            for t in (49.9, 50.0, 50.1)
        ]
        around_80 = [
            calculate_misery_index(
                temp_f=t,
                dew_point_f=65,
                humidity=65,
                wind_speed_mph=4,
                cloud_cover_pct=20,
                precip_in=0.0,
                is_day=True,
            )
            for t in (79.9, 80.0, 80.1)
        ]
        self.assertLess(max(around_50) - min(around_50), 2.0)
        self.assertLess(max(around_80) - min(around_80), 2.0)

    def test_no_large_jump_at_precip_thresholds(self) -> None:
        values = [
            calculate_misery_index(
                temp_f=55,
                dew_point_f=50,
                humidity=90,
                wind_speed_mph=4,
                cloud_cover_pct=90,
                precip_in=p,
                is_day=True,
            )
            for p in (0.029, 0.030, 0.031, 0.099, 0.100, 0.101)
        ]
        self.assertLess(max(values) - min(values), 6.0)

    def test_string_weather_inputs_are_handled(self) -> None:
        score = calculate_misery_index(
            temp_f=34,
            dew_point_f=30,
            humidity=90,
            wind_speed_mph=8,
            cloud_cover_pct=95,
            precip_in=0.0,
            is_day=True,
            chance_of_snow="80",
            will_it_snow="1",
            condition_text="Cloudy",
        )
        self.assertLess(score, 50)

    def test_component_breakdown_exposes_hot_and_cold_totals(self) -> None:
        components = calculate_misery_index_components(
            temp_f=55,
            dew_point_f=45,
            humidity=50,
            wind_speed_mph=5,
        )
        self.assertIn("score", components)
        self.assertIn("score_raw", components)
        self.assertIn("hot_points", components)
        self.assertIn("cold_points", components)

    def test_aqi_description(self) -> None:
        self.assertEqual(get_aqi_description(1), "😃")
        self.assertEqual(get_aqi_description(99), "Unknown")


if __name__ == "__main__":
    unittest.main()
