#!/usr/bin/env python3
"""Focused tests for external links: Medium articles by language, certified entity links on Home
and CV, and per-song Spotify / Apple Music links on Music.

Static checks always run. Behaviour checks run the real pages in tests/support/minidom.js and need
Node.js. Standard library only.

Run: python3 -m unittest tests/test_external_links.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
NODE = shutil.which("node")
MEDIUM = "https://medium.com/@soyluisguinea/"

# English article (URL kept from CV_MASTER.md) -> Spanish version of the same article, identified by
# the Spanish title CV_MASTER.md records for it. Articles without a confirmed Spanish version keep
# their URL in both languages.
ARTICLES = {
    "a1-title": (MEDIUM + "i-tracked-a-likely-ai-generated-artist-for-18-months-the-problem-is-bigger-than-i-thought-a9bbb92d93bc",
                 MEDIUM + "llevo-18-meses-espiando-un-cat%C3%A1logo-generado-por-ia-el-problema-no-es-tecnol%C3%B3gico-es-econ%C3%B3mico-c4b0fed00cd8"),
    "a2-title": (MEDIUM + "are-we-measuring-artist-growth-wrong-522c3d6a9280", None),
    "a3-title": (MEDIUM + "seven-days-to-turn-a-viral-moment-into-a-career-2f53d1cb7179",
                 MEDIUM + "siete-d%C3%ADas-para-convertir-un-viral-en-una-carrera-d42cbcbd65ed"),
    "a4-title": (MEDIUM + "how-rata-turned-an-explosion-of-listeners-into-a-real-fan-base-560dbabd2242",
                 MEDIUM + "c%C3%B3mo-rata-convirti%C3%B3-una-explosi%C3%B3n-de-oyentes-en-una-base-real-de-fans-e856cc781091"),
    "a5-title": (MEDIUM + "las-pol%C3%A9micas-de-aleks-syntek-son-marketing-50cd7a723318", None),
}
ENTITIES = {
    "Jazztone Studios": "https://www.jazztonestudios.com/",
    "Santo Chilaquil": "https://santochilaquil.es/",
    "Moctezuma Music Group": "https://moctezumamusic.wixsite.com/moctezumamusic",
    "Berklee College of Music": "https://valencia.berklee.edu/",
    "REC Música": "https://www.recmusica.com/",
    "Tec de Monterrey": "https://tec.mx/",
}
LINKED = {
    "index.html": {"Jazztone Studios", "Santo Chilaquil", "Berklee College of Music", "REC Música", "Tec de Monterrey"},
    "cv.html": {"Jazztone Studios", "Moctezuma Music Group", "Berklee College of Music", "REC Música", "Tec de Monterrey"},
}
NEVER_LINKED = ("Grupo Botanas", "Tipazo Music Group", "Peermusic Spain")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def anchors(html):
    return [(m.group(1), m.group(2)) for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html, re.S)]


def attr(attrs, name):
    m = re.search(r'\b%s="([^"]*)"' % re.escape(name), attrs)
    return m.group(1) if m else None


class SpanishArticleTitlesTests(unittest.TestCase):
    def test_spanish_versions_match_the_spanish_titles_recorded_in_cv_master(self):
        master = read("CV_MASTER.md")
        for section, key in (("4.1", "a1-title"), ("4.3", "a3-title"), ("4.4", "a4-title")):
            block = master[master.index("### " + section):].split("\n### ", 1)[0]
            en_url = re.search(r"- URL: (\S+)", block).group(1)
            es_title = re.search(r'ES title: "([^"]+?)(?:\.\.\.)?"', block).group(1)
            en, es = ARTICLES[key]
            with self.subTest(section=section):
                self.assertEqual(en, en_url)
                slug = re.sub(r"[^a-z0-9]+", "-", es_title.lower()
                              .translate(str.maketrans("áéíóúñ", "aeioun"))).strip("-")
                es_slug = unquote(es).rsplit("/", 1)[1].translate(str.maketrans("áéíóúñ", "aeioun"))
                self.assertTrue(es_slug.startswith(slug), (slug, es_slug))
        # English-only and Spanish-only studies have no counterpart.
        self.assertIn("- Language: EN\n", master[master.index("### 4.2"):master.index("### 4.3")])
        self.assertIn("- Language: ES\n", master[master.index("### 4.5"):master.index("### Also on Medium")])


class StaticLinkTests(unittest.TestCase):
    def test_medium_links_carry_both_language_versions_only_when_confirmed(self):
        html = read("index.html")
        for key, (en, es) in ARTICLES.items():
            link = next(a for a, _ in anchors(html) if attr(a, "aria-describedby") == key)
            with self.subTest(article=key):
                self.assertEqual(attr(link, "href"), en)
                if es:
                    self.assertEqual((attr(link, "data-href-en"), attr(link, "data-href-es")), (en, es))
                else:
                    self.assertIsNone(attr(link, "data-href-es"))
                self.assertEqual(attr(link, "hreflang"), "es" if key == "a5-title" else "en")

    def test_every_external_link_opens_in_a_new_tab_and_says_so(self):
        for rel in ("index.html", "cv.html", "music/index.html"):
            for attrs, body in anchors(read(rel)):
                href = attr(attrs, "href") or ""
                if not href.startswith("http"):
                    continue
                with self.subTest(page=rel, href=href):
                    self.assertEqual(attr(attrs, "target"), "_blank")
                    self.assertIn("noopener", (attr(attrs, "rel") or "").split())
                    self.assertIn('<span class="sr-only" data-i18n="ui.newTab">', body)

    def test_certified_entities_are_linked_once_and_the_rest_are_not(self):
        for rel, names in LINKED.items():
            html = read(rel)
            linked = {}
            for attrs, body in anchors(html):
                text = re.sub(r"<[^>]+>.*?</[^>]+>|<[^>]+>", "", body).strip()
                if text in ENTITIES:
                    linked.setdefault(text, []).append(attr(attrs, "href"))
            with self.subTest(page=rel):
                self.assertEqual(set(linked), names)
                for name, hrefs in linked.items():
                    self.assertEqual(hrefs, [ENTITIES[name]], name)
                for name in NEVER_LINKED:
                    self.assertNotRegex(html, r"<a\b[^>]*>[^<]*%s" % re.escape(name))


# Titles as published on Medium (the author's feed), keyed like ARTICLES. The English titles are the
# CV_MASTER.md headings; the Spanish ones are the CV_MASTER.md "ES title" of the same article.
TITLES = {
    "a1-title": ("I Tracked a Phantom AI Artist for 18 Months. The Problem Isn't Technological, It's Economic",
                 "Llevo 18 meses espiando un catálogo generado por IA: el problema no es tecnológico, es económico."),
    "a2-title": ("Are We Measuring Artist Growth Wrong?", None),
    "a3-title": ("Seven Days to Turn a Viral Moment into a Career", "Siete días para convertir un viral en una carrera"),
    "a4-title": ("How RATA Turned an Explosion of Listeners into a Real Fan Base",
                 "Cómo RATA convirtió una explosión de oyentes en una base real de fans"),
}


class SpanishArticleTitleTextTests(unittest.TestCase):
    def test_titles_match_cv_master(self):
        master = read("CV_MASTER.md")
        for section, key in (("4.1", "a1-title"), ("4.2", "a2-title"), ("4.3", "a3-title"), ("4.4", "a4-title")):
            block = master[master.index("### " + section):].split("\n### ", 1)[0]
            en, es = TITLES[key]
            with self.subTest(section=section):
                self.assertEqual(re.search(r"### \d\.\d (.+)", block).group(1).strip(), en)
                found = re.search(r'ES title: "([^"]+)"', block)
                self.assertEqual(found and found.group(1), es)

    def test_english_titles_are_the_no_javascript_fallback(self):
        html = read("index.html")
        for key, (en, _) in TITLES.items():
            with self.subTest(article=key):
                self.assertRegex(html, r'<h3 id="%s"[^>]*>%s</h3>' % (key, re.escape(en)))


@unittest.skipUnless(NODE, "node not installed")
class BehaviourTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_language_switch_updates_article_links_and_restores_the_exact_english_urls(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const links = () => Object.fromEntries(page.$$('a[aria-describedby]').map(a =>"
            "  [a.getAttribute('aria-describedby'), [a.getAttribute('href'), a.getAttribute('hreflang')]]));"
            "out.en = links(); page.click('[data-lang=\"es\"]'); await settle(); out.es = links();"
            "out.notice = page.$('a[aria-describedby=\"a1-title\"] .sr-only').textContent;"
            "out.read = page.$('a[aria-describedby=\"a1-title\"] [data-i18n=\"writing.readResearch\"]').textContent;"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = links();"
            "browser.local['lg-language'] = 'es';"
            "const es = browser.tab().open('index.html'); await settle();"
            "out.loadEs = es.$('a[aria-describedby=\"a3-title\"]').getAttribute('href');"
        )
        for key, (en, es) in ARTICLES.items():
            with self.subTest(article=key):
                self.assertEqual(out["en"][key][0], en)
                self.assertEqual(out["es"][key][0], es or en)
                self.assertEqual(out["back"][key], out["en"][key])
        self.assertEqual(out["es"]["a1-title"][1], "es")
        self.assertEqual(out["back"]["a1-title"][1], "en")
        self.assertEqual(out["es"]["a2-title"][1], "en")
        self.assertEqual(out["notice"], " (se abre en una pestaña nueva)")
        self.assertEqual(out["read"], "Leer la investigación ↗")
        self.assertEqual(out["loadEs"], ARTICLES["a3-title"][1])

    def test_language_switch_shows_the_published_spanish_titles_and_restores_the_english_ones(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "const titles = () => Object.fromEntries(['a1-title', 'a2-title', 'a3-title', 'a4-title'].map(id => {"
            "  const h = page.$('#' + id); return [id, [h.textContent, h.closest('[lang]').getAttribute('lang')]]; }));"
            "out.en = titles(); page.click('[data-lang=\"es\"]'); await settle(); out.es = titles();"
            "out.described = page.$('a[aria-describedby=\"a3-title\"]').getAttribute('hreflang');"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = titles();"
            "browser.local['lg-language'] = 'es'; const fresh = browser.tab().open('index.html'); await settle();"
            "out.load = fresh.$('#a4-title').textContent;"
        )
        for key, (en, es) in TITLES.items():
            with self.subTest(article=key):
                self.assertEqual(out["en"][key], [en, "en"])
                # An English-only study keeps its title, marked as English, in the Spanish interface.
                self.assertEqual(out["es"][key], [es, "es"] if es else [en, "en"])
                self.assertEqual(out["back"][key], out["en"][key])
        self.assertEqual(out["described"], "es")
        self.assertEqual(out["load"], TITLES["a4-title"][1])

    def test_entity_role_titles_stay_translated_next_to_their_links(self):
        out = self.run_scenario(
            "const page = browser.tab().open('cv.html'); await settle(); page.click('[data-lang=\"es\"]'); await settle();"
            "out.h3 = page.$$('.cv-entry h3').map(h => h.textContent);"
        )
        self.assertIn("Productor musical · Jazztone Studios (se abre en una pestaña nueva)", out["h3"])
        self.assertIn("Fundador y director del sello · Moctezuma Music Group (se abre en una pestaña nueva)", out["h3"])

    def test_music_links_each_song_to_its_certified_platforms_only(self):
        out = self.run_scenario(
            "const page = browser.tab().open('music/index.html'); await settle();"
            "const read = () => page.$$('#catalog > li').map(li => li.querySelectorAll('a').map(a => ({"
            "  platform: a.dataset.platform, href: a.getAttribute('href'), target: a.getAttribute('target'),"
            "  rel: a.getAttribute('rel'), label: a.getAttribute('aria-label'), text: a.textContent})));"
            "out.en = read(); out.data = page.eval('MUSIC_DATA');"
            "out.np = page.$$('#np-links a').map(a => a.dataset.platform); out.current = page.eval('LGPlayer.index()');"
            "page.click('[data-lang=\"es\"]'); await settle(); out.es = read();"
        )
        names = {"spotify": "Spotify", "appleMusic": "Apple Music"}
        for row, links, links_es in zip(out["data"], out["en"], out["es"]):
            expected = [k for k in ("spotify", "appleMusic") if row[k]]
            with self.subTest(title=row["title"], artist=row["artist"]):
                self.assertEqual([l["platform"] for l in links], expected)
                for link, link_es in zip(links, links_es):
                    platform = names[link["platform"]]
                    self.assertEqual(link["href"], row[link["platform"]])
                    self.assertEqual((link["target"], link["rel"]), ("_blank", "noopener"))
                    self.assertEqual(link["text"], platform + " ↗")
                    self.assertEqual(link["label"], f"Listen to {row['title']} by {row['artist']} on {platform} (opens in a new tab)")
                    self.assertEqual(link_es["label"], f"Escuchar {row['title']} de {row['artist']} en {platform} (se abre en una pestaña nueva)")
        self.assertEqual(sum(len(l) for l in out["en"]), 28)
        current = out["data"][out["current"]]
        self.assertEqual(out["np"], [k for k in ("spotify", "appleMusic") if current[k]])

    def test_opening_a_platform_pauses_the_preview(self):
        out = self.run_scenario(
            "const page = browser.tab().open('music/index.html'); await settle();"
            "const row = i => page.$$('#catalog > li')[i];"
            "page.click(row(5).querySelector('.pl-title')); await settle(); out.before = !page.audio().paused;"
            "page.click(row(5).querySelector('a[data-platform=\"appleMusic\"]')); await settle(); out.after = !page.audio().paused;"
            "page.click('#toggle'); await settle(); out.again = !page.audio().paused;"
            "page.document._dispatch(page.$('#np-links a'), {type: 'auxclick', bubbles: true}); await settle(); out.middle = !page.audio().paused;"
            "out.session = JSON.parse(page.tab.session['lg-player']).playing;"
        )
        self.assertEqual((out["before"], out["after"], out["again"], out["middle"]), (True, False, True, False))
        self.assertFalse(out["session"])

    def test_songs_without_a_platform_get_no_link(self):
        out = self.run_scenario(
            "const page = browser.tab().open('music/index.html'); await settle();"
            "const data = page.eval('MUSIC_DATA');"
            "const i = data.findIndex(x => !x.appleMusic);"
            "page.click(page.$$('#catalog > li')[i].querySelector('.pl-title')); await settle();"
            "out.title = data[i].title; out.np = page.$$('#np-links a').map(a => a.dataset.platform);"
            "out.hidden = page.$('#np-links-field').hidden;"
            "out.html = page.$('#catalog').innerHTML;"
        )
        self.assertEqual(out["np"], ["spotify"])
        self.assertFalse(out["hidden"])
        self.assertNotIn("null", out["html"])
        self.assertNotIn('href=""', out["html"])


if __name__ == "__main__":
    unittest.main()
