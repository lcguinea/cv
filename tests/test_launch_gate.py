#!/usr/bin/env python3
"""The launch gate: the class plans cannot be generated for publication until the launch checklist is complete and
signed (tools/launch_gate.py, docs/lanzamiento/CHECKLIST-LANZAMIENTO.md). Run: python3 -m unittest tests/test_launch_gate.py"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import launch_gate  # noqa: E402


class LaunchGate(unittest.TestCase):
    def unsigned(self):
        """The checklist as it was before Luis signed it: every box open, no signature."""
        text = re.sub(r"^- \[[x~]\]", "- [ ]", launch_gate.CHECKLIST.read_text(encoding="utf-8"), flags=re.M)
        text = re.sub(r" Dispensado\b.*$", "", text, flags=re.M)  # the real waiver notes would hide a missing reason
        return re.sub(r"^Autorizado por:.*$", "Autorizado por: ______________________ Fecha: __________", text, flags=re.M)

    def test_unsigned_checklist_blocks_the_launch(self):
        missing = launch_gate.check(self.unsigned())
        self.assertTrue(any(m.startswith("A1 ") for m in missing))
        self.assertTrue(any("Autorizado por" in m for m in missing))

    def test_complete_and_signed_checklist_passes(self):
        text = self.unsigned().replace("- [ ]", "- [x]")
        self.assertTrue(launch_gate.check(text))  # ticked but not signed
        signed = re.sub(r"Autorizado por: _+ Fecha: _+", "Autorizado por: Luis Guinea Fecha: 2027-01-15", text)
        self.assertEqual(launch_gate.check(signed), [])

    def test_current_checklist_is_signed(self):
        self.assertEqual(launch_gate.check(), [])

    def test_waivers_are_accepted_only_with_a_reason_and_always_listed(self):
        signed = re.sub(r"Autorizado por: _+ Fecha: _+", "Autorizado por: Luis Guinea Fecha: 2027-01-15",
                        self.unsigned().replace("- [ ]", "- [x]"))
        first = next(l for l in signed.splitlines() if l.startswith("- [x] L1 "))
        waived = signed.replace(first, first.replace("- [x]", "- [~]") + " Dispensado por Luis: lanza sin revisión jurídica.")
        self.assertEqual(launch_gate.check(waived), [])
        self.assertEqual(len(launch_gate.waivers(waived)), 1)
        self.assertEqual(launch_gate.waivers(signed), [])
        self.assertTrue(launch_gate.check(signed.replace(first, first.replace("- [x]", "- [~]"))))  # no reason

    def test_the_authorisation_cannot_be_waived(self):
        signed = re.sub(r"Autorizado por: _+ Fecha: _+", "Autorizado por: Luis Guinea Fecha: 2027-01-15",
                        self.unsigned().replace("- [ ]", "- [x]"))
        a1 = next(l for l in signed.splitlines() if l.startswith("- [x] A1 "))
        self.assertTrue(launch_gate.check(signed.replace(a1, a1.replace("- [x]", "- [~]") + " Dispensado por Luis: sin más.")))

    def test_removing_items_does_not_open_the_gate(self):
        self.assertTrue(launch_gate.check("Autorizado por: Alguien Fecha: 2027-01-15\n- [x] A1 ok\n"))

    def test_build_refuses_to_publish_the_plans_without_it(self):
        code = ("import sys; sys.path.insert(0,'tools'); import formacion_content as C; "
                "import launch_gate as G; G.check=lambda text=None: ['A1 sin firmar']; "
                "C.SUBSCRIPTIONS={'published': True, 'endpoint': ''}; import build_formacion as B; B.TREE=B.build_tree(); B.outputs()")
        run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("LAUNCH GATE", run.stderr + run.stdout)

    def test_preview_is_not_blocked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            run = subprocess.run([sys.executable, "tools/build_formacion.py", "--preview", "http://127.0.0.1:8792/exec", "--out", d],
                                 cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
