#!/usr/bin/env python3
"""Grupo Botanas starts in January 2024 everywhere it is published, in English and Spanish.

Standard library only. Scans the site and canonical sources for "Grupo Botanas" and checks:
- CV_MASTER.md: the role is dated "Jan 2024 – Present" and the start-date open item is gone.
- cv.html and index.html: the Grupo Botanas entry carries an i18n date key whose English value
  says "Jan 2024" and whose Spanish value says "enero de 2024", with an English fallback and a
  machine-readable 2024-01 where the markup has a <time> element.
- No Grupo Botanas block anywhere declares a start year earlier than 2024.
Any new file that mentions Grupo Botanas must be added to CHECKS so it is verified too.

Run: python3 tests/test_grupo_botanas_start.py   ->   GRUPO_BOTANAS_OK
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".git", "One Page Luis Guinea", "estado", ".orchestrator", "__pycache__", "node_modules"}
TEXT_SUFFIXES = {".md", ".html", ".js", ".json", ".txt", ".csv"}
# Mission reports narrate the change itself (old and new dates); they are not published sources.
NARRATIVE = re.compile(r"(^|/)MISSION_REPORT_[0-9]+\.md$")
YEAR = re.compile(r"\b(19[0-9]{2}|20[0-9]{2})\b")
EN_START = "Jan 2024"
ES_START = "enero de 2024"

failures = []


def fail(message):
    failures.append(message)


def read(relative):
    return (REPO / relative).read_text(encoding="utf-8")


def earlier_years(text):
    return sorted({int(y) for y in YEAR.findall(text) if int(y) < 2024})


def language_blocks():
    source = read("js/strings.js")
    split = source.find("\n  es:")
    if split < 0:
        fail("js/strings.js: cannot find the es block")
        return {}, {}
    return source[:split], source[split:]


def i18n_value(block, path):
    """Value of section.key inside one language block of strings.js (single-quoted literal)."""
    section, key = path.split(".")
    match = re.search(r"\b" + re.escape(section) + r"\s*:\s*\{(.*?)\}\s*,?\s*\n", block, re.S)
    if not match:
        return None
    value = re.search(r"\b" + re.escape(key) + r"\s*:\s*'((?:[^'\\]|\\.)*)'", match.group(1))
    return value.group(1) if value else None


def check_bilingual_key(file, path):
    en, es = language_blocks()
    for lang, block, expected in (("en", en, EN_START), ("es", es, ES_START)):
        value = i18n_value(block, path)
        if value is None:
            fail(f"{file}: i18n key {path} is missing in {lang}")
            continue
        if expected not in value:
            fail(f"{file}: {lang} {path} = {value!r} does not start in {expected!r}")
        if earlier_years(value):
            fail(f"{file}: {lang} {path} = {value!r} declares an earlier year")


def botanas_element(html, tag):
    """The <tag ...>...</tag> element that contains Grupo Botanas."""
    for match in re.finditer(rf"<{tag}\b[^>]*>.*?</{tag}>", html, re.S):
        if "Grupo Botanas" in match.group(0):
            return match.group(0)
    return None


def check_cv_master(file):
    text = read(file)
    section = re.search(r"^### [^\n]*Grupo Botanas\n(.*?)(?=^### |^## |\Z)", text, re.S | re.M)
    if not section:
        fail(f"{file}: Grupo Botanas role section not found")
        return
    dates = re.search(r"^- dates:\s*(.+)$", section.group(1), re.M)
    if not dates or not re.match(r"Jan 2024\s*[–-]\s*Present\s*$", dates.group(1)):
        fail(f"{file}: Grupo Botanas dates must be 'Jan 2024 – Present', found {dates and dates.group(1)!r}")
    if earlier_years(section.group(1)):
        fail(f"{file}: Grupo Botanas section declares earlier years {earlier_years(section.group(1))}")
    if re.search(r"Start date for the current Grupo Botanas role", text):
        fail(f"{file}: the Grupo Botanas start date is still listed as an open item")
    for line in text.splitlines():
        if "Grupo Botanas" in line and earlier_years(line):
            fail(f"{file}: line declares an earlier year for Grupo Botanas: {line.strip()!r}")


def check_html(file, tag, date_tag, key):
    html = read(file)
    element = botanas_element(html, tag)
    if element is None:
        fail(f"{file}: no <{tag}> element contains Grupo Botanas")
        return
    date = re.search(rf"<{date_tag}\b([^>]*)>(.*?)</{date_tag}>", element, re.S)
    if not date:
        fail(f"{file}: the Grupo Botanas entry has no <{date_tag}> date")
        return
    attrs, fallback = date.group(1), date.group(2)
    if f'data-i18n="{key}"' not in attrs:
        fail(f"{file}: the Grupo Botanas date must use data-i18n=\"{key}\"")
    if date_tag == "time" and 'datetime="2024-01"' not in attrs:
        fail(f"{file}: the Grupo Botanas <time> must declare datetime=\"2024-01\"")
    if EN_START not in fallback:
        fail(f"{file}: the Grupo Botanas fallback date {fallback!r} does not say {EN_START!r}")
    if earlier_years(element):
        fail(f"{file}: the Grupo Botanas entry declares earlier years {earlier_years(element)}")
    check_bilingual_key(file, key)


def check_strings(file):
    for lang, block in zip(("en", "es"), language_blocks()):
        value = i18n_value(block, "experience.botanas")
        if value is None:
            fail(f"{file}: experience.botanas missing in {lang}")
        elif earlier_years(value):
            fail(f"{file}: {lang} experience.botanas declares an earlier year")


def check_no_earlier_dates(file):
    for line in read(file).splitlines():
        if "Grupo Botanas" in line and earlier_years(line):
            fail(f"{file}: line declares an earlier year for Grupo Botanas: {line.strip()!r}")


CHECKS = {
    "CV_MASTER.md": check_cv_master,
    "cv.html": lambda f: check_html(f, "article", "p", "cv.botanasDate"),
    "index.html": lambda f: check_html(f, "article", "time", "experience.botanasDate"),
    "js/strings.js": check_strings,
    "PROPUESTA.md": check_no_earlier_dates,
}


def mentions():
    found = []
    for path in sorted(REPO.rglob("*")):
        relative = path.relative_to(REPO)
        if any(part in EXCLUDED_DIRS for part in relative.parts) or not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or path == Path(__file__).resolve():
            continue
        posix = relative.as_posix()
        if NARRATIVE.search(posix):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if re.search(r"botanas", text, re.I):
            found.append(posix)
    return found


def main():
    files = mentions()
    for required in ("CV_MASTER.md", "cv.html", "index.html", "js/strings.js"):
        if required not in files:
            fail(f"{required}: Grupo Botanas is expected here but was not found")
    for file in files:
        check = CHECKS.get(file)
        if check is None:
            fail(f"{file}: mentions Grupo Botanas but has no start-date check; add it to CHECKS")
            continue
        check(file)
    if failures:
        for message in failures:
            print(f"FAIL {message}", file=sys.stderr)
        return 1
    print("GRUPO_BOTANAS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
