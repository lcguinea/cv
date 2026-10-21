(function () {
  'use strict';
  var app = document.getElementById('agenda-app');
  if (!app) return;
  var ENDPOINT_RE = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/;
  var TOKEN_RE = /^#confirm=([0-9a-f]{32}\.[0-9a-f]{64})$/;
  var MEET_RE = /^https:\/\/meet\.google\.com\/[a-z0-9-]+$/i;
  var DURATIONS = [30, 60, 120, 180];
  var MODALITIES = { virtual: 'agenda.virtual', in_person: 'agenda.inPerson' };
  var TZ = 'Europe/Madrid';
  var MEET_POLLS = 6, MEET_POLL_MS = 4000;
  var ERRORS = {
    invalid_name: 'agenda.errName', invalid_email: 'agenda.errEmail', invalid_notes: 'agenda.errNotes',
    invalid_modality: 'agenda.errModality', invalid_reason: 'agenda.errReason',
    slot_unavailable: 'agenda.errSlot', busy: 'agenda.errBusy', rate_limited: 'agenda.errRate', pending_exists: 'agenda.errPending',
    invalid_token: 'agenda.errToken', expired: 'agenda.errExpired'
  };
  var $ = function (id) { return document.getElementById(id); };
  var endpoint = app.getAttribute('data-endpoint') || '';
  var state = { duration: 60, slots: [], day: null, slot: null, busy: false, shown: null };
  var statusEl = $('agenda-status'), booking = $('agenda-booking'), form = $('agenda-form');

  function say(key) { statusEl.textContent = key ? t(key) : ''; statusEl.dataset.key = key || ''; }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function choice(label, pressed, onClick) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.setAttribute('aria-pressed', String(pressed));
    b.addEventListener('click', onClick);
    return b;
  }
  function locale() { return window.currentLanguage === 'es' ? 'es-ES' : 'en-GB'; }
  function dayLabel(iso) {
    return new Intl.DateTimeFormat(locale(), { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(iso));
  }
  function fullLabel(iso) {
    return new Intl.DateTimeFormat(locale(), { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  }
  function timeLabel(iso) {
    return new Intl.DateTimeFormat(locale(), { timeZone: TZ, hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  }

  function renderDurations() {
    var box = $('agenda-duration-list'); clear(box);
    DURATIONS.forEach(function (d) {
      box.appendChild(choice(d + ' ' + t('agenda.minutes'), d === state.duration, function () { state.duration = d; loadSlots(); }));
    });
  }
  function days() {
    var seen = {}, out = [];
    state.slots.forEach(function (s) { if (!seen[s.day]) { seen[s.day] = s.start; out.push({ day: s.day, start: s.start }); } });
    return out;
  }
  function renderDays() {
    var box = $('agenda-day-list'); clear(box);
    days().forEach(function (d) {
      box.appendChild(choice(dayLabel(d.start), d.day === state.day, function () { state.day = d.day; state.slot = null; render(); }));
    });
  }
  function renderTimes() {
    var box = $('agenda-time-list'); clear(box);
    state.slots.filter(function (s) { return s.day === state.day; }).forEach(function (s) {
      box.appendChild(choice(s.time, !!state.slot && state.slot.start === s.start, function () { state.slot = s; render(); form.querySelector('input').focus(); }));
    });
  }
  function render() {
    renderDurations(); renderDays(); renderTimes();
    form.hidden = !state.slot;
    if (state.slot) $('agenda-picked').textContent = fullLabel(state.slot.start) + ' (' + state.duration + ' ' + t('agenda.minutes') + ')';
  }

  function get(duration) {
    return fetch(endpoint + '?action=slots&duration=' + duration, { method: 'GET', credentials: 'omit', redirect: 'follow' })
      .then(function (r) { return r.json(); });
  }
  // text/plain keeps this a "simple" cross-origin request: no preflight, no custom headers, no cookies.
  function post(body) {
    return fetch(endpoint, { method: 'POST', credentials: 'omit', redirect: 'follow', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json(); });
  }
  function loadSlots() {
    state.slots = []; state.day = null; state.slot = null; render();
    say('agenda.loading');
    var wanted = state.duration;
    get(wanted).then(function (data) {
      if (wanted !== state.duration) return;
      if (!data || !data.ok || !Array.isArray(data.slots)) throw new Error('bad');
      state.slots = data.slots.filter(function (s) { return s && typeof s.start === 'string' && typeof s.day === 'string' && typeof s.time === 'string'; });
      var first = days()[0];
      state.day = first ? first.day : null;
      say(state.slots.length ? '' : 'agenda.noSlots');
      render();
    }).catch(function () { say('agenda.errNetwork'); });
  }

  // One id per distinct request, reused when the same request is sent again (network retry, double click,
  // reload of the tab), so the backend answers a retry with the original result instead of a second booking.
  function newId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var a = new Uint8Array(16); crypto.getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }
  function requestIdFor(payload) {
    var key = JSON.stringify(payload), saved = null;
    try { saved = JSON.parse(sessionStorage.getItem('lg-agenda-request') || 'null'); } catch (e) { saved = state.request || null; }
    if (saved && saved.key === key && typeof saved.id === 'string') return saved.id;
    var id = newId();
    try { sessionStorage.setItem('lg-agenda-request', JSON.stringify({ key: key, id: id })); } catch (e) { state.request = { key: key, id: id }; }
    return id;
  }

  function modality() { var m = form.elements.modality.value; return MODALITIES[m] ? m : ''; }
  // The hint under the selector says what each format means: a Meet link, or a place agreed by email.
  function renderModalityNote() {
    var key = modality() === 'in_person' ? 'agenda.inPersonNote' : 'agenda.virtualNote';
    $('agenda-modality-note').setAttribute('data-i18n', key); $('agenda-modality-note').textContent = t(key);
  }
  Array.prototype.forEach.call(form.elements.modality, function (r) { r.addEventListener('change', renderModalityNote); });

  function showError(key) { $('agenda-error').textContent = key ? t(key) : ''; $('agenda-error').dataset.key = key || ''; }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (state.busy || !state.slot) return;
    var name = $('agenda-name').value.trim(), email = $('agenda-email').value.trim();
    if (name.length < 2) { showError('agenda.errName'); return; }
    if (!form.elements.email.validity.valid || !email) { showError('agenda.errEmail'); return; }
    if (!modality()) { showError('agenda.errModality'); return; }
    showError('');
    state.busy = true; $('agenda-submit').disabled = true; $('agenda-submit').textContent = t('agenda.submitting');
    var payload = { name: name, email: email, start: state.slot.start, duration: state.duration, modality: modality(),
      reason: $('agenda-reason').value.trim(), notes: $('agenda-notes').value.trim(),
      website: $('agenda-website').value, lang: window.currentLanguage === 'es' ? 'es' : 'en' };
    var body = Object.assign({ op: 'book', requestId: requestIdFor(payload) }, payload);
    post(body)
      .then(function (data) {
        if (data && data.ok && data.status === 'verification_sent') { showCheckEmail(data, payload); return; }
        if (data && data.ok && data.status === 'confirmed') { showConfirmed(withMeeting(data, payload), null); return; }
        showError(ERRORS[data && data.error] || 'agenda.errGeneric');
        if (data && data.error === 'slot_unavailable') loadSlots();
      })
      .catch(function () { showError('agenda.errNetwork'); })
      .then(function () { state.busy = false; $('agenda-submit').disabled = false; $('agenda-submit').textContent = t('agenda.submit'); });
  });

  function showPanel(id) {
    booking.hidden = true;
    ['agenda-check', 'agenda-done'].forEach(function (p) { $(p).hidden = p !== id; });
  }
  // Format and reason as the backend stored them; older responses without them fall back to what was sent.
  function withMeeting(data, payload) {
    var m = data.modality || (payload && payload.modality);
    var reason = typeof data.reason === 'string' ? data.reason : (payload && payload.reason) || '';
    return Object.assign({}, data, { modality: MODALITIES[m] ? m : 'virtual', reason: reason });
  }
  function renderMeeting(prefix, s) {
    $(prefix + '-modality').textContent = t(MODALITIES[s.modality]);
    $(prefix + '-reason').textContent = s.reason;
    $(prefix + '-reason-row').hidden = !s.reason;
  }
  function renderShown() {
    var s = state.shown;
    if (!s) return;
    if (s.panel === 'check') {
      $('agenda-check-time').textContent = fullLabel(s.start); $('agenda-check-until').textContent = timeLabel(s.expiresAt);
      renderMeeting('agenda-check', s);
    } else {
      $('agenda-done-time').textContent = fullLabel(s.start);
      renderMeeting('agenda-done', s);
      $('agenda-place').hidden = s.modality !== 'in_person';
    }
  }
  // Step 1 done: nothing is booked or sent to a calendar until the visitor opens the link in the email.
  function showCheckEmail(data, payload) {
    var d = withMeeting(data, payload);
    state.shown = { panel: 'check', start: d.start, expiresAt: d.expiresAt, modality: d.modality, reason: d.reason };
    renderShown(); showPanel('agenda-check'); say('');
  }

  // A Meet link is only shown once the backend reports one that exists; otherwise say what is known.
  // In-person meetings have no conference ("none"): nothing to show and nothing to wait for.
  function setMeet(meet) {
    var link = $('agenda-meet'), note = $('agenda-meet-status');
    var ready = meet && meet.status === 'ready' && typeof meet.link === 'string' && MEET_RE.test(meet.link);
    link.hidden = !ready;
    if (ready) link.href = meet.link;
    var key = ready ? '' : meet && meet.status === 'failed' ? 'agenda.meetFailed' : meet && meet.status === 'pending' ? 'agenda.meetPending' : '';
    note.textContent = key ? t(key) : '';
    if (key) note.setAttribute('data-i18n', key); else note.removeAttribute('data-i18n');
    return ready || (meet && (meet.status === 'failed' || meet.status === 'none'));
  }
  function showConfirmed(data, token) {
    state.shown = { panel: 'done', start: data.start, modality: data.modality, reason: data.reason };
    renderShown(); showPanel('agenda-done'); say('');
    var settled = setMeet(data.meet);
    if (!token || settled) return;
    var polls = 0;
    (function poll() {
      if (++polls > MEET_POLLS) return;
      setTimeout(function () {
        post({ op: 'status', token: token }).then(function (res) {
          if (res && res.ok && res.status === 'confirmed' && setMeet(res.meet)) return;
          poll();
        }).catch(poll);
      }, MEET_POLL_MS);
    })();
  }

  // Step 2: the visitor arrives from the link in the email (#confirm=...). The token lives in the fragment,
  // so it is never sent to GitHub Pages, and it is removed from the address bar before anything else.
  function confirmFromLink(token) {
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { location.hash = ''; }
    say('agenda.confirming');
    post({ op: 'confirm', token: token })
      .then(function (data) {
        if (data && data.ok && data.status === 'confirmed') { showConfirmed(withMeeting(data, null), token); return; }
        say(ERRORS[data && data.error] || 'agenda.errGeneric');
        $('agenda-restart').hidden = false;
      })
      .catch(function () { say('agenda.errNetwork'); $('agenda-restart').hidden = false; });
  }

  // Keep dynamic text in the chosen language when the visitor switches EN/ES.
  document.addEventListener('click', function (ev) {
    if (!ev.target.closest || !ev.target.closest('[data-lang]')) return;
    setTimeout(function () {
      if (statusEl.dataset.key) say(statusEl.dataset.key);
      if ($('agenda-error').dataset.key) showError($('agenda-error').dataset.key);
      if (!booking.hidden) { render(); renderModalityNote(); }
      renderShown();
    }, 0);
  });

  if (!ENDPOINT_RE.test(endpoint)) { say('agenda.notConfigured'); return; }
  var fromLink = TOKEN_RE.exec(location.hash || '');
  if (fromLink) { confirmFromLink(fromLink[1]); return; }
  booking.hidden = false;
  loadSlots();
})();
