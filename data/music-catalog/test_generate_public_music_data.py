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

    def test_projection_uses_only_the_explicit_public_schema(self):
        rows = self.project()

        # Historical projection had 7 works; the six newly confirmed works make 13.
        self.assertEqual(len(rows), 13)
        self.assertEqual(
            set(rows[0]),
            {"title", "artist", "role", "artwork", "releaseType", "year", "roles", "preview"},
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
            },
        )
        self.assertEqual({row["role"] for row in rows}, {"Artist", "Producer", "Composer"})
        self.assertTrue(all(
            row["role"] in row["roles"]
            or (row["role"] == "Composer" and "Songwriter" in row["roles"])
            for row in rows
        ))
        self.assertEqual(
            [row["title"] for row in rows],
            [
                "Adiós Amor (Versión Bolero)",
                "Hasta Que Lleguemos Al Mar",
                "Hace Tanto Tiempo",
                "Blue Moon",
                "Volver a Verte",
                "Cómo Decirte",
                "Nuestro Hogar",
                "12 Meses",
                "La Bamba",
                "A Escondidas",
                "Lo Que Queda de Mí",
                "Abrazo Imaginario",
                "Shape of You - Acoustic",
            ],
        )

    def test_new_human_credit_decisions_project_exact_facets_and_roles(self):
        rows = {row["title"]: row for row in self.project()}

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
            "spotify",
            "apple_music",
            "isrc",
            "provenance",
            "conflict",
            "catalog_link",
            "vocal_performer",
            "recording_engineer",
        ):
            self.assertNotIn(forbidden, javascript)
        # `preview` contains the substring "review"; review ids/keys must still be absent.
        self.assertNotRegex(javascript, r"\breview")

        role_pattern = re.compile(
            r"title:\s*'((?:[^'\\]|\\.)*)',\s*"
            r"artist:\s*'((?:[^'\\]|\\.)*)',\s*"
            r"role:\s*'((?:[^'\\]|\\.)*)'"
        )
        self.assertEqual(len(role_pattern.findall(javascript)), len(rows))

    def test_preview_is_published_only_for_verified_manifest_entries(self):
        rows = {row["title"]: row["preview"] for row in self.project()}

        self.assertEqual(
            rows,
            {
                "Adiós Amor (Versión Bolero)": None,
                "Hasta Que Lleguemos Al Mar": "hasta-que-lleguemos-al-mar--luis-guinea--2024.mp3",
                "Hace Tanto Tiempo": "hace-tanto-tiempo--luis-guinea--2021.mp3",
                "Blue Moon": None,
                "Volver a Verte": "volver-a-verte--luis-guinea--2020.mp3",
                "Cómo Decirte": "como-decirte--luis-guinea--2022.mp3",
                "Nuestro Hogar": "nuestro-hogar--luis-guinea--2022.mp3",
                "12 Meses": "12-meses--rogelio-edel--2022.mp3",
                "La Bamba": "la-bamba--rogelio-edel--2022.mp3",
                "A Escondidas": None,
                "Lo Que Queda de Mí": None,
                "Abrazo Imaginario": "abrazo-imaginario--ricardo-bojalil--2022.mp3",
                "Shape of You - Acoustic": None,
            },
        )

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

    def test_projection_rejects_a_declared_preview_that_was_not_generated(self):
        manifest = json.loads(generator.PREVIEW_MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            fake_repo = Path(directory)
            for row in self.master:
                artwork = (row.get("artwork") or {}).get("web_file")
                if artwork:
                    target = fake_repo / artwork
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
            with self.assertRaisesRegex(ValueError, "preview .* does not exist"):
                generator.project(
                    self.master, self.selection, self.decisions,
                    repo=fake_repo, manifest=manifest,
                )

    def test_serialized_preview_never_exposes_private_audio_details(self):
        javascript = generator.serialize(self.project())

        self.assertEqual(javascript.count("preview:null"), 5)
        self.assertEqual(len(re.findall(r"preview:'[a-z0-9-]+\.mp3'", javascript)), 8)
        for forbidden in ("source", "sha256", "Productor", "Cantautor", "MixV1", "evidence"):
            self.assertNotIn(forbidden, javascript)
        row = dict(self.project()[0], preview="../secret/master.mp3")
        with self.assertRaisesRegex(ValueError, "public schema"):
            generator.serialize([row])

    def test_checked_in_output_is_current_and_generation_is_deterministic(self):
        expected = generator.serialize(self.project())
        self.assertEqual(expected, (REPO / "js" / "music-data.js").read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.js"
            second = Path(directory) / "second.js"
            generator.generate(output=first)
            generator.generate(output=second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
