#!/usr/bin/env python3
"""Launch gate for the class subscriptions: reads docs/lanzamiento/CHECKLIST-LANZAMIENTO.md.

The plans section can only be generated for publication (SUBSCRIPTIONS["published"] = True in
tools/formacion_content.py) when every checkbox is ticked and the final authorisation line carries a name and a date.

Two closed states, kept apart on purpose:
    - [x]  done and verified (the note says how).
    - [~]  WAIVED by Luis: not done, he decided to launch anyway. The line must contain "Dispensado" and the reason.
           The gate accepts it but always lists it, so a waiver is never reported as a verification. A1 (the launch
           authorisation itself) can never be waived.
tools/build_formacion.py calls check() and stops otherwise. --preview builds are not affected.

    python3 tools/launch_gate.py        prints what is missing; exit 1 if anything is
"""
import re
import sys
from pathlib import Path

CHECKLIST = Path(__file__).resolve().parent.parent / "docs" / "lanzamiento" / "CHECKLIST-LANZAMIENTO.md"
ITEM = re.compile(r"^- \[( |x|X|~)\] ([A-Z]\d+) (.+)$")
SIGNED = re.compile(r"^Autorizado por: *(?!_)(\S.*?) +Fecha: *(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\s*$")


def check(text=None):
    """List of what is missing (empty when the launch is authorised)."""
    text = CHECKLIST.read_text(encoding="utf-8") if text is None else text
    items, missing = 0, []
    signed = False
    for line in text.splitlines():
        m = ITEM.match(line.strip())
        if m:
            items += 1
            if m.group(1) == " ":
                missing.append(f"{m.group(2)} {m.group(3)}")
            elif m.group(1) == "~" and (m.group(2) == "A1" or not re.search(r"Dispensado\b.{10,}", m.group(3))):
                missing.append(f"{m.group(2)}: una dispensa necesita «Dispensado» y el motivo; A1 no se puede dispensar")
        elif SIGNED.match(line.strip()):
            signed = True
    if items < 20:
        missing.append("checklist incompleto o alterado: se esperaban al menos 20 casillas")
    if not signed:
        missing.append("falta la línea «Autorizado por: <nombre> Fecha: <aaaa-mm-dd>»")
    return missing


def waivers(text=None):
    """Items Luis waived ("- [~]"): printed every time, never counted as verified."""
    text = CHECKLIST.read_text(encoding="utf-8") if text is None else text
    found = (ITEM.match(line.strip()) for line in text.splitlines())
    return [f"{m.group(2)} {m.group(3)}" for m in found if m and m.group(1) == "~"]


def main():
    missing = check()
    if missing:
        print("LANZAMIENTO NO AUTORIZADO. Falta:")
        for m in missing:
            print("  -", m)
        return 1
    waived = waivers()
    print(f"Checklist completo y firmado ({len(waived)} requisitos dispensados por Luis, no verificados):")
    for w in waived:
        print("  ~", w[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
