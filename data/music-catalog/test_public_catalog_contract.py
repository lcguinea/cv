#!/usr/bin/env python3
"""Contract of the real public music catalogue (js/music-data.js), standard library only.

Every published song must have a valid preview: a file that exists inside assets/audio/previews/,
in a browser-playable format (MPEG-1/2 Layer III, .mp3) and lasting 45 seconds or less (declared
duration when the row has one, otherwise the real duration read from the MP3 frames). No public
path may point to One Page Luis Guinea, to the private audio folder or to a master. Songs left out
must be recorded in public_catalog_exclusions.json, and .gitignore must keep the private folder and
every non-preview audio out of Git.

Run: python3 data/music-catalog/test_public_catalog_contract.py   ->   PUBLIC_CATALOG_CONTRACT_OK
"""

import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLIC_JS = REPO / "js" / "music-data.js"
PREVIEW_DIR = REPO / "assets" / "audio" / "previews"
PRIVATE_DIR = REPO / "One Page Luis Guinea"
SELECTION = HERE / "public_music_selection.json"
EXCLUSIONS = HERE / "public_catalog_exclusions.json"
GITIGNORE = REPO / ".gitignore"
MAX_PREVIEW_S = 45.0
PREVIEW_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*\.mp3$")
FORBIDDEN = re.compile(r"one page luis guinea|one%20page|audios/|master|\.\./|^/|\\", re.I)
FIELDS = ("title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview")

failures = []


def fail(message):
    failures.append(message)


# ----------------------------------------------------------------- minimal JS literal parser

class Parser:
    """Parses the JSON-like subset emitted by generate_public_music_data.py (bare keys, '…' strings)."""

    def __init__(self, text):
        self.text, self.pos = text, 0

    def ws(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def value(self):
        self.ws()
        ch = self.text[self.pos]
        if ch == "[":
            return self.array()
        if ch == "{":
            return self.object()
        if ch in "'\"":
            return self.string()
        match = re.compile(r"-?\d+(\.\d+)?|null|true|false").match(self.text, self.pos)
        if not match:
            raise ValueError(f"unexpected token at {self.pos}: {self.text[self.pos:self.pos + 20]!r}")
        self.pos = match.end()
        token = match.group(0)
        if token in ("null", "true", "false"):
            return {"null": None, "true": True, "false": False}[token]
        return float(token) if "." in token else int(token)

    def string(self):
        quote, self.pos, out = self.text[self.pos], self.pos + 1, []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "'": "'", '"': '"'}
        while self.text[self.pos] != quote:
            ch = self.text[self.pos]
            if ch == "\\":
                nxt = self.text[self.pos + 1]
                if nxt == "u":
                    out.append(chr(int(self.text[self.pos + 2:self.pos + 6], 16)))
                    self.pos += 6
                    continue
                out.append(escapes.get(nxt, nxt))
                self.pos += 2
                continue
            out.append(ch)
            self.pos += 1
        self.pos += 1
        return "".join(out)

    def array(self):
        self.pos += 1
        items = []
        while True:
            self.ws()
            if self.text[self.pos] == "]":
                self.pos += 1
                return items
            items.append(self.value())
            self.ws()
            if self.text[self.pos] == ",":
                self.pos += 1

    def object(self):
        self.pos += 1
        result = {}
        while True:
            self.ws()
            if self.text[self.pos] == "}":
                self.pos += 1
                return result
            match = re.compile(r"[A-Za-z_$][\w$]*").match(self.text, self.pos)
            if match:
                key, self.pos = match.group(0), match.end()
            else:
                key = self.string()
            self.ws()
            if self.text[self.pos] != ":":
                raise ValueError(f"expected ':' at {self.pos}")
            self.pos += 1
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = self.value()
            self.ws()
            if self.text[self.pos] == ",":
                self.pos += 1


def load_public_rows():
    text = PUBLIC_JS.read_text(encoding="utf-8")
    match = re.search(r"window\.MUSIC_DATA\s*=\s*", text)
    if not match:
        raise ValueError("js/music-data.js does not assign window.MUSIC_DATA")
    parser = Parser(text)
    parser.pos = match.end()
    rows = parser.value()
    parser.ws()
    if text[parser.pos:].strip() not in (";", ""):
        raise ValueError("unexpected content after window.MUSIC_DATA")
    return text, rows


# ----------------------------------------------------------------- MP3 reader (independent of the generator)

_BITRATES = {
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _frame(data, pos):
    if pos + 4 > len(data) or data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
        return None
    version, layer = (data[pos + 1] >> 3) & 3, (data[pos + 1] >> 1) & 3
    bitrate_index, rate_index = data[pos + 2] >> 4, (data[pos + 2] >> 2) & 3
    if version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
        return None  # only Layer III (what browsers call MP3) is accepted
    bitrate = _BITRATES[(3 if version == 3 else 2, 1)][bitrate_index] * 1000
    rate = _RATES[version][rate_index]
    padding = (data[pos + 2] >> 1) & 1
    samples = 1152 if version == 3 else 576
    length = (144 if version == 3 else 72) * bitrate // rate + padding
    return rate, samples, length


def mp3_duration(path):
    """Real duration from every MPEG Layer III frame; headers are not trusted (they can under-report)."""
    data = path.read_bytes()
    pos = 0
    while data[pos:pos + 3] == b"ID3":
        size = 0
        for byte in data[pos + 6:pos + 10]:
            size = (size << 7) | (byte & 0x7F)
        pos += 10 + size + (10 if data[pos + 5] & 0x10 else 0)
    first = _frame(data, pos)
    if not first or not _frame(data, pos + first[2]):
        raise ValueError("does not start with two consecutive MPEG Layer III frames")
    rate, total = first[0], 0
    while True:
        frame = _frame(data, pos)
        if not frame or frame[2] <= 0 or pos + frame[2] > len(data):
            break
        total += frame[1]
        pos += frame[2]
    rest = data[pos:]
    if rest and not (len(rest) == 128 and rest[:3] == b"TAG"):
        raise ValueError(f"{len(rest)} unexpected bytes after the last frame")
    return total / rate


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------- checks

def check_rows(text, rows):
    if not isinstance(rows, list) or not rows:
        fail("window.MUSIC_DATA must be a non-empty list")
        return []
    if re.search(r"one page luis guinea|audios/", text, re.I):
        fail("js/music-data.js mentions One Page Luis Guinea or the private audios/ folder")
    names = []
    for index, row in enumerate(rows, start=1):
        label = f"row {index} ({row.get('title') if isinstance(row, dict) else '?'})"
        if not isinstance(row, dict):
            fail(f"{label}: not an object")
            continue
        missing = [field for field in FIELDS if field not in row]
        if missing:
            fail(f"{label}: missing public fields {missing}")
        preview = row.get("preview")
        if not isinstance(preview, str) or not PREVIEW_NAME.match(preview):
            fail(f"{label}: published without a valid preview file name: {preview!r}")
            continue
        for field in ("preview", "artwork"):
            value = row.get(field)
            if isinstance(value, str) and FORBIDDEN.search(value):
                fail(f"{label}: public {field} {value!r} points to a private folder or a master")
        path = (PREVIEW_DIR / preview)
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, OSError):
            fail(f"{label}: preview does not exist on disk: assets/audio/previews/{preview}")
            continue
        if resolved.parent != PREVIEW_DIR.resolve() or not resolved.is_file():
            fail(f"{label}: preview resolves outside assets/audio/previews/: {resolved}")
            continue
        try:
            real = mp3_duration(resolved)
        except (ValueError, IndexError, struct.error) as exc:
            fail(f"{label}: preview is not a playable MP3: {exc}")
            continue
        declared = row.get("previewDuration")
        duration = declared if isinstance(declared, (int, float)) and not isinstance(declared, bool) else real
        if not 0 < duration <= MAX_PREVIEW_S:
            fail(f"{label}: preview lasts {duration:.3f} s, outside (0, {MAX_PREVIEW_S}]")
        if not 0 < real <= MAX_PREVIEW_S:
            fail(f"{label}: preview file lasts {real:.3f} s, outside (0, {MAX_PREVIEW_S}]")
        if preview in names:
            fail(f"{label}: preview {preview} is published twice")
        names.append(preview)
    return names


def check_not_a_master_copy(names):
    audios = PRIVATE_DIR / "audios"
    if not audios.is_dir():
        return  # private folder absent (clean checkout): nothing to compare against
    private = {sha256(p) for p in audios.rglob("*") if p.is_file() and p.name != ".DS_Store"}
    for name in names:
        if sha256(PREVIEW_DIR / name) in private:
            fail(f"preview {name} is a byte-for-byte copy of a private master")


def check_exclusions(rows):
    selection = [e["review_id"] for e in json.loads(SELECTION.read_text(encoding="utf-8"))["entries"]]
    if not EXCLUSIONS.is_file():
        fail("public_catalog_exclusions.json (exclusion log) does not exist")
        return
    log = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    published = log.get("published") or []
    excluded = [item.get("review_id") for item in log.get("excluded") or []]
    if len(published) != len(rows):
        fail(f"exclusion log publishes {len(published)} works but js/music-data.js has {len(rows)}")
    if set(published) & set(excluded):
        fail("a review_id is both published and excluded")
    if sorted(published + excluded) != sorted(selection):
        fail("published + excluded must be exactly the public selection")
    for item in log.get("excluded") or []:
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            fail(f"exclusion #{item.get('review_id')} has no reason")
    if [r.get("preview") for r in rows] != [p.get("preview") for p in log.get("published_previews") or []]:
        fail("exclusion log published_previews differ from js/music-data.js")


def check_gitignore():
    rules = [line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()]
    if not any(rule in ("One Page Luis Guinea/", "/One Page Luis Guinea/") for rule in rules):
        fail(".gitignore does not ignore the whole One Page Luis Guinea/ folder")
    git = shutil.which("git")
    if not git or not (REPO / ".git").exists():
        return
    probes = {
        "One Page Luis Guinea/CLASIFICACION_HUMANA_MUSICA.md": True,
        "One Page Luis Guinea/audios/Cantautor/x.mp3": True,
        "data/music-catalog/x_master.wav": True,
        "assets/audio/x.m4a": True,
        "assets/audio/previews/x.wav": True,
        "assets/audio/previews/sub/x.mp3": True,
        "assets/audio/previews/x.mp3": False,
    }
    env = {"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(REPO), "PATH": "/usr/bin:/bin:/opt/homebrew/bin"}
    for probe, should_ignore in probes.items():
        result = subprocess.run([git, "-C", str(REPO), "check-ignore", "-q", "--no-index", probe],
                                capture_output=True, text=True, env=env)
        if result.returncode not in (0, 1):
            fail(f"git check-ignore failed for {probe}: {result.stderr.strip()}")
        elif (result.returncode == 0) != should_ignore:
            fail(f".gitignore {'does not ignore' if should_ignore else 'ignores'} {probe}")


def main():
    try:
        text, rows = load_public_rows()
    except (OSError, ValueError, IndexError) as exc:
        print(f"FAIL cannot load the public catalogue: {exc}", file=sys.stderr)
        return 1
    names = check_rows(text, rows)
    check_not_a_master_copy(names)
    check_exclusions(rows)
    check_gitignore()
    if failures:
        for message in failures:
            print(f"FAIL {message}", file=sys.stderr)
        return 1
    print("PUBLIC_CATALOG_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
