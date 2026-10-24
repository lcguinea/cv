#!/usr/bin/env python3
"""Focused tests for playing what a shared link into /music/ points at: one recording (?song=<work id>) opens the large
player on it and tries to start it; filters (q, artist, credit, mood, genre) become the queue that Next, Previous, the end
of a preview and the random picks stay in. When the browser refuses sound without a gesture, a Play button waits on the
cover or beside the results and its first press plays the right recording.

The real page runs with its real scripts in tests/support/minidom.js. Pages refuse playback without a gesture unless
opened with `autoplayBlocked: false`; `navigation: 'reload'` opens a page the way a reload does. The layout on desktop
and phone is checked in a real browser; here the markup and styles it relies on are checked statically.
Requires Node.js; standard library only.

Run: python3 -m unittest tests/test_music_link_playback.py
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
PREVIEWS = re.findall(r"preview:'([^']+)\.mp3'", (ROOT / "js" / "music-data.js").read_text(encoding="utf-8"))
SONG = "como-decirte--luis-guinea--2022"

PRELUDE = r"""
const BASE = 'music/index.html';
const open = (query, options, tab) => (tab || browser.tab()).open(BASE + (query || ''), options);
const rows = page => page.$$('#catalog .pl-row').map(r => Number(r.dataset.index));
const state = page => ({
  url: page.location.pathname + page.location.search + page.location.hash,
  current: page.eval('LGPlayer.index()'), playing: !page.audio().paused, queue: page.eval('LGPlayer.queue()'),
  rows: rows(page), attempts: page.log.filter(e => e.startsWith('play:') || e.startsWith('blocked:')),
  sources: page.log.filter(e => e.startsWith('src:engine:')).map(e => e.split('/').pop().replace('.mp3', '')),
  songButton: page.$('#np-start').hidden ? null : page.$('#np-start').getAttribute('aria-label'),
  selectionButton: page.$('#play-selection').hidden ? null : page.$('#play-selection').getAttribute('aria-label'),
  status: page.$('#np-status').textContent, notice: page.$('#link-notice').hidden ? '' : page.$('#link-notice').textContent,
  prevDisabled: page.$('#prev').disabled, nextDisabled: page.$('#next').disabled,
  session: JSON.parse(page.tab.session['lg-player'] || 'null'),
});
// Plays the current preview to its end `n` times and records which recording followed each time.
const finish = async (page, n) => { const seen = []; for (let k = 0; k < n; k++) { page.audio().finish(); await settle(); seen.push(page.eval('LGPlayer.index()')); } return seen; };
"""


@unittest.skipUnless(NODE, "node not installed")
class MusicLinkPlaybackTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), PRELUDE + scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_a_song_link_starts_exactly_that_recording_when_the_browser_allows_it(self):
        out = self.run_scenario(
            "const page = open('?song=%s', {autoplayBlocked: false}); await settle(); out.open = state(page);"
            "page.window._fire('load'); await settle(); out.scrolled = page.scrolled; out.focus = page.document.activeElement.id;"
            "out.title = page.$('#np-title').textContent; out.data = page.eval('MUSIC_DATA[%d].title');" % (SONG, PREVIEWS.index(SONG))
        )
        i, s = PREVIEWS.index(SONG), out["open"]
        # One source, one request: no other recording is loaded or played before it.
        self.assertEqual((s["sources"], s["attempts"], s["playing"], s["current"]), ([SONG], ["play:engine"], True, i))
        self.assertEqual((s["songButton"], s["selectionButton"]), (None, None))
        self.assertTrue(s["status"].startswith("Playing: "))
        # The large player shows it, in view, with the focus on Play/Pause.
        self.assertEqual(out["title"], out["data"])
        self.assertEqual([x["id"] for x in out["scrolled"]], ["player"])
        self.assertEqual(out["focus"], "toggle")
        # Without filters in the link the whole catalogue follows it.
        self.assertIsNone(s["queue"])

    def test_a_refused_song_link_waits_on_that_recording_and_one_press_plays_it(self):
        out = self.run_scenario(
            "const page = open('?song=%s'); await settle(); out.open = state(page);"
            "page.click('.chip[data-id=\"pop\"]'); await settle(); out.chip = state(page);"
            "page.click('#np-start'); await settle(); out.play = state(page);"
            "const es = open('?song=%s', {languages: ['es-ES']}); await settle(); out.es = state(es);"
            "const bar = open('?song=%s'); await settle(); bar.click('#mp-toggle'); await settle(); out.bar = state(bar);" % (SONG, SONG, SONG)
        )
        i, s = PREVIEWS.index(SONG), out["open"]
        self.assertEqual((s["sources"], s["attempts"], s["playing"], s["current"]), ([SONG], ["blocked:engine"], False, i))
        self.assertTrue(s["songButton"].startswith("Play preview: C"))
        self.assertEqual(s["status"], "Your browser did not let playback start on its own. Press play to listen.")
        # No implicit start: a click elsewhere on the page (a filter) plays nothing.
        self.assertEqual((out["chip"]["attempts"], out["chip"]["playing"]), (["blocked:engine"], False))
        # The button on the cover plays that recording on the first press and then goes away.
        self.assertEqual((out["play"]["attempts"], out["play"]["playing"], out["play"]["current"]), (["blocked:engine", "play:engine"], True, i))
        self.assertEqual((out["play"]["songButton"], out["play"]["status"].startswith("Playing: ")), (None, True))
        self.assertTrue(out["es"]["songButton"].startswith("Reproducir fragmento: "))
        self.assertTrue(out["es"]["status"].startswith("Tu navegador no permitió"))
        # Play in the bottom bar does the same.
        self.assertEqual((out["bar"]["attempts"], out["bar"]["current"], out["bar"]["playing"]), (["blocked:engine", "play:engine"], i, True))

    def test_a_filter_link_queues_its_results_and_starts_the_first_one(self):
        out = self.run_scenario(
            "out.cases = {};"
            "for (const query of ['?genre=rock', '?mood=warm&genre=pop', '?artist=Ana%20Guinea', '?credit=producer&q=amor']) {"
            "  const page = open(query, {autoplayBlocked: false}); await settle(); page.window._fire('load'); await settle();"
            "  out.cases[query] = Object.assign(state(page), {scrolled: page.scrolled.map(x => x.id)});"
            "  out.previews = page.eval('MUSIC_DATA.map(x => x.preview)'); }"
        )
        for query, s in out["cases"].items():
            with self.subTest(query=query):
                self.assertTrue(s["rows"])
                self.assertEqual(sorted(s["queue"]), sorted(s["rows"]))
                self.assertEqual((s["current"], s["playing"], s["attempts"]), (s["rows"][0], True, ["play:engine"]))
                self.assertEqual(s["sources"][-1], s["session"]["preview"].replace(".mp3", ""))
                self.assertEqual(s["session"]["preview"], out["previews"][s["rows"][0]])
                self.assertEqual(s["scrolled"], ["playlist-heading"])
                self.assertEqual(s["selectionButton"], None)

    def test_a_refused_filter_link_prepares_the_selection_and_one_press_starts_it(self):
        out = self.run_scenario(
            "const page = open('?mood=warm&genre=pop'); await settle(); out.open = state(page);"
            "page.click('#play-selection'); await settle(); out.play = state(page);"
            "const es = open('?mood=warm', {languages: ['es-MX']}); await settle(); out.es = state(es);"
        )
        s = out["open"]
        self.assertEqual((s["current"], s["playing"], s["attempts"]), (s["rows"][0], False, ["blocked:engine"]))
        self.assertEqual(sorted(s["queue"]), sorted(s["rows"]))
        self.assertEqual(s["selectionButton"], f"Play selection: {len(s['rows'])} recordings")
        self.assertEqual(s["songButton"], None)
        self.assertTrue(s["notice"].endswith(f"to listen to these {len(s['rows'])} recordings."))
        self.assertEqual((out["play"]["current"], out["play"]["playing"]), (s["rows"][0], True))
        self.assertEqual(out["play"]["attempts"], ["blocked:engine", "play:engine"])
        self.assertEqual((out["play"]["selectionButton"], out["play"]["notice"]), (None, ""))
        self.assertEqual(out["es"]["selectionButton"], f"Reproducir selección: {len(out['es']['rows'])} grabaciones")

    def test_next_previous_and_the_end_of_a_preview_stay_in_the_selection(self):
        out = self.run_scenario(
            "browser.randomQueue = Array.from({length: 200}, (x, k) => (k * 0.37) % 1);"
            "const page = open('?genre=pop', {autoplayBlocked: false}); await settle(); out.rows = rows(page);"
            "out.next = []; for (let k = 0; k < out.rows.length + 2; k++) { page.click('#next'); await settle(); out.next.push(page.eval('LGPlayer.index()')); }"
            "out.prev = []; for (let k = 0; k < 3; k++) { page.click('#prev'); await settle(); out.prev.push(page.eval('LGPlayer.index()')); }"
            "out.ended = await finish(page, out.rows.length * 2);"
            "out.bar = []; for (let k = 0; k < 10; k++) { page.click('#mp-next'); await settle(); out.bar.push(page.eval('LGPlayer.index()')); }"
            "out.playing = !page.audio().paused; out.genres = page.eval('MUSIC_DATA.map(x => x.genres || [])');"
        )
        rows = out["rows"]
        # Next and Previous follow the list as shown and wrap around inside it.
        self.assertEqual(out["next"], rows[1:] + rows[:3])
        self.assertEqual(out["prev"], [rows[1], rows[0], rows[-1]])
        # Continuous play is a shuffle of the results only: each one plays once before any repeats.
        self.assertEqual(sorted(out["ended"][:len(rows)]), sorted(rows))
        self.assertTrue(set(out["ended"]) <= set(rows))
        self.assertTrue(set(out["bar"]) <= set(rows))
        self.assertTrue(out["playing"])

    def test_orchestral_results_join_random_play_in_a_selection_but_not_in_the_whole_catalogue(self):
        out = self.run_scenario(
            "browser.randomQueue = Array.from({length: 400}, (x, k) => (k * 0.37) % 1);"
            "const page = open('?genre=pop', {autoplayBlocked: false}); await settle(); out.rows = rows(page);"
            "out.genres = page.eval('MUSIC_DATA.map(x => x.genres || [])');"
            "out.ended = await finish(page, out.rows.length);"
            "out.bar = []; for (let k = 0; k < out.rows.length; k++) { page.click('#mp-next'); await settle(); out.bar.push(page.eval('LGPlayer.index()')); }"
            "page.click('#clear'); await settle(); out.queue = page.eval('LGPlayer.queue()');"
            "out.whole = await finish(page, 80);"
        )
        rows, genres = out["rows"], out["genres"]
        orchestral = [i for i in rows if "cinematic_classical" in genres[i]]
        # The pop selection mixes orchestral and other pieces. The first result already played, so the round of the
        # shuffle that follows it plays every other result once, the orchestral ones included.
        self.assertTrue(orchestral)
        self.assertLess(len(orchestral), len(rows))
        self.assertNotIn(rows[0], orchestral)
        self.assertEqual(sorted(out["ended"][:len(rows) - 1]), sorted(rows[1:]))
        self.assertTrue(set(orchestral) <= set(out["ended"]))
        self.assertTrue(set(out["bar"]) <= set(rows))
        # Without filters, random play keeps leaving orchestral pieces out.
        self.assertIsNone(out["queue"])
        self.assertFalse([i for i in out["whole"] if "cinematic_classical" in genres[i]])

    def test_random_play_in_a_selection_of_orchestral_pieces_stays_among_them(self):
        out = self.run_scenario(
            "const page = open('?genre=cinematic_classical', {autoplayBlocked: false}); await settle(); out.rows = rows(page);"
            "out.ended = await finish(page, 6);"
            "page.click('#clear'); await settle(); out.queue = page.eval('LGPlayer.queue()');"
            "out.after = await finish(page, 12); out.genres = page.eval('MUSIC_DATA.map(x => x.genres || [])');"
        )
        self.assertTrue(out["rows"])
        self.assertTrue(set(out["ended"]) <= set(out["rows"]))
        # Back to the whole catalogue, orchestral pieces are again never picked at random.
        self.assertIsNone(out["queue"])
        self.assertFalse([i for i in out["after"] if "cinematic_classical" in out["genres"][i]])

    def test_changing_and_resetting_filters_update_the_queue_without_interrupting(self):
        out = self.run_scenario(
            "const page = open('?genre=rock', {autoplayBlocked: false}); await settle(); out.rock = state(page);"
            "page.click('.chip[data-id=\"rock\"]'); page.click('.chip[data-id=\"cinematic_classical\"]'); await settle(); out.pop = state(page);"
            "out.ended = await finish(page, 5);"
            "page.input('#search', 'zzzz'); await settle(); out.none = state(page);"
            "page.audio().finish(); await settle(); out.stopped = state(page);"
            "page.click('#reset'); await settle(); out.reset = state(page);"
        )
        rock, pop = out["rock"], out["pop"]
        # The recording that no longer matches keeps playing; the queue is already the new selection.
        self.assertEqual((pop["current"], pop["playing"]), (rock["current"], True))
        self.assertNotIn(rock["current"], pop["rows"])
        self.assertEqual(sorted(pop["queue"]), sorted(pop["rows"]))
        self.assertTrue(set(out["ended"]) <= set(pop["rows"]))
        # A selection with no results plays nothing more: Next and Previous are disabled and the end stops.
        none = out["none"]
        self.assertEqual((none["queue"], none["rows"], none["prevDisabled"], none["nextDisabled"]), ([], [], True, True))
        self.assertEqual((out["stopped"]["playing"], out["stopped"]["current"]), (False, none["current"]))
        # Resetting returns to the whole catalogue.
        self.assertEqual((out["reset"]["queue"], out["reset"]["url"], out["reset"]["prevDisabled"]), (None, "/music/index.html", False))

    def test_history_and_reload_restore_the_queue_and_never_start_sound_on_their_own(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const page = open('?mood=warm', {}, tab); await settle(); out.open = state(page);"
            "page.click('.chip[data-id=\"pop\"]'); await settle(); out.pop = state(page);"
            "page.history.back(); await settle(); out.back = state(page);"
            "page.history.forward(); await settle(); out.forward = state(page);"
            "const reloaded = tab.open(page.location.pathname.slice(1) + page.location.search, {navigation: 'reload'}); await settle(); out.reload = state(reloaded);"
            "reloaded.click('#toggle'); await settle(); out.playing = state(reloaded);"
            "const again = tab.open(reloaded.location.pathname.slice(1) + reloaded.location.search, {navigation: 'reload'}); await settle(); out.again = state(again);"
            "const song = tab.open('music/index.html?song=%s', {navigation: 'back_forward'}); await settle(); out.song = state(song);" % SONG
        )
        self.assertEqual(out["open"]["attempts"], ["blocked:engine"])
        self.assertEqual(sorted(out["back"]["queue"]), sorted(out["open"]["rows"]))
        self.assertEqual(sorted(out["forward"]["queue"]), sorted(out["pop"]["rows"]))
        # History steps write no attempts of their own.
        self.assertEqual(out["forward"]["attempts"], ["blocked:engine"])
        # A reload restores the filters and the queue, paused as it was and without a new attempt or a prompt.
        reload = out["reload"]
        self.assertEqual((reload["attempts"], reload["playing"], reload["selectionButton"]), ([], False, None))
        self.assertEqual((reload["url"], sorted(reload["queue"])), (out["pop"]["url"], sorted(out["pop"]["rows"])))
        self.assertEqual(reload["current"], out["pop"]["current"])
        # What was playing in this tab resumes after a reload, as anywhere on the site.
        self.assertEqual((out["again"]["attempts"], out["again"]["current"]), (["blocked:engine"], out["playing"]["current"]))
        # Coming back to a song link selects it, paused, without trying to play.
        self.assertEqual((out["song"]["current"], out["song"]["attempts"], out["song"]["playing"]), (PREVIEWS.index(SONG), [], False))

    def test_song_wins_over_filters_and_the_compatible_ones_become_its_queue(self):
        out = self.run_scenario(
            "const hidden = open('?song=%s&genre=cinematic_classical', {autoplayBlocked: false}); await settle(); out.hidden = state(hidden);"
            "const kept = open('?song=%s&genre=pop', {autoplayBlocked: false}); await settle(); out.kept = state(kept);"
            "out.ended = await finish(kept, 4);" % (SONG, SONG)
        )
        i = PREVIEWS.index(SONG)
        self.assertEqual((out["hidden"]["current"], out["hidden"]["playing"], out["hidden"]["queue"]), (i, True, None))
        kept = out["kept"]
        self.assertEqual((kept["current"], kept["playing"], kept["attempts"]), (i, True, ["play:engine"]))
        self.assertEqual(sorted(kept["queue"]), sorted(kept["rows"]))
        self.assertTrue(set(out["ended"]) <= set(kept["rows"]))

    def test_links_that_select_nothing_start_nothing(self):
        out = self.run_scenario(
            "out.cases = {};"
            "for (const query of ['?q=zzzz', '?song=no-such-song&genre=pop', '?mood=nope', '?song=%s#jingles', '?genre=pop#jingles']) {"
            "  const page = open(query, {autoplayBlocked: false}); await settle(); page.click('.music-hero'); await settle();"
            "  out.cases[query] = state(page); }" % SONG
        )
        for query, s in out["cases"].items():
            with self.subTest(query=query):
                self.assertEqual((s["attempts"], s["playing"], s["songButton"], s["selectionButton"]), ([], False, None, None))
        self.assertEqual(out["cases"]["?q=zzzz"]["queue"], [])
        # A hash keeps its destination and its own players: nothing starts, the recording or the first result is selected
        # and the queue still follows the filters.
        hashed = out["cases"]["?genre=pop#jingles"]
        self.assertEqual((sorted(hashed["queue"]), hashed["current"]), (sorted(hashed["rows"]), hashed["rows"][0]))
        self.assertEqual(out["cases"]["?song=%s#jingles" % SONG]["current"], PREVIEWS.index(SONG))
        missing = out["cases"]["?song=no-such-song&genre=pop"]
        self.assertEqual(missing["current"], missing["rows"][0])

    def test_never_two_sounds_at_once(self):
        out = self.run_scenario(
            "const first = open('', {autoplayBlocked: false}); await settle(); out.first = !first.audio().paused;"
            "const second = open('?genre=pop', {autoplayBlocked: false}); await settle(); await settle();"
            "out.after = {first: !first.audio().paused, second: !second.audio().paused, attempts: state(second).attempts};"
            "out.again = second.eval('LGPlayer.openLink(0)'); out.current = second.eval('LGPlayer.index()');"
            "const jingle = second.$('#jingle-bachoco audio'); jingle.click(); jingle.play(); await settle();"
            "out.jingle = {engine: !second.audio().paused, jingle: !jingle.paused};"
            "out.audios = second.engineAudio.length;"
        )
        self.assertTrue(out["first"])
        # Another tab that starts a link pauses this one; the link starts once, and a second call does nothing.
        self.assertEqual(out["after"], {"first": False, "second": True, "attempts": ["play:engine"]})
        self.assertNotEqual(out["current"], 0)
        # A jingle player that starts pauses the engine; there is still one engine audio element.
        self.assertEqual(out["jingle"], {"engine": False, "jingle": True})
        self.assertEqual(out["audios"], 1)

    def test_the_queue_follows_the_visitor_to_other_pages(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const page = open('?genre=rock', {autoplayBlocked: false}, tab); await settle(); out.rows = rows(page);"
            "const home = tab.open('index.html', {autoplayBlocked: false}); await settle();"
            "out.home = []; for (let k = 0; k < 6; k++) { home.click('#mp-next'); await settle(); out.home.push(home.eval('LGPlayer.index()')); }"
            "const music = tab.open('music/index.html', {autoplayBlocked: false}); await settle(); out.plain = music.eval('LGPlayer.queue()');"
        )
        self.assertTrue(set(out["home"]) <= set(out["rows"]))
        # /music/ without filters is the whole catalogue again.
        self.assertIsNone(out["plain"])

    def test_the_prompts_sit_on_the_cover_and_beside_the_results_on_desktop_and_phone(self):
        html = (ROOT / "music" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('<figure class="np-art"><img id="np-art" src="" alt="" width="640" height="640"><button id="np-start" class="np-start" type="button" hidden>', html)
        self.assertIn('<div class="playlist-meta"><p class="catalog-count" role="status"', html)
        self.assertIn('<button id="play-selection" class="clear-filters play-selection" type="button" hidden>', html)
        # Both keep a touch target of at least 44px; the cover button is laid over the artwork at every width.
        self.assertIn(".np-start{position:absolute;left:50%;bottom:1.25rem;transform:translateX(-50%);display:inline-flex;align-items:center;gap:.6rem;min-height:48px;", css)
        self.assertIn(".np-art{grid-column:1/6;margin:0;position:relative}", css)
        self.assertIn("@media(max-width:700px){.playlist-meta{justify-content:space-between;margin-top:1rem}", css)


if __name__ == "__main__":
    unittest.main()
