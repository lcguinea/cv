#!/usr/bin/env python3
"""Focused tests for the AI & automation profile on Home and CV: the new facet, the Experience filter,
the AI & Automation Systems block of the CV, the AI & automation skills line, the education and
Santo Chilaquil corrections, the El Remedio link and the matching CV_MASTER.md records, in English
and Spanish and across the live language switch.

Static checks always run. Behaviour checks run the real pages in tests/support/minidom.js and need
Node.js. Standard library only.

Run: python3 -m unittest tests/test_ai_profile.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
NODE = shutil.which("node")
REMEDIO = "https://lcguinea.github.io/landing-el-remedio/"
NB = " "

FACETS = {
    "en": ["Music & Audio", "Data & Technology", "AI Systems & Automation", "Business & Entrepreneurship", "Creative Direction"],
    "es": ["Música y audio", "Datos y tecnología", "Sistemas de IA y automatización", "Negocio y emprendimiento", "Dirección creativa"],
}
SYSTEMS = {
    "en": ("AI & Automation Systems", [
        ("2026", "Argos · Multi-agent orchestrator"),
        ("2025 – 2026", "LedgerApp · Grupo Botanas"),
        ("Hospitality", "AI creative direction and Dispra"),
        ("2024 – Present", "Real-time data pipeline · Grupo Botanas"),
        ("2024", "Music analytics automation · Peermusic Spain (internship)"),
    ]),
    "es": ("Sistemas de IA y automatización", [
        ("2026", "Argos · Orquestador multiagente"),
        ("2025 – 2026", "LedgerApp · Grupo Botanas"),
        ("Hostelería", "Dirección creativa con IA y Dispra"),
        ("2024 – actualidad", "Pipeline de datos en tiempo real · Grupo Botanas"),
        ("2024", "Automatización de analítica musical · Peermusic Spain (prácticas)"),
    ]),
}
AI_TERMS = ("Claude", "Codex", "Gemini", "MCP", "agent")
# Inflated wording the profile must not use, in either language.
INFLATED = ("expert", "visionary", "cutting-edge", "experto", "visionario", "vanguardia",
            "does not look generic", "does not read as AI", "any label roster")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def run(scenario):
    result = subprocess.run([NODE, str(RUNNER), str(ROOT), scenario], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class StaticTests(unittest.TestCase):
    def test_home_has_five_numbered_facets_with_ai_third(self):
        html = read("index.html")
        index = re.search(r'<div class="facet-index">(.*?)</div></div></section>', html, re.S).group(1)
        self.assertEqual(re.findall(r"<b>(\d\d)</b><span data-i18n=\"facets\.(\w+)\"", index),
                         [("01", "music"), ("02", "data"), ("03", "ai"), ("04", "business"), ("05", "creative")])

    def test_experience_filter_offers_ai_and_tags_the_entries_that_did_ai_or_automation_work(self):
        html = read("index.html")
        options = re.findall(r'<option value="(\w+)"', re.search(r'<select id="experience-filter">.*?</select>', html).group(0))
        self.assertEqual(options, ["all", "music", "data", "ai", "business", "creative"])
        entries = re.findall(r'<article data-facets="([^"]*)">.*?data-i18n="experience\.(\w+)Role"', html)
        tagged = [name for facets, name in entries if "ai" in facets.split()]
        self.assertEqual(tagged, ["santo", "peer", "botanas"])

    def test_cv_systems_block_sits_between_profile_and_experience(self):
        html = read("cv.html")
        order = [html.index(k) for k in ('data-i18n="cv.profile"', 'data-i18n="cv.systems"', 'data-i18n="cv.experience"')]
        self.assertEqual(order, sorted(order))
        block = html[order[1]:order[2]]
        self.assertEqual(len(re.findall(r'<article class="cv-entry">', block)), 5)

    def test_el_remedio_is_linked_once_per_page_as_a_new_tab(self):
        for rel in ("index.html", "cv.html"):
            links = re.findall(r'<a\b([^>]*href="%s"[^>]*)>(.*?)</a>' % re.escape(REMEDIO), read(rel))
            with self.subTest(page=rel):
                self.assertEqual(len(links), 1)
                attrs, body = links[0]
                self.assertIn('target="_blank"', attrs)
                self.assertIn('rel="noopener"', attrs)
                self.assertIn('data-i18n="ui.newTab"', body)

    def test_tec_de_monterrey_is_studies_2011_2014_not_a_degree(self):
        home, cv = read("index.html"), read("cv.html")
        self.assertIn('<span data-i18n="education.communication">Communication and Digital Media studies</span>', home)
        self.assertIn("Tec de Monterrey", home)
        self.assertRegex(home, r"tec\.mx/.*?/ 2011–14</small>")
        self.assertRegex(cv, r'<strong data-i18n="cv.communicationField">Communication and Digital Media</strong> <span class="cv-degree" data-i18n="cv.studies">\(studies\)</span>')
        self.assertRegex(cv, r"tec\.mx/.*?· 2011 – 2014</span>")
        self.assertNotIn("2011 – 2015", cv)
        self.assertNotIn("2011–15", home)

    def test_cv_master_records_the_confirmed_corrections(self):
        master = read("CV_MASTER.md")
        self.assertNotRegex(master, r"100\+|weekly customers retained")
        self.assertIn("### Co-founder · Santo Chilaquil, Valencia", master)
        self.assertIn("NOT part of Grupo Botanas", master)
        # LedgerApp is Grupo Botanas' financial platform; the Santo Chilaquil entry must not claim it.
        santo = master[master.index("### Co-founder · Santo Chilaquil"):].split("\n### ", 1)[0]
        self.assertNotIn("LedgerApp", santo)
        self.assertIn("created by Luis for Grupo Botanas", master[master.index("### LedgerApp"):].split("\n### ", 1)[0])
        self.assertIn("| Communication and Digital Media (studies, degree not completed) | Tec de Monterrey | 2011 – 2014 |", master)
        self.assertNotIn("Bachelor's Degree, Communication", master)
        for heading in ("### Argos", "### Dispra", "### AI creative direction for hospitality",
                        "### Real-time data pipeline and automated reporting", "### Custom AI agents",
                        "### Music analytics automation"):
            self.assertIn(heading, master)
        self.assertNotIn("### Digital Signage", master)
        self.assertNotIn("### MCP integrations for restaurant data", master)
        self.assertIn(REMEDIO, master)
        self.assertIn("### A&R / Admin Intern · Peermusic Spain", master)
        self.assertIn("- **AI & automation:**", master)
        self.assertIn("- **Data & technology:** Python, SQL", master)

    def test_no_inflated_wording(self):
        for rel in ("index.html", "cv.html", "js/strings.js"):
            text = read(rel).lower()
            for phrase in INFLATED:
                with self.subTest(file=rel, phrase=phrase):
                    self.assertNotIn(phrase.lower(), text)


@unittest.skipUnless(NODE, "node not installed")
class BehaviourTests(unittest.TestCase):
    def test_home_ai_profile_in_both_languages_and_across_the_live_switch(self):
        out = run(
            "const page = browser.tab().open('index.html'); await settle();"
            "const read = () => ({"
            "  intro: page.$('[data-i18n=\"hero.intro\"]').textContent, practice: page.$('[data-i18n=\"hero.practice\"]').textContent,"
            "  descriptor: page.$('.descriptor').textContent,"
            "  facets: page.$$('.facet-index [data-i18n^=\"facets.\"]').filter(e => e.closest('summary') || (e.closest('a') && !e.closest('details'))).map(e => e.textContent),"
            "  ai: page.$('[data-i18n=\"facets.aiDesc\"]').textContent, link: page.$('[data-i18n=\"facets.remedioLink\"]').textContent,"
            "  data: page.$('[data-i18n=\"facets.dataDesc\"]').textContent, business: page.$('[data-i18n=\"facets.businessDesc\"]').textContent,"
            "  creative: page.$('[data-i18n=\"facets.creativeDesc\"]').textContent,"
            "  santo: page.$('[data-i18n=\"experience.santoRole\"]').textContent, botanas: page.$('[data-i18n=\"experience.botanas\"]').textContent,"
            "  santoText: page.$('[data-i18n=\"experience.santo\"]').textContent, peer: page.$('[data-i18n=\"experience.peer\"]').textContent,"
            "  skillsAiLabel: page.$('[data-i18n=\"skills.aiLabel\"]').textContent, skillsAi: page.$('[data-i18n=\"skills.ai\"]').textContent,"
            "  skillsData: page.$('[data-i18n=\"skills.data\"]').textContent, tec: page.$('[data-i18n=\"education.communication\"]').textContent,"
            "  eduTitle: page.$('[data-i18n=\"education.title\"]').textContent,"
            "  option: page.$('#experience-filter option[value=\"ai\"]').textContent, playing: page.eval('LGPlayer.isPlaying()') });"
            "out.en = read(); page.click('[data-lang=\"es\"]'); await settle(); out.es = read();"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = read();")
        en, es = out["en"], out["es"]
        self.assertEqual(out["back"], en)
        for lang, got in (("en", en), ("es", es)):
            with self.subTest(lang=lang):
                self.assertEqual(got["facets"], FACETS[lang])
                self.assertEqual(got["option"], FACETS[lang][2])
                for term in ("Argos", "Telegram", "Claude", "Codex", "Gemini", "MCP", "LedgerApp", "El Remedio", "Santo Chilaquil"):
                    self.assertIn(term, got["ai"])
                self.assertTrue(got["link"].startswith("El Remedio: "))
                self.assertIn("Dispra", got["business"])
                self.assertIn("El Remedio", got["creative"])
                # Data keeps its own tools; AI terms stay in the AI line.
                for term in ("Python", "SQL", "ETL", "AWS", "Power BI"):
                    self.assertIn(term, got["skillsData"])
                for term in AI_TERMS:
                    self.assertNotIn(term, got["skillsData"])
                for term in ("Claude", "Codex", "Gemini", "MCP"):
                    self.assertIn(term, got["skillsAi"])
                self.assertNotIn("Python", got["skillsAi"])
                for term in ("Chartmetric", "AWS" + NB + "EC2", "Grupo Botanas"):
                    self.assertIn(term, got["data"])
                # Santo Chilaquil and Grupo Botanas stay separate.
                self.assertNotIn("Santo", got["botanas"])
                self.assertNotIn("Botanas", got["santoText"])
                self.assertIn("Dispra", got["botanas"])
                self.assertIn("Chartmetric", got["peer"])
                self.assertFalse(got["playing"])
        self.assertEqual(en["descriptor"], "Creative × Analytical × Entrepreneurial")
        self.assertEqual(es["descriptor"], "Creativo × Analítico × Emprendedor")
        self.assertEqual((en["practice"], es["practice"]), ("Music · Data · AI · Writing", "Música · Datos · IA · Escritura"))
        self.assertIn("AI and automation systems", en["intro"])
        self.assertIn("sistemas de IA y automatización", es["intro"])
        self.assertEqual((en["santo"], es["santo"]), ("Co-founder, Brand & Digital Growth", "Cofundador, marca y crecimiento digital"))
        self.assertEqual((en["skillsAiLabel"], es["skillsAiLabel"]), ("AI & automation:", "IA y automatización:"))
        self.assertEqual((en["tec"], es["tec"]), ("Communication and Digital Media studies", "Estudios de Comunicación y Medios Digitales"))
        self.assertEqual(en["eduTitle"], "Academic background")
        for got in (en, es):
            self.assertNotRegex(got["tec"], r"\bBA\b|Licenciatura")

    def test_experience_filter_ai_shows_only_the_ai_and_automation_entries(self):
        out = run(
            "const page = browser.tab().open('index.html'); await settle();"
            "const f = page.$('#experience-filter'); const shown = () => page.$$('.experience-list article').filter(a => !a.hidden).map(a => a.querySelector('h3').textContent);"
            "f.value = 'ai'; f.dispatchEvent({type: 'change', bubbles: true}); await settle(); out.ai = shown();"
            "f.value = 'all'; f.dispatchEvent({type: 'change', bubbles: true}); await settle(); out.all = shown();")
        self.assertEqual([h.split(" · ")[-1].replace(" (opens in a new tab)", "") for h in out["ai"]],
                         ["Santo Chilaquil", "Peermusic Spain", "Grupo Botanas"])
        self.assertEqual(len(out["all"]), 4)

    def test_cv_systems_block_and_corrections_in_both_languages(self):
        out = run(
            "const page = browser.tab().open('cv.html'); await settle();"
            "const read = () => { const s = page.$('[data-i18n=\"cv.systems\"]').closest('section');"
            "  return { title: s.querySelector('h2').textContent,"
            "    entries: s.querySelectorAll('.cv-entry').map(e => [e.querySelector('.cv-date').textContent, e.querySelector('h3').textContent]),"
            "    creative: page.$('[data-i18n=\"cv.creative\"]').textContent, analytics: page.$('[data-i18n=\"cv.analytics\"]').textContent,"
            "    link: page.$('[data-i18n=\"cv.remedioLink\"]').textContent, role: page.$('[data-i18n=\"cv.role\"]').textContent,"
            "    profile: page.$('[data-i18n=\"cv.profileText\"]').textContent, santo: page.$('[data-i18n=\"cv.santoRole\"]').closest('h3').textContent,"
            "    santoDate: page.$('[data-i18n=\"cv.santoDate\"]').textContent, peer: page.$('[data-i18n=\"cv.peermusicRole\"]').textContent,"
            "    botanas: page.$('[data-i18n=\"cv.botanas\"]').textContent, tec: page.$('[data-i18n=\"cv.communicationField\"]').textContent + ' ' + page.$('[data-i18n=\"cv.studies\"]').textContent,"
            "    ai: page.$('[data-i18n=\"cv.ai\"]').textContent, data: page.$('[data-i18n=\"cv.data\"]').textContent, playing: page.eval('LGPlayer.isPlaying()') }; };"
            "out.en = read(); page.click('[data-lang=\"es\"]'); await settle(); out.es = read();"
            "page.click('[data-lang=\"en\"]'); await settle(); out.back = read();")
        self.assertEqual(out["back"], out["en"])
        for lang, got in (("en", out["en"]), ("es", out["es"])):
            title, entries = SYSTEMS[lang]
            with self.subTest(lang=lang):
                self.assertEqual(got["title"], title)
                self.assertEqual(got["entries"], [list(e) for e in entries])
                self.assertIn("El Remedio", got["creative"])
                self.assertIn("Santo Chilaquil", got["creative"])
                self.assertIn("Dispra", got["creative"])
                self.assertIn("Chartmetric", got["analytics"])
                self.assertTrue(got["link"].startswith("El Remedio: "))
                self.assertIn("Santo Chilaquil", got["santo"])
                self.assertNotIn("Santo", got["botanas"])
                self.assertIn("Dispra", got["botanas"])
                self.assertRegex(got["peer"], r"Intern|Becario")
                self.assertNotRegex(got["tec"], r"\bBA\b|Licenciatura")
                for term in ("Claude", "Codex", "Gemini", "MCP"):
                    self.assertIn(term, got["ai"])
                    self.assertNotIn(term, got["data"])
                self.assertFalse(got["playing"])
        en, es = out["en"], out["es"]
        self.assertEqual((en["role"], es["role"]), ("Music producer · A&R · AI systems & automation", "Productor musical · A&R · Sistemas de IA y automatización"))
        self.assertTrue(en["profile"].startswith("I work where creative and analytical thinking meet."))
        self.assertIn("Today that work centres on AI systems", en["profile"])
        self.assertIn("Hoy ese trabajo se centra en sistemas de IA", es["profile"])
        self.assertEqual((en["santoDate"], es["santoDate"]), ("Feb 2025 – Present", "feb. 2025 – actualidad"))
        self.assertEqual((en["tec"], es["tec"]), ("Communication and Digital Media (studies)", "Comunicación y Medios Digitales (estudios)"))


if __name__ == "__main__":
    unittest.main()
