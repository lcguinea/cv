#!/usr/bin/env python3
"""A shared link can set the theme (?theme=dark|light) and the language (?lang=es|en).

The link's value wins over the visitor's saved choice for that tab (sessionStorage keeps it across internal
navigation) without overwriting it; clicking the theme or EN/ES buttons clears it. Covers js/theme-init.js,
js/i18n.js and the inline copies in 404.html, run in Node with a stubbed browser.

Needs Node.js. Standard library only.

Run: python3 -m unittest tests/test_link_preferences.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [file, cfg] = [process.argv[1], JSON.parse(process.argv[2])];
let code = fs.readFileSync(file, 'utf8');
if (cfg.inline !== undefined) code = [...code.matchAll(/<script>([\s\S]*?)<\/script>/g)][cfg.inline][1];
function store(init) { const m = new Map(Object.entries(init || {})); return {
  getItem: k => m.has(k) ? m.get(k) : null, setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k),
  dump: () => Object.fromEntries(m) }; }
const attrs = { lang: cfg.pageLang || 'en' };
const root = { dataset: {}, classList: { add() {} }, getAttribute: k => k in attrs ? attrs[k] : null,
  set lang(v) { attrs.lang = v; }, get lang() { return attrs.lang; } };
const local = store(cfg.local), session = store(cfg.session);
const ctx = { localStorage: local, sessionStorage: session, URLSearchParams,
  location: { search: cfg.search || '' }, navigator: { languages: cfg.languages || ['en-US'] },
  document: { documentElement: root, title: '', querySelectorAll: () => [], addEventListener() {} },
  STRINGS: { en: {}, es: {} } };
ctx.window = ctx;
vm.runInNewContext(code, ctx);
process.stdout.write(JSON.stringify({ theme: root.dataset.theme || 'light', lang: ctx.currentLanguage || attrs.lang,
  local: local.dump(), session: session.dump() }));
"""


def run(rel, inline=None, **cfg):
    if inline is not None:
        cfg["inline"] = inline
    out = subprocess.run([NODE, "-e", HARNESS, str(ROOT / rel), json.dumps(cfg)], capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


def inline_index(substring):
    scripts = re.findall(r"<script>([\s\S]*?)</script>", (ROOT / "404.html").read_text())
    return next(i for i, s in enumerate(scripts) if substring in s)


@unittest.skipUnless(NODE, "node not installed")
class ThemeLinkTests(unittest.TestCase):
    def check(self, **kw):
        a = run("js/theme-init.js", **kw)
        b = run("404.html", inline_index("lg-theme"), **kw)
        self.assertEqual(a["theme"], b["theme"])
        return a

    def test_link_sets_the_theme_and_keeps_it_in_the_tab(self):
        r = self.check(search="?theme=dark")
        self.assertEqual(r["theme"], "dark")
        self.assertEqual(r["session"].get("lg-theme-link"), "dark")
        self.assertNotIn("lg-theme", r["local"])

    def test_link_wins_over_saved_choice_without_overwriting_it(self):
        r = self.check(search="?song=x&theme=light", local={"lg-theme": "dark"})
        self.assertEqual(r["theme"], "light")
        self.assertEqual(r["local"]["lg-theme"], "dark")
        self.assertEqual(self.check(search="?theme=dark", local={"lg-theme": "light"})["theme"], "dark")

    def test_internal_navigation_keeps_the_link_theme(self):
        r = self.check(session={"lg-theme-link": "dark"}, local={"lg-theme": "light"})
        self.assertEqual(r["theme"], "dark")

    def test_invalid_or_missing_values_fall_back_to_the_saved_choice(self):
        self.assertEqual(self.check(search="?theme=blue", local={"lg-theme": "dark"})["theme"], "dark")
        self.assertEqual(self.check()["theme"], "light")


@unittest.skipUnless(NODE, "node not installed")
class LanguageLinkTests(unittest.TestCase):
    def test_link_sets_the_language_over_browser_and_saved_choice(self):
        r = run("js/i18n.js", search="?lang=es", languages=["en-US"],
                local={"lg-language": "en", "lg-language-manual": "1"})
        self.assertEqual(r["lang"], "es")
        self.assertEqual(r["session"]["lg-language-link"], "es")
        self.assertEqual(r["local"]["lg-language"], "en")

    def test_link_overrides_a_spanish_page_default(self):
        self.assertEqual(run("js/i18n.js", search="?lang=en", pageLang="es")["lang"], "en")

    def test_internal_navigation_keeps_the_link_language(self):
        r = run("js/i18n.js", session={"lg-language-link": "en"}, languages=["es-ES"], local={"lg-language": "es"})
        self.assertEqual(r["lang"], "en")

    def test_invalid_value_is_ignored(self):
        self.assertEqual(run("js/i18n.js", search="?lang=fr", languages=["es-MX"])["lang"], "es")

    def test_404_follows_the_link_language(self):
        i = inline_index("lg-language")
        self.assertEqual(run("404.html", i, search="?lang=es", languages=["en-US"])["lang"], "es")
        self.assertEqual(run("404.html", i, search="?lang=en", local={"lg-language": "es"})["lang"], "en")
        self.assertEqual(run("404.html", i, session={"lg-language-link": "es"})["lang"], "es")


class ButtonsClearTheLinkTests(unittest.TestCase):
    def test_clicks_clear_the_link_override(self):
        self.assertIn("sessionStorage.removeItem('lg-theme-link')", (ROOT / "js/site.js").read_text())
        self.assertIn("sessionStorage.removeItem('lg-language-link')", (ROOT / "js/i18n.js").read_text())


if __name__ == "__main__":
    unittest.main()
