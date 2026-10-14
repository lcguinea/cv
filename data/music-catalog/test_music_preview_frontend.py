#!/usr/bin/env python3
"""Focused frontend tests for the /music/ page: selection, player updates, exclusive playback, role
filters and internationalisation.

The large player and the playlist are views of the global engine in js/player.js, which owns the only
<audio> element of the page. Static checks always run. When Node.js is available the real page runs
with its real scripts in tests/support/minidom.js, a small DOM without dependencies whose media
elements record every play/pause and refuse playback without a user gesture, like a browser.
"""

import json
import re
import shutil
import subprocess
import unicodedata
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
MUSIC_HTML = ROOT / "music" / "index.html"
MUSIC_DATA = ROOT / "js" / "music-data.js"
MUSIC_PAGE = ROOT / "js" / "music-page.js"
PLAYER_JS = ROOT / "js" / "player.js"
STRINGS_JS = ROOT / "js" / "strings.js"
STYLES = ROOT / "css" / "styles.css"
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
NODE = shutil.which("node")

# Helpers available to every scenario: `page` is /music/ in a fresh tab and `snapshot()` reads its state.
PRELUDE = r"""
const tab = browser.tab();
const page = tab.open('music/index.html');
await settle();
const $ = id => page.document.getElementById(id);
const rows = () => page.$$('.pl-row');
const engine = () => page.audio();
const click = async i => { page.click(rows().find(r => r.dataset.index === String(i)).querySelector('.pl-title')); await settle(); };
const press = async id => { page.click('#' + id); await settle(); };
const filter = async (value, query) => { page.change('#role', value); page.input('#search', query || ''); await settle(); };
const foreign = page.document.createElement('audio');
foreign.src = 'other.mp3';
page.document.body.appendChild(foreign);
const playForeign = async () => { page.gesture = true; foreign.play(); page.gesture = false; await settle(); };
const snapshot = () => ({
  title: $('np-title').textContent, artist: $('np-artist').textContent,
  year: $('np-year').textContent, type: $('np-type').textContent, index: $('np-index').textContent,
  art: $('np-art').src, alt: $('np-art').alt, roles: $('np-roles').innerHTML,
  audioSrc: engine().src, playing: !engine().paused, foreignPlaying: !foreign.paused,
  audioCount: page.created.filter(m => m !== foreign).length + page.$$('audio').filter(m => m !== foreign).length,
  toggleState: $('toggle').dataset.state, toggleLabel: $('toggle').getAttribute('aria-label'),
  prevLabel: $('prev').getAttribute('aria-label'), nextLabel: $('next').getAttribute('aria-label'),
  status: $('np-status').textContent, count: $('count').textContent,
  total: $('total').textContent, emptyHidden: $('empty').hidden,
  active: page.eval('LGPlayer.index()'),
  rows: rows().map(r => ({index: Number(r.dataset.index), current: r.getAttribute('aria-current'),
    playing: r.classList.contains('is-playing'), state: r.querySelector('.pl-state').textContent})),
  data: page.eval('MUSIC_DATA'), log: page.log.slice(),
});
"""


def node_json(expression, path):
    result = subprocess.run(
        [NODE, "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                     f"process.stdout.write(JSON.stringify({expression}))", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


class MusicPlayerStaticTests(unittest.TestCase):
    def setUp(self):
        self.html = MUSIC_HTML.read_text(encoding="utf-8")

    def test_the_page_has_no_audio_element_of_its_own(self):
        # The engine in js/player.js creates the page's only <audio>; the markup holds none.
        self.assertEqual(re.findall(r"<audio\b", self.html), [])
        self.assertNotRegex(self.html, r"(?i)autoplay")
        self.assertNotIn("<script>", self.html)
        scripts = re.findall(r'<script src="([^"]+)"', self.html)
        self.assertEqual(scripts[-3:], ["../js/music-data.js", "../js/player.js", "../js/music-page.js"])

    def test_preview_url_is_confined_to_the_public_preview_directory(self):
        player = PLAYER_JS.read_text(encoding="utf-8")
        self.assertIn(
            "function previewUrl(name){return /^[a-z0-9][a-z0-9-]*\\.mp3$/.test(String(name||''))"
            "?new URL('assets/audio/previews/'+encodeURIComponent(name),root).href:''}",
            player,
        )
        self.assertIn("audio.src=previewUrl(tracks[i].preview)", player)
        self.assertEqual(player.count("createElement('audio')"), 1)

    def test_controls_and_states_are_exposed_to_assistive_technology(self):
        # Icon-only buttons: an accessible name in the markup (before any script runs) that the
        # i18n engine keeps translated through data-i18n-label.
        for control, key in (("prev", "music.previous"), ("next", "music.next")):
            self.assertRegex(
                self.html,
                rf'<button id="{control}" class="ctl" type="button" aria-label="[^"]+" data-i18n-label="{key}">',
            )
        for fragment in ('id="toggle" class="ctl ctl-play" type="button"',
                         '<label for="np-volume" data-i18n="player.volume">',
                         'role="status" aria-live="polite"'):
            self.assertIn(fragment, self.html)
        # Grouping and form labels carry an English fallback in the markup and an i18n key.
        for pattern in (r'role="group" aria-label="[^"]+" data-i18n-label="music\.controls"',
                        r'<label class="sr-only" for="seek" data-i18n="music\.seek">[^<]+</label>',
                        r'<label for="role" data-i18n="music\.roleLabel">[^<]+</label>',
                        r'<label for="artist" data-i18n="music\.artistFilter">[^<]+</label>',
                        r'<label for="sort" data-i18n="music\.sortLabel">[^<]+</label>',
                        r'role="group" aria-labelledby="mood-label" aria-describedby="style-note"',
                        r'role="group" aria-labelledby="genre-label" aria-describedby="style-note"'):
            self.assertRegex(self.html, pattern)
        self.assertIn("row.setAttribute('aria-current',String(current))", MUSIC_PAGE.read_text(encoding="utf-8"))
        self.assertNotRegex(self.html, r'<svg (?![^>]*aria-hidden="true")')

    def test_visible_text_is_bound_to_i18n(self):
        body = self.html[self.html.index("<body"):self.html.index("<script src=")]
        bound = r'<(\w+)\b[^>]*\bdata-i18n="[^"]+"[^>]*>[^<]*</\1>'
        texts = {text.strip() for text in re.findall(r">([^<]+)<", re.sub(bound, "", body)) if text.strip()}
        # Brand mark, language codes, separators and the initial counters are not translatable.
        self.assertLessEqual(texts, {"LUIS GUINEA", "/ MUSIC", "EN", "ES", "·", "/", "0", "0:00", "↺"})

    def test_reduced_motion_disables_player_transitions(self):
        css = STYLES.read_text(encoding="utf-8")
        self.assertIn("@media(prefers-reduced-motion:reduce){.pl-row,.ctl,.np-art img{transition:none}}", css)


@unittest.skipUnless(NODE, "node not installed")
class MusicStringsTests(unittest.TestCase):
    def test_every_music_key_used_by_the_page_exists_in_both_languages(self):
        html = MUSIC_HTML.read_text(encoding="utf-8")
        code = MUSIC_PAGE.read_text(encoding="utf-8") + PLAYER_JS.read_text(encoding="utf-8")
        used = set(re.findall(r"'music\.(\w+)'(?!\+)", code))
        used |= set(re.findall(r'data-i18n(?:-label|-placeholder)?="music\.(\w+)"', html))
        data = node_json("window.MUSIC_DATA", MUSIC_DATA)
        used |= {"role" + re.sub(r"[^A-Za-z]", "", r) for x in data for r in x["roles"]}
        used |= {"type" + re.sub(r"[^A-Za-z]", "", x["releaseType"]) for x in data}
        used |= {"genre_" + g for x in data for g in x["genres"]} | {"mood_" + m for x in data for m in x["moods"]}
        english = node_json("window.STRINGS.en.music", STRINGS_JS)
        spanish = node_json("window.STRINGS.es.music", STRINGS_JS)
        self.assertEqual(set(english), set(spanish))
        self.assertLessEqual(used, set(english))
        for key in used:
            self.assertTrue(english[key].strip() and spanish[key].strip(), key)

    def test_genre_and_mood_labels_are_the_approved_vocabulary(self):
        fields = json.loads((ROOT / "data" / "music-catalog" / "vocabularies.json").read_text(encoding="utf-8"))["fields"]
        english = node_json("window.STRINGS.en.music", STRINGS_JS)
        spanish = node_json("window.STRINGS.es.music", STRINGS_JS)
        for field in ("genre", "mood"):
            for term in fields[field]["terms"]:
                key = f"{field}_{term['id']}"
                self.assertEqual((english[key], spanish[key]), (term["label_en"], term["label_es"]), key)


def year(x):
    """Text the player shows for a row's year: unreleased recordings may have none."""
    return "" if x["year"] is None else str(x["year"])


@unittest.skipUnless(NODE, "node not installed")
class MusicPlayerBehaviourTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), PRELUDE + scenario],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_initial_state_shows_the_session_track_without_playing(self):
        state = self.run_scenario("out.s = snapshot();")["s"]
        active = state["active"]
        x = state["data"][active]

        n = len(state["data"])
        self.assertEqual(len(state["rows"]), n)
        self.assertEqual((state["count"], state["total"]), (str(n), str(n)))
        self.assertEqual((state["title"], state["artist"], state["year"]), (x["title"], x["artist"], year(x)))
        self.assertEqual(state["index"], f"{active + 1:02d} / {n:02d}")
        self.assertTrue(state["audioSrc"].endswith("/assets/audio/previews/" + x["preview"]))
        self.assertEqual(state["audioCount"], 1)
        self.assertFalse(state["playing"])
        # A new session asks to play on arrival; without a gesture the browser refuses and it stays paused.
        self.assertEqual([e for e in state["log"] if e.startswith(("play:", "blocked:"))], ["blocked:engine"])
        self.assertEqual(state["toggleLabel"], "Play preview: " + x["title"])
        self.assertEqual([r["current"] for r in state["rows"]].count("true"), 1)
        self.assertEqual([r["state"] for r in state["rows"] if r["current"] == "true"], ["Selected"])

    def test_selecting_a_song_updates_artwork_text_credits_and_audio(self):
        state = self.run_scenario("await click(12); out.s = snapshot();")["s"]
        x = state["data"][12]

        self.assertEqual((state["title"], state["artist"], state["year"]), (x["title"], x["artist"], year(x)))
        self.assertEqual(state["index"], f"13 / {len(state['data']):02d}")
        self.assertEqual(state["art"], "http://test.local/assets/images/" + quote(x["artwork"], safe="-_.!~*'()"))
        self.assertEqual(state["alt"], "Artwork: " + x["title"])
        self.assertEqual(state["type"], "Single")
        self.assertEqual(re.findall(r"<li [^>]*>([^<]*)</li>", state["roles"]), x["roles"])
        self.assertTrue(state["audioSrc"].endswith("/assets/audio/previews/" + x["preview"]))
        self.assertTrue(state["playing"])
        self.assertEqual(state["toggleState"], "playing")
        self.assertEqual(state["toggleLabel"], "Pause preview: " + x["title"])
        current = [(r["index"], r["playing"], r["state"]) for r in state["rows"] if r["current"] == "true"]
        self.assertEqual(current, [(12, True, "Playing")])
        self.assertFalse(any(r["playing"] for r in state["rows"] if r["index"] != 12))
        self.assertIn(x["title"], state["status"])

    def test_only_one_preview_can_sound_at_a_time(self):
        out = self.run_scenario(
            "await click(2); out.a = snapshot();"
            "await click(7); out.b = snapshot();"
            "await playForeign(); out.c = snapshot();"
            "await press('toggle'); out.d = snapshot();"
        )
        a, b, c, d = out["a"], out["b"], out["c"], out["d"]
        self.assertTrue(a["playing"])
        # Changing song pauses the current preview before the new source is assigned.
        tail = b["log"][len(a["log"]):]
        self.assertEqual(tail[0], "pause:engine")
        self.assertTrue(tail[1].startswith("src:engine:") and tail[1].endswith(b["data"][7]["preview"]))
        self.assertEqual(tail[2:], ["play:engine"])
        self.assertEqual([r["index"] for r in b["rows"] if r["playing"]], [7])
        # Another media element starting pauses the player and its visual state follows.
        self.assertTrue(c["foreignPlaying"])
        self.assertFalse(c["playing"])
        self.assertEqual(c["toggleState"], "paused")
        self.assertFalse(any(r["playing"] for r in c["rows"]))
        # Resuming the player pauses the other element again.
        self.assertTrue(d["playing"])
        self.assertFalse(d["foreignPlaying"])
        for state in (a, b, c, d):
            self.assertLessEqual(int(state["playing"]) + int(state["foreignPlaying"]), 1)
            self.assertEqual(state["audioCount"], 1)

    def test_play_pause_and_track_navigation_without_reload(self):
        out = self.run_scenario(
            "await click(0); await press('toggle'); out.start = snapshot();"
            "await press('toggle'); out.a = snapshot();"
            "await press('toggle'); out.b = snapshot();"
            "await press('prev'); out.c = snapshot();"
            "await press('toggle'); await press('next'); out.d = snapshot();"
            "await click(0); out.e = snapshot();"
        )
        last = out["a"]["data"][-1]
        self.assertFalse(out["start"]["playing"])
        self.assertTrue(out["a"]["playing"])
        self.assertEqual(out["a"]["toggleState"], "playing")
        self.assertFalse(out["b"]["playing"])
        self.assertTrue(out["b"]["toggleLabel"].startswith("Play preview: "))
        # Previous from the first song wraps to the last; a paused player stays paused.
        self.assertEqual((out["c"]["title"], out["c"]["artist"]), (last["title"], last["artist"]))
        self.assertFalse(out["c"]["playing"])
        # Next while playing moves on in list order and keeps playing.
        total = len(out["a"]["data"])
        self.assertEqual(out["d"]["index"], f"01 / {total:02d}")
        self.assertTrue(out["d"]["playing"])
        # Clicking the song that is playing pauses it.
        self.assertFalse(out["e"]["playing"])
        self.assertEqual(out["e"]["index"], f"01 / {total:02d}")

    def test_role_filters_and_search(self):
        out = self.run_scenario(
            "await click(0); await press('toggle');"
            "for (const role of ['Artist', 'Producer', 'Composer']) { await filter(role); out[role] = snapshot(); }"
            "await filter('', 'ana guinea'); out.search = snapshot();"
            "await filter('Composer', 'zzz'); out.none = snapshot();"
            "await filter('Composer'); await press('next'); out.step = snapshot();"
            "await filter(''); out.reset = snapshot();"
        )
        data = out["reset"]["data"]
        credit = {"Artist": {"Artist"}, "Producer": {"Producer", "Co-producer"}, "Composer": {"Songwriter", "Co-writer"}}
        for role, needed in credit.items():
            expected = [i for i, x in enumerate(data) if x["role"] == role or needed & set(x["roles"])]
            with self.subTest(role=role):
                self.assertTrue(expected)
                self.assertEqual([r["index"] for r in out[role]["rows"]], expected)
                self.assertEqual(out[role]["count"], str(len(expected)))
        ana = [i for i, x in enumerate(data) if "Ana Guinea" in x["artist"]]
        self.assertEqual([r["index"] for r in out["search"]["rows"]], ana)
        self.assertEqual(out["none"]["rows"], [])
        self.assertFalse(out["none"]["emptyHidden"])
        # The active song stays on stage while filtered out; next jumps to the first visible one.
        self.assertEqual(out["none"]["title"], data[0]["title"])
        composer = [i for i, x in enumerate(data) if {"Songwriter", "Co-writer"} & set(x["roles"])]
        self.assertEqual(out["step"]["title"], data[composer[0]]["title"])
        self.assertEqual(len(out["reset"]["rows"]), len(data))
        self.assertTrue(out["reset"]["emptyHidden"])

    def test_sorting_by_year_and_artist_is_stable_and_keeps_undated_last(self):
        out = self.run_scenario(
            "for (const mode of ['year-desc', 'year-asc', 'artist-asc', 'artist-desc', 'curated']) {"
            " page.change('#sort', mode); await settle(); out[mode] = snapshot(); }"
            "out.nums = page.$$('.pl-num').slice(0, 3).map(n => n.textContent);"
        )
        data = out["curated"]["data"]
        order = lambda mode: [r["index"] for r in out[mode]["rows"]]
        # Approximates the page's Intl.Collator: accents and leading punctuation («¿») do not count.
        title = lambda i: re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFD", data[i]["title"].casefold()))
        dated = [i for i, x in enumerate(data) if x["year"] is not None]
        undated = [i for i, x in enumerate(data) if x["year"] is None]
        for mode, newest in (("year-desc", True), ("year-asc", False)):
            with self.subTest(mode=mode):
                got = order(mode)
                self.assertEqual(len(got), len(data))
                years = [data[i]["year"] for i in got[:len(dated)]]
                self.assertEqual(years, sorted(years, reverse=newest))
                # Undated recordings close the list in both directions.
                self.assertEqual(set(got[len(dated):]), set(undated))
        for mode, reverse in (("artist-asc", False), ("artist-desc", True)):
            with self.subTest(mode=mode):
                artists = [data[i]["artist"].casefold() for i in order(mode)]
                self.assertEqual(artists[0] <= artists[-1], not reverse)
                self.assertEqual(len(order(mode)), len(data))
        self.assertEqual(order("curated"), list(range(len(data))))
        # Ties are broken by title, so the order never depends on chance.
        got = order("year-desc")
        for a, b in zip(got, got[1:]):
            if data[a]["year"] == data[b]["year"]:
                self.assertLessEqual(title(a), title(b))
        self.assertEqual(out["nums"], ["01", "02", "03"])

    def test_artist_mood_and_genre_filters_combine_and_clear(self):
        out = self.run_scenario(
            "const chipState = () => Object.fromEntries(page.$$('.chip').map(c => [c.dataset.group + ':' + c.dataset.id,"
            " [Number(c.querySelector('.chip-count').textContent), c.disabled, c.getAttribute('aria-pressed') === 'true']]));"
            "out.chips = page.$$('.chip').map(c => [c.dataset.group, c.dataset.id]);"
            "page.change('#artist', 'Rogelio Edel'); await settle(); out.artist = snapshot();"
            "page.click('.chip[data-id=\"melancholic\"]'); await settle(); out.mood = snapshot();"
            "page.click('.chip[data-id=\"warm\"]'); await settle(); out.moods = snapshot();"
            "page.click('.chip[data-id=\"pop\"]'); await settle(); out.both = snapshot(); out.state = chipState();"
            "out.clearOn = !$('clear').disabled;"
            "page.click('.chip[data-id=\"rock\"]'); await settle(); out.genres = snapshot();"
            "page.click('.chip[data-id=\"melancholic\"]'); await settle(); out.deselected = snapshot(); out.after = chipState();"
            "await click(out.deselected.rows[0].index); out.play = snapshot();"
            "page.change('#sort', 'year-asc'); await settle(); out.sorted = snapshot();"
            "page.input('#search', 'zzz'); await settle(); out.none = snapshot();"
            "page.click('#reset'); await settle(); out.reset = snapshot(); out.clearAfterReset = !$('clear').disabled;"
            "out.sortKept = $('sort').value; out.pressedAfter = page.$$('.chip[aria-pressed=\"true\"]').length;"
            "page.change('#artist', 'Ana Guinea'); page.click('.chip[data-id=\"pop\"]'); await settle();"
            "page.click('#clear'); await settle(); out.cleared = snapshot(); out.clearOff = $('clear').disabled;"
            "out.sortReset = $('sort').value; out.artistReset = $('artist').value;"
            "out.pressedCleared = page.$$('.chip[aria-pressed=\"true\"]').length;"
        )
        data = out["reset"]["data"]
        ids = lambda state: [r["index"] for r in state["rows"]]
        has = lambda i, group, values: bool(set(data[i][group]) & set(values))
        # Chips come from the data only: every value some recording has, none that it lacks.
        self.assertEqual({tuple(c) for c in out["chips"]},
                         {("mood", m) for x in data for m in x["moods"]} | {("genre", g) for x in data for g in x["genres"]})
        rogelio = [i for i, x in enumerate(data) if "Rogelio Edel" in x["artists"]]
        self.assertEqual(ids(out["artist"]), rogelio)
        # Moods combine with OR among themselves, and with AND with the artist.
        self.assertEqual(ids(out["mood"]), [i for i in rogelio if has(i, "moods", ["melancholic"])])
        moods = [i for i in rogelio if has(i, "moods", ["melancholic", "warm"])]
        self.assertGreater(len(moods), len(ids(out["mood"])))
        self.assertEqual(ids(out["moods"]), moods)
        # Genre and mood combine with AND.
        both = [i for i in moods if has(i, "genres", ["pop"])]
        self.assertTrue(both)
        self.assertEqual(ids(out["both"]), both)
        self.assertEqual(out["both"]["count"], str(len(both)))
        # Each chip counts its recordings among those passing every other filter, its own group aside;
        # a chip is disabled only when selecting it could add nothing.
        pools = {"mood": [i for i in rogelio if has(i, "genres", ["pop"])], "genre": moods}
        for key, (count, disabled, pressed) in out["state"].items():
            group, value = key.split(":")
            with self.subTest(chip=key):
                n = sum(value in data[i][group + "s"] for i in pools[group])
                self.assertEqual(count, n)
                self.assertEqual(disabled, n == 0 and not pressed)
        self.assertEqual(sorted(k for k, v in out["state"].items() if v[2]), ["genre:pop", "mood:melancholic", "mood:warm"])
        self.assertTrue(out["clearOn"])
        # Genres combine with OR among themselves.
        self.assertEqual(ids(out["genres"]), [i for i in moods if has(i, "genres", ["pop", "rock"])])
        # An active chip can be deselected.
        self.assertEqual(ids(out["deselected"]),
                         [i for i in rogelio if has(i, "moods", ["warm"]) and has(i, "genres", ["pop", "rock"])])
        self.assertFalse(out["after"]["mood:melancholic"][2])
        # Playback works on a filtered list and survives re-sorting.
        self.assertTrue(out["play"]["playing"])
        self.assertEqual(out["play"]["title"], data[ids(out["deselected"])[0]]["title"])
        self.assertEqual((out["sorted"]["title"], out["sorted"]["playing"]), (out["play"]["title"], True))
        self.assertEqual(out["none"]["rows"], [])
        self.assertFalse(out["none"]["emptyHidden"])
        # «Show all recordings» restores the whole catalogue and keeps the chosen order, so Reset all stays available.
        self.assertEqual(len(out["reset"]["rows"]), len(data))
        self.assertTrue(out["reset"]["emptyHidden"])
        self.assertEqual((out["sortKept"], out["pressedAfter"]), ("year-asc", 0))
        self.assertTrue(out["clearAfterReset"])
        # Reset all returns filters, search and order to the initial curated state.
        self.assertEqual(ids(out["cleared"]), list(range(len(data))))
        self.assertEqual((out["sortReset"], out["artistReset"], out["pressedCleared"]), ("curated", "", 0))
        self.assertTrue(out["clearOff"])

    def test_unreleased_recording_shows_type_version_and_no_year(self):
        # A synthetic unreleased row appended to a temporary copy of the front end: the page must
        # render it without a year, with its type and version, and the Composer filter must find
        # a co-writing credit.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for top in ("music", "js", "css"):
                shutil.copytree(ROOT / top, Path(tmp) / top)
            data = Path(tmp) / "js" / "music-data.js"
            text = data.read_text(encoding="utf-8")
            row = ("  { title:'Synthetic', artist:'Luis Guinea', role:'Composer', artwork:'generic-cover.webp', "
                   "releaseType:'Unreleased', year:null, roles:['Co-writer'], "
                   "preview:'hace-tanto-tiempo--luis-guinea--2021.mp3', spotify:null, appleMusic:null, "
                   "version:'RoughMix', youtube:null, soundcloud:null }")
            data.write_text(text.replace("\n];", ",\n" + row + "\n];"), encoding="utf-8")
            scenario = (
                "const last = rows().length - 1; await click(last); out.s = snapshot();"
                "out.meta = page.document.querySelector('.np-meta').textContent;"
                "out.yearHidden = $('np-year-field').hidden; out.versionHidden = $('np-version-field').hidden;"
                "out.line = rows()[last].querySelector('.pl-artist').textContent;"
                "out.cell = rows()[last].querySelector('.pl-year').textContent;"
                "out.links = $('np-links-field').hidden;"
                "await filter('Composer'); out.composer = snapshot();"
                "page.click('[data-lang=es]'); await settle(); out.es = page.document.querySelector('.np-meta').textContent;"
            )
            result = subprocess.run([NODE, str(RUNNER), tmp, PRELUDE + scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["s"]["title"], "Synthetic")
        self.assertEqual((out["s"]["year"], out["yearHidden"], out["versionHidden"]), ("", True, False))
        self.assertEqual(out["s"]["type"], "Unreleased")
        self.assertIn("Rough mix", out["meta"])
        self.assertEqual(out["line"], "Luis Guinea · Unreleased · Rough mix")
        self.assertEqual(out["cell"], "")
        self.assertTrue(out["links"])
        self.assertIn(len(out["composer"]["data"]) - 1, [r["index"] for r in out["composer"]["rows"]])
        self.assertIn("Inédita", out["es"])
        self.assertIn("Mezcla preliminar", out["es"])

    def test_language_switch_translates_player_labels_and_credits(self):
        out = self.run_scenario(
            "await click(4); out.en = snapshot(); page.click('[data-lang=\"es\"]'); await settle(); out.es = snapshot();"
            "await filter('', 'productor'); out.search = snapshot();"
        )
        en, es = out["en"], out["es"]
        x = es["data"][4]
        self.assertEqual(en["toggleLabel"], "Pause preview: " + x["title"])
        self.assertEqual(es["toggleLabel"], "Pausar fragmento: " + x["title"])
        self.assertEqual((es["prevLabel"], es["nextLabel"]), ("Canción anterior", "Canción siguiente"))
        self.assertEqual(es["alt"], "Portada: " + x["title"])
        self.assertEqual(es["type"], "Sencillo")
        self.assertEqual(re.findall(r"<li [^>]*>([^<]*)</li>", es["roles"]), ["Artista"])
        self.assertEqual([r["state"] for r in es["rows"] if r["current"] == "true"], ["Sonando"])
        self.assertTrue(es["status"].startswith("Sonando: "))
        # The song, audio and playback state survive the language switch untouched.
        self.assertEqual((es["title"], es["audioSrc"], es["playing"]), (en["title"], en["audioSrc"], True))
        # Search also matches translated credit labels («productor» is also inside «Coproductor»).
        producers = [i for i, x in enumerate(es["data"]) if {"Producer", "Co-producer"} & set(x["roles"])]
        self.assertEqual([r["index"] for r in out["search"]["rows"]], producers)


if __name__ == "__main__":
    unittest.main()
