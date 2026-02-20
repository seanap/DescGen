import unittest

from chronicle.stat_modules.crono_api import format_crono_line


class TestCronoApiFormatting(unittest.TestCase):
    def test_format_line_with_macros(self) -> None:
        line = format_crono_line(
            {
                "average_net_kcal_per_day": 624.21,
                "average_status": "surplus",
                "protein_g": 109.42,
                "carbs_g": 319.3,
            }
        )
        self.assertEqual(
            line,
            "🔥 7d avg daily Energy Balance:+624 kcal (surplus) | 🥩:109.4g | 🍞:319.3g",
        )

    def test_omit_zero_macros(self) -> None:
        line = format_crono_line(
            {
                "average_net_kcal_per_day": -210.0,
                "average_status": "deficit",
                "protein_g": 0,
                "carbs_g": 0,
            }
        )
        self.assertEqual(line, "🔥 7d avg daily Energy Balance:-210 kcal (deficit)")

    def test_requires_energy_balance(self) -> None:
        line = format_crono_line({"protein_g": 10, "carbs_g": 20})
        self.assertIsNone(line)


if __name__ == "__main__":
    unittest.main()
