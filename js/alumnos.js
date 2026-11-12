// Student area (/alumnos/): sign-in with a one-time email link, the return from Stripe Checkout, the plan, the lessons
// (credits), booking up to four lessons at once, moving or cancelling them, and the Stripe billing portal.
//
// Security: the one-time link (#acceso=...) is read from the fragment, removed from the address bar and exchanged for a
// session token, which is the only thing kept (localStorage "lg-student-session", removed on sign-out or expiry). The
// backend checks the token on every request; the page never decides what a student owns or whether a payment exists.
// The Checkout session id (?checkout=cs_...) only asks the backend for the payment status: it unlocks nothing.
(function () {
  'use strict';
  var main = document.querySelector('main.students');
  if (!main) return;
  var ENDPOINT_RE = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/;
  var LOCAL_RE = /^http:\/\/127\.0\.0\.1:\d+\/exec$/;
  var LINK_RE = /^#acceso=([0-9a-f]{32}\.[0-9a-f]{64})$/;
  var TOKEN_RE = /^[0-9a-f]{32}\.[0-9a-f]{64}$/;
  var SESSION_RE = /^cs_(?:test|live)_[A-Za-z0-9]{10,200}$/;
  var KEY = 'lg-student-session';
  var ZONE = 'Europe/Madrid';
  var endpoint = main.getAttribute('data-endpoint') || '';
  if (!(ENDPOINT_RE.test(endpoint) || (location.hostname === '127.0.0.1' && LOCAL_RE.test(endpoint)))) endpoint = '';
  var $ = function (id) { return document.getElementById(id); };
  var S = 'learn.students.';
  var state = { token: null, view: null, slots: null, slotsState: 'idle', picked: [], requestId: null, moving: null, confirming: null, busy: false,
    checkout: null, polls: 0, message: '' };

  function tr(key, vars) { return t(S + key).replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] !== undefined ? vars[k] : m; }); }
  function say(key, vars) { state.message = key ? [key, vars] : ''; $('stu-status').textContent = key ? tr(key, vars) : ''; }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function button(cls, text, onClick) { var b = el('button', cls, text); b.type = 'button'; b.addEventListener('click', onClick); return b; }
  function locale() { return window.currentLanguage === 'es' ? 'es-ES' : 'en-GB'; }
  function when(iso) {
    return new Intl.DateTimeFormat(locale(), { timeZone: ZONE, weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  }
  function day(iso) { return new Intl.DateTimeFormat(locale(), { timeZone: ZONE, weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(iso)); }
  function hour(iso) { return new Intl.DateTimeFormat(locale(), { timeZone: ZONE, hour: '2-digit', minute: '2-digit' }).format(new Date(iso)); }
  function dayKey(iso) { return new Intl.DateTimeFormat('en-CA', { timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(iso)); }
  function money(cents) { return new Intl.NumberFormat(locale(), { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(cents / 100); }
  function newId() {
    var a = new Uint8Array(16);
    window.crypto.getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }
  function store(token) { try { if (token) localStorage.setItem(KEY, token); else localStorage.removeItem(KEY); } catch (e) {} }
  function stored() { try { var v = localStorage.getItem(KEY); return TOKEN_RE.test(v || '') ? v : null; } catch (e) { return null; } }

  function post(body) {
    if (!endpoint) return Promise.reject(new Error('not_configured'));
    return fetch(endpoint, { method: 'POST', credentials: 'omit', redirect: 'follow', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }
  function show(id) { ['stu-login', 'stu-dash'].forEach(function (x) { $(x).hidden = x !== id; }); }
  function failed(res) {
    var e = res && res.error;
    if (e === 'invalid_token') { signOutLocal(); say('errSession'); return; }
    var map = { busy: 'errBusy', slot_unavailable: 'errSlot', no_credits: 'errNoCredits', overlap: 'errOverlap', too_late: 'errTooLate',
      reschedule_limit: 'errLimit', after_deadline: 'errAfterDeadline', rate_limited: 'errRate', invalid_email: 'errEmail' };
    say(map[e] || 'errGeneric');
  }

  // ---------- sign in ----------
  $('stu-login-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var email = $('stu-email').value.trim();
    $('stu-login-error').textContent = '';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { $('stu-login-error').textContent = tr('errEmail'); $('stu-email').focus(); return; }
    var b = ev.target.querySelector('button'); b.disabled = true;
    post({ op: 'stu_link', email: email, lang: window.currentLanguage === 'en' ? 'en' : 'es', website: $('stu-website').value })
      .then(function (res) { b.disabled = false; if (res && res.ok) say('linkSent'); else failed(res); })
      .catch(function () { b.disabled = false; say('errGeneric'); });
  });
  function signOutLocal() { state.token = null; state.view = null; store(null); show('stu-login'); }
  $('stu-signout').addEventListener('click', function () {
    var tok = state.token;
    signOutLocal(); say('');
    if (tok) post({ op: 'stu_logout', token: tok }).catch(function () {});
  });
  $('stu-portal').addEventListener('click', function () {
    var b = $('stu-portal'); b.disabled = true;
    post({ op: 'stu_portal', token: state.token }).then(function (res) {
      if (res && res.ok && /^https:\/\/billing\.stripe\.com\//.test(res.url || '')) { location.assign(res.url); return; }
      b.disabled = false; failed(res);
    }).catch(function () { b.disabled = false; say('errGeneric'); });
  });

  // ---------- dashboard ----------
  function load() {
    return post({ op: 'stu_view', token: state.token }).then(function (res) {
      if (!res || !res.ok) { failed(res); return; }
      state.view = res; show('stu-dash'); render();
      if (state.slotsState === 'idle') loadSlots();
    }).catch(function () { say('errGeneric'); });
  }
  function loadSlots() {
    state.slotsState = 'loading'; renderBook();
    post({ op: 'stu_slots', token: state.token }).then(function (res) {
      if (!res || !res.ok) { state.slotsState = 'error'; failed(res); renderBook(); return; }
      state.slots = res.slots; state.slotsState = 'ready'; renderBook(); renderBookings();
    }).catch(function () { state.slotsState = 'error'; renderBook(); });
  }
  function render() {
    var v = state.view;
    if (!v) return;
    $('stu-hello').textContent = v.student.name ? tr('hello', { name: v.student.name.split(' ')[0] }) : tr('helloAnon');
    renderPlan(); renderCounts(); renderBook(); renderBookings();
    if (state.message) say(state.message[0], state.message[1]);
  }
  function renderPlan() {
    var box = $('stu-plan'), p = state.view.plan;
    clear(box);
    if (!p) { box.appendChild(el('p', 'learn-hint', tr('noPlan'))); return; }
    box.appendChild(el('p', 'students-plan-name', tr('plan_' + p.plan)));
    box.appendChild(el('p', 'students-plan-price', tr('price', { amount: money(p.amount), weeks: p.intervalWeeks })));
    var known = ['active', 'past_due', 'unpaid', 'canceled', 'incomplete'];
    box.appendChild(el('p', 'students-plan-status status-' + p.status, tr('status_' + (known.indexOf(p.status) !== -1 ? p.status : 'other'))));
    if (p.renewsAt) box.appendChild(el('p', '', tr('renews', { date: when(p.renewsAt) })));
    if (p.endsAt) box.appendChild(el('p', '', tr('ends', { date: when(p.endsAt) })));
    if (p.status === 'past_due' || p.status === 'unpaid') box.appendChild(el('p', 'learn-hint', tr('pastDueNote')));
  }
  function renderCounts() {
    var c = state.view.counts, dl = $('stu-counts');
    clear(dl);
    [['available', c.available], ['reserved', c.reserved], ['done', c.done], ['carried', c.carried]].forEach(function (pair) {
      var d = el('div'); d.appendChild(el('dt', '', tr(pair[0]))); d.appendChild(el('dd', '', String(pair[1]))); dl.appendChild(d);
    });
    var ul = $('stu-credits');
    clear(ul);
    state.view.credits.forEach(function (cr) {
      var li = el('li', 'students-credit status-' + cr.status);
      li.appendChild(el('b', '', '0' + cr.n));
      var text = cr.status === 'expired_review' ? tr('expiredReview') : cr.status === 'past_deadline' ? tr('pastDeadline')
        : cr.expiresAt ? tr(state.view.policy.enforced ? 'deadline' : 'deadlineSoft', { date: when(cr.expiresAt) }) : tr('noDeadline');
      li.appendChild(el('span', '', text));
      if (cr.carried) li.appendChild(el('small', '', tr('carriedTag')));
      ul.appendChild(li);
    });
    var pol = state.view.policy;
    $('stu-policy').textContent = tr('policyNote', { h: pol.changeHours, carry: pol.carryMax, days: pol.carryDays });
  }
  function maxPick() { return Math.min(state.view.counts.available, state.view.policy.maxPerRequest); }

  /** Slot picker: several starts for booking, or one for moving a lesson (state.moving). */
  function picker(container, onPick, isPicked) {
    if (state.slotsState === 'loading' || state.slotsState === 'idle') { container.appendChild(el('p', 'learn-hint', tr('loadingSlots'))); return; }
    var mine = {};
    (state.view.bookings || []).forEach(function (b) { if (b.status === 'reservada') mine[b.start] = true; });
    var list = (state.slots || []).filter(function (s) { return !mine[s.start]; });
    if (!list.length) { container.appendChild(el('p', 'learn-hint', tr('noSlots'))); return; }
    var days = {};
    var order = [];
    list.forEach(function (s) { var k = dayKey(s.start); if (!days[k]) { days[k] = []; order.push(k); } days[k].push(s); });
    var grid = el('div', 'students-days');
    order.slice(0, 21).forEach(function (k) {
      var col = el('div', 'students-day');
      col.appendChild(el('p', 'students-day-name', day(days[k][0].start)));
      days[k].forEach(function (s) {
        var b = button('students-time', hour(s.start), function () { onPick(s.start); });
        b.setAttribute('aria-pressed', String(!!isPicked(s.start)));
        b.setAttribute('aria-label', when(s.start));
        col.appendChild(b);
      });
      grid.appendChild(col);
    });
    container.appendChild(grid);
  }
  function renderBook() {
    var box = $('stu-book');
    if (!box || !state.view) return;
    clear(box);
    var n = maxPick();
    if (n < 1) { box.appendChild(el('p', 'learn-hint', tr('noCredits'))); return; }
    box.appendChild(el('p', 'learn-intro', n === 1 ? tr('bookIntroOne') : tr('bookIntro', { n: n })));
    picker(box, function (start) {
      var at = state.picked.indexOf(start);
      if (at !== -1) state.picked.splice(at, 1);
      else if (state.picked.length < n) state.picked.push(start);
      state.requestId = null;
      renderBook();
    }, function (start) { return state.picked.indexOf(start) !== -1; });
    if (state.picked.length) {
      var bar = el('div', 'students-bookbar');
      bar.appendChild(el('p', '', tr('selected', { n: state.picked.length })));
      bar.appendChild(button('learn-button', tr('confirmBook', { n: state.picked.length }), book));
      box.appendChild(bar);
    }
  }
  function book() {
    if (state.busy || !state.picked.length) return;
    state.busy = true;
    state.requestId = state.requestId || newId(); // the same selection keeps its id: a retry books nothing twice
    post({ op: 'stu_book', token: state.token, requestId: state.requestId, starts: state.picked.slice() }).then(function (res) {
      state.busy = false;
      if (!res || !res.ok) { failed(res); if (res && res.error === 'slot_unavailable') { state.picked = []; loadSlots(); } return; }
      state.view = res; state.picked = []; state.requestId = null;
      say('booked'); render(); loadSlots();
    }).catch(function () { state.busy = false; say('errGeneric'); });
  }
  function renderBookings() {
    var ol = $('stu-bookings');
    if (!ol || !state.view) return;
    clear(ol);
    var list = state.view.bookings;
    if (!list.length) { ol.appendChild(el('li', 'learn-hint', tr('noBookings'))); return; }
    list.forEach(function (b) {
      var li = el('li', 'students-booking status-' + b.status);
      li.appendChild(el('p', 'students-booking-when', when(b.start)));
      var meta = tr('inPerson') + (b.location ? ' · ' + b.location : '') + ' · ' + (b.status === 'cancelada' && b.reason === 'profesor' ? tr('cancelledByTeacher') : tr('status_' + b.status));
      li.appendChild(el('p', 'students-booking-meta', meta));
      if (b.status === 'reservada') {
        if (b.canChange) {
          li.appendChild(el('p', 'learn-hint', tr('changeUntil', { date: when(b.changeUntil) })));
          var actions = el('div', 'students-actions');
          if (state.confirming === b.id) {
            actions.appendChild(button('learn-button', tr('confirmCancel'), function () { cancel(b.id); }));
            actions.appendChild(button('learn-button learn-button-quiet', tr('keep'), function () { state.confirming = null; renderBookings(); }));
          } else {
            actions.appendChild(button('learn-button learn-button-quiet', tr('move'), function () { state.moving = state.moving === b.id ? null : b.id; renderBookings(); }));
            actions.appendChild(button('learn-button learn-button-quiet', tr('cancel'), function () { state.confirming = b.id; state.moving = null; renderBookings(); }));
          }
          li.appendChild(actions);
          if (state.moving === b.id) {
            var pick = el('div', 'students-move');
            pick.appendChild(el('p', 'kicker', tr('chooseNew')));
            picker(pick, function (start) { move(b.id, start); }, function () { return false; });
            li.appendChild(pick);
          }
        } else {
          li.appendChild(el('p', 'learn-hint', tr('tooLate')));
        }
      }
      ol.appendChild(li);
    });
  }
  function cancel(id) {
    if (state.busy) return;
    state.busy = true;
    post({ op: 'stu_cancel', token: state.token, booking: id, confirm: true }).then(function (res) {
      state.busy = false; state.confirming = null;
      if (!res || !res.ok) { failed(res); renderBookings(); return; }
      state.view = res; say('cancelled'); render(); loadSlots();
    }).catch(function () { state.busy = false; say('errGeneric'); });
  }
  function move(id, start) {
    if (state.busy) return;
    state.busy = true;
    post({ op: 'stu_move', token: state.token, booking: id, start: start }).then(function (res) {
      state.busy = false;
      if (!res || !res.ok) { failed(res); return; }
      state.moving = null; state.view = res; say('moved'); render(); loadSlots();
    }).catch(function () { state.busy = false; say('errGeneric'); });
  }

  // ---------- return from Stripe Checkout ----------
  function checkCheckout() {
    post({ op: 'checkout_status', session: state.checkout }).then(function (res) {
      if (!res || !res.ok) { $('stu-checkout-text').textContent = tr('errGeneric'); return; }
      var key = { ready: 'paymentReady', processing: 'paymentPending', open: 'paymentOpen', expired: 'paymentExpired' }[res.state] || 'paymentPending';
      $('stu-checkout-text').textContent = tr(key);
      $('stu-checkout-text').dataset.key = key;
      $('stu-checkout').querySelector('.students-back').hidden = res.state === 'ready' || res.state === 'processing';
      if (res.state === 'processing' && state.polls++ < 20) setTimeout(checkCheckout, 3000);
    }).catch(function () { if (state.polls++ < 20) setTimeout(checkCheckout, 3000); });
  }

  document.addEventListener('lg:language', function () {
    render();
    var k = $('stu-checkout-text').dataset.key;
    if (k) $('stu-checkout-text').textContent = tr(k);
  });

  // ---------- start ----------
  var link = LINK_RE.exec(location.hash);
  var params = new URLSearchParams(location.search);
  var cs = params.get('checkout');
  if (link || cs) history.replaceState(null, '', location.pathname); // tokens and ids leave the address bar at once
  if (cs && SESSION_RE.test(cs)) {
    state.checkout = cs;
    $('stu-checkout').hidden = false;
    $('stu-checkout-text').textContent = tr('checkingPayment');
    checkCheckout();
  }
  if (!endpoint) { show('stu-login'); say('errGeneric'); return; }
  function exchange(linkToken) {
    post({ op: 'stu_login', token: linkToken }).then(function (res) {
      if (res && res.ok && TOKEN_RE.test(res.session || '')) { state.token = res.session; store(res.session); say(''); load(); return; }
      show('stu-login'); say('errLink');
    }).catch(function () { show('stu-login'); say('errGeneric'); });
  }
  // A link pasted into this same tab only changes the fragment: no reload, so it is handled here too.
  window.addEventListener('hashchange', function () {
    var m = LINK_RE.exec(location.hash);
    if (!m) return;
    history.replaceState(null, '', location.pathname);
    exchange(m[1]);
  });
  if (link) { exchange(link[1]); return; }
  state.token = stored();
  if (state.token) load(); else show('stu-login');
})();
