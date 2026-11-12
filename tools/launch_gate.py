#!/usr/bin/env python3
"""Launch gate for the class subscriptions: reads docs/lanzamiento/CHECKLIST-LANZAMIENTO.md.

The plans section can only be generated for publication (SUBSCRIPTIONS["published"] = True in
tools/formacion_content.py) when every checkbox is ticked and the final authorisation line carries a name and a date.
tools/build_formacion.py calls check() and stops otherwise. --preview builds are not affected.

    python3 tools/launch_gate.py        prints what is missing; exit 1 if anything is
"""
import re
import sys
from pathlib import Path

CHECKLIST = Path(__file__).resolve().parent.parent / "docs" / "lanzamiento" / "CHECKLIST-LANZAMIENTO.md"
ITEM = re.compile(r"^- \[( |x|X)\] ([A-Z]\d+) (.+)$")
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
        elif SIGNED.match(line.strip()):
            signed = True
    if items < 20:
        missing.append("checklist incompleto o alterado: se esperaban al menos 20 casillas")
    if not signed:
        missing.append("falta la línea «Autorizado por: <nombre> Fecha: <aaaa-mm-dd>»")
    return missing


def main():
    missing = check()
    if missing:
        print("LANZAMIENTO NO AUTORIZADO. Falta:")
        for m in missing:
            print("  -", m)
        return 1
    print("Checklist completo y firmado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
