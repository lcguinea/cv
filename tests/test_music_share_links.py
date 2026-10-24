#!/usr/bin/env python3
"""Focused tests for shareable links on /music/: filters in the query string, links to one recording (?song=<work id>),
the Share actions with their clipboard fallback, history, reload, language and invalid links.

The real page runs with its real scripts in tests/support/minidom.js, whose location and History API follow
pushState/replaceState (every change is recorded in `page.urls`) and whose clipboard is absent unless a page is opened
with `clipboard: 'granted'` or `'denied'`. Media elements refuse playback without a user gesture, as in browsers.
Requires Node.js; standard library only.

Run: python3 -m unittest tests/test_music_share_links.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "support" / "run_scenario.js"
MANIFEST = ROOT / "data" / "music-catalog" / "music_preview_manifest.json"
EXCLUSIONS = ROOT / "data" / "music-catalog" / "public_catalog_exclusions.json"
NODE = shutil.which("node")
PREVIEWS = re.findall(r"preview:'([^']+)\.mp3'", (ROOT / "js" / "music-data.js").read_text(encoding="utf-8"))
SONG = "como-decirte--luis-guinea--2022"
# Hidden by the owner: its work id is real but it is no longer published.
RETIRED = "toxic--isabella-macias--2018"

PRELUDE = r"""
const BASE = 'music/index.html';
const open = (query, options, tab) => (tab || browser.tab()).open(BASE + (query || ''), options);
const view = page => ({
  url: page.location.pathname + page.location.search + page.location.hash, urls: page.urls.slice(),
  search: page.$('#search').value, artist: page.$('#artist').value, credit: page.$('#role').value, sort: page.$('#sort').value,
  pressed: page.$$('.chip[aria-pressed="true"]').map(c => c.dataset.group + ':' + c.dataset.id),
  rows: page.$$('#catalog .pl-row').map(r => Number(r.dataset.index)), count: page.$('#count').textContent,
  linked: page.$$('#catalog > li.is-linked').map(li => Number(li.querySelector('.pl-row').dataset.index)),
  notice: page.$('#link-notice').hidden ? '' : page.$('#link-notice').textContent,
  current: page.eval('LGPlayer.index()'), playing: !page.audio().paused,
  attempts: page.log.filter(e => e.startsWith('play:') || e.startsWith('blocked:')),
  session: JSON.parse(page.tab.session['lg-player'] || 'null'), scrolled: page.scrolled.slice(),
});
const data = () => browser.tab().open(BASE).eval('MUSIC_DATA');
"""


@unittest.skipUnless(NODE, "node not installed")
class MusicShareLinkTests(unittest.TestCase):
    def run_scenario(self, scenario):
        result = subprocess.run([NODE, str(RUNNER), str(ROOT), PRELUDE + scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_song_ids_are_the_catalogue_work_ids_unique_and_independent_of_titles(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
        work = {Path(e["preview"]).stem: e["work_id"] for e in manifest if e.get("preview")}
        self.assertEqual(len(PREVIEWS), len(set(PREVIEWS)))
        for stem in PREVIEWS:
            with self.subTest(song=stem):
                self.assertRegex(stem, r"^[a-z0-9][a-z0-9-]*$")
                self.assertEqual(work[stem], stem)
        retired = {e["work_id"] for e in json.loads(EXCLUSIONS.read_text(encoding="utf-8"))["excluded"]}
        self.assertIn(RETIRED, retired)
        self.assertFalse(retired & set(PREVIEWS))

    def test_phone_layout_gives_reset_and_share_their_own_row_and_lets_row_links_wrap(self):
        css = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
        html = (ROOT / "music" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="field field-artist"><label for="artist"', html)
        self.assertIn('<div class="toolbar-actions"><button id="clear"', html)
        phone = "@media(max-width:700px){.pl-links{flex-wrap:wrap;column-gap:1rem;row-gap:0}.field-artist{grid-column:1/-1}" \
                ".toolbar-actions{grid-column:1/-1;justify-self:stretch;justify-content:space-between;flex-wrap:nowrap}}"
        self.assertIn(phone, css)
        # Both actions keep the 44px target of .clear-filters and the share buttons in the rows keep theirs.
        self.assertIn(".clear-filters{display:inline-flex;align-items:center;gap:.4rem;min-height:44px;", css)
        self.assertIn(".pl-share{display:inline-flex;align-items:center;min-height:44px;", css)

    def test_combined_filters_in_the_url_match_the_same_filters_chosen_on_the_page(self):
        out = self.run_scenario(
            "const linked = open('?artist=Rogelio%20Edel&credit=producer&mood=warm,melancholic&genre=pop&sort=year-asc'); await settle();"
            "out.linked = view(linked);"
            "const page = open(); await settle();"
            "page.change('#artist', 'Rogelio Edel'); page.change('#role', 'Producer');"
            "page.click('.chip[data-id=\"warm\"]'); page.click('.chip[data-id=\"melancholic\"]'); page.click('.chip[data-id=\"pop\"]');"
            "page.change('#sort', 'year-asc'); await settle(); out.chosen = view(page);"
            "const single = open('?genre=rock'); await settle(); out.single = view(single);"
            "const search = open('?q=c%C3%B3mo'); await settle(); out.search = view(search);"
        )
        linked, chosen = out["linked"], out["chosen"]
        self.assertEqual(linked["rows"], chosen["rows"])
        self.assertTrue(linked["rows"])
        self.assertEqual((linked["artist"], linked["credit"], linked["sort"]), ("Rogelio Edel", "Producer", "year-asc"))
        self.assertEqual(sorted(linked["pressed"]), ["genre:pop", "mood:melancholic", "mood:warm"])
        self.assertEqual(linked["notice"], "")
        # The page writes the same URL the link had: the catalogue's ids, a fixed order, no labels and no language.
        self.assertEqual(chosen["url"], "/music/index.html?artist=Rogelio%20Edel&credit=producer&mood=warm,melancholic&genre=pop&sort=year-asc")
        self.assertEqual(linked["url"], chosen["url"])
        self.assertEqual(linked["urls"], [])
        self.assertEqual((out["single"]["pressed"], out["single"]["url"]), (["genre:rock"], "/music/index.html?genre=rock"))
        self.assertEqual(out["search"]["search"], "cómo")
        self.assertIn(3, out["search"]["rows"])

    def test_without_filters_the_url_stays_clean_and_jingles_keeps_its_hash(self):
        out = self.run_scenario(
            "const plain = open(); await settle(); out.plain = view(plain);"
            "const jingles = open('#jingles'); await settle(); out.jingles = view(jingles);"
            "jingles.click('.chip[data-id=\"pop\"]'); await settle(); out.filtered = view(jingles);"
            "jingles.click('#clear'); await settle(); out.cleared = view(jingles);"
            "const extra = open('?utm_source=newsletter'); await settle(); extra.change('#role', 'Artist'); await settle(); out.extra = view(extra);"
        )
        self.assertEqual((out["plain"]["url"], out["plain"]["urls"]), ("/music/index.html", []))
        self.assertEqual((out["jingles"]["url"], out["jingles"]["urls"]), ("/music/index.html#jingles", []))
        self.assertEqual(out["filtered"]["url"], "/music/index.html?genre=pop#jingles")
        self.assertEqual(out["cleared"]["url"], "/music/index.html#jingles")
        # Parameters that are not the page's own are kept as they are.
        self.assertEqual(out["extra"]["url"], "/music/index.html?credit=artist&utm_source=newsletter")

    def test_each_change_is_a_history_entry_that_back_and_forward_restore(self):
        out = self.run_scenario(
            "const page = open(); await settle(); out.start = view(page);"
            "page.click('.chip[data-id=\"warm\"]'); await settle(); out.warm = view(page);"
            "page.change('#artist', 'Ana Guinea'); await settle(); out.ana = view(page);"
            "page.input('#search', 'c'); page.input('#search', 'co'); page.input('#search', 'cov'); await settle(); out.typed = view(page);"
            "page.history.back(); await settle(); out.back1 = view(page);"
            "page.history.back(); await settle(); out.back2 = view(page);"
            "page.history.back(); await settle(); out.back3 = view(page);"
            "page.history.forward(); await settle(); out.forward = view(page);"
        )
        self.assertEqual(out["warm"]["url"], "/music/index.html?mood=warm")
        self.assertEqual(out["ana"]["url"], "/music/index.html?artist=Ana%20Guinea&mood=warm")
        self.assertEqual(out["typed"]["url"], "/music/index.html?q=cov&artist=Ana%20Guinea&mood=warm")
        # Typing adds one entry, not one per key.
        self.assertEqual([u.split(":")[0] for u in out["typed"]["urls"]], ["push", "push", "push", "replace", "replace"])
        self.assertEqual((out["back1"]["url"], out["back1"]["search"]), (out["ana"]["url"], ""))
        self.assertEqual(out["back1"]["rows"], out["ana"]["rows"])
        self.assertEqual((out["back2"]["artist"], out["back2"]["pressed"], out["back2"]["rows"]), ("", ["mood:warm"], out["warm"]["rows"]))
        self.assertEqual((out["back3"]["url"], out["back3"]["pressed"], out["back3"]["rows"]), ("/music/index.html", [], out["start"]["rows"]))
        self.assertEqual((out["forward"]["url"], out["forward"]["rows"]), (out["warm"]["url"], out["warm"]["rows"]))
        # History steps never write new entries.
        self.assertEqual(out["forward"]["urls"], out["typed"]["urls"])

    def test_a_reload_restores_the_same_filters_and_shared_recording(self):
        out = self.run_scenario(
            "const tab = browser.tab(); const page = open('', {}, tab); await settle();"
            "page.click('.chip[data-id=\"pop\"]'); page.change('#sort', 'artist-asc'); await settle(); out.before = view(page);"
            "const again = tab.open(page.location.pathname.slice(1) + page.location.search); await settle(); out.after = view(again);"
            "const song = open('?song=%s', {}, tab); await settle(); const reloaded = tab.open(song.location.pathname.slice(1) + song.location.search); await settle();"
            "out.song = view(reloaded);" % SONG
        )
        before, after = out["before"], out["after"]
        self.assertEqual((after["url"], after["rows"], after["pressed"], after["sort"]), (before["url"], before["rows"], ["genre:pop"], "artist-asc"))
        self.assertEqual(len(out["song"]["linked"]), 1)
        self.assertFalse(out["song"]["playing"])

    def test_a_song_link_locates_the_recording_without_playing_it(self):
        out = self.run_scenario(
            "const page = open('?song=%s', {autoplayBlocked: false}); await settle(); out.open = view(page);"
            "page.window._fire('load'); await settle(); out.loaded = view(page); out.focus = page.document.activeElement.dataset.index;"
            "page.click('.music-hero'); await settle(); out.click = view(page);"
            "out.data = page.eval('MUSIC_DATA.map(x => [x.title, x.artist])');" % SONG
        )
        i = PREVIEWS.index(SONG)
        s = out["open"]
        self.assertEqual((s["linked"], s["current"]), ([i], i))
        # Even where the browser allows sound, a link to one recording never starts it, then or on a later click.
        self.assertEqual(s["attempts"], [])
        self.assertFalse(s["playing"])
        self.assertEqual((s["session"]["playing"], s["session"]["auto"]), (False, False))
        self.assertEqual(out["click"]["attempts"], [])
        title, artist = out["data"][i]
        self.assertEqual(s["notice"], f"Shared link: {title} by {artist} is highlighted in the list.")
        self.assertEqual(out["loaded"]["scrolled"], [{"id": "", "index": str(i), "options": {"block": "center", "behavior": "instant"}}])
        self.assertEqual(out["focus"], str(i))
        self.assertEqual(s["url"], f"/music/index.html?song={SONG}")

    def test_after_a_song_link_the_first_press_on_play_starts_that_recording(self):
        out = self.run_scenario(
            "const page = open('?song=%s'); await settle(); out.open = view(page);"
            "page.click('#toggle'); await settle(); out.play = view(page);"
            "out.label = page.$('#toggle').getAttribute('aria-label');"
            "page.click('#toggle'); await settle(); out.pause = view(page);"
            "const bar = open('?song=%s'); await settle(); bar.click('#mp-toggle'); await settle(); out.bar = view(bar);" % (SONG, SONG)
        )
        i = PREVIEWS.index(SONG)
        self.assertEqual((out["open"]["attempts"], out["open"]["playing"]), ([], False))
        # One press, one request, and it is granted because it comes from the visitor's gesture.
        self.assertEqual((out["play"]["attempts"], out["play"]["playing"], out["play"]["current"]), (["play:engine"], True, i))
        self.assertTrue(out["label"].startswith("Pause preview: "))
        self.assertFalse(out["pause"]["playing"])
        # The bottom bar's button does the same.
        self.assertEqual((out["bar"]["attempts"], out["bar"]["playing"], out["bar"]["current"]), (["play:engine"], True, i))

    def test_a_song_link_wins_over_filters_that_would_hide_it_and_keeps_compatible_ones(self):
        out = self.run_scenario(
            "const hidden = open('?song=%s&genre=cinematic_classical&q=zzz&sort=year-asc'); await settle(); out.hidden = view(hidden);"
            "const kept = open('?song=%s&artist=Luis%%20Guinea&genre=pop'); await settle(); out.kept = view(kept);"
            "kept.click('.chip[data-id=\"reggae\"]'); await settle(); out.changed = view(kept);"
            "kept.history.back(); await settle(); out.back = view(kept);"
            "const hash = open('?song=%s#jingles'); await settle(); hash.window._fire('load'); await settle(); out.hash = view(hash);" % (SONG, SONG, SONG)
        )
        i = PREVIEWS.index(SONG)
        hidden = out["hidden"]
        self.assertEqual(hidden["linked"], [i])
        self.assertEqual((hidden["pressed"], hidden["search"], hidden["sort"]), ([], "", "year-asc"))
        self.assertEqual(len(hidden["rows"]), len(PREVIEWS))
        self.assertTrue(hidden["notice"].endswith("The filters in the link did not include it, so they were cleared."))
        self.assertEqual(hidden["url"], f"/music/index.html?song={SONG}&sort=year-asc")
        kept = out["kept"]
        self.assertEqual((kept["linked"], kept["artist"], kept["pressed"]), ([i], "Luis Guinea", ["genre:pop"]))
        self.assertNotIn("cleared", kept["notice"])
        # Changing the view leaves the shared link behind; Back brings it back.
        self.assertEqual((out["changed"]["linked"], out["changed"]["notice"]), ([], ""))
        self.assertEqual(out["changed"]["url"], "/music/index.html?artist=Luis%20Guinea&genre=pop,reggae")
        self.assertEqual((out["back"]["linked"], out["back"]["url"]), ([i], kept["url"]))
        # A hash keeps its own destination (site.js scrolls to #jingles): the recording is highlighted, not scrolled to.
        self.assertEqual((out["hash"]["linked"], [x["id"] for x in out["hash"]["scrolled"]]), ([i], ["jingles"]))

    def test_retired_unknown_and_malformed_songs_are_reported_without_a_misleading_list(self):
        songs = [RETIRED, "no-such-song", '<img src=x onerror=alert(1)>', "../../etc/passwd", "COMO-DECIRTE--LUIS-GUINEA--2022", ""]
        out = self.run_scenario(
            "out.cases = [];"
            "for (const song of %s) { const page = open('?song=' + encodeURIComponent(song) + '&mood=warm'); await settle();"
            "  out.cases.push(Object.assign(view(page), {html: page.$('#catalog').innerHTML + page.$('#link-notice').innerHTML})); }"
            "const warm = open('?mood=warm'); await settle(); out.warm = view(warm);" % json.dumps(songs)
        )
        for song, s in zip(songs, out["cases"]):
            with self.subTest(song=song):
                self.assertEqual(s["linked"], [])
                self.assertEqual((s["rows"], s["pressed"]), (out["warm"]["rows"], ["mood:warm"]))
                self.assertEqual(s["url"], "/music/index.html?mood=warm")
                self.assertNotIn("<img src=x", s["html"])
                self.assertFalse(s["playing"])
                expected = "" if song == "" else "The shared recording is not available in this catalogue."
                self.assertEqual(s["notice"], expected)

    def test_unknown_values_are_left_out_and_reported_and_special_characters_round_trip(self):
        out = self.run_scenario(
            "const bad = open('?mood=WARM,nope,warm&genre=%3Cb%3E&artist=Nobody&credit=drummer&sort=random&q=%20'); await settle(); out.bad = view(bad);"
            "const names = open('?artist=carla%20calderon'); await settle(); out.lower = view(names);"
            "const accent = open('?artist=CARLA%20CALDER%C3%93N'); await settle(); out.accent = view(accent);"
            "const page = open(); await settle(); page.input('#search', 'Ana & \"Bo\" #1+2/?'); await settle(); out.typed = view(page);"
            "const back = open(page.location.search); await settle(); out.reopened = view(back);"
            "const repeat = open('?genre=pop&genre=rock&credit=Producer&credit=Artist'); await settle(); out.repeat = view(repeat);"
        )
        bad = out["bad"]
        self.assertEqual((bad["pressed"], bad["artist"], bad["credit"], bad["sort"], bad["search"]), (["mood:warm"], "", "", "year-desc", ""))
        self.assertEqual(bad["url"], "/music/index.html?mood=warm")
        self.assertEqual(bad["notice"], "Some filters in the link are not available and were left out.")
        self.assertEqual(out["lower"]["artist"], "Carla Calderon")
        self.assertEqual(out["accent"]["artist"], "Carla Calderón")
        typed = out["typed"]
        self.assertEqual(typed["url"], "/music/index.html?q=Ana%20%26%20%22Bo%22%20%231%2B2%2F%3F")
        self.assertEqual((out["reopened"]["search"], out["reopened"]["notice"]), ('Ana & "Bo" #1+2/?', ""))
        self.assertEqual((out["repeat"]["pressed"], out["repeat"]["credit"]), (["genre:pop", "genre:rock"], "Producer"))

    def test_links_carry_no_language_and_open_in_the_visitor_language(self):
        out = self.run_scenario(
            "const es = open('?song=%s&mood=warm', {languages: ['es-MX'], clipboard: 'granted'}); await settle(); out.es = view(es);"
            "es.click('.chip[data-id=\"bright\"]'); await settle(); out.esBright = view(es);"
            "es.click('#share-view'); await settle(); out.copied = es.copied.slice();"
            "es.click('[data-lang=\"en\"]'); await settle(); out.en = view(es);"
            "const en = open('?mood=warm,bright'); await settle(); out.enRows = view(en).rows;" % SONG
        )
        self.assertTrue(out["es"]["notice"].startswith("Enlace compartido: Cómo Decirte de "))
        self.assertEqual(out["esBright"]["rows"], out["enRows"])
        self.assertEqual(out["copied"], ["http://test.local/music/index.html?mood=warm,bright"])
        # Switching the language changes neither the URL nor the list.
        self.assertEqual((out["en"]["url"], out["en"]["rows"]), (out["esBright"]["url"], out["esBright"]["rows"]))

    def test_share_copies_the_view_or_one_recording_and_confirms_it(self):
        out = self.run_scenario(
            "const page = open('?genre=pop&sort=artist-desc&utm_source=x#jingles', {clipboard: 'granted'}); await settle();"
            "out.hidden = page.$('#share-view').hidden; out.label = page.$('#share-view').getAttribute('aria-label');"
            "page.click('#share-view'); await settle();"
            "out.status = page.$('#share-status').textContent; out.state = page.$('#share-view').dataset.state;"
            "out.text = page.$('#share-view .share-text').textContent;"
            "const button = page.$$('.pl-share').find(b => b.dataset.song === '%s');"
            "out.songLabel = button.getAttribute('aria-label'); page.click(button); await settle();"
            "out.copied = page.copied.slice(); out.attempts = view(page).attempts; out.current = view(page).current;"
            "out.shares = page.$$('#catalog > li').map(li => li.querySelectorAll('.pl-share').length);"
            "await new Promise(r => setTimeout(r, 2600)); out.later = [page.$('#share-status').textContent, page.$('#share-view .share-text').textContent];"
            "page.click('[data-lang=\"es\"]'); await settle(); out.esLabel = page.$$('.pl-share')[0].getAttribute('aria-label');" % SONG
        )
        self.assertFalse(out["hidden"])
        self.assertEqual(out["label"], "Share: copy a link to this view of the catalogue")
        # The view link holds the filters only: no hash, no foreign parameters, no recording.
        self.assertEqual(out["copied"], ["http://test.local/music/index.html?genre=pop&sort=artist-desc",
                                         f"http://test.local/music/index.html?song={SONG}"])
        self.assertEqual((out["status"], out["state"], out["text"]), ("Link copied to the clipboard.", "copied", "Copied"))
        self.assertTrue(out["songLabel"].startswith("Share: copy a link to Cómo Decirte by "))
        self.assertTrue(all(n == 1 for n in out["shares"]))
        # Sharing never plays or selects anything.
        self.assertEqual(out["attempts"], ["blocked:engine"])
        self.assertEqual(out["later"], ["", "Share"])
        self.assertTrue(out["esLabel"].startswith("Compartir: copiar un enlace a "))

    def test_without_a_clipboard_the_link_is_shown_selected_to_copy_by_hand(self):
        out = self.run_scenario(
            "out.cases = {};"
            "for (const clipboard of ['none', 'denied']) {"
            "  const page = open('?mood=warm', clipboard === 'none' ? {} : {clipboard}); await settle();"
            "  const button = page.$$('.pl-share').find(b => b.dataset.song === '%s'); page.click(button); await settle();"
            "  const box = page.$('#share-fallback');"
            "  const song = {hidden: box.hidden, value: page.$('#share-url').value, inRow: !!box.closest('#catalog'),"
            "    focus: page.document.activeElement.id, selected: page.selected && page.selected.id};"
            "  page.click('#share-close'); await settle();"
            "  const closed = {hidden: box.hidden, focus: page.document.activeElement === button, home: !box.closest('#catalog')};"
            "  page.click('#share-view'); await settle();"
            "  const viewLink = {hidden: box.hidden, value: page.$('#share-url').value};"
            "  page.document._dispatch(page.$('#share-url'), {type: 'keydown', key: 'Escape', bubbles: true});"
            "  out.cases[clipboard] = {song, closed, view: viewLink, escaped: box.hidden, focus: page.document.activeElement.id,"
            "    status: page.$('#share-status').textContent}; }" % SONG
        )
        for name, case in out["cases"].items():
            with self.subTest(clipboard=name):
                self.assertEqual(case["song"], {"hidden": False, "value": f"http://test.local/music/index.html?song={SONG}",
                                                "inRow": True, "focus": "share-url", "selected": "share-url"})
                self.assertEqual(case["closed"], {"hidden": True, "focus": True, "home": True})
                self.assertEqual(case["view"], {"hidden": False, "value": "http://test.local/music/index.html?mood=warm"})
                self.assertTrue(case["escaped"])
                self.assertEqual(case["focus"], "share-view")
                self.assertEqual(case["status"], "")

    def test_a_history_step_to_a_shared_recording_never_interrupts_what_is_playing(self):
        out = self.run_scenario(
            "const page = open('?song=%s'); await settle();"
            "page.click('.chip[data-id=\"pop\"]'); await settle();"
            "const other = page.$$('#catalog .pl-row').find(r => r.dataset.index !== '%d');"
            "page.click(other.querySelector('.pl-title')); await settle(); out.playing = view(page);"
            "page.history.back(); await settle(); out.back = view(page);" % (SONG, PREVIEWS.index(SONG))
        )
        self.assertTrue(out["playing"]["playing"])
        self.assertEqual((out["back"]["linked"], out["back"]["playing"], out["back"]["current"]),
                         ([PREVIEWS.index(SONG)], True, out["playing"]["current"]))


if __name__ == "__main__":
    unittest.main()
