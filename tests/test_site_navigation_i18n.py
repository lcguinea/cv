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
PAGES = {"index.html": "home", "cv.html": "cv", "music/index.html": "music", "sobre-mi.html": "about"}
# Pages that share the site header (the booking page has its own content tests in tests/test_reservas.py).
HEADER_PAGES = dict(PAGES, **{"agenda/index.html": "agenda"})
# One menu on every page, written in the HTML (no link is added by JavaScript), in the reading order of Home
# (2026-10-13): Background with Experience and Education as secondary entries, Music with Film (2026-10-23) and Jingles (2026-10-24), Research, About, CV, Agenda
# (booking page, 2026-10-21), then Contact as the action. Home is reached through the brand.
NAV_KEYS = ["nav.background", "nav.experience", "nav.education", "nav.music", "nav.film", "nav.jingles", "nav.research", "nav.about", "nav.cv", "nav.agenda", "nav.contact"]
NAV_HREFS = {
    "home": ["#background", "#experience", "#education", "music/", "music/#film", "music/#jingles", "#writing", "sobre-mi.html", "cv.html", "agenda/", "#contact"],
    "cv": ["./#background", "./#experience", "./#education", "music/", "music/#film", "music/#jingles", "./#writing", "sobre-mi.html", "cv.html", "agenda/", "./#contact"],
    "about": ["./#background", "./#experience", "./#education", "music/", "music/#film", "music/#jingles", "./#writing", "sobre-mi.html", "cv.html", "agenda/", "./#contact"],
    "music": ["../#background", "../#experience", "../#education", "./", "#film", "#jingles", "../#writing", "../sobre-mi.html", "../cv.html", "../agenda/", "../#contact"],
    "agenda": ["../#background", "../#experience", "../#education", "../music/", "../music/#film", "../music/#jingles", "../#writing", "../sobre-mi.html", "../cv.html", "./", "../#contact"],
}
CURRENT = {"home": None, "cv": "nav.cv", "music": "nav.music", "about": "nav.about", "agenda": "nav.agenda"}
PUBLISHED_JS = ("strings.js", "i18n.js", "site.js", "player.js", "music-page.js", "agenda.js", "theme-init.js")
# Keys built at runtime from data: 'music.role'+credit and 'music.type'+release type.
# Genre and mood labels are looked up from the human-reviewed values in js/music-data.js.
DYNAMIC_PREFIXES = ("music.role", "music.type", "music.version", "music.genre_", "music.mood_")


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
    def test_navigation_is_plain_html_not_created_by_javascript(self):
        site = read("js/site.js")
        self.assertNotIn("createElement", site)
        self.assertNotIn("sobre-mi.html", site)

    def test_every_page_shares_the_same_header_and_primary_navigation(self):
        shapes = set()
        for rel, page in HEADER_PAGES.items():
            block = header(read(rel))
            with self.subTest(page=page):
                nav = re.search(r'<nav class="nav" aria-label="Primary" data-i18n-label="ui.primaryNav">(.*?)</nav>(.*?)<div class="tools">', block)
                links = re.findall(r'<a (?:class="nav-cta" )?href="([^"]+)"(?: data-section="[a-z]+")?( aria-current="page")? data-i18n="([^"]+)">', nav.group(1) + nav.group(2))
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
            shape = re.sub(r'href="[^"]*"| aria-current="page"|<span> / <span data-i18n="nav\.\w+">\w+</span></span>| no-print', "", block)
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
        self.assertIn("main [id]{scroll-margin-top:calc(var(--header-offset,4rem) + 1rem)}", css)
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
        used |= set(re.findall(r'data-i18n(?:-label|-placeholder)?="([\w.]+)"', read("sobre-mi.html")))
        used |= set(re.findall(r'data-i18n(?:-label|-placeholder)?="([\w.]+)"', read("agenda/index.html")))
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
        # /music/ header (2026-10-13): title, three-role tagline and "Selected Works", no explanatory paragraphs.
        self.assertEqual((self.en["music.title"], self.es["music.title"]), ("Music", "Música"))
        self.assertEqual((self.en["music.tagline"], self.es["music.tagline"]),
                         ("Composer · Producer · Artist", "Compositor · Productor · Artista"))
        self.assertEqual((self.en["music.playlist"], self.es["music.playlist"]), ("Selected Works", "Obras seleccionadas"))
        for gone in ("music.label", "music.intro", "music.profilesHeading", "music.profilesIntro"):
            self.assertNotIn(gone, self.en)
            self.assertNotIn(gone, self.es)
        self.assertEqual(self.es["skills.music"], "producción, composición, arreglos, dirección musical.")
        # /agenda/ headline (2026-10-21): the accent word is part of the title in both languages.
        self.assertEqual((self.en["agenda.title"], self.en["agenda.titleAccent"]), ("Let’s meet.", "meet."))
        self.assertEqual((self.es["agenda.title"], self.es["agenda.titleAccent"]), ("¡Conectemos!", "¡Conectemos!"))
        for lang in (self.en, self.es):
            self.assertIn(lang["agenda.titleAccent"], lang["agenda.title"])
        self.assertNotIn("pool de", self.es["writing.a1"])
        self.assertFalse([k for k, v in self.es.items() if k.startswith("music.") and "preview" in v.lower()])
        # The long CV profile stays as it is in CV_MASTER.md.
        self.assertTrue(self.en["cv.profileText"].startswith("I work where creative and analytical thinking meet."))

    def test_no_em_dash_in_published_copy(self):
        for rel in list(PAGES) + ["agenda/index.html"] + ["js/" + n for n in PUBLISHED_JS if (ROOT / "js" / n).is_file()]:
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

    def test_sacm_workshop_is_listed_in_education_apart_from_the_membership(self):
        html = read("index.html")
        # Same layout as the other entries: programme, then the linked institution and the years.
        name = "Sociedad de Autores y Compositores de México"
        programme = ('<span data-i18n="education.workshop">Workshop (TCSACM)</span>, '
                     '<span data-i18n="education.sacm">Scholarship recipient, 6th generation</span>')
        link = (f'<a class="entity-link" href="https://www.sacm.org.mx/" target="_blank" rel="noopener" lang="es">{name}'
                '<span class="sr-only" data-i18n="ui.newTab"> (opens in a new tab)</span></a>')
        section = re.search(r'data-i18n="education\.title".*?<ol>(.*?)</ol>', html, re.S).group(1)
        items = re.findall(r"<li>(.*?)</li>", section, re.S)
        order = ["Berklee College of Music", "REC Música", name, "Tec de Monterrey"]
        self.assertEqual(len(items), len(order))
        for item, expected in zip(items, order):
            self.assertIn(expected, item)
        workshop = items[2]
        for word in ("Member", "Miembro"):
            self.assertNotIn(word, workshop)
        # One year, August 2021 to July 2022 (confirmed by the owner); same date style as the other entries.
        self.assertEqual(workshop, f"{programme} <small>{link} / 2021–22</small>")
        cv = read("cv.html")
        entry = re.search(r'<div class="cv-education">(.*?)</div>', cv, re.S).group(1)
        entries = re.findall(r"<p>(.*?)</p>", entry, re.S)
        self.assertEqual(len(entries), len(order))
        for item, expected in zip(entries, order):
            self.assertIn(expected, item)
        self.assertEqual(entries[2], '<strong data-i18n="education.workshop">Workshop (TCSACM)</strong> '
                         '<span class="cv-degree" data-i18n="education.sacm">Scholarship recipient, 6th generation</span>'
                         f'<br><span>{link} · 2021 – 2022</span>')
        source = read("js/strings.js")
        self.assertIn("sacm:'Scholarship recipient, 6th generation'", source)
        self.assertIn("sacm:'Becado, 6.ª generación'", source)
        self.assertIn("workshop:'Workshop (TCSACM)'", source)
        self.assertIn("workshop:'Taller (TCSACM)'", source)


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
            "out.label = button.textContent; page.click(button); out.openLabel = button.textContent;"
            "page.click(page.$('.nav a[data-i18n=\"nav.music\"]')); out.link = view(); out.closedLabel = button.textContent;"
            "out.js = root.classList.contains('js');"
        )
        self.assertEqual(out["start"], {"expanded": "false", "open": False, "focus": None})
        self.assertEqual(out["open"], {"expanded": "true", "open": True, "focus": "nav.background"})
        self.assertEqual((out["label"], out["openLabel"], out["closedLabel"]), ("Menu", "Close", "Menu"))
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
        self.assertEqual(out["nav"], ["Trayectoria", "Experiencia", "Formación", "Música", "Cine", "Jingles", "Investigación", "Sobre mí", "CV", "Agenda"])
        self.assertEqual((out["label"], out["menu"]), ("Principal", "Menú"))
        self.assertEqual(out["groups"], ["Idioma", "Tema"])
        self.assertEqual((out["lang"], out["stored"]), ("es", "es"))
        self.assertEqual(out["cv"], out["nav"])

    def test_home_marks_the_section_under_the_header_as_current(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const parts = page.$$('main [data-nav]'); const header = page.$('.site-header'); header.rect.height = 60;"
            "const scrollTo = id => { let top = -5000; parts.forEach(s => { s.rect.top = top; top += 1000; });"
            "  const target = page.$('#' + id); const shift = target.rect.top - 100;"
            "  parts.forEach(s => { s.rect.top -= shift; }); page.window._fire('scroll'); };"
            "const current = () => page.$$('.site-header a[aria-current]').map(a => a.getAttribute('href') + ':' + a.getAttribute('aria-current'));"
            "for (const id of ['top', 'writing', 'facets', 'experience', 'education', 'skills', 'music', 'about', 'contact']) { scrollTo(id); await settle(); out[id] = current(); }"
        )
        # Every part of Home marks its menu entry; What I do, Education and Skills belong to Background.
        self.assertEqual(out["top"], [])
        self.assertEqual(out["writing"], ["#writing:location"])
        self.assertEqual(out["facets"], ["#background:location"])
        self.assertEqual(out["experience"], ["#background:location", "#experience:location"])
        self.assertEqual(out["education"], ["#background:location", "#education:location"])
        self.assertEqual(out["skills"], ["#background:location"])
        self.assertEqual(out["music"], ["music/:location"])
        self.assertEqual(out["about"], ["sobre-mi.html:location"])
        self.assertEqual(out["contact"], ["#contact:location"])



class DiscoveryTests(unittest.TestCase):
    """Home leads to every page and every page leads back: Background groups its parts, Music and About
    have a short section on Home, and the other pages end with a few contextual links."""

    def test_home_order_anchors_and_contextual_links(self):
        html = read("index.html")
        ids = re.findall(r'<section id="([a-z]+)"', html)
        self.assertEqual(ids, ["top", "background", "facets", "experience", "education", "music", "writing", "about", "contact"])
        kickers = re.findall(r'<section id="(background|music|writing|about|contact)".*?<p class="kicker">(\d\d) /', html, re.S)
        self.assertEqual(kickers, [("background", "01"), ("music", "02"), ("writing", "03"), ("about", "04"), ("contact", "05")])
        # Historical anchors still exist; Education and Skills have their own.
        for anchor in ("writing", "facets", "experience", "education", "skills", "contact"):
            self.assertIn(f'id="{anchor}"', html)
        self.assertIn('<a class="button" href="music/"><span data-i18n="hero.ctaMusic">', html)
        self.assertIn('<a class="button button-quiet" href="#background"><span data-i18n="hero.ctaBackground">', html)
        # The cue under the hero leads to the section right after it.
        self.assertIn('<div class="hero-bottom"><a href="#background" data-i18n="hero.scroll">', html)
        data = strings()
        self.assertEqual((data["en"]["hero"]["scroll"], data["es"]["hero"]["scroll"]),
                         ("Explore my background ↓", "Explorar mi trayectoria ↓"))
        index = re.search(r'<nav class="section-index"[^>]*>(.*?)</nav>', html).group(1)
        self.assertEqual(re.findall(r'href="([^"]+)"', index), ["#facets", "#experience", "#education", "#skills", "cv.html"])
        self.assertEqual(html.count('data-i18n="background.cvLink"'), 2)
        self.assertIn('<a class="text-link to-page" href="music/"><span data-i18n="featured.all">', html)
        self.assertIn('<a class="text-link to-page" href="sobre-mi.html"><span data-i18n="home.aboutLink">', html)

    def test_research_is_one_featured_study_and_four_compact_cards(self):
        html = read("index.html")
        section = re.search(r'<section id="writing".*?</section>', html, re.S).group(0)
        self.assertEqual(section.count('<article class="writing-feature">'), 1)
        cards = re.findall(r'<article class="writing-card">(.*?)</article>', section, re.S)
        self.assertEqual(len(cards), 4)
        for n, card in zip("2345", cards):
            with self.subTest(study=n):
                # Every study keeps its title, one-line summary, figure and link to the full publication.
                self.assertIn(f'id="a{n}-title"', card)
                self.assertIn(f'data-i18n="writing.a{n}"', card)
                self.assertIn('<span class="card-metric"><strong>', card)
                self.assertRegex(card, r'href="https://medium\.com/@soyluisguinea/[^"]+"')
        self.assertEqual(len(re.findall(r'href="https://medium\.com/@soyluisguinea/[^"]+"', section)), 5)
        # Off-screen cards in the mobile strip must not widen the page through their .sr-only text.
        self.assertIn(".writing-card{position:relative;", read("css/styles.css"))

    def test_background_index_stays_on_screen_and_marks_the_part(self):
        html, css = read("index.html"), read("css/styles.css")
        # A direct child of the Background section, so position:sticky keeps it under the header only there.
        self.assertRegex(html, r'aria-labelledby="background-title"><div class="wrap background-head"[^>]*>.*?</div></div><nav class="section-index"')
        self.assertIn(".section-index{position:sticky;top:var(--header-offset,58px);", css)
        self.assertIn(".background [id]{scroll-margin-top:calc(var(--header-offset,4rem) + 4rem)}", css)
        self.assertIn(".section-index a[data-section]", read("js/site.js"))

    def test_skills_beside_education_does_not_take_over_the_index(self):
        # On wide screens Skills sits next to Education; it is marked only when it is the chosen destination.
        self.assertIn('<div id="skills" class="skills-block" data-nav="background" data-beside="education">', read("index.html"))
        self.assertIn("if(m.dataset.beside&&box.left>window.innerWidth*.4&&location.hash!=='#'+m.id)return;", read("js/site.js"))
        self.assertIn("#content>#music,#content>#writing,#content>#contact{scroll-margin-top:var(--header-offset,4rem)}", read("css/styles.css"))

    def test_about_on_home_is_a_synopsis_with_the_chapters(self):
        html, about = read("index.html"), read("sobre-mi.html")
        self.assertIn('<p class="about-synopsis" data-i18n="home.aboutSynopsis">', html)
        data = strings()
        self.assertEqual(data["es"]["home"]["aboutSynopsis"], "Del teclado de juguete en el que aprendí mi primera canción al escenario "
                         "del Lunario, un sello propio, Berklee Valencia y Santo Chilaquil: música, tecnología y emprendimiento "
                         "como un mismo camino.")
        self.assertNotIn('data-i18n="about.p1"', html)
        chapters = re.findall(r'<a href="sobre-mi\.html#([a-z-]+)"><span class="chapter-num">\d\d</span><span data-i18n="about\.c(\d)title">', html)
        self.assertEqual([n for _, n in chapters], list("1234567"))
        for anchor, _ in chapters:
            self.assertIn(f'<section id="{anchor}" class="about-chapter', about)

    def test_secondary_colour_is_one_olive_token_used_for_the_music_band(self):
        css = read("css/styles.css")
        light, dark = css_tokens(css)
        # Approved palette (2026-10-13): paper, terracotta, sand, deep olive and ink; no other colour.
        self.assertEqual((light["olive"], light["sand"]), ("#3d4635", "#e6e0d3"))
        self.assertEqual(dark["olive"], "#3d4635")
        self.assertIn("--sand:var(--bg);", re.search(r":root\[data-theme=dark\]\{([^}]*)\}", css).group(1))
        self.assertNotIn("petrol", css)
        self.assertGreaterEqual(contrast(light["paper"], light["olive"]), 7)
        self.assertGreaterEqual(contrast(light["mist"], light["olive"]), 4.5)
        self.assertGreaterEqual(contrast(light["graphite"], light["sand"]), 4.5)
        self.assertGreaterEqual(contrast(light["ink"], light["sand"]), 7)
        self.assertIn(".featured-section{background:var(--olive);color:var(--paper);", css)
        # Terracotta is under 3:1 on olive: focus and hover there use paper and mist.
        self.assertLess(contrast(light["accent"], light["olive"]), 3)
        self.assertIn(".featured-section a:focus-visible,.featured-section .feature-play:focus-visible{outline-color:var(--paper)}", css)

    def test_featured_recordings_are_entries_of_the_public_catalogue(self):
        html = read("index.html")
        data = read("js/music-data.js")
        cards = re.findall(r'<li class="feature" data-preview="([^"]+)"><figure class="feature-art"><img src="assets/images/([^"]+)".*?'
                           r'data-feature="([^"]+)".*?<h3 class="feature-title">([^<]+)</h3><p class="feature-artist">([^<]+)</p>', html)
        self.assertEqual(len(cards), 3)
        from urllib.parse import unquote
        for preview, art, button, title, artist in cards:
            with self.subTest(preview=preview):
                self.assertEqual(preview, button)
                line = next(l for l in data.splitlines() if f"preview:'{preview}'" in l)
                self.assertIn(f"title:'{title}'", line)
                self.assertIn(f"artist:'{artist}'", line)
                self.assertIn(f"artwork:'{unquote(art)}'", line)
                self.assertTrue((ROOT / "assets/audio/previews" / preview).is_file())

    def test_pages_end_with_contextual_links_and_share_the_footer(self):
        expected = {
            "music/index.html": ["../#background", "../sobre-mi.html", "../#contact"],
            "sobre-mi.html": ["music/", "./#background", "cv.html"],
            "cv.html": ["sobre-mi.html", "music/", "./#background"],
        }
        for rel, hrefs in expected.items():
            html = read(rel)
            with self.subTest(page=rel):
                block = re.search(r'<nav class="continue[^"]*"[^>]*>(.*?)</nav>', html).group(1)
                self.assertEqual(re.findall(r'href="([^"]+)"', block), hrefs)
                self.assertNotIn("↗", block)
        for rel in PAGES:
            footer = re.search(r'<footer class="footer[^"]*">(.*?)</footer>', read(rel)).group(1)
            self.assertEqual(re.findall(r'data-i18n="(nav\.\w+)"', footer), ["nav.home", "nav.music", "nav.about", "nav.cv", "nav.contact"])

    def test_cv_print_action_is_outside_the_menu(self):
        cv = read("cv.html")
        self.assertNotIn("print-button", header(cv))
        self.assertIn('<button type="button" class="print-button no-print" onclick="window.print()">', cv)

    def test_icons_follow_the_destination(self):
        html = read("index.html")
        # The Music facet and the CV contact row open a page of the site: →, not the external ↗.
        self.assertIn('<span data-i18n="facets.music">Music &amp; Audio</span><i aria-hidden="true">→</i>', html)
        self.assertIn('<span data-i18n="contact.cv">View the CV</span><b aria-hidden="true">→</b>', html)
        self.assertIn('<svg class="icon-mail"', html)

    def test_404_offers_home_and_the_main_pages(self):
        html = read("404.html")
        self.assertIn('<a class="home" href="/">', html)
        self.assertEqual(re.findall(r'<li><a href="([^"]+)"', html), ["/#background", "/music/", "/#writing", "/sobre-mi.html", "/cv.html", "/#contact"])


@unittest.skipUnless(NODE, "node not installed")
class FeaturedPlaybackTests(unittest.TestCase):
    def test_featured_buttons_drive_the_global_player(self):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT),
            "const page = browser.tab().open('index.html', {autoplayBlocked: false}); await settle();"
            "const buttons = page.$$('.feature-play'); out.hidden = buttons.map(b => b.hidden);"
            "page.click(buttons[1]); await settle();"
            "out.second = [page.eval('LGPlayer.current().title'), page.eval('LGPlayer.isPlaying()'), buttons.map(b => b.dataset.state), page.$('#mp-title').textContent];"
            "page.click(buttons[2]); await settle(); out.third = [page.eval('LGPlayer.current().title'), buttons.map(b => b.dataset.state), page.engineAudio.length];"
            "page.click(buttons[2]); await settle(); out.paused = [page.eval('LGPlayer.isPlaying()'), buttons[2].getAttribute('aria-label')];"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["hidden"], [False, False, False])
        self.assertEqual(out["second"], ["Sin Mirar Atrás", True, ["paused", "playing", "paused"], "Sin Mirar Atrás"])
        self.assertEqual(out["third"], ["Eres Veneno", ["paused", "paused", "playing"], 1])
        self.assertEqual(out["paused"], [False, "Play preview: Eres Veneno"])


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
        # The section name in the brand mark is the translated menu label, shown in capitals.
        self.assertIn('LUIS GUINEA<span> / <span data-i18n="nav.music">Music</span></span>', read("music/index.html"))

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
    "en": ("Python", "SQL", "REST APIs", "ETL pipelines", "Chartmetric", "Power BI", "Tableau", "Excel",
           "Google Analytics", "AWS\u00a0(EC2)", "Next.js", "Supabase"),
    "es": ("Python", "SQL", "APIs REST", "pipelines ETL", "Chartmetric", "Power BI", "Tableau", "Excel",
           "Google Analytics", "AWS\u00a0(EC2)", "Next.js", "Supabase"),
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
