#!/usr/bin/env python3
"""Focused tests for the browser-safe /music/ catalogue projection."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import generate_public_music_data as generator  # noqa: E402


class PublicMusicDataTests(unittest.TestCase):
    def setUp(self):
        self.master = json.loads((HERE / "catalog_master.json").read_text(encoding="utf-8"))
        self.selection = json.loads(
            (HERE / "public_music_selection.json").read_text(encoding="utf-8")
        )
        evidence_dir = HERE / "spikes" / "essentia"
        self.decisions = json.loads(
            (evidence_dir / "human_review_decisions.json").read_text(encoding="utf-8")
        )
        self.recordings = json.loads(generator.RECORDINGS.read_text(encoding="utf-8"))
        self.manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        # Counts come from the manifest: one published row per verified entry, one selected
        # work per manifest entry.
        self.verified = [e for e in self.manifest["entries"] if e["status"] == "verified"]
        self.blocked = {e["review_id"]: e["work_id"] for e in self.manifest["entries"]
                        if e["status"] == "blocked"}
        # Selection entries the owner hid ("hidden": true) keep a verified preview but are not published.
        self.hidden = generator.hidden_review_ids(self.selection)
        self.published = [e for e in self.verified if e["review_id"] not in self.hidden]

    def project(self, master=None, selection=None, decisions=None):
        return generator.project(
            master or self.master,
            selection or self.selection,
            decisions or self.decisions,
            repo=REPO,
        )

    def project_all(self):
        """Whole selection before the preview requirement (credit checks of excluded works)."""
        return generator.project_all(self.master, self.selection, self.decisions, repo=REPO)

    PUBLISHED = [
        "Hasta Que Lleguemos Al Mar",
        "Hace Tanto Tiempo",
        "Volver a Verte",
        "Cómo Decirte",
        "Nuestro Hogar",
        "12 Meses",
        "La Bamba",
        "Abrazo Imaginario",
        "Allá",
        "Anoche Me Enamoré",
        "Eres Veneno",
        "Imagina",
        "Invencible",
        "Si Antes Te Hubiera Conocido - Cover Acústico",
        "Vida Tras Vida",
        "Volver a Verte",
    ]
    # Selected works whose audio is not available locally: always excluded, never fabricated.
    EXCLUDED = {
        "33": "adios-amor-version-bolero--luis-guinea--2020",
        "34": "blue-moon--luis-guinea--2015",
        "37": "lo-que-queda-de-mi--escala-de-grises--2016",
        "38": "shape-of-you-acoustic--segundo-piso--2017",
    }

    def test_projection_uses_only_the_explicit_public_schema(self):
        rows = self.project()

        # Every selected work is validated; only those with a verified preview are published.
        self.assertEqual(len(rows), len(self.published))
        self.assertEqual(len(self.project_all()), len(self.selection["entries"]))
        self.assertEqual(len(self.selection["entries"]), len(self.manifest["entries"]))
        self.assertEqual(
            set(rows[0]),
            {"title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview",
             "spotify", "appleMusic", "version", "youtube", "soundcloud", "artists", "genres", "moods"},
        )
        hasta = next(row for row in rows if row["title"] == "Hasta Que Lleguemos Al Mar")
        self.assertEqual(
            hasta,
            {
                "title": "Hasta Que Lleguemos Al Mar",
                "artist": "Luis Guinea, Tony Barhoum",
                "role": "Artist",
                "artwork": "Hasta-Que-Lleguemos-Al-Mar---Luis-Guinea.webp",
                "releaseType": "Single",
                "year": 2024,
                "roles": ["Artist"],
                "preview": "hasta-que-lleguemos-al-mar--luis-guinea--2024.mp3",
                "spotify": "https://open.spotify.com/track/0kfbpBjVoJ9hrNbS8S4CzM",
                "appleMusic": "https://music.apple.com/mx/album/hasta-que-lleguemos-al-mar-feat-"
                              "tony-barhoum/1753986775?i=1753986777&uo=4",
                "version": None,
                "youtube": None,
                "soundcloud": None,
                "artists": ["Luis Guinea", "Tony Barhoum"],
                "genres": ["pop", "folk_singer_songwriter"],
                "moods": ["warm", "bright"],
            },
        )
        self.assertLessEqual({row["role"] for row in rows}, generator.ALLOWED_ROLES)
        self.assertTrue(all(
            row["role"] in row["roles"]
            or (row["role"] == "Composer" and generator.COMPOSER_CREDITS & set(row["roles"]))
            or (row["role"] == "Producer" and generator.PRODUCER_CREDITS & set(row["roles"]))
            for row in rows
        ))
        # The original sixteen previews keep their place at the head of the curated order.
        original = [row["title"] for row in rows if row["title"] in self.PUBLISHED]
        self.assertEqual(original[:len(self.PUBLISHED)], self.PUBLISHED)

    def test_new_human_credit_decisions_project_exact_facets_and_roles(self):
        # Credits are validated for the whole selection, even for works excluded for lack of preview.
        rows = {row["title"]: row for row in self.project_all()}

        self.assertEqual(rows["Adiós Amor (Versión Bolero)"]["role"], "Artist")
        self.assertEqual(rows["Adiós Amor (Versión Bolero)"]["roles"], ["Artist", "Producer"])
        self.assertEqual(rows["Blue Moon"]["role"], "Composer")
        self.assertEqual(
            rows["Blue Moon"]["roles"], ["Songwriter", "Artist", "Producer"]
        )
        self.assertEqual(rows["Cómo Decirte"]["role"], "Producer")
        self.assertEqual(
            rows["Cómo Decirte"]["roles"], ["Artist", "Songwriter", "Producer"]
        )
        self.assertEqual(rows["Lo Que Queda de Mí"]["role"], "Producer")
        self.assertEqual(
            rows["Lo Que Queda de Mí"]["roles"], ["Songwriter", "Producer", "Artist"]
        )
        for title in ("A Escondidas", "Shape of You - Acoustic"):
            self.assertEqual(rows[title]["role"], "Producer")
            self.assertEqual(rows[title]["roles"], ["Producer"])

    def test_publicly_excluded_human_case_is_rejected(self):
        for review_id in ("39", "40"):
            with self.subTest(review_id=review_id):
                selection = json.loads(json.dumps(self.selection))
                selection["entries"].append({"review_id": review_id})

                with self.assertRaisesRegex(ValueError, "excluded from public selection"):
                    self.project(selection=selection)

    def test_composer_facet_requires_luis_songwriter_credit(self):
        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "34")
        luis = next(c for c in case["credits"] if c["name"] == "Luis Guinea")
        luis["roles"].remove("songwriter")

        with self.assertRaisesRegex(ValueError, "Composer facet requires songwriter"):
            self.project(decisions=decisions)

    def test_abrazo_imaginario_projects_the_human_credits_decision(self):
        row = next(row for row in self.project() if row["title"] == "Abrazo Imaginario")

        self.assertEqual(row["artist"], "Ricardo Bojalil")
        self.assertEqual(row["role"], "Producer")
        self.assertEqual(row["roles"], ["Songwriter", "Producer", "Recording Engineer"])

    def test_human_credits_must_name_a_performer_of_the_work(self):
        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "01")
        case["credits"][0]["name"] = "Someone Else"
        selection = json.loads(json.dumps(self.selection))
        selection["entries"].append({"review_id": "01"})

        with self.assertRaisesRegex(ValueError, "credit performer"):
            generator.project(self.master, selection, decisions, repo=REPO)

    def test_human_credits_must_include_a_supported_public_role(self):
        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "01")
        case["credits"][1]["roles"] = ["songwriter"]
        selection = json.loads(json.dumps(self.selection))
        selection["entries"].append({"review_id": "01"})

        with self.assertRaisesRegex(ValueError, "supported public role"):
            generator.project(self.master, selection, decisions, repo=REPO)

    def test_genres_and_moods_come_only_from_the_human_review(self):
        rows = {row["title"]: row for row in self.project_all()}
        # Reviewed values are published literally, in the order of the review.
        self.assertEqual(rows["La Bamba"]["genres"], ["reggae"])
        self.assertEqual(rows["La Bamba"]["moods"], ["bright", "warm", "playful", "groovy"])
        self.assertEqual((rows["Peligro"]["genres"], rows["Peligro"]["moods"]), (["latin_urban", "pop"], ["groovy", "playful"]))
        # An explicit editorial decision may approve a genre and leave the moods empty on purpose.
        self.assertEqual((rows["Alacrán"]["genres"], rows["Alacrán"]["moods"]), (["folk_singer_songwriter"], []))
        self.assertEqual(rows["Peligro"]["artists"],
                         ["Nina Jori", "Carla Calderon", "Luis Guinea", "Salvador Álvarez"])
        genres, moods = set(generator.vocabulary_terms("genre")), set(generator.vocabulary_terms("mood"))
        for row in rows.values():
            self.assertLessEqual(set(row["genres"]), genres)
            self.assertLessEqual(set(row["moods"]), moods)
            self.assertEqual(", ".join(row["artists"]), row["artist"])

        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "11")
        case["values"]["evidence"] = "analisis_audio"
        # A work without a human review publishes empty lists, never an inference.
        bamba = next(r for r in self.project(decisions=decisions) if r["title"] == "La Bamba")
        self.assertEqual((bamba["genres"], bamba["moods"]), ([], []))
        case["values"].update(evidence="human_review", mood=["sad"])
        with self.assertRaisesRegex(ValueError, "mood outside vocabularies.json"):
            self.project(decisions=decisions)

    def test_an_empty_mood_needs_an_explicit_decision_allowed_by_the_vocabulary(self):
        vocabularies = json.loads(generator.VOCABULARIES.read_text(encoding="utf-8"))
        fields = vocabularies["fields"]
        # Only mood admits an explicit empty list; every other cardinality is unchanged.
        self.assertEqual([f for f, spec in fields.items() if "explicit_empty" in spec], ["mood"])
        self.assertEqual((fields["mood"]["cardinality"], fields["genre"]["cardinality"]), ([1, 4], [1, 2]))
        # «Alacrán» is published with its approved genre and no mood, as the review records.
        alacran = next(c for c in self.decisions["classifications"] if c["review_id"] == "51")
        self.assertEqual(alacran["values"]["mood"], [])
        self.assertTrue(any("mood" in note.lower() for note in alacran["negative_decisions"]))

        def project_with(change):
            decisions = json.loads(json.dumps(self.decisions))
            change(next(c for c in decisions["classifications"] if c["review_id"] == "51"))
            return next(r for r in self.project(decisions=decisions) if r["title"] == "Alacrán")

        # Without the recorded decision the empty list is rejected.
        with self.assertRaisesRegex(ValueError, "empty mood needs an explicit editorial decision"):
            project_with(lambda case: case.update(negative_decisions=[]))
        # Genre has no such exception, and non-empty lists keep the vocabulary cardinality.
        with self.assertRaisesRegex(ValueError, "empty genre needs an explicit editorial decision"):
            project_with(lambda case: case["values"].update(genre=[]))
        with self.assertRaisesRegex(ValueError, "5 mood values"):
            project_with(lambda case: case["values"].update(
                mood=["warm", "bright", "dreamy", "intimate", "calm"]))
        with self.assertRaisesRegex(ValueError, "3 genre values"):
            project_with(lambda case: case["values"].update(genre=["pop", "rock", "reggae"]))
        # An absent field stays unclassified rather than invalid.
        row = project_with(lambda case: case["values"].pop("mood"))
        self.assertEqual((row["genres"], row["moods"]), (["folk_singer_songwriter"], []))

    def test_projection_rejects_unreleased_or_incomplete_works(self):
        master = json.loads(json.dumps(self.master))
        chosen_id = "hasta-que-lleguemos-al-mar--luis-guinea--2024"
        work = next(item for item in master if item["id"] == chosen_id)
        work["release"]["status"] = "unreleased"

        with self.assertRaisesRegex(ValueError, "not a released work"):
            self.project(master=master)

    def test_projection_rejects_an_open_human_case(self):
        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "19")
        case["catalog_link"]["status"] = "unmapped"

        with self.assertRaisesRegex(ValueError, "is not mapped"):
            self.project(decisions=decisions)

    def test_owner_exclusions_stay_out_of_the_selection(self):
        # 2026-10-13: Antes de Irme (Mariachi), Hasta El Altar, Junto A Mí, Me Equivoqué and
        # El Ganador (#72, kept in the private inventory) are not published.
        selected = {e["review_id"] for e in self.selection["entries"]}
        # 2026-10-24: No Hay Más (Stripped) (#90) withdrawn by the owner after its window was approved.
        for review_id in ("17", "24", "27", "29", "72", "90"):
            case = next(c for c in self.decisions["classifications"] if c["review_id"] == review_id)
            self.assertIs(case["public_exclusion"], True)
            self.assertNotIn(review_id, selected)
        # One public row per work: no two selected cases point at the same work.
        works = [next(c for c in self.decisions["classifications"] if c["review_id"] == r)
                 ["catalog_link"]["work_id"] for r in selected]
        self.assertEqual(len(works), len(set(works)))
        self.assertIn("in-my-life-cover--rogelio-edel--2021", works)
        self.assertNotIn("in-my-life--rogelio-edel--2021", works)

    def test_unreleased_recordings_project_without_release_identifiers(self):
        rows = {row["title"]: row for row in self.project_all()}

        peligro = rows["Peligro"]
        self.assertEqual((peligro["releaseType"], peligro["year"], peligro["version"]),
                         ("Unreleased", None, None))
        self.assertEqual((peligro["role"], peligro["roles"]), ("Composer", ["Co-writer"]))
        self.assertEqual((peligro["spotify"], peligro["appleMusic"]), (None, None))
        self.assertEqual(peligro["artwork"], "generic-cover.webp")
        piano = rows["Inenarrable (Qué Suerte)"]
        self.assertEqual((piano["releaseType"], piano["version"]), ("Unreleased", "PianoVocal"))
        # Instrumentales is a category, not a credit: the roles come from explicit decisions, and
        # covers of third-party works never carry a songwriting credit.
        self.assertEqual((rows["Prometheus"]["version"], rows["Prometheus"]["roles"]),
                         ("Instrumental", ["Songwriter", "Arranger", "Producer"]))
        for cover in ("Diamonds - Cover", "She Wolf - Cover",
                      "One Last Time vs Rather Be vs Outside vs Summer"):
            self.assertEqual((rows[cover]["role"], rows[cover]["roles"]), ("Producer", ["Arranger", "Producer"]))
        # Co-production surfaces under Producer, co-writing under Composer.
        self.assertEqual((rows["Jinne, Jinne"]["role"], rows["Jinne, Jinne"]["artist"]),
                         ("Producer", "Canciones de Puño y Letra"))
        self.assertEqual((rows["It Feels Like Falling In Love"]["role"],
                          rows["It Feels Like Falling In Love"]["roles"]),
                         ("Composer", ["Co-writer", "Co-arranger", "Co-producer"]))

    def test_releases_newer_than_the_sheet_carry_verified_links_and_official_artwork(self):
        rows = {row["title"]: row for row in self.project_all()}
        for title in ("I Want U", "Te Extraño", "Mejor Versión"):
            row = rows[title]
            self.assertEqual((row["releaseType"], row["year"], row["artwork"]),
                             ("EP", 2025, "Mil-Versiones---Rogelio-Edel.webp"))
            self.assertTrue(row["spotify"] and row["appleMusic"])
        beso = rows["El Beso"]
        self.assertEqual((beso["artist"], beso["releaseType"], beso["year"]), ("Tufic, Luis Guinea", "Single", 2026))
        self.assertEqual(beso["spotify"], "https://open.spotify.com/track/4XUUtkTby59nhAjIZ6A0uI")
        self.assertEqual(rows["La Martiniana"]["roles"], ["Artist", "Arranger", "Producer"])
        # The rough mix of a released song is another recording: no links, no release artwork.
        rough = rows["Dame Más de Ti"]
        self.assertEqual((rough["releaseType"], rough["version"], rough["spotify"], rough["artwork"]),
                         ("Unreleased", "RoughMix", None, "generic-cover.webp"))
        recordings = json.loads(json.dumps(self.recordings))
        released = next(w for w in recordings["recordings"] if w["release"]["status"] == "released")
        released["spotify"]["url"] = released["apple_music"]["url"] = None
        with self.assertRaisesRegex(ValueError, "needs a verified streaming link"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO,
                              recordings=recordings)

    def test_a_release_without_spotify_records_it_as_unverified_and_keeps_urls_consistent(self):
        def project(recordings):
            return generator.project(self.master, self.selection, self.decisions, repo=REPO,
                                     recordings=recordings)
        recordings = json.loads(json.dumps(self.recordings))
        work = next(w for w in recordings["recordings"] if w["id"] == "1000-dias--pablo-delgado")
        work["basis"] = [b.replace(generator.SPOTIFY_UNVERIFIED, "") for b in work["basis"]]
        with self.assertRaisesRegex(ValueError, "release without Spotify must record"):
            project(recordings)
        for track_id, url in ((None, "https://open.spotify.com/track/" + "a" * 22),
                              ("a" * 22, None),
                              ("a" * 22, "https://open.spotify.com/track/" + "b" * 22)):
            recordings = json.loads(json.dumps(self.recordings))
            work = next(w for w in recordings["recordings"] if w["id"] == "el-beso--tufic")
            work["spotify"] = {"track_id": track_id, "url": url}
            with self.subTest(track_id=track_id, url=url), \
                    self.assertRaisesRegex(ValueError, "Spotify URL must be the one of its track_id"):
                project(recordings)

    def test_sync_availability_is_an_internal_owner_decision_independent_of_use_scene(self):
        works = {w["id"]: w for w in self.recordings["recordings"]}
        decided = {wid: w["sync_availability"] for wid, w in works.items() if w["sync_availability"]}
        self.assertEqual(decided, {
            "1000-dias--pablo-delgado": "on_request", "en-el-momento-justo--pablo-delgado": "on_request",
            "solo-esta-noche--pablo-delgado": "on_request", "tonto-enamorado--pablo-delgado": "on_request",
            "ahi-estas--canciones-de-puno-y-letra": "not_offered",
            "el-sembrador--canciones-de-puno-y-letra": "not_offered",
            "gracias-por-todo--canciones-de-puno-y-letra": "not_offered",
            "hasta-el-final-de-mis-dias--canciones-de-puno-y-letra": "not_offered",
            "juntos-somos-imparables--canciones-de-puno-y-letra": "not_offered"})
        # No scenes approved yet: availability does not come from use_scene.
        self.assertTrue(all(works[wid]["editorial"]["use_scene"] == [] for wid in decided))
        # Never published.
        rows = generator.project(self.master, self.selection, self.decisions, repo=REPO,
                                 recordings=self.recordings)
        javascript = generator.serialize(rows)
        for term in ("sync", "on_request", "not_offered", "one_stop"):
            self.assertNotIn(term, javascript)
        for value, message in (("one_stop", "unsupported sync_availability"),
                               (True, "unsupported sync_availability")):
            recordings = json.loads(json.dumps(self.recordings))
            next(w for w in recordings["recordings"] if w["id"] == "solo-esta-noche--pablo-delgado")[
                "sync_availability"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                generator.project(self.master, self.selection, self.decisions, repo=REPO, recordings=recordings)
        recordings = json.loads(json.dumps(self.recordings))
        next(w for w in recordings["recordings"] if w["id"] == "el-sembrador--canciones-de-puno-y-letra")[
            "editorial"]["use_scene"] = ["romantic"]
        with self.assertRaisesRegex(ValueError, "not offered for sync cannot list use_scene"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, recordings=recordings)
        recordings = json.loads(json.dumps(self.recordings))
        del recordings["recordings"][0]["sync_availability"]
        with self.assertRaisesRegex(ValueError, "keys must be"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, recordings=recordings)

    def test_recordings_cannot_publish_provisional_fields_or_release_identifiers(self):
        manifest = json.loads(json.dumps(self.manifest))
        entry = next(e for e in manifest["entries"] if e["review_id"] == "22")  # El Feo, verified
        self.assertEqual(entry["status"], "verified")
        recordings = json.loads(json.dumps(self.recordings))
        next(w for w in recordings["recordings"] if w["id"] == entry["work_id"])["provisional"] = ["artists"]
        with self.assertRaisesRegex(ValueError, "provisional fields .* need the owner's approval"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, manifest=manifest,
                              recordings=recordings)

        recordings = json.loads(json.dumps(self.recordings))
        unreleased = next(w for w in recordings["recordings"] if w["release"]["status"] == "unreleased")
        unreleased["spotify"]["url"] = "https://open.spotify.com/track/" + "a" * 22
        with self.assertRaisesRegex(ValueError, "cannot carry release identifiers"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO,
                              recordings=recordings)
        recordings = json.loads(json.dumps(self.recordings))
        recordings["recordings"][0]["version"] = "Remix"
        with self.assertRaisesRegex(ValueError, "unsupported version"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO,
                              recordings=recordings)
        recordings = json.loads(json.dumps(self.recordings))
        recordings["recordings"][0]["id"] = "hace-tanto-tiempo--luis-guinea--2021"
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO,
                              recordings=recordings)

    def test_instrumental_folder_requires_an_explicit_credits_decision(self):
        decisions = json.loads(json.dumps(self.decisions))
        case = next(c for c in decisions["classifications"] if c["review_id"] == "48")
        del case["credits"], case["credits_decision"]
        with self.assertRaisesRegex(ValueError, "#48: audio folder 'Instrumentales' has no public role"):
            self.project(decisions=decisions)

    def test_unreleased_rows_serialize_a_null_year_and_their_version(self):
        row = next(r for r in self.project_all() if r["title"] == "Peligro")
        javascript = generator.serialize([dict(row, preview="peligro--nina-jori.mp3")])
        self.assertIn("releaseType:'Unreleased', year:null", javascript)
        self.assertIn("appleMusic:null, version:null, youtube:null, soundcloud:null, artists:['Nina Jori', "
                      "'Carla Calderon', 'Luis Guinea', 'Salvador Álvarez'], genres:['latin_urban', 'pop'], moods:['groovy', 'playful'] }", javascript)
        with self.assertRaisesRegex(ValueError, "artists, genres and moods are string lists"):
            generator.serialize([dict(row, preview="peligro--nina-jori.mp3", artists=[])])
        released = self.project()[0]
        with self.assertRaisesRegex(ValueError, "sixteen-field public schema"):
            generator.serialize([dict(released, year=None)])
        with self.assertRaisesRegex(ValueError, "sixteen-field public schema"):
            generator.serialize([dict(row, preview="x.mp3", spotify=released["spotify"])])

    def test_generated_javascript_contains_no_internal_catalog_fields(self):
        rows = self.project()
        javascript = generator.serialize(rows)

        for forbidden in (
            "audio_ref",
            "One Page Luis Guinea",
            "Master.wav",
            "apple_music",
            "track_id",
            "collection_id",
            "storefront",
            "isrc",
            "provenance",
            "conflict",
            "catalog_link",
            "vocal_performer",
            "recording_engineer",
        ):
            self.assertNotIn(forbidden, javascript)
        # Spotify appears only as the public field and its track URLs.
        self.assertEqual(javascript.count("spotify"), len(rows) + sum(1 for r in rows if r["spotify"]))
        # `preview` contains the substring "review"; review ids/keys must still be absent.
        self.assertNotRegex(javascript, r"\breview")

        role_pattern = re.compile(
            r"title:\s*'((?:[^'\\]|\\.)*)',\s*"
            r"artist:\s*'((?:[^'\\]|\\.)*)',\s*"
            r"role:\s*'((?:[^'\\]|\\.)*)'"
        )
        self.assertEqual(len(role_pattern.findall(javascript)), len(rows))

    def test_only_songs_with_a_valid_preview_are_published_and_the_rest_are_logged(self):
        rows, exclusions = generator.project_with_exclusions(
            self.master, self.selection, self.decisions, repo=REPO)

        # Two published works share the title "Volver a Verte" (Luis Guinea / Ana Guinea). The
        # sixteen original previews keep their order at the head of the list.
        self.assertEqual(len(rows), len(self.published))
        self.assertEqual(
            [(row["title"], row["preview"]) for row in rows if row["title"] in self.PUBLISHED][:len(self.PUBLISHED)],
            [
                ("Hasta Que Lleguemos Al Mar", "hasta-que-lleguemos-al-mar--luis-guinea--2024.mp3"),
                ("Hace Tanto Tiempo", "hace-tanto-tiempo--luis-guinea--2021.mp3"),
                ("Volver a Verte", "volver-a-verte--luis-guinea--2020.mp3"),
                ("Cómo Decirte", "como-decirte--luis-guinea--2022.mp3"),
                ("Nuestro Hogar", "nuestro-hogar--luis-guinea--2022.mp3"),
                ("12 Meses", "12-meses--rogelio-edel--2022.mp3"),
                ("La Bamba", "la-bamba--rogelio-edel--2022.mp3"),
                ("Abrazo Imaginario", "abrazo-imaginario--ricardo-bojalil--2022.mp3"),
                ("Allá", "alla--rogelio-edel--2022.mp3"),
                ("Anoche Me Enamoré", "anoche-me-enamore--rogelio-edel--2021.mp3"),
                ("Eres Veneno", "eres-veneno--rogelio-edel--2024.mp3"),
                ("Imagina", "imagina--rogelio-edel--2024.mp3"),
                ("Invencible", "invencible--ana-guinea--2021.mp3"),
                ("Si Antes Te Hubiera Conocido - Cover Acústico",
                 "si-antes-te-hubiera-conocido-cover-acustico--ana-guinea--2024.mp3"),
                ("Vida Tras Vida", "vida-tras-vida--ana-guinea--2024.mp3"),
                ("Volver a Verte", "volver-a-verte--ana-guinea--2022.mp3"),
            ],
        )
        hidden = {e["review_id"]: e["work_id"] for e in self.verified if e["review_id"] in self.hidden}
        self.assertEqual({item["review_id"]: item["work_id"] for item in exclusions}, self.blocked | hidden)
        self.assertLessEqual(self.EXCLUDED.items(), self.blocked.items())
        self.assertEqual({item["reason"] for item in exclusions if item["review_id"] in self.blocked},
                         {"no_authorized_preview"})
        self.assertTrue(all(item["detail"].strip() for item in exclusions))

        log = generator.exclusions_log(rows, exclusions, self.selection)
        self.assertEqual(sorted(log["published"] + [e["review_id"] for e in log["excluded"]]),
                         sorted(e["review_id"] for e in self.selection["entries"]))
        self.assertEqual(log, json.loads(generator.EXCLUSIONS_LOG.read_text(encoding="utf-8")))

    def test_invalid_preview_files_are_excluded_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_repo = Path(directory)
            real = REPO / "assets" / "audio" / "previews" / "12-meses--rogelio-edel--2022.mp3"
            target = fake_repo / "assets" / "audio" / "previews"
            target.mkdir(parents=True)
            (target / real.name).write_bytes(real.read_bytes() * 3)  # ~133 s: too long
            (target / "la-bamba--rogelio-edel--2022.mp3").write_bytes(b"not an mp3")
            self.assertEqual(generator.preview_problem(
                "assets/audio/previews/12-meses--rogelio-edel--2022.mp3", repo=fake_repo)[0],
                "preview_too_long")
            self.assertEqual(generator.preview_problem(
                "assets/audio/previews/la-bamba--rogelio-edel--2022.mp3", repo=fake_repo)[0],
                "preview_unplayable")
            self.assertEqual(generator.preview_problem(
                "assets/audio/previews/nuestro-hogar--luis-guinea--2022.mp3", repo=fake_repo)[0],
                "preview_missing")
            self.assertEqual(generator.preview_problem(
                "One Page Luis Guinea/audios/x.mp3", repo=fake_repo)[0], "preview_outside_public_dir")
        self.assertIsNone(generator.preview_problem(
            "assets/audio/previews/12-meses--rogelio-edel--2022.mp3", repo=REPO))

    def test_evidence_role_comes_from_the_authorized_audio_folder(self):
        # #05 has no credits decision: Producer comes from the manifest source folder.
        manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        rows = {row["title"]: row for row in generator.project(
            self.master, self.selection, self.decisions, repo=REPO, manifest=manifest)}
        self.assertEqual((rows["12 Meses"]["role"], rows["12 Meses"]["roles"]),
                         ("Producer", ["Producer"]))

        entry = next(e for e in manifest["entries"] if e["review_id"] == "05")
        entry["source"] = entry["source"].replace("/Productor/", "/Instrumentales/")
        with self.assertRaisesRegex(ValueError, "#05: audio folder 'Instrumentales' has no public role"):
            generator.project(self.master, self.selection, self.decisions,
                              repo=REPO, manifest=manifest)

    def test_a_declared_preview_that_was_not_generated_is_excluded(self):
        manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            fake_repo = Path(directory)
            corrected = json.loads(generator.ARTWORK_CORRECTIONS.read_text(encoding="utf-8"))["corrections"]
            for row in self.master + self.recordings["recordings"] + [{"artwork": c} for c in corrected]:
                artwork = (row.get("artwork") or {}).get("web_file")
                if artwork:
                    target = fake_repo / artwork
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
            rows, exclusions = generator.project_with_exclusions(
                self.master, self.selection, self.decisions,
                repo=fake_repo, manifest=manifest,
            )
            self.assertEqual(rows, [])
            reasons = {item["review_id"]: item["reason"] for item in exclusions}
            self.assertEqual(len(reasons), len(self.selection["entries"]))
            self.assertEqual({r for i, r in reasons.items() if i not in self.blocked.keys() | self.hidden},
                             {"preview_missing"})

    def test_serialized_preview_never_exposes_private_audio_details(self):
        javascript = generator.serialize(self.project())

        self.assertEqual(javascript.count("preview:null"), 0)
        self.assertEqual(len(re.findall(r"preview:'[a-z0-9-]+\.mp3'", javascript)), len(self.published))
        for forbidden in ("source", "sha256", "Productor", "Cantautor", "MixV1", "evidence"):
            self.assertNotIn(forbidden, javascript)
        row = dict(self.project()[0], preview="../secret/master.mp3")
        with self.assertRaisesRegex(ValueError, "public schema"):
            generator.serialize([row])
        with self.assertRaisesRegex(ValueError, "preview is required"):
            generator.serialize([dict(self.project()[0], preview=None)])

    CERTIFIED_APPLE = {
        "12 Meses": "https://music.apple.com/us/album/12-meses/1650041672?i=1650041673",
        "La Bamba": "https://music.apple.com/us/album/la-bamba/1754643674?i=1754643675",
        "Imagina": "https://music.apple.com/us/album/imagina/1778357807?i=1778357960",
        "Abrazo Imaginario": "https://music.apple.com/mx/album/abrazo-imaginario-single/1846996818",
        "Anoche Me Enamoré": "https://music.apple.com/mx/album/anoche-me-enamor%C3%A9/1754644382?i=1754644383",
        "In My Life - Cover": "https://music.apple.com/mx/album/in-my-life-cover/1754643926?i=1754643927",
        "Sunday Morning": "https://music.apple.com/mx/album/sunday-morning/1754639153?i=1754639154",
        "¿Por Qué Lloras?": "https://music.apple.com/mx/album/por-qu%C3%A9-lloras-feat-luis-guinea/1312566966?i=1312566970",
        "Alguien Como Yo": "https://music.apple.com/mx/album/alguien-como-yo/879580207?i=879580219",
        "Llegue Muy Tarde": "https://music.apple.com/mx/album/llegue-muy-tarde/1659031631?i=1659031632",
    }
    # Catalogue Apple URLs that point to another recording, replaced by the certified one.
    CORRECTED_APPLE = {
        "How Deep Is Your Love": "https://music.apple.com/mx/album/how-deep-is-your-love/1613658995?i=1613659506&uo=4",
    }
    WITHOUT_APPLE = {"Allá", "Eres Veneno"}
    # Releases whose Spotify URL is not verified (not a claim that they are absent from Spotify):
    # Apple Music only, verified with the iTunes Search API on 2026-10-20 and 2026-10-21.
    WITHOUT_SPOTIFY = {("1000 Días", "Pablo Delgado, Paz Álvarez"), ("En El Momento Justo", "Pablo Delgado"),
                       ("Solo Esta Noche", "Pablo Delgado"), ("Tonto Enamorado", "Pablo Delgado"),
                       ("Juntos Somos Imparables", "Canciones de Puño y Letra"),
                       ("Yeah (Intro)", "Abe Rapa"), ("Puerta", "Abe Rapa"), ("Luces de Ayer", "Abe Rapa"),
                       ("Best of Me", "Abe Rapa"), ("No Hay Más", "Abe Rapa")}

    def test_streaming_links_come_from_the_catalogue_or_the_certified_additions_only(self):
        rows = self.project()
        works = {(row["title"], row["artist"]): row for row in rows}
        released = [row for row in rows if row["releaseType"] in generator.RELEASE_TYPES.values()]
        for row in released:
            with self.subTest(title=row["title"], artist=row["artist"]):
                work = next(w for w in self.master + self.recordings["recordings"]
                            if w["title"] == row["title"] and ", ".join(w["artists"]) == row["artist"])
                self.assertEqual(row["spotify"], work["spotify"]["url"])
                registered = work["apple_music"]["url"]
                expected = self.CORRECTED_APPLE.get(row["title"]) or registered or self.CERTIFIED_APPLE.get(row["title"])
                self.assertEqual(row["appleMusic"], expected)
        self.assertEqual({(row["title"], row["artist"]) for row in released if not row["spotify"]},
                         self.WITHOUT_SPOTIFY)
        for row in released:
            if not row["spotify"]:
                with self.subTest(unverified_spotify=row["title"]):
                    self.assertTrue(row["appleMusic"])
                    work = next(w for w in self.recordings["recordings"]
                                if w["title"] == row["title"] and ", ".join(w["artists"]) == row["artist"])
                    self.assertTrue(any(generator.SPOTIFY_UNVERIFIED in b for b in work["basis"]))
        # Unreleased recordings never carry streaming links.
        self.assertTrue(all(row["spotify"] is None and row["appleMusic"] is None
                            for row in rows if row not in released))
        missing = {(row["title"], row["artist"]) for row in released if row["appleMusic"] is None}
        self.assertLessEqual({(t, "Rogelio Edel") for t in self.WITHOUT_APPLE}
                             | {("Volver a Verte", "Luis Guinea")}, missing)
        # Cómo Decirte keeps its registered URL (track 1646476110, the certified one's track).
        self.assertIn("i=1646476110", works[("Cómo Decirte", "Luis Guinea, Pablo Delgado")]["appleMusic"])

    def test_self_published_recordings_are_neither_unreleased_nor_commercial(self):
        rows = {row["title"]: row for row in self.project()}
        self_published = {t for t, r in rows.items() if r["releaseType"] == "SelfPublished"}
        self.assertEqual(self_published, {"Prometheus", "Singularidad del Genio", "She Wolf - Cover",
                                          "Diamonds - Cover", "One Last Time vs Rather Be vs Outside vs Summer"})
        for title in self_published:
            row = rows[title]
            with self.subTest(title=title):
                self.assertIsNone(row["year"])
                self.assertIsNone(row["spotify"])
                self.assertIsNone(row["appleMusic"])
                self.assertTrue(row["youtube"] or row["soundcloud"])
        links = json.loads(generator.PLATFORM_LINKS.read_text(encoding="utf-8"))
        links["full_recordings"] = [x for x in links["full_recordings"] if x["work_id"] != "prometheus--luis-guinea"]
        with self.assertRaisesRegex(ValueError, "self-published recording needs its YouTube or SoundCloud link"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, links=links)

    def test_owner_confirmed_credits_keep_arrangement_apart_from_authorship(self):
        rows = {(r["title"], r["artist"]): r for r in generator.project_all(
            self.master, self.selection, self.decisions, repo=REPO)}
        expected = {
            ("Tóxica", "Isabella Macías"): (["Producer", "Arranger"], "Producer"),
            ("Toxic", "Isabella Macías"): (["Arranger", "Producer"], "Producer"),
            ("Quién Soy - Acústica", "Louisiana"): (["Songwriter", "Co-writer", "Arranger", "Performer", "Producer"], "Composer"),
            ("A Million Dreams - Acoustic Cover", "Isabella Macías"): (["Producer", "Arranger"], "Producer"),
            ("Shallow - Cover", "Ana Guinea"): (["Arranger", "Producer"], "Producer"),
            ("En Libertad - Cover", "Ana Guinea"): (["Arranger", "Producer"], "Producer"),
            ("Súper Héroe", "Edson Corona, Charlie B"): (["Songwriter", "Co-writer", "Arranger", "Producer", "Performer"], "Composer"),
            ("Volver a Verte", "Ana Guinea"): (["Songwriter", "Producer"], "Producer"),
            ("Agua de Mar", "Luis Guinea, Salo, Efra Ardila"): (["Artist", "Co-writer", "Producer"], "Artist"),
            ("El Beso", "Tufic, Luis Guinea"): (["Artist", "Co-writer", "Co-producer"], "Artist"),
            ("How Deep Is Your Love", "Luis Guinea"): (["Artist", "Producer"], "Artist"),
            ("Imagina", "Rogelio Edel"): (["Producer"], "Producer"),
            ("Te Esperé - Cover", "Ana Guinea"): (["Producer", "Arranger"], "Producer"),
            ("Hagamos Un Trío", "Luis Guinea, Mirley Cauich Navarro"): (["Songwriter", "Co-writer"], "Composer"),
            ("Dime Señorita", "Carla Calderón, Luis Guinea, Efraín Ardila, Brandon Orr"): (["Songwriter", "Co-writer", "Co-producer"], "Composer"),
            ("Vuelta Completa", "Luis Guinea, Carla Merchant, Angel Elizalde, Paola Zozaya"): (["Songwriter", "Co-writer", "Producer"], "Composer"),
        }
        for key, (roles, role) in expected.items():
            with self.subTest(work=key):
                self.assertEqual((rows[key]["roles"], rows[key]["role"]), (roles, role))

    def test_artwork_correction_gives_each_release_its_own_cover(self):
        rows = {r["title"]: r for r in generator.project_all(self.master, self.selection, self.decisions, repo=REPO)}
        self.assertEqual(rows["Anoche Me Enamoré"]["artwork"], "Anoche-Me-Enamoré-2021---Rogelio-Edel.webp")
        live = next(w for w in self.master if w["id"] == "anoche-me-enamore--rogelio-edel--2024")
        self.assertEqual(live["artwork"]["web_file"], "assets/images/Anoche-Me-Enamoré---Rogelio-Edel.webp")
        self.assertTrue((REPO / live["artwork"]["web_file"]).is_file())
        stale = json.loads(generator.ARTWORK_CORRECTIONS.read_text(encoding="utf-8"))
        stale["corrections"][0]["wrong_web_file"] = "assets/images/other.webp"
        with self.assertRaisesRegex(ValueError, "artwork correction expects"):
            generator.project_all(self.master, self.selection, self.decisions, repo=REPO,
                                  artwork_corrections=stale)

    def test_full_recordings_and_apple_corrections_are_validated(self):
        rows = {row["title"]: row for row in self.project()}
        self.assertEqual(rows["Prometheus"]["youtube"], "https://www.youtube.com/watch?v=yHnT3_4kRRA")
        self.assertEqual(rows["Diamonds - Cover"]["soundcloud"], "https://soundcloud.com/lcguinea/diamonds")
        self.assertEqual(sum(1 for r in rows.values() if r["youtube"] or r["soundcloud"]), 5)
        links = json.loads(generator.PLATFORM_LINKS.read_text(encoding="utf-8"))
        for bad in ("https://youtu.be/yHnT3_4kRRA", "https://www.youtube.com/watch?v=x'><script>",
                    "javascript:alert(1)"):
            broken = json.loads(json.dumps(links))
            broken["full_recordings"][0]["url"] = bad
            with self.subTest(url=bad), self.assertRaisesRegex(ValueError, "not a valid public URL"):
                generator.project(self.master, self.selection, self.decisions, repo=REPO, links=broken)
        # A correction applies only while the catalogue still holds the exact wrong URL.
        stale = json.loads(json.dumps(links))
        stale["apple_music_corrections"][0]["wrong_url"] = "https://music.apple.com/mx/song/1"
        with self.assertRaisesRegex(ValueError, "Apple Music correction expects"):
            generator.project_all(self.master, self.selection, self.decisions, repo=REPO, links=stale)
        hdiyl = next(r for r in generator.project_all(self.master, self.selection, self.decisions, repo=REPO)
                     if r["title"] == "How Deep Is Your Love")
        self.assertIn("i=1613659506", hdiyl["appleMusic"])

    def test_certified_links_never_replace_a_registered_url_and_are_validated(self):
        links = json.loads(generator.PLATFORM_LINKS.read_text(encoding="utf-8"))
        conflict = json.loads(json.dumps(links))
        conflict["apple_music"].append({"work_id": "hace-tanto-tiempo--luis-guinea--2021",
                                        "url": "https://music.apple.com/us/album/x/1?i=2"})
        with self.assertRaisesRegex(ValueError, "already has a registered Apple Music URL"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, links=conflict)
        unknown = json.loads(json.dumps(links))
        unknown["apple_music"].append({"work_id": "not-a-work", "url": "https://music.apple.com/us/song/1"})
        with self.assertRaisesRegex(ValueError, "unknown works"):
            generator.project(self.master, self.selection, self.decisions, repo=REPO, links=unknown)
        for bad in ("http://music.apple.com/us/song/1", "https://evil.example/us/song/1",
                    "https://music.apple.com/us/song/1'><script>", "javascript:alert(1)"):
            broken = {"schema": links["schema"], "apple_music": [
                {"work_id": "alla--rogelio-edel--2022", "url": bad}]}
            with self.subTest(url=bad), self.assertRaisesRegex(ValueError, "not a valid public URL"):
                generator.project(self.master, self.selection, self.decisions, repo=REPO, links=broken)
        master = json.loads(json.dumps(self.master))
        next(w for w in master if w["id"] == "alla--rogelio-edel--2022")["spotify"]["url"] = "https://x.example/t"
        with self.assertRaisesRegex(ValueError, "Spotify is not a valid public URL"):
            generator.project(master, self.selection, self.decisions, repo=REPO)

    def test_absent_platforms_serialize_as_null_and_bad_urls_are_refused(self):
        rows = self.project()
        javascript = generator.serialize(rows)
        self.assertEqual(javascript.count("appleMusic:null"),
                         sum(1 for row in rows if row["appleMusic"] is None))
        self.assertEqual(javascript.count("spotify:null"),
                         sum(1 for row in rows if row["spotify"] is None))
        no_links = dict(rows[0], spotify=None, appleMusic=None)
        self.assertIn("spotify:null, appleMusic:null", generator.serialize([no_links]))
        with self.assertRaisesRegex(ValueError, "sixteen-field public schema"):
            generator.serialize([dict(rows[0], spotify="https://open.spotify.com/track/short")])
        with self.assertRaisesRegex(ValueError, "sixteen-field public schema"):
            generator.serialize([{k: v for k, v in rows[0].items() if k != "appleMusic"}])

    def test_checked_in_output_is_current_and_generation_is_deterministic(self):
        expected = generator.serialize(self.project())
        self.assertEqual(expected, (REPO / "js" / "music-data.js").read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.js"
            second = Path(directory) / "second.js"
            generator.generate(output=first, log_path=Path(directory) / "first.json")
            generator.generate(output=second, log_path=Path(directory) / "second.json")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual((Path(directory) / "first.json").read_bytes(),
                             generator.EXCLUSIONS_LOG.read_bytes())


class MandalaLoveTests(unittest.TestCase):
    """The three Mandala LOVE medleys, added on 2026-10-24 from the owner's express declaration (#93–#95)."""

    WORKS = {
        "93": ("a-puro-dolor-medley--mandala-love--2022", "A Puro Dolor - Medley", 2022, ["latin_tropical"],
               "https://music.apple.com/mx/album/a-puro-dolor-medley/1638433863?i=1638434043&uo=4"),
        "94": ("medley-cumbia-sabrosa--mandala-love--2023", "Medley Cumbia Sabrosa", 2023, ["latin_tropical"], None),
        "95": ("perdoname-rica-y-apretadita-no-me-trates-de-enganar-todavia--mandala-love--2023",
               "Perdóname / Rica y Apretadita / No Me Trates de Engañar / Todavía", 2023, ["latin_urban"], None),
    }

    @classmethod
    def setUpClass(cls):
        master = json.loads(generator.MASTER.read_text(encoding="utf-8"))
        selection = json.loads(generator.SELECTION.read_text(encoding="utf-8"))
        decisions = json.loads(generator.DECISIONS.read_text(encoding="utf-8"))
        manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        cls.rows, _ = generator.project_with_exclusions(master, selection, decisions, repo=REPO, manifest=manifest)
        cls.master = {w["id"]: w for w in master}

    def test_the_medleys_publish_the_declared_credits_and_nothing_more(self):
        by_preview = {row["preview"]: row for row in self.rows}
        for review_id, (work_id, title, year, genres, apple) in self.WORKS.items():
            with self.subTest(review_id=review_id):
                row = by_preview[f"{work_id}.mp3"]
                self.assertEqual((row["title"], row["artist"], row["artists"], row["year"], row["releaseType"]),
                                 (title, "Mandala LOVE", ["Mandala LOVE"], year, "Single"))
                self.assertEqual(row["role"], "Producer")
                self.assertEqual(row["roles"], ["Producer", "Arranger", "Music Director", "Keyboards", "Audio Editing Engineer"])
                # No composition, authorship or mixing credit is attributed.
                self.assertFalse({"Songwriter", "Co-writer", "Artist", "Recording Engineer"} & set(row["roles"]))
                self.assertEqual((row["genres"], row["moods"]), (genres, ["groovy", "bright"]))
                self.assertEqual(row["spotify"], self.master[work_id]["spotify"]["url"])
                # Apple Music only where the catalogue has a verified URL; never deduced.
                self.assertEqual(row["appleMusic"], apple)
                self.assertEqual(row["artwork"], self.master[work_id]["artwork"]["web_file"].split("/")[-1])
                self.assertTrue((REPO / "assets" / "images" / row["artwork"]).is_file())

    def test_the_medleys_close_the_catalogue_after_the_previous_works(self):
        self.assertEqual(len(self.rows), 76)
        self.assertEqual([row["preview"] for row in self.rows[-3:]], [f"{w[0]}.mp3" for w in self.WORKS.values()])


class HiddenSongsTests(unittest.TestCase):
    """Songs the owner withdrew from /music/ without deleting their audio or metadata."""

    HIDDEN = {
        "60": "jesus-set-me-free--luis-guinea--2021",
        "61": "por-que-lloras--renata-isabel--2017",
        "62": "alguien-como-yo--segundo-piso--2014",
        "70": "super-heroe--edson-corona--2017",
        "19": "asi-habla-el-amor--luis-guinea",
        "31": "promesas-decepciones-cover--luis-guinea",
        # English version only (2026-10-21); the Spanish «Tóxica» stays published.
        "65": "toxic--isabella-macias--2018",
    }
    HIDDEN_PREVIEWS = {f"{work_id}.mp3" for work_id in HIDDEN.values()}

    @classmethod
    def setUpClass(cls):
        cls.master = json.loads(generator.MASTER.read_text(encoding="utf-8"))
        cls.selection = json.loads(generator.SELECTION.read_text(encoding="utf-8"))
        cls.decisions = json.loads(generator.DECISIONS.read_text(encoding="utf-8"))
        cls.manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        cls.rows, cls.exclusions = generator.project_with_exclusions(
            cls.master, cls.selection, cls.decisions, repo=REPO, manifest=cls.manifest)
        unhidden = {**cls.selection, "entries": [{"review_id": e["review_id"]} for e in cls.selection["entries"]]}
        cls.all_rows = generator.project(cls.master, unhidden, cls.decisions, repo=REPO, manifest=cls.manifest)

    def test_the_hidden_songs_are_flagged_hidden_and_kept_in_the_selection(self):
        self.assertEqual(generator.hidden_review_ids(self.selection), set(self.HIDDEN))
        verified = {e["review_id"]: e for e in self.manifest["entries"] if e["status"] == "verified"}
        for review_id, work_id in self.HIDDEN.items():
            # Mapping, verified preview and the preview file itself are preserved.
            self.assertEqual(verified[review_id]["work_id"], work_id)
            self.assertTrue((REPO / verified[review_id]["preview"]).is_file())

    def test_hidden_songs_are_not_published_and_are_logged(self):
        self.assertFalse({row["preview"] for row in self.rows} & self.HIDDEN_PREVIEWS)
        javascript = (REPO / "js" / "music-data.js").read_text(encoding="utf-8")
        for name in self.HIDDEN_PREVIEWS:
            self.assertNotIn(name, javascript)
        for title in ("Jesus, Set Me Free", "¿Por Qué Lloras?", "Alguien Como Yo", "Súper Héroe",
                      "Así Habla El Amor", "Promesas Decepciones - Cover"):
            self.assertNotIn(f"title:'{title}'", javascript)
        logged = {item["review_id"]: item for item in self.exclusions if item["reason"] == "hidden_by_owner"}
        self.assertEqual({k: v["work_id"] for k, v in logged.items()}, self.HIDDEN)
        log = json.loads(generator.EXCLUSIONS_LOG.read_text(encoding="utf-8"))
        self.assertFalse(set(log["published"]) & set(self.HIDDEN))

    def test_the_rest_of_the_catalogue_keeps_its_content_and_order(self):
        expected = [row for row in self.all_rows if row["preview"] not in self.HIDDEN_PREVIEWS]
        self.assertEqual(self.rows, expected)
        self.assertEqual(len(self.all_rows) - len(self.rows), len(self.HIDDEN))

    def test_removing_the_flag_publishes_the_song_again(self):
        self.assertTrue(self.HIDDEN_PREVIEWS <= {row["preview"] for row in self.all_rows})

    def test_hidden_must_be_true_when_present(self):
        selection = json.loads(json.dumps(self.selection))
        selection["entries"][0]["hidden"] = False
        with self.assertRaisesRegex(ValueError, "hidden must be true"):
            generator.project(self.master, selection, self.decisions, repo=REPO, manifest=self.manifest)


if __name__ == "__main__":
    unittest.main()
