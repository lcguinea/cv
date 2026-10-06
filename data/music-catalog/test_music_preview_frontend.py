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
        for fragment in ('id="toggle" class="ctl ctl-play" type="button"',
                         'id="prev" class="ctl" type="button" data-i18n-label="music.previous"',
                         'id="next" class="ctl" type="button" data-i18n-label="music.next"',
                         'role="group" data-i18n-label="music.controls"',
                         '<label class="sr-only" for="seek" data-i18n="music.seek"></label>',
                         '<label for="np-volume" data-i18n="player.volume">',
                         'role="status" aria-live="polite"',
                         '<label class="sr-only" for="role" data-i18n="music.roleFilter"></label>'):
            self.assertIn(fragment, self.html)
        self.assertIn("row.setAttribute('aria-current',String(current))", MUSIC_PAGE.read_text(encoding="utf-8"))
        self.assertNotRegex(self.html, r'<svg (?![^>]*aria-hidden="true")')

    def test_visible_text_is_bound_to_i18n(self):
        body = self.html[self.html.index("<body"):self.html.index("<script src=")]
        bound = r'<(\w+)\b[^>]*\bdata-i18n="[^"]+"[^>]*>[^<]*</\1>'
        texts = {text.strip() for text in re.findall(r">([^<]+)<", re.sub(bound, "", body)) if text.strip()}
        # Brand mark, language codes, separators and the initial counters are not translatable.
        self.assertLessEqual(texts, {"LUIS GUINEA", "/ MUSIC", "EN", "ES", "·", "/", "0", "0:00"})

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
        english = node_json("window.STRINGS.en.music", STRINGS_JS)
        spanish = node_json("window.STRINGS.es.music", STRINGS_JS)
        self.assertEqual(set(english), set(spanish))
        self.assertLessEqual(used, set(english))
        for key in used:
            self.assertTrue(english[key].strip() and spanish[key].strip(), key)


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

        self.assertEqual(len(state["rows"]), 16)
        self.assertEqual((state["count"], state["total"]), ("16", "16"))
        self.assertEqual((state["title"], state["artist"], state["year"]), (x["title"], x["artist"], str(x["year"])))
        self.assertEqual(state["index"], f"{active + 1:02d} / 16")
        self.assertTrue(state["audioSrc"].endswith("/assets/audio/previews/" + x["preview"]))
        self.assertEqual(state["audioCount"], 1)
        self.assertFalse(state["playing"])
        self.assertFalse([e for e in state["log"] if e.startswith(("play:", "blocked:"))])
        self.assertEqual(state["toggleLabel"], "Play preview: " + x["title"])
        self.assertEqual([r["current"] for r in state["rows"]].count("true"), 1)
        self.assertEqual([r["state"] for r in state["rows"] if r["current"] == "true"], ["Selected"])

    def test_selecting_a_song_updates_artwork_text_credits_and_audio(self):
        state = self.run_scenario("await click(12); out.s = snapshot();")["s"]
        x = state["data"][12]

        self.assertEqual((state["title"], state["artist"], state["year"]), (x["title"], x["artist"], str(x["year"])))
        self.assertEqual(state["index"], "13 / 16")
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
        self.assertEqual(out["d"]["index"], "01 / 16")
        self.assertTrue(out["d"]["playing"])
        # Clicking the song that is playing pauses it.
        self.assertFalse(out["e"]["playing"])
        self.assertEqual(out["e"]["index"], "01 / 16")

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
        credit = {"Artist": "Artist", "Producer": "Producer", "Composer": "Songwriter"}
        for role, needed in credit.items():
            expected = [i for i, x in enumerate(data) if x["role"] == role or needed in x["roles"]]
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
        composer = [i for i, x in enumerate(data) if "Songwriter" in x["roles"]]
        self.assertEqual(out["step"]["title"], data[composer[0]]["title"])
        self.assertEqual(len(out["reset"]["rows"]), 16)
        self.assertTrue(out["reset"]["emptyHidden"])

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
        # Search also matches translated credit labels.
        producers = [i for i, x in enumerate(es["data"]) if "Producer" in x["roles"]]
        self.assertEqual([r["index"] for r in out["search"]["rows"]], producers)


if __name__ == "__main__":
    unittest.main()
