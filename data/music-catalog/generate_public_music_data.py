#!/usr/bin/env python3
"""Generate the browser-safe data consumed by /music/.

Only sixteen explicitly allowed display fields are emitted. Every published song has a valid
`preview`: the file name of a verified derivative (music_preview_manifest.json) that exists in
assets/audio/previews/, is a readable MP3 and lasts 45 s or less (measured with the standard
library). Songs of the selection without such a preview are left out of the public output and
recorded in public_catalog_exclusions.json. A selection entry marked `"hidden": true` is withheld the
same way (reason `hidden_by_owner`) while keeping its place, mapping, preview and metadata, so it can
be shown again by removing the flag. The private source, its hash and the evidence never
leave the manifest. `spotify` and `appleMusic` are optional streaming destinations (a validated
URL or null): Spotify comes from the catalogue entry; Apple Music comes from the catalogue entry or,
when it has none, from the owner-certified public_platform_links.json. `youtube` and `soundcloud`
are optional links to the full recording (owner-supplied and verified, public_platform_links.json
`full_recordings`). No URL is ever deduced. `artists` lists the credited recording artists of the
catalogue entry, for the artist filter. `genres` and `moods` come only from the owner's human review
(evidence `human_review` in human_review_decisions.json), validated against vocabularies.json; a
work without a reviewed value publishes an empty list, never an inferred one.
Recordings that are not in the «Released» sheet (unreleased songs and instrumentals, and releases
newer than that sheet, with links verified against the platforms) come from the hand-curated
catalog_recordings.json, never from catalog_master.json, which is generated and hash-pinned; a
recording with provisional fields cannot be published. A release may lack a Spotify URL only when its
basis says so (SPOTIFY_UNVERIFIED): absence means unverified, never «not on Spotify». The internal
`sync_availability` of a recording (SYNC_AVAILABILITY) is the owner's decision on sync enquiries,
independent of editorial.use_scene and never published. The canonical catalogue is
never copied wholesale to the web bundle because it also contains internal-use file
references and metadata that the current UI does not need.
"""

import argparse
import json
import re
import struct
from pathlib import Path, PurePosixPath

import audio_stdlib
import generate_music_previews as previews


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MASTER = HERE / "catalog_master.json"
RECORDINGS = HERE / "catalog_recordings.json"
RECORDINGS_SCHEMA = "catalog-recordings-v1"
SELECTION = HERE / "public_music_selection.json"
OUTPUT = REPO / "js" / "music-data.js"
EVIDENCE_DIR = HERE / "spikes" / "essentia"
DECISIONS = EVIDENCE_DIR / "human_review_decisions.json"
PREVIEW_MANIFEST = previews.MANIFEST
EXCLUSIONS_LOG = HERE / "public_catalog_exclusions.json"
PLATFORM_LINKS = HERE / "public_platform_links.json"
PLATFORM_LINKS_SCHEMA = "public-platform-links-v1"
ARTWORK_CORRECTIONS = HERE / "public_artwork_corrections.json"
ARTWORK_CORRECTIONS_SCHEMA = "public-artwork-corrections-v1"
VOCABULARIES = HERE / "vocabularies.json"
EXCLUSIONS_SCHEMA = "public-catalog-exclusions-v1"
PUBLICATION_RULE = (
    "Toda canción publicada necesita un preview válido: entrada verified en "
    "music_preview_manifest.json, fichero existente en assets/audio/previews/, MP3 legible y "
    "duración <= 45 s. Las canciones de la selección sin preview reproducible se excluyen de "
    "js/music-data.js y se registran aquí. Las entradas de public_music_selection.json marcadas "
    "\"hidden\": true se ocultan por decisión del propietario (hidden_by_owner) y conservan su "
    "posición, su preview y sus metadatos."
)
HIDDEN_DETAIL = (
    "Oculta del catálogo público por decisión del propietario (\"hidden\": true en "
    "public_music_selection.json). Audio, preview y metadatos se conservan; quitar la marca la "
    "vuelve a publicar en su posición."
)

SELECTION_SCHEMA = "public-music-selection-v2"
ALLOWED_ROLES = {"Artist", "Producer", "Composer"}
# CATALOG_CATEGORY.md: the first-level folder under audios/ is the user's declared facet.
# Instrumentales declares a category, not a credit, so its works need an explicit credits decision.
EVIDENCE_FOLDER_ROLES = {"Cantautor": "Artist", "Productor": "Producer", "Coautorías": "Co-writer"}
RELEASE_TYPES = {"single": "Single", "album": "Album", "ep": "EP"}
# Recordings without a commercial release (no distributor, ISRC or streaming link), by
# release.status: `unreleased` was never made public; `self_published` is published in full by the
# artist on YouTube or SoundCloud (a `full_recordings` link is required). Neither carries a date.
NON_COMMERCIAL_TYPES = {"unreleased": "Unreleased", "self_published": "SelfPublished"}
# Closed vocabulary of the public `version` label (translated by js/strings.js music.version*).
# Owner's decision on sync enquiries for a recording, or None when there is none. Neither value is a
# one-stop or rights-cleared claim; "not_offered" (portfolio only) admits no use_scene.
SYNC_AVAILABILITY = {"on_request", "not_offered"}
SPOTIFY_UNVERIFIED = "Spotify sin verificar"
VERSIONS = {"Instrumental", "PianoVocal", "RoughMix", "RegionalMexican", "Mashup"}
CREDIT_ROLES = {
    "artist": "Artist",
    "songwriter": "Songwriter",
    "co_writer": "Co-writer",
    "arranger": "Arranger",
    "co_arranger": "Co-arranger",
    "producer": "Producer",
    "co_producer": "Co-producer",
    "performer": "Performer",
    "recording_engineer": "Recording Engineer",
}
# Songwriting credits surface under the Composer facet, production credits under Producer.
COMPOSER_CREDITS = {"Songwriter", "Co-writer"}
PRODUCER_CREDITS = {"Producer", "Co-producer"}
LUIS = "Luis Guinea"
# `role` is the primary Artist/Producer/Composer facet (filter); `roles` lists
# every public credit of Luis Guinea in that work.
# `preview` is a validated preview file name in assets/audio/previews/ (never None).
# `spotify` and `appleMusic` are a validated streaming URL or None when the platform is uncertified;
# `youtube` and `soundcloud` link the full recording, or are None.
# `releaseType` is Single/Album/EP for released works, SelfPublished or Unreleased otherwise; `year` is None
# only for an unreleased recording whose year no source states. `version` is None or one of VERSIONS.
# `artists` is the credited artist list behind `artist`; `genres` and `moods` are vocabulary ids from the
# human review, possibly empty.
PUBLIC_FIELDS = ("title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview",
                 "spotify", "appleMusic", "version", "youtube", "soundcloud", "artists", "genres", "moods")
SCHEMA_ERROR = "rows must match the sixteen-field public schema"
SPOTIFY_URL_RE = re.compile(r"^https://open\.spotify\.com/track/[A-Za-z0-9]{22}$")
APPLE_MUSIC_URL_RE = re.compile(r"^https://music\.apple\.com/[a-z]{2}/(?:album|song)/[A-Za-z0-9%._~/?=&-]+$")
FULL_RECORDING_URL_RES = {
    "youtube": re.compile(r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}$"),
    "soundcloud": re.compile(r"^https://soundcloud\.com/[a-z0-9_-]+/[a-z0-9_-]+$"),
}


def _platform_url(value, pattern, label):
    """A validated public streaming URL, or None when the platform has none."""
    if value is None:
        return None
    if not isinstance(value, str) or not pattern.match(value):
        raise ValueError(f"{label} is not a valid public URL: {value!r}")
    return value


def certified_apple_music(links):
    """work_id -> URL from public_platform_links.json (owner-certified additions only)."""
    if links.get("schema") != PLATFORM_LINKS_SCHEMA:
        raise ValueError(f"platform links schema must be {PLATFORM_LINKS_SCHEMA}")
    out = {}
    for position, item in enumerate(links.get("apple_music") or [], start=1):
        if not isinstance(item, dict) or set(item) != {"work_id", "url"}:
            raise ValueError(f"platform link {position} must contain only work_id and url")
        work_id = _required_text(item["work_id"], f"platform link {position} work_id")
        if work_id in out:
            raise ValueError(f"platform links repeat {work_id}")
        out[work_id] = _platform_url(item["url"], APPLE_MUSIC_URL_RE, f"{work_id} certified Apple Music")
    return out


def apple_music_corrections(links):
    """work_id -> (wrong registered URL, verified URL) from `apple_music_corrections`.

    catalog_master.json is generated and hash-pinned, so a registered Apple Music URL that points
    to another artist's recording is replaced here, never edited there. Each correction names the
    exact wrong URL, so it stops applying if the catalogue changes.
    """
    out = {}
    for position, item in enumerate(links.get("apple_music_corrections") or [], start=1):
        if not isinstance(item, dict) or set(item) != {"work_id", "wrong_url", "url", "evidence"}:
            raise ValueError(f"Apple Music correction {position} must contain only work_id, "
                             "wrong_url, url and evidence")
        work_id = _required_text(item["work_id"], f"Apple Music correction {position} work_id")
        _required_text(item["evidence"], f"{work_id} Apple Music correction evidence")
        if work_id in out:
            raise ValueError(f"Apple Music corrections repeat {work_id}")
        out[work_id] = (item["wrong_url"],
                        _platform_url(item["url"], APPLE_MUSIC_URL_RE, f"{work_id} corrected Apple Music"))
    return out


def certified_full_recordings(links):
    """work_id -> {platform: URL} from the `full_recordings` of public_platform_links.json."""
    out = {}
    for position, item in enumerate(links.get("full_recordings") or [], start=1):
        if not isinstance(item, dict) or set(item) != {"work_id", "platform", "url"}:
            raise ValueError(f"full recording {position} must contain only work_id, platform and url")
        work_id = _required_text(item["work_id"], f"full recording {position} work_id")
        platform = item["platform"]
        if platform not in FULL_RECORDING_URL_RES:
            raise ValueError(f"full recording {position}: unsupported platform {platform!r}")
        if platform in out.setdefault(work_id, {}):
            raise ValueError(f"full recordings repeat {platform} for {work_id}")
        out[work_id][platform] = _platform_url(item["url"], FULL_RECORDING_URL_RES[platform],
                                               f"{work_id} {platform}")
    return out


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
    if preview_entry.get("source"):
        # A verified entry, or a blocked one whose source is already associated (awaiting its
        # window): validate_manifest() guarantees One Page Luis Guinea/audios/<folder>/...
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
    if not ({"Artist"} | PRODUCER_CREDITS) & set(public) and not (
        explicit_facet == "Composer" and COMPOSER_CREDITS & set(public)
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
    if facet == "Composer":
        if not COMPOSER_CREDITS & set(roles):
            raise ValueError(f"{label}: Composer facet requires songwriter credit for Luis Guinea")
    elif facet == "Producer":
        if not PRODUCER_CREDITS & set(roles):
            raise ValueError(f"{label}: Producer facet requires producer credit for Luis Guinea")
    elif facet not in roles:
        raise ValueError(f"{label}: {facet} facet requires {facet.lower()} credit for Luis Guinea")
    return facet


def _primary_role(decision, roles, work_id):
    role = _public_facet(decision, roles)
    if role is None:
        role = next(("Producer" if item in PRODUCER_CREDITS else item for item in roles
                     if item in ALLOWED_ROLES or item in PRODUCER_CREDITS), None)
    if role is None:
        role = "Composer" if COMPOSER_CREDITS & set(roles) else roles[0]
    if role not in ALLOWED_ROLES:
        raise ValueError(f"{work_id}: unsupported public role {role!r}")
    return role


def vocabulary_terms(field, vocabularies=None):
    """The approved ids of a vocabularies.json field (genre or mood), in vocabulary order."""
    if vocabularies is None:
        vocabularies = json.loads(VOCABULARIES.read_text(encoding="utf-8"))
    return [term["id"] for term in vocabularies["fields"][field]["terms"]]


def vocabulary_rules(field, vocabularies=None):
    """(ids, (minimum, maximum), explicit empty allowed) of a vocabularies.json field."""
    if vocabularies is None:
        vocabularies = json.loads(VOCABULARIES.read_text(encoding="utf-8"))
    spec = vocabularies["fields"][field]
    low, high = spec["cardinality"]
    return [term["id"] for term in spec["terms"]], (low, high), bool((spec.get("explicit_empty") or {}).get("allowed"))


def _reviewed_terms(decision, field, rules, work_id):
    """Human-reviewed vocabulary ids of one field, or [] when the review has none. Never inferred.

    An absent field is unclassified. A present list must respect the vocabulary cardinality; an
    empty list is valid only where the vocabulary allows an explicit empty value and the review
    records that choice in negative_decisions (e.g. a work published without mood on purpose).
    """
    terms, (low, high), explicit_empty = rules
    values = decision.get("values") or {}
    if values.get("evidence") != "human_review" or field not in values:
        return []
    found = values[field]
    if not isinstance(found, list) or not all(isinstance(term, str) for term in found):
        raise ValueError(f"{work_id}: human-reviewed {field} must be a list of ids")
    unknown = [term for term in found if term not in terms]
    if unknown:
        raise ValueError(f"{work_id}: {field} outside vocabularies.json: {unknown}")
    if len(set(found)) != len(found):
        raise ValueError(f"{work_id}: duplicate {field} values")
    if not found:
        recorded = any(field in str(note).lower() for note in decision.get("negative_decisions") or [])
        if not (explicit_empty and recorded):
            raise ValueError(f"{work_id}: an empty {field} needs an explicit editorial decision "
                             "allowed by vocabularies.json")
    elif not low <= len(found) <= high:
        raise ValueError(f"{work_id}: {len(found)} {field} values (vocabularies.json allows {low}-{high})")
    return list(found)


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


def project(master, selection, decisions, *, repo=REPO, manifest=None, links=None, recordings=None):
    """Return the public rows: songs with a valid preview, in curated display order."""
    return project_with_exclusions(master, selection, decisions, repo=repo, manifest=manifest,
                                   links=links, recordings=recordings)[0]


def project_with_exclusions(master, selection, decisions, *, repo=REPO, manifest=None, links=None,
                            recordings=None):
    """Return (published rows, exclusions); every published row has a valid preview."""
    rows, exclusions = [], []
    hidden = hidden_review_ids(selection)
    for review_id, work_id, row, entry in _candidates(master, selection, decisions, repo=repo,
                                                      manifest=manifest, links=links,
                                                      recordings=recordings):
        if review_id in hidden:
            exclusions.append({"review_id": review_id, "work_id": work_id, "title": row["title"],
                               "reason": "hidden_by_owner", "detail": HIDDEN_DETAIL})
            continue
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


def hidden_review_ids(selection):
    """review_ids of the selection entries the owner marked `"hidden": true`."""
    return {entry["review_id"] for entry in selection.get("entries") or []
            if isinstance(entry, dict) and entry.get("hidden") is True}


def project_all(master, selection, decisions, *, repo=REPO, manifest=None, links=None,
                recordings=None, artwork_corrections=None):
    """Every selected work with validated credits and role, before the preview requirement.

    Internal: `preview` is None here. Used to check credit decisions of works that are
    currently excluded for lack of a preview; never serialized.
    """
    return [row for _, _, row, _ in _candidates(master, selection, decisions, repo=repo,
                                                manifest=manifest, links=links,
                                                recordings=recordings,
                                                artwork_corrections=artwork_corrections)]


RECORDING_KEYS = {"id", "title", "artists", "credits", "release", "duration_ms", "explicit",
                  "is_collaboration", "isrc", "spotify", "apple_music", "artwork", "audio_ref",
                  "editorial", "version", "basis", "provisional", "sync_availability"}


def recording_works(recordings):
    """Validated works of catalog_recordings.json (recordings outside the «Released» sheet)."""
    if not isinstance(recordings, dict) or recordings.get("schema") != RECORDINGS_SCHEMA:
        raise ValueError(f"recordings schema must be {RECORDINGS_SCHEMA}")
    works = recordings.get("recordings")
    if not isinstance(works, list):
        raise ValueError("recordings must be a list")
    for position, work in enumerate(works, start=1):
        if not isinstance(work, dict) or set(work) != RECORDING_KEYS:
            raise ValueError(f"recording {position} keys must be {sorted(RECORDING_KEYS)}")
        label = _required_text(work["id"], f"recording {position} id")
        status = (work.get("release") or {}).get("status")
        spotify = work["spotify"]
        if status == "released":
            # Released after the «Released» sheet was compiled: needs a verified streaming link.
            if not (work["spotify"].get("url") or work["apple_music"].get("url")):
                raise ValueError(f"{label}: a released recording needs a verified streaming link")
        elif status not in NON_COMMERCIAL_TYPES:
            raise ValueError(f"{label}: unsupported release status {status!r}")
        elif work["spotify"].get("url") or work["apple_music"].get("url") or work["isrc"]:
            raise ValueError(f"{label}: an unreleased recording cannot carry release identifiers")
        if spotify.get("url") != (spotify.get("track_id") and "https://open.spotify.com/track/" + spotify["track_id"]):
            raise ValueError(f"{label}: the Spotify URL must be the one of its track_id")
        if work["sync_availability"] is not None and work["sync_availability"] not in SYNC_AVAILABILITY:
            raise ValueError(f"{label}: unsupported sync_availability {work['sync_availability']!r}")
        if work["sync_availability"] == "not_offered" and work["editorial"].get("use_scene"):
            raise ValueError(f"{label}: a recording not offered for sync cannot list use_scene")
        if work["version"] is not None and work["version"] not in VERSIONS:
            raise ValueError(f"{label}: unsupported version {work['version']!r}")
        if not isinstance(work["provisional"], list) or not all(isinstance(f, str) for f in work["provisional"]):
            raise ValueError(f"{label}: provisional must list field names")
        if not isinstance(work["basis"], list) or not work["basis"] \
                or not all(isinstance(b, str) and b.strip() for b in work["basis"]):
            raise ValueError(f"{label}: basis must cite the evidence of every public field")
        if status == "released" and not spotify.get("url") \
                and not any(SPOTIFY_UNVERIFIED in b for b in work["basis"]):
            raise ValueError(f"{label}: a release without Spotify must record {SPOTIFY_UNVERIFIED!r} in its basis")
    return works


def corrected_artwork(corrections):
    """work_id -> (wrong web_file, corrected web_file) from public_artwork_corrections.json.

    Two releases of a song may share one image in the hash-pinned catalog_master.json; a correction
    gives one of them its own official cover and applies only while the catalogue still holds the
    exact wrong file.
    """
    if corrections.get("schema") != ARTWORK_CORRECTIONS_SCHEMA:
        raise ValueError(f"artwork corrections schema must be {ARTWORK_CORRECTIONS_SCHEMA}")
    out = {}
    for position, item in enumerate(corrections.get("corrections") or [], start=1):
        keys = {"work_id", "wrong_web_file", "web_file", "file", "evidence"}
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError(f"artwork correction {position} must contain only {sorted(keys)}")
        work_id = _required_text(item["work_id"], f"artwork correction {position} work_id")
        _required_text(item["evidence"], f"{work_id} artwork correction evidence")
        if work_id in out:
            raise ValueError(f"artwork corrections repeat {work_id}")
        out[work_id] = (item["wrong_web_file"], _required_text(item["web_file"], f"{work_id} web_file"))
    return out


def _candidates(master, selection, decisions, *, repo=REPO, manifest=None, links=None, recordings=None,
                artwork_corrections=None):
    """Validate the whole selection; yield (review_id, work_id, row, manifest entry).

    `manifest` defaults to the canonical music_preview_manifest.json, `links` to
    public_platform_links.json and `recordings` to catalog_recordings.json.
    """
    if links is None:
        links = json.loads(PLATFORM_LINKS.read_text(encoding="utf-8"))
    certified_apple = certified_apple_music(links)
    full_recordings = certified_full_recordings(links)
    corrections = apple_music_corrections(links)
    if recordings is None:
        recordings = json.loads(RECORDINGS.read_text(encoding="utf-8"))
    if not isinstance(master, list):
        raise ValueError("catalog_master.json must contain a list")
    master = list(master) + recording_works(recordings)
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
    if artwork_corrections is None:
        artwork_corrections = json.loads(ARTWORK_CORRECTIONS.read_text(encoding="utf-8"))
    artwork_fixes = corrected_artwork(artwork_corrections)
    unknown = sorted((set(certified_apple) | set(full_recordings) | set(corrections)
                      | set(artwork_fixes)) - set(by_id))
    if unknown:
        raise ValueError(f"platform links reference unknown works: {unknown}")

    genre_rules, mood_rules = vocabulary_rules("genre"), vocabulary_rules("mood")
    classifications = decisions.get("classifications")
    if not isinstance(classifications, list):
        raise ValueError("human mapping artifacts have an invalid schema")
    decisions_by_review = {item.get("review_id"): item for item in classifications}
    if len(decisions_by_review) != len(classifications):
        raise ValueError("human mapping artifacts contain duplicate review_id values")

    seen = set()
    pending = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) - {"hidden"} != {"review_id"}:
            raise ValueError(f"selection entry {position} must contain only review_id and hidden")
        if "hidden" in entry and entry["hidden"] is not True:
            raise ValueError(f"selection entry {position}: hidden must be true when present")
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
        status = release.get("status")
        if status == "released":
            release_type = RELEASE_TYPES.get(release.get("type"))
            if release_type is None:
                raise ValueError(f"{work_id}: unsupported release type {release.get('type')!r}")
        elif status in NON_COMMERCIAL_TYPES and "provisional" in work:
            release_type = NON_COMMERCIAL_TYPES[status]
        else:
            raise ValueError(f"{work_id} is not a released work")
        year = release.get("year")
        if not (isinstance(year, int) and not isinstance(year, bool)) and not (
            year is None and status != "released"
        ):
            raise ValueError(f"{work_id}: release year must be an integer")

        artists = work.get("artists")
        if not isinstance(artists, list) or not artists or not all(
            isinstance(artist, str) and artist.strip() for artist in artists
        ):
            raise ValueError(f"{work_id}: artists must be a non-empty string list")

        web_file = (work.get("artwork") or {}).get("web_file")
        if work_id in artwork_fixes:
            wrong, web_file = artwork_fixes[work_id]
            if (work.get("artwork") or {}).get("web_file") != wrong:
                raise ValueError(f"{work_id}: artwork correction expects {wrong!r}")
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
            "spotify": _platform_url((work.get("spotify") or {}).get("url"), SPOTIFY_URL_RE,
                                     f"{work_id} Spotify"),
            "appleMusic": _apple_music(work, work_id, certified_apple, corrections),
            "version": work.get("version"),
            "youtube": full_recordings.get(work_id, {}).get("youtube"),
            "soundcloud": full_recordings.get(work_id, {}).get("soundcloud"),
            "artists": [artist.strip() for artist in artists],
            "genres": _reviewed_terms(decision, "genre", genre_rules, work_id),
            "moods": _reviewed_terms(decision, "mood", mood_rules, work_id),
        }
        if tuple(row) != PUBLIC_FIELDS:
            raise AssertionError("public field order changed")
        if release_type == "SelfPublished" and not (row["youtube"] or row["soundcloud"]):
            raise ValueError(f"{work_id}: a self-published recording needs its YouTube or SoundCloud link")
        pending.append((review_id, work_id, decision, row, work.get("provisional") or []))

    # Previews last, so selection and credit errors keep precedence.
    if manifest is None:
        manifest = json.loads(PREVIEW_MANIFEST.read_text(encoding="utf-8"))
    preview_entries = {
        entry["review_id"]: entry
        for entry in previews.validate_manifest(manifest, selection, decisions)
    }
    for review_id, work_id, decision, row, provisional in pending:
        entry = preview_entries[review_id]
        if entry["work_id"] != work_id:
            raise ValueError(f"#{review_id}: preview manifest work_id differs from the mapping")
        if provisional and entry["status"] == "verified":
            raise ValueError(f"{work_id}: provisional fields {provisional} need the owner's approval "
                             "before publication")
        if row["roles"] is None:
            row["roles"] = [_role_from_evidence(decision, entry)]
            row["role"] = _primary_role(decision, row["roles"], work_id)
    return [(review_id, work_id, row, preview_entries[review_id])
            for review_id, work_id, _, row, _ in pending]


def _apple_music(work, work_id, certified, corrections=None):
    """The registered catalogue URL (or its correction), else the certified addition, else None."""
    registered = (work.get("apple_music") or {}).get("url")
    if corrections and work_id in corrections:
        wrong, corrected = corrections[work_id]
        if registered != wrong:
            raise ValueError(f"{work_id}: Apple Music correction expects {wrong!r}, "
                             f"catalogue has {registered!r}")
        registered = corrected
    registered = _platform_url(registered, APPLE_MUSIC_URL_RE, f"{work_id} Apple Music")
    if registered and work_id in certified:
        raise ValueError(f"{work_id} already has a registered Apple Music URL; "
                         "a certified addition must not replace it")
    return registered or certified.get(work_id)


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
            raise ValueError(SCHEMA_ERROR)
        unreleased = row["releaseType"] in NON_COMMERCIAL_TYPES.values()
        if not all(isinstance(row[key], str) for key in PUBLIC_FIELDS[:5]) or not (
            (isinstance(row["year"], int) and not isinstance(row["year"], bool)
             and 1000 <= row["year"] <= 9999)
            or (row["year"] is None and unreleased)
        ) or not (row["version"] is None or row["version"] in VERSIONS) or (
            unreleased and (row["spotify"] or row["appleMusic"])
        ) or not (
            isinstance(row["roles"], list) and row["roles"]
            and all(isinstance(role, str) for role in row["roles"])
        ) or not (
            isinstance(row["preview"], str) and previews.PREVIEW_NAME_RE.match(row["preview"])
        ):
            raise ValueError(f"{SCHEMA_ERROR} (preview is required)")
        if not row["artists"] or not all(
            isinstance(row[key], list) and all(isinstance(item, str) and item for item in row[key])
            for key in ("artists", "genres", "moods")
        ):
            raise ValueError(f"{SCHEMA_ERROR} (artists, genres and moods are string lists)")
        try:
            _platform_url(row["spotify"], SPOTIFY_URL_RE, "spotify")
            _platform_url(row["appleMusic"], APPLE_MUSIC_URL_RE, "appleMusic")
            for platform, pattern in FULL_RECORDING_URL_RES.items():
                _platform_url(row[platform], pattern, platform)
        except ValueError as exc:
            raise ValueError(f"{SCHEMA_ERROR}: {exc}") from None
        values = [quote(row[key]) for key in PUBLIC_FIELDS[:5]]
        values.append("null" if row["year"] is None else str(row["year"]))
        values.append("[" + ", ".join(quote(role) for role in row["roles"]) + "]")
        values.append(quote(row["preview"]))
        values.extend("null" if row[key] is None else quote(row[key])
                      for key in ("spotify", "appleMusic", "version", "youtube", "soundcloud"))
        values.extend("[" + ", ".join(quote(item) for item in row[key]) + "]"
                      for key in ("artists", "genres", "moods"))
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
    *, master_path=MASTER, recordings_path=RECORDINGS, selection_path=SELECTION, decisions_path=DECISIONS,
    manifest_path=PREVIEW_MANIFEST, output=OUTPUT, log_path=EXCLUSIONS_LOG
):
    """Write js/music-data.js and the exclusion log; return (rows, exclusions)."""
    master = json.loads(Path(master_path).read_text(encoding="utf-8"))
    recordings = json.loads(Path(recordings_path).read_text(encoding="utf-8"))
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    decisions = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows, exclusions = project_with_exclusions(master, selection, decisions, repo=REPO,
                                               manifest=manifest, recordings=recordings)
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
    hidden = sum(item["reason"] == "hidden_by_owner" for item in exclusions)
    print(f"PUBLIC MUSIC DATA OK: {len(rows)} published with preview, {len(exclusions) - hidden} excluded "
          f"without a reproducible preview, {hidden} hidden by the owner -> {args.output} "
          f"(log: {args.log.name})")


if __name__ == "__main__":
    main()
