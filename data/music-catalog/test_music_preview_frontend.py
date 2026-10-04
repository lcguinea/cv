#!/usr/bin/env python3
"""Focused frontend tests: /music/ shows an <audio> player only for verified previews.

Static checks always run. When Node.js is available the page's own inline script is executed
against js/music-data.js with a stubbed DOM, so the rendered HTML is checked, not just the source.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MUSIC_HTML = ROOT / "music" / "index.html"
MUSIC_DATA = ROOT / "js" / "music-data.js"
NODE = shutil.which("node")

RENDER_JS = r"""
const fs = require('fs'), vm = require('vm');
const [html, data, extra] = process.argv.slice(1);
const script = fs.readFileSync(html, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const el = () => ({value: '', textContent: '', innerHTML: '', addEventListener() {}});
const nodes = {'#catalog': el(), '#search': el(), '#role': el(), '#count': el()};
const ctx = {document: {querySelector: s => nodes[s], addEventListener() {}}, t: k => '[' + k + ']'};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(data, 'utf8'), ctx);
if (extra) ctx.MUSIC_DATA.push(...JSON.parse(extra));
vm.runInContext(script + '\nrender();', ctx);
process.stdout.write(nodes['#catalog'].innerHTML);
"""


# Runs the real js/strings.js + js/i18n.js + page script. The stub DOM exposes the
# [data-i18n] elements rendered inside #catalog, so setLanguage() reaches them exactly as a
# browser would; render() is never called again after the language switch.
LANGUAGE_SWITCH_JS = r"""
const fs = require('fs'), vm = require('vm');
const [html, strings, i18n, data] = process.argv.slice(1);
const script = fs.readFileSync(html, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const el = () => ({value: '', textContent: '', innerHTML: '', dataset: {}, setAttribute() {},
                   addEventListener() {}});
const nodes = {'#catalog': el(), '#search': el(), '#role': el(), '#count': el()};
const ready = [];
const LEAF = /(<([a-z]+)\b[^>]*\bdata-i18n="([^"]*)"[^>]*>)([^<]*)(<\/\2>)/g;
function i18nNodes() {
  const found = [];
  nodes['#catalog'].innerHTML.replace(LEAF, (m, open, tag, key, text, close, at) => {
    found.push({open, close, at, length: m.length, dataset: {i18n: key}});
    return m;
  });
  return found.reverse().map(n => ({dataset: n.dataset, set textContent(value) {
    const html = nodes['#catalog'].innerHTML;
    nodes['#catalog'].innerHTML = html.slice(0, n.at) + n.open + value + n.close +
      html.slice(n.at + n.length);
  }}));
}
const ctx = {
  localStorage: {getItem: () => 'en', setItem() {}},
  document: {documentElement: {}, querySelector: s => nodes[s],
             querySelectorAll: s => s === '[data-i18n]' ? i18nNodes() : [],
             addEventListener: (type, fn) => { if (type === 'DOMContentLoaded') ready.push(fn); }},
};
ctx.window = ctx;
vm.createContext(ctx);
for (const file of [strings, i18n, data]) vm.runInContext(fs.readFileSync(file, 'utf8'), ctx);
vm.runInContext(script, ctx);
ready.forEach(fn => fn());
const before = nodes['#catalog'].innerHTML;
ctx.setLanguage('es');
process.stdout.write(JSON.stringify({before, after: nodes['#catalog'].innerHTML}));
"""


def inline_script():
    return re.search(r"<script>(.*?)</script>", MUSIC_HTML.read_text(encoding="utf-8"), re.S).group(1)


class MusicPreviewStaticTests(unittest.TestCase):
    def test_player_is_conditional_on_preview_and_lazy(self):
        script = inline_script()

        self.assertRegex(
            script,
            r"x\.preview&&previewUrl\(x\.preview\)\?`<audio class=\"track-preview\" controls "
            r"preload=\"none\" src=\"\$\{previewUrl\(x\.preview\)\}\"",
        )
        self.assertIn(
            "<span class=\"preview-status\"><i></i>"
            "<span data-i18n=\"music.noPreview\">${t('music.noPreview')}</span></span>",
            script,
        )
        self.assertNotRegex(script, r"(?i)autoplay")

    def test_preview_url_is_confined_to_the_public_preview_directory(self):
        script = inline_script()

        self.assertIn(
            "function previewUrl(name){return /^[a-z0-9][a-z0-9-]*\\.mp3$/.test(String(name||''))"
            "?'../assets/audio/previews/'+encodeURIComponent(name):''}",
            script,
        )


@unittest.skipUnless(NODE, "node not installed")
class MusicPreviewRenderTests(unittest.TestCase):
    def render(self, extra=None):
        result = subprocess.run(
            [NODE, "-e", RENDER_JS, str(MUSIC_HTML), str(MUSIC_DATA), json.dumps(extra or [])],
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def test_rendered_catalogue_has_players_only_for_verified_previews(self):
        html = self.render()
        cards = re.findall(r"<article class=\"track editorial-track\">.*?</article>", html)
        data = MUSIC_DATA.read_text(encoding="utf-8")
        expected = re.findall(r"preview:(null|'[^']*')", data)

        self.assertEqual(len(cards), 13)
        self.assertEqual(len(expected), 13)
        for card, preview in zip(cards, expected):
            players = re.findall(r"<audio [^>]*>", card)
            if preview == "null":
                self.assertEqual(players, [])
                self.assertIn("[music.noPreview]", card)
            else:
                name = preview.strip("'")
                self.assertEqual(len(players), 1)
                self.assertIn('controls preload="none"', players[0])
                self.assertIn(f'src="../assets/audio/previews/{name}"', players[0])
                self.assertNotIn("[music.noPreview]", card)
                self.assertTrue((ROOT / "assets" / "audio" / "previews" / name).is_file())

    def test_unsafe_preview_values_fall_back_to_the_no_preview_message(self):
        base = {"title": "X", "artist": "Y", "role": "Producer", "artwork": "x.webp",
                "releaseType": "Single", "year": 2020, "roles": ["Producer"]}
        unsafe = ["../../One Page Luis Guinea/audios/x.mp3", "https://evil.example/a.mp3",
                  "master.wav", "x.mp3\" onerror=\"alert(1)", ""]
        html = self.render([dict(base, preview=value) for value in unsafe])
        cards = re.findall(r"<article class=\"track editorial-track\">.*?</article>", html)[13:]

        self.assertEqual(len(cards), len(unsafe))
        for card in cards:
            self.assertNotIn("<audio", card)
            self.assertIn("[music.noPreview]", card)


@unittest.skipUnless(NODE, "node not installed")
class MusicPreviewLanguageSwitchTests(unittest.TestCase):
    def test_language_switch_updates_the_no_preview_fallback_without_rerender(self):
        result = subprocess.run(
            [NODE, "-e", LANGUAGE_SWITCH_JS, str(MUSIC_HTML), str(ROOT / "js" / "strings.js"),
             str(ROOT / "js" / "i18n.js"), str(MUSIC_DATA)],
            capture_output=True, text=True, check=True,
        )
        html = json.loads(result.stdout)
        english, spanish = "No short preview available", "No hay preview corto disponible"

        def statuses(markup):
            return re.findall(r"<span class=\"preview-status\"><i></i>(?:<span[^>]*>)?[^<]*"
                              r"(?:</span>)?</span>", markup)

        self.assertEqual(len(statuses(html["before"])), 5)
        self.assertTrue(all(english in item for item in statuses(html["before"])))
        self.assertEqual(len(statuses(html["after"])), 5)
        self.assertTrue(all(spanish in item and english not in item
                            for item in statuses(html["after"])), statuses(html["after"]))
        self.assertEqual(html["after"].count("<audio "), 8)
        self.assertEqual(html["before"].replace(english, spanish), html["after"])


if __name__ == "__main__":
    unittest.main()
