#!/usr/bin/env python3
"""Focused tests for the GitHub Pages artifact built by tools/build_site.py and for the publication
files it carries: allowlist, forbidden content, previews, self-hosted fonts, JSON-LD, canonical URLs,
internal links that work at the domain root and under a temporary project-site subpath, robots.txt,
sitemap.xml, 404.html and the Pages workflow.

Standard library only. Builds into a temporary directory; never touches _site/.

Run: python3 -m unittest tests/test_site_artifact.py
"""

import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build_site.py")
build_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_site)

SITE = "https://luisguinea.com/"
CANONICAL = {"index.html": SITE, "cv.html": SITE + "cv.html", "music/index.html": SITE + "music/"}
FONTS = {
    "instrument-serif-latin-400-normal.woff2": ("Instrument Serif", "normal"),
    "instrument-serif-latin-400-italic.woff2": ("Instrument Serif", "italic"),
    "inter-latin-wght-normal.woff2": ("Inter", "normal"),
    "ibm-plex-mono-latin-400-normal.woff2": ("IBM Plex Mono", "normal"),
}
# Fonts each page needs before first paint: body text and headings everywhere, the italic hero name on Home.
PRELOADS = {
    "index.html": ["instrument-serif-latin-400-normal.woff2", "instrument-serif-latin-400-italic.woff2", "inter-latin-wght-normal.woff2"],
    "cv.html": ["instrument-serif-latin-400-normal.woff2", "inter-latin-wght-normal.woff2"],
    "music/index.html": ["instrument-serif-latin-400-normal.woff2", "inter-latin-wght-normal.woff2"],
}
FONT_HOSTS = re.compile(r"fonts\.googleapis|fonts\.gstatic|use\.typekit|fonts\.bunny|cdnjs|jsdelivr|unpkg", re.I)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def json_ld(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out = Path(cls.tmp) / "_site"
        cls.files = build_site.build(cls.out)
        cls.present = build_site.artifact_files(cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_artifact_is_valid(self):
        self.assertEqual(build_site.validate(self.out), [])

    def test_exact_composition(self):
        self.assertEqual(self.present, sorted(self.files))
        top = {p.split("/")[0] for p in self.present}
        self.assertEqual(top, {"404.html", "assets", "css", "cv.html", "fonts", "index.html", "js", "music",
                               "robots.txt", "sitemap.xml"})
        previews = [p for p in self.present if p.startswith("assets/audio/previews/")]
        images = [p for p in self.present if p.startswith("assets/images/")]
        self.assertEqual(len(previews), 16)
        self.assertTrue(all(p.endswith(".mp3") for p in previews))
        self.assertEqual(len(images), 17)  # 16 artworks + the profile portrait
        self.assertNotIn("assets/images/cover.webp", self.present)
        self.assertEqual(len(self.present), 54)

    def test_no_private_or_development_content(self):
        for rel in self.present:
            self.assertFalse(rel.endswith((".md", ".py", ".json", ".csv", ".xlsx", ".png")), rel)
            self.assertFalse(re.match(r"(tests|data|tools|\.github|One Page Luis Guinea)/", rel), rel)
        for name in ("catalog_master.json", "CV_MASTER.md", "local-server.js", "cover.png", "profile_pic.png"):
            self.assertFalse(any(p.endswith(name) for p in self.present), name)

    def test_every_untracked_file_is_left_out(self):
        tracked = build_site.tracked_files()
        self.assertTrue(set(self.files) <= tracked)

    def test_validate_rejects_forbidden_additions(self):
        cases = {
            "README.md": b"# x",
            "data/music-catalog/catalog_master.json": b"{}",
            "tests/test_x.py": b"",
            "assets/audio/previews/extra.mp3": b"ID3",
            "assets/audio/master.wav": b"RIFF",
            ".DS_Store": b"",
        }
        for rel, data in cases.items():
            with self.subTest(rel=rel):
                target = self.out / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                try:
                    self.assertTrue(any(rel in e for e in build_site.validate(self.out)))
                finally:
                    target.unlink()
        self.assertEqual(build_site.validate(self.out), [])

    def test_validate_rejects_altered_preview(self):
        rel = next(p for p in self.present if p.endswith(".mp3"))
        original = (self.out / rel).read_bytes()
        (self.out / rel).write_bytes(original + b"\0")
        try:
            self.assertIn(f"preview differs from its manifest sha256: {rel}", build_site.validate(self.out))
        finally:
            (self.out / rel).write_bytes(original)


class PublicationFilesTest(unittest.TestCase):
    def test_canonical_urls_are_kept(self):
        for rel, url in CANONICAL.items():
            self.assertEqual(re.findall(r'<link rel="canonical" href="([^"]+)">', read(rel)), [url], rel)

    def test_person_json_ld_is_one_entity(self):
        blocks = {rel: json_ld(read(rel)) for rel in ("index.html", "cv.html")}
        self.assertEqual(blocks["index.html"], blocks["cv.html"])
        (person,) = blocks["index.html"]
        self.assertEqual(person["@type"], "Person")
        self.assertEqual(person["@id"], SITE + "#person")
        self.assertEqual(person["url"], SITE)
        self.assertEqual(json_ld(read("music/index.html")), [])

    def test_open_graph_uses_page_metadata(self):
        for rel, url in CANONICAL.items():
            html = read(rel)
            og = dict(re.findall(r'<meta property="og:([a-z:_]+)" content="([^"]*)">', html))
            self.assertEqual(og["url"], url, rel)
            self.assertEqual(og["title"], re.search(r"<title[^>]*>(.*?)</title>", html).group(1), rel)
            self.assertEqual(og["description"], re.search(r'<meta name="description" content="([^"]*)">', html).group(1), rel)
            self.assertEqual(og["image"], SITE + "assets/images/profile.webp", rel)

    def test_internal_links_are_canonical_and_relative(self):
        for rel in CANONICAL:
            hrefs = re.findall(r'\bhref="([^"]*)"', read(rel))
            self.assertFalse([h for h in hrefs if re.search(r"(^|/)index\.html", h)], rel)
            self.assertFalse([h for h in hrefs if h.startswith("/")], rel)
            self.assertFalse([h for h in re.findall(r'\bsrc="([^"]*)"', read(rel)) if h.startswith("/")], rel)

    def test_links_resolve_under_a_project_subpath(self):
        # Simulates https://user.github.io/repo/: every local reference must stay inside the subpath.
        from urllib.parse import urljoin
        base = "https://example.github.io/cv/"
        for rel in CANONICAL:
            page = urljoin(base, rel)
            for ref in re.findall(r'\b(?:href|src)="([^"]*)"', read(rel)):
                if build_site.EXTERNAL.match(ref):
                    continue
                self.assertTrue(urljoin(page, ref).startswith(base), (rel, ref))

    def test_self_hosted_fonts(self):
        css = read("css/styles.css")
        faces = re.findall(r"@font-face\{([^}]*)\}", css)
        self.assertEqual(len(faces), len(FONTS))
        for face in faces:
            self.assertIn("font-display:swap", face)
            src = re.search(r"url\(\.\./fonts/([^)]+)\) format\('woff2'\)", face).group(1)
            family, style = FONTS[src]
            self.assertIn(f"font-family:'{family}'", face)
            self.assertIn(f"font-style:{style}", face)
            self.assertEqual((ROOT / "fonts" / src).read_bytes()[:4], b"wOF2")
        self.assertIn("--serif:'Instrument Serif',", css)
        self.assertIn("--sans:'Inter',", css)
        self.assertIn("--mono:'IBM Plex Mono',", css)
        for name in ("Playfair", "DM Sans", "DM Mono"):
            self.assertNotIn(name, css)
        for lic in ("OFL-InstrumentSerif.txt", "OFL-Inter.txt", "OFL-IBMPlexMono.txt"):
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", read("fonts/" + lic))

    def test_preloads_only_needed_fonts(self):
        for rel, expected in PRELOADS.items():
            html = read(rel)
            preloads = re.findall(r'<link rel="preload" href="(?:\.\./)?fonts/([^"]+)" as="font" type="font/woff2" crossorigin>', html)
            self.assertEqual(preloads, expected, rel)
            self.assertEqual(html.count('rel="preload"'), len(expected), rel)
            self.assertLess(html.index('rel="preload"'), html.index('rel="stylesheet"'), rel)

    def test_no_font_or_script_cdn(self):
        for rel in list(CANONICAL) + ["404.html", "css/styles.css"]:
            self.assertIsNone(FONT_HOSTS.search(read(rel)), rel)

    def test_robots_and_sitemap(self):
        self.assertEqual(read("robots.txt"), "User-agent: *\nAllow: /\n\nSitemap: https://luisguinea.com/sitemap.xml\n")
        locs = re.findall(r"<loc>([^<]+)</loc>", read("sitemap.xml"))
        self.assertEqual(locs, list(CANONICAL.values()))

    def test_404_is_self_contained(self):
        html = read("404.html")
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertNotIn("<link rel=\"stylesheet\"", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("—", html)  # no em dashes in published copy
        self.assertIn('href="/"', html)

    def test_workflow_publishes_only_the_built_artifact(self):
        wf = read(".github/workflows/pages.yml")
        self.assertIn("python3 tools/build_site.py --out _site", wf)
        self.assertIn("python3 -m unittest tests/test_site_artifact.py", wf)
        self.assertRegex(wf, r"actions/upload-pages-artifact@[0-9a-f]{40} # v\d")
        self.assertRegex(wf, r"actions/deploy-pages@[0-9a-f]{40} # v\d")
        self.assertRegex(wf, r"(?m)^\s+path: _site$")
        self.assertIn("_site/", read(".gitignore"))

    def test_workflow_is_manual_only(self):
        # Publication is not approved yet: the workflow may only run by hand (workflow_dispatch).
        wf = read(".github/workflows/pages.yml")
        on = re.search(r"(?ms)^on:\n(.*?)^\S", wf).group(1)
        triggers = re.findall(r"(?m)^  ([a-z_]+):", on)
        self.assertEqual(triggers, ["workflow_dispatch"])
        for event in ("push", "pull_request", "pull_request_target", "schedule", "workflow_run",
                      "repository_dispatch", "release", "create"):
            self.assertNotRegex(wf, rf"(?m)^\s*{event}:", event)
        self.assertRegex(wf, r"(?m)^on:[ \t]*$")  # block form only, no inline "on: push" or "on: [push]"
        self.assertIn("actions/deploy-pages@", wf)
        self.assertIn("needs: build", wf)


if __name__ == "__main__":
    unittest.main()
