#!/usr/bin/env python3
"""Focused tests for the global music engine (js/player.js) and its bottom bar on Home, CV and Music.

The real pages run with their real scripts in tests/support/minidom.js. Media elements there refuse
playback without a user gesture unless a page is opened with `autoplayBlocked: false`, and an element
the user started once may keep playing, as in browsers. Math.random is fed from `browser.randomQueue`
(0.5 when empty), so random choices are deterministic. Requires Node.js; standard library only.

Run: python3 -m unittest tests/test_global_player.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
PAGES = ("index.html", "cv.html", "music/index.html")
NODE = shutil.which("node")

PRELUDE = r"""
const state = page => ({
  index: page.eval('LGPlayer.index()'), title: page.eval('LGPlayer.current().title'),
  playing: !page.audio().paused, time: page.eval('LGPlayer.time()'), src: page.audio().src,
  created: page.created.length, markupAudio: page.$$('audio').length,
  log: page.log.slice(), session: JSON.parse(page.tab.session['lg-player'] || 'null'),
  bar: page.$('#mini-player') && {hidden: page.$('#mini-player').hidden, title: page.$('#mp-title').textContent,
    artist: page.$('#mp-artist').textContent, art: page.$('#mp-art').src,
    toggle: page.$('#mp-toggle').getAttribute('aria-label'), toggleState: page.$('#mp-toggle').dataset.state,
    mute: page.$('#mp-mute').getAttribute('aria-pressed'), volume: page.$('#mp-volume').value,
    volumeMode: page.$('#mini-player').dataset.volume || '', status: page.$('#mp-status').textContent,
    link: page.$('#mp-link').getAttribute('href')},
  data: page.eval('MUSIC_DATA.map(x => x.title)'),
});
"""


@unittest.skipUnless(NODE, "node not installed")
class GlobalPlayerTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), PRELUDE + scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_every_page_has_one_engine_audio_and_no_sound_on_arrival(self):
        out = self.run_scenario(
            "for (const rel of %s) { const page = browser.tab().open(rel); await settle(); out[rel] = state(page); }"
            % json.dumps(PAGES)
        )
        for rel in PAGES:
            with self.subTest(page=rel):
                s = out[rel]
                self.assertEqual((s["created"], s["markupAudio"]), (1, 0))
                self.assertFalse(s["playing"])
                self.assertFalse([e for e in s["log"] if e.startswith(("play:", "blocked:"))])
                self.assertEqual(s["session"]["playing"], False)
                self.assertEqual(s["bar"]["title"], s["title"])
                self.assertEqual(s["bar"]["toggleState"], "paused")
                self.assertEqual(s["bar"]["toggle"], "Play preview: " + s["title"])
        # Bar link goes to Music from Home and CV; on Music it points to the large player.
        self.assertEqual(out["index.html"]["bar"]["link"], "music/")
        self.assertEqual(out["cv.html"]["bar"]["link"], "music/")
        self.assertEqual(out["music/index.html"]["bar"]["link"], "#player")
        self.assertFalse(out["index.html"]["bar"]["hidden"])
        self.assertFalse(out["cv.html"]["bar"]["hidden"])

    def test_a_new_session_starts_on_a_random_track(self):
        out = self.run_scenario(
            "for (const r of [0, 0.5, 0.99]) { browser.randomQueue.push(r);"
            "  const page = browser.tab().open('index.html'); await settle(); out[r] = state(page).index; }"
        )
        self.assertEqual((out["0"], out["0.5"], out["0.99"]), (0, 8, 15))

    def test_the_session_track_is_kept_while_navigating_in_the_tab(self):
        out = self.run_scenario(
            "browser.randomQueue.push(0.25); const tab = browser.tab();"
            "for (const rel of %s) { const page = tab.open(rel); await settle(); out[rel] = state(page).index; }"
            % json.dumps(PAGES)
        )
        self.assertEqual(set(out.values()), {4})

    def test_a_finished_preview_moves_to_another_random_track_without_repeating(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "page.click('#mp-toggle'); await settle(); out.steps = [];"
            "for (const r of [0, 0.2, 0.47, 0.5, 0.53, 0.8, 0.999]) {"
            "  const before = state(page).index; browser.randomQueue.push(r);"
            "  page.audio().loadMetadata(40); page.audio().finish(); await settle();"
            "  const after = state(page); out.steps.push([before, after.index, after.playing]); }"
        )
        for before, after, playing in out["steps"]:
            self.assertNotEqual(before, after)
            self.assertTrue(0 <= after < 16)
            self.assertTrue(playing, "the next preview keeps playing after `ended`")

    def test_next_picks_another_track_and_keeps_the_play_state(self):
        out = self.run_scenario(
            "const page = browser.tab().open('cv.html'); await settle(); out.a = state(page);"
            "browser.randomQueue.push(0.5); page.click('#mp-next'); await settle(); out.b = state(page);"
            "page.click('#mp-toggle'); await settle();"
            "browser.randomQueue.push(0); page.click('#mp-next'); await settle(); out.c = state(page);"
        )
        a, b, c = out["a"], out["b"], out["c"]
        self.assertNotEqual(a["index"], b["index"])
        self.assertFalse(b["playing"])
        self.assertEqual(b["bar"]["title"], b["title"])
        self.assertNotEqual(b["index"], c["index"])
        self.assertTrue(c["playing"])
        self.assertEqual(c["bar"]["toggle"], "Pause preview: " + c["title"])

    def test_playback_resumes_at_the_same_position_after_a_page_change_when_allowed(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const home = tab.open('index.html'); await settle();"
            "home.click('#mp-toggle'); await settle(); home.audio().loadMetadata(40); home.audio().advance(12.5); await settle();"
            "out.home = state(home);"
            "const cv = tab.open('cv.html', {autoplayBlocked: false}); await settle(); out.cvBefore = state(cv);"
            "cv.audio().loadMetadata(40); await settle(); out.cv = state(cv); out.cvTime = cv.audio().currentTime;"
        )
        home, before, cv = out["home"], out["cvBefore"], out["cv"]
        self.assertTrue(home["playing"])
        self.assertEqual(home["session"]["preview"].split(".")[0], home["src"].rsplit("/", 1)[1].split(".")[0])
        self.assertEqual(cv["src"], home["src"])
        self.assertIn("play:engine", before["log"])
        self.assertTrue(cv["playing"])
        self.assertEqual(out["cvTime"], 12.5)
        self.assertEqual(cv["bar"]["toggleState"], "playing")

    def test_a_refused_resume_keeps_the_position_and_shows_paused(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const home = tab.open('index.html'); await settle();"
            "home.click('#mp-toggle'); await settle(); home.audio().loadMetadata(40); home.audio().advance(7.25); await settle();"
            "const music = tab.open('music/index.html'); await settle(); out.music = state(music);"
            "out.seek = music.$('#seek').value; out.np = music.$('#time-current').textContent;"
            "out.npState = music.$('#toggle').dataset.state; out.npStatus = music.$('#np-status').textContent;"
        )
        s = out["music"]
        self.assertIn("blocked:engine", s["log"])
        self.assertNotIn("play:engine", s["log"])
        self.assertFalse(s["playing"])
        self.assertEqual(s["time"], 7.25)
        self.assertEqual(s["session"]["time"], 7.25)
        self.assertEqual(s["session"]["playing"], False)
        self.assertEqual(out["seek"], "7.25")
        self.assertEqual(out["np"], "0:07")
        self.assertEqual(out["npState"], "paused")
        # A refusal is not an error: no failure message, just the paused state.
        self.assertTrue(out["npStatus"].startswith("Paused: "))
        self.assertEqual(s["bar"]["toggleState"], "paused")

    def test_a_paused_player_stays_paused_and_a_new_tab_never_resumes(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const home = tab.open('index.html'); await settle();"
            "home.click('#mp-toggle'); await settle(); home.audio().loadMetadata(40); home.audio().advance(3);"
            "home.click('#mp-toggle'); await settle();"
            "const cv = tab.open('cv.html', {autoplayBlocked: false}); await settle(); out.paused = state(cv);"
            "cv.click('#mp-toggle'); await settle();"
            "const copy = browser.tab({session: tab.session}); const other = copy.open('index.html', {autoplayBlocked: false});"
            "await settle(); out.copy = state(other);"
        )
        self.assertFalse([e for e in out["paused"]["log"] if e.startswith(("play:", "blocked:"))])
        self.assertEqual(out["paused"]["time"], 3)
        # A new tab inherits a copy of sessionStorage but not window.name: same track, no attempt to sound.
        self.assertFalse([e for e in out["copy"]["log"] if e.startswith(("play:", "blocked:"))])
        self.assertEqual(out["copy"]["title"], out["paused"]["title"])

    def test_back_forward_cache_restores_the_latest_track_position_and_state(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const home = tab.open('index.html'); await settle();"
            "home.click('#mp-toggle'); await settle(); home.audio().loadMetadata(40); home.audio().advance(2); await settle();"
            "const cv = tab.open('cv.html', {autoplayBlocked: false}); await settle(); cv.audio().loadMetadata(40);"
            "browser.randomQueue.push(0.9); cv.click('#mp-next'); await settle(); cv.audio().loadMetadata(40); cv.audio().advance(5); await settle();"
            "out.cv = state(cv); home.autoplayBlocked = false; tab.back(home); await settle(); out.back = state(home);"
            "home.audio().loadMetadata(40); out.time = home.audio().currentTime;"
            "home.click('#mp-toggle'); await settle(); const again = tab.open('cv.html', {autoplayBlocked: false}); await settle();"
            "tab.back(home); await settle(); out.paused = state(home);"
        )
        self.assertTrue(out["cv"]["playing"])
        self.assertEqual(out["back"]["title"], out["cv"]["title"])
        self.assertTrue(out["back"]["playing"])
        self.assertEqual(out["time"], 5)
        self.assertEqual(out["back"]["bar"]["title"], out["cv"]["title"])
        # Paused before leaving: it comes back paused.
        self.assertFalse(out["paused"]["playing"])

    def test_volume_and_mute_persist_in_local_storage(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle();"
            "page.input('#mp-volume', '0.3'); page.click('#mp-mute'); await settle();"
            "out.local = Object.assign({}, browser.local); out.first = state(page);"
            "const next = browser.tab().open('music/index.html'); await settle(); out.next = state(next);"
            "out.volume = next.audio().volume; out.muted = next.audio().muted; out.np = next.$('#np-volume').value;"
            "next.input('#np-volume', '0.6'); await settle(); out.after = [next.audio().volume, next.audio().muted, browser.local['lg-volume']];"
            "const ios = browser.tab().open('cv.html', {fixedVolume: true}); await settle(); out.ios = state(ios);"
        )
        self.assertEqual(out["local"]["lg-volume"], "0.3")
        self.assertEqual(out["local"]["lg-muted"], "1")
        self.assertEqual(out["first"]["bar"]["mute"], "true")
        self.assertEqual((out["volume"], out["muted"]), (0.3, True))
        self.assertEqual(out["next"]["bar"]["mute"], "true")
        self.assertEqual(out["np"], "0")
        # Raising the volume unmutes.
        self.assertEqual(out["after"], [0.6, False, "0.6"])
        # Where the volume cannot be set (iOS), the slider is hidden and mute remains.
        self.assertEqual(out["ios"]["bar"]["volumeMode"], "fixed")

    def test_only_one_tab_sounds_at_a_time(self):
        out = self.run_scenario(
            "const a = browser.tab().open('index.html'); const b = browser.tab().open('music/index.html'); await settle();"
            "a.click('#mp-toggle'); await settle(); out.a1 = state(a).playing;"
            "b.click('#toggle'); await settle(); out.a2 = state(a).playing; out.b2 = state(b).playing;"
            "a.click('#mp-toggle'); await settle(); out.a3 = state(a).playing; out.b3 = state(b).playing;"
            "out.aSession = state(a).session.playing;"
        )
        self.assertTrue(out["a1"])
        self.assertEqual((out["a2"], out["b2"]), (False, True))
        self.assertEqual((out["a3"], out["b3"]), (True, False))
        self.assertTrue(out["aSession"])

    def test_media_session_metadata_and_actions(self):
        out = self.run_scenario(
            "const page = browser.tab().open('cv.html'); await settle(); const ms = page.mediaSession;"
            "out.meta = Object.assign({}, ms.metadata); out.actions = Object.keys(ms.handlers).sort(); out.state0 = ms.playbackState;"
            "page.click('#mp-toggle'); await settle(); out.state1 = ms.playbackState;"
            "ms.handlers.pause(); await settle(); out.state2 = [ms.playbackState, state(page).playing];"
            "browser.randomQueue.push(0); ms.handlers.nexttrack(); await settle(); out.next = [state(page).title, ms.metadata.title];"
            "out.title = state(page).title;"
            "const plain = browser.tab().open('index.html', {mediaSession: false}); await settle(); out.plain = state(plain).created;"
        )
        self.assertEqual(out["actions"], ["nexttrack", "pause", "play", "seekto"])
        self.assertEqual(out["meta"]["album"], "Luis Guinea")
        self.assertTrue(out["meta"]["artwork"][0]["src"].startswith("http://test.local/assets/images/"))
        self.assertEqual((out["state0"], out["state1"]), ("paused", "playing"))
        self.assertEqual(out["state2"], ["paused", False])
        self.assertEqual(out["next"][0], out["next"][1])
        self.assertEqual(out["plain"], 1)

    def test_bar_hides_while_the_large_player_is_in_view_on_music(self):
        out = self.run_scenario(
            "const page = browser.tab().open('music/index.html'); await settle(); out.a = page.$('#mini-player').hidden;"
            "page.observers[0].trigger(false); out.b = page.$('#mini-player').hidden;"
            "page.observers[0].trigger(true); out.c = page.$('#mini-player').hidden;"
            "out.status = page.$('#mp-status').textContent;"
            "page.click('#toggle'); await settle(); out.status2 = page.$('#mp-status').textContent;"
        )
        self.assertEqual((out["a"], out["b"], out["c"]), (True, False, True))
        # The large player announces playback on Music; the bar stays silent there.
        self.assertEqual((out["status"], out["status2"]), ("", ""))

    def test_bar_labels_follow_the_language(self):
        out = self.run_scenario(
            "const page = browser.tab().open('index.html'); await settle(); page.click('[data-lang=\"es\"]'); await settle();"
            "out.es = state(page); out.region = page.$('#mini-player').getAttribute('aria-label');"
            "out.next = page.$('#mp-next').getAttribute('aria-label'); out.mute = page.$('#mp-mute').getAttribute('aria-label');"
            "out.link = page.$('#mp-link').textContent;"
            "page.click('#mp-toggle'); await settle(); out.status = page.$('#mp-status').textContent;"
        )
        self.assertEqual(out["es"]["bar"]["toggle"], "Reproducir fragmento: " + out["es"]["title"])
        self.assertEqual((out["region"], out["next"], out["mute"], out["link"]),
                         ("Reproductor de música", "Canción siguiente", "Silenciar", "Música"))
        self.assertTrue(out["status"].startswith("Sonando: "))

    def test_an_unknown_saved_track_falls_back_to_a_random_one(self):
        out = self.run_scenario(
            "browser.randomQueue.push(0.1);"
            "const tab = browser.tab({session: {'lg-player': JSON.stringify({preview: 'gone.mp3', time: 9, playing: true})}});"
            "const page = tab.open('index.html', {autoplayBlocked: false}); await settle(); out.s = state(page);"
        )
        self.assertEqual(out["s"]["index"], 1)
        self.assertFalse(out["s"]["playing"])
        self.assertEqual(out["s"]["time"], 0)


class GlobalPlayerStaticTests(unittest.TestCase):
    def test_pages_load_the_engine_once_and_have_no_audio_markup(self):
        for rel in PAGES:
            html = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertEqual(re.findall(r"<audio\b", html), [])
                self.assertNotRegex(html, r"(?i)\bautoplay\b")
                scripts = re.findall(r'<script src="([^"]+)"', html)
                self.assertEqual([s.rsplit("/", 1)[1] for s in scripts].count("player.js"), 1)
                self.assertLess(scripts.index(next(s for s in scripts if s.endswith("music-data.js"))),
                                scripts.index(next(s for s in scripts if s.endswith("player.js"))))
                bar = re.search(r'<div id="mini-player"[^>]*>', html).group(0)
                self.assertIn('role="region"', bar)
                self.assertIn("hidden", bar)
                for control in ('id="mp-toggle"', 'id="mp-next"', 'id="mp-mute"', 'id="mp-volume"', 'id="mp-link"'):
                    self.assertIn(control, html)
        css = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".mp-btn{display:inline-grid;place-items:center;width:44px;height:44px;", css)
        self.assertIn("@media print{.mini-player{display:none}html.js body{padding-bottom:0}}", css)


if __name__ == "__main__":
    unittest.main()
