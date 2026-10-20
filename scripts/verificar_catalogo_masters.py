#!/usr/bin/env python3
"""Verifica el estado de la integración del ZIP de masters: ficha de pendientes completa, nada
pendiente publicado, seis ocultas intactas y ningún audio versionado fuera de previews."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PENDIENTES = ["Cómo Decirte", "Jinee Jinee", "1000 Días", "En El Momento Justo", "Solo Esta Noche",
              "Tonto Enamorado", "Allí Estás", "El Sembrador", "Gracias Por Todo",
              "Hasta el Final de mis Días", "Juntos Somos Imparables"]
NUEVAS = PENDIENTES[2:]
OCULTAS = {"60", "61", "62", "70", "19", "31"}
errores = []

doc = (REPO / "METADATOS-PENDIENTES-CATALOGO.md").read_text(encoding="utf-8")
for titulo in PENDIENTES:
    if f"### " not in doc or titulo not in doc:
        errores.append(f"ficha ausente: {titulo}")

data = (REPO / "js/music-data.js").read_text(encoding="utf-8")
for titulo in NUEVAS:
    if re.search(r"title:\s*['\"]%s['\"]" % re.escape(titulo), data):
        errores.append(f"obra pendiente publicada: {titulo}")
ids = re.findall(r'\bid:\s*"([^"]+)"', data)
if len(ids) != len(set(ids)):
    errores.append("ids duplicados en music-data.js")

sel = json.loads((REPO / "data/music-catalog/public_music_selection.json").read_text(encoding="utf-8"))
ocultas = {e["review_id"] for e in sel["entries"] if e.get("hidden")}
if ocultas != OCULTAS:
    errores.append(f"ocultas cambiadas: {sorted(ocultas)}")

tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
for f in tracked:
    if f.lower().endswith((".wav", ".flac", ".aif", ".aiff", ".m4a")):
        errores.append(f"audio versionado: {f}")

print("\n".join(errores) or "OK: catálogo coherente con la ficha de pendientes")
sys.exit(1 if errores else 0)
