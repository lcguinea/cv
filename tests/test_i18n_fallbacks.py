#!/usr/bin/env python3
"""Focused tests for the English fallback that Home, CV and Music carry in their served HTML.

Without JavaScript every translatable element already reads in English; with JavaScript the i18n system
replaces it from js/strings.js, which stays the only authority for the copy. These tests keep the two
from drifting: every data-i18n element, data-i18n-label and data-i18n-placeholder holds exactly the
value of STRINGS.en, except a closed list of Music labels that only describe what the catalogue script
renders. They also check that the semantic structure is not empty without JavaScript and that the live
EN -> ES -> EN switch restores the English content exactly.

Static checks always run. Behaviour checks run the real pages in tests/support/minidom.js and need
Node.js. Standard library only.

Run: python3 -m unittest tests/test_i18n_fallbacks.py
"""

import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
STRINGS_JS = ROOT / "js" / "strings.js"
NODE = shutil.which("node")
PAGES = ("index.html", "cv.html", "music/index.html")
# Labels for values that exist only once music-page.js has rendered the catalogue and the selected track:
# a static fallback would read "0 / 0 releases" or announce a selection and credits that are not there.
JS_ONLY = {"music.releases", "music.nowSelected", "music.creditsLabel"}
CHART_LABEL = {"en": "Tracks and streams rise across three observations",
               "es": "Las canciones y los streams crecen en las tres observaciones"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


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


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def walk(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.walk()


class Tree(HTMLParser):
    """The served HTML as a crawler without JavaScript reads it."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("#root", [], None)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def tree(rel):
    return Tree((ROOT / rel).read_text(encoding="utf-8")).root


def run(scenario):
    result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


@unittest.skipUnless(NODE, "node not installed")
class StaticFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = strings()
        cls.en, cls.es = cls.s["en"], cls.s["es"]
        cls.trees = {rel: tree(rel) for rel in PAGES}

    def test_every_text_fallback_is_the_english_string(self):
        for rel, root in self.trees.items():
            for node in root.walk():
                key = node.attrs.get("data-i18n")
                if key is None or key in JS_ONLY:
                    continue
                with self.subTest(page=rel, key=key):
                    self.assertEqual(node.text(), self.en[key])

    def test_translatable_attributes_carry_the_english_string(self):
        for rel, root in self.trees.items():
            for node in root.walk():
                for hook, attr in (("data-i18n-label", "aria-label"), ("data-i18n-placeholder", "placeholder")):
                    key = node.attrs.get(hook)
                    if key is not None:
                        with self.subTest(page=rel, key=key, attr=attr):
                            self.assertEqual(node.attrs.get(attr), self.en[key])

    def test_js_only_labels_are_exactly_three_and_stay_empty(self):
        found = {}
        for rel, root in self.trees.items():
            for node in root.walk():
                key = node.attrs.get("data-i18n")
                if key in JS_ONLY:
                    found.setdefault(key, []).append((rel, node.text()))
        self.assertEqual(set(found), JS_ONLY)
        for key, places in found.items():
            self.assertEqual(places, [("music/index.html", "")], key)

    def test_every_key_exists_in_english_and_spanish(self):
        for rel, root in self.trees.items():
            for node in root.walk():
                for hook in ("data-i18n", "data-i18n-label", "data-i18n-placeholder"):
                    key = node.attrs.get(hook)
                    if key is not None:
                        with self.subTest(page=rel, key=key):
                            self.assertIn(key, self.en)
                            self.assertIn(key, self.es)

    def test_semantic_structure_is_not_empty_without_javascript(self):
        for rel, root in self.trees.items():
            nodes = list(root.walk())
            heads = [n for n in nodes if n.tag in ("h1", "h2")]
            self.assertEqual(sum(n.tag == "h1" for n in heads), 1, rel)
            for node in heads:
                with self.subTest(page=rel, heading=node.attrs.get("data-i18n")):
                    self.assertTrue(node.text().strip())
            for node in nodes:
                if node.tag == "a":
                    with self.subTest(page=rel, href=node.attrs.get("href")):
                        self.assertTrue(node.text().strip() or node.attrs.get("aria-label", "").strip())
                if node.tag in ("label", "option"):
                    with self.subTest(page=rel, tag=node.tag, key=node.attrs.get("data-i18n")):
                        self.assertTrue(node.text().strip())

    def test_hero_practice_includes_ai(self):
        (practice,) = [n for n in self.trees["index.html"].walk() if n.attrs.get("data-i18n") == "hero.practice"]
        self.assertEqual(practice.text(), "Music · Data · AI · Writing")

    def test_chart_label_is_connected_to_i18n(self):
        (chart,) = [n for n in self.trees["index.html"].walk() if n.tag == "svg" and n.attrs.get("role") == "img"]
        self.assertEqual(chart.attrs.get("data-i18n-label"), "writing.chartLabel")
        self.assertEqual(chart.attrs.get("aria-label"), CHART_LABEL["en"])
        self.assertEqual((self.en["writing.chartLabel"], self.es["writing.chartLabel"]), (CHART_LABEL["en"], CHART_LABEL["es"]))


@unittest.skipUnless(NODE, "node not installed")
class LanguageSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = strings()

    def test_switch_renders_each_language_and_restores_english_exactly(self):
        for rel in PAGES:
            with self.subTest(page=rel):
                out = run(
                    f"const page = browser.tab().open({json.dumps(rel)}); await settle();"
                    "const read = () => ({"
                    "  text: page.$$('[data-i18n]').map(e => [e.dataset.i18n, e.textContent]),"
                    "  labels: page.$$('[data-i18n-label]').map(e => [e.dataset.i18nLabel, e.getAttribute('aria-label')]),"
                    "  placeholders: page.$$('[data-i18n-placeholder]').map(e => [e.dataset.i18nPlaceholder, e.placeholder]),"
                    "  main: page.$('main').innerHTML, lang: page.$('html').getAttribute('lang'),"
                    "  playing: page.eval('LGPlayer.isPlaying()') });"
                    "out.en = read(); page.click('[data-lang=\"es\"]'); await settle(); out.es = read();"
                    "page.click('[data-lang=\"en\"]'); await settle(); out.back = read();")
                self.assertEqual(out["back"], out["en"])
                for lang in ("en", "es"):
                    got = out[lang]
                    self.assertEqual(got["lang"], lang)
                    self.assertFalse(got["playing"])
                    for kind in ("text", "labels", "placeholders"):
                        for key, value in got[kind]:
                            with self.subTest(lang=lang, kind=kind, key=key):
                                if kind == "text" and key in ("music.playing", "music.selected"):
                                    continue
                                self.assertEqual(value, self.s[lang][key])
                self.assertNotEqual(out["es"]["main"], out["en"]["main"])

    def test_chart_label_follows_the_language(self):
        out = run(
            "const page = browser.tab().open('index.html'); await settle();"
            "const chart = () => page.$('svg[role=\"img\"]').getAttribute('aria-label');"
            "out.en = chart(); page.click('[data-lang=\"es\"]'); await settle(); out.es = chart();"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = chart();")
        self.assertEqual(out, {"en": CHART_LABEL["en"], "es": CHART_LABEL["es"], "back": CHART_LABEL["en"]})


if __name__ == "__main__":
    unittest.main()
