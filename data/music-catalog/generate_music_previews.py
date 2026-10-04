#!/usr/bin/env python3
"""Generate the short public MP3 previews declared in music_preview_manifest.json.

Each verified manifest entry ties review_id -> work_id (human mapping) -> private source
(path + sha256) -> public preview assets/audio/previews/<work_id>.mp3. Masters are only
read, never copied: ffmpeg encodes a uniform window (manifest policy) with no embedded
metadata and bitexact flags, so the same source always yields the same bytes.

Usage: python3 data/music-catalog/generate_music_previews.py
Success: MUSIC PREVIEWS OK: <n> generated ...
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MANIFEST = HERE / "music_preview_manifest.json"
SELECTION = HERE / "public_music_selection.json"
DECISIONS = HERE / "spikes" / "essentia" / "human_review_decisions.json"

MANIFEST_SCHEMA = "music-preview-manifest-v1"
OUTPUT_DIR = "assets/audio/previews"
SOURCE_ROOT = ("One Page Luis Guinea", "audios")
SOURCE_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aif", ".aiff", ".flac"}
MAX_PREVIEW_S = 45.0
POLICY = {
    "id": "uniform-start30-v1",
    "start_s": 30.0,
    "duration_s": 44.5,
    "fade_in_s": 0.5,
    "fade_out_s": 2.0,
    "format": "mp3",
    "codec": "libmp3lame",
    "bitrate": "128k",
    "sample_rate": 44100,
    "channels": 2,
    "rationale": (
        "No existía criterio previo de recorte. Política uniforme y determinista, sin análisis "
        "musical: empieza en el segundo 30 de la fuente y codifica 44,5 s (ffprobe informa "
        "< 45,000 s), con fundidos cortos para evitar cortes bruscos. Sin metadatos embebidos y "
        "con flags bitexact: la misma fuente produce los mismos bytes."
    ),
}
ASSOCIATION_BASES = {"objective_evidence", "human_authorization"}
COMMON_KEYS = {"review_id", "work_id", "status", "source", "source_sha256", "preview", "trim_policy"}
ENTRY_KEYS = {
    "verified": COMMON_KEYS | {"association"},
    "blocked": COMMON_KEYS | {"blocked_reason", "candidates", "evidence_needed"},
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.mp3$")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _safe_relative(value, label):
    path = PurePosixPath(_text(value, label))
    if path.is_absolute() or "\\" in value or ".." in path.parts or "." in path.parts \
            or str(path) != value:
        raise ValueError(f"{label} must be a normalised relative path: {value!r}")
    return path


def validate_manifest(manifest, selection, decisions):
    """Return the manifest entries in selection order, or raise ValueError."""
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"manifest schema must be {MANIFEST_SCHEMA}")
    if manifest.get("output_dir") != OUTPUT_DIR:
        raise ValueError(f"manifest output_dir must be {OUTPUT_DIR}")
    if manifest.get("policy") != POLICY:
        raise ValueError("manifest policy differs from the documented uniform policy")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("manifest entries must be a list")

    mapped = {}
    for item in decisions.get("classifications", []):
        link = item.get("catalog_link") or {}
        if link.get("status") == "mapped":
            mapped[item.get("review_id")] = link.get("work_id")

    by_review, sources, previews = {}, set(), set()
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry {position} must be an object")
        review_id = _text(entry.get("review_id"), f"manifest entry {position} review_id")
        label = f"#{review_id}"
        if review_id in by_review:
            raise ValueError(f"manifest contains duplicate review_id {review_id}")
        status = entry.get("status")
        if status not in ENTRY_KEYS:
            raise ValueError(f"{label}: unsupported status {status!r}")
        if set(entry) != ENTRY_KEYS[status]:
            raise ValueError(f"{label}: {status} entry keys must be {sorted(ENTRY_KEYS[status])}")
        work_id = _text(entry.get("work_id"), f"{label} work_id")
        if mapped.get(review_id) != work_id:
            raise ValueError(f"{label}: work_id {work_id!r} does not match the human mapping")

        if status == "blocked":
            if any(entry[key] is not None for key in ("source", "source_sha256", "preview", "trim_policy")):
                raise ValueError(f"{label}: blocked entries must not declare a source or preview")
            _text(entry["blocked_reason"], f"{label} blocked_reason")
            _text(entry["evidence_needed"], f"{label} evidence_needed")
            if not isinstance(entry["candidates"], list):
                raise ValueError(f"{label}: candidates must be a list")
        else:
            source = _safe_relative(entry["source"], f"{label} source")
            if source.parts[:2] != SOURCE_ROOT or len(source.parts) < 3 \
                    or source.suffix.lower() not in SOURCE_EXTENSIONS:
                raise ValueError(f"{label}: source must be an audio file under {'/'.join(SOURCE_ROOT)}")
            if unicodedata.normalize("NFC", entry["source"]) != entry["source"]:
                raise ValueError(f"{label}: source must be NFC-normalised")
            if not isinstance(entry["source_sha256"], str) or not SHA256_RE.match(entry["source_sha256"]):
                raise ValueError(f"{label}: source_sha256 must be a lowercase sha256")
            preview = _safe_relative(entry["preview"], f"{label} preview")
            if str(preview) != f"{OUTPUT_DIR}/{work_id}.mp3" or not PREVIEW_NAME_RE.match(preview.name):
                raise ValueError(f"{label}: preview must be {OUTPUT_DIR}/{work_id}.mp3")
            if entry["trim_policy"] != POLICY["id"]:
                raise ValueError(f"{label}: trim_policy must be {POLICY['id']}")
            association = entry["association"]
            if not isinstance(association, dict) or association.get("basis") not in ASSOCIATION_BASES \
                    or not isinstance(association.get("evidence"), list) \
                    or not association["evidence"] \
                    or not all(isinstance(e, str) and e.strip() for e in association["evidence"]):
                raise ValueError(f"{label}: association needs an authorized basis and evidence")
            if association["basis"] == "human_authorization":
                _text(association.get("authority"), f"{label} association authority")
            if entry["source"] in sources or entry["preview"] in previews:
                raise ValueError(f"{label}: a source or preview is used more than once")
            sources.add(entry["source"])
            previews.add(entry["preview"])
        by_review[review_id] = entry

    order = [_text(item.get("review_id"), "selection review_id") for item in selection.get("entries", [])]
    if set(order) != set(by_review) or len(order) != len(by_review):
        raise ValueError("manifest must contain exactly one entry per public selection review_id")
    return [by_review[review_id] for review_id in order]


def resolve_source(relative, repo=REPO):
    """Resolve a manifest source path, tolerating NFC/NFD differences in file names."""
    path = Path(repo)
    for part in PurePosixPath(relative).parts:
        candidate = path / part
        if not candidate.exists() and path.is_dir():
            wanted = unicodedata.normalize("NFC", part)
            matches = [p for p in path.iterdir() if unicodedata.normalize("NFC", p.name) == wanted]
            if len(matches) == 1:
                candidate = matches[0]
        path = candidate
    if not path.is_file():
        raise ValueError(f"source not found: {relative}")
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tool(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f"{name} is required but was not found in PATH")
    return found


def probe(path):
    """Return the ffprobe facts the public contract depends on."""
    result = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-show_entries",
         "format=format_name,duration:format_tags:stream=codec_type,codec_name,sample_rate,channels",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe cannot read {path.name}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    fmt = data.get("format") or {}
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    return {
        "format_name": fmt.get("format_name"),
        "duration": float(fmt.get("duration") or 0.0),
        "tags": fmt.get("tags") or {},
        "streams": len(data.get("streams", [])),
        "codec_name": audio[0].get("codec_name") if audio else None,
        "sample_rate": int(audio[0].get("sample_rate") or 0) if audio else 0,
        "channels": audio[0].get("channels") if audio else 0,
    }


def ffmpeg_command(source, output):
    policy = POLICY
    fade_out_start = policy["duration_s"] - policy["fade_out_s"]
    return [
        _tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(policy["start_s"]), "-t", str(policy["duration_s"]), "-i", str(source),
        "-map", "0:a:0", "-map_metadata", "-1", "-map_chapters", "-1", "-vn", "-sn", "-dn",
        "-af", f"afade=t=in:st=0:d={policy['fade_in_s']},"
               f"afade=t=out:st={fade_out_start}:d={policy['fade_out_s']}",
        "-ac", str(policy["channels"]), "-ar", str(policy["sample_rate"]),
        "-c:a", policy["codec"], "-b:a", policy["bitrate"],
        "-id3v2_version", "0", "-write_id3v1", "0",
        "-fflags", "+bitexact", "-flags:a", "+bitexact", "-f", policy["format"], str(output),
    ]


def check_preview(path):
    """Raise unless path is a playable MP3 of at most MAX_PREVIEW_S seconds without metadata."""
    info = probe(path)
    if info["format_name"] != "mp3" or info["codec_name"] != "mp3" or info["streams"] != 1:
        raise ValueError(f"{path.name}: not a single-stream MP3 ({info['format_name']}/{info['codec_name']})")
    if not 0.0 < info["duration"] <= MAX_PREVIEW_S:
        raise ValueError(f"{path.name}: duration {info['duration']:.3f}s outside (0, {MAX_PREVIEW_S}]")
    if info["tags"]:
        raise ValueError(f"{path.name}: embedded metadata {sorted(info['tags'])}")
    return info


def encode(source, output):
    """Encode source into output atomically; return True when the bytes changed."""
    duration = probe(source)["duration"]
    if duration < POLICY["start_s"] + POLICY["duration_s"]:
        raise ValueError(
            f"{source.name}: source is shorter ({duration:.3f}s) than the uniform window "
            f"{POLICY['start_s']}+{POLICY['duration_s']}s"
        )
    tmp = output.with_name(f".{output.stem}.tmp.mp3")
    try:
        result = subprocess.run(ffmpeg_command(source, tmp), capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"ffmpeg failed for {source.name}: {result.stderr.strip()}")
        check_preview(tmp)
        if output.is_file() and output.read_bytes() == tmp.read_bytes():
            return False
        os.replace(tmp, output)
        return True
    finally:
        if tmp.exists():
            tmp.unlink()


def generate(manifest, selection, decisions, *, repo=REPO):
    """Generate every verified preview; return their paths in selection order."""
    entries = validate_manifest(manifest, selection, decisions)
    verified = [entry for entry in entries if entry["status"] == "verified"]
    output_dir = Path(repo) / OUTPUT_DIR
    expected = {PurePosixPath(entry["preview"]).name for entry in verified}
    if output_dir.is_dir():
        unexpected = sorted(p.name for p in output_dir.iterdir() if p.name not in expected)
        if unexpected:
            raise ValueError(f"unexpected files in {OUTPUT_DIR}: {unexpected}")

    jobs = []
    for entry in verified:
        source = resolve_source(entry["source"], repo)
        if sha256_file(source) != entry["source_sha256"]:
            raise ValueError(f"#{entry['review_id']}: source sha256 differs from the manifest")
        jobs.append((source, Path(repo) / entry["preview"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    for source, output in jobs:
        encode(source, output)
    return [output for _, output in jobs]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    try:
        manifest = _load(MANIFEST)
        outputs = generate(manifest, _load(SELECTION), _load(DECISIONS), repo=REPO)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MUSIC PREVIEWS FAILED: {exc}", file=sys.stderr)
        return 1
    blocked = len(manifest["entries"]) - len(outputs)
    print(f"MUSIC PREVIEWS OK: {len(outputs)} generated ({blocked} works without an authorized source) "
          f"-> {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
