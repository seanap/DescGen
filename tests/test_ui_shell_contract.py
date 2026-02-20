from __future__ import annotations

import unittest
from pathlib import Path


class TestUiShellContract(unittest.TestCase):
    def test_shared_nav_partial_has_required_links_and_active_semantics(self) -> None:
        nav_path = Path("templates/_app_shell_nav.html")
        self.assertTrue(nav_path.exists(), "Missing shared nav partial")
        nav = nav_path.read_text(encoding="utf-8")

        self.assertIn('href="/setup"', nav)
        self.assertIn('href="/editor"', nav)
        self.assertIn('href="/control"', nav)
        self.assertIn('href="/dashboard"', nav)
        self.assertIn("aria-label=\"Primary\"", nav)
        self.assertIn("aria-current=\"page\"", nav)
        self.assertIn("is-active", nav)

    def test_all_web_pages_include_shared_theme_and_nav(self) -> None:
        targets = {
            "templates/setup.html": {
                "required": [
                    '<link rel="stylesheet" href="/static/ui-theme.css">',
                    '{% include "_app_shell_nav.html" %}',
                    '<link rel="stylesheet" href="/static/setup.css">',
                ],
                "forbidden": [
                    "<style>",
                ],
            },
            "templates/editor.html": {
                "required": [
                    '<link rel="stylesheet" href="/static/ui-theme.css">',
                    '{% include "_app_shell_nav.html" %}',
                ],
                "forbidden": [],
            },
            "templates/dashboard.html": {
                "required": [
                    '<link rel="stylesheet" href="/static/ui-theme.css" />',
                    '{% include "_app_shell_nav.html" %}',
                ],
                "forbidden": [],
            },
            "templates/control.html": {
                "required": [
                    '<link rel="stylesheet" href="/static/ui-theme.css">',
                    '{% include "_app_shell_nav.html" %}',
                    '<link rel="stylesheet" href="/static/control.css">',
                ],
                "forbidden": [
                    "<style>",
                ],
            },
        }

        for path, rules in targets.items():
            content = Path(path).read_text(encoding="utf-8")
            for required in rules["required"]:
                self.assertIn(required, content, f"Missing required shell contract in {path}: {required}")
            for forbidden in rules["forbidden"]:
                self.assertNotIn(forbidden, content, f"Unexpected legacy markup in {path}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
