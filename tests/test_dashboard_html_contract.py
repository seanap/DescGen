from __future__ import annotations

import unittest
from pathlib import Path


class TestDashboardHtmlContract(unittest.TestCase):
    def test_dashboard_mount_ids_and_script_contract(self) -> None:
        html_path = Path("templates/dashboard.html")
        self.assertTrue(html_path.exists(), "templates/dashboard.html missing")
        html = html_path.read_text(encoding="utf-8")

        required_ids = [
            "dashboardTitle",
            "summary",
            "heatmaps",
            "tooltip",
            "headerMeta",
            "typeButtons",
            "yearButtons",
            "typeMenu",
            "yearMenu",
            "typeClearButton",
            "yearClearButton",
            "resetAllButton",
            "footerHostedPrefix",
            "footerHostedLink",
            "footerPoweredLabel",
            "footerPoweredLink",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', html, f"Missing dashboard mount id: {element_id}")

        self.assertIn('<script src="/static/dashboard.js"></script>', html)


if __name__ == "__main__":
    unittest.main()
