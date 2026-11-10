#!/usr/bin/env python3
"""Language-specific link previews for the main pages (WhatsApp, social networks, messaging apps).

Their crawlers read the HTML of the URL without running JavaScript, and GitHub Pages serves /formacion/?lang=en as the
same file as /formacion/, so a shared link always previews the page's own language. Each main page therefore gets a
small static page per language, at en/<page> and es/<page> (https://luisguinea.com/en/formacion/,
https://luisguinea.com/es/cv.html), with the title, description and og:locale of that language. Visitors go on at
once to the real page with ?lang=<language>, keeping any other parameter (?theme=dark) and the hash.

The page's own language comes from its HTML <head>, so it never drifts. The other language comes from js/strings.js
and js/learn-strings.js for titles that the site already translates, and from OTHER below for the rest.

Usage: python3 tools/build_lang_previews.py           write the pages
       python3 tools/build_lang_previews.py --check   exit 1, writing nothing, if a page is missing, stale or out of
                                                      date (the Pages workflow checks it before building)
       --root DIR                                     work on another copy of the site (tests)
Standard library only (Node reads the strings files).
"""

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://luisguinea.com/"
LANGS = ("en", "es")
LOCALE = {"en": "en_US", "es": "es_ES"}
OPEN = {"en": "Open {} on luisguinea.com", "es": "Abrir {} en luisguinea.com"}

# Main page -> its key in js/strings.js or js/learn-strings.js (None: the site does not translate its title).
PAGES = {
    "index.html": None,
    "cv.html": None,
    "sobre-mi.html": "about.pageTitle",
    "music/index.html": "music.pageTitle",
    "agenda/index.html": "agenda.pageTitle",
    "formacion/index.html": "learn.hub.pageTitle",
    "formacion/piano/index.html": "learn.pages.piano.pageTitle",
    "formacion/composicion/index.html": "learn.pages.composicion.pageTitle",
    "formacion/produccion-musical/index.html": "learn.pages.produccion.pageTitle",
}

# The other language of each page: (title, description); a title of None comes from the strings files.
OTHER = {
    "index.html": ("Luis Guinea · Productor musical, A&R, datos y sistemas de IA",
                   "Productor musical y A&R desde hace más de 10 años. Luis Guinea crea sistemas de IA y automatización, "
                   "trabaja con datos, fundó un sello y escribe sobre cómo crecen los artistas."),
    "cv.html": ("CV / Luis Guinea",
                "CV de Luis Guinea: productor musical y A&R, fundador de un sello, desarrollador de TI y automatización en "
                "Grupo Botanas; sistemas de IA, datos e investigación musical. Máster, Berklee."),
    "sobre-mi.html": (None, "Un relato personal del camino de Luis Guinea por la música, la tecnología, el emprendimiento "
                            "y la curiosidad."),
    "music/index.html": (None, "Grabaciones de Luis Guinea como artista, compositor, coautor, arreglista y productor, "
                               "publicadas e inéditas, con fragmentos de hasta 45 segundos, créditos y enlaces para escuchar."),
    "agenda/index.html": (None, "Reúnete con Luis Guinea en línea o en persona: elige un formato, de 30 a 180 minutos y un "
                                "horario libre, y recibe una invitación de Google Calendar que puedes cancelar o cambiar."),
    "formacion/index.html": (None, "Private piano, harmony, songwriting and music production lessons in Valencia and "
                                   "online, and mentoring for artists, with Luis Guinea, pianist and producer."),
    "formacion/piano/index.html": (None, "Piano lessons in Valencia and online for children, teens and adults: technique, "
                                         "reading, accompaniment, improvisation, and classical and contemporary repertoire."),
    "formacion/composicion/index.html": (None, "Songwriting lessons in Valencia and online: melody, lyrics, harmony, "
                                               "structure and arrangement, for anyone who wants to finish their songs."),
    "formacion/produccion-musical/index.html": (None, "Music production lessons in Valencia and online: DAW, MIDI, "
                                                      "recording, synthesis, mixing and mastering with Logic Pro, Pro Tools "
                                                      "or Ableton Live."),
}


def strings(root):
    js = ("global.window={};const fs=require('fs');"
          "for(const f of process.argv.slice(1))eval(fs.readFileSync(f,'utf8'));"
          "process.stdout.write(JSON.stringify(window.STRINGS))")
    out = subprocess.run(["node", "-e", js, str(root / "js/strings.js"), str(root / "js/learn-strings.js")],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def leaf(tree, key):
    for part in key.split("."):
        tree = tree[part]
    return tree


def meta(text, rel):
    """Language, title, description and image of a page, from its <head>."""
    head = text[: text.index("</head>")]

    def one(pattern, optional=False):
        found = re.findall(pattern, head)
        if optional and not found:
            return None
        if len(found) != 1:
            raise SystemExit(f"{rel}: expected one match for {pattern}")
        return html.unescape(found[0])

    return {
        "lang": one(r'<html lang="([a-z]{2})'),
        "title": one(r'<meta property="og:title" content="([^"]*)"'),
        "description": one(r'<meta property="og:description" content="([^"]*)"'),
        "image": one(r'<meta property="og:image" content="([^"]*)"'),
        "alt": one(r'<meta property="og:image:alt" content="([^"]*)"'),
        "width": one(r'<meta property="og:image:width" content="([^"]*)"', True),
        "height": one(r'<meta property="og:image:height" content="([^"]*)"', True),
        "type": one(r'<meta property="og:image:type" content="([^"]*)"'),
    }


def preview_path(lang, rel):
    return f"{lang}/{rel}"


def page(lang, rel, m, title, description):
    e = lambda s: html.escape(s, quote=True)
    own = SITE + preview_path(lang, rel).removesuffix("index.html")
    depth = preview_path(lang, rel).count("/")
    target = "../" * depth + rel.removesuffix("index.html")
    shown = (target or "./") + "?lang=" + lang
    name = title.split(" · ")[0].split(" / ")[0]
    size = (f'<meta property="og:image:width" content="{e(m["width"])}"><meta property="og:image:height" content="{e(m["height"])}">'
            if m["width"] and m["height"] else "")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Generated by tools/build_lang_previews.py. Do not edit. A link preview: crawlers read this page; visitors go on to the page in this language. -->
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="noindex">
<link rel="canonical" href="{e(own)}">
<link rel="icon" href="data:,">
<meta property="og:type" content="website"><meta property="og:site_name" content="Luis Guinea"><meta property="og:locale" content="{LOCALE[lang]}">
<meta property="og:url" content="{e(own)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:image" content="{e(m['image'])}"><meta property="og:image:type" content="{e(m['type'])}">{size}<meta property="og:image:alt" content="{e(m['alt'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{e(m['image'])}"><meta name="twitter:image:alt" content="{e(m['alt'])}">
<script>(function(){{var t={json.dumps(target or "./")},q=location.search.slice(1).split('&').filter(function(p){{if(!p)return false;try{{return decodeURIComponent(p.split('=')[0].replace(/\\+/g,' '))!=='lang'}}catch(e){{return false}}}});q.push('lang={lang}');location.replace(t+'?'+q.join('&')+location.hash)}})();</script>
<style>:root{{color-scheme:light dark}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f2efe8;color:#111;font:1rem/1.5 system-ui,sans-serif}}@media(prefers-color-scheme:dark){{body{{background:#111;color:#f2efe8}}}}main{{max-width:36rem;padding:2rem 16px}}p{{margin:.5rem 0}}.kicker{{font:.75rem ui-monospace,monospace;text-transform:uppercase;letter-spacing:.08em}}h1{{font:400 clamp(2rem,8vw,3.5rem)/1 Georgia,serif;margin:.5rem 0}}a{{color:inherit;display:inline-flex;align-items:center;min-height:44px;text-underline-offset:4px}}a:focus-visible{{outline:3px solid #c4552b;outline-offset:3px}}</style>
</head>
<body><main><p class="kicker">Luis Guinea</p><h1>{e(name)}</h1><p>{e(description)}</p><p><a href="{e(shown)}">{e(OPEN[lang].format(name))}</a></p></main></body>
</html>
"""


def expected(root=ROOT):
    s = strings(root)
    files = {}
    for rel, key in PAGES.items():
        m = meta((root / rel).read_text(encoding="utf-8"), rel)
        other_title, other_desc = OTHER[rel]
        for lang in LANGS:
            if lang == m["lang"]:
                title, desc = m["title"], m["description"]
            else:
                title = other_title if other_title is not None else leaf(s[lang], key)
                desc = other_desc
            files[preview_path(lang, rel)] = page(lang, rel, m, title, desc)
    return files


def existing(root):
    return {p.relative_to(root).as_posix() for lang in LANGS for p in (root / lang).rglob("*") if p.is_file()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files = expected(root)
    stale = sorted(existing(root) - set(files))
    if args.check:
        problems = [f"stale: {r}" for r in stale]
        problems += [f"missing or out of date: {r}" for r, text in files.items()
                     if not (root / r).is_file() or (root / r).read_text(encoding="utf-8") != text]
        if problems:
            print("\n".join(problems) + "\nrun: python3 tools/build_lang_previews.py", file=sys.stderr)
            sys.exit(1)
        return
    for r in stale:
        (root / r).unlink()
    for r, text in files.items():
        (root / r).parent.mkdir(parents=True, exist_ok=True)
        (root / r).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} language previews")


if __name__ == "__main__":
    main()
