#!/usr/bin/env python3
"""Focused tests for the Formación Musical section (/formacion/ and its subpages, 2026-11-10).

Covers: generated files up to date, Spanish served HTML that matches STRINGS.es, SEO metadata and structured data,
accessibility basics, the language default of Spanish pages, and the editorial guard rails of the mission: no prices,
free lessons, discounts, cancellation terms, address, testimonials or claims that CV_MASTER.md does not support are
published until Luis approves them.

Standard library; the language behaviour tests need Node.js. Run: python3 -m unittest tests/test_formacion.py
"""

import html
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://luisguinea.com/"
NODE = shutil.which("node")
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
PAGES = {
    "formacion/index.html": SITE + "formacion/",
    "formacion/piano/index.html": SITE + "formacion/piano/",
    "formacion/composicion/index.html": SITE + "formacion/composicion/",
    "formacion/produccion-musical/index.html": SITE + "formacion/produccion-musical/",
}
# Wording that needs Luis's approval or evidence before it can appear (mission §6, §9; CV_MASTER.md rules).
FORBIDDEN = [
    r"€", r"\beuros?\b", r"\bgratis\b", r"gratuit", r"descuento", r"\bcancela", r"reembols", r"matr[ií]cula",
    r"permanencia", r"\bCarrer\b", r"\bCalle\b", r"\bC/\s", r"\bAvda?\.", r"\b460\d\d\b", r"13 años", r"Sync Camp", r"galardonad", r"Top 10",
    r"virtuos", r"Palau de les Arts", r"Cubase", r"9[.,]7", r"testimoni", r"\bjazz\b", r"pedagog",
    # Mission 02 §8: provisional terms stay unpublished until Luis approves them.
    r"sin coste", r"15 minutos", r"24 horas", r"learn-fees", r"Jazztone Studios[^<]{0,40}clases",
]
ENQUIRY_SCENARIOS = ROOT / "tests" / "support" / "enquiry_scenarios.js"
sys.path.insert(0, str(ROOT / "tools"))
import formacion_content as C  # noqa: E402


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def strings():
    out = subprocess.run(
        ["node", "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                       "eval(require('fs').readFileSync(process.argv[2],'utf8'));"
                       "process.stdout.write(JSON.stringify(window.STRINGS))",
         str(ROOT / "js" / "strings.js"), str(ROOT / "js" / "learn-strings.js")],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def lookup(tree, key):
    for part in key.split("."):
        tree = tree[part]
    return tree


class GeneratedTest(unittest.TestCase):
    def test_generated_files_are_up_to_date(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_formacion.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_published_with_the_site(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_site
        for rel in list(PAGES) + ["js/learn.js", "js/learn-strings.js"]:
            self.assertIn(rel, build_site.STATIC_FILES)
        locs = re.findall(r"<loc>([^<]+)</loc>", read("sitemap.xml"))
        self.assertLessEqual(set(PAGES.values()), set(locs))


def visible_words(page):
    """Words of <main> a visitor sees on load: closed disclosures count only their summary."""
    main = re.search(r"<main.*?</main>", page, re.S).group(0)
    main = re.sub(r'<span class="sr-only">.*?</span></span>', " ", main, flags=re.S)
    main = re.sub(r"<details(?![^>]*\bopen\b)[^>]*>(.*?)</details>",
                  lambda m: re.search(r"<summary.*?</summary>", m.group(1), re.S).group(0), main, flags=re.S)
    main = re.sub(r"<(option|textarea)[^>]*>.*?</\1>", " ", main, flags=re.S)
    return len(html.unescape(re.sub(r"<[^>]+>", " ", main)).split())


class SecondIterationTest(unittest.TestCase):
    """Mission 02: less explanation, more visual evidence, same information."""

    def test_hub_shows_much_less_text_on_load(self):
        # First iteration: 1,383 visible words. Target of the mission: 30 to 40 % less (at most about 970).
        self.assertLessEqual(visible_words(read("formacion/index.html")), 970)

    def test_hub_structure(self):
        hub = read("formacion/index.html")
        self.assertEqual(re.findall(r'<li class="learn-goal learn-goal-(\w+)"><a href="([^"]+)"', hub),
                         [("piano", "piano/"), ("composicion", "composicion/"), ("produccion", "produccion-musical/"),
                          ("armonia", "#armonia"), ("carrera", "#carrera")])
        self.assertEqual(re.findall(r'<li class="learn-block[^"]*" id="(\w+)">', hub), C.AREAS)
        self.assertEqual(len(re.findall(r'<ul class="learn-skills"[^>]*>(?:<li[^>]*>[^<]+</li>){3}</ul>', hub)), 5)
        self.assertEqual(hub.count('<details class="learn-q">'), 5)
        self.assertEqual(len(re.findall(r'<ol class="learn-principles">(?:<li>.*?</li>){3}</ol>', hub)), 1)
        self.assertEqual(re.findall(r'<li id="(\w+)"><h3', hub), ["presencial", "online", "mentorias"])
        # Hero: the two actions of the brief, in order.
        actions = re.search(r'<section class="learn-hero.*?</section>', hub, re.S).group(0)
        self.assertEqual(re.findall(r'class="learn-button[^"]*" href="([^"]+)"', actions), ["#empezar", "#consulta"])

    def test_detail_is_kept_in_disclosures_and_subpages(self):
        hub = read("formacion/index.html")
        for a in ("armonia", "carrera"):
            block = re.search(rf'<li class="learn-block[^"]*" id="{a}">.*?</li></ul>', hub, re.S)
            self.assertIsNotNone(block, a)
            for item in C.L["hub"]["areas"][a]["learn"]:
                self.assertIn(html.escape(item[0], quote=False), hub)
        for key, slug in C.AREA_PAGES.items():
            page = read(f"formacion/{slug}/index.html")
            stages = C.L["pages"][key]["plan"]
            self.assertEqual(page.count('<details class="learn-stage"'), len(stages))
            self.assertEqual(page.count('<details class="learn-stage" open>'), 1)
            for _, items in stages:
                for item in items:
                    self.assertIn(html.escape(item[0], quote=False), page)

    def test_photographs_are_real_optimised_and_published(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_site
        for rel in PAGES:
            page = read(rel)
            imgs = re.findall(r"<img [^>]+>", re.search(r"<main.*?</main>", page, re.S).group(0))
            with self.subTest(page=rel):
                self.assertTrue(imgs or "data-photo-pending=" in page)
                for i, tag in enumerate(imgs):
                    self.assertRegex(tag, r'width="\d+" height="\d+"')
                    self.assertIn('alt=', tag)
                    self.assertIn('fetchpriority="high"' if i == 0 else 'loading="lazy"', tag)
        for key, photo in C.PHOTOS.items():
            if not photo:
                continue
            path = ROOT / photo["src"]
            with self.subTest(photo=key):
                self.assertIn(photo["src"], build_site.STATIC_FILES)
                self.assertLess(path.stat().st_size, 250 * 1024)
        # Areas without a photograph show a typographic composition that says what is missing.
        hub = read("formacion/index.html")
        pending = [k for k, v in C.PHOTOS.items() if v is None]
        self.assertEqual(len(re.findall(r"data-photo-pending=", hub)), len(pending))

    def test_commercial_terms_wait_for_approval(self):
        self.assertFalse(C.COMMERCIAL["published"], "publishing fees needs Luis's approval and new tests")
        self.assertEqual(C.COMMERCIAL["fees"], {"piano": 40, "armonia": 45, "composicion": 45, "produccion": 45, "mentoria": 50})

    def test_enquiry_form_fields_and_mode(self):
        hub = read("formacion/index.html")
        form = re.search(r'<form id="learn-form".*?</form>', hub, re.S).group(0)
        self.assertEqual(re.findall(r'<(?:select|input|textarea) id="learn-(\w+)"', form),
                         ["area", "level", "format", "name", "email", "message", "website"])
        if C.ENQUIRY_ENDPOINT:
            self.assertRegex(C.ENQUIRY_ENDPOINT, r"^https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec$")
            self.assertIn(f'data-endpoint="{C.ENQUIRY_ENDPOINT}"', form)
        else:
            self.assertNotIn("data-endpoint", form)
            self.assertIn('data-i18n="learn.form.prepare"', form)

    @unittest.skipUnless(NODE, "node not installed")
    def test_enquiry_backend_proposal(self):
        out = subprocess.run([NODE, str(ENQUIRY_SCENARIOS)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        results = json.loads(out.stdout)
        self.assertGreaterEqual(len(results), 9)
        self.assertEqual({k: v for k, v in results.items() if v != "ok"}, {})
        # The proposal is never published with the site.
        sys.path.insert(0, str(ROOT / "tools"))
        import build_site
        self.assertFalse([f for f in build_site.allowlist() if f.startswith("apps-script")])


class PlayerTest(unittest.TestCase):
    """Mission 03: the Formación pages use the one global player exactly like the rest of the site."""

    def test_same_mini_player_and_engine_as_the_other_pages(self):
        about = read("sobre-mi.html")
        bar = lambda page: re.sub(r'href="[^"]*"|aria-label="[^"]*"|>[^<]*<', "", re.search(r'<div id="mini-player".*?(?=<script)', page, re.S).group(0))
        for rel in PAGES:
            page = read(rel)
            with self.subTest(page=rel):
                self.assertEqual(bar(page), bar(about))
                scripts = re.findall(r'<script src="(?:\.\./)*js/([\w-]+\.js)"></script>', page)
                self.assertLess(scripts.index("music-data.js"), scripts.index("player.js"))
                self.assertEqual(scripts.count("player.js"), 1)
                self.assertNotIn("<audio", page)
        self.assertNotIn("Audio(", read("js/learn.js"))
        self.assertNotIn("LGPlayer", read("js/learn.js"))


class StaticPagesTest(unittest.TestCase):
    def test_seo_metadata(self):
        titles = set()
        for rel, url in PAGES.items():
            page = read(rel)
            with self.subTest(page=rel):
                self.assertTrue(page.startswith('<!doctype html>\n<html lang="es" data-lang-default="es">'))
                self.assertEqual(re.findall(r'<link rel="canonical" href="([^"]+)">', page), [url])
                title = re.search(r"<title[^>]*>(.*?)</title>", page).group(1)
                desc = re.search(r'<meta name="description" content="([^"]+)">', page).group(1)
                self.assertIn("Valencia", title)
                self.assertLessEqual(len(html.unescape(title)), 75)
                self.assertTrue(120 <= len(html.unescape(desc)) <= 165, len(desc))
                self.assertIn(f'<meta property="og:url" content="{url}">', page)
                self.assertEqual(len(re.findall(r"<h1[ >]", page)), 1)
                titles.add(title)
        self.assertEqual(len(titles), len(PAGES))

    def test_structured_data(self):
        for rel, url in PAGES.items():
            blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', read(rel))]
            with self.subTest(page=rel):
                service = next(b for b in blocks if b["@type"] == "Service")
                self.assertEqual(service["url"], url)
                self.assertEqual(service["provider"]["@id"], SITE + "#person")
                self.assertEqual(service["areaServed"]["name"], "Valencia")
                self.assertNotIn("offers", json.dumps(service).replace("OfferCatalog", "").replace('"Offer"', ""))
                self.assertNotIn("price", json.dumps(blocks).lower())
                self.assertNotIn("address", json.dumps(blocks).lower())
                if rel != "formacion/index.html":
                    crumbs = next(b for b in blocks if b["@type"] == "BreadcrumbList")
                    self.assertEqual(crumbs["itemListElement"][-1]["item"], url)

    def test_static_spanish_text_matches_strings(self):
        es = strings()["es"]
        for rel in PAGES:
            page = read(rel)
            with self.subTest(page=rel):
                for key, text in re.findall(r'data-i18n="(learn\.[\w.]+)"[^>]*>((?:[^<]|<em>[^<]*</em>)*)<', page):
                    if not text:
                        continue
                    self.assertEqual(html.unescape(text.replace("<em>", "").replace("</em>", "")), lookup(es, key), key)

    def test_both_languages_cover_every_key(self):
        data = strings()

        def keys(tree, prefix=""):
            return {prefix + k if not isinstance(v, dict) else x
                    for k, v in tree.items() for x in ([prefix + k] if not isinstance(v, dict) else keys(v, prefix + k + "."))}
        self.assertEqual(keys(data["en"]["learn"]), keys(data["es"]["learn"]))

    @staticmethod
    def without_approved_plans(rel, text):
        """The class plans (prices, renewal, cancellation, 24 h rule, venue) were approved by Luis in Mission 06 and are
        checked by tests/test_billing.py; every other wording rule below still applies to the rest of the content."""
        if rel.endswith(".html"):
            return re.sub(r'<section id="planes".*?</section>', "", text, flags=re.S)
        start = text.index("var L=") + len("var L=")
        tree, end = json.JSONDecoder().raw_decode(text, start)
        for lang in tree.values():
            for key in ("plans", "students", "legalNote"):
                lang.pop(key, None)
        return text[:start] + json.dumps(tree, ensure_ascii=False) + text[end:]

    def test_editorial_guard_rails(self):
        texts = [self.without_approved_plans(rel, read(rel)) for rel in list(PAGES) + ["js/learn-strings.js"]]
        for text in texts:
            self.assertNotIn("—", text)
            for pattern in FORBIDDEN:
                self.assertIsNone(re.search(pattern, text, re.I), pattern)
        hub = read("formacion/index.html")
        # The master's degree is presented as what it is: music business, not performance or pedagogy.
        self.assertIn("máster en Global Entertainment and Music Business por Berklee College of Music", hub)
        self.assertIn("Licenciatura en Producción Musical (REC Música)", hub)
        self.assertNotRegex(hub, r"(?i)máster en (?:interpretación|piano|jazz|pedagog)")

    def test_enquiry_form_is_accessible_and_has_no_backend(self):
        hub = read("formacion/index.html")
        form = re.search(r'<form id="learn-form".*?</form>', hub, re.S).group(0)
        self.assertNotIn("action=", form)
        self.assertNotIn('method="post"', form.lower())
        for field in re.findall(r'<(?:select|textarea|input) id="([\w-]+)"', form):
            self.assertIn(f'<label for="{field}"', form, field)
        self.assertEqual(form.count("<fieldset"), form.count("<legend"))
        self.assertIn('role="alert"', form)
        self.assertNotRegex(form, r"<button(?![^>]*type=\")")

    def test_internal_links_reach_the_section(self):
        self.assertIn('<a href="formacion/"><span data-i18n="contact.lessons">', read("index.html"))
        for rel in ("index.html", "cv.html", "sobre-mi.html", "music/index.html", "agenda/index.html"):
            self.assertRegex(read(rel), r'href="(?:\.\./)?formacion/" data-section="lessons" data-i18n="nav.lessons"', rel)


@unittest.skipUnless(NODE, "node not installed")
class LanguageTest(unittest.TestCase):
    def run_scenario(self, body):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), body], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_spanish_page_stays_spanish_for_an_english_browser_arriving_directly(self):
        out = self.run_scenario(
            "const page = browser.tab().open('formacion/index.html', {languages: ['en-US']}); await settle();"
            "out.lang = page.document.documentElement.lang; out.h1 = page.$('h1').innerHTML;"
            "out.nav = page.$('a[data-section=\"lessons\"]').textContent;")
        self.assertEqual(out["lang"], "es")
        self.assertEqual(out["nav"], "Clases")
        self.assertIn("<em>haciendo</em>", out["h1"])

    def test_visitor_browsing_in_english_keeps_english(self):
        out = self.run_scenario(
            "const tab = browser.tab(); tab.open('index.html', {languages: ['en-US']}); await settle();"
            "const page = tab.open('formacion/piano/index.html', {languages: ['en-US']}); await settle();"
            "out.lang = page.document.documentElement.lang; out.h1 = page.$('h1').innerHTML;"
            "out.crumb = page.$('.learn-crumbs [aria-current]').textContent;")
        self.assertEqual(out["lang"], "en")
        self.assertEqual(out["h1"], "<em>Piano</em> lessons.")
        self.assertEqual(out["crumb"], "Piano")

    def test_manual_choice_wins(self):
        out = self.run_scenario(
            "browser.local['lg-language'] = 'en'; browser.local['lg-language-manual'] = '1';"
            "const page = browser.tab().open('formacion/index.html', {languages: ['es-ES']}); await settle();"
            "out.lang = page.document.documentElement.lang; out.title = page.$('title').textContent;")
        self.assertEqual(out["lang"], "en")
        self.assertTrue(out["title"].startswith("Piano, songwriting and music production lessons"))

    def test_english_pages_still_follow_the_browser(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html', {languages: ['es-ES']}); await settle();"
            "out.lang = page.document.documentElement.lang;"
            "const en = browser.tab().open('index.html', {languages: ['en-GB']}); await settle();"
            "out.en = en.document.documentElement.lang;")
        self.assertEqual((out["lang"], out["en"]), ("es", "en"))


if __name__ == "__main__":
    unittest.main()
