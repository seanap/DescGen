import tempfile
import unittest
from pathlib import Path

from storage import is_activity_processed, mark_activity_processed, read_json, write_json


class TestStorage(unittest.TestCase):
    def test_processed_activity_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            self.assertFalse(is_activity_processed(path, 123))
            mark_activity_processed(path, 123)
            self.assertTrue(is_activity_processed(path, 123))
            mark_activity_processed(path, 123)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["123"])

    def test_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "latest.json"
            payload = {"activity_id": 123, "description": "hello"}
            write_json(path, payload)
            self.assertEqual(read_json(path), payload)


if __name__ == "__main__":
    unittest.main()
