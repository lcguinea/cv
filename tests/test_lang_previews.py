#!/usr/bin/env python3
"""Language link previews of the main pages (tools/build_lang_previews.py): en/<page> and es/<page>.

Crawlers (WhatsApp, social networks) read them without JavaScript, so each one carries the title, description and
og:locale of its language; visitors go on to the real page with ?lang=<language>, keeping the other parameters.

Run: python3 -m unittest tests/test_lang_previews.py
"""

import html
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "build_lang_previews.py"
NODE = shutil.which("node")
SITE = "https://luisguinea.com/"
PAGES = ("index.html", "cv.html", "sobre-mi.html", "music/index.html", "agenda/index.html", "formacion/index.html",
         "formacion/piano/index.html", "formacion/composicion/index.html", "formacion/produccion-musical/index.html")

REDIRECT = r"""
const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync(process.argv[1], 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
let to = null;
vm.runInNewContext(code, { location: { search: process.argv[2], hash: process.argv[3], replace: u => { to = u; } } });
process.stdout.write(to);
"""


def tag(text, name):
    found = re.findall(rf'<meta (?:property|name)="{name}" content="([^"]*)"', text)
    return html.unescape(found[0]) if len(found) == 1 else None


@unittest.skipUnless(NODE, "node not installed")
class LangPreviewTests(unittest.TestCase):
    def test_pages_are_up_to_date(self):
        out = subprocess.run(["python3", str(TOOL), "--check"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_each_page_has_both_languages_with_their_own_metadata(self):
        for rel in PAGES:
            source = (ROOT / rel).read_text(encoding="utf-8")
            native = re.search(r'<html lang="([a-z]{2})', source).group(1)
            texts = {}
            for lang in ("en", "es"):
                with self.subTest(page=rel, lang=lang):
                    text = (ROOT / lang / rel).read_text(encoding="utf-8")
                    texts[lang] = text
                    self.assertIn(f'<html lang="{lang}">', text)
                    self.assertEqual(tag(text, "og:locale"), {"en": "en_US", "es": "es_ES"}[lang])
                    self.assertEqual(tag(text, "og:url"), SITE + f"{lang}/{rel}".removesuffix("index.html"))
                    self.assertIn('<meta name="robots" content="noindex">', text)
                    self.assertEqual(tag(text, "og:image"), tag(source, "og:image"))
                    if lang == native:
                        self.assertEqual(tag(text, "og:title"), tag(source, "og:title"))
                        self.assertEqual(tag(text, "og:description"), tag(source, "og:description"))
            with self.subTest(page=rel):
                self.assertNotEqual(tag(texts["en"], "og:description"), tag(texts["es"], "og:description"))

    def go(self, rel, search="", hash_=""):
        return subprocess.run([NODE, "-e", REDIRECT, str(ROOT / rel), search, hash_],
                              capture_output=True, text=True, check=True).stdout

    def test_visitors_go_on_to_the_page_in_that_language(self):
        self.assertEqual(self.go("en/formacion/index.html"), "../../formacion/?lang=en")
        self.assertEqual(self.go("es/index.html"), "../?lang=es")
        self.assertEqual(self.go("es/cv.html", "?theme=dark", "#experience"), "../cv.html?theme=dark&lang=es#experience")
        self.assertEqual(self.go("en/formacion/piano/index.html", "?lang=es&theme=light"),
                         "../../../formacion/piano/?theme=light&lang=en")

    def test_fallback_link_points_to_the_page(self):
        text = (ROOT / "en/music/index.html").read_text(encoding="utf-8")
        self.assertIn('<a href="../../music/?lang=en">', text)


if __name__ == "__main__":
    unittest.main()
