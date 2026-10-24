#!/usr/bin/env node
// Link previews for shared music links (WhatsApp, social networks, messaging apps). Their crawlers read the HTML of the
// URL without running JavaScript, and GitHub Pages serves /music/?song=… and /music/?genre=… as the same file, so a link
// with parameters can only ever preview /music/ itself. Each shareable link therefore gets a small static page at its own
// path, with its own title, description, image and URL, that sends the visitor on at once to the address the player
// already understands (music/song/<work id>/ -> /music/?song=<work id>), keeping any other parameter and the hash.
//
// Pages are generated for every published recording and for the usual selections, never for every combination:
//   - one artist, one genre, one mood, one Luis Guinea credit;
//   - credit and genre ("Pop Music Produced by Luis Guinea");
//   - genre and mood with at least MIN_PAIR recordings ("Warm Pop Songs by Luis Guinea");
//   - two of the moods with at least MIN_MOOD recordings ("Warm or Melancholic Songs": chips of one group add up).
// Any other selection (search text, three filters, rare pairs) is shared as /music/?… and previews as /music/.
// Everything comes from js/music-data.js (the public catalogue) and the English labels of js/strings.js.
// js/share-pages.js maps each selection to its page, so the Share buttons know which links have one.
//
// Usage: node tools/build_share_pages.js           write the pages and js/share-pages.js
//        node tools/build_share_pages.js --check   exit 1, writing nothing, if a page is missing, stale (a retired
//                                                  recording) or out of date, if the index is, or if an image no
//                                                  longer matches its cover; runs anywhere Node runs (the Pages
//                                                  workflow checks it before building)
//        node tools/build_share_pages.js --images  also (re)make the JPEG preview images with macOS sips, only when
//                                                  covers change, and record them in tools/share-images.lock.json
//        --root DIR                                work on another copy of the site (tests)
// The lock pins each image to the sha256 of its source cover and of the JPEG itself, so the check needs no image tools.
// Standard library only.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const {execFileSync} = require('child_process');
const crypto = require('crypto');

const rootAt = process.argv.indexOf('--root');
const ROOT = path.resolve(rootAt > 0 ? process.argv[rootAt + 1] : path.join(__dirname, '..'));
const LOCK = 'tools/share-images.lock.json';
const SITE = 'https://luisguinea.com/';
const GENERATED_DIRS = ['music/song', 'music/artist', 'music/genre', 'music/mood', 'music/credit'];
const MANIFEST = 'js/share-pages.js';
const IMAGE_DIR = 'assets/images/share';
// The music cover (studio photo) cropped to 1200x630: the image of every selection.
const SELECTION_IMAGE = {file: `${IMAGE_DIR}/music.jpg`, width: 1200, height: 630, alt: 'Jazztone Studios: recording studio with a mixing console'};
const MIN_PAIR = 3, MIN_MOOD = 10;
const CREDITS = {
  artist: {value: 'Artist', title: 'Luis Guinea as Artist', withGenre: g => `${g.label} ${g.noun} by Luis Guinea as Artist`},
  producer: {value: 'Producer', title: 'Music Produced by Luis Guinea', withGenre: g => `${g.label} Music Produced by Luis Guinea`},
  composer: {value: 'Composer', title: 'Songs Written by Luis Guinea', withGenre: g => `${g.label} ${g.noun} Written by Luis Guinea`},
};
// Same credit rule as js/music-page.js: Composer gathers songwriting and co-writing, Producer production and co-production.
const FACET_CREDITS = {Composer: ['Songwriter', 'Co-writer'], Producer: ['Producer', 'Co-producer']};
const ROLE_ORDER = ['Artist', 'Songwriter', 'Co-writer', 'Producer', 'Co-producer', 'Arranger', 'Co-arranger', 'Music Director', 'Performer', 'Keyboards', 'Recording Engineer', 'Audio Editing Engineer'];

function load(file, name) {
  const context = {window: {}};
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, file), 'utf8'), context, {filename: file});
  return context.window[name];
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const enc = encodeURIComponent;
const slug = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const list = items => items.length < 2 ? items.join('') : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

function model() {
  const tracks = load('js/music-data.js', 'MUSIC_DATA');
  const en = load('js/strings.js', 'STRINGS').en.music;
  const label = (key, fallback) => en[key] || fallback;
  const roleLabel = r => label('role' + r.replace(/[^A-Za-z]/g, ''), r);
  const artistsOf = x => Array.isArray(x.artists) && x.artists.length ? x.artists : [x.artist];
  const matchesRole = (x, value) => x.role === value || (FACET_CREDITS[value] || [value]).some(c => x.roles.includes(c));
  const id = x => x.preview.replace(/\.mp3$/, '');
  // The order /music/ opens with: newest first, undated last, then title.
  const byYear = (a, b) => (a.year == null) - (b.year == null) || (b.year || 0) - (a.year || 0) || a.title.localeCompare(b.title, 'en');
  const terms = group => [...new Set(tracks.flatMap(x => x[group + 's'] || []))].sort();
  const genre = g => ({id: g, label: label('genre_' + g, g), noun: g === 'cinematic_classical' ? 'Music' : 'Songs'});
  const mood = m => ({id: m, label: label('mood_' + m, m)});
  return {tracks, en, label, roleLabel, artistsOf, matchesRole, id, byYear, terms, genre, mood};
}

// A recording's own cover; generic-cover.webp is the site's placeholder for those without one, so they get the music image.
const PLACEHOLDER = 'generic-cover.webp';
function imageFor(m, x) {
  const stem = String(x.artwork || '').replace(/\.webp$/, '');
  if (!stem || x.artwork === PLACEHOLDER || !fs.existsSync(path.join(ROOT, 'assets/images', x.artwork))) return SELECTION_IMAGE;
  return {file: `${IMAGE_DIR}/${slug(stem)}.jpg`, source: `assets/images/${x.artwork}`, width: 600, height: 600, alt: `Cover art: ${x.title}`};
}

// Pages: [{path, key, query, title, docTitle, description, image, heading}]
function pages(m) {
  const out = [];
  const add = page => out.push(page);
  for (const x of m.tracks) {
    const version = x.version ? ` (${m.label('version' + x.version, x.version)})` : '';
    const title = `${x.title}${version} · ${x.artist}`;
    const release = [m.label('type' + x.releaseType, x.releaseType), x.year].filter(v => v != null && v !== '').join(', ');
    const roles = list(x.roles.map(r => m.roleLabel(r).toLowerCase()));
    add({path: `music/song/${m.id(x)}/`, key: `song=${enc(m.id(x))}`, query: `song=${enc(m.id(x))}`, title,
      docTitle: m.artistsOf(x).includes('Luis Guinea') ? title : `${title} · Luis Guinea`,
      description: `${x.title} by ${x.artist}. Luis Guinea: ${roles}. ${release}. Listen to a preview of up to 45 seconds.`,
      image: imageFor(m, x), heading: x.title, sub: x.artist});
  }
  const selection = (where, extra) => {
    const found = m.tracks.filter(where).sort(m.byYear);
    if (!found.length) return null;
    const titles = list(found.slice(0, 3).map(x => x.title).concat(found.length > 3 ? ['more'] : []));
    const lead = extra ? extra(found) + ' ' : '';
    return {count: found.length, description: `${plural(found.length, 'recording', 'recordings')} from the catalogue of Luis Guinea. ${lead}Includes ${titles}. Previews, credits and links to listen.`};
  };
  const addSelection = (p, where, extra) => {
    const s = selection(where, extra);
    if (s) add(Object.assign({image: SELECTION_IMAGE, heading: p.title, sub: 'Luis Guinea · Music', docTitle: `${p.title} · Luis Guinea`, count: s.count, description: s.description}, p));
    return s;
  };
  // Artists: their credited name. Names that only differ in accents (Carla Calderon, Carla Calderón) are different
  // people: in alphabetical order the first keeps the plain slug and the next ones add -2, -3.
  const names = [...new Set(m.tracks.flatMap(m.artistsOf))].sort((a, b) => a.localeCompare(b, 'en'));
  const used = new Set();
  for (const name of names) {
    let s = slug(name) || 'artist', k = 2;
    while (used.has(s)) s = `${slug(name) || 'artist'}-${k++}`;
    used.add(s);
    const credits = found => `Luis Guinea's credits: ${list(ROLE_ORDER.filter(r => found.some(x => x.roles.includes(r))).map(r => m.roleLabel(r).toLowerCase()))}.`;
    addSelection({path: `music/artist/${s}/`, key: `artist=${enc(name)}`, query: `artist=${enc(name)}`, title: name, docTitle: `${name} · Music · Luis Guinea`},
      x => m.artistsOf(x).includes(name), credits);
  }
  const genres = m.terms('genre').map(m.genre), moods = m.terms('mood').map(m.mood);
  const hyphen = s => s.replace(/_/g, '-');
  for (const g of genres) addSelection({path: `music/genre/${hyphen(g.id)}/`, key: `genre=${g.id}`, query: `genre=${g.id}`, title: `${g.label} ${g.noun} by Luis Guinea`}, x => (x.genres || []).includes(g.id));
  for (const o of moods) addSelection({path: `music/mood/${o.id}/`, key: `mood=${o.id}`, query: `mood=${o.id}`, title: `${o.label} Songs by Luis Guinea`}, x => (x.moods || []).includes(o.id));
  for (const [c, credit] of Object.entries(CREDITS)) {
    const isCredit = x => m.matchesRole(x, credit.value);
    addSelection({path: `music/credit/${c}/`, key: `credit=${c}`, query: `credit=${c}`, title: credit.title}, isCredit);
    for (const g of genres) addSelection({path: `music/credit/${c}/${hyphen(g.id)}/`, key: `credit=${c}&genre=${g.id}`, query: `credit=${c}&genre=${g.id}`, title: credit.withGenre(g)},
      x => isCredit(x) && (x.genres || []).includes(g.id));
  }
  for (const g of genres) for (const o of moods) {
    const both = x => (x.genres || []).includes(g.id) && (x.moods || []).includes(o.id);
    if (m.tracks.filter(both).length < MIN_PAIR) continue;
    addSelection({path: `music/genre/${hyphen(g.id)}/${o.id}/`, key: `genre=${g.id}&mood=${o.id}`, query: `mood=${o.id}&genre=${g.id}`, title: `${o.label} ${g.label} ${g.noun} by Luis Guinea`}, both);
  }
  // The most frequent mood first, in the title and the path; the key keeps its ids sorted.
  const moodCount = o => m.tracks.filter(x => (x.moods || []).includes(o.id)).length;
  const common = moods.filter(o => moodCount(o) >= MIN_MOOD).sort((a, b) => moodCount(b) - moodCount(a) || (a.id < b.id ? -1 : 1));
  for (let i = 0; i < common.length; i++) for (let j = i + 1; j < common.length; j++) {
    const [a, b] = [common[i], common[j]], ids = [a.id, b.id].sort();
    addSelection({path: `music/mood/${a.id}-or-${b.id}/`, key: `mood=${ids.join(',')}`, query: `mood=${ids.join(',')}`, title: `${a.label} or ${b.label} Songs by Luis Guinea`},
      x => (x.moods || []).includes(a.id) || (x.moods || []).includes(b.id));
  }
  return out;
}

function html(p) {
  const url = SITE + p.path, image = SITE + p.image.file, depth = p.path.split('/').filter(Boolean).length;
  const target = '../'.repeat(depth - 1) + '?' + p.query;
  const fixed = JSON.stringify([...new Set(p.query.split('&').map(part => part.split('=')[0]))]);
  const card = p.image.width === p.image.height ? 'summary' : 'summary_large_image';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Generated by tools/build_share_pages.js. Do not edit. A link preview: crawlers read this page; visitors go on to the player. -->
<title>${esc(p.docTitle)}</title>
<meta name="description" content="${esc(p.description)}">
<meta name="robots" content="noindex">
<link rel="canonical" href="${esc(url)}">
<link rel="icon" href="data:,">
<meta property="og:type" content="website"><meta property="og:site_name" content="Luis Guinea"><meta property="og:locale" content="en_US">
<meta property="og:url" content="${esc(url)}">
<meta property="og:title" content="${esc(p.title)}">
<meta property="og:description" content="${esc(p.description)}">
<meta property="og:image" content="${esc(image)}"><meta property="og:image:type" content="image/jpeg"><meta property="og:image:width" content="${p.image.width}"><meta property="og:image:height" content="${p.image.height}"><meta property="og:image:alt" content="${esc(p.image.alt)}">
<meta name="twitter:card" content="${card}">
<meta name="twitter:title" content="${esc(p.title)}">
<meta name="twitter:description" content="${esc(p.description)}">
<meta name="twitter:image" content="${esc(image)}"><meta name="twitter:image:alt" content="${esc(p.image.alt)}">
<script>(function(){var t=${JSON.stringify(target)},fixed=${fixed},q=location.search.slice(1).split('&').filter(function(p){if(!p)return false;try{return fixed.indexOf(decodeURIComponent(p.split('=')[0].replace(/\\+/g,' ')))<0}catch(e){return false}});location.replace(t+(q.length?'&'+q.join('&'):'')+location.hash)})();</script>
<style>:root{color-scheme:light dark}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f2efe8;color:#111;font:1rem/1.5 system-ui,sans-serif}@media(prefers-color-scheme:dark){body{background:#111;color:#f2efe8}}main{max-width:36rem;padding:2rem 16px}p{margin:.5rem 0}.kicker{font:.75rem ui-monospace,monospace;text-transform:uppercase;letter-spacing:.08em}h1{font:400 clamp(2rem,8vw,3.5rem)/1 Georgia,serif;margin:.5rem 0}a{color:inherit;display:inline-flex;align-items:center;min-height:44px;text-underline-offset:4px}a:focus-visible{outline:3px solid #c4552b;outline-offset:3px}</style>
</head>
<body><main><p class="kicker">Luis Guinea · Music</p><h1>${esc(p.heading)}</h1><p>${esc(p.sub)}</p><p><a href="${esc(target)}">Listen to ${esc(p.heading)} on luisguinea.com</a></p></main></body>
</html>
`;
}

function manifest(list_) {
  const entries = list_.map(p => `  ${JSON.stringify(p.key)}: ${JSON.stringify(p.path)}`);
  return `// Generated by tools/build_share_pages.js. Do not edit.\n// Shareable selections that have a link-preview page: canonical filters (sorted names and values) -> page path.\nwindow.SHARE_PAGES = {\n${entries.join(',\n')}\n};\n`;
}

function expected() {
  const m = model(), list_ = pages(m), files = new Map();
  const seen = new Set();
  for (const p of list_) {
    if (seen.has(p.path)) throw new Error('duplicate page ' + p.path);
    seen.add(p.path);
    files.set(p.path + 'index.html', html(p));
  }
  files.set(MANIFEST, manifest(list_));
  return {files, pages: list_};
}

function existing() {
  const found = [];
  const walk = dir => { if (!fs.existsSync(path.join(ROOT, dir))) return; for (const e of fs.readdirSync(path.join(ROOT, dir), {withFileTypes: true})) { const rel = dir + '/' + e.name; if (e.isDirectory()) walk(rel); else found.push(rel); } };
  GENERATED_DIRS.forEach(walk);
  return found;
}

const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
// (width, height) from a JPEG's SOF marker, or null.
function jpegSize(buffer) {
  if (buffer[0] !== 0xff || buffer[1] !== 0xd8) return null;
  for (let i = 2; i + 9 < buffer.length;) {
    const marker = buffer[i + 1], length = buffer.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc2) return [buffer.readUInt16BE(i + 7), buffer.readUInt16BE(i + 5)];
    i += 2 + length;
  }
  return null;
}
const sourceOf = image => image.source || 'assets/images/cover.webp';
function lockFor(wanted) {
  const entries = {};
  for (const [file, image] of [...wanted].sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
    entries[file] = {source: sourceOf(image), source_sha256: sha256(path.join(ROOT, sourceOf(image))), sha256: sha256(path.join(ROOT, file)), width: image.width, height: image.height};
  }
  return JSON.stringify({generator: 'tools/build_share_pages.js --images', images: entries}, null, 2) + '\n';
}
function checkImages(wanted) {
  const problems = [];
  let lock = {};
  try { lock = JSON.parse(fs.readFileSync(path.join(ROOT, LOCK), 'utf8')).images || {}; } catch (e) { return ['missing or unreadable ' + LOCK]; }
  for (const [file, image] of wanted) {
    const entry = lock[file], target = path.join(ROOT, file);
    if (!fs.existsSync(target)) { problems.push('missing image ' + file); continue; }
    if (!entry) { problems.push('image not in the lock ' + file); continue; }
    if (entry.source !== sourceOf(image) || entry.source_sha256 !== sha256(path.join(ROOT, sourceOf(image)))) problems.push('cover changed, run --images: ' + file);
    if (entry.sha256 !== sha256(target)) problems.push('image differs from the lock ' + file);
    const size = jpegSize(fs.readFileSync(target));
    if (!size || size[0] !== image.width || size[1] !== image.height) problems.push('image is not a ' + image.width + 'x' + image.height + ' JPEG ' + file);
  }
  for (const file of Object.keys(lock)) if (!wanted.has(file)) problems.push('image no longer used ' + file);
  if (fs.existsSync(path.join(ROOT, IMAGE_DIR))) for (const name of fs.readdirSync(path.join(ROOT, IMAGE_DIR))) if (!wanted.has(`${IMAGE_DIR}/${name}`)) problems.push('stale image ' + `${IMAGE_DIR}/${name}`);
  return problems;
}

function wantedImages(list_) {
  const wanted = new Map();
  list_.forEach(p => { const known = wanted.get(p.image.file); if (known && known.source !== p.image.source) throw new Error('two covers share ' + p.image.file); wanted.set(p.image.file, p.image); });
  return wanted;
}

function images(list_, make) {
  const wanted = new Map();
  list_.forEach(p => { const known = wanted.get(p.image.file); if (known && known.source !== p.image.source) throw new Error('two covers share ' + p.image.file); wanted.set(p.image.file, p.image); });
  const missing = [];
  for (const [file, image] of wanted) {
    const target = path.join(ROOT, file);
    if (make) {
      fs.mkdirSync(path.dirname(target), {recursive: true});
      if (image.source) execFileSync('sips', ['-s', 'format', 'jpeg', '-s', 'formatOptions', '80', path.join(ROOT, image.source), '--out', target], {stdio: 'ignore'});
      else {
        execFileSync('sips', ['-s', 'format', 'jpeg', '-s', 'formatOptions', '80', '--resampleHeight', String(image.height), path.join(ROOT, 'assets/images/cover.webp'), '--out', target], {stdio: 'ignore'});
        execFileSync('sips', ['-c', String(image.height), String(image.width), target], {stdio: 'ignore'});
      }
    }
    if (!fs.existsSync(target)) missing.push(file);
  }
  if (make && fs.existsSync(path.join(ROOT, IMAGE_DIR))) {
    for (const name of fs.readdirSync(path.join(ROOT, IMAGE_DIR))) if (!wanted.has(`${IMAGE_DIR}/${name}`)) fs.unlinkSync(path.join(ROOT, IMAGE_DIR, name));
  }
  if (make && !missing.length) fs.writeFileSync(path.join(ROOT, LOCK), lockFor(wanted));
  return missing;
}

function main() {
  const check = process.argv.includes('--check'), make = process.argv.includes('--images');
  const {files, pages: list_} = expected();
  if (check) {
    const problems = [];
    for (const [rel, text] of files) {
      const file = path.join(ROOT, rel);
      if (!fs.existsSync(file)) problems.push('missing ' + rel);
      else if (fs.readFileSync(file, 'utf8') !== text) problems.push('out of date ' + rel);
    }
    for (const rel of existing()) if (!files.has(rel)) problems.push('stale ' + rel);
    problems.push(...checkImages(wantedImages(list_)));
    if (problems.length) { console.log(`SHARE PAGES OUT OF DATE (${problems.length}): run node tools/build_share_pages.js\n - ` + problems.slice(0, 20).join('\n - ')); process.exit(1); }
    console.log(`SHARE PAGES OK: ${list_.length} pages`);
    return;
  }
  for (const dir of GENERATED_DIRS) fs.rmSync(path.join(ROOT, dir), {recursive: true, force: true});
  for (const [rel, text] of files) { fs.mkdirSync(path.dirname(path.join(ROOT, rel)), {recursive: true}); fs.writeFileSync(path.join(ROOT, rel), text); }
  const missing = images(list_, make);
  const kinds = {};
  list_.forEach(p => { const k = p.path.split('/')[1]; kinds[k] = (kinds[k] || 0) + 1; });
  console.log(`SHARE PAGES WRITTEN: ${list_.length} pages ${JSON.stringify(kinds)}` + (missing.length ? `; missing images (run with --images on macOS): ${missing.length}` : ''));
}

if (require.main === module) main();
module.exports = {expected, html, SITE, IMAGE_DIR, SELECTION_IMAGE};
