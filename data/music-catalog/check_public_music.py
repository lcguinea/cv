#!/usr/bin/env python3
"""Read-only contract check for the browser-safe /music/ catalogue and its audio previews."""

import io
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import generate_music_previews as previews
import generate_public_music_data as generator
import test_check_public_music
import test_generate_music_previews
import test_generate_public_music_data
import test_music_filter_i18n
import test_music_preview_frontend


REPO = HERE.parent.parent
MUSIC_HTML = REPO / "music" / "index.html"
PUBLIC_JS = REPO / "js" / "music-data.js"
PLAYER_JS = REPO / "js" / "player.js"
MUSIC_PAGE_JS = REPO / "js" / "music-page.js"
_REAL_PATH_IS_FILE = Path.is_file
ARTWORK_DIR = REPO / "assets" / "images"
PREVIEW_DIR = REPO / previews.OUTPUT_DIR
SOURCE_ROOT = REPO.joinpath(*previews.SOURCE_ROOT)
# Kept in sync with the root .gitignore, which makes all of them unversionable everywhere
# except the validated previews (test_check_public_music proves it with the real rules).
# The policy treats suffixes case-insensitively; callers compare ``suffix.lower()``.
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".oga", ".opus", ".aif",
    ".aiff", ".aifc", ".wma", ".weba", ".webm", ".mka", ".amr", ".caf", ".au",
    ".mid", ".midi", ".ape", ".wv",
}
AUDIO_EXTENSION_PATTERN = "|".join(
    re.escape(extension[1:]) for extension in sorted(AUDIO_EXTENSIONS, key=len, reverse=True)
)
FOCUSED_TESTS = (test_generate_public_music_data, test_generate_music_previews,
                 test_music_preview_frontend, test_music_filter_i18n, test_check_public_music)


def _is_artwork_path(path):
    return path.suffix.lower() == ".webp" and path.parent == ARTWORK_DIR


def _is_file_without_source_artworks(path):
    if _is_artwork_path(path):
        return True
    return _REAL_PATH_IS_FILE(path)


def _artworks_stripped():
    """True only when this checkout has no web artwork at all (text-only sandbox copy).

    A normal checkout has them, so nothing is mocked there and a missing artwork fails.
    """
    if not ARTWORK_DIR.is_dir():
        return True
    return not any(_is_artwork_path(path) for path in ARTWORK_DIR.iterdir())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-missing-artworks",
        action="store_true",
        help="accepted for compatibility; missing artworks now always only warn",
    )
    parser.parse_args(argv)
    if _artworks_stripped():
        # Isolated sandbox copies do not include the .webp artworks: warn instead of aborting.
        print("WARNING: assets/images has no .webp files (isolated copy): "
              "artwork existence is NOT verified in this run")
        with mock.patch.object(Path, "is_file", new=_is_file_without_source_artworks):
            return _check()
    return _check()


def _check():
    errors = []

    warnings = []
    test_output = io.StringIO()
    test_suite = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromModule(module) for module in FOCUSED_TESTS
    )
    test_result = unittest.TextTestRunner(stream=test_output).run(test_suite)
    if not test_result.wasSuccessful():
        detail = test_output.getvalue().strip()
        errors.append("focused unittest failed" + (f":\n{detail}" if detail else ""))

    try:
        master = json.loads(generator.MASTER.read_text(encoding="utf-8"))
        selection = json.loads(generator.SELECTION.read_text(encoding="utf-8"))
        decisions = json.loads(generator.DECISIONS.read_text(encoding="utf-8"))
        manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        rows, exclusions = generator.project_with_exclusions(
            master, selection, decisions, repo=REPO, manifest=manifest)
        expected_js = generator.serialize(rows)
        actual_js = PUBLIC_JS.read_text(encoding="utf-8")
        expected_log = generator.exclusions_log(rows, exclusions, selection)
        if json.loads(generator.EXCLUSIONS_LOG.read_text(encoding="utf-8")) != expected_log:
            errors.append(f"{generator.EXCLUSIONS_LOG.name} is not identical to the current generator output")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot build the public projection: {exc}")
        rows, exclusions, decisions, selection, expected_js, actual_js = [], [], {}, {}, "", ""
        manifest = None
    preview_names = _check_previews(manifest, selection, decisions, errors, warnings)

    if actual_js != expected_js:
        errors.append("js/music-data.js is not identical to the current generator output")

    try:
        html = MUSIC_HTML.read_text(encoding="utf-8")
        engine = PLAYER_JS.read_text(encoding="utf-8")
        page = MUSIC_PAGE_JS.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read the /music/ frontend: {exc}")
        html = engine = page = ""
    # /music/ loads the public data, then the global engine, then the page view, in that order.
    scripts = re.findall(r"<script\s+[^>]*src=[\"']([^\"']+)[\"'][^>]*></script>", html, re.IGNORECASE)
    if scripts[-3:] != ["../js/music-data.js", "../js/player.js", "../js/music-page.js"]:
        errors.append("music/index.html must load ../js/music-data.js, ../js/player.js and ../js/music-page.js last, in that order")
    if "window.MUSIC_DATA" not in engine:
        errors.append("js/player.js does not consume MUSIC_DATA")
    # One engine-owned player element (exclusive playback) that only ever loads a validated preview.
    pages = [html] + [(REPO / rel).read_text(encoding="utf-8") for rel in ("index.html", "cv.html") if (REPO / rel).is_file()]
    if any(re.search(r"<audio\b", markup) for markup in pages) or engine.count("createElement('audio')") != 1 \
            or "audio.src=previewUrl(tracks[i].preview)" not in engine or re.search(r"createElement\(|new Audio\b|\.play\(", page):
        errors.append("the global engine in js/player.js must own the only <audio> element, whose source "
                      "is only previewUrl(tracks[i].preview); pages must not declare their own")
    if "new URL('assets/audio/previews/'+encodeURIComponent(name),root)" not in engine \
            or any(re.search(r"(?i)\bautoplay\b", markup) for markup in pages + [engine]):
        errors.append("js/player.js does not confine preview URLs to assets/audio/previews/")
    consumed_fields = set(re.findall(r"\bx\.([A-Za-z_$][\w$]*)", engine + page))
    expected_fields = set(generator.PUBLIC_FIELDS)
    if consumed_fields != expected_fields:
        errors.append(
            "/music/ frontend field contract differs: "
            f"expected {sorted(expected_fields)}, found {sorted(consumed_fields)}"
        )

    for index, row in enumerate(rows, start=1):
        if set(row) != expected_fields:
            errors.append(f"public row {index} has unexpected fields: {sorted(row)}")
        if row.get("role") not in generator.ALLOWED_ROLES:
            errors.append(f"public row {index} has unsupported role: {row.get('role')!r}")
        artwork = row.get("artwork", "")
        if Path(artwork).name != artwork or not (REPO / "assets" / "images" / artwork).is_file():
            errors.append(f"public row {index} has a missing or unsafe artwork: {artwork!r}")
        preview = row.get("preview")
        if preview is None:
            errors.append(f"public row {index} is published without a preview")
        elif preview not in preview_names:
            errors.append(f"public row {index} publishes an unvalidated preview: {preview!r}")

    forbidden = {
        "local user path": r"(?i)(?:/Users/|[A-Z]:\\Users\\)",
        "private source path": r"(?i)One Page Luis Guinea",
        "audio reference": rf"(?i)audio_ref|\.(?:{AUDIO_EXTENSION_PATTERN})\b",
        "master name": r"(?i)\bmaster(?:[\s._/-]|$)",
        "ISRC": r"(?i)\bisrc\b",
        "platform URL or key": r"(?i)https?://|spotify|apple[_ ]?music|music\.apple\.com",
        "internal key": r"(?i)provenance|conflict|catalog_link|internal|human_review",
    }
    # Only validated preview file names may carry an audio extension in the bundle.
    scanned_js = re.sub(
        r"preview:'([a-z0-9-]+\.mp3)'",
        lambda m: "preview:''" if m.group(1) in preview_names else m.group(0),
        actual_js,
    )
    for label, pattern in forbidden.items():
        if re.search(pattern, scanned_js):
            errors.append(f"public JavaScript contains forbidden {label}")

    classifications = decisions.get("classifications", []) if isinstance(decisions, dict) else []
    mapped = [item for item in classifications if (item.get("catalog_link") or {}).get("status") == "mapped"]
    open_cases = [item for item in classifications if (item.get("catalog_link") or {}).get("status") == "unmapped"]
    # Historical baseline was 32 classifications / 21 mapped / 11 open. Eight explicit
    # mapped decisions extend the canonical layer to 40 / 29 / 11.
    if (len(classifications), len(mapped), len(open_cases)) != (40, 29, 11):
        errors.append(
            "human decision counts changed: "
            f"{len(classifications)} classifications, {len(mapped)} mappings, {len(open_cases)} open"
        )
    by_review = {item.get("review_id"): item for item in classifications}
    excluded = {
        item.get("review_id") for item in classifications if item.get("public_exclusion") is True
    }
    for entry in selection.get("entries", []) if isinstance(selection, dict) else []:
        review_id = entry.get("review_id")
        item = by_review.get(review_id)
        if item is None or (item.get("catalog_link") or {}).get("status") != "mapped":
            errors.append(f"public selection uses open or unknown case #{review_id}")
        if review_id in excluded:
            errors.append(f"public selection uses explicitly excluded case #{review_id}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        print(f"PUBLIC MUSIC CHECK FAILED: {len(errors)} error(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "PUBLIC MUSIC CHECK OK: "
        f"{len(rows)} public works; {len(classifications)} classifications; "
        f"{len(mapped)} mappings; {len(open_cases)} open cases; "
        f"{len(preview_names)} validated previews (<= {previews.MAX_PREVIEW_S:.0f} s), "
        f"{len(exclusions)} selected works excluded without a reproducible preview"
    )
    return 0


def _check_previews(manifest, selection, decisions, errors, warnings):
    """Validate manifest -> source -> preview traceability; return the validated file names."""
    try:
        entries = previews.validate_manifest(manifest, selection, decisions)
    except (ValueError, TypeError, AttributeError) as exc:
        errors.append(f"invalid preview manifest: {exc}")
        return set()
    if len(entries) != 21:
        errors.append(f"preview manifest has {len(entries)} entries, expected 21")
    verified = [entry for entry in entries if entry["status"] == "verified"]
    expected = {PurePosixPath(entry["preview"]).name for entry in verified}

    present = sorted(p.name for p in PREVIEW_DIR.iterdir()) if PREVIEW_DIR.is_dir() else []
    for name in sorted(set(present) - expected):
        errors.append(f"{previews.OUTPUT_DIR} contains an undeclared file: {name}")
    check_audio_exposure(REPO, expected, errors)

    sources_available = SOURCE_ROOT.is_dir()
    if not sources_available:
        warnings.append(f"{'/'.join(previews.SOURCE_ROOT)} is absent (private masters are not "
                        "versioned): source sha256 and byte-identical regeneration NOT verified")
    validated = set()
    with tempfile.TemporaryDirectory() as tmp:
        for entry in verified:
            label = f"#{entry['review_id']} {entry['work_id']}"
            output = REPO / entry["preview"]
            if not output.is_file():
                errors.append(f"{label}: preview {entry['preview']} does not exist")
                continue
            try:
                previews.check_preview(output)
            except ValueError as exc:
                errors.append(f"{label}: {exc}")
                continue
            preview_sha = previews.sha256_file(output)
            if preview_sha != entry["preview_sha256"]:
                errors.append(f"{label}: preview sha256 differs from the manifest")
                continue
            if preview_sha == entry["source_sha256"]:
                errors.append(f"{label}: the preview is a copy of the private master")
                continue
            if sources_available:
                try:
                    source = previews.resolve_source(entry["source"], REPO)
                    if previews.sha256_file(source) != entry["source_sha256"]:
                        raise ValueError("source sha256 differs from the manifest")
                    rebuilt = Path(tmp) / output.name
                    previews.encode(source, rebuilt, entry)
                    if previews.sha256_file(rebuilt) != preview_sha:
                        raise ValueError("preview bytes differ from a fresh deterministic encode "
                                         "of the authorized source")
                except ValueError as exc:
                    errors.append(f"{label}: {exc}")
                    continue
                if shutil.which("git"):
                    ignored = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", entry["source"]],
                                             capture_output=True)
                    if ignored.returncode == 1:
                        errors.append(f"{label}: private source is not ignored by Git")
            validated.add(output.name)
    return validated


def gitignore_files(repo):
    """Relative POSIX paths of every .gitignore of the project (outside .git)."""
    found = []
    for directory, subdirs, files in os.walk(repo):
        subdirs[:] = sorted(d for d in subdirs if d != ".git")
        if ".gitignore" in files:
            found.append((Path(directory) / ".gitignore").relative_to(repo).as_posix())
    return found


def _git_env():
    """Only the project's rules count: no user/system config or global excludes."""
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def ignored_paths(repo, paths):
    """Return the subset of `paths` (relative POSIX) ignored by the project's .gitignore files.

    The rules are evaluated in a throw-away Git repository that holds only copies of those
    .gitignore files (plus empty placeholders for `paths`), so this works in copies that are
    not Git checkouts. Matching is case-sensitive. Raises RuntimeError without git.
    """
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git is required to evaluate the project's ignore rules")
    paths = list(paths)
    if not paths:
        return set()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "rules"
        env = _git_env()
        init = subprocess.run([git, "init", "-q", str(root)], capture_output=True, env=env)
        if init.returncode != 0:
            raise RuntimeError(f"git init failed: {init.stderr.decode(errors='replace').strip()}")
        for rel in gitignore_files(repo):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(repo) / rel, root / rel)
        for rel in paths:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).touch()
        result = subprocess.run(
            [git, "-C", str(root), "-c", f"core.excludesFile={os.devnull}",
             "-c", "core.ignoreCase=false", "check-ignore", "--no-index", "-z", "--stdin"],
            input="".join(f"{rel}\0" for rel in paths).encode("utf-8"),
            capture_output=True, env=env,
        )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore failed: {result.stderr.decode(errors='replace').strip()}")
    reported = {unicodedata.normalize("NFC", item)
                for item in result.stdout.decode("utf-8").split("\0") if item}
    return {rel for rel in paths if unicodedata.normalize("NFC", rel) in reported}


def _tracked_files(repo):
    """Tracked files when `repo` is the top level of a Git checkout, else None."""
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git is required to list tracked files")
    top = subprocess.run([git, "-C", str(repo), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, env=_git_env())
    if top.returncode != 0 and (Path(repo) / ".git").exists():
        raise RuntimeError(f"git cannot read this checkout: {top.stderr.strip()}")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(repo).resolve():
        return None
    listed = subprocess.run([git, "-C", str(repo), "ls-files", "-z"], capture_output=True,
                            env=_git_env())
    if listed.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {listed.stderr.decode(errors='replace').strip()}")
    return [item for item in listed.stdout.decode("utf-8").split("\0") if item]


def check_audio_exposure(repo, authorized, errors):
    """No audio may be versionable or publishable outside the authorized previews.

    `authorized` are the verified manifest file names inside OUTPUT_DIR. Every audio file of
    the working tree, in any directory (One Page Luis Guinea/ and data/ included), must be
    ignored by the project's Git rules unless it is one of them; the authorized previews must
    stay versionable; in a Git checkout no other audio may be tracked.
    """
    repo = Path(repo)
    allowed = {f"{previews.OUTPUT_DIR}/{name}" for name in authorized}
    present = []
    for directory, subdirs, files in os.walk(repo):
        subdirs[:] = sorted(d for d in subdirs if d != ".git")
        for name in sorted(files):
            if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                present.append((Path(directory) / name).relative_to(repo).as_posix())
    try:
        ignored = ignored_paths(repo, sorted(set(present) | allowed))
        tracked = _tracked_files(repo)
    except RuntimeError as exc:
        errors.append(f"cannot audit audio exposure: {exc}")
        return
    for rel in present:
        if rel not in allowed and rel not in ignored:
            errors.append(f"audio outside the authorized previews is versionable/publishable: {rel}")
    for rel in sorted(allowed & ignored):
        errors.append(f"authorized preview is ignored by Git (not versionable): {rel}")
    for rel in tracked or []:
        if Path(rel).suffix.lower() in AUDIO_EXTENSIONS and rel not in allowed:
            errors.append(f"audio tracked by Git outside the authorized previews: {rel}")


if __name__ == "__main__":
    sys.exit(main())
