#!/usr/bin/env python3
"""Focused tests for the /music/ preview manifest, the preview generator and the #02 audio_ref fix."""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import generate_music_previews as previews  # noqa: E402

# The sixteen original previews (2026-10-05) and the 29 windows the owner approved on 2026-10-13.
VERIFIED = {"25", "02", "04", "35", "03", "05", "11", "01", "06", "07", "08", "09", "10", "13", "14", "15",
            "12", "18", "20", "21", "16", "41", "42", "43", "19", "22", "23", "26", "28", "30",
            "31", "44", "45", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55", "56", "57",
            # Spotify-folder recordings, main windows approved on 2026-10-13 (#32, #61 and #62 with a
            # master that differs from the commercial release, authorized by the owner).
            "32", "36", "58", "60", "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",
            # Owner-designated masters with their windows approved on 2026-10-13.
            "59", "71",
            # Unreleased co-writes from Coautorías, main windows approved on 2026-10-13.
            "73", "74", "75",
            # Masters of the official ZIP, windows approved on 2026-10-20 (approved-preview-window-v3).
            "76", "77", "78", "79", "80", "81", "82", "83", "84",
            # Abe Rapa's Best of Me EP, Di Que Sí and Dime, windows approved on 2026-10-24
            # (approved-preview-window-v4).
            "85", "86", "87", "88", "89", "91", "92",
            # Mandala LOVE medleys: windows chosen automatically with the owner's prior express authorization
            # of 2026-10-24 (authorized-automatic-window-v5).
            "93", "94", "95"}
# Selected works whose audio is not in One Page Luis Guinea/audios (no source to cut).
BLOCKED_WITHOUT_AUDIO = {"33", "34", "37", "38"}
# No associated source waits for a window approval.
PENDING_WINDOW_APPROVAL = set()
# Window approved, but the release status is still provisional (not publishable yet).
PENDING_RELEASE_CONFIRMATION = set()
# Window approved on 2026-10-24, then withdrawn from the public selection by the owner (same day).
WITHDRAWN_AFTER_APPROVAL = {"90"}
BLOCKED = BLOCKED_WITHOUT_AUDIO | PENDING_WINDOW_APPROVAL | PENDING_RELEASE_CONFIRMATION
# Owner-approved chorus intervals (s) and the encoded end where an edge was adjusted.
APPROVED = {
    "25": (106.5, 145.0, 145.0), "02": (57.5, 91.0, 91.0), "04": (67.0, 107.5, 107.5),
    "35": (98.0, 141.0, 141.0), "03": (69.5, 114.5, 114.4), "05": (86.0, 129.5, 129.5),
    "11": (130.5, 170.5, 170.5), "01": (168.0, 205.0, 205.0), "06": (170.0, 213.5, 213.5),
    "07": (75.0, 115.0, 115.0), "08": (126.5, 164.0, 164.0), "09": (72.0, 106.0, 106.0),
    "10": (120.0, 165.0, 164.9), "13": (47.0, 83.0, 83.0), "14": (44.0, 83.0, 83.0),
    "15": (70.3, 111.0, 111.0),
}
# Main proposals approved on 2026-10-13 for the Spotify-folder recordings (approved-preview-window-v2).
APPROVED_V2 = {
    "36": (91.0, 132.0, 132.0), "58": (138.5, 178.5, 178.5), "60": (91.5, 129.0, 129.0),
    "63": (156.5, 195.5, 195.5), "64": (98.0, 138.0, 138.0), "65": (116.5, 155.5, 155.5),
    "66": (58.5, 95.5, 95.5), "67": (140.5, 185.0, 185.0), "68": (101.5, 144.5, 144.5),
    "69": (116.0, 151.0, 151.0), "70": (151.5, 191.5, 191.5), "32": (148.5, 185.5, 185.5),
    "61": (108.0, 142.0, 142.0), "62": (114.0, 153.0, 153.0),
    # Si Estás De Paso: section equivalent to the window approved on the wrong file; Te Esperé: alternative.
    "59": (75.0, 116.6, 116.6), "71": (97.0, 132.0, 132.0),
    "73": (46.0, 90.0, 90.0), "74": (76.5, 116.0, 116.0), "75": (78.0, 117.5, 117.5),
}
# Windows the owner chose on 2026-10-20 between two loudness-based proposals (approved-preview-window-v3).
APPROVED_V3 = {
    "76": (74.8, 114.8, 114.8), "77": (161.5, 201.5, 201.5), "78": (200.4, 240.4, 240.4),
    "79": (175.4, 215.4, 215.4), "80": (199.6, 239.6, 239.6), "81": (24.7, 64.7, 64.7),
    "82": (47.6, 87.6, 87.6), "83": (48.9, 88.9, 88.9), "84": (34.5, 74.5, 74.5),
}
# Windows the owner chose on 2026-10-24 between two analysed proposals (approved-preview-window-v4).
APPROVED_V4 = {
    "85": (25.24, 65.84, 65.84), "86": (172.71, 214.32, 214.32), "87": (22.15, 60.6, 60.6),
    "88": (104.61, 145.08, 145.08), "89": (143.27, 183.04, 183.04),
    "91": (126.13, 166.37, 166.37), "92": (168.81, 212.39, 212.39),
}
# Windows chosen automatically on 2026-10-24 under the owner's prior authorization (authorized-automatic-window-v5).
APPROVED_V5 = {
    "93": (133.97, 177.88, 177.88), "94": (228.7, 273.36, 273.36), "95": (140.06, 184.9, 184.9),
}
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class PreviewManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load(previews.MANIFEST)
        self.selection = load(previews.SELECTION)
        self.decisions = load(previews.DECISIONS)

    def validate(self, manifest=None):
        return previews.validate_manifest(
            manifest or self.manifest, self.selection, self.decisions
        )

    def entry(self, manifest, review_id):
        return next(e for e in manifest["entries"] if e["review_id"] == review_id)

    def test_manifest_has_one_entry_per_public_work(self):
        entries = self.validate()

        self.assertEqual(
            [e["review_id"] for e in entries],
            [e["review_id"] for e in self.selection["entries"]],
        )
        self.assertEqual({e["review_id"] for e in entries if e["status"] == "verified"}, VERIFIED)
        self.assertEqual({e["review_id"] for e in entries if e["status"] == "blocked"}, BLOCKED)
        for entry in entries:
            if entry["status"] == "verified":
                self.assertEqual(entry["preview"], f"assets/audio/previews/{entry['work_id']}.mp3")
                self.assertRegex(entry["preview_sha256"], r"^[0-9a-f]{64}$")
                self.assertLessEqual(entry["window"]["duration_s"], previews.MAX_PREVIEW_S)
            else:
                self.assertIsNone(entry["preview"])
                self.assertIsNone(entry["window"])
                self.assertTrue(entry["evidence_needed"])
                # A source awaiting its window or its release status is already associated and pinned by sha256.
                self.assertEqual(entry["source"] is not None,
                                 entry["review_id"] in PENDING_WINDOW_APPROVAL | PENDING_RELEASE_CONFIRMATION)

    def test_authorized_sources_are_the_human_decisions(self):
        entries = {e["review_id"]: e for e in self.validate()}

        self.assertEqual(
            entries["02"]["source"], "One Page Luis Guinea/audios/Cantautor/Hace Tanto Tiempo.mp3"
        )
        self.assertEqual(
            entries["35"]["source"],
            "One Page Luis Guinea/audios/Productor/Pablo Delgado/PDelgado_Cómo Decirte_MixV1_.mp3",
        )
        self.assertEqual(entries["25"]["association"]["basis"], "objective_evidence")
        # A duration-only match contradicted by title/artist must never become #33's source.
        self.assertIsNone(entries["33"]["source"])
        # Owner-designated masters (2026-10-13) replace the wrong Spotify-folder files.
        self.assertEqual(entries["59"]["source"],
                         "One Page Luis Guinea/audios/Productor/Si Estás de Paso (masterizada).mp3")
        self.assertEqual(entries["71"]["source"],
                         "One Page Luis Guinea/audios/Productor/Ana Guinea/Te Esperé (Master).mp3")
        # Previews cut from a master other than the commercial one say so in their evidence.
        for review_id in ("32", "59", "61", "62", "71"):
            with self.subTest(review_id=review_id):
                association = entries[review_id]["association"]
                self.assertEqual(association["basis"], "human_authorization")
                self.assertTrue(any(e.startswith("Master del preview:") and "Master comercial: ISRC" in e
                                    for e in association["evidence"]))

    def test_manifest_rejects_a_work_id_that_differs_from_the_human_mapping(self):
        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "02")["work_id"] = "llegue-muy-tarde--valeria-ferro--2023"

        with self.assertRaisesRegex(ValueError, "human mapping"):
            self.validate(manifest)

    def test_manifest_rejects_missing_or_extra_works(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entries"].pop()
        with self.assertRaisesRegex(ValueError, "exactly one entry"):
            self.validate(manifest)

        manifest = copy.deepcopy(self.manifest)
        manifest["entries"].append(copy.deepcopy(manifest["entries"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.validate(manifest)

    def test_manifest_rejects_unsafe_sources_and_destinations(self):
        cases = {
            "source": [
                "/Users/someone/One Page Luis Guinea/audios/Cantautor/Hace Tanto Tiempo.mp3",
                "One Page Luis Guinea/audios/../Hace Tanto Tiempo.mp3",
                "assets/audio/previews/hace-tanto-tiempo--luis-guinea--2021.mp3",
                "One Page Luis Guinea/audios/Cantautor/notes.txt",
            ],
            "preview": [
                "assets/audio/previews/../hace-tanto-tiempo--luis-guinea--2021.mp3",
                "assets/audio/hace-tanto-tiempo--luis-guinea--2021.mp3",
                "assets/audio/previews/Hace Tanto Tiempo.mp3",
                "assets/audio/previews/hace-tanto-tiempo--luis-guinea--2021.wav",
            ],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    manifest = copy.deepcopy(self.manifest)
                    self.entry(manifest, "02")[field] = value
                    with self.assertRaises(ValueError):
                        self.validate(manifest)

    def test_manifest_rejects_reused_sources_and_unauthorized_associations(self):
        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "03")["source"] = self.entry(manifest, "02")["source"]
        with self.assertRaisesRegex(ValueError, "more than once"):
            self.validate(manifest)

        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "02")["association"] = {"basis": "duration_only", "evidence": ["x"]}
        with self.assertRaisesRegex(ValueError, "association"):
            self.validate(manifest)

    def test_blocked_entries_cannot_publish_a_preview(self):
        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "33")["preview"] = (
            "assets/audio/previews/adios-amor-version-bolero--luis-guinea--2020.mp3"
        )
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.validate(manifest)

    def test_manifest_rejects_a_window_over_45_seconds(self):
        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "04")["window"]["duration_s"] = 45.1

        with self.assertRaisesRegex(ValueError, "45"):
            self.validate(manifest)

    def test_manifest_uses_the_approved_chorus_windows(self):
        self.assertEqual(self.manifest["schema"], "music-preview-manifest-v2")
        self.assertEqual(self.manifest["policies"], previews.POLICIES)
        self.assertEqual(self.manifest["encoding"], previews.ENCODING)
        approved = [(r, w, "approved-chorus-window-v1") for r, w in APPROVED.items()]
        approved += [(r, w, "approved-preview-window-v2") for r, w in APPROVED_V2.items()]
        approved += [(r, w, "approved-preview-window-v3") for r, w in APPROVED_V3.items()]
        approved += [(r, w, "approved-preview-window-v4") for r, w in APPROVED_V4.items()]
        approved += [(r, w, "authorized-automatic-window-v5") for r, w in APPROVED_V5.items()]
        for review_id, (start, end, encoded_end), policy in approved:
            with self.subTest(review_id=review_id):
                entry = self.entry(self.manifest, review_id)
                window = entry["window"]
                self.assertEqual(entry["trim_policy"], policy)
                self.assertEqual(window["approved_s"], [start, end])
                self.assertEqual(window["start_s"], start)
                self.assertAlmostEqual(window["start_s"] + window["duration_s"], encoded_end, places=3)
                self.assertLessEqual(window["duration_s"], previews.MAX_PREVIEW_S)
                self.assertEqual(window["edge_adjustment"] is not None, encoded_end != end)

    def test_v3_windows_trace_to_the_owner_approval_in_the_human_case(self):
        cases = {c["review_id"]: c for c in self.decisions["classifications"]}
        for review_id in APPROVED_V3:
            with self.subTest(review_id=review_id):
                entry = self.entry(self.manifest, review_id)
                self.assertEqual(entry["association"]["basis"], "human_authorization")
                approval = [n for n in cases[review_id]["notes"]
                            if n.startswith("Ventana de preview aprobada por Luis Guinea el 2026-10-20")]
                self.assertEqual(len(approval), 1)
                self.assertIn(entry["source_sha256"], approval[0])
                self.assertIn(entry["preview_sha256"], approval[0])

    def test_v4_approvals_trace_to_the_owner_decision_in_the_human_case(self):
        cases = {c["review_id"]: c for c in self.decisions["classifications"]}
        for review_id in set(APPROVED_V4) | PENDING_RELEASE_CONFIRMATION:
            with self.subTest(review_id=review_id):
                entry = self.entry(self.manifest, review_id)
                self.assertEqual(entry["association"]["basis"], "human_authorization")
                approval = [n for n in cases[review_id]["notes"]
                            if n.startswith("Ventana de preview aprobada por Luis Guinea el 2026-10-24")]
                self.assertEqual(len(approval), 1)
                self.assertIn(entry["source_sha256"], approval[0])
                if review_id in APPROVED_V4:
                    self.assertIn(entry["preview_sha256"], approval[0])
                else:
                    # Approved but unpublished: the case says why, the manifest stays blocked.
                    self.assertIn("estado de publicación sigue provisional", approval[0])

    def test_v5_windows_trace_to_the_owner_authorization_and_the_published_drive_masters(self):
        cases = {c["review_id"]: c for c in self.decisions["classifications"]}
        drive = {"93": "180b4db7abf01f17de88cb30aacf2cdc715692596ce355d6fef72f8e09b89693",
                 "94": "054600df2d55cf9d36916dd3bce0e117f83938a8629a9cdb15851529ada9b8e1",
                 "95": "68e1acb3042439c394076bbde169098aaeba182a62740e303552ef1e317c7d9d"}
        for review_id in APPROVED_V5:
            with self.subTest(review_id=review_id):
                entry, case = self.entry(self.manifest, review_id), cases[review_id]
                # The masters published on Google Drive, never the local copies of Productor/Mandala Love.
                self.assertEqual(entry["source_sha256"], drive[review_id])
                self.assertTrue(entry["source"].startswith("One Page Luis Guinea/audios/Productor/Mandala LOVE (masters Drive)/"))
                self.assertEqual(entry["association"]["basis"], "human_authorization")
                window = [n for n in case["notes"] if n.startswith("Ventana de preview seleccionada automáticamente el 2026-10-24 "
                                                                  "con autorización expresa previa de Luis Guinea")]
                self.assertEqual(len(window), 1)
                self.assertIn(entry["source_sha256"], window[0])
                self.assertIn(entry["preview_sha256"], window[0])
                self.assertEqual(case["credits"], [{"name": "Luis Guinea", "roles": [
                    "producer", "arranger", "music_director", "keyboards", "audio_editing_engineer"]}])
                self.assertEqual(case["credits_decision"]["public_facet"], "Producer")

    def test_withdrawn_case_keeps_its_master_and_approval_record_but_is_not_selected(self):
        cases = {c["review_id"]: c for c in self.decisions["classifications"]}
        selected = {e["review_id"] for e in self.selection["entries"]}
        manifest_ids = {e["review_id"] for e in self.manifest["entries"]}
        for review_id in WITHDRAWN_AFTER_APPROVAL:
            with self.subTest(review_id=review_id):
                case = cases[review_id]
                self.assertIs(case["public_exclusion"], True)
                self.assertNotIn(review_id, selected)
                self.assertNotIn(review_id, manifest_ids)
                self.assertFalse((REPO / previews.OUTPUT_DIR / f"{case['catalog_link']['work_id']}.mp3").exists())
                self.assertTrue(any(n.startswith("Ventana de preview aprobada por Luis Guinea el 2026-10-24")
                                    for n in case["notes"]))
                if HAVE_FFMPEG:
                    master = REPO / "One Page Luis Guinea" / "audios" / "Productor" / "Abe Rapa" / case["reviewed_asset"]
                    self.assertTrue(master.is_file())

    def test_manifest_rejects_undocumented_or_excessive_edge_adjustments(self):
        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "03")["window"]["edge_adjustment"] = None
        with self.assertRaisesRegex(ValueError, "edge_adjustment"):
            self.validate(manifest)

        manifest = copy.deepcopy(self.manifest)
        self.entry(manifest, "04")["window"]["start_s"] = 65.9
        with self.assertRaisesRegex(ValueError, "approved edge"):
            self.validate(manifest)

    def test_manifest_publishes_no_absolute_path(self):
        text = previews.MANIFEST.read_text(encoding="utf-8")

        self.assertNotRegex(text, r"(?i)/Users/|[A-Z]:\\\\|GoogleDrive|@")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class PreviewEncodingTests(unittest.TestCase):
    """Encodes a synthetic tone, so these tests never need the private masters."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        source = self.repo / "One Page Luis Guinea" / "audios" / "Cantautor" / "Tono Público.mp3"
        source.parent.mkdir(parents=True)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=440:sample_rate=48000:duration=90", "-ac", "2",
             "-metadata", "title=Secret Master", "-c:a", "libmp3lame", "-b:a", "192k", str(source)],
            check=True,
        )
        self.source = source
        self.work_id = "tono-publico--luis-guinea--2020"
        self.entry = {
            "review_id": "99",
            "work_id": self.work_id,
            "status": "verified",
            "source": "One Page Luis Guinea/audios/Cantautor/Tono Público.mp3",
            "source_sha256": previews.sha256_file(source),
            "preview": f"assets/audio/previews/{self.work_id}.mp3",
            "preview_sha256": "0" * 64,
            "trim_policy": "approved-chorus-window-v1",
            "window": {
                "approved_s": [10.0, 54.5],
                "start_s": 10.0,
                "duration_s": 44.5,
                "edge_adjustment": None,
                "method": "synthetic-test",
                "justification": "Synthetic approved window.",
            },
            "association": {"basis": "objective_evidence", "evidence": ["synthetic"]},
        }
        self.manifest = {
            "schema": previews.MANIFEST_SCHEMA,
            "output_dir": "assets/audio/previews",
            "encoding": copy.deepcopy(previews.ENCODING),
            "policies": copy.deepcopy(previews.POLICIES),
            "entries": [self.entry],
        }
        self.selection = {"entries": [{"review_id": "99"}]}
        self.decisions = {"classifications": [{
            "review_id": "99",
            "catalog_link": {"status": "mapped", "work_id": self.work_id},
        }]}
        reference = self.repo / "reference.mp3"
        previews.encode(self.source, reference, self.entry)
        self.entry["preview_sha256"] = previews.sha256_file(reference)
        reference.unlink()

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, manifest=None):
        return previews.generate(
            manifest or self.manifest, self.selection, self.decisions, repo=self.repo
        )

    def test_generation_is_deterministic_short_mp3_without_metadata(self):
        source_bytes = self.source.read_bytes()
        [out] = self.generate()
        first = out.read_bytes()
        out.unlink()
        [out] = self.generate()

        self.assertEqual(out, self.repo / "assets" / "audio" / "previews" / f"{self.work_id}.mp3")
        self.assertEqual(out.read_bytes(), first)
        self.assertEqual(self.source.read_bytes(), source_bytes)
        info = previews.probe(out)
        self.assertEqual(info["format_name"], "mp3")
        self.assertEqual(info["codec_name"], "mp3")
        self.assertGreater(info["duration"], 40.0)
        self.assertLessEqual(info["duration"], previews.MAX_PREVIEW_S)
        self.assertEqual(info["tags"], {})
        self.assertNotIn(b"Secret Master", first)
        self.assertEqual([p.name for p in out.parent.iterdir()], [out.name])

    def test_rejects_a_preview_whose_hash_differs_from_the_manifest(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entries"][0]["preview_sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "preview sha256"):
            self.generate(manifest)

    def test_a_full_45_second_window_is_rejected_by_the_frame_walk(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entries"][0]["window"].update(approved_s=[10.0, 55.0], duration_s=45.0)

        with self.assertRaisesRegex(ValueError, "frame-walk duration"):
            self.generate(manifest)

    def test_rejects_a_source_whose_hash_changed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entries"][0]["source_sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "sha256"):
            self.generate(manifest)
        self.assertFalse((self.repo / "assets" / "audio" / "previews" / f"{self.work_id}.mp3").exists())

    def test_rejects_unexpected_files_in_the_public_preview_directory(self):
        stray = self.repo / "assets" / "audio" / "previews" / "full-master.mp3"
        stray.parent.mkdir(parents=True)
        stray.write_bytes(b"not a preview")

        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.generate()

    def test_rejects_a_source_shorter_than_the_selected_window(self):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
             "sine=frequency=440:duration=50", "-c:a", "libmp3lame", str(self.source)],
            check=True,
        )
        manifest = copy.deepcopy(self.manifest)
        manifest["entries"][0]["source_sha256"] = previews.sha256_file(self.source)

        with self.assertRaisesRegex(ValueError, "shorter|exceeds source duration"):
            self.generate(manifest)


class CatalogAudioRefCorrectionTests(unittest.TestCase):
    """#02: the wrong audio_ref is corrected declaratively by build_catalog.py."""

    WORK = "hace-tanto-tiempo--luis-guinea--2021"

    def test_master_uses_the_human_corrected_audio_ref(self):
        master = {w["id"]: w for w in load(HERE / "catalog_master.json")}
        corrections = load(HERE / "audio_ref_corrections.json")["corrections"]

        self.assertEqual(master[self.WORK]["audio_ref"], "Hace Tanto Tiempo.mp3")
        self.assertEqual(
            [(c["work_id"], c["source_value"], c["corrected_value"]) for c in corrections],
            [(self.WORK, "Llegue Muy Tarde.wav", "Hace Tanto Tiempo.mp3")],
        )

    # internal/ holds private provenance (absolute paths of the owner's machine) and is never
    # versioned, so this check only runs where build_catalog.py has produced it locally.
    @unittest.skipUnless((HERE / "internal" / "provenance.json").is_file(),
                         "internal/ is private local build output and is not versioned")
    def test_provenance_and_conflict_keep_the_original_value(self):
        prov = load(HERE / "internal" / "provenance.json")["works"][self.WORK]["fields"]["audio_ref"]
        conflicts = [
            c for c in load(HERE / "internal" / "conflicts.json")
            if c["work_id"] == self.WORK and c["field"] == "audio_ref"
        ]

        self.assertEqual(prov["value"], "Hace Tanto Tiempo.mp3")
        self.assertIn("Llegue Muy Tarde.wav", prov["original"][0]["value"])
        self.assertIn("audio_ref_corrections.json", prov["rule"])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "audio_ref_corregido_por_decision_humana")
        self.assertEqual(conflicts[0]["resolution"], "resuelto_humano")
        self.assertEqual(conflicts[0]["public_value"], "Hace Tanto Tiempo.mp3")
        self.assertEqual(prov["conflicts"], [conflicts[0]["conflict_id"]])


if __name__ == "__main__":
    unittest.main()
