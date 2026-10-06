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

VERIFIED = {"25", "02", "04", "35", "03", "05", "11", "01", "06", "07", "08", "09", "10", "13", "14", "15"}
BLOCKED = {"33", "34", "36", "37", "38"}
# Owner-approved chorus intervals (s) and the encoded end where an edge was adjusted.
APPROVED = {
    "25": (106.5, 145.0, 145.0), "02": (57.5, 91.0, 91.0), "04": (67.0, 107.5, 107.5),
    "35": (98.0, 141.0, 141.0), "03": (69.5, 114.5, 114.4), "05": (86.0, 129.5, 129.5),
    "11": (130.5, 170.5, 170.5), "01": (168.0, 205.0, 205.0), "06": (170.0, 213.5, 213.5),
    "07": (75.0, 115.0, 115.0), "08": (126.5, 164.0, 164.0), "09": (72.0, 106.0, 106.0),
    "10": (120.0, 165.0, 164.9), "13": (47.0, 83.0, 83.0), "14": (44.0, 83.0, 83.0),
    "15": (70.3, 111.0, 111.0),
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
                self.assertTrue(entry["evidence_needed"])

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
        for review_id, (start, end, encoded_end) in APPROVED.items():
            with self.subTest(review_id=review_id):
                entry = self.entry(self.manifest, review_id)
                window = entry["window"]
                self.assertEqual(entry["trim_policy"], "approved-chorus-window-v1")
                self.assertEqual(window["approved_s"], [start, end])
                self.assertEqual(window["start_s"], start)
                self.assertAlmostEqual(window["start_s"] + window["duration_s"], encoded_end, places=3)
                self.assertLessEqual(window["duration_s"], previews.MAX_PREVIEW_S)
                self.assertEqual(window["edge_adjustment"] is not None, encoded_end != end)

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
