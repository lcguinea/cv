"""Regression test: the /music/ role filter must label every public facet correctly.

The Producer option once pointed at ``music.role`` and rendered "Role"/"Rol".
This test reads music/index.html and js/strings.js statically (no JavaScript).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MUSIC_HTML = ROOT / "music" / "index.html"
STRINGS_JS = ROOT / "js" / "strings.js"

FACETS = ("Artist", "Producer", "Composer")
EXPECTED = {
    "en": {"Artist": "Artist", "Producer": "Producer", "Composer": "Songwriter"},
    "es": {"Artist": "Artista", "Producer": "Productor", "Composer": "Compositor"},
}


def role_option_keys(html):
    select = re.search(r'<select\b[^>]*\bid="role"[^>]*>(.*?)</select>', html, re.S)
    if not select:
        raise AssertionError('select#role not found in music/index.html')
    keys = {}
    for attrs in re.findall(r"<option\b([^>]*)>", select.group(1)):
        value = re.search(r'\bvalue="([^"]*)"', attrs)
        key = re.search(r'\bdata-i18n="([^"]*)"', attrs)
        if value and value.group(1) in FACETS:
            keys[value.group(1)] = key.group(1) if key else None
    return keys


def music_strings(js, lang):
    lang_block = re.search(r"\b%s\s*:\s*\{(.*?)\n\s*\}" % lang, js, re.S)
    if not lang_block:
        raise AssertionError("STRINGS.%s not found in js/strings.js" % lang)
    music = re.search(r"\bmusic\s*:\s*\{(.*?)\}", lang_block.group(1), re.S)
    if not music:
        raise AssertionError("STRINGS.%s.music not found in js/strings.js" % lang)
    return dict(re.findall(r"(\w+)\s*:\s*'((?:[^'\\]|\\.)*)'", music.group(1)))


def resolve(key, strings):
    if not key or not key.startswith("music."):
        return None
    return strings.get(key.split(".", 1)[1])


class MusicFilterI18nTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = role_option_keys(MUSIC_HTML.read_text(encoding="utf-8"))
        js = STRINGS_JS.read_text(encoding="utf-8")
        cls.strings = {lang: music_strings(js, lang) for lang in EXPECTED}

    def test_every_public_facet_has_an_i18n_key(self):
        self.assertEqual(set(self.keys), set(FACETS))
        for facet in FACETS:
            self.assertTrue(self.keys[facet], "%s option has no data-i18n" % facet)

    def test_producer_does_not_use_role_key(self):
        self.assertNotEqual(self.keys.get("Producer"), "music.role")

    def test_labels_resolve_distinct_and_correct_per_language(self):
        for lang, expected in EXPECTED.items():
            with self.subTest(lang=lang):
                labels = {facet: resolve(self.keys.get(facet), self.strings[lang]) for facet in FACETS}
                for facet, label in labels.items():
                    self.assertTrue(label and label.strip(), "%s/%s has no label" % (lang, facet))
                self.assertEqual(len(set(labels.values())), len(FACETS), labels)
                self.assertNotIn(labels["Producer"].casefold(), {"role", "rol"})
                self.assertEqual(labels, expected)


if __name__ == "__main__":
    unittest.main()
