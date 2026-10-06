#!/usr/bin/env python3
"""Build the public site artifact for GitHub Pages and validate it.

Copies an explicit allowlist of tracked files into _site/ (or --out DIR) and then checks the result:
only authorised files, no repository Markdown, tests, catalogue data, scripts or masters, exactly the
16 verified previews (sha256 from music_preview_manifest.json) and no broken local reference in the
pages or the stylesheet. Artwork and previews are the ones js/music-data.js publishes, so the
artifact carries only the images and audio the site actually uses.

The artifact is served as is: at https://luisguinea.com/ in production and at a temporary
https://<user>.github.io/<repo>/ preview. Every page uses relative URLs, so both roots work.

Standard library only. Run: python3 tools/build_site.py [--out DIR]
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "_site"
MUSIC_DATA = "js/music-data.js"
MANIFEST = ROOT / "data" / "music-catalog" / "music_preview_manifest.json"
PREVIEW_DIR = "assets/audio/previews"
ARTWORK_DIR = "assets/images"
EXPECTED_PREVIEWS = 16

PAGES = ("index.html", "cv.html", "music/index.html", "404.html")
STATIC_FILES = PAGES + (
    "robots.txt",
    "sitemap.xml",
    "css/styles.css",
    "js/theme-init.js",
    "js/strings.js",
    "js/i18n.js",
    "js/site.js",
    MUSIC_DATA,
    "js/player.js",
    "js/music-page.js",
    "fonts/instrument-serif-latin-400-normal.woff2",
    "fonts/instrument-serif-latin-400-italic.woff2",
    "fonts/inter-latin-wght-normal.woff2",
    "fonts/ibm-plex-mono-latin-400-normal.woff2",
    "fonts/OFL-InstrumentSerif.txt",
    "fonts/OFL-Inter.txt",
    "fonts/OFL-IBMPlexMono.txt",
    "assets/images/profile.webp",
)

ALLOWED_SUFFIXES = {".html", ".css", ".js", ".woff2", ".txt", ".xml", ".webp", ".mp3"}
# Same audio extensions the repository refuses to version (.gitignore, check_public_music.py).
AUDIO_SUFFIXES = {".mp3", ".wav", ".wave", ".m4a", ".aif", ".aiff", ".aifc", ".flac", ".ogg", ".oga",
                  ".aac", ".opus", ".wma", ".mp4", ".alac", ".caf", ".mp2", ".mka", ".amr", ".au",
                  ".ac3", ".dts", ".weba", ".webm", ".midi", ".mid", ".ape", ".wv"}
FORBIDDEN_PARTS = {"tests", "data", "tools", "internal", "spikes", "sample_v1", ".github", ".git",
                   "One Page Luis Guinea", "estado", ".orchestrator", ".claude", "__pycache__"}
FORBIDDEN_NAMES = {"catalog_master.json", "CV_MASTER.md", "BRAND.md", "PROPUESTA.md", "README.md",
                   "local-server.js", "cover.png", "profile_pic.png", ".DS_Store", ".gitignore"}
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)


def music_files(root=ROOT):
    """Artwork and preview file names published by js/music-data.js, one entry per line."""
    artworks, previews = [], []
    for line in (root / MUSIC_DATA).read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("{ title:"):
            continue
        artwork = re.search(r"\bartwork:'([^']+)'", line)
        preview = re.search(r"\bpreview:'([^']+)'", line)
        if not artwork or not preview:
            raise ValueError(f"{MUSIC_DATA}: entry without artwork or preview: {line.strip()[:80]}")
        artworks.append(f"{ARTWORK_DIR}/{artwork.group(1)}")
        previews.append(f"{PREVIEW_DIR}/{preview.group(1)}")
    return artworks, previews


def allowlist(root=ROOT):
    artworks, previews = music_files(root)
    return list(STATIC_FILES) + sorted(set(artworks)) + previews


def tracked_files(root=ROOT):
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


def verified_previews():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {PurePosixPath(e["preview"]).name: e["preview_sha256"]
            for e in manifest["entries"] if e.get("status") == "verified" and e.get("preview")}


def build(out=DEFAULT_OUT, root=ROOT):
    out = Path(out).resolve()
    if out == root or root.is_relative_to(out):
        raise SystemExit(f"refusing to build into {out}")
    files = allowlist(root)
    tracked = tracked_files(root)
    missing = [f for f in files if f not in tracked]
    if missing:
        raise SystemExit("not tracked by Git, refusing to publish: " + ", ".join(missing))
    if out.exists():
        shutil.rmtree(out)
    for rel in files:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
    return files


def artifact_files(out):
    out = Path(out)
    return sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file() or p.is_symlink())


def _local_refs(text, kind):
    if kind == "html":
        return re.findall(r'\b(?:href|src)="([^"]*)"', text)
    return [u.strip("'\"") for u in re.findall(r"url\(([^)]*)\)", text)]


def _resolve(base, ref, out):
    """Artifact path a local reference points to, or None when it leaves the artifact."""
    path = unquote(urlsplit(ref).path)
    if not path:
        return base
    joined = PurePosixPath("/") / path if path.startswith("/") else PurePosixPath("/") / PurePosixPath(base).parent / path
    parts = []
    for part in joined.parts[1:]:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part != ".":
            parts.append(part)
    rel = "/".join(parts)
    if path.endswith("/") or not rel or (Path(out) / rel).is_dir():
        rel = (rel + "/index.html").lstrip("/")
    return rel


def validate(out=DEFAULT_OUT, root=ROOT):
    """Return a list of problems; empty means the artifact is publishable."""
    out = Path(out)
    errors = []
    present = artifact_files(out)
    expected = set(allowlist(root))
    for rel in sorted(set(present) - expected):
        errors.append(f"unexpected file: {rel}")
    for rel in sorted(expected - set(present)):
        errors.append(f"missing file: {rel}")
    previews = verified_previews()
    audio = []
    for rel in present:
        p = PurePosixPath(rel)
        if (out / rel).is_symlink():
            errors.append(f"symlink: {rel}")
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            errors.append(f"file type not allowed: {rel}")
        if p.suffix.lower() == ".md":
            errors.append(f"Markdown: {rel}")
        if FORBIDDEN_PARTS & set(p.parts[:-1]) or p.name in FORBIDDEN_NAMES or p.name.startswith("."):
            errors.append(f"private or development file: {rel}")
        if p.suffix.lower() in AUDIO_SUFFIXES:
            audio.append(rel)
            if str(p.parent) != PREVIEW_DIR or p.suffix != ".mp3":
                errors.append(f"audio outside {PREVIEW_DIR}: {rel}")
            elif p.name not in previews:
                errors.append(f"audio that is not a verified preview: {rel}")
            elif hashlib.sha256((out / rel).read_bytes()).hexdigest() != previews[p.name]:
                errors.append(f"preview differs from its manifest sha256: {rel}")
    if len(audio) != EXPECTED_PREVIEWS:
        errors.append(f"expected {EXPECTED_PREVIEWS} previews, found {len(audio)}")
    for rel in present:
        kind = {".html": "html", ".css": "css"}.get(PurePosixPath(rel).suffix)
        if not kind:
            continue
        for ref in _local_refs((out / rel).read_text(encoding="utf-8"), kind):
            if EXTERNAL.match(ref):
                continue
            target = _resolve(rel, ref, out)
            if target is None or not (out / target).is_file():
                errors.append(f"broken local reference in {rel}: {ref}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="artifact directory (default: _site)")
    args = parser.parse_args(argv)
    files = build(args.out)
    errors = validate(args.out)
    if errors:
        print(f"SITE ARTIFACT FAILED: {len(errors)} error(s)")
        for e in errors:
            print(" -", e)
        return 1
    size = sum((Path(args.out) / f).stat().st_size for f in files)
    print(f"SITE ARTIFACT OK: {len(files)} files, {size} bytes in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
