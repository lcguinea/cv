#!/usr/bin/env python3
"""Focused tests for the link previews of shared music links (WhatsApp, social networks, messaging apps).

Crawlers read a URL's HTML without running JavaScript, so each recording and each usual selection has a static page
(tools/build_share_pages.js) with its own Open Graph and Twitter Card metadata that sends visitors on to /music/ with
the parameters the player already understands. These tests serve the built public artifact over HTTP and read the pages
as a crawler does (no JavaScript), check the images, the titles against the public catalogue, special characters, the
URLs and the redirect, that the Share buttons copy these pages, and that nothing private is published.
Requires Node.js; standard library only.

Run: python3 -m unittest tests/test_share_previews.py
"""

import functools
import html.parser
import http.server
import importlib.util
import json
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
GENERATOR = ROOT / "tools" / "build_share_pages.js"
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
SITE = "https://luisguinea.com/"
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build_site.py")
build_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_site)
EXCLUSIONS = ROOT / "data" / "music-catalog" / "public_catalog_exclusions.json"
SONG = "como-decirte--luis-guinea--2022"
CRAWLERS = ["facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", "WhatsApp/2.24.1 A", "Twitterbot/1.0"]


class Meta(html.parser.HTMLParser):
    """What a crawler reads: <title>, meta tags, canonical and scripts (never run)."""

    def __init__(self):
        super().__init__()
        self.meta, self.title, self.canonical, self.scripts, self._in = {}, "", None, [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and ("property" in a or "name" in a):
            self.meta.setdefault(a.get("property") or a.get("name"), []).append(a.get("content"))
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag in ("title", "script"):
            self._in = tag
            if tag == "script":
                self.scripts.append("")

    def handle_endtag(self, tag):
        self._in = None

    def handle_data(self, data):
        if self._in == "title":
            self.title += data
        elif self._in == "script":
            self.scripts[-1] += data

    def one(self, name):
        values = self.meta.get(name, [])
        assert len(values) == 1, (name, values)
        return values[0]


def jpeg_size(data):
    """(width, height) from a JPEG's SOF marker."""
    assert data[:3] == b"\xff\xd8\xff", "not a JPEG"
    i = 2
    while i < len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + length
    raise AssertionError("no SOF marker")


def catalogue():
    out = subprocess.run([NODE, "-e", "global.window={};require('vm').runInThisContext(require('fs').readFileSync('js/music-data.js','utf8'));"
                          "process.stdout.write(JSON.stringify(window.MUSIC_DATA))"], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node not installed")
class SharePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out = Path(cls.tmp) / "_site"
        build_site.build(cls.out)
        handler = functools.partial(QuietHandler, directory=str(cls.out))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.pages, cls.images = build_site.share_files()
        cls.tracks = catalogue()
        manifest = (ROOT / "js" / "share-pages.js").read_text(encoding="utf-8")
        cls.manifest = dict(re.findall(r'^\s*"([^"]+)": "([^"]+)"', manifest, re.M))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.tmp)

    def fetch(self, path, agent=CRAWLERS[0]):
        request = urllib.request.Request(self.base + path, headers={"User-Agent": agent})
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()

    def read(self, path, agent=CRAWLERS[0]):
        status, kind, body = self.fetch(path, agent)
        self.assertEqual((status, kind.split(";")[0]), (200, "text/html"))
        parser = Meta()
        parser.feed(body.decode("utf-8"))
        return parser

    def scenario(self, body):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), body], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_generated_pages_are_up_to_date(self):
        result = subprocess.run([NODE, str(GENERATOR), "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_song_link_previews_its_title_artist_cover_and_luis_guinea_credits_over_http(self):
        for agent in CRAWLERS:
            with self.subTest(agent=agent):
                m = self.read(f"music/song/{SONG}/", agent)
                self.assertEqual(m.one("og:title"), "Cómo Decirte · Luis Guinea, Pablo Delgado")
                self.assertEqual(m.one("og:description"), "Cómo Decirte by Luis Guinea, Pablo Delgado. Luis Guinea: artist, songwriter "
                                 "and producer. Single, 2022. Listen to a preview of up to 45 seconds.")
                self.assertEqual(m.one("og:url"), f"{SITE}music/song/{SONG}/")
                self.assertEqual(m.canonical, m.one("og:url"))
                self.assertEqual(m.one("og:image"), SITE + "assets/images/share/como-decirte-luis-guinea.jpg")
                self.assertEqual((m.one("og:image:width"), m.one("og:image:height"), m.one("og:image:type")), ("600", "600", "image/jpeg"))
                self.assertEqual(m.one("og:image:alt"), "Cover art: Cómo Decirte")
                self.assertEqual((m.one("og:type"), m.one("og:site_name")), ("website", "Luis Guinea"))
                self.assertEqual(m.one("twitter:card"), "summary")
                for name in ("title", "description", "image"):
                    self.assertEqual(m.one("twitter:" + name), m.one("og:" + name))
                self.assertEqual(m.title.strip(), "Cómo Decirte · Luis Guinea, Pablo Delgado")

    def test_every_song_page_comes_from_its_public_catalogue_entry(self):
        retired = {e["work_id"] for e in json.loads(EXCLUSIONS.read_text(encoding="utf-8"))["excluded"]}
        songs = [p for p in self.pages if p.startswith("music/song/")]
        self.assertEqual(len(songs), len(self.tracks))
        for x in self.tracks:
            work = x["preview"][:-4]
            with self.subTest(song=work):
                self.assertNotIn(work, retired)
                m = self.read(f"music/song/{work}/")
                self.assertTrue(m.one("og:title").startswith(x["title"]))
                self.assertTrue(m.one("og:title").endswith(" · " + x["artist"]))
                self.assertTrue(m.one("og:description").startswith(f'{x["title"]} by {x["artist"]}. Luis Guinea: '))
                own = x["artwork"] != "generic-cover.webp"
                # The recording's own cover when it has one; otherwise the music image, never the placeholder.
                self.assertEqual(m.one("og:image").endswith("/music.jpg"), not own)
                self.assertEqual(m.one("twitter:card"), "summary" if own else "summary_large_image")
        for work in retired:
            self.assertFalse((self.out / "music" / "song" / work).exists(), work)

    def test_selection_titles_use_catalogue_values_and_counts_match_the_player(self):
        expected = {
            "music/genre/rock/": "Rock Songs by Luis Guinea",
            "music/artist/pablo-delgado/": "Pablo Delgado",
            "music/mood/warm-or-melancholic/": "Warm or Melancholic Songs by Luis Guinea",
            "music/credit/producer/pop/": "Pop Music Produced by Luis Guinea",
            "music/genre/pop/warm/": "Warm Pop Songs by Luis Guinea",
            "music/credit/composer/": "Songs Written by Luis Guinea",
            "music/genre/cinematic-classical/": "Cinematic & Classical Music by Luis Guinea",
        }
        for path, title in expected.items():
            m = self.read(path)
            self.assertEqual((m.one("og:title"), m.one("twitter:card")), (title, "summary_large_image"))
            self.assertEqual(m.one("og:image"), SITE + "assets/images/share/music.jpg")
        # Every selection page: the number in its description is what /music/ shows for the same filters.
        selections = {key: path for key, path in self.manifest.items() if not key.startswith("song=")}
        counts = {}
        for key, path in selections.items():
            m = self.read(path)
            counts[path] = int(re.match(r"(\d+) recordings? from the catalogue of Luis Guinea\.", m.one("og:description")).group(1))
        targets = {path: re.search(r'var t="([^"]+)"', (self.out / path / "index.html").read_text(encoding="utf-8")).group(1).split("?", 1)[1]
                   for path in selections.values()}
        out = self.scenario(
            "const targets = %s; out.rows = {};"
            "for (const [path, query] of Object.entries(targets)) { const page = browser.tab().open('music/index.html?' + query); await settle();"
            "  out.rows[path] = [page.$$('#catalog .pl-row').length, page.$('#link-notice').hidden ? '' : page.$('#link-notice').textContent]; }" % json.dumps(targets))
        for path, (rows, notice) in out["rows"].items():
            with self.subTest(path=path):
                self.assertEqual(rows, counts[path])
                self.assertNotIn("left out", notice)
        # Only real values: every artist, genre and mood named by a page is in the public catalogue.
        artists = {a for x in self.tracks for a in (x.get("artists") or [x["artist"]])}
        genres = {g for x in self.tracks for g in x.get("genres") or []}
        moods = {g for x in self.tracks for g in x.get("moods") or []}
        for key in selections:
            for part in key.split("&"):
                name, values = part.split("=")
                for value in values.split(","):
                    value = urllib.request.unquote(value)
                    known = {"artist": artists, "genre": genres, "mood": moods, "credit": {"artist", "producer", "composer"}}[name]
                    self.assertIn(value, known, key)

    def test_special_characters_are_escaped_and_read_back_exactly(self):
        m = self.read("music/genre/rnb-soul/")
        self.assertEqual(m.one("og:title"), "R&B / Soul Songs by Luis Guinea")
        raw = (self.out / "music/genre/rnb-soul/index.html").read_text(encoding="utf-8")
        self.assertIn('content="R&amp;B / Soul Songs by Luis Guinea"', raw)
        accents = self.read("music/artist/carla-calderon-2/")
        self.assertEqual(accents.one("og:title"), "Carla Calderón")
        self.assertEqual(self.read("music/artist/carla-calderon/").one("og:title"), "Carla Calderon")
        self.assertIn("Luis Guinea's credits", self.read("music/artist/pablo-delgado/").one("og:description"))
        # Hostile values cannot break out of the markup or the script.
        crafted = subprocess.run([NODE, "-e", "const {html}=require('./tools/build_share_pages.js');process.stdout.write(html({path:'music/song/x/',"
                                  "query:'song=x',title:'</title><script>alert(1)</script>\"&\\'',docTitle:'<b>',description:'\"><img src=x>',heading:'<i>',sub:'&',"
                                  "image:{file:'assets/images/share/music.jpg',width:1200,height:630,alt:'\"'}}))"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertNotIn("<script>alert", crafted)
        self.assertNotIn("<img src=x>", crafted)
        parser = Meta()
        parser.feed(crafted)
        self.assertEqual(parser.one("og:title"), "</title><script>alert(1)</script>\"&'")
        self.assertEqual(len(parser.scripts), 1)

    def test_images_are_published_jpegs_of_the_declared_size(self):
        self.assertTrue(self.images)
        on_disk = sorted("assets/images/share/" + p.name for p in (ROOT / "assets/images/share").iterdir())
        self.assertEqual(on_disk, self.images)
        for rel in self.images:
            with self.subTest(image=rel):
                status, kind, body = self.fetch(rel)
                self.assertEqual((status, kind), (200, "image/jpeg"))
                self.assertLess(len(body), 300_000)
                self.assertIn(jpeg_size(body), {(600, 600), (1200, 630)})
                self.assertRegex(rel, r"^assets/images/share/[a-z0-9-]+\.jpg$")
        for path in self.manifest.values():
            m = self.read(path)
            rel = m.one("og:image")[len(SITE):]
            status, kind, body = self.fetch(rel)
            self.assertEqual(jpeg_size(body), (int(m.one("og:image:width")), int(m.one("og:image:height"))))

    def test_urls_and_the_redirect_keep_the_player_behaviour(self):
        for path in self.manifest.values():
            m = self.read(path)
            self.assertEqual((m.one("og:url"), m.canonical), (SITE + path, SITE + path))
            self.assertEqual(m.meta["robots"], ["noindex"])
        # The script sends visitors to /music/ with the page's own parameters, keeping others (order, campaign) and the
        # hash, and dropping a parameter the page fixes.
        cases = {f"music/song/{SONG}/": ("?sort=year-asc&song=other&utm_source=wa", "#jingles"),
                 "music/credit/producer/pop/": ("?genre=rock&sort=artist-asc", ""),
                 "music/artist/pablo-delgado/": ("", "")}
        scripts = {path: Meta() for path in cases}
        for path, parser in scripts.items():
            parser.feed((self.out / path / "index.html").read_text(encoding="utf-8"))
        out = subprocess.run([NODE, "-e", "const vm=require('vm'),cases=JSON.parse(process.argv[1]),out={};"
                              "for (const [path,[script,search,hash]] of Object.entries(cases)) { const url=new URL('https://luisguinea.com/'+path+search+hash);"
                              "  const location={search:url.search,hash:url.hash,replace(t){out[path]=new URL(t,url).href}}; vm.runInNewContext(script,{location}); }"
                              "process.stdout.write(JSON.stringify(out))",
                              json.dumps({p: [scripts[p].scripts[0], *cases[p]] for p in cases})], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), {
            f"music/song/{SONG}/": f"{SITE}music/?song={SONG}&sort=year-asc&utm_source=wa#jingles",
            "music/credit/producer/pop/": f"{SITE}music/?credit=producer&genre=pop&sort=artist-asc",
            "music/artist/pablo-delgado/": f"{SITE}music/?artist=Pablo%20Delgado",
        })
        # Without JavaScript the page still links to the same place.
        body = (self.out / f"music/song/{SONG}/index.html").read_text(encoding="utf-8")
        self.assertIn(f'<a href="../../?song={SONG}">Listen to Cómo Decirte on luisguinea.com</a>', body)

    def test_share_copies_the_preview_page_when_there_is_one_and_the_plain_link_otherwise(self):
        out = self.scenario(
            "const open = q => browser.tab().open('music/index.html' + q, {clipboard: 'granted'});"
            "const copy = async q => { const page = open(q); await settle(); page.click('#share-view'); await settle(); return page.copied[0]; };"
            "out.artist = await copy('?artist=Pablo%%20Delgado');"
            "out.pair = await copy('?credit=producer&genre=pop&sort=year-asc');"
            "out.moods = await copy('?mood=melancholic,warm');"
            "out.search = await copy('?genre=pop&q=amor');"
            "out.three = await copy('?credit=producer&genre=pop&mood=warm');"
            "out.none = await copy('');"
            "const page = open(''); await settle(); page.click(page.$$('.pl-share').find(b => b.dataset.song === '%s')); await settle(); out.song = page.copied[0];" % SONG)
        self.assertEqual(out, {
            "artist": "http://test.local/music/artist/pablo-delgado/",
            "pair": "http://test.local/music/credit/producer/pop/?sort=year-asc",
            "moods": "http://test.local/music/mood/warm-or-melancholic/",
            # Search text and rarer combinations have no page: they are shared as they are and preview as /music/.
            "search": "http://test.local/music/index.html?q=amor&genre=pop",
            "three": "http://test.local/music/index.html?credit=producer&mood=warm&genre=pop",
            "none": "http://test.local/music/index.html",
            "song": f"http://test.local/music/song/{SONG}/",
        })

    def test_pages_carry_only_public_catalogue_data(self):
        allowed_keys = {"title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview", "spotify", "appleMusic",
                        "version", "youtube", "soundcloud", "artists", "genres", "moods"}
        self.assertTrue(all(set(x) <= allowed_keys for x in self.tracks))
        for path in self.manifest.values():
            body = (self.out / path / "index.html").read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotRegex(body, r"[\w.+-]+@[\w-]+\.[\w.]+")
                for private in ("data/music-catalog", "catalog_master", "work_id", "sha256", "manifest", "approval", "isrc", "notes"):
                    self.assertNotIn(private, body.lower())
                self.assertNotIn("http://", body)
                # Only the site itself is linked: no external services.
                self.assertEqual(set(re.findall(r'https://[^/"]+/', body)), {SITE})

    def test_without_javascript_every_page_offers_an_accessible_link_to_its_destination(self):
        for path in self.manifest.values():
            body = (self.out / path / "index.html").read_text(encoding="utf-8")
            with self.subTest(path=path):
                target = re.search(r'var t="([^"]+)"', body).group(1)
                heading = re.search(r"<h1>([^<]+)</h1>", body).group(1)
                links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', body)
                # One link, inside the main landmark, to the same place the script goes, named after what it opens.
                self.assertEqual(links, [(target.replace("&", "&amp;"), f"Listen to {heading} on luisguinea.com")])
                self.assertRegex(body, r"<main>.*<h1>.*<a href=.*</main>")
                self.assertIn('<html lang="en">', body)
                self.assertNotIn('http-equiv="refresh"', body)

    def test_old_links_with_parameters_keep_working(self):
        out = self.scenario(
            "const open = q => browser.tab().open('music/index.html' + q);"
            "const view = p => ({url: p.location.search, current: p.eval('LGPlayer.index()'), rows: p.$$('#catalog .pl-row').length,"
            "  pressed: p.$$('.chip[aria-pressed=\"true\"]').map(c => c.dataset.id), artist: p.$('#artist').value, sort: p.$('#sort').value,"
            "  queue: p.eval('LGPlayer.queue()') && p.eval('LGPlayer.queue()').length, attempts: p.log.filter(e => /^(play|blocked):/.test(e)).length});"
            "out.song = view(open('?song=%s')); await settle(); out.song = view(browser.tab().open('music/index.html?song=%s'));"
            "const f = open('?mood=warm&genre=pop&sort=artist-asc'); await settle(); out.filters = view(f);"
            "const a = open('?artist=Pablo%%20Delgado&credit=producer'); await settle(); out.artist = view(a);" % (SONG, SONG))
        i = next(k for k, x in enumerate(self.tracks) if x["preview"] == SONG + ".mp3")
        self.assertEqual((out["song"]["url"], out["song"]["current"], out["song"]["attempts"]), (f"?song={SONG}", i, 1))
        self.assertEqual((out["filters"]["url"], sorted(out["filters"]["pressed"]), out["filters"]["sort"]), ("?mood=warm&genre=pop&sort=artist-asc", ["pop", "warm"], "artist-asc"))
        self.assertEqual(out["filters"]["queue"], out["filters"]["rows"])
        self.assertEqual((out["artist"]["artist"], out["artist"]["url"]), ("Pablo Delgado", "?artist=Pablo%20Delgado&credit=producer"))
        # /music/ itself keeps its generic preview, which is what a link with parameters shows.
        m = self.read("music/?song=" + SONG)
        self.assertEqual((m.one("og:url"), m.one("og:title")), (SITE + "music/", "Music / Audio · Luis Guinea"))

    def test_validate_rejects_a_preview_whose_image_is_missing(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "_site"
            shutil.copytree(self.out, out)
            (out / "assets/images/share/music.jpg").unlink()
            errors = build_site.validate(out)
            self.assertTrue(any("og:image outside the artifact" in e for e in errors), errors[:3])
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(NODE, "node not installed")
class ShareCheckTests(unittest.TestCase):
    """node tools/build_share_pages.js --check, as the Pages workflow runs it, on copies of the site (--root)."""

    INPUTS = ["tools/build_share_pages.js", "tools/share-images.lock.json", "js/music-data.js", "js/strings.js", "js/share-pages.js",
              "music/song", "music/artist", "music/genre", "music/mood", "music/credit", "assets/images"]

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.pristine = cls.tmp / "pristine"
        for rel in cls.INPUTS:
            src, dst = ROOT / rel, cls.pristine / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copyfile)(src, dst)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def copy(self, name):
        root = self.tmp / name
        shutil.copytree(self.pristine, root)
        return root

    @staticmethod
    def snapshot(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def check(self, root):
        # Only Node on the PATH: no sips or other image tools, as on the Ubuntu runner.
        env = {"PATH": str(Path(NODE).resolve().parent)}
        before = self.snapshot(root)
        result = subprocess.run([NODE, str(root / "tools/build_share_pages.js"), "--check", "--root", str(root)], capture_output=True, text=True, env=env)
        self.assertEqual(self.snapshot(root), before, "the check wrote files")
        return result.returncode, result.stdout + result.stderr

    def test_an_up_to_date_copy_passes_without_image_tools(self):
        code, output = self.check(self.copy("ok"))
        self.assertEqual((code, output.strip()), (0, "SHARE PAGES OK: 185 pages"))

    def test_missing_retired_and_out_of_date_pages_fail(self):
        def missing(root): shutil.rmtree(root / "music/song" / SONG)
        def retired(root):
            page = root / "music/song/toxic--isabella-macias--2018/index.html"
            page.parent.mkdir(parents=True)
            page.write_text((root / "music/song" / SONG / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
        def edited(root):
            page = root / "music/genre/rock/index.html"
            page.write_text(page.read_text(encoding="utf-8").replace('content="Rock Songs by Luis Guinea"', 'content="Rock"', 1), encoding="utf-8")
        def catalogue(root):
            data = root / "js/music-data.js"
            data.write_text(data.read_text(encoding="utf-8").replace("title:'Cómo Decirte'", "title:'Como Decirte (Remaster)'", 1), encoding="utf-8")
        def index(root):
            manifest = root / "js/share-pages.js"
            manifest.write_text(manifest.read_text(encoding="utf-8").replace('"music/genre/rock/"', '"music/genre/rock-2/"'), encoding="utf-8")
        def cover(root):
            with open(root / "assets/images/Cómo-Decirte---Luis-Guinea.webp", "ab") as f:
                f.write(b"changed")
        def image(root):
            with open(root / "assets/images/share/music.jpg", "ab") as f:
                f.write(b"changed")
        cases = {missing: f"missing music/song/{SONG}/index.html", retired: "stale music/song/toxic--isabella-macias--2018/index.html",
                 edited: "out of date music/genre/rock/index.html", catalogue: f"out of date music/song/{SONG}/index.html",
                 index: "out of date js/share-pages.js", cover: "cover changed, run --images: assets/images/share/como-decirte-luis-guinea.jpg",
                 image: "image differs from the lock assets/images/share/music.jpg"}
        for change, message in cases.items():
            with self.subTest(case=change.__name__):
                root = self.copy(change.__name__)
                change(root)
                code, output = self.check(root)
                self.assertEqual(code, 1)
                self.assertIn("SHARE PAGES OUT OF DATE", output)
                self.assertIn(message, output)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


if __name__ == "__main__":
    unittest.main()
