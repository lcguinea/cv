// Internal navigation without reload (progressive enhancement), so the one global <audio> of js/player.js keeps playing
// across pages instead of being destroyed and restored. Loaded first on every page that shares the site shell.
//
// How it works: a click on an eligible internal link fetches the next page, swaps <body> and the page metadata in
// <head>, updates the URL with the History API and runs that page's scripts again in order. The engine (player.js) and
// the catalogue data (music-data.js) are never re-run: their state, and the audio element, survive. Back and Forward
// load the entry the same way. Whatever this layer cannot handle falls back to a normal navigation: unsupported
// browsers, external links, downloads, new tabs, modified clicks, in-page anchors, shared /music/ links (they start
// what they point at on a full load), agenda token links, pages outside the shell (404, link-preview pages) and any
// error while fetching or initialising the next page. Without JavaScript every link is a plain link.
//
// Page scripts were written to run once per document, so each page runs in a scope: listeners added to window and
// document, timers, observers, matchMedia listeners and LGPlayer.on subscriptions made by page code are recorded and
// released before the next page starts. Listeners of the persistent scripts (this file, player.js, music-data.js)
// are never recorded. Opt out of one link with data-no-soft.
(function () {
  'use strict';
  if (!(window.fetch && window.DOMParser && window.history && history.pushState && window.Promise && window.URL &&
        document.querySelector && Element.prototype.closest && document.body && document.body.replaceChildren)) return;

  var PERSISTENT = /\/js\/(?:soft-nav|player|music-data)\.js(?:[?#]|$)/;
  var SKIP = /\/js\/(?:soft-nav|music-data|theme-init)\.js(?:[?#]|$)/;
  var PLAYER = /\/js\/player\.js(?:[?#]|$)/;
  var ASSET = /\.(?:pdf|mp3|wav|m4a|zip|xml|txt|json|webp|jpe?g|png|gif|svg|ico|css|js|woff2?)$/i;
  var HEAD_META = 'title,meta[name="description"],meta[name="robots"],meta[property^="og:"],meta[name^="twitter:"],' +
    'link[rel="canonical"],script[type="application/ld+json"]';
  var origAdd = { win: window.addEventListener, doc: document.addEventListener };
  var native = { fetch: window.fetch, setTimeout: window.setTimeout, setInterval: window.setInterval, clearTimeout: window.clearTimeout,
    clearInterval: window.clearInterval, matchMedia: window.matchMedia };
  var depth = 0, docId = 1, docKey = location.pathname, controller = null, busy = false;
  var scope = newScope();

  function newScope() { return { alive: true, abort: window.AbortController ? new AbortController() : null, listeners: [], timeouts: [], intervals: [], observers: [], media: [], offs: [] }; }
  // Registrations made directly by a persistent script while it runs belong to the shell, everything else to the page.
  function pageOwned() {
    if (depth > 0) return true;
    var s = document.currentScript;
    return !(s && s.src && PERSISTENT.test(s.src));
  }

  // ---------- scope tracking ----------
  [[window, 'win'], [document, 'doc']].forEach(function (pair) {
    var target = pair[0], add = origAdd[pair[1]];
    target.addEventListener = function (type, fn, options) {
      add.call(target, type, fn, options);
      if (fn && pageOwned()) scope.listeners.push([target, type, fn, options]);
    };
  });
  window.setTimeout = function () {
    var id = native.setTimeout.apply(window, arguments);
    if (pageOwned()) scope.timeouts.push(id);
    return id;
  };
  window.setInterval = function () {
    var id = native.setInterval.apply(window, arguments);
    if (pageOwned()) scope.intervals.push(id);
    return id;
  };
  ['IntersectionObserver', 'MutationObserver', 'ResizeObserver'].forEach(function (name) {
    var Base = window[name];
    if (typeof Base !== 'function') return;
    var Tracked = function (callback, options) {
      var instance = new Base(callback, options);
      if (pageOwned()) scope.observers.push(instance);
      return instance;
    };
    Tracked.prototype = Base.prototype;
    window[name] = Tracked;
  });
  // Requests of page code end with the page, as on a traditional navigation: they are aborted, and neither they nor
  // reading their body settle afterwards, so no callback of a page that is gone runs (or writes into the next one).
  function gate(promise, owner) {
    return new Promise(function (resolve, reject) {
      promise.then(function (v) { if (owner.alive) resolve(v); }, function (e) { if (owner.alive) reject(e); });
    });
  }
  window.fetch = function (input, init) {
    var owner = scope;
    if (!pageOwned() || !owner.abort) return native.fetch.apply(window, arguments);
    var options = Object.assign({}, init || {}), own = owner.abort.signal, given = options.signal;
    if (given && AbortSignal.any) options.signal = AbortSignal.any([given, own]);
    else if (given) { given.addEventListener('abort', function () { owner.abort.abort(); }); options.signal = own; }
    else options.signal = own;
    return gate(native.fetch.call(window, input, options).then(function (res) {
      ['json', 'text', 'blob', 'arrayBuffer', 'formData'].forEach(function (name) {
        var read = res[name];
        if (typeof read === 'function') res[name] = function () { return gate(read.call(res), owner); };
      });
      return res;
    }), owner);
  };
  if (native.matchMedia) window.matchMedia = function (query) {
    var list = native.matchMedia.call(window, query);
    if (pageOwned() && list) {
      var add = list.addEventListener, addListener = list.addListener;
      if (add) list.addEventListener = function (type, fn, options) { add.call(list, type, fn, options); scope.media.push([list, type, fn, options]); };
      if (addListener) list.addListener = function (fn) { addListener.call(list, fn); scope.media.push([list, 'change', fn]); };
    }
    return list;
  };

  function teardown() {
    var old = scope;
    scope = newScope();
    old.alive = false;
    if (old.abort) try { old.abort.abort(); } catch (e) {}
    old.listeners.forEach(function (l) { try { l[0].removeEventListener(l[1], l[2], l[3]); } catch (e) {} });
    old.media.forEach(function (l) { try { l[0].removeEventListener(l[1], l[2], l[3]); } catch (e) {} });
    old.timeouts.forEach(function (id) { native.clearTimeout.call(window, id); });
    old.intervals.forEach(function (id) { native.clearInterval.call(window, id); });
    old.observers.forEach(function (o) { try { o.disconnect(); } catch (e) {} });
    old.offs.forEach(function (off) { try { off(); } catch (e) {} });
    return old;
  }

  // ---------- which links ----------
  function eligible(a) {
    if (a.hasAttribute('download') || a.hasAttribute('data-no-soft')) return null;
    var target = a.getAttribute('target');
    if (target && target !== '_self') return null;
    if (/(?:^|\s)external(?:\s|$)/.test(a.getAttribute('rel') || '')) return null;
    var url;
    try { url = new URL(a.getAttribute('href'), location.href); } catch (e) { return null; }
    if (url.origin !== location.origin || !/^https?:$/.test(url.protocol) || ASSET.test(url.pathname)) return null;
    // In-page anchors stay native.
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return null;
    // Shared /music/ links (a recording or filters) start what they point at only on a full load (js/player.js).
    if (/\/music\/$/.test(url.pathname) && /[?&](?:song|q|artist|credit|mood|genre)=/.test(url.search)) return null;
    if (/\/music\/(?:song|artist|credit|genre|mood)\//.test(url.pathname)) return null;
    // Booking confirmation and management links carry a token for js/agenda.js.
    if (/^#(?:confirm|manage)=/.test(url.hash)) return null;
    return url;
  }

  function onClick(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var a = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!a) return;
    var url = eligible(a);
    if (!url) return;
    event.preventDefault();
    navigate(url.href, { push: true });
  }

  // ---------- navigation ----------
  function hard(url, replace) { if (replace) location.replace(url); else location.assign(url); }

  function scriptUrls(doc, base) {
    return Array.prototype.map.call(doc.body.querySelectorAll('script'), function (s) {
      var src = s.getAttribute('src');
      return src ? { src: new URL(src, base).href } : { code: s.textContent };
    });
  }

  function load(url, signal) {
    return native.fetch.call(window, url, { credentials: 'same-origin', signal: signal, headers: { Accept: 'text/html' } }).then(function (res) {
      var type = res.headers.get('content-type') || '';
      if (!res.ok || !/text\/html/i.test(type)) throw new Error('not a page');
      // Response.url never carries the fragment: keep the one of the link (#background, #consulta).
      var finalUrl = res.url || url, hash = new URL(url).hash;
      if (hash && !new URL(finalUrl).hash) finalUrl = finalUrl.split('#')[0] + hash;
      if (new URL(finalUrl).origin !== location.origin) throw new Error('left the site');
      return res.text().then(function (text) {
        var doc = new DOMParser().parseFromString(text, 'text/html');
        // Only pages that share the shell take part: same engine, same mini player, this script.
        if (!doc.getElementById('mini-player') || !doc.querySelector('script[src$="soft-nav.js"]')) throw new Error('outside the shell');
        var scripts = scriptUrls(doc, finalUrl);
        return Promise.all(scripts.map(function (s) {
          if (!s.src || SKIP.test(s.src) || PLAYER.test(s.src)) return Promise.resolve(s);
          return native.fetch.call(window, s.src, { credentials: 'same-origin', signal: signal }).then(function (r) {
            if (!r.ok) throw new Error('script ' + s.src);
            return r.text().then(function (code) { s.code = code; return s; });
          });
        })).then(function (ready) { return { doc: doc, url: finalUrl, scripts: ready }; });
      });
    });
  }

  function swapHead(doc) {
    var head = document.head;
    Array.prototype.forEach.call(head.querySelectorAll(HEAD_META), function (n) { n.remove(); });
    var anchor = head.querySelector('script[src$="theme-init.js"]') || null;
    Array.prototype.forEach.call(doc.head.querySelectorAll(HEAD_META), function (n) { head.insertBefore(document.importNode(n, true), anchor); });
    var html = document.documentElement, next = doc.documentElement;
    ['lang', 'data-lang-default'].forEach(function (name) {
      if (next.hasAttribute(name)) html.setAttribute(name, next.getAttribute(name)); else html.removeAttribute(name);
    });
    html.classList.remove('menu-open');
  }

  function swapBody(doc) {
    var fresh = doc.body;
    Array.prototype.forEach.call(fresh.querySelectorAll('script'), function (s) { s.remove(); });
    Array.prototype.slice.call(document.body.attributes).forEach(function (a) { document.body.removeAttribute(a.name); });
    Array.prototype.forEach.call(fresh.attributes, function (a) { document.body.setAttribute(a.name, a.value); });
    // childNodes is live and adoptNode moves each node out of it: copy the list first.
    var nodes = Array.prototype.slice.call(fresh.childNodes).map(function (n) { return document.adoptNode(n); });
    document.body.replaceChildren.apply(document.body, nodes);
    if (!document.querySelector('main') || !document.getElementById('mini-player')) throw new Error('incomplete page');
  }

  // Runs the page scripts synchronously, in order, as inline scripts (no flash of untranslated text). player.js is
  // replaced by mounting its views on the new markup; the engine keeps running.
  function runScripts(scripts) {
    var failed = false;
    function onError() { failed = true; }
    origAdd.win.call(window, 'error', onError);
    depth++;
    try {
      scripts.forEach(function (s) {
        if (failed) return;
        if (s.src && PLAYER.test(s.src)) { if (window.LGPlayerViews) window.LGPlayerViews(); return; }
        if (s.src && SKIP.test(s.src)) return;
        var el = document.createElement('script');
        el.textContent = s.code + (s.src ? '\n//# sourceURL=' + s.src : '');
        document.body.appendChild(el);
        el.remove();
      });
      // Scripts that wait for these events (i18n.js binds the language buttons on DOMContentLoaded).
      document.dispatchEvent(new Event('DOMContentLoaded', { bubbles: true }));
      window.dispatchEvent(new Event('load'));
    } finally {
      depth--;
      window.removeEventListener('error', onError);
    }
    return !failed;
  }

  function settle(url, state) {
    var hash = new URL(url).hash, target = null;
    if (hash) { try { target = document.getElementById(decodeURIComponent(hash.slice(1))); } catch (e) { target = null; } }
    if (state && typeof state.scrollY === 'number') window.scrollTo({ top: state.scrollY, left: 0, behavior: 'instant' });
    else if (target && target.scrollIntoView) target.scrollIntoView({ behavior: 'instant', block: 'start' });
    else window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    // Keyboard and screen reader users land on the new content, and hear the new page title.
    if (!target) {
      var main = document.getElementById('content') || document.querySelector('main');
      if (main) {
        if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');
        try { main.focus({ preventScroll: true }); } catch (e) { main.focus(); }
      }
    }
    var status = document.createElement('p');
    status.className = 'sr-only';
    status.setAttribute('role', 'status');
    status.setAttribute('data-soft-nav-status', '');
    document.body.appendChild(status);
    native.setTimeout.call(window, function () { status.textContent = document.title; }, 60);
  }

  function navigate(url, options) {
    if (controller) controller.abort();
    controller = window.AbortController ? new AbortController() : null;
    var signal = controller ? controller.signal : undefined;
    busy = true;
    document.documentElement.setAttribute('aria-busy', 'true');
    return load(url, signal).then(function (next) {
      // Remember where this page was left, for Back.
      try { history.replaceState(Object.assign({}, history.state, { lgSoft: 1, lgDoc: docId, scrollY: window.scrollY }), ''); } catch (e) {}
      if (saveTimer) { native.clearTimeout.call(window, saveTimer); saveTimer = 0; }
      teardown();
      docId++;
      var state = { lgSoft: 1, lgDoc: docId };
      if (options.push) history.pushState(state, '', next.url);
      else history.replaceState(Object.assign({}, options.state, { lgSoft: 1, lgDoc: docId }), '', next.url);
      try { history.scrollRestoration = 'manual'; } catch (e) {}
      docKey = location.pathname;
      swapHead(next.doc);
      swapBody(next.doc);
      if (!runScripts(next.scripts)) throw new Error('page script failed');
      settle(next.url, options.push ? null : options.state);
      document.dispatchEvent(new CustomEvent('lg:navigate', { detail: { url: next.url } }));
    }).catch(function (error) {
      if (error && error.name === 'AbortError') return;
      // The URL may already point at the new page: a full load of it is the safe state.
      hard(url, !options.push || location.href === url);
    }).then(function () {
      busy = false;
      document.documentElement.removeAttribute('aria-busy');
    });
  }

  // Reload of an entry created here: history.scrollRestoration is 'manual' on it, so the position is saved on the way
  // out and restored once the reloaded page has its layout.
  // Browsers drop history changes made while the page unloads, so the position is kept up to date while scrolling
  // (debounced, entries of this layer only).
  var saveTimer = 0;
  function savePosition() {
    saveTimer = 0;
    try { if (history.state && history.state.lgSoft) history.replaceState(Object.assign({}, history.state, { scrollY: window.scrollY }), ''); } catch (e) {}
  }
  origAdd.win.call(window, 'scroll', function () {
    if (saveTimer) native.clearTimeout.call(window, saveTimer);
    saveTimer = native.setTimeout.call(window, savePosition, 400);
  }, { passive: true });
  origAdd.win.call(window, 'pagehide', savePosition);
  (function restoreOnReload() {
    var entry = null;
    try { entry = performance.getEntriesByType('navigation')[0]; } catch (e) {}
    var state = history.state;
    if (!entry || entry.type !== 'reload' || !state || !state.lgSoft || typeof state.scrollY !== 'number') return;
    var restore = function () { window.scrollTo({ top: state.scrollY, left: 0, behavior: 'instant' }); };
    if (document.readyState === 'complete') restore(); else origAdd.win.call(window, 'load', function () { requestAnimationFrame(restore); });
  })();
  origAdd.doc.call(document, 'click', onClick);
  origAdd.win.call(window, 'popstate', function (event) {
    var state = event.state;
    // Same document (in-page anchors, the catalogue's own filter history): the page handles it.
    if (state && state.lgDoc === docId) return;
    if (!state && location.pathname === docKey) return;
    navigate(location.href, { push: false, state: state || {} });
  });

  window.LGSoftNav = {
    // Run fn as page code: what it registers is released when the page is left (player.js views use it).
    page: function (fn) { depth++; try { return fn(); } finally { depth--; } },
    // Unsubscribe functions of page code (LGPlayer.on).
    track: function (off) { if (typeof off === 'function') scope.offs.push(off); },
    navigate: function (url) { return navigate(new URL(url, location.href).href, { push: true }); },
    // The URL a link would be loaded with, or null when it keeps a traditional navigation.
    eligible: function (a) { var url = a && a.getAttribute && a.getAttribute('href') !== null ? eligible(a) : null; return url ? url.href : null; },
    busy: function () { return busy; },
    scopeSize: function () { return { listeners: scope.listeners.length, timeouts: scope.timeouts.length, intervals: scope.intervals.length,
      observers: scope.observers.length, media: scope.media.length, offs: scope.offs.length }; }
  };
})();
