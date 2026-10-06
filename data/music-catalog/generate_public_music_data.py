#!/usr/bin/env python3
"""Generate the browser-safe data consumed by /music/.

Only eight explicitly allowed display fields are emitted. Every published song has a valid
`preview`: the file name of a verified derivative (music_preview_manifest.json) that exists in
assets/audio/previews/, is a readable MP3 and lasts 45 s or less (measured with the standard
library). Songs of the selection without such a preview are left out of the public output and
recorded in public_catalog_exclusions.json. The private source, its hash and the evidence never
leave the manifest. The canonical catalogue is
never copied wholesale to the web bundle because it also contains internal-use file
references and metadata that the current UI does not need.
"""

import argparse
import json
import struct
from pathlib import Path, PurePosixPath

import audio_stdlib
import generate_music_previews as previews


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MASTER = HERE / "catalog_master.json"
SELECTION = HERE / "public_music_selection.json"
OUTPUT = REPO / "js" / "music-data.js"
EVIDENCE_DIR = HERE / "spikes" / "essentia"
DECISIONS = EVIDENCE_DIR / "human_review_decisions.json"
PREVIEW_MANIFEST = previews.MANIFEST
EXCLUSIONS_LOG = HERE / "public_catalog_exclusions.json"
EXCLUSIONS_SCHEMA = "public-catalog-exclusions-v1"
PUBLICATION_RULE = (
    "Toda canción publicada necesita un preview válido: entrada verified en "
    "music_preview_manifest.json, fichero existente en assets/audio/previews/, MP3 legible y "
    "duración <= 45 s. Las canciones de la selección sin preview reproducible se excluyen de "
    "js/music-data.js y se registran aquí."
)

SELECTION_SCHEMA = "public-music-selection-v2"
ALLOWED_ROLES = {"Artist", "Producer", "Composer"}
EVIDENCE_FOLDER_ROLES = {"Cantautor": "Artist", "Productor": "Producer"}
RELEASE_TYPES = {"single": "Single", "album": "Album"}
CREDIT_ROLES = {
    "artist": "Artist",
    "songwriter": "Songwriter",
    "producer": "Producer",
    "recording_engineer": "Recording Engineer",
}
LUIS = "Luis Guinea"
# `role` is the primary Artist/Producer/Composer facet (filter); `roles` lists
# every public credit of Luis Guinea in that work.
# `preview` is a validated preview file name in assets/audio/previews/ (never None).
PUBLIC_FIELDS = ("title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview")


def _required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _role_from_evidence(decision, preview_entry):
    """Primary role from the versioned evidence of the linked audio (CATALOG_CATEGORY.md).

    catalog_category is by definition the first-level folder under audios/ of the audio linked
    to the work. It is read from the human decision's catalog_link.evidence and from the
    authorized source of a verified preview (music_preview_manifest.json), never from the
    unversioned spike bank (human_classification_bank.json), which only derives it.
    """
    evidence_roles = set()
    for evidence in (decision.get("catalog_link") or {}).get("evidence") or []:
        source = evidence.get("source", "")
        parts = PurePosixPath(source).parts
        for folder, role in EVIDENCE_FOLDER_ROLES.items():
            if "audios" in parts and folder in parts:
                evidence_roles.add(role)
    if preview_entry.get("status") == "verified":
        # validate_manifest() guarantees One Page Luis Guinea/audios/<folder>/...
        folder = PurePosixPath(preview_entry["source"]).parts[2]
        role = EVIDENCE_FOLDER_ROLES.get(folder)
        if role is None:
            raise ValueError(
                f"#{decision['review_id']}: audio folder {folder!r} has no public role"
            )
        evidence_roles.add(role)
    if len(evidence_roles) != 1:
        raise ValueError(
            f"#{decision['review_id']}: role is missing or ambiguous in verified evidence"
        )
    return evidence_roles.pop()


def _credit_roles(decision, work):
    """Public roles from an explicit human credits decision, or None if there is none."""
    credits = decision.get("credits")
    if credits is None:
        return None
    label = f"#{decision['review_id']}"
    if not isinstance(credits, list):
        raise ValueError(f"{label}: credits must be a list")
    people = {}
    for credit in credits:
        name = _required_text(credit.get("name") if isinstance(credit, dict) else None,
                              f"{label} credit name")
        roles = credit.get("roles")
        if not isinstance(roles, list) or not roles or name in people:
            raise ValueError(f"{label}: credit for {name!r} is empty or duplicated")
        people[name] = roles
        if "vocal_performer" in roles and name not in work.get("artists", []):
            raise ValueError(f"{label}: credit performer {name!r} is not an artist of the work")
    luis = people.get(LUIS, [])
    unknown = [role for role in luis if role not in CREDIT_ROLES]
    if unknown:
        raise ValueError(f"{label}: unsupported credit roles {unknown}")
    public = [CREDIT_ROLES[role] for role in luis]
    explicit_facet = (decision.get("credits_decision") or {}).get("public_facet")
    if not any(role in {"Artist", "Producer"} for role in public) and not (
        explicit_facet == "Composer" and "Songwriter" in public
    ):
        raise ValueError(f"{label}: no supported public role in credits")
    return public


def _public_facet(decision, roles):
    facet = (decision.get("credits_decision") or {}).get("public_facet")
    if facet is None:
        return None
    label = f"#{decision['review_id']}"
    if facet not in ALLOWED_ROLES:
        raise ValueError(f"{label}: unsupported explicit public facet {facet!r}")
    required_role = {"Artist": "Artist", "Producer": "Producer", "Composer": "Songwriter"}[facet]
    if required_role not in roles:
        if facet == "Composer":
            raise ValueError(f"{label}: Composer facet requires songwriter credit for Luis Guinea")
        raise ValueError(f"{label}: {facet} facet requires {required_role.lower()} credit for Luis Guinea")
    return facet


def _primary_role(decision, roles, work_id):
    role = _public_facet(decision, roles)
    if role is None:
        role = next((item for item in roles if item in ALLOWED_ROLES), roles[0])
    if role not in ALLOWED_ROLES:
        raise ValueError(f"{work_id}: unsupported public role {role!r}")
    return role


def preview_problem(preview, *, repo=REPO):
    """None when `preview` is a playable public MP3 of at most 45 s, else (reason, detail)."""
    path = PurePosixPath(preview)
    if "/".join(path.parts[:-1]) != previews.OUTPUT_DIR or not previews.PREVIEW_NAME_RE.match(path.name):
        return "preview_outside_public_dir", f"{preview} is not a file name directly under {previews.OUTPUT_DIR}"
    file = Path(repo) / Path(*path.parts)
    if not file.is_file():
        return "preview_missing", f"{preview} does not exist; run generate_music_previews.py"
    try:
        duration, _ = audio_stdlib.mp3_duration(file, strict=True)
    except (ValueError, IndexError, struct.error) as exc:
        return "preview_unplayable", f"{preview} is not a readable MP3: {exc}"
    if not 0 < duration <= previews.MAX_PREVIEW_S:
        return "preview_too_long", f"{preview} lasts {duration:.3f} s (maximum {previews.MAX_PREVIEW_S:.0f} s)"
    return None


def project(master, selection, decisions, *, repo=REPO, manifest=None):
    """Return the public rows: songs with a valid preview, in curated display order."""
    return project_with_exclusions(master, selection, decisions, repo=repo, manifest=manifest)[0]


def project_with_exclusions(master, selection, decisions, *, repo=REPO, manifest=None):
    """Return (published rows, exclusions); every published row has a valid preview."""
    rows, exclusions = [], []
    for review_id, work_id, row, entry in _candidates(master, selection, decisions, repo=repo,
                                                      manifest=manifest):
        if entry["status"] != "verified":
            exclusions.append({"review_id": review_id, "work_id": work_id, "title": row["title"],
                               "reason": "no_authorized_preview", "detail": entry["blocked_reason"]})
            continue
        problem = preview_problem(entry["preview"], repo=repo)
        if problem:
            exclusions.append({"review_id": review_id, "work_id": work_id, "title": row["title"],
                               "reason": problem[0], "detail": problem[1]})
            continue
        row["preview"] = PurePosixPath(entry["preview"]).name
        rows.append(row)
    return rows, exclusions


def project_all(master, selection, decisions, *, repo=REPO, manifest=None):
    """Every selected work with validated credits and role, before the preview requirement.

    Internal: `preview` is None here. Used to check credit decisions of works that are
    currently excluded for lack of a preview; never serialized.
    """
    return [row for _, _, row, _ in _candidates(master, selection, decisions, repo=repo,
                                                manifest=manifest)]


def _candidates(master, selection, decisions, *, repo=REPO, manifest=None):
    """Validate the whole selection; yield (review_id, work_id, row, manifest entry).

    `manifest` defaults to the canonical music_preview_manifest.json.
    """
    if not isinstance(master, list):
        raise ValueError("catalog_master.json must contain a list")
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError(f"selection schema must be {SELECTION_SCHEMA}")
    entries = selection.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("selection entries must be a non-empty list")

    by_id = {}
    for work in master:
        work_id = work.get("id") if isinstance(work, dict) else None
        if not work_id or work_id in by_id:
            raise ValueError(f"catalogue contains an empty or duplicate id: {work_id!r}")
        by_id[work_id] = work

    classifications = decisions.get("classifications")
    if not isinstance(classifications, list):
        raise ValueError("human mapping artifacts have an invalid schema")
    decisions_by_review = {item.get("review_id"): item for item in classifications}
    if len(decisions_by_review) != len(classifications):
        raise ValueError("human mapping artifacts contain duplicate review_id values")

    seen = set()
    pending = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {"review_id"}:
            raise ValueError(f"selection entry {position} must contain only review_id")
        review_id = _required_text(entry["review_id"], f"selection entry {position} review_id")
        if review_id in seen:
            raise ValueError(f"selection contains duplicate review_id: {review_id}")
        seen.add(review_id)
        decision = decisions_by_review.get(review_id)
        if decision is None:
            raise ValueError(f"selection references unknown review case: #{review_id}")
        if decision.get("public_exclusion") is True:
            raise ValueError(f"selection case #{review_id} is excluded from public selection")
        link = decision.get("catalog_link") or {}
        if link.get("status") != "mapped" or not link.get("work_id"):
            raise ValueError(f"selection case #{review_id} is not mapped")
        work_id = link["work_id"]
        if work_id not in by_id:
            raise ValueError(f"selection references unknown work: {work_id}")

        work = by_id[work_id]
        roles = _credit_roles(decision, work)
        # Without a credits decision the role comes from the audio evidence, resolved below.
        role = None if roles is None else _primary_role(decision, roles, work_id)
        release = work.get("release") or {}
        if release.get("status") != "released":
            raise ValueError(f"{work_id} is not a released work")
        release_type = RELEASE_TYPES.get(release.get("type"))
        if release_type is None:
            raise ValueError(f"{work_id}: unsupported release type {release.get('type')!r}")
        year = release.get("year")
        if not isinstance(year, int):
            raise ValueError(f"{work_id}: release year must be an integer")

        artists = work.get("artists")
        if not isinstance(artists, list) or not artists or not all(
            isinstance(artist, str) and artist.strip() for artist in artists
        ):
            raise ValueError(f"{work_id}: artists must be a non-empty string list")

        web_file = (work.get("artwork") or {}).get("web_file")
        web_file = _required_text(web_file, f"{work_id} artwork.web_file")
        web_path = PurePosixPath(web_file)
        if web_path.is_absolute() or ".." in web_path.parts or web_path.parts[:2] != (
            "assets",
            "images",
        ):
            raise ValueError(f"{work_id}: artwork.web_file is outside assets/images")
        if not (repo / Path(*web_path.parts)).is_file():
            raise ValueError(f"{work_id}: artwork.web_file does not exist: {web_file}")

        row = {
            "title": _required_text(work.get("title"), f"{work_id} title"),
            "artist": ", ".join(artists),
            "role": role,
            "artwork": web_path.name,
            "releaseType": release_type,
            "year": year,
            "roles": roles,
            "preview": None,
        }
        if tuple(row) != PUBLIC_FIELDS:
            raise AssertionError("public field order changed")
        pending.append((review_id, work_id, decision, row))

    # Previews last, so selection and credit errors keep precedence.
    if manifest is None:
        manifest = json.loads(PREVIEW_MANIFEST.read_text(encoding="utf-8"))
    preview_entries = {
        entry["review_id"]: entry
        for entry in previews.validate_manifest(manifest, selection, decisions)
    }
    for review_id, work_id, decision, row in pending:
        entry = preview_entries[review_id]
        if entry["work_id"] != work_id:
            raise ValueError(f"#{review_id}: preview manifest work_id differs from the mapping")
        if row["roles"] is None:
            row["roles"] = [_role_from_evidence(decision, entry)]
            row["role"] = _primary_role(decision, row["roles"], work_id)
    return [(review_id, work_id, row, preview_entries[review_id])
            for review_id, work_id, _, row in pending]


def serialize(rows):
    def quote(value):
        escaped = (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
        return f"'{escaped}'"

    lines = []
    for row in rows:
        if tuple(row) != PUBLIC_FIELDS:
            raise ValueError("rows must match the eight-field public schema")
        if not all(isinstance(row[key], str) for key in PUBLIC_FIELDS[:5]) or not (
            isinstance(row["year"], int)
            and not isinstance(row["year"], bool)
            and 1000 <= row["year"] <= 9999
        ) or not (
            isinstance(row["roles"], list) and row["roles"]
            and all(isinstance(role, str) for role in row["roles"])
        ) or not (
            isinstance(row["preview"], str) and previews.PREVIEW_NAME_RE.match(row["preview"])
        ):
            raise ValueError("rows must match the eight-field public schema (preview is required)")
        values = [quote(row[key]) for key in PUBLIC_FIELDS[:5]]
        values.append(str(row["year"]))
        values.append("[" + ", ".join(quote(role) for role in row["roles"]) + "]")
        values.append(quote(row["preview"]))
        fields = ", ".join(f"{key}:{value}" for key, value in zip(PUBLIC_FIELDS, values))
        lines.append(f"  {{ {fields} }}")
    payload = "[\n" + ",\n".join(lines) + "\n]"
    return (
        "// Generated by data/music-catalog/generate_public_music_data.py. Do not edit.\n"
        f"window.MUSIC_DATA = {payload};\n"
    )


def exclusions_log(rows, exclusions, selection):
    """Deterministic record of what was published and what was left out (no timestamps)."""
    published_ids = [entry["review_id"] for entry in selection["entries"]
                     if entry["review_id"] not in {item["review_id"] for item in exclusions}]
    if len(published_ids) != len(rows):
        raise AssertionError("published rows and selection disagree")
    return {
        "schema": EXCLUSIONS_SCHEMA,
        "generated_by": "data/music-catalog/generate_public_music_data.py",
        "rule": PUBLICATION_RULE,
        "published": published_ids,
        "published_previews": [{"review_id": review_id, "preview": row["preview"]}
                               for review_id, row in zip(published_ids, rows)],
        "excluded": exclusions,
    }


def generate(
    *, master_path=MASTER, selection_path=SELECTION, decisions_path=DECISIONS,
    manifest_path=PREVIEW_MANIFEST, output=OUTPUT, log_path=EXCLUSIONS_LOG
):
    """Write js/music-data.js and the exclusion log; return (rows, exclusions)."""
    master = json.loads(Path(master_path).read_text(encoding="utf-8"))
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    decisions = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows, exclusions = project_with_exclusions(master, selection, decisions, repo=REPO,
                                               manifest=manifest)
    if not rows:
        raise ValueError("no song of the selection has a valid preview: refusing an empty catalogue")
    javascript = serialize(rows)
    log = json.dumps(exclusions_log(rows, exclusions, selection), ensure_ascii=False, indent=2) + "\n"
    Path(output).write_text(javascript, encoding="utf-8")
    Path(log_path).write_text(log, encoding="utf-8")
    return rows, exclusions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--log", type=Path, default=EXCLUSIONS_LOG)
    args = parser.parse_args()
    rows, exclusions = generate(output=args.output, log_path=args.log)
    for item in exclusions:
        print(f"EXCLUDED #{item['review_id']} {item['work_id']}: {item['reason']}")
    print(f"PUBLIC MUSIC DATA OK: {len(rows)} published with preview, {len(exclusions)} excluded "
          f"without a reproducible preview -> {args.output} (log: {args.log.name})")


if __name__ == "__main__":
    main()
