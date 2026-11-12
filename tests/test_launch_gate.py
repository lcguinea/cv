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
    def test_current_checklist_blocks_the_launch(self):
        missing = launch_gate.check()
        self.assertTrue(any(m.startswith("A1 ") for m in missing))
        self.assertTrue(any("Autorizado por" in m for m in missing))

    def test_complete_and_signed_checklist_passes(self):
        text = launch_gate.CHECKLIST.read_text(encoding="utf-8").replace("- [ ]", "- [x]")
        self.assertTrue(launch_gate.check(text))  # ticked but not signed
        signed = re.sub(r"Autorizado por: _+ Fecha: _+", "Autorizado por: Luis Guinea Fecha: 2027-01-15", text)
        self.assertEqual(launch_gate.check(signed), [])

    def test_removing_items_does_not_open_the_gate(self):
        self.assertTrue(launch_gate.check("Autorizado por: Alguien Fecha: 2027-01-15\n- [x] A1 ok\n"))

    def test_build_refuses_to_publish_the_plans_without_it(self):
        code = ("import sys; sys.path.insert(0,'tools'); import formacion_content as C; "
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
