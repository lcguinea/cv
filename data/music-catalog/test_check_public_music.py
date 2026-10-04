"""Regression tests for check_public_music.py.

- A checkout without web artworks (isolated sandbox copy) must warn, not abort: the
  orchestrator sandbox does not copy assets/images/*.webp; check_public_music.py once
  returned 1 there before validating anything else.
- Audio exposure: any audio outside the authorized previews must be ignored by the project's
  own Git rules (and never tracked), wherever it lives, including One Page Luis Guinea/ and
  data/, which the checker once skipped entirely.
- Clean checkout: the public projection must rebuild from versionable files only.

Everything runs on synthetic fixtures in temporary directories, so it also works in a copy
that is not a Git repository and has no masters; git itself is required.
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_public_music as check

PREVIEW = "hace-tanto-tiempo--luis-guinea--2021.mp3"
PREVIEW_PATH = f"assets/audio/previews/{PREVIEW}"
GIT = shutil.which("git")


class MissingArtworksTest(unittest.TestCase):
    def run_main(self, stripped):
        seen = {}
        is_file_before = Path.is_file

        def fake_check():
            seen["patched"] = Path.is_file is not is_file_before
            seen["artwork_is_file"] = Path.is_file(check.ARTWORK_DIR / "missing.webp")
            return 0

        out = io.StringIO()
        with mock.patch.object(check, "_artworks_stripped", return_value=stripped), \
                mock.patch.object(check, "_check", side_effect=fake_check), \
                contextlib.redirect_stdout(out):
            code = check.main([])
        return code, out.getvalue(), seen

    def test_missing_artworks_warn_and_continue(self):
        code, out, seen = self.run_main(stripped=True)
        self.assertEqual(code, 0)
        self.assertIn("WARNING: assets/images has no .webp files", out)
        self.assertNotIn("FAILED", out)
        self.assertTrue(seen["patched"])
        self.assertTrue(seen["artwork_is_file"])

    def test_present_artworks_are_not_mocked(self):
        code, out, seen = self.run_main(stripped=False)
        self.assertEqual(code, 0)
        self.assertNotIn("WARNING", out)
        self.assertFalse(seen["patched"])


def _tree(root, files, gitignores):
    """Create empty `files` and the given {relative path: content} .gitignore files."""
    for rel, content in gitignores.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for rel in files:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()


def _project_gitignores():
    """The project's real ignore rules; the root .gitignore is material, never optional."""
    rules = {rel: (check.REPO / rel).read_text(encoding="utf-8")
             for rel in check.gitignore_files(check.REPO)}
    if ".gitignore" not in rules:
        raise AssertionError("the project's root .gitignore is missing")
    return rules


def _unauthorized():
    """Unauthorized audio in the zones the old checker skipped (One Page Luis Guinea/, data/)
    and next to the previews, plus every audio extension in both cases at arbitrary paths.
    Upper case lives in another directory: macOS file systems are case-insensitive."""
    return [
        "One Page Luis Guinea/assets/Antes De Irme.mp3",
        "One Page Luis Guinea/assets/Asi Habla El Amor.mp3",
        "One Page Luis Guinea/assets/Nuevo Master.WAV",
        "One Page Luis Guinea/audios/Cantautor/Hace Tanto Tiempo.mp3",
        "data/music-catalog/spikes/essentia/stray master.flac",
        "data/stray.m4a",
        "assets/audio/full-track.mp3",
        "assets/audio/previews/nested/full-track.mp3",
        "assets/audio/previews/full-track.wav",
    ] + [f"somewhere/deep/track{ext}" for ext in sorted(check.AUDIO_EXTENSIONS)] \
      + [f"elsewhere/upper/TRACK{ext.upper()}" for ext in sorted(check.AUDIO_EXTENSIONS)]


class AudioExposureTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(GIT, "git is required to evaluate the project's ignore rules")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def exposure(self, files, gitignores):
        _tree(self.root, files, gitignores)
        errors = []
        check.check_audio_exposure(self.root, {PREVIEW}, errors)
        return errors

    def test_real_rules_ignore_every_unauthorized_audio_and_keep_previews_versionable(self):
        rules = _project_gitignores()
        errors = self.exposure(_unauthorized() + [PREVIEW_PATH], rules)

        self.assertEqual(errors, [])
        ignored = check.ignored_paths(self.root, _unauthorized() + [PREVIEW_PATH])
        self.assertEqual(sorted(set(_unauthorized()) - ignored), [])
        self.assertNotIn(PREVIEW_PATH, ignored)

    def test_unignored_unauthorized_audio_fails_anywhere(self):
        # The rules before the fix: only the masters folder was ignored.
        errors = self.exposure(_unauthorized() + [PREVIEW_PATH],
                               {".gitignore": "One Page Luis Guinea/audios/\n"})

        flagged = {error.rsplit(": ", 1)[1] for error in errors}
        self.assertEqual(flagged, set(_unauthorized()) - {
            "One Page Luis Guinea/audios/Cantautor/Hace Tanto Tiempo.mp3"})
        self.assertTrue(all("versionable" in error for error in errors), errors)

    def test_an_ignored_authorized_preview_is_an_error(self):
        errors = self.exposure([PREVIEW_PATH], {".gitignore": "*.mp3\n"})

        self.assertEqual(errors, [f"authorized preview is ignored by Git (not versionable): "
                                  f"{PREVIEW_PATH}"])

    def test_tracked_audio_fails_even_if_ignored(self):
        rules = _project_gitignores()
        stray = "One Page Luis Guinea/assets/Antes De Irme.mp3"
        _tree(self.root, [stray, PREVIEW_PATH], rules)
        for args in (["init", "-q"], ["add", "-f", "--", stray, PREVIEW_PATH]):
            subprocess.run([GIT, "-C", str(self.root), *args], check=True, capture_output=True)
        errors = []
        check.check_audio_exposure(self.root, {PREVIEW}, errors)

        self.assertEqual(errors, [f"audio tracked by Git outside the authorized previews: {stray}"])

    def test_missing_git_is_an_error_not_a_pass(self):
        _tree(self.root, [PREVIEW_PATH], _project_gitignores())
        errors = []
        with mock.patch.object(check.shutil, "which", return_value=None):
            check.check_audio_exposure(self.root, {PREVIEW}, errors)

        self.assertEqual(len(errors), 1)
        self.assertIn("git is required", errors[0])

    def test_only_lowercase_mp3_directly_under_previews_is_authorized(self):
        rules = _project_gitignores()
        paths = [PREVIEW_PATH, "assets/audio/previews/UPPER.MP3",
                 "assets/audio/previews/Mp3.Mp3", "assets/audio/previews/nested/ok.mp3",
                 "assets/audio/elsewhere.mp3"]
        paths += [f"assets/audio/previews/track{ext}" for ext in sorted(check.AUDIO_EXTENSIONS)
                  if ext != ".mp3"]
        _tree(self.root, paths, rules)
        ignored = check.ignored_paths(self.root, paths)
        self.assertNotIn(PREVIEW_PATH, ignored)
        self.assertEqual(set(paths) - {PREVIEW_PATH}, ignored)

    def test_every_registered_extension_is_detected_case_insensitively(self):
        paths = [f"outside/track{ext}" for ext in sorted(check.AUDIO_EXTENSIONS)]
        paths += [f"outside/UPPER{ext.upper()}" for ext in sorted(check.AUDIO_EXTENSIONS)]
        _tree(self.root, paths + [PREVIEW_PATH], _project_gitignores())
        errors = []
        check.check_audio_exposure(self.root, {PREVIEW}, errors)
        self.assertEqual(errors, [])
        ignored = check.ignored_paths(self.root, paths + [PREVIEW_PATH])
        self.assertEqual(set(paths), ignored)

    def test_lowercase_mp3_directly_under_previews_is_the_only_public_audio(self):
        paths = [PREVIEW_PATH, "assets/audio/previews/UPPER.MP3",
                 "assets/audio/previews/Mp3.Mp3", "assets/audio/previews/nested/ok.mp3"]
        paths += [f"assets/audio/previews/track{ext}" for ext in sorted(check.AUDIO_EXTENSIONS)
                  if ext != ".mp3"]
        paths += [f"outside/track{ext}" for ext in sorted(check.AUDIO_EXTENSIONS)]
        _tree(self.root, paths, _project_gitignores())
        errors = []
        check.check_audio_exposure(self.root, {PREVIEW}, errors)
        self.assertEqual(errors, [])
        ignored = check.ignored_paths(self.root, paths)
        self.assertEqual(ignored, set(paths) - {PREVIEW_PATH})


class CleanCheckoutReproducibilityTest(unittest.TestCase):
    """The projection must rebuild from versionable files only (no bank, masters, spike output)."""

    PIPELINE_TREES = ("data/music-catalog", "assets/audio/previews")

    def test_public_projection_rebuilds_from_versionable_files_only(self):
        self.assertTrue(GIT, "git is required to evaluate the project's ignore rules")
        candidates = []
        for top in self.PIPELINE_TREES:
            for path in sorted((check.REPO / top).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    candidates.append(path.relative_to(check.REPO).as_posix())
        ignored = check.ignored_paths(check.REPO, candidates)
        versionable = [rel for rel in candidates if rel not in ignored]
        # The spike bank stays private: the copy below really lacks it.
        bank = "data/music-catalog/spikes/essentia/human_classification_bank.json"
        self.assertIn(bank, check.ignored_paths(check.REPO, [bank]))
        self.assertNotIn(bank, versionable)
        master = json.loads((check.REPO / "data/music-catalog/catalog_master.json")
                            .read_text(encoding="utf-8"))
        artworks = sorted({(w.get("artwork") or {}).get("web_file") for w in master} - {None})
        self.assertEqual(check.ignored_paths(check.REPO, artworks), set())

        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp)
            for rel in versionable:
                (clean / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(check.REPO / rel, clean / rel)
            # Versionable web artworks: the generator only checks that they exist.
            _tree(clean, artworks, {})
            output = clean / "music-data.js"
            subprocess.run(
                [sys.executable, str(clean / "data/music-catalog/generate_public_music_data.py"),
                 "--output", str(output)],
                cwd=clean, check=True, capture_output=True, text=True,
            )
            generated = output.read_text(encoding="utf-8")

        self.assertEqual(generated, check.PUBLIC_JS.read_text(encoding="utf-8"))
        self.assertIn(
            "{ title:'Hace Tanto Tiempo', artist:'Luis Guinea', role:'Artist', "
            "artwork:'Hace-Tanto-Tiempo---Luis-Guinea.webp', releaseType:'Single', year:2021, "
            "roles:['Artist'], preview:'hace-tanto-tiempo--luis-guinea--2021.mp3' }",
            generated,
        )


if __name__ == "__main__":
    unittest.main()
