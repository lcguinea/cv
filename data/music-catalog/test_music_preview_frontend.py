#!/usr/bin/env python3
"""Focused frontend tests for the /music/ player: selection, player updates, exclusive
playback, role filters and internationalisation.

Static checks always run. When Node.js is available the page's own inline script runs together
with the real js/strings.js, js/i18n.js, js/music-data.js and js/site.js against a small stub DOM
whose <audio> elements record every play/pause, so behaviour is checked without a browser and
without dependencies.
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
STRINGS_JS = ROOT / "js" / "strings.js"
STYLES = ROOT / "css" / "styles.css"
NODE = shutil.which("node")

HARNESS_JS = r"""
const fs = require('fs'), vm = require('vm');
const [root, scenario] = process.argv.slice(1);
const read = rel => fs.readFileSync(root + '/' + rel, 'utf8');
const html = read('music/index.html');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const kebab = k => k.replace(/[A-Z]/g, c => '-' + c.toLowerCase());
const docListeners = {};
const log = [];
const all = [];

class El {
  constructor(tag, attrs) {
    this.tagName = tag.toUpperCase(); this.attrs = Object.assign({}, attrs); this.listeners = {};
    this.textContent = ''; this.html = ''; this.rows = null; this.value = this.attrs.value || '';
    this.hidden = 'hidden' in this.attrs; this.alt = this.attrs.alt || '';
    this.disabled = 'disabled' in this.attrs;
    if (tag !== 'audio') this.src = this.attrs.src || '';
    const self = this;
    this.dataset = new Proxy({}, {
      get: (o, k) => self.attrs['data-' + kebab(String(k))],
      set: (o, k, v) => { self.attrs['data-' + kebab(String(k))] = String(v); return true; },
    });
    this.classList = {
      toggle: (c, on) => { const set = new Set((self.attrs.class || '').split(/\s+/).filter(Boolean));
        if (on) set.add(c); else set.delete(c); self.attrs.class = [...set].join(' '); },
      contains: c => (self.attrs.class || '').split(/\s+/).includes(c),
    };
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  fire(type, event) {
    (this.listeners[type] || []).forEach(fn => fn(Object.assign({type, target: this, preventDefault() {}}, event)));
  }
  focus() { document.activeElement = this; }
  get innerHTML() { return this.html; }
  set innerHTML(value) {
    this.html = value;
    if (this.attrs.id !== 'catalog') return;
    this.rows = [...value.matchAll(/<button type="button" class="pl-row" data-index="(\d+)"[^>]*>/g)].map(m => {
      const row = new El('button', {class: 'pl-row', 'data-index': m[1], 'aria-current': 'false'});
      row.state = new El('span', {class: 'pl-state'});
      row.querySelector = sel => sel === '.pl-state' ? row.state : null;
      return row;
    });
  }
  querySelectorAll(sel) { return sel === '.pl-row' ? (this.rows || []) : []; }
}

class Media extends El {
  constructor(attrs) { super('audio', attrs); this.paused = true; this.ended = false; this.currentTime = 0; this.duration = NaN; }
  get src() { return this.attrs.src || ''; }
  set src(value) {
    this.attrs.src = value; this.currentTime = 0; this.duration = NaN;
    log.push('src:' + this.attrs.id + ':' + value); this.fire('emptied');
  }
  play() {
    if (!this.attrs.src) return Promise.reject(new Error('no source'));
    if (this.paused) {
      this.paused = false; this.ended = false; log.push('play:' + this.attrs.id);
      (docListeners.play || []).forEach(fn => fn({type: 'play', target: this}));
      this.fire('play');
    }
    return Promise.resolve();
  }
  pause() { if (!this.paused) { this.paused = true; log.push('pause:' + this.attrs.id); this.fire('pause'); } }
}

const body = html.slice(html.indexOf('<body'), html.indexOf('<script'));
for (const m of body.matchAll(/<(\w+)\b([^>]*)>/g)) {
  const attrs = {};
  for (const a of m[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) attrs[a[1]] = a[2] === undefined ? '' : a[2];
  if (m[1] === 'audio') all.push(new Media(attrs));
  else if (attrs.id || Object.keys(attrs).some(k => k.startsWith('data-'))) all.push(new El(m[1], attrs));
}
const foreign = new Media({id: 'foreign-audio', src: 'other.mp3'});
all.push(foreign);
const byId = id => all.find(el => el.attrs.id === id) || null;
const everything = () => { const rows = byId('catalog').rows || []; return all.concat(rows, rows.map(r => r.state)); };
const document = {
  activeElement: null, documentElement: {dataset: {}, lang: 'en'},
  getElementById: byId,
  querySelector: sel => sel.startsWith('#') ? byId(sel.slice(1)) : null,
  querySelectorAll: sel => {
    const attr = sel.match(/^\[([\w-]+)\]$/);
    if (attr) return everything().filter(el => attr[1] in el.attrs);
    const tags = sel.split(',').map(s => s.trim().toUpperCase());
    return everything().filter(el => tags.includes(el.tagName));
  },
  addEventListener: (type, fn) => { (docListeners[type] = docListeners[type] || []).push(fn); },
};
const store = {};
const ctx = {document, console, localStorage: {getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; }}};
ctx.window = ctx;
vm.createContext(ctx);
for (const file of ['js/strings.js', 'js/i18n.js', 'js/music-data.js', 'js/site.js']) vm.runInContext(read(file), ctx);
vm.runInContext(script, ctx);
(docListeners.DOMContentLoaded || []).forEach(fn => fn());

const rows = () => byId('catalog').rows || [];
const click = i => byId('catalog').fire('click', {target: {closest: () => rows().find(r => r.dataset.index === String(i)) || null}});
const press = id => byId(id).fire('click');
const filter = (value, query) => { byId('role').value = value; byId('search').value = query || '';
  byId('role').fire('change'); byId('search').fire('input'); };
const snapshot = () => ({
  title: byId('np-title').textContent, artist: byId('np-artist').textContent,
  year: String(byId('np-year').textContent), type: byId('np-type').textContent, index: byId('np-index').textContent,
  art: byId('np-art').src, alt: byId('np-art').alt, roles: byId('np-roles').innerHTML,
  audioSrc: byId('player-audio').src, playing: !byId('player-audio').paused, foreignPlaying: !foreign.paused,
  toggleState: byId('toggle').dataset.state, toggleLabel: byId('toggle').getAttribute('aria-label'),
  prevLabel: byId('prev').getAttribute('aria-label'), nextLabel: byId('next').getAttribute('aria-label'),
  status: byId('np-status').textContent, count: String(byId('count').textContent),
  total: String(byId('total').textContent), emptyHidden: byId('empty').hidden,
  rows: rows().map(r => ({index: Number(r.dataset.index), current: r.getAttribute('aria-current'),
    playing: r.classList.contains('is-playing'), state: r.state.textContent})),
  list: byId('catalog').innerHTML, data: ctx.MUSIC_DATA, log: log.slice(),
});
const out = {};
const api = {click, press, filter, snapshot, foreign, out, setLanguage: l => ctx.setLanguage(l)};
new Function(...Object.keys(api), scenario)(...Object.values(api));
setTimeout(() => process.stdout.write(JSON.stringify(out)), 0);
"""


def inline_script():
    return re.search(r"<script>(.*?)</script>", MUSIC_HTML.read_text(encoding="utf-8"), re.S).group(1)


def node_json(expression, path, *args):
    result = subprocess.run(
        [NODE, "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                     f"process.stdout.write(JSON.stringify({expression}))", str(path), *args],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


class MusicPlayerStaticTests(unittest.TestCase):
    def setUp(self):
        self.html = MUSIC_HTML.read_text(encoding="utf-8")

    def test_a_single_audio_element_without_native_controls(self):
        self.assertEqual(re.findall(r"<audio\b[^>]*>", self.html), ['<audio id="player-audio" preload="none">'])
        self.assertNotRegex(self.html, r"(?i)autoplay")

    def test_preview_url_is_confined_to_the_public_preview_directory(self):
        script = inline_script()
        self.assertIn(
            "function previewUrl(name){return /^[a-z0-9][a-z0-9-]*\\.mp3$/.test(String(name||''))"
            "?'../assets/audio/previews/'+encodeURIComponent(name):''}",
            script,
        )
        self.assertIn("audio.src=previewUrl(x.preview)", script)

    def test_controls_and_states_are_exposed_to_assistive_technology(self):
        for fragment in ('id="toggle" class="ctl ctl-play" type="button"',
                         'id="prev" class="ctl" type="button" data-i18n-label="music.previous"',
                         'id="next" class="ctl" type="button" data-i18n-label="music.next"',
                         'role="group" data-i18n-label="music.controls"',
                         '<label class="sr-only" for="seek" data-i18n="music.seek"></label>',
                         'role="status" aria-live="polite"',
                         '<label class="sr-only" for="role" data-i18n="music.roleFilter"></label>'):
            self.assertIn(fragment, self.html)
        self.assertIn("row.setAttribute('aria-current',String(current))", inline_script())
        self.assertNotRegex(self.html, r'<svg (?![^>]*aria-hidden="true")')

    def test_visible_text_is_bound_to_i18n(self):
        body = self.html[self.html.index("<body"):self.html.index("<script")]
        texts = {text.strip() for text in re.findall(r">([^<]+)<", body) if text.strip()}
        # Brand mark, language codes, separators and the initial counters are not translatable.
        self.assertLessEqual(texts, {"LUIS GUINEA", "/ MUSIC", "EN", "ES", "·", "/", "0", "0:00"})

    def test_reduced_motion_disables_player_transitions(self):
        css = STYLES.read_text(encoding="utf-8")
        self.assertIn("@media(prefers-reduced-motion:reduce){.pl-row,.ctl,.np-art img{transition:none}}", css)


@unittest.skipUnless(NODE, "node not installed")
class MusicStringsTests(unittest.TestCase):
    def test_every_music_key_used_by_the_page_exists_in_both_languages(self):
        html = MUSIC_HTML.read_text(encoding="utf-8")
        used = set(re.findall(r"t\('music\.(\w+)'\)", inline_script()))
        used |= set(re.findall(r'data-i18n(?:-label|-placeholder)?="music\.(\w+)"', html))
        # Whole keys only: 'music.role'+name and 'music.type'+name are prefixes, checked below.
        used |= set(re.findall(r"'music\.(\w+)'(?!\+)", inline_script()))
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
        result = subprocess.run([NODE, "-e", HARNESS_JS, str(ROOT), scenario],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_initial_state_shows_the_first_release_without_playing(self):
        state = self.run_scenario("out.s = snapshot();")["s"]
        first = state["data"][0]

        self.assertEqual(len(state["rows"]), 16)
        self.assertEqual((state["count"], state["total"]), ("16", "16"))
        self.assertEqual((state["title"], state["artist"], state["year"]),
                         (first["title"], first["artist"], str(first["year"])))
        self.assertEqual(state["index"], "01 / 16")
        self.assertTrue(state["audioSrc"].endswith("/assets/audio/previews/" + first["preview"]))
        self.assertFalse(state["playing"])
        self.assertNotIn("play:player-audio", state["log"])
        self.assertEqual(state["toggleLabel"], "Play preview: " + first["title"])
        self.assertEqual([r["current"] for r in state["rows"]], ["true"] + ["false"] * 15)
        self.assertEqual(state["rows"][0]["state"], "Selected")

    def test_selecting_a_song_updates_artwork_text_credits_and_audio(self):
        state = self.run_scenario("click(12); out.s = snapshot();")["s"]
        x = state["data"][12]

        self.assertEqual((state["title"], state["artist"], state["year"]), (x["title"], x["artist"], str(x["year"])))
        self.assertEqual(state["index"], "13 / 16")
        self.assertEqual(state["art"], "../assets/images/" + quote(x["artwork"], safe="-_.!~*'()"))
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
            "click(2); out.a = snapshot();"
            "click(7); out.b = snapshot();"
            "foreign.play(); out.c = snapshot();"
            "press('toggle'); out.d = snapshot();"
        )
        a, b, c, d = out["a"], out["b"], out["c"], out["d"]
        self.assertTrue(a["playing"])
        # Changing song pauses the current preview before the new source is assigned.
        tail = b["log"][len(a["log"]):]
        self.assertEqual(tail[0], "pause:player-audio")
        self.assertTrue(tail[1].startswith("src:player-audio:") and tail[1].endswith(b["data"][7]["preview"]))
        self.assertEqual(tail[2:], ["play:player-audio"])
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

    def test_play_pause_and_track_navigation_without_reload(self):
        out = self.run_scenario(
            "press('toggle'); out.a = snapshot();"
            "press('toggle'); out.b = snapshot();"
            "press('prev'); out.c = snapshot();"
            "press('toggle'); press('next'); out.d = snapshot();"
            "click(0); out.e = snapshot();"
        )
        last = out["a"]["data"][-1]
        self.assertTrue(out["a"]["playing"])
        self.assertEqual(out["a"]["toggleState"], "playing")
        self.assertFalse(out["b"]["playing"])
        self.assertTrue(out["b"]["toggleLabel"].startswith("Play preview: "))
        # Previous from the first song wraps to the last; a paused player stays paused.
        self.assertEqual((out["c"]["title"], out["c"]["artist"]), (last["title"], last["artist"]))
        self.assertFalse(out["c"]["playing"])
        # Next while playing moves on and keeps playing.
        self.assertEqual(out["d"]["index"], "01 / 16")
        self.assertTrue(out["d"]["playing"])
        # Clicking the song that is playing pauses it.
        self.assertFalse(out["e"]["playing"])
        self.assertEqual(out["e"]["index"], "01 / 16")

    def test_role_filters_and_search(self):
        out = self.run_scenario(
            "for (const role of ['Artist', 'Producer', 'Composer']) { filter(role); out[role] = snapshot(); }"
            "filter('', 'ana guinea'); out.search = snapshot();"
            "filter('Composer', 'zzz'); out.none = snapshot();"
            "filter('Composer'); press('next'); out.step = snapshot();"
            "filter(''); out.reset = snapshot();"
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
            "click(4); out.en = snapshot(); setLanguage('es'); out.es = snapshot();"
            "filter('', 'productor'); out.search = snapshot();"
        )
        en, es = out["en"], out["es"]
        x = es["data"][4]
        self.assertEqual(en["toggleLabel"], "Pause preview: " + x["title"])
        self.assertEqual(es["toggleLabel"], "Pausar preview: " + x["title"])
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
