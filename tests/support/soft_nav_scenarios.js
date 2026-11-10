// Runs js/soft-nav.js in a vm with a minimal browser stub and prints {scenario: "ok" | failure}. Driven by
// tests/test_soft_nav.py. Covers what does not need a real browser: which links keep a traditional navigation, scope
// tracking and release of page listeners, timers and subscriptions, and inertness without the needed APIs. Continuity of
// the audio element itself was verified in Chrome (see the mission report).
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const CODE = fs.readFileSync(path.join(__dirname, '..', '..', 'js', 'soft-nav.js'), 'utf8');

function makeTarget() {
  const map = {};
  return {
    map,
    addEventListener(type, fn) { (map[type] = map[type] || []).push(fn); },
    removeEventListener(type, fn) { const l = map[type] || []; const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); },
    count(type) { return (map[type] || []).length; },
  };
}

function boot(opts = {}) {
  const win = makeTarget(), doc = makeTarget();
  const timers = new Set();
  let nextId = 1;
  const ctx = {
    URL, Promise, Object, Array, Error, RegExp, JSON, Math, String, Number, Event: class { constructor(t) { this.type = t; } },
    CustomEvent: class { constructor(t, i) { this.type = t; this.detail = i && i.detail; } },
    Element: function () {}, AbortController, AbortSignal,
    location: { href: 'http://test.local/formacion/', origin: 'http://test.local', pathname: '/formacion/', search: '', hash: '' },
    history: { state: null, pushState() {}, replaceState() {} },
    setTimeout: () => { const id = nextId++; timers.add(id); return id; },
    clearTimeout: id => timers.delete(id),
    setInterval: () => { const id = nextId++; timers.add(id); return id; },
    clearInterval: id => timers.delete(id),
    fetch: opts.noFetch ? undefined : () => new Promise(() => {}),
    DOMParser: opts.noParser ? undefined : function () {},
    matchMedia: () => { const t = makeTarget(); t.matches = false; return t; },
    IntersectionObserver: function () { this.disconnected = false; this.disconnect = () => { this.disconnected = true; }; },
  };
  ctx.Element.prototype.closest = function () { return null; };
  doc.body = { replaceChildren() {} };
  doc.querySelector = () => null;
  doc.currentScript = null;
  win.document = doc;
  Object.assign(ctx, { window: null, document: doc });
  // window and the global object are the same thing, as in a browser.
  Object.assign(win, ctx);
  win.window = win;
  vm.createContext(win);
  vm.runInContext(CODE, win);
  return { win, doc, timers };
}

function link(href, attrs = {}) {
  return { getAttribute: name => (name === 'href' ? href : name in attrs ? attrs[name] : null), hasAttribute: name => name in attrs };
}

const scenarios = {
  inert_without_the_needed_apis() {
    assert.strictEqual(boot({ noFetch: true }).win.LGSoftNav, undefined);
    assert.strictEqual(boot({ noParser: true }).win.LGSoftNav, undefined);
  },
  internal_pages_are_loaded_without_reload() {
    const { win } = boot();
    ['../cv.html', 'piano/', '../', '../#background', '../music/', '?area=armonia#consulta', '../agenda/', '../sobre-mi.html']
      .forEach(h => assert.ok(win.LGSoftNav.eligible(link(h)), h));
  },
  traditional_navigation_is_kept_where_it_is_needed() {
    const { win } = boot();
    const native = ['#consulta', 'https://www.instagram.com/soyluisguinea/', 'mailto:a@example.org', 'tel:+34000',
      '../assets/audio/previews/x.mp3', '../sitemap.xml', '../assets/images/profile.webp', '../music/?credit=producer',
      '../music/?song=toxic--isabella-macias--2018', '../music/?genre=pop', '../music/song/toxic--isabella-macias--2018/',
      '../agenda/#confirm=abc', '../agenda/#manage=abc', 'javascript:void(0)'];
    native.forEach(h => assert.strictEqual(win.LGSoftNav.eligible(link(h)), null, h));
    assert.strictEqual(win.LGSoftNav.eligible(link('../cv.html', { download: '' })), null, 'download');
    assert.strictEqual(win.LGSoftNav.eligible(link('../cv.html', { target: '_blank' })), null, 'new tab');
    assert.strictEqual(win.LGSoftNav.eligible(link('../cv.html', { rel: 'external noopener' })), null, 'rel external');
    assert.strictEqual(win.LGSoftNav.eligible(link('../cv.html', { 'data-no-soft': '' })), null, 'opt-out');
    assert.ok(win.LGSoftNav.eligible(link('../cv.html', { target: '_self' })), 'target _self');
  },
  page_listeners_timers_and_subscriptions_are_recorded() {
    const { win, doc } = boot();
    const before = win.LGSoftNav.scopeSize();
    win.addEventListener('scroll', () => {});
    doc.addEventListener('keydown', () => {});
    win.setTimeout(() => {}, 10);
    win.setInterval(() => {}, 10);
    new win.IntersectionObserver(() => {});
    win.matchMedia('(min-width: 701px)').addEventListener('change', () => {});
    win.LGSoftNav.track(() => {});
    const after = win.LGSoftNav.scopeSize();
    assert.strictEqual(after.listeners - before.listeners, 2);
    assert.deepStrictEqual([after.timeouts, after.intervals, after.observers, after.media, after.offs], [1, 1, 1, 1, 1]);
  },
  persistent_scripts_are_not_recorded() {
    const { win, doc } = boot();
    const before = win.LGSoftNav.scopeSize().listeners;
    doc.currentScript = { src: 'http://test.local/js/player.js' };
    doc.addEventListener('play', () => {}, true);
    win.addEventListener('pagehide', () => {});
    doc.currentScript = { src: 'http://test.local/js/site.js' };
    doc.addEventListener('keydown', () => {});
    doc.currentScript = null;
    assert.strictEqual(win.LGSoftNav.scopeSize().listeners - before, 1, 'only site.js counts as page code');
    // ...unless the persistent script explicitly runs page code (the player views).
    doc.currentScript = { src: 'http://test.local/js/player.js' };
    win.LGSoftNav.page(() => doc.addEventListener('lg:language', () => {}));
    doc.currentScript = null;
    assert.strictEqual(win.LGSoftNav.scopeSize().listeners - before, 2);
  },
  own_listeners_are_installed_once() {
    const { win, doc } = boot();
    assert.strictEqual(doc.count('click'), 1);
    assert.strictEqual(win.count('popstate'), 1);
  },
};

const results = {};
Object.keys(scenarios).forEach(name => {
  try { scenarios[name](); results[name] = 'ok'; } catch (e) { results[name] = String(e && e.stack || e).split('\n').slice(0, 3).join(' | '); }
});
process.stdout.write(JSON.stringify(results));
