#!/usr/bin/env python3
"""Focused tests for internal navigation without reload (js/soft-nav.js, 2026-11-10).

The music must keep playing across pages: one engine and one <audio> element for the whole visit. These tests pin the
integration (every page of the shell loads soft-nav.js first, the engine is never re-run, the player views can be
mounted again) and run the link and scope rules in Node (tests/support/soft_nav_scenarios.js). Audio continuity
itself is verified in a real browser (mission report): no pause, emptied, loadstart or seeking event and zero new
audio elements across every route, Back and Forward.

Run: python3 -m unittest tests/test_soft_nav.py
"""

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
SHELL_PAGES = ("index.html", "cv.html", "sobre-mi.html", "music/index.html", "agenda/index.html", "formacion/index.html",
               "formacion/piano/index.html", "formacion/composicion/index.html", "formacion/produccion-musical/index.html")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class IntegrationTest(unittest.TestCase):
    def test_every_shell_page_loads_it_first_and_once(self):
        for rel in SHELL_PAGES:
            scripts = re.findall(r'<script src="(?:\.\./)*js/([\w-]+\.js)"></script>', read(rel))
            with self.subTest(page=rel):
                self.assertEqual(scripts[0], "theme-init.js")
                self.assertEqual(scripts[1], "soft-nav.js")
                self.assertEqual(scripts.count("soft-nav.js"), 1)
                self.assertEqual(scripts.count("player.js"), 1)
                self.assertIn('id="mini-player"', read(rel))

    def test_pages_outside_the_shell_keep_a_traditional_load(self):
        # 404.html is self-contained and the link-preview pages redirect: no soft-nav.js, so a link to them reloads.
        self.assertNotIn("soft-nav.js", read("404.html"))
        share = next((ROOT / "music" / "song").iterdir()) / "index.html"
        self.assertNotIn("soft-nav.js", share.read_text(encoding="utf-8"))

    def test_published_with_the_site(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_site
        self.assertIn("js/soft-nav.js", build_site.STATIC_FILES)

    def test_engine_is_created_once_and_views_can_be_mounted_again(self):
        player = read("js/player.js")
        self.assertEqual(player.count("document.createElement('audio')"), 1)
        self.assertIn("window.LGPlayerViews=mountPlayerViews;", player)
        self.assertIn("if(window.LGSoftNav)window.LGSoftNav.page(mountPlayerViews);else mountPlayerViews();", player)
        # Subscriptions can be released, so a page left behind stops receiving engine events.
        self.assertRegex(player, r"on:fn=>\{listeners\.push\(fn\);const off=")
        soft = read("js/soft-nav.js")
        # The engine and the catalogue data are never executed again; player.js is replaced by mounting its views.
        self.assertIn(r"var SKIP = /\/js\/(?:soft-nav|music-data|theme-init)\.js(?:[?#]|$)/;", soft)
        self.assertIn(r"var PLAYER = /\/js\/player\.js(?:[?#]|$)/;", soft)
        self.assertIn("window.LGPlayerViews()", soft)
        # No audio element of its own.
        self.assertNotIn("createElement('audio')", soft)
        self.assertNotIn("Audio(", soft)

    def test_agenda_page_code_is_unchanged(self):
        # The navigation layer needs no change in the booking page (its backend changes only for owner notifications).
        out = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", "js/agenda.js"])
        self.assertEqual(out.returncode, 0, "js/agenda.js is not modified")

    def test_no_em_dash(self):
        self.assertNotIn("—", read("js/soft-nav.js"))


@unittest.skipUnless(NODE, "node not installed")
class ScenarioTest(unittest.TestCase):
    def test_link_rules_scope_tracking_and_inertness(self):
        out = subprocess.run([NODE, str(ROOT / "tests" / "support" / "soft_nav_scenarios.js")], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        results = json.loads(out.stdout)
        self.assertGreaterEqual(len(results), 6)
        self.assertEqual({k: v for k, v in results.items() if v != "ok"}, {})


if __name__ == "__main__":
    unittest.main()
