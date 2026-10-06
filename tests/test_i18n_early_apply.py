#!/usr/bin/env python3
"""Focused tests for the early application of a saved language in js/i18n.js.

i18n.js runs after the whole body is parsed. With a saved non-default language it applies it at once, so the
browser does not paint the English fallback while the later scripts load; DOMContentLoaded applies it again
through the site.js wrapper, which adds translated aria-labels, the language version of bilingual article links
and the lg:language event. These tests look at each page between its last script and DOMContentLoaded
(tests/support/minidom.js, deferReady) and after it.

Needs Node.js. Standard library only.

Run: python3 -m unittest tests/test_i18n_early_apply.py
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
STRINGS_JS = ROOT / "js" / "strings.js"
NODE = shutil.which("node")
PAGES = ("index.html", "cv.html", "music/index.html")
# Music labels whose served fallback is empty on purpose (tests/test_i18n_fallbacks.py): until DOMContentLoaded
# an English page shows them as served.
JS_ONLY = {"music.releases", "music.nowSelected", "music.creditsLabel"}
COUNT = "page.eval(\"window.__languageEvents = 0; document.addEventListener('lg:language', () => { window.__languageEvents++; })\");"

READ = (
    "const read = () => ({"
    "  text: page.$$('[data-i18n]').filter(e => !['music.playing', 'music.selected'].includes(e.dataset.i18n)).map(e => [e.dataset.i18n, e.textContent]),"
    "  labels: page.$$('[data-i18n-label]').map(e => [e.dataset.i18nLabel, e.getAttribute('aria-label')]),"
    "  placeholders: page.$$('[data-i18n-placeholder]').map(e => [e.dataset.i18nPlaceholder, e.placeholder]),"
    "  links: page.$$('a[data-href-en][data-href-es]').map(a => [a.getAttribute('href'), a.getAttribute('hreflang'), a.dataset.hrefEn, a.dataset.hrefEs]),"
    "  pressed: page.$$('[data-lang]').map(b => [b.dataset.lang, b.getAttribute('aria-pressed')]),"
    "  lang: page.$('html').getAttribute('lang'), main: page.$('main').innerHTML,"
    "  events: page.eval('window.__languageEvents'), playing: page.eval('LGPlayer.isPlaying()') });"
)


def strings():
    result = subprocess.run(
        [NODE, "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                     "process.stdout.write(JSON.stringify(window.STRINGS))", str(STRINGS_JS)],
        capture_output=True, text=True, check=True)
    return {lang: flatten(tree) for lang, tree in json.loads(result.stdout).items()}


def flatten(tree, prefix=""):
    out = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            out.update(flatten(value, prefix + key + "."))
        else:
            out[prefix + key] = value
    return out


def run(scenario):
    result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def load(rel, saved):
    """State of a page before and after DOMContentLoaded with a given saved language (None: nothing saved)."""
    store = "" if saved is None else f"browser.local['lg-language'] = {json.dumps(saved)};"
    return run(
        store + f"const page = browser.tab().open({json.dumps(rel)}, {{deferReady: true}});"
        + COUNT + READ + "out.before = read(); page.ready(); await settle(); out.after = read();")


@unittest.skipUnless(NODE, "node not installed")
class EarlyApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = strings()

    def assert_language(self, state, lang, extras, served=False):
        """Texts, placeholders, html lang and the EN/ES buttons in `lang`; aria-labels and links in `extras`.
        served: the English page as served, before i18n has written anything (JS-only labels still empty)."""
        s = self.s
        self.assertEqual(state["lang"], lang)
        self.assertEqual(sorted(state["pressed"]), [["en", str(lang == "en").lower()], ["es", str(lang == "es").lower()]])
        for key, value in state["text"] + state["placeholders"]:
            with self.subTest(key=key):
                self.assertEqual(value, "" if served and key in JS_ONLY else s[lang][key])
        for key, value in state["labels"]:
            with self.subTest(label=key):
                self.assertEqual(value, s[extras][key])
        for href, hreflang, en, es in state["links"]:
            self.assertEqual(href, es if extras == "es" else en)
            if extras == "es":
                self.assertEqual(hreflang, "es")

    def test_saved_spanish_is_applied_before_domcontentloaded(self):
        for rel in PAGES:
            with self.subTest(page=rel):
                out = load(rel, "es")
                # Before DOMContentLoaded: copy already Spanish; the site.js extras are not applied yet.
                self.assert_language(out["before"], "es", "en")
                self.assertEqual(out["before"]["events"], 0)
                # After: everything Spanish and lg:language emitted exactly once.
                self.assert_language(out["after"], "es", "es")
                self.assertEqual(out["after"]["events"], 1)
                self.assertFalse(out["before"]["playing"] or out["after"]["playing"])

    def test_english_and_no_or_invalid_preference_keep_the_fallback_until_domcontentloaded(self):
        for saved in (None, "en", "xx"):
            for rel in PAGES:
                with self.subTest(saved=saved, page=rel):
                    out = load(rel, saved)
                    self.assert_language(out["before"], "en", "en", served=True)
                    self.assertEqual(out["before"]["events"], 0)
                    self.assert_language(out["after"], "en", "en")
                    self.assertEqual(out["after"]["events"], 1)
                    self.assertFalse(out["before"]["playing"] or out["after"]["playing"])

    def test_spanish_load_ends_like_a_live_switch_to_spanish(self):
        for rel in PAGES:
            with self.subTest(page=rel):
                early = load(rel, "es")["after"]
                live = run(f"const page = browser.tab().open({json.dumps(rel)}); await settle();"
                           + COUNT + READ + "page.click('[data-lang=\"es\"]'); await settle(); out.es = read();")["es"]
                for field in ("text", "labels", "placeholders", "links", "pressed", "lang", "playing"):
                    self.assertEqual(early[field], live[field], field)

    def test_switch_from_english_to_spanish_and_back_restores_the_content(self):
        for rel in PAGES:
            with self.subTest(page=rel):
                out = run(f"const page = browser.tab().open({json.dumps(rel)}); await settle();"
                          + COUNT + READ +
                          "out.en = read(); page.click('[data-lang=\"es\"]'); await settle(); out.es = read();"
                          "page.click('[data-lang=\"en\"]'); await settle(); out.back = read();")
                self.assertEqual(out["back"]["main"], out["en"]["main"])
                self.assertNotEqual(out["es"]["main"], out["en"]["main"])
                self.assert_language(out["es"], "es", "es")
                self.assert_language(out["back"], "en", "en")
                self.assertEqual(out["back"]["events"], 2)
                self.assertFalse(any(out[k]["playing"] for k in ("en", "es", "back")))


if __name__ == "__main__":
    unittest.main()
