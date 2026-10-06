// Minimal DOM for focused frontend tests, standard library only (no jsdom). It parses the real pages, runs their
// real scripts in a vm context and models the parts of the browser the site uses: elements and selectors, events
// with capture and bubbling, storage, media elements with an autoplay policy, BroadcastChannel, Media Session and
// IntersectionObserver. It is deliberately small; anything the site starts using must be added here.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const VOID = new Set(['img', 'input', 'br', 'meta', 'link', 'source', 'hr']);
const decode = s => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const kebab = k => k.replace(/[A-Z]/g, c => '-' + c.toLowerCase());

class Node {
  constructor(doc) { this.ownerDocument = doc; this.parentNode = null; this.childNodes = []; this.listeners = {}; }
  addEventListener(type, fn, options) {
    const capture = options === true || !!(options && options.capture);
    (this.listeners[type] = this.listeners[type] || []).push({fn, capture});
  }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter(l => l.fn !== fn); }
  dispatchEvent(event) { return this.ownerDocument._dispatch(this, event); }
  appendChild(child) { if (child.parentNode) child.remove(); child.parentNode = this; this.childNodes.push(child); return child; }
  contains(other) { for (let n = other; n; n = n.parentNode) if (n === this) return true; return false; }
  get children() { return this.childNodes.filter(n => n instanceof Element); }
  get textContent() { return this.childNodes.map(n => n.textContent).join(''); }
  set textContent(value) { this.childNodes.forEach(n => { n.parentNode = null; }); this.childNodes = []; if (value !== '' && value != null) this.appendChild(new Text(this.ownerDocument, String(value))); }
  querySelectorAll(selector) { const out = []; const list = parseSelector(selector); walk(this, el => { if (list.some(s => matchComplex(el, s, this))) out.push(el); }); return out; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
class Text extends Node {
  constructor(doc, data) { super(doc); this.data = data; }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v); }
}
function walk(node, fn) { node.childNodes.forEach(c => { if (c instanceof Element) { fn(c); walk(c, fn); } }); }

class Element extends Node {
  constructor(doc, tag, attrs) {
    super(doc);
    this.tagName = tag.toUpperCase(); this.localName = tag.toLowerCase(); this.attrs = Object.assign({}, attrs || {});
    this.style = {}; this._value = this.attrs.value || ''; this.rect = {top: 0, height: 0};
    const self = this;
    this.dataset = new Proxy({}, {
      get: (o, k) => self.attrs['data-' + kebab(String(k))],
      set: (o, k, v) => { self.attrs['data-' + kebab(String(k))] = String(v); return true; },
      deleteProperty: (o, k) => { delete self.attrs['data-' + kebab(String(k))]; return true; },
      has: (o, k) => ('data-' + kebab(String(k))) in self.attrs,
    });
    this.classList = {
      list: () => (self.attrs.class || '').split(/\s+/).filter(Boolean),
      contains(c) { return this.list().includes(c); },
      add(...cs) { const s = new Set(this.list()); cs.forEach(c => s.add(c)); self.attrs.class = [...s].join(' '); },
      remove(...cs) { const s = new Set(this.list()); cs.forEach(c => s.delete(c)); self.attrs.class = [...s].join(' '); },
      toggle(c, force) { const on = force === undefined ? !this.contains(c) : !!force; if (on) this.add(c); else this.remove(c); return on; },
    };
  }
  get id() { return this.attrs.id || ''; }
  get className() { return this.attrs.class || ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }
  removeAttribute(k) { delete this.attrs[k]; }
  get hidden() { return 'hidden' in this.attrs; }
  set hidden(v) { if (v) this.attrs.hidden = ''; else delete this.attrs.hidden; }
  get disabled() { return 'disabled' in this.attrs; }
  set disabled(v) { if (v) this.attrs.disabled = ''; else delete this.attrs.disabled; }
  get value() { return this._value; }
  set value(v) { this._value = String(v); }
  get max() { return this.attrs.max; }
  set max(v) { this.attrs.max = String(v); }
  get src() { return this.attrs.src || ''; }
  set src(v) { this.attrs.src = String(v); }
  get alt() { return this.attrs.alt || ''; }
  set alt(v) { this.attrs.alt = String(v); }
  get href() { return this.attrs.href || ''; }
  get placeholder() { return this.attrs.placeholder || ''; }
  set placeholder(v) { this.attrs.placeholder = String(v); }
  get innerHTML() { return this.childNodes.map(serialize).join(''); }
  set innerHTML(html) { this.childNodes.forEach(n => { n.parentNode = null; }); this.childNodes = []; parseInto(this, html, this.ownerDocument); }
  remove() { if (this.parentNode) { this.parentNode.childNodes = this.parentNode.childNodes.filter(n => n !== this); this.parentNode = null; } }
  closest(selector) { const list = parseSelector(selector); for (let n = this; n instanceof Element; n = n.parentNode) if (list.some(s => matchComplex(n, s, null))) return n; return null; }
  matches(selector) { return parseSelector(selector).some(s => matchComplex(this, s, null)); }
  getBoundingClientRect() { return {top: this.rect.top, bottom: this.rect.top + this.rect.height, height: this.rect.height, left: 0, width: 0}; }
  focus() { this.ownerDocument.activeElement = this; }
  click() { this.ownerDocument._userClick(this); }
}

class Media extends Element {
  constructor(doc, attrs) {
    super(doc, 'audio', attrs);
    this.paused = true; this.ended = false; this.currentTime = 0; this.duration = NaN; this.readyState = 0;
    this.preload = 'auto'; this.muted = false; this._volume = 1;
  }
  get src() { return this.attrs.src || ''; }
  set src(v) {
    this.attrs.src = String(v); this.paused = true; this.ended = false; this.currentTime = 0; this.duration = NaN; this.readyState = 0;
    this.ownerDocument._log('src:' + this.label + ':' + v); this._fire('emptied');
  }
  get label() { return this.attrs.id || 'engine'; }
  get volume() { return this._volume; }
  set volume(v) { if (!this.ownerDocument._page.fixedVolume) this._volume = Number(v); }
  play() {
    const page = this.ownerDocument._page;
    if (!this.attrs.src) return Promise.reject(Object.assign(new Error('no source'), {name: 'NotSupportedError'}));
    // Like browsers, an element the user started once may keep playing (next preview after `ended`) without a new gesture.
    if (page.autoplayBlocked && !page.gesture && !this.activated) {
      this.ownerDocument._log('blocked:' + this.label);
      return Promise.reject(Object.assign(new Error('autoplay blocked'), {name: 'NotAllowedError'}));
    }
    if (page.gesture) this.activated = true;
    if (this.paused) { this.paused = false; this.ended = false; this.ownerDocument._log('play:' + this.label); this._fire('play'); }
    return Promise.resolve();
  }
  pause() { if (!this.paused) { this.paused = true; this.ownerDocument._log('pause:' + this.label); this._fire('pause'); } }
  // Test helpers: the media "network" is driven explicitly by the scenario.
  loadMetadata(duration) { this.readyState = 1; this.duration = duration; this._fire('loadedmetadata'); this._fire('durationchange'); }
  advance(seconds) { this.currentTime += seconds; this._fire('timeupdate'); }
  finish() { this.currentTime = this.duration; this.paused = true; this.ended = true; this._fire('pause'); this._fire('ended'); }
  _fire(type) { this.ownerDocument._dispatch(this, {type, bubbles: false}); }
}

function serialize(n) {
  if (n instanceof Text) return n.data.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const attrs = Object.entries(n.attrs).map(([k, v]) => v === '' ? ' ' + k : ` ${k}="${String(v).replace(/"/g, '&quot;')}"`).join('');
  return VOID.has(n.localName) ? `<${n.localName}${attrs}>` : `<${n.localName}${attrs}>${n.childNodes.map(serialize).join('')}</${n.localName}>`;
}

function parseAttrs(source) {
  const attrs = {};
  for (const a of source.matchAll(/([^\s=/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
    const v = a[2] !== undefined ? a[2] : a[3] !== undefined ? a[3] : a[4];
    attrs[a[1]] = v === undefined ? '' : decode(v);
  }
  return attrs;
}
function parseInto(parent, html, doc) {
  const re = /<!--[\s\S]*?-->|<!doctype[^>]*>|<(\/?)([a-zA-Z][\w-]*)((?:"[^"]*"|'[^']*'|[^'">])*)>|([^<]+)/gi;
  let current = parent, m;
  while ((m = re.exec(html))) {
    if (m[4] !== undefined) { current.appendChild(new Text(doc, decode(m[4]))); continue; }
    if (!m[2]) continue;
    const tag = m[2].toLowerCase();
    if (m[1]) { for (let n = current; n && n !== parent; n = n.parentNode) if (n.localName === tag) { current = n.parentNode; break; } continue; }
    const attrs = parseAttrs(m[3].replace(/\/$/, ''));
    const el = tag === 'audio' || tag === 'video' ? new Media(doc, attrs) : new Element(doc, tag, attrs);
    current.appendChild(el);
    if (tag === 'script' || tag === 'style') {
      const end = html.toLowerCase().indexOf('</' + tag, re.lastIndex);
      el.childNodes.push(Object.assign(new Text(doc, html.slice(re.lastIndex, end)), {parentNode: el}));
      re.lastIndex = html.indexOf('>', end) + 1;
    } else if (!VOID.has(tag) && !/\/$/.test(m[3])) current = el;
  }
}

// Selectors: lists, descendant and child combinators, tag, #id, .class, [attr], [attr=v], [attr^=v].
function parseSelector(selector) {
  return selector.split(',').map(part => {
    const tokens = part.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/);
    const steps = []; let combinator = ' ';
    tokens.forEach(tok => { if (tok === '>') combinator = '>'; else { steps.push({combinator, compound: parseCompound(tok)}); combinator = ' '; } });
    return steps;
  });
}
function parseCompound(tok) {
  const c = {tag: null, id: null, classes: [], attrs: []};
  for (const m of tok.matchAll(/^[a-zA-Z*][\w-]*|#[\w-]+|\.[\w-]+|\[([\w-]+)(?:([\^]?=)"?([^"\]]*)"?)?\]/g)) {
    const s = m[0];
    if (s[0] === '#') c.id = s.slice(1);
    else if (s[0] === '.') c.classes.push(s.slice(1));
    else if (s[0] === '[') c.attrs.push({name: m[1], op: m[2] || null, value: m[3]});
    else if (s !== '*') c.tag = s.toLowerCase();
  }
  return c;
}
function matchCompound(el, c) {
  if (!(el instanceof Element)) return false;
  if (c.tag && el.localName !== c.tag) return false;
  if (c.id && el.attrs.id !== c.id) return false;
  if (c.classes.some(k => !el.classList.contains(k))) return false;
  return c.attrs.every(a => {
    if (!(a.name in el.attrs)) return false;
    if (a.op === '=') return el.attrs[a.name] === a.value;
    if (a.op === '^=') return el.attrs[a.name].startsWith(a.value);
    return true;
  });
}
function matchComplex(el, steps, scope) {
  const match = (node, i) => {
    if (!matchCompound(node, steps[i].compound)) return false;
    if (i === 0) return !scope || scope.contains(node) && node !== scope;
    if (steps[i].combinator === '>') return match(node.parentNode, i - 1);
    for (let p = node.parentNode; p instanceof Element; p = p.parentNode) if (match(p, i - 1)) return true;
    return false;
  };
  return match(el, steps.length - 1);
}

class Document extends Node {
  constructor(page) {
    super(null); this.ownerDocument = this; this._page = page; this.activeElement = null; this.currentScript = null;
  }
  get documentElement() { return this.children.find(e => e.localName === 'html'); }
  get body() { return this.querySelector('body'); }
  createElement(tag) { return tag.toLowerCase() === 'audio' || tag.toLowerCase() === 'video' ? this._track(new Media(this, {})) : new Element(this, tag, {}); }
  _track(media) { this._page.created.push(media); return media; }
  getElementById(id) { return this.querySelector('#' + id); }
  _log(entry) { this._page.log.push(entry); }
  _dispatch(target, event) {
    const ev = Object.assign({bubbles: false, defaultPrevented: false}, event);
    ev.target = target; ev.preventDefault = () => { ev.defaultPrevented = true; }; ev.stopPropagation = () => {};
    const chain = [];
    for (let n = target.parentNode; n; n = n.parentNode) chain.unshift(n);
    const attached = chain[0] === this;
    const call = (node, capture) => (node.listeners[ev.type] || []).filter(l => capture === null || l.capture === capture).forEach(l => { ev.currentTarget = node; l.fn.call(node, ev); });
    if (attached) chain.forEach(n => call(n, true));
    call(target, null);
    if (attached && ev.bubbles) chain.slice().reverse().forEach(n => call(n, false));
    return !ev.defaultPrevented;
  }
  _userClick(el) { this._page.gesture = true; try { this._dispatch(el, {type: 'click', bubbles: true}); } finally { this._page.gesture = false; } }
}

function makeStorage(backing) {
  return {
    getItem: k => (Object.prototype.hasOwnProperty.call(backing, k) ? backing[k] : null),
    setItem: (k, v) => { backing[k] = String(v); },
    removeItem: k => { delete backing[k]; },
  };
}

// One browser "tab": pages opened in it share sessionStorage and window.name.
class Browser {
  constructor(root) { this.root = root; this.local = {}; this.bus = []; this.randomQueue = []; }
  random() { return this.randomQueue.length ? this.randomQueue.shift() : 0.5; }
  tab(options) { return new Tab(this, options || {}); }
}
class Tab {
  constructor(browser, options) {
    this.browser = browser; this.session = Object.assign({}, options.session || {}); this.name = options.name || '';
    this.page = null;
  }
  // Back button with the back/forward cache: the previous page object comes back as it was left.
  back(previous) {
    this.page.window._fire('pagehide', {persisted: true}); this.page.closed = true;
    previous.closed = false; this.page = previous;
    previous.window._fire('pageshow', {persisted: true});
    return previous;
  }
  open(rel, options) {
    if (this.page) { this.page.window._fire('pagehide'); this.page.closed = true; this.name = this.page.window.name; }
    this.page = new Page(this, rel, options || {});
    return this.page;
  }
}

class Page {
  constructor(tab, rel, options) {
    this.tab = tab; this.rel = rel; this.log = []; this.created = []; this.gesture = false; this.closed = false;
    this.autoplayBlocked = options.autoplayBlocked !== false; this.fixedVolume = !!options.fixedVolume;
    this.mediaSession = options.mediaSession === false ? undefined : {metadata: null, playbackState: 'none', handlers: {}, setActionHandler(a, fn) { this.handlers[a] = fn; }};
    this.observers = [];
    const browser = tab.browser;
    const html = fs.readFileSync(path.join(browser.root, rel), 'utf8');
    const doc = this.document = new Document(this);
    parseInto(doc, html, doc);
    const url = 'http://test.local/' + rel;
    const page = this;
    const win = this.window = {
      name: tab.name, innerHeight: 800, scrollY: 0, listeners: {},
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      _fire(type, extra) { (this.listeners[type] || []).forEach(fn => fn(Object.assign({type}, extra))); },
    };
    class BroadcastChannel {
      constructor(name) { this.name = name; this.onmessage = null; this.closed = false; browser.bus.push(this); this.page = page; }
      postMessage(data) { browser.bus.filter(c => c !== this && c.name === this.name && !c.page.closed && c.onmessage).forEach(c => setImmediate(() => c.onmessage({data}))); }
      close() { this.closed = true; }
    }
    class IntersectionObserver {
      constructor(cb) { this.cb = cb; this.targets = []; page.observers.push(this); }
      observe(el) { this.targets.push(el); }
      trigger(isIntersecting) { this.cb(this.targets.map(target => ({target, isIntersecting}))); }
    }
    class CustomEvent { constructor(type, init) { this.type = type; this.detail = init && init.detail; } }
    class MediaMetadata { constructor(init) { Object.assign(this, init); } }
    const ctx = {
      document: doc, location: {href: url, pathname: '/' + rel}, console, URL, JSON, Promise, Date, setTimeout, clearTimeout, setImmediate,
      localStorage: makeStorage(browser.local), sessionStorage: makeStorage(tab.session),
      navigator: options.mediaSession === false ? {} : {mediaSession: this.mediaSession},
      BroadcastChannel: options.broadcastChannel === false ? undefined : BroadcastChannel,
      IntersectionObserver, CustomEvent, MediaMetadata,
      requestAnimationFrame: fn => setImmediate(fn),
      matchMedia: () => ({matches: false, addEventListener() {}}),
    };
    Object.assign(win, ctx);
    win.window = win;
    vm.createContext(win);
    vm.runInContext('Math.random = __random; delete this.__random;', Object.assign(win, {__random: () => browser.random()}));
    for (const script of doc.querySelectorAll('script')) {
      const src = script.getAttribute('src');
      const type = script.getAttribute('type');
      if (type && type !== 'text/javascript' && type !== 'module') continue;
      if (!src) { vm.runInContext(script.textContent, win); continue; }
      const file = path.posix.normalize(path.posix.join(path.posix.dirname(rel), src));
      doc.currentScript = {src: 'http://test.local/' + file};
      vm.runInContext(fs.readFileSync(path.join(browser.root, file), 'utf8'), win, {filename: file});
      doc.currentScript = null;
    }
    doc._dispatch(doc, {type: 'DOMContentLoaded'});
  }
  $(selector) { return this.document.querySelector(selector); }
  $$(selector) { return this.document.querySelectorAll(selector); }
  click(target) { const el = typeof target === 'string' ? this.$(target) : target; if (!el) throw new Error('no element ' + target); el.click(); }
  input(selector, value) { const el = this.$(selector); el.value = String(value); this.document._dispatch(el, {type: 'input', bubbles: true}); }
  change(selector, value) { const el = this.$(selector); el.value = String(value); this.document._dispatch(el, {type: 'change', bubbles: true}); }
  key(key) { this.document._dispatch(this.document.activeElement || this.document.body, {type: 'keydown', key, bubbles: true}); }
  get engineAudio() { return this.created.filter(m => m instanceof Media); }
  audio() { return this.created[0]; }
  eval(code) { return vm.runInContext(code, this.window); }
}

const settle = () => new Promise(resolve => setImmediate(() => setImmediate(resolve)));

module.exports = {Browser, Media, settle};
