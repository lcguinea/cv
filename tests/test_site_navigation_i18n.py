#!/usr/bin/env python3
"""Focused tests for the shared header, mobile menu, theme switch, active navigation and i18n of Home,
CV and Music, plus the editorial copy rules (no em dashes, no unused strings).

Static checks always run. Behaviour checks run the real pages in tests/support/minidom.js and need
Node.js. Standard library only.

Run: python3 -m unittest tests/test_site_navigation_i18n.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
STRINGS_JS = ROOT / "js" / "strings.js"
NODE = shutil.which("node")
PAGES = {"index.html": "home", "cv.html": "cv", "music/index.html": "music"}
NAV_KEYS = ["nav.research", "nav.experience", "nav.music", "nav.cv", "nav.contact"]
NAV_HREFS = {
    "home": ["#writing", "#experience", "music/", "cv.html", "#contact"],
    "cv": ["./#writing", "./#experience", "music/", "cv.html", "./#contact"],
    "music": ["../#writing", "../#experience", "./", "../cv.html", "../#contact"],
}
CURRENT = {"home": None, "cv": "nav.cv", "music": "nav.music"}
PUBLISHED_JS = ("strings.js", "i18n.js", "site.js", "player.js", "music-page.js", "theme-init.js")
# Keys built at runtime from data: 'music.role'+credit and 'music.type'+release type.
DYNAMIC_PREFIXES = ("music.role", "music.type")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def strings():
    result = subprocess.run(
        [NODE, "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                     "process.stdout.write(JSON.stringify(window.STRINGS))", str(STRINGS_JS)],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def flatten(tree, prefix=""):
    out = {}
    for key, value in tree.items():
        path = prefix + key
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


def header(html):
    return re.search(r'<header class="site-header[^"]*">.*?</header>', html, re.S).group(0)


class HeaderStaticTests(unittest.TestCase):
    def test_every_page_shares_the_same_header_and_primary_navigation(self):
        shapes = set()
        for rel, page in PAGES.items():
            block = header(read(rel))
            with self.subTest(page=page):
                nav = re.search(r'<nav class="nav" aria-label="Primary" data-i18n-label="ui.primaryNav">(.*?)</nav>', block).group(1)
                links = re.findall(r'<a href="([^"]+)"( aria-current="page")? data-i18n="([^"]+)">', nav)
                self.assertEqual([k for _, _, k in links], NAV_KEYS)
                self.assertEqual([h for h, _, _ in links], NAV_HREFS[page])
                current = [k for _, cur, k in links if cur]
                self.assertEqual(current, [CURRENT[page]] if CURRENT[page] else [])
                self.assertIn('<button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-menu" data-i18n="ui.menu">', block)
                self.assertIn('<div class="site-menu" id="site-menu">', block)
                self.assertIn('data-theme-choice="light" aria-pressed="true" data-i18n="ui.light"', block)
                self.assertIn('data-theme-choice="dark" aria-pressed="false" data-i18n="ui.dark"', block)
                self.assertNotRegex(block, r"<button(?![^>]*type=\"button\")")
            # Same structure everywhere once page-specific paths, brand suffix and CV print button are removed.
            shape = re.sub(r'href="[^"]*"| aria-current="page"|<span> / \w+</span>|<button type="button" class="print-button".*?</button>| no-print', "", block)
            shapes.add(shape)
        self.assertEqual(len(shapes), 1)

    def test_theme_is_restored_in_head_before_the_stylesheet(self):
        for rel in PAGES:
            html = read(rel)
            head = html[:html.index("</head>")]
            with self.subTest(page=rel):
                init = re.search(r'<script src="(?:\.\./)?js/theme-init\.js"></script>', head)
                css = re.search(r'<link rel="stylesheet" href="(?:\.\./)?css/styles\.css">', head)
                self.assertTrue(init and css and init.start() < css.start())
        init = read("js/theme-init.js")
        self.assertIn("localStorage.getItem('lg-theme')==='dark'", init)
        self.assertIn("classList.add('js')", init)

    def test_sticky_header_scroll_margin_and_touch_targets(self):
        css = read("css/styles.css")
        self.assertIn(".site-header{position:sticky;top:0;", css)
        self.assertIn("main [id]{scroll-margin-top:5rem}", css)
        self.assertIn(".tools button{border:0;min-width:44px;min-height:44px;", css)
        self.assertIn(".nav a{display:inline-flex;align-items:center;min-height:44px;", css)
        self.assertIn("html.js .menu-toggle{display:inline-flex;align-items:center;margin-left:auto;min-height:44px;min-width:44px;", css)
        self.assertIn(".nav a[aria-current]{border-bottom-color:var(--accent)}", css)

    def test_desktop_header_wraps_its_tools_instead_of_overflowing(self):
        # Between the mobile breakpoint and about 1060px the brand, navigation and tools (the CV print button
        # and the longer Spanish labels) do not fit on one line; the tools drop to a second line instead.
        css = read("css/styles.css")
        self.assertIn("@media(min-width:701px){.site-menu{flex-wrap:wrap;row-gap:0;justify-content:flex-end}}", css)
        self.assertIn("html.js.menu-open .site-menu{display:flex;flex-direction:column;align-items:stretch;flex-wrap:nowrap;", css)


@unittest.skipUnless(NODE, "node not installed")
class StringsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = strings()
        cls.en, cls.es = flatten(data["en"]), flatten(data["es"])

    def used_keys(self):
        used = set()
        code = [read("js/" + name) for name in PUBLISHED_JS if (ROOT / "js" / name).is_file()]
        for rel in PAGES:
            html = read(rel)
            used |= set(re.findall(r'data-i18n(?:-label|-placeholder)?="([\w.]+)"', html))
            code += re.findall(r"<script>(.*?)</script>", html, re.S)
        for source in code:
            used |= {m for m in re.findall(r"'([a-z]+\.[A-Za-z]+)'", source) if m in self.en}
        return used

    def test_both_languages_have_the_same_non_empty_keys(self):
        self.assertEqual(set(self.en), set(self.es))
        for key in self.en:
            self.assertTrue(self.en[key].strip() and self.es[key].strip(), key)

    def test_every_used_key_exists_and_every_key_is_used(self):
        used = self.used_keys()
        self.assertLessEqual(used, set(self.en))
        unused = {k for k in set(self.en) - used if not k.startswith(DYNAMIC_PREFIXES)}
        self.assertEqual(unused, set())

    def test_editorial_decisions(self):
        self.assertEqual((self.en["facets.title"], self.es["facets.title"]), ("What I do", "Lo que hago"))
        for gone in ("facets.intro", "hero.imageNote", "hero.selected", "music.topNote", "experience.independent"):
            self.assertNotIn(gone, self.en)
        self.assertEqual(self.en["writing.title"], "What streaming data says about how artists grow.")
        self.assertEqual(self.es["music.title"], "Lanzamientos como artista y productor, 2020–2024.")
        self.assertEqual(self.es["skills.music"], "producción, composición, arreglos, dirección musical.")
        self.assertNotIn("pool de", self.es["writing.a1"])
        self.assertFalse([k for k, v in self.es.items() if k.startswith("music.") and "preview" in v.lower()])
        # The long CV profile stays as it is in CV_MASTER.md.
        self.assertTrue(self.en["cv.profileText"].startswith("I work where creative and analytical thinking meet."))

    def test_no_em_dash_in_published_copy(self):
        for rel in list(PAGES) + ["js/" + n for n in PUBLISHED_JS if (ROOT / "js" / n).is_file()]:
            with self.subTest(file=rel):
                self.assertNotIn("—", read(rel))


class HomeContentTests(unittest.TestCase):
    def test_the_fifth_medium_article_from_cv_master_is_on_the_home_page(self):
        master = read("CV_MASTER.md")
        section = master[master.index("### 4.5"):master.index("### Also on Medium")]
        title = re.search(r"### 4\.5 (.+)", section).group(1).strip()
        url = re.search(r"- URL: (\S+)", section).group(1)
        html = read("index.html")
        self.assertIn(f'<h3 id="a5-title" lang="es">{title}</h3>', html)
        self.assertIn(f'href="{url}"', html)
        self.assertEqual(len(re.findall(r'href="https://medium\.com/@soyluisguinea/[^"]+"', html)), 5)

    def test_removed_hero_note_and_facets_intro(self):
        html = read("index.html")
        for gone in ("hero.imageNote", "hero.selected", "facets.intro", "image-note"):
            self.assertNotIn(gone, html)


@unittest.skipUnless(NODE, "node not installed")
class NavigationBehaviourTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_mobile_menu_opens_closes_with_escape_and_returns_focus(self):
        out = self.run_scenario(
            "const page = browser.tab().open('cv.html'); await settle();"
            "const button = page.$('.menu-toggle'), root = page.document.documentElement;"
            "const view = () => ({expanded: button.getAttribute('aria-expanded'), open: root.classList.contains('menu-open'),"
            "  focus: page.document.activeElement && (page.document.activeElement.getAttribute('data-i18n') || page.document.activeElement.className)});"
            "out.start = view(); page.click(button); out.open = view();"
            "page.key('Escape'); out.closed = view();"
            "page.click(button); page.click(page.$('.nav a[data-i18n=\"nav.music\"]')); out.link = view();"
            "out.js = root.classList.contains('js');"
        )
        self.assertEqual(out["start"], {"expanded": "false", "open": False, "focus": None})
        self.assertEqual(out["open"], {"expanded": "true", "open": True, "focus": "nav.research"})
        self.assertEqual(out["closed"], {"expanded": "false", "open": False, "focus": "ui.menu"})
        self.assertEqual((out["link"]["expanded"], out["link"]["open"]), ("false", False))
        self.assertTrue(out["js"])

    def test_theme_buttons_show_state_persist_and_restore_before_scripts(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const pressed = p => p.$$('[data-theme-choice]').map(b => b.dataset.themeChoice + ':' + b.getAttribute('aria-pressed'));"
            "out.a = pressed(page); page.click('[data-theme-choice=\"dark\"]');"
            "out.b = [pressed(page), page.document.documentElement.dataset.theme, browser.local['lg-theme']];"
            "const next = browser.tab().open('music/index.html'); await settle();"
            "out.c = [pressed(next), next.document.documentElement.dataset.theme];"
            "next.click('[data-lang=\"es\"]'); out.labels = next.$$('[data-theme-choice]').map(b => b.textContent);"
            "next.click('[data-theme-choice=\"light\"]'); out.d = [pressed(next), next.document.documentElement.dataset.theme || '', browser.local['lg-theme']];"
        )
        self.assertEqual(out["a"], ["light:true", "dark:false"])
        self.assertEqual(out["b"], [["light:false", "dark:true"], "dark", "dark"])
        self.assertEqual(out["c"], [["light:false", "dark:true"], "dark"])
        self.assertEqual(out["labels"], ["Claro", "Oscuro"])
        self.assertEqual(out["d"], [["light:true", "dark:false"], "", "light"])

    def test_language_switch_translates_navigation_and_labels(self):
        out = self.run_scenario(
            "const page = browser.tab().open('music/index.html'); await settle(); page.click('[data-lang=\"es\"]'); await settle();"
            "out.nav = page.$$('.nav a').map(a => a.textContent);"
            "out.label = page.$('.nav').getAttribute('aria-label'); out.menu = page.$('.menu-toggle').textContent;"
            "out.groups = page.$$('.tool-group').map(g => g.getAttribute('aria-label'));"
            "out.lang = page.document.documentElement.lang; out.stored = browser.local['lg-language'];"
            "const cv = browser.tab().open('cv.html'); await settle(); out.cv = cv.$$('.nav a').map(a => a.textContent);"
        )
        self.assertEqual(out["nav"], ["Investigación", "Experiencia", "Música", "CV", "Contacto"])
        self.assertEqual((out["label"], out["menu"]), ("Principal", "Menú"))
        self.assertEqual(out["groups"], ["Idioma", "Tema"])
        self.assertEqual((out["lang"], out["stored"]), ("es", "es"))
        self.assertEqual(out["cv"], out["nav"])

    def test_home_marks_the_section_under_the_header_as_current(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const sections = page.$$('main > section'); const header = page.$('.site-header'); header.rect.height = 60;"
            "const scrollTo = id => { let top = -5000; sections.forEach(s => { s.rect.top = top; top += 1000; });"
            "  const target = sections.find(s => s.id === id); const shift = target.rect.top - 100;"
            "  sections.forEach(s => { s.rect.top -= shift; }); page.window._fire('scroll'); };"
            "const current = () => page.$$('.nav a[aria-current]').map(a => a.getAttribute('href') + ':' + a.getAttribute('aria-current'));"
            "for (const id of ['writing', 'facets', 'experience', 'contact']) { scrollTo(id); await settle(); out[id] = current(); }"
        )
        self.assertEqual(out["writing"], ["#writing:true"])
        self.assertEqual(out["facets"], [])
        self.assertEqual(out["experience"], ["#experience:true"])
        self.assertEqual(out["contact"], ["#contact:true"])



def css_tokens(css):
    """Colour tokens of the light (:root) and dark (:root[data-theme=dark]) themes."""
    light = dict(re.findall(r"--([a-z]+):(#[0-9a-f]{3,6})", re.search(r":root\{([^}]*)\}", css).group(1)))
    dark = dict(light, **dict(re.findall(r"--([a-z]+):(#[0-9a-f]{3,6})", re.search(r":root\[data-theme=dark\]\{([^}]*)\}", css).group(1))))
    return light, dark


def contrast(a, b):
    def lum(color):
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        def channel(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b_ = (channel(int(color[i:i + 2], 16)) for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class ProductionAuditCorrectionsTests(unittest.TestCase):
    """Regressions found by the production audit of b070039: contrast, playlist columns, Music title,
    volume value format, English fragments marked as English, and the corrected copy."""

    def resolve(self, value, tokens):
        m = re.fullmatch(r"var\(--([a-z]+)\)", value)
        return tokens[m.group(1)] if m else value

    def test_small_labels_on_inverted_and_accent_surfaces_reach_aa(self):
        css = read("css/styles.css")
        light, dark = css_tokens(css)
        screen = css[:css.index("@media print")]
        kicker = re.search(r"\.contact \.kicker\{color:([^}]+)\}", screen).group(1)
        kicker_dark = re.search(r":root\[data-theme=dark\] \.contact \.kicker\{color:([^}]+)\}", screen).group(1)
        # The contact section inverts the theme: its background is the theme's text colour.
        self.assertGreaterEqual(contrast(self.resolve(kicker, light), light["ink"]), 4.5)
        self.assertGreaterEqual(contrast(self.resolve(kicker_dark, dark), dark["text"]), 4.5)
        # The dark article card is ink in both themes.
        self.assertRegex(screen, r"\.writing-dark p,\.writing-dark \.metric,\.writing-dark \.article-index\{color:var\(--mist\)\}")
        self.assertGreaterEqual(contrast(light["mist"], light["ink"]), 4.5)
        # Text on the accent band.
        facets = re.search(r"\.facets-section\{background:var\(--accent\);color:([^;]+);", screen).group(1)
        labels = re.search(r"\.facets-section \.kicker,\.facets-section \.section-intro\{color:([^}]+)\}", screen).group(1)
        for value in (facets, labels):
            self.assertGreaterEqual(contrast(self.resolve(value, light), light["accent"]), 4.5)
        # Print keeps the dark-on-white muted colour for the labels that changed.
        self.assertIn(".contact .kicker,.writing-dark .article-index{color:var(--muted)}", css[css.index("@media print"):])

    def test_playlist_columns_do_not_depend_on_the_number_of_platform_links(self):
        css = read("css/styles.css")
        self.assertIn(".playlist{display:grid;grid-template-columns:minmax(0,1fr) auto}", css)
        self.assertIn(".playlist li{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-columns:subgrid;", css)
        self.assertIn("@media(max-width:700px){.playlist{display:block}", css)
        # A shared column must not squeeze "Apple Music" onto two lines.
        self.assertIn(".pl-links .platform-link{color:var(--muted);white-space:nowrap}", css)

    def test_english_fragments_kept_in_the_spanish_interface_are_marked_as_english(self):
        home, cv = read("index.html"), read("cv.html")
        # The descriptor and the titles with a Spanish edition follow the page language; only the
        # English-only and Spanish-only studies carry a fixed lang.
        self.assertIn('<p class="descriptor" data-i18n="hero.title">', home)
        for n in "134":
            self.assertIn(f'<h3 id="a{n}-title" data-i18n="writing.a{n}Title">', home)
        self.assertIn('<h3 id="a2-title" lang="en">Are We Measuring Artist Growth Wrong?</h3>', home)
        self.assertIn('<h3 id="a5-title" lang="es">', home)
        self.assertIn('<span data-i18n="education.ma">MA</span>, <span lang="en">Global Entertainment and Music Business</span>', home)
        self.assertIn('<span class="cv-degree" lang="en" data-i18n="cv.maField">Global Entertainment and Music Business</span>', cv)

    def test_music_title_is_a_translated_string(self):
        self.assertIn('<title data-i18n="music.pageTitle">Music / Audio · Luis Guinea</title>', read("music/index.html"))
        # The section name in the brand mark stays MUSIC, like / CV and / 01.
        self.assertIn('LUIS GUINEA<span> / MUSIC</span>', read("music/index.html"))

    @unittest.skipUnless(NODE, "node not installed")
    def test_corrected_copy(self):
        data = strings()
        en, es = flatten(data["en"]), flatten(data["es"])
        self.assertTrue(en["writing.a4"].startswith("A study with Chartmetric data "))
        self.assertTrue(es["writing.a4"].startswith("Un estudio con datos de Chartmetric "))
        self.assertIn("19 artistas emergentes", es["writing.a2"])
        self.assertIn("casos de estudio", es["skills.research"])
        self.assertIn("planificación de lanzamientos", es["skills.industry"])
        self.assertEqual((en["music.pageTitle"], es["music.pageTitle"]), ("Music / Audio · Luis Guinea", "Música / Audio · Luis Guinea"))
        self.assertEqual((en["player.percent"], es["player.percent"]), ("{n}%", "{n} %"))
        self.assertEqual((en["education.ma"], es["education.ma"]), ("MA", "Máster"))
        # Left for an editorial decision.
        self.assertEqual(en["ui.footerPlaces"], "Valencia / Mexico City")

    @unittest.skipUnless(NODE, "node not installed")
    def test_title_and_volume_value_follow_the_language(self):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT),
            "const page = browser.tab().open('music/index.html'); await settle();"
            "const v = () => [page.$('#np-volume').getAttribute('aria-valuetext'), page.$('#mp-volume').getAttribute('aria-valuetext')];"
            "out.en = [page.$('title').textContent, ...v()];"
            "page.click('[data-lang=\"es\"]'); await settle(); out.es = [page.$('title').textContent, ...v()];"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = [page.$('title').textContent, ...v()];"
            "const home = browser.tab().open('index.html'); await settle(); home.click('[data-lang=\"es\"]'); await settle();"
            "out.home = [home.$('.descriptor').closest('[lang]').getAttribute('lang'), home.$('[data-i18n=\"education.ma\"]').parentNode.textContent];"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["en"], ["Music / Audio · Luis Guinea", "100%", "100%"])
        self.assertEqual(out["es"], ["Música / Audio · Luis Guinea", "100 %", "100 %"])
        self.assertEqual(out["back"], out["en"])
        self.assertEqual(out["home"][0], "es")
        self.assertTrue(out["home"][1].startswith("Máster, Global Entertainment and Music Business"), out["home"][1])


SKILLS = {
    "en": {
        "instrumentsLabel": "Multi-instrumentalist",
        "instruments": ("piano", "keyboards", "synthesizers", "drums", "percussion", "guitar", "bass", "flute", "accordion", "trumpet"),
    },
    "es": {
        "instrumentsLabel": "Multiinstrumentista",
        "instruments": ("piano", "teclados", "sintetizadores", "batería", "percusiones", "guitarra", "bajo", "flauta", "acordeón", "trompeta"),
    },
}
SOFTWARE = ("Pro Tools", "Logic Pro X", "Ableton Live", "Sibelius", "Final Cut Pro", "Photoshop", "Illustrator")
DATA_TOOLS = {
    "en": ("Python", "SQL", "ETL", "Chartmetric", "Power BI", "Tableau", "Excel", "Google Analytics",
           "AWS\u00a0(EC2)", "Next.js", "Supabase", "MCP servers"),
    "es": ("Python", "SQL", "ETL", "Chartmetric", "Power BI", "Tableau", "Excel", "Google Analytics",
           "AWS\u00a0(EC2)", "Next.js", "Supabase", "servidores MCP"),
}


@unittest.skipUnless(NODE, "node not installed")
class DescriptorAndCapabilitiesTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_descriptor_is_localised_only_in_spanish_and_follows_the_live_switch(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const d = () => [page.$('.descriptor').textContent, page.$('.descriptor').closest('[lang]').getAttribute('lang')];"
            "out.en = d(); page.click('[data-lang=\"es\"]'); await settle(); out.es = d();"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = d();"
            "browser.local['lg-language'] = 'es'; const fresh = browser.tab().open('index.html'); await settle();"
            "out.load = fresh.$('.descriptor').textContent;")
        self.assertEqual(out["en"], ["Creative × Analytical × Entrepreneurial", "en"])
        self.assertEqual(out["es"], ["Creativo × Analítico × Emprendedor", "es"])
        self.assertEqual(out["back"], out["en"])
        self.assertEqual(out["load"], "Creativo × Analítico × Emprendedor")

    def test_instruments_and_software_are_listed_apart_in_both_languages_on_home_and_cv(self):
        out = self.run_scenario(
            "const read = (page, scope, ns) => Object.fromEntries(['data', 'music', 'instruments', 'software'].flatMap(k => ["
            "  [k + 'Label', page.$(scope + ' [data-i18n=\"' + ns + '.' + k + 'Label\"]').textContent],"
            "  [k, page.$(scope + ' [data-i18n=\"' + ns + '.' + k + '\"]').textContent]]));"
            "const home = browser.tab().open('index.html'); await settle(); const cv = browser.tab().open('cv.html'); await settle();"
            "out.en = {home: read(home, '.skills-block', 'skills'), cv: read(cv, '.cv-skills', 'cv')};"
            "home.click('[data-lang=\"es\"]'); cv.click('[data-lang=\"es\"]'); await settle();"
            "out.es = {home: read(home, '.skills-block', 'skills'), cv: read(cv, '.cv-skills', 'cv')};")
        for lang, expected in SKILLS.items():
            for page in ("home", "cv"):
                got = out[lang][page]
                with self.subTest(lang=lang, page=page):
                    self.assertEqual(got["instrumentsLabel"].rstrip(":"), expected["instrumentsLabel"])
                    instruments = got["instruments"].lower()
                    for name in expected["instruments"]:
                        self.assertRegex(instruments, r"\b%s\b" % name)
                    for name in SOFTWARE:
                        self.assertIn(name, got["software"])
                        # Software stays out of the instrument and music lines.
                        self.assertNotIn(name, got["instruments"] + got["music"])
                    for name in expected["instruments"]:
                        self.assertNotIn(name, got["software"].lower())
                    # Data tools stay in their own category, apart from the music and visual software.
                    for name in DATA_TOOLS[lang]:
                        self.assertIn(name, got["data"])
                        self.assertNotIn(name, got["software"])
                    for name in SOFTWARE:
                        self.assertNotIn(name, got["data"])
        self.assertEqual(out["es"]["home"]["softwareLabel"], "Software musical y visual:")
        self.assertEqual(out["en"]["cv"]["softwareLabel"], "Music & visual software")

    def test_no_javascript_fallback_of_the_cv_matches_the_english_strings(self):
        data = strings()
        en = flatten(data["en"])
        cv = read("cv.html")
        for key in ("data", "music", "instrumentsLabel", "instruments", "softwareLabel", "software"):
            with self.subTest(key=key):
                text = en["cv." + key].replace("&", "&amp;")
                self.assertIn(f'<span data-i18n="cv.{key}">{text}</span>' if "Label" not in key
                              else f'<strong data-i18n="cv.{key}">{text}</strong>', cv)


if __name__ == "__main__":
    unittest.main()
