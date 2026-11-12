#!/usr/bin/env python3
"""Generate the Formación Musical section from tools/formacion_content.py.

Writes four pages and one strings file:

    formacion/index.html                      hub: areas, method, teacher, formats, FAQ and the enquiry form
    formacion/piano/index.html                subpages with their own search intent and enough content
    formacion/composicion/index.html
    formacion/produccion-musical/index.html
    js/learn-strings.js                       STRINGS.en.learn and STRINGS.es.learn for the EN/ES switch

The pages are served in Spanish (the audience searches "clases de piano en Valencia"): the HTML carries the Spanish
text, lang="es" and data-lang-default="es", and js/i18n.js switches them to English on request. The shared header,
footer and mini player are taken from sobre-mi.html, so they stay identical to the rest of the site.

Standard library plus Node.js (to read js/strings.js). Run after editing the copy:

    python3 tools/build_formacion.py           write the files
    python3 tools/build_formacion.py --check   fail if any file is out of date (writes nothing)
"""

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import formacion_content as C  # noqa: E402

SITE = "https://luisguinea.com/"
OUT_STRINGS = "js/learn-strings.js"
SUBPAGES = {"piano": "piano", "composicion": "composicion", "produccion": "produccion-musical"}
DESCRIPTIONS = {
    "hub": "Clases particulares de piano, armonía, composición y producción musical en Valencia y online, y mentorías para artistas, con Luis Guinea, pianista y productor.",
    "piano": "Clases de piano en Valencia y online para niños, jóvenes y adultos: técnica, lectura, acompañamiento, improvisación y repertorio clásico y contemporáneo.",
    "composicion": "Clases de composición de canciones en Valencia y online: melodía, letra, armonía, estructura y arreglo, para quien quiere terminar sus canciones.",
    "produccion": "Clases de producción musical en Valencia y online: DAW, MIDI, grabación, síntesis, mezcla y masterización con Logic Pro, Pro Tools o Ableton Live.",
}


# ---------- content tree ----------

def is_leaf(x):
    return isinstance(x, tuple) and len(x) == 2 and all(isinstance(v, str) for v in x)


def normalise(x):
    """Content as a tree whose leaves are (es, en): lists become "0", "1"...; (title, text) and (title, items) pairs
    become {"title", "text"} and {"title", "items"}; (area id, leaf) keeps only the leaf."""
    if is_leaf(x):
        return x
    if isinstance(x, dict):
        # Plain strings (such as evidenceHref) are settings, not copy: they stay out of the strings file.
        return {k: normalise(v) for k, v in x.items() if not isinstance(v, str)}
    if isinstance(x, list):
        return {str(i): normalise(v) for i, v in enumerate(x)}
    if isinstance(x, tuple) and len(x) == 2:
        a, b = x
        if isinstance(a, str):
            return normalise(b)
        if isinstance(b, list):
            return {"title": normalise(a), "items": normalise(b)}
        return {"title": normalise(a), "text": normalise(b)}
    raise ValueError(f"unexpected content node: {x!r}")


def build_tree():
    """Copy tree; the plans and the student area only exist once published (or in --preview)."""
    hidden = () if C.SUBSCRIPTIONS["published"] else ("plans", "students", "legalNote")
    return normalise({k: v for k, v in C.L.items() if k not in hidden})


TREE = build_tree()


def leaf(path):
    node = TREE
    for part in path.split("."):
        node = node[part]
    if not is_leaf(node):
        raise KeyError(path)
    return node


def es(path):
    return html.escape(leaf(path)[0], quote=False)


def lang_tree(node, i):
    return node[i] if is_leaf(node) else {k: lang_tree(v, i) for k, v in node.items()}


def el(tag, path, attrs=""):
    """<tag data-i18n="learn.path">Spanish text</tag>"""
    return f'<{tag}{attrs} data-i18n="learn.{path}">{es(path)}</{tag}>'


def accent_title(path, attrs=""):
    """Heading with its accent word in italics; js/learn.js keeps the italics after a language switch."""
    title, word = leaf(path + ".title")[0], leaf(path + ".titleAccent")[0]
    at = title.rfind(word)
    inner = html.escape(title, quote=False) if at < 0 else (
        html.escape(title[:at], quote=False) + "<em>" + html.escape(word, quote=False) + "</em>"
        + html.escape(title[at + len(word):], quote=False))
    return f'<h1{attrs} data-i18n="learn.{path}.title" data-accent="learn.{path}.titleAccent">{inner}</h1>'


# ---------- shared site chrome, from sobre-mi.html ----------

def site_strings():
    out = subprocess.run(
        ["node", "-e", "global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
                       "process.stdout.write(JSON.stringify(window.STRINGS))", str(ROOT / "js" / "strings.js")],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def lookup(tree, key):
    node = tree
    for part in key.split("."):
        node = node[part]
    return node


def localise(fragment, tree):
    """Spanish text for every data-i18n element and data-i18n-label attribute of an English fragment."""
    def text(m):
        return m.group(1) + html.escape(lookup(tree, m.group(2)), quote=False) + "<"
    fragment = re.sub(r'(<(?:a|span|button|p|li)\b[^>]*\bdata-i18n="([\w.]+)"[^>]*>)[^<]*<', text, fragment)

    def label(m):
        attrs = m.group(0)
        key = re.search(r'data-i18n-label="([\w.]+)"', attrs).group(1)
        return re.sub(r'aria-label="[^"]*"', 'aria-label="' + html.escape(lookup(tree, key)) + '"', attrs)
    return re.sub(r'<[^>]*\bdata-i18n-label="[\w.]+"[^>]*>', label, fragment)


def rebase(fragment, root):
    """Links of a root-level page (./, ./#x, music/, cv.html) made relative to a page `root` levels deep."""
    def fix(m):
        href = m.group(1)
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|/)", href, re.I):
            return m.group(0)
        if href.startswith("./"):
            href = href[2:]
        return f'href="{root}{href}"'
    return re.sub(r'href="([^"]*)"', fix, fragment)


def chrome(es_tree, root, current):
    """Header, footer and mini player of sobre-mi.html for a page at `root`, in Spanish, with `current` marking the
    Formación entry: "page" on the hub, "true" on its subpages."""
    about = (ROOT / "sobre-mi.html").read_text(encoding="utf-8")
    header = re.search(r'<header class="site-header">.*?</header>', about, re.S).group(0)
    footer = re.search(r'<footer class="footer">.*?</footer>', about, re.S).group(0)
    player = re.search(r'<div id="mini-player".*?(?=<script)', about, re.S).group(0)
    if 'data-i18n="nav.lessons"' not in header:
        raise SystemExit("sobre-mi.html has no Formación entry in its menu: add it before generating")
    header = header.replace('<span> / <span data-i18n="nav.about">About</span></span>',
                            '<span> / <span data-i18n="nav.lessons">Lessons</span></span>')
    header = header.replace(' aria-current="page"', "")
    footer = footer.replace(' aria-current="page"', "")
    header = rebase(header, root)
    footer = rebase(footer, root)
    player = rebase(player, root)
    own = "./" if current == "page" else "../"
    header = re.sub(r'href="[^"]*formacion/" data-section="lessons"',
                    f'href="{own}" data-section="lessons" aria-current="{current}"', header)
    footer = re.sub(r'href="[^"]*formacion/" data-i18n="nav.lessons"',
                    f'href="{own}" aria-current="{current}" data-i18n="nav.lessons"', footer)
    # Spanish page: the ES button is the pressed one until a language switch.
    header = header.replace('data-lang="en" aria-pressed="true"', 'data-lang="en" aria-pressed="false"')
    header = header.replace('data-lang="es" aria-pressed="false"', 'data-lang="es" aria-pressed="true"')
    return localise(header, es_tree), localise(footer, es_tree), localise(player, es_tree)


def skip_links(es_tree):
    return localise('<a class="skip-link" href="#content" data-i18n="ui.skip">Skip to content</a>'
                    '<a class="skip-link skip-player" href="#mini-player" data-i18n="ui.skipPlayer">Skip to music player</a>',
                    es_tree)


def head(page, root, url, json_ld):
    title = leaf(f"{'hub' if page == 'hub' else 'pages.' + page}.pageTitle")[0]
    key = "learn.hub.pageTitle" if page == "hub" else f"learn.pages.{page}.pageTitle"
    desc = DESCRIPTIONS[page]
    e = lambda s: html.escape(s)
    ld = "".join('<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False, separators=(",", ":"))
                 + "</script>" for d in json_ld)
    return (
        '<!doctype html>\n<html lang="es" data-lang-default="es">\n<head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<meta name="description" content="{e(desc)}">\n'
        f'<link rel="canonical" href="{url}"><link rel="icon" href="data:,">\n'
        f'<title data-i18n="{key}">{e(title)}</title>\n'
        f'<meta property="og:type" content="website"><meta property="og:site_name" content="Luis Guinea">'
        f'<meta property="og:locale" content="es_ES"><meta property="og:url" content="{url}">'
        f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">'
        f'<meta property="og:image" content="{SITE}assets/images/profile.webp"><meta property="og:image:type" content="image/webp">'
        '<meta property="og:image:alt" content="Luis Guinea"><meta name="twitter:card" content="summary_large_image">\n'
        f"{ld}\n"
        f'<script src="{root}js/theme-init.js"></script>'
        f'<link rel="preload" href="{root}fonts/instrument-serif-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="preload" href="{root}fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="stylesheet" href="{root}css/styles.css">\n</head>\n'
    )


def scripts(root, extra=()):
    names = ("soft-nav.js", "strings.js", "learn-strings.js", "i18n.js", "site.js", "music-data.js", "player.js", "learn.js") + tuple(extra)
    return "".join(f'<script src="{root}js/{n}"></script>' for n in names)


def subscriptions_on():
    return bool(C.SUBSCRIPTIONS["published"])


# ---------- structured data ----------

PERSON = {"@type": "Person", "@id": SITE + "#person", "name": "Luis Carlos Guinea Moctezuma",
          "alternateName": "Luis Guinea", "url": SITE}


def service(name, url, description, extra=None):
    data = {"@context": "https://schema.org", "@type": "Service", "@id": url + "#service", "name": name,
            "serviceType": "Clases particulares de música", "url": url, "description": description,
            "provider": PERSON, "areaServed": {"@type": "City", "name": "Valencia"},
            "availableLanguage": ["es", "en"]}
    data.update(extra or {})
    return data


def breadcrumb(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                                for i, (n, u) in enumerate(items)]}


# ---------- page parts ----------

def head_block(kicker, title, title_id, intro=None, cls=""):
    out = (f'<div class="learn-head{cls}"><div>{el("p", kicker, " class=\"kicker\"")}'
           f'{el("h2", title, f" id=\"{title_id}\"")}</div>')
    if intro:
        out += el("p", intro, ' class="learn-intro"')
    return out + "</div>"


def arrow_link(href, path, cls="", extra="", sr=None):
    sr_html = f'<span class="sr-only">: {el("span", sr)}</span>' if sr else ""
    return (f'<a class="text-link to-page{cls}" href="{href}"{extra}>{el("span", path)}{sr_html}'
            '<b aria-hidden="true">→</b></a>')


def faq(path, count):
    return "".join(f'<details class="learn-q">{el("summary", f"{path}.{i}.title")}{el("p", f"{path}.{i}.text")}</details>'
                   for i in range(count))


def photo(key, root, cls="learn-photo", caption=None, eager=False, sizes="(max-width: 700px) 100vw, 50vw"):
    """A real photograph (black and white in CSS), or None when the area still waits for one."""
    p = C.PHOTOS.get(key)
    if not p:
        return None
    load = ' fetchpriority="high"' if eager else ' loading="lazy" decoding="async"'
    cap = el("figcaption", caption) if caption else ""
    return (f'<figure class="{cls}"><img src="{root}{p["src"]}" alt="" width="{p["w"]}" height="{p["h"]}" '
            f'sizes="{sizes}"{load}>{cap}</figure>')


def type_figure(key, cls="learn-type"):
    """Typographic composition that stands in for a missing photograph (data-photo-pending names what is needed)."""
    if key == "composicion":
        return (f'<figure class="{cls} learn-type-staff" data-photo-pending="cuaderno, letra o partitura">'
                '<span class="learn-staff" aria-hidden="true"></span>'
                f'{el("p", "hub.goals.composicion.detail", " class=\"learn-type-words\"")}</figure>')
    return (f'<figure class="{cls} learn-type-chords" data-photo-pending="teclado con material de análisis">'
            f'{el("p", "hub.goals.armonia.detail", " class=\"learn-type-roman\"")}'
            '<p class="learn-type-symbols" aria-hidden="true"><span>Dm7</span><span>G7</span><span>Cmaj7</span></p></figure>')


def figure_for(key, root, caption=None):
    return photo(key, root, caption=caption) or type_figure(key)


def pricing():
    """Fees and booking terms: only once Luis approves them (COMMERCIAL["published"])."""
    c = C.COMMERCIAL
    if not c["published"]:
        return ""
    fees = "".join(f'<li><span>{es("area." + a)}</span><b>{c["fees"][a]} €/h</b></li>'
                   for a in ("piano", "armonia", "composicion", "produccion", "mentoria"))
    return f'<ul class="learn-fees">{fees}</ul>'


def enquiry_form():
    def select(name, label, pick, values, path, required=False):
        opts = f'<option value="" data-i18n="learn.form.{pick}">{es("form." + pick)}</option>' + "".join(
            f'<option value="{v}" data-i18n="learn.{path}.{v}">{es(path + "." + v)}</option>' for v in values)
        req = ' required aria-describedby="learn-error"' if required else ""
        return (f'<div class="learn-field"><label for="learn-{name}" data-i18n="learn.form.{label}">{es("form." + label)}'
                f'</label><select id="learn-{name}" name="{name}"{req}>{opts}</select></div>')

    def text(name, label, kind, auto, maxlength):
        return (f'<div class="learn-field"><label for="learn-{name}" data-i18n="learn.form.{label}">{es("form." + label)}'
                f'</label><input id="learn-{name}" name="{name}" type="{kind}" maxlength="{maxlength}" autocomplete="{auto}" '
                'required aria-describedby="learn-error"></div>')

    mode = "send" if C.ENQUIRY_ENDPOINT else "prepare"
    endpoint = f' data-endpoint="{html.escape(C.ENQUIRY_ENDPOINT)}"' if C.ENQUIRY_ENDPOINT else ""
    hint = "" if C.ENQUIRY_ENDPOINT else el("p", "form.prepareHint", ' class="learn-hint"')
    return (
        f'<form id="learn-form" class="learn-form" novalidate aria-label="{es("form.label")}" '
        f'data-i18n-label="learn.form.label"{endpoint}>'
        + select("area", "area", "areaPick", C.AREAS + ["mentoria", "nose"], "area", required=True)
        + '<div class="learn-row">'
        + select("level", "level", "levelPick", ["inicio", "base", "avanzado"], "form.levels")
        + select("format", "format", "formatPick", ["presencial", "online", "mentoria", "igual"], "form.formats")
        + '</div><div class="learn-row">' + text("name", "name", "text", "name", 80)
        + text("email", "email", "email", "email", 254) + "</div>"
        '<div class="learn-field"><label for="learn-message" data-i18n="learn.form.message">' + es("form.message")
        + '</label><textarea id="learn-message" name="message" rows="3" maxlength="1000" '
        f'data-i18n-placeholder="learn.form.messagePlaceholder" placeholder="{es("form.messagePlaceholder")}"></textarea></div>'
        '<div class="learn-trap" aria-hidden="true"><label for="learn-website">Website</label>'
        '<input id="learn-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>'
        '<p id="learn-error" class="learn-error" role="alert"></p>'
        '<div class="learn-form-actions"><button class="learn-button learn-button-invert" type="submit" '
        f'data-i18n="learn.form.{mode}">{es("form." + mode)}</button>'
        + el("p", "form.privacy", ' class="learn-hint"') + hint + "</div>"
        '<p id="learn-status" class="learn-status" role="status" aria-live="polite"></p>'
        '<div id="learn-sent" class="learn-sent" hidden>' + el("p", "form.opened")
        + '<pre id="learn-copytext" class="learn-message" tabindex="0"></pre>'
        '<button id="learn-copy" class="learn-button learn-button-quiet" type="button" data-i18n="learn.form.copy">'
        + es("form.copy") + '</button><p id="learn-copy-status" class="learn-hint" role="status" aria-live="polite"></p></div>'
        "</form>"
    )


def continue_nav(root):
    links = [("music/", "next.music", "Escucha mi música"), ("sobre-mi.html", "next.about", "Sobre mí"),
             ("cv.html", "next.cv", "Ver el CV completo")]
    return ('<nav class="continue wrap no-print" aria-labelledby="continue-title"><p id="continue-title" class="kicker" '
            'data-i18n="next.label">Sigue explorando</p><ul class="continue-links">' + "".join(
                f'<li><a href="{root}{h}"><span data-i18n="{k}">{t}</span><b aria-hidden="true">→</b></a></li>'
                for h, k, t in links) + "</ul></nav>")


def plans_section(root):
    """One plan card with a weekly / every-two-weeks switch, the renewal conditions and the subscribe form (js/plans.js). Only when subscriptions are on."""
    if not subscriptions_on():
        return ""
    endpoint = html.escape(C.SUBSCRIPTIONS["endpoint"])
    # One card: the price is the same for both rhythms, so a weekly / every-two-weeks switch picks the plan and the
    # lines that differ (renewal period) follow the checked radio (CSS :has). Weekly is preselected.
    switch = "".join(
        f'<label class="plan-option" for="plan-{key}"><input id="plan-{key}" type="radio" name="plan" value="{key}" required'
        f'{" checked" if key == "weekly" else ""}>{el("span", f"plans.{key}.name")}</label>'
        for key in ("weekly", "biweekly"))
    per = "".join(el("small", f"plans.{key}.per", f' data-plan="{key}"') for key in ("weekly", "biweekly"))
    lines = "".join(
        f'<span class="plan-detail" data-plan="{key}">{el("span", f"plans.{key}.rhythm", " class=\"plan-rhythm\"")}'
        f'{el("span", f"plans.{key}.detail")}</span>' for key in ("weekly", "biweekly"))
    cards = ('<div class="plan-card">'
             f'{el("p", "plans.cardTitle", " class=\"plan-name\"")}'
             f'<span class="plan-price">{el("b", "plans.weekly.price")}{per}</span>'
             f'<fieldset class="plan-switch"><legend class="sr-only" data-i18n="learn.plans.legend">{es("plans.legend")}</legend>'
             f'{switch}</fieldset>{lines}</div>')
    terms = "".join(el("li", f"plans.terms.{i}") for i in range(len(C.L["plans"]["terms"])))
    conditions = "".join(f'<div>{el("dt", f"plans.conditions.{i}.title")}{el("dd", f"plans.conditions.{i}.text")}</div>'
                         for i in range(len(C.L["plans"]["conditions"])))
    return (
        '<section id="planes" class="learn-section plans" aria-labelledby="plans-title"><div class="wrap">'
        + head_block("plans.kicker", "plans.title", "plans-title", "plans.intro")
        + f'<form id="plans-form" class="plans-form" novalidate data-endpoint="{endpoint}">'
        f'<div class="plan-cards">{cards}</div>'
        '<div class="plans-terms">' + el("h3", "plans.termsTitle") + f'<ul>{terms}</ul>'
        f'<details class="learn-more plans-conditions">{el("summary", "plans.conditionsSummary")}<dl>{conditions}</dl></details></div>'
        '<div class="plans-consent">'
        f'<label class="plans-check"><input id="plans-accept" type="checkbox" required>{el("span", "plans.acceptTerms")}</label>'
        f'<label class="plans-check"><input id="plans-early" type="checkbox" required>{el("span", "plans.earlyStart")}</label>'
        + arrow_link("condiciones/", "plans.termsLink", cls=" plans-terms-link") +
        '<div class="learn-trap" aria-hidden="true"><label for="plans-website">Website</label>'
        '<input id="plans-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>'
        '<p id="plans-error" class="learn-error" role="alert"></p>'
        f'<div class="plans-actions"><button class="learn-button" type="submit" data-i18n="learn.plans.submit">{es("plans.submit")}</button>'
        + el("p", "plans.secure", ' class="learn-hint"') + '</div>'
        '<p id="plans-status" class="learn-status" role="status" aria-live="polite"></p>'
        f'<p class="plans-already">{el("span", "plans.already")} '
        + arrow_link(root + "alumnos/", "plans.studentLink") + "</p></div></form></div></section>"
    )


def area_target(a):
    return SUBPAGES[a] + "/" if a in SUBPAGES else "#" + a


def hub(es_tree):
    root = "../"
    url = SITE + "formacion/"
    catalogue = {"@type": "OfferCatalog", "name": "Áreas de formación musical", "itemListElement": [
        {"@type": "Offer", "itemOffered": {"@type": "Service", "name": leaf("area." + a)[0],
                                           "url": url + area_target(a)}} for a in C.AREAS]}
    ld = [service("Formación musical con Luis Guinea", url, DESCRIPTIONS["hub"], {"hasOfferCatalog": catalogue})]
    header, footer, player = chrome(es_tree, root, "page")
    h = "hub"

    hero = (
        '<section class="learn-hero wrap" aria-labelledby="learn-title"><div class="learn-hero-copy">'
        + el("p", f"{h}.eyebrow", ' class="eyebrow"') + accent_title(h, ' id="learn-title"')
        + el("p", f"{h}.lede", ' class="learn-lede"') + '<div class="learn-actions">'
        + el("a", f"{h}.cta", ' class="learn-button" href="#empezar"')
        + el("a", f"{h}.cta2", ' class="learn-button learn-button-quiet" href="#consulta"') + "</div></div>"
        + photo("hero", root, "learn-hero-photo", caption=f"{h}.caption", eager=True,
                sizes="(max-width: 700px) 100vw, 46vw") + "</section>"
    )

    goals = "".join(
        f'<li class="learn-goal learn-goal-{a}"><a href="{area_target(a)}"><span class="learn-goal-num">0{i + 1}</span>'
        f'{el("span", f"{h}.goals.{a}.goal", " class=\"learn-goal-text\"")}'
        f'{el("span", f"{h}.goals.{a}.detail", " class=\"learn-goal-detail\"")}<b aria-hidden="true">→</b></a></li>'
        for i, a in enumerate(C.AREAS))
    selector = ('<section id="empezar" class="learn-section learn-sand" aria-labelledby="goals-title"><div class="wrap">'
                + head_block(f"{h}.goalsKicker", f"{h}.goalsTitle", "goals-title")
                + f'<ul class="learn-goals">{goals}</ul></div></section>')

    blocks = ""
    for i, a in enumerate(C.AREAS):
        p = f"{h}.areas.{a}"
        skills = " · ".join(es(f"{p}.skills.{j}") for j in range(3))
        skills_html = "".join(el("li", f"{p}.skills.{j}") for j in range(3))
        cap = f"{p}.caption" if "caption" in C.L["hub"]["areas"][a] else None
        if a in SUBPAGES:
            more = arrow_link(SUBPAGES[a] + "/", f"{p}.link")
        else:
            items = "".join(el("li", f"{p}.learn.{j}") for j in range(4))
            more = (f'<details class="learn-more">{el("summary", "seeContents")}<ul>{items}</ul><dl>'
                    f'<div>{el("dt", "labelWho")}{el("dd", p + ".who")}</div>'
                    f'<div>{el("dt", "labelOutcome")}{el("dd", p + ".outcome")}</div></dl></details>'
                    + arrow_link(f"?area={a}#consulta", "ctaButton", extra=f' data-area="{a}"', sr=f"area.{a}"))
        blocks += (
            f'<li class="learn-block{" learn-block-flip" if i % 2 else ""}" id="{a}">'
            + figure_for(a, root, cap)
            + f'<div class="learn-block-text"><p class="learn-block-num" aria-hidden="true">0{i + 1}</p>'
            + el("h3", "area." + a) + el("p", f"{p}.line", ' class="learn-block-line"')
            + f'<ul class="learn-skills" aria-label="{skills}">{skills_html}</ul>{more}</div></li>'
        )
    areas = ('<section id="areas" class="learn-section" aria-labelledby="areas-title"><div class="wrap">'
             + head_block(f"{h}.areasKicker", f"{h}.areasTitle", "areas-title", f"{h}.areasIntro")
             + f'<ol class="learn-blocks">{blocks}</ol></div></section>')

    principles = "".join(f'<li><b aria-hidden="true">0{i + 1}</b>{el("h3", f"{h}.method.{i}.title")}'
                         f'{el("p", f"{h}.method.{i}.text")}</li>' for i in range(3))
    method = ('<section id="metodo" class="learn-section learn-olive" aria-labelledby="method-title"><div class="wrap">'
              + el("h2", f"{h}.methodKicker", ' class="kicker" id="method-title"')
              + f'<ol class="learn-principles">{principles}</ol></div></section>')

    about_rows = "".join(f'<div>{el("dt", f"{h}.about.{i}.title")}{el("dd", f"{h}.about.{i}.text")}</div>'
                         for i in range(3))
    evidence = "".join(
        f'<li><a href="{root}{href}">{el("span", f"{h}.{key}")}<b aria-hidden="true">→</b></a></li>'
        for href, key in (("music/", "evidenceMusic"), ("cv.html", "evidenceCv"), ("sobre-mi.html", "evidenceAbout")))
    about = (
        '<section id="profesor" class="learn-section" aria-labelledby="about-title"><div class="wrap learn-about">'
        + photo("about", root, "learn-about-photo", caption=f"{h}.aboutCaption", sizes="(max-width: 700px) 100vw, 40vw")
        + '<div class="learn-about-copy">' + el("p", f"{h}.aboutKicker", ' class="kicker"')
        + el("h2", f"{h}.aboutTitle", ' id="about-title"') + el("p", f"{h}.aboutText", ' class="learn-about-text"')
        + f'<dl class="learn-credentials">{about_rows}</dl>'
        + f'<ul class="learn-links">{evidence}</ul></div></div></section>'
    )

    modes = "".join(f'<li id="{m}">{el("h3", f"{h}.modes.{m}.title")}{el("p", f"{h}.modes.{m}.text")}</li>'
                    for m in ("presencial", "online", "mentorias"))
    terms = "".join(el("li", f"{h}.terms.{i}") for i in range(3))
    formats = ('<section id="modalidades" class="learn-section learn-sand" aria-labelledby="modes-title"><div class="wrap">'
               + head_block(f"{h}.modesKicker", f"{h}.modesTitle", "modes-title")
               + f'<ul class="learn-modes">{modes}</ul><ul class="learn-terms">{terms}</ul>{pricing()}</div></section>')

    questions = ('<section id="preguntas" class="learn-section" aria-labelledby="faq-title">'
                 '<div class="wrap learn-faq-layout"><div class="learn-head"><div><p class="kicker">'
                 + el("span", "faqKicker") + "</p>" + el("h2", f"{h}.faqTitle", ' id="faq-title"') + "</div></div>"
                 + f'<div class="learn-faq">{faq(f"{h}.faq", len(C.L["hub"]["faq"]))}</div></div></section>')

    enquiry = (
        '<section id="consulta" class="learn-section learn-enquiry" aria-labelledby="enquiry-title">'
        '<div class="wrap learn-enquiry-grid"><div class="learn-enquiry-copy">'
        + el("p", f"{h}.enquiryKicker", ' class="kicker"') + el("h2", f"{h}.enquiryTitle", ' id="enquiry-title"')
        + el("p", f"{h}.enquiryIntro", ' class="learn-intro"') + '<div class="learn-alt">'
        + el("p", f"{h}.talkTitle") + arrow_link(root + "agenda/", f"{h}.talkLink") + "</div></div>"
        + enquiry_form() + "</div></section>"
    )

    main = (f'<main id="content" class="learn-page">{hero}{selector}{areas}{method}{about}{formats}{plans_section(root)}'
            f"{questions}{enquiry}{continue_nav(root)}</main>")
    extra = ("plans.js",) if subscriptions_on() else ()
    return (head("hub", root, url, ld) + "<body>" + skip_links(es_tree) + "\n" + header + "\n" + main + footer
            + player + scripts(root, extra) + "</body></html>\n")


def subpage(es_tree, key):
    slug = SUBPAGES[key]
    root = "../../"
    url = f"{SITE}formacion/{slug}/"
    p = f"pages.{key}"
    name = leaf("area." + key)[0]
    ld = [service(leaf(f"{p}.pageTitle")[0].split(" · ")[0], url, DESCRIPTIONS[key]),
          breadcrumb([("Inicio", SITE), ("Formación musical", SITE + "formacion/"), (name, url)])]
    header, footer, player = chrome(es_tree, root, "true")
    ask = f"../?area={key}#consulta"
    page = C.L["pages"][key]

    crumbs = (f'<nav class="learn-crumbs wrap" aria-label="{es("crumbLabel")}" data-i18n-label="learn.crumbLabel"><ol>'
              f'<li>{el("a", "crumbHome", f" href=\"{root}\"")}</li><li>{el("a", "crumbLearn", " href=\"../\"")}</li>'
              f'<li aria-current="page" data-i18n="learn.area.{key}">{es("area." + key)}</li></ol></nav>')
    meta = "".join(el("li", f"{p}.meta.{i}") for i in range(3))
    figure = (photo(key, root, "learn-hero-photo learn-hero-photo-wide", eager=True, sizes="(max-width: 700px) 100vw, 42vw")
              or type_figure(key, "learn-type learn-hero-photo"))
    hero = (
        '<section class="learn-hero learn-hero-sub wrap" aria-labelledby="learn-title"><div class="learn-hero-copy">'
        + el("p", f"{p}.eyebrow", ' class="eyebrow"') + accent_title(p, ' id="learn-title"')
        + el("p", f"{p}.lede", ' class="learn-lede"') + f'<ul class="learn-meta">{meta}</ul>'
        '<div class="learn-actions">' + el("a", "ctaButton", f' class="learn-button" href="{ask}"')
        + el("a", "bookTalk", f' class="learn-button learn-button-quiet" href="{root}agenda/"') + "</div></div>"
        + figure + "</section>"
    )
    who = "".join(f'<li>{el("h3", f"{p}.who.{i}.title")}{el("p", f"{p}.who.{i}.text")}</li>' for i in range(3))
    who = ('<section id="para-quien" class="learn-section learn-section-tight" aria-labelledby="who-title">'
           '<div class="wrap">' + el("h2", f"{p}.whoKicker", ' class="kicker" id="who-title"')
           + f'<ul class="learn-who">{who}</ul></div></section>')
    stages = "".join(
        f'<details class="learn-stage"{" open" if i == 0 else ""}><summary><b aria-hidden="true">0{i + 1}</b>'
        f'{el("span", f"{p}.plan.{i}.title")}<small aria-hidden="true">{len(items)}</small></summary><ul>'
        + "".join(el("li", f"{p}.plan.{i}.items.{j}") for j in range(len(items))) + "</ul></details>"
        for i, (_, items) in enumerate(page["plan"]))
    plan = ('<section id="programa" class="learn-section learn-sand" aria-labelledby="plan-title">'
            '<div class="wrap learn-plan-layout">' + head_block(f"{p}.planKicker", f"{p}.planTitle", "plan-title")
            + f'<div class="learn-stages">{stages}</div></div></section>')
    how = ('<section id="clases" class="learn-section" aria-labelledby="how-title"><div class="wrap learn-how-layout">'
           '<div>' + el("h2", f"{p}.howKicker", ' class="kicker" id="how-title"') + el("p", f"{p}.how", ' class="learn-how"')
           + arrow_link(root + page["evidenceHref"], f"{p}.evidence") + '</div><dl class="learn-credentials">'
           f'<div>{el("dt", f"{p}.needTitle")}{el("dd", f"{p}.need")}</div>'
           f'<div>{el("dt", f"{p}.proofTitle")}{el("dd", f"{p}.proof")}</div></dl></div></section>')
    questions = ('<section id="preguntas" class="learn-section learn-sand" aria-labelledby="faq-title">'
                 '<div class="wrap learn-faq-layout"><div class="learn-head"><div>'
                 + f'<h2 id="faq-title" class="kicker">04 / {el("span", "faqKicker")}</h2></div></div>'
                 f'<div class="learn-faq">{faq(f"{p}.faq", len(page["faq"]))}</div></div></section>')
    cta = ('<section class="learn-section learn-enquiry learn-cta" aria-labelledby="cta-title"><div class="wrap learn-cta-inner">'
           + el("h2", f"{p}.ctaTitle", ' id="cta-title"') + el("p", "ctaIntro", ' class="learn-intro"')
           + '<div class="learn-actions">' + el("a", "ctaButton", f' class="learn-button learn-button-invert" href="{ask}"')
           + el("a", "bookTalk", f' class="learn-button learn-button-quiet" href="{root}agenda/"')
           + "</div></div></section>")
    others = [k for k in SUBPAGES if k != key]
    related = ('<nav class="continue wrap no-print" aria-labelledby="continue-title">'
               + el("p", "relatedKicker", ' id="continue-title" class="kicker"') + '<ul class="continue-links">'
               + "".join(f'<li><a href="../{SUBPAGES[o]}/">{el("span", "area." + o)}<b aria-hidden="true">→</b></a></li>'
                         for o in others)
               + f'<li><a href="../">{el("span", "allAreas")}<b aria-hidden="true">→</b></a></li></ul></nav>')
    main = (f'<main id="content" class="learn-page learn-sub">{crumbs}{hero}{who}{plan}{how}{questions}{cta}'
            f"{related}</main>")
    return (head(key, root, url, ld) + "<body>" + skip_links(es_tree) + "\n" + header + "\n" + main + footer
            + player + scripts(root) + "</body></html>\n")


def students_page(es_tree):
    """/alumnos/: sign-in by email link, Checkout return, plan, lessons, bookings and billing (js/alumnos.js).
    Private area: noindex, not in the sitemap, no personal data in the HTML."""
    root = "../"
    url = SITE + "alumnos/"
    header, footer, player = chrome(es_tree, root, "true")
    # chrome() points the Formación entry at "../" (right for its subpages); from /alumnos/ it lives at ../formacion/.
    header = header.replace('href="../" data-section="lessons" aria-current="true"', 'href="../formacion/" data-section="lessons" aria-current="true"')
    footer = footer.replace('href="../" aria-current="true" data-i18n="nav.lessons"', 'href="../formacion/" aria-current="true" data-i18n="nav.lessons"')
    header = header.replace('<span> / <span data-i18n="nav.lessons">', '<span> / <span data-i18n="learn.students.eyebrow">', 1)
    header = re.sub(r'(<span data-i18n="learn.students.eyebrow">)[^<]*', r"\1" + es("students.eyebrow"), header, count=1)
    endpoint = html.escape(C.SUBSCRIPTIONS["endpoint"])
    title = leaf("students.pageTitle")[0]
    page_head = (
        '<!doctype html>\n<html lang="es" data-lang-default="es">\n<head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">\n'
        f'<link rel="canonical" href="{url}"><link rel="icon" href="data:,">\n'
        f'<title data-i18n="learn.students.pageTitle">{html.escape(title)}</title>\n'
        f'<script src="{root}js/theme-init.js"></script>'
        f'<link rel="preload" href="{root}fonts/instrument-serif-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="preload" href="{root}fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="stylesheet" href="{root}css/styles.css">\n</head>\n')
    main = (
        f'<main id="content" class="learn-page students" data-endpoint="{endpoint}">'
        '<section class="learn-hero learn-hero-sub wrap students-hero" aria-labelledby="learn-title"><div class="learn-hero-copy">'
        + el("p", "students.eyebrow", ' class="eyebrow"') + accent_title("students", ' id="learn-title"') + "</div></section>"
        '<div class="wrap students-app">'
        '<p id="stu-status" class="learn-status students-status" role="status" aria-live="polite"></p>'
        # return from Checkout: first thing on the page
        '<section id="stu-checkout" class="students-panel" hidden><p id="stu-checkout-text" class="students-checkout" role="status" aria-live="polite"></p>'
        + arrow_link(root + "formacion/#planes", "students.backToPlans", cls=" students-back") + "</section>"
        # sign in
        '<section id="stu-login" class="students-panel" aria-labelledby="stu-login-title" hidden>'
        + el("h2", "students.loginTitle", ' id="stu-login-title"') + el("p", "students.loginIntro", ' class="learn-intro"')
        + '<form id="stu-login-form" class="learn-form students-login" novalidate><div class="learn-field">'
        f'<label for="stu-email" data-i18n="learn.students.email">{es("students.email")}</label>'
        '<input id="stu-email" type="email" maxlength="254" autocomplete="email" required aria-describedby="stu-login-error"></div>'
        '<div class="learn-trap" aria-hidden="true"><label for="stu-website">Website</label>'
        '<input id="stu-website" type="text" tabindex="-1" autocomplete="off"></div>'
        '<p id="stu-login-error" class="learn-error" role="alert"></p>'
        f'<button class="learn-button" type="submit" data-i18n="learn.students.sendLink">{es("students.sendLink")}</button></form></section>'
        # dashboard
        '<div id="stu-dash" class="students-dash" hidden>'
        '<div class="students-top"><p id="stu-hello" class="students-hello"></p>'
        f'<button id="stu-signout" class="learn-button learn-button-quiet" type="button" data-i18n="learn.students.signOut">{es("students.signOut")}</button></div>'
        '<section class="students-panel" aria-labelledby="stu-plan-title">' + el("h2", "students.planTitle", ' id="stu-plan-title" class="kicker"')
        + '<div id="stu-plan"></div></section>'
        '<section class="students-panel" aria-labelledby="stu-classes-title">' + el("h2", "students.classesTitle", ' id="stu-classes-title" class="kicker"')
        + '<dl id="stu-counts" class="students-counts"></dl><ul id="stu-credits" class="students-credits"></ul><p id="stu-policy" class="learn-hint"></p></section>'
        '<section class="students-panel" aria-labelledby="stu-book-title">' + el("h2", "students.bookTitle", ' id="stu-book-title" class="kicker"')
        + '<div id="stu-book"></div></section>'
        '<section class="students-panel" aria-labelledby="stu-bookings-title">' + el("h2", "students.bookingsTitle", ' id="stu-bookings-title" class="kicker"')
        + '<ol id="stu-bookings" class="students-bookings"></ol></section>'
        '<section class="students-panel" aria-labelledby="stu-billing-title">' + el("h2", "students.billingTitle", ' id="stu-billing-title" class="kicker"')
        + el("p", "students.billingIntro") + f'<button id="stu-portal" class="learn-button learn-button-quiet" type="button" data-i18n="learn.students.portal">{es("students.portal")}</button></section>'
        + el("p", "students.help", ' class="learn-hint students-help"') + "</div>"
        "</div></main>"
    )
    return (page_head + "<body>" + skip_links(es_tree) + "\n" + header + "\n" + main + footer + player
            + scripts(root, ("alumnos.js",)) + "</body></html>\n")


def provider_text(text):
    return html.escape(text.format(**C.PROVIDER), quote=False)


def legal_page(es_tree):
    """/formacion/condiciones/: terms of the class plans and privacy policy, in Spanish (the binding text)."""
    missing = [k for k, v in C.PROVIDER.items() if not v]
    if missing and not PREVIEW:
        raise SystemExit("PROVIDER data missing in tools/formacion_content.py: " + ", ".join(missing))
    root = "../../"
    url = SITE + "formacion/condiciones/"
    header, footer, player = chrome(es_tree, root, "true")
    sections = "".join(
        f'<section class="legal-section"><h2>{html.escape(t)}</h2>' + "".join(f"<p>{provider_text(p)}</p>" for p in ps) + "</section>"
        for t, ps in C.LEGAL)
    privacy = "".join(
        f'<section class="legal-section"><h3>{html.escape(t)}</h3>' + "".join(f"<p>{provider_text(p)}</p>" for p in ps) + "</section>"
        for t, ps in C.PRIVACY)
    page_head = (
        '<!doctype html>\n<html lang="es" data-lang-default="es">\n<head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="description" content="Condiciones de contratación de los planes de clases de música y política de privacidad.">\n'
        f'<link rel="canonical" href="{url}"><link rel="icon" href="data:,">\n'
        '<title>Condiciones y privacidad · Clases · Luis Guinea</title>\n'
        f'<script src="{root}js/theme-init.js"></script>'
        f'<link rel="preload" href="{root}fonts/instrument-serif-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="preload" href="{root}fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="stylesheet" href="{root}css/styles.css">\n</head>\n')
    main = (
        '<main id="content" class="learn-page legal-page"><div class="wrap legal-wrap">'
        '<p class="eyebrow">Formación musical</p><h1 class="legal-title">Condiciones y <em>privacidad.</em></h1>'
        f'<p class="legal-meta">Versión {C.LEGAL_VERSION} · El texto en español es el vinculante. '
        '<span data-i18n="learn.legalNote">Este texto se ofrece en español.</span></p>'
        f'<nav class="legal-toc"><a href="#condiciones">Condiciones de contratación</a> · <a href="#privacidad">Política de privacidad</a> · '
        f'<a href="../#planes">Volver a los planes</a></nav>'
        f'<article id="condiciones" class="legal-body"><h2 class="kicker">Condiciones de contratación</h2>{sections}'
        f'<section class="legal-section"><h3>Modelo de formulario de desistimiento</h3><p>{provider_text(C.WITHDRAWAL_FORM)}</p></section></article>'
        f'<article id="privacidad" class="legal-body"><h2 class="kicker">Política de privacidad</h2>{privacy}</article>'
        "</div></main>")
    return (page_head + "<body>" + skip_links(es_tree) + "\n" + header + "\n" + main + footer + player
            + scripts(root) + "</body></html>\n")


def strings_js():
    data = {lang: lang_tree(TREE, i) for i, lang in enumerate(("es", "en"))}
    body = ("// Generated by tools/build_formacion.py from tools/formacion_content.py. Do not edit by hand.\n"
            "// Copy of the Formación Musical pages for the EN/ES switch, merged into window.STRINGS.\n"
            "(function(){var L=" + json.dumps({"en": data["en"], "es": data["es"]}, ensure_ascii=False,
                                               separators=(",", ":"))
            + ";window.STRINGS.en.learn=L.en;window.STRINGS.es.learn=L.es;})();\n")
    return body


PREVIEW = False


def outputs():
    if subscriptions_on() and not PREVIEW:
        # Publishing the plans needs the signed launch checklist (docs/lanzamiento/CHECKLIST-LANZAMIENTO.md).
        import launch_gate
        missing = launch_gate.check()
        if missing:
            raise SystemExit("LAUNCH GATE: the plans cannot be published yet. Missing:\n  - " + "\n  - ".join(missing))
    tree = site_strings()["es"]
    files = {"formacion/index.html": hub(tree), OUT_STRINGS: strings_js()}
    for key, slug in SUBPAGES.items():
        files[f"formacion/{slug}/index.html"] = subpage(tree, key)
    if subscriptions_on():
        files["alumnos/index.html"] = students_page(tree)
        files["formacion/condiciones/index.html"] = legal_page(tree)
    for rel, text in files.items():
        if "—" in text:
            raise SystemExit(f"{rel}: em dash in published copy")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a generated file is out of date")
    parser.add_argument("--preview", metavar="ENDPOINT", help="build with the class plans on, calling ENDPOINT (needs --out)")
    parser.add_argument("--out", metavar="DIR", help="with --preview: directory for the preview files (never the repo)")
    args = parser.parse_args(argv)
    if args.preview:
        out = Path(args.out or "").resolve()
        if not args.out or out == ROOT or ROOT in out.parents:
            parser.error("--preview needs --out outside the repository")
        global TREE, PREVIEW
        PREVIEW = True
        C.SUBSCRIPTIONS = {"published": True, "endpoint": args.preview}
        TREE = build_tree()
        for rel, text in outputs().items():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_text(text, encoding="utf-8")
            print("preview", out / rel)
        return 0
    stale = []
    for rel, text in outputs().items():
        path = ROOT / rel
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if args.check:
            stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print("wrote", rel)
    if stale:
        print("FORMACIÓN OUT OF DATE, run python3 tools/build_formacion.py: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
