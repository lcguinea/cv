#!/usr/bin/env python3
"""Focused tests for the agreed search and sharing metadata: <title>, meta description, Open Graph,
twitter:card and the Person JSON-LD on Home and CV. Music carries no JSON-LD.

Metadata stays static and in English; the client-side language switch does not change it.

Standard library only. Run: python3 -m unittest tests/test_seo_metadata.py
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://luisguinea.com/"

PAGES = {
    "index.html": {
        "url": SITE,
        "title": "Luis Guinea · Music Producer, A&amp;R, Data &amp; AI Systems",
        "description": "Music producer and A&amp;R for 10+ years. Luis Guinea builds AI and automation systems, "
                       "works with data, founded a label and writes about how artists grow.",
    },
    "cv.html": {
        "url": SITE + "cv.html",
        "title": "CV / Luis Guinea",
        "description": "CV of Luis Guinea: music producer and A&amp;R, label founder, IT and automation developer "
                       "at Grupo Botanas; AI systems, data and music research. MA, Berklee.",
    },
    "music/index.html": {
        "url": SITE + "music/",
        "title": "Music / Audio · Luis Guinea",
        "description": "Releases by Luis Guinea as artist, producer and songwriter, 2020–2024, "
                       "with chorus previews, credits and links to listen.",
    },
}

PERSON = {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": SITE + "#person",
    "name": "Luis Carlos Guinea Moctezuma",
    "alternateName": "Luis Guinea",
    "url": SITE,
    "image": SITE + "assets/images/profile.webp",
    "email": "lguinea@berklee.edu",
    "jobTitle": ["Music Producer", "Information Technology & Automation Developer"],
    "description": "Music producer and A&R with 10+ years in the music industry. Builds AI and automation systems "
                   "for real business operations, works with data and publishes research on how artists grow.",
    "worksFor": [
        {"@type": "Organization", "name": "Jazztone Studios", "url": "https://www.jazztonestudios.com/"},
        {"@type": "Organization", "name": "Grupo Botanas"},
    ],
    "alumniOf": [
        {"@type": "CollegeOrUniversity", "name": "Berklee College of Music", "url": "https://valencia.berklee.edu/"},
        {"@type": "EducationalOrganization", "name": "REC Música", "url": "https://www.recmusica.com/"},
    ],
    "knowsAbout": ["Music production", "Composition and arrangement", "A&R", "Artist development", "AI systems",
                   "Multi-agent orchestration", "Automation", "Data analysis", "Data pipelines", "Data journalism",
                   "Brand strategy"],
    "knowsLanguage": ["es", "en", "fr"],
    "homeLocation": {"@type": "Place", "name": "Valencia, Spain"},
    "sameAs": ["https://medium.com/@soyluisguinea"],
}


def head(rel):
    html = (ROOT / rel).read_text(encoding="utf-8")
    return re.search(r"<head>(.*?)</head>", html, re.S).group(1)


def json_ld(rel):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', head(rel), re.S)]


class PageMetadataTest(unittest.TestCase):
    def test_title_description_and_open_graph(self):
        for rel, want in PAGES.items():
            with self.subTest(rel=rel):
                h = head(rel)
                self.assertEqual(re.findall(r"<title[^>]*>(.*?)</title>", h), [want["title"]])
                self.assertEqual(re.findall(r'<meta name="description" content="([^"]*)">', h), [want["description"]])
                og = re.findall(r'<meta property="og:([a-z:_]+)" content="([^"]*)">', h)
                self.assertEqual(og, [
                    ("type", "website"), ("site_name", "Luis Guinea"), ("url", want["url"]),
                    ("title", want["title"]), ("description", want["description"]),
                    ("image", SITE + "assets/images/profile.webp"), ("image:type", "image/webp"),
                    ("image:width", "1200"), ("image:height", "1200"), ("image:alt", "Luis Guinea"),
                ])

    def test_twitter_card_only_declares_the_card_type(self):
        for rel in PAGES:
            with self.subTest(rel=rel):
                self.assertEqual(re.findall(r'<meta name="twitter:([a-z:_]+)" content="([^"]*)">', head(rel)),
                                 [("card", "summary_large_image")])
                self.assertNotIn("twitter:", head(rel).replace('name="twitter:card"', ""))

    def test_descriptions_have_no_em_dash(self):
        for rel, want in PAGES.items():
            self.assertNotIn("—", want["title"] + want["description"], rel)
        self.assertNotIn("—", json.dumps(PERSON, ensure_ascii=False))


class PersonJsonLdTest(unittest.TestCase):
    def test_home_and_cv_carry_the_agreed_person(self):
        for rel in ("index.html", "cv.html"):
            with self.subTest(rel=rel):
                self.assertEqual(json_ld(rel), [PERSON])

    def test_music_has_no_json_ld(self):
        self.assertEqual(json_ld("music/index.html"), [])

    def test_person_avoids_unsupported_claims(self):
        text = json.dumps(PERSON)
        self.assertNotIn("Specialist", text)
        self.assertNotIn("Santo Chilaquil", text)
        self.assertNotIn("Tec de Monterrey", text)
        for name in ("Argos", "LedgerApp", "Dispra"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
