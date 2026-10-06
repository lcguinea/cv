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
    EXCLUDED = {
        "33": "adios-amor-version-bolero--luis-guinea--2020",
        "34": "blue-moon--luis-guinea--2015",
        "36": "a-escondidas--isabella-macias--2018",
        "37": "lo-que-queda-de-mi--escala-de-grises--2016",
        "38": "shape-of-you-acoustic--segundo-piso--2017",
    }

    def test_projection_uses_only_the_explicit_public_schema(self):
        rows = self.project()

        # The selection has 21 works; only the 16 with a valid preview are published.
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(self.project_all()), 21)
        self.assertEqual(
            set(rows[0]),
            {"title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview",
             "spotify", "appleMusic"},
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
            },
        )
        # Blue Moon (the only Composer facet) has no authorized preview, so it is excluded.
        self.assertEqual({row["role"] for row in rows}, {"Artist", "Producer"})
        self.assertTrue(all(
            row["role"] in row["roles"]
            or (row["role"] == "Composer" and "Songwriter" in row["roles"])
            for row in rows
        ))
        self.assertEqual([row["title"] for row in rows], self.PUBLISHED)

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

    def test_projection_rejects_unreleased_or_incomplete_works(self):
        master = json.loads(json.dumps(self.master))
        chosen_id = "hasta-que-lleguemos-al-mar--luis-guinea--2024"
        work = next(item for item in master if item["id"] == chosen_id)
        work["release"]["status"] = "unreleased"

        with self.assertRaisesRegex(ValueError, "not a released work"):
            self.project(master=master)

    def test_projection_rejects_an_open_human_case(self):
        selection = json.loads(json.dumps(self.selection))
        selection["entries"][0] = {"review_id": "16"}

        with self.assertRaisesRegex(ValueError, "is not mapped"):
            self.project(selection=selection)

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
        self.assertEqual(javascript.count("spotify"), 2 * len(rows))
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

        # Two published works share the title "Volver a Verte" (Luis Guinea / Ana Guinea).
        self.assertEqual(
            [(row["title"], row["preview"]) for row in rows],
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
        self.assertEqual({item["review_id"]: item["work_id"] for item in exclusions}, self.EXCLUDED)
        self.assertEqual({item["reason"] for item in exclusions}, {"no_authorized_preview"})
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
            for row in self.master:
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
            self.assertEqual(len(reasons), 21)
            self.assertEqual({r for i, r in reasons.items() if i not in self.EXCLUDED}, {"preview_missing"})

    def test_serialized_preview_never_exposes_private_audio_details(self):
        javascript = generator.serialize(self.project())

        self.assertEqual(javascript.count("preview:null"), 0)
        self.assertEqual(len(re.findall(r"preview:'[a-z0-9-]+\.mp3'", javascript)), 16)
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
    }
    WITHOUT_APPLE = {"Allá", "Anoche Me Enamoré", "Eres Veneno"}

    def test_streaming_links_come_from_the_catalogue_or_the_certified_additions_only(self):
        rows = self.project()
        works = {(row["title"], row["artist"]): row for row in rows}
        for row in rows:
            with self.subTest(title=row["title"], artist=row["artist"]):
                work = next(w for w in self.master if w["title"] == row["title"]
                            and ", ".join(w["artists"]) == row["artist"])
                self.assertEqual(row["spotify"], work["spotify"]["url"])
                registered = work["apple_music"]["url"]
                expected = registered or self.CERTIFIED_APPLE.get(row["title"])
                self.assertEqual(row["appleMusic"], expected)
        self.assertTrue(all(row["spotify"] for row in rows))
        self.assertEqual(sum(1 for row in rows if row["appleMusic"]), 12)
        missing = {(row["title"], row["artist"]) for row in rows if row["appleMusic"] is None}
        self.assertEqual(missing, {(t, "Rogelio Edel") for t in self.WITHOUT_APPLE}
                         | {("Volver a Verte", "Luis Guinea")})
        # Cómo Decirte keeps its registered URL (track 1646476110, the certified one's track).
        self.assertIn("i=1646476110", works[("Cómo Decirte", "Luis Guinea, Pablo Delgado")]["appleMusic"])

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
        self.assertEqual(javascript.count("appleMusic:null"), 4)
        self.assertEqual(javascript.count("spotify:null"), 0)
        no_links = dict(rows[0], spotify=None, appleMusic=None)
        self.assertIn("spotify:null, appleMusic:null", generator.serialize([no_links]))
        with self.assertRaisesRegex(ValueError, "ten-field public schema"):
            generator.serialize([dict(rows[0], spotify="https://open.spotify.com/track/short")])
        with self.assertRaisesRegex(ValueError, "ten-field public schema"):
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


if __name__ == "__main__":
    unittest.main()
