import unittest

from stat_modules.misery_index import get_aqi_description, get_misery_index_description


class TestMiseryIndex(unittest.TestCase):
    def test_misery_buckets(self) -> None:
        self.assertEqual(get_misery_index_description(135), "😅 Mild")
        self.assertEqual(get_misery_index_description(170), "☠️⚠️ High risk")

    def test_aqi_description(self) -> None:
        self.assertEqual(get_aqi_description(1), "😃")
        self.assertEqual(get_aqi_description(99), "Unknown")


if __name__ == "__main__":
    unittest.main()
