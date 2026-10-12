import json
import re
import subprocess
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('build_site', ROOT / 'tools/build_site.py')
build_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_site)

class AboutPageTest(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / 'sobre-mi.html').read_text(encoding='utf-8')
        self.strings = (ROOT / 'js/strings.js').read_text(encoding='utf-8')

    def test_public_story_has_accessible_structure_and_no_editorial_notes(self):
        self.assertEqual(len(re.findall(r'<h1\b', self.html)), 1)
        self.assertIn('<main id="content"', self.html)
        self.assertIn('alt="Luis Guinea"', self.html)
        self.assertNotIn('Notas editoriales', self.html)
        self.assertNotIn('autobiograf', self.html.lower())
        self.assertEqual(len(re.findall(r'data-i18n="about\.p\d+"', self.html)), 33)
        for forbidden in ('Notas editoriales para la implementación', 'Propuesta de recorrido visual', 'Privacidad y criterio', 'Historia_completa_Luis_Carlos_Guinea_Moctezuma'):
            self.assertNotIn(forbidden, self.html)

    def test_public_paragraphs_are_present_in_source_and_translations(self):
        result = subprocess.run(['node', '-e', "global.window={};eval(require('fs').readFileSync('js/strings.js','utf8'));process.stdout.write(JSON.stringify(window.STRINGS.en.about))"], cwd=ROOT, capture_output=True, text=True, check=True)
        about = json.loads(result.stdout)
        editorial = (ROOT / 'Sobre_mi_editorial_luisguinea.md').read_text(encoding='utf-8')
        self.assertIn('Mi Niño Bonito', about['p1'])
        self.assertIn('Mi Niño Bonito', editorial)
        self.assertIn('Camino de Santiago', about['p21'])
        self.assertIn('Camino de Santiago', editorial)
        self.assertIn('Santo Chilaquil', about['p28'])
        self.assertIn('Santo Chilaquil', editorial)
        self.assertIn('There is a photograph', about['p1'])
        self.assertIn('many more keys', about['p33'])
        self.assertTrue(all(about[f'p{i}'] for i in range(1, 34)))

    def test_opening_paragraphs_share_typography_rule(self):
        opening = re.search(r'<section class="about-chapter about-opening">(.*?)</section>', self.html, re.S).group(1)
        self.assertRegex(opening, r'<p data-i18n="about\.p1">')
        self.assertRegex(opening, r'<p data-i18n="about\.p2">')
        self.assertNotIn('about-display', opening)
        css = (ROOT / 'css/styles.css').read_text(encoding='utf-8')
        self.assertEqual(css.count('.about-display'), 0)
        self.assertEqual(css.count('.about-chapter p{'), 1)
        self.assertNotRegex(css, r'@media\(max-width:700px\)[^}]*\.about-chapter p')

    def test_story_keys_are_present_in_both_languages(self):
        result = subprocess.run(['node', '-e', "global.window={};eval(require('fs').readFileSync('js/strings.js','utf8'));process.stdout.write(JSON.stringify(window.STRINGS))"], cwd=ROOT, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(set(data['en']['about']), set(data['es']['about']))
        self.assertTrue(all(data['en']['about'].values()))
        self.assertTrue(all(data['es']['about'].values()))

    def test_shared_navigation_and_seo(self):
        for rel in ('index.html', 'cv.html', 'music/index.html', 'sobre-mi.html'):
            text = (ROOT / rel).read_text(encoding='utf-8')
            self.assertIn('data-i18n="nav.about"', text if rel == 'sobre-mi.html' else (ROOT / 'js/site.js').read_text())
        self.assertIn('https://luisguinea.com/sobre-mi.html', self.html)
        self.assertIn('sobre-mi.html', (ROOT / 'sitemap.xml').read_text())
        self.assertIn('"sobre-mi.html"', (ROOT / 'tools/build_site.py').read_text())
        self.assertIn('aria-current="page"', self.html)
        self.assertIn('menu-toggle', self.html)
        self.assertIn('id="site-menu"', self.html)

    def test_accessibility_assets_links_and_motion(self):
        self.assertIn('<header class="site-header">', self.html)
        self.assertIn('<footer class="footer">', self.html)
        self.assertRegex(self.html, r'<html lang="en">')
        images = re.findall(r'<img\b[^>]*>', self.html)
        self.assertTrue(images)
        self.assertTrue(all('alt=' in image for image in images))
        for ref in re.findall(r'(?:href|src)="([^"]+)"', self.html):
            if ref.startswith(('http:', 'https:', '#', 'mailto:', 'data:')):
                continue
            ref = ref.split('#', 1)[0]
            if not ref:
                continue
            target = ROOT / ref
            if ref.endswith('/'):
                target = target / 'index.html'
            self.assertTrue(target.is_file() or target.is_dir(), ref)
        self.assertIn('assets/images/profile.webp', self.html)
        self.assertIn('prefers-reduced-motion', (ROOT / 'css/styles.css').read_text(encoding='utf-8'))
        for marker in ('<title data-i18n="about.pageTitle">', 'rel="canonical"', 'property="og:title"', 'property="og:description"', 'name="twitter:card"', 'name="description"'):
            self.assertIn(marker, self.html)

    def test_allowlist_excludes_private_sources(self):
        files = set(build_site.allowlist())
        self.assertIn('sobre-mi.html', files)
        self.assertIn('assets/images/profile.webp', files)
        for forbidden in ('CV_MASTER.md', 'BRAND.md', 'PROPUESTA.md', 'Historia_completa_Luis_Carlos_Guinea_Moctezuma.md', 'Sobre_mi_editorial_luisguinea.md', 'local-server.js'):
            self.assertNotIn(forbidden, files)
        self.assertFalse(any(path.startswith('data/music-catalog/') for path in files))

if __name__ == '__main__':
    unittest.main()
