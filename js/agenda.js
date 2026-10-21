(function () {
  'use strict';
  var app = document.getElementById('agenda-app');
  if (!app) return;
  var ENDPOINT_RE = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/;
  var TOKEN_RE = /^#confirm=([0-9a-f]{32}\.[0-9a-f]{64})$/;
  var MANAGE_RE = /^#manage=([0-9a-f]{32}\.[0-9a-f]{64})$/;
  var MEET_RE = /^https:\/\/meet\.google\.com\/[a-z0-9-]+$/i;
  var DURATIONS = [30, 60, 120, 180];
  var MODALITIES = { virtual: 'agenda.virtual', in_person: 'agenda.inPerson' };
  var TZ = 'Europe/Madrid';
  var MEET_POLLS = 6, MEET_POLL_MS = 4000;
  var ERRORS = {
    invalid_name: 'agenda.errName', invalid_email: 'agenda.errEmail', invalid_notes: 'agenda.errNotes',
    invalid_modality: 'agenda.errModality', invalid_reason: 'agenda.errReason',
    slot_unavailable: 'agenda.errSlot', busy: 'agenda.errBusy', rate_limited: 'agenda.errRate', pending_exists: 'agenda.errPending',
    invalid_token: 'agenda.errToken', expired: 'agenda.errExpired', cancelled: 'agenda.errCancelled'
  };
  // Management link (#manage=...): its own wording for an unknown link and the change policy.
  var MANAGE_ERRORS = {
    invalid_token: 'agenda.errManageToken', too_late: 'agenda.errTooLate', reschedule_limit: 'agenda.errLimit',
    slot_unavailable: 'agenda.errSlot', cancelled: 'agenda.errCancelled', busy: 'agenda.errBusy', unavailable: 'agenda.errGoogle'
  };
  // What the confirmation page says about the email with the management link, from the backend's manageEmail:
  // it only claims an email that really went out. An unknown or missing value says nothing.
  var MANAGE_NOTES = { sent: 'agenda.manageNote', failed: 'agenda.manageNoteFailed', too_late: 'agenda.manageNoteClosed' };
  var $ = function (id) { return document.getElementById(id); };
  var endpoint = app.getAttribute('data-endpoint') || '';
  var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  // slotsState: loading | ready | empty | error
  var state = { duration: 60, slots: [], slotsState: 'loading', day: null, slot: null, busy: false, shown: null };
  // The management token only lives in this variable: it is removed from the address bar and never stored.
  var manage = { token: null, booking: null, mode: 'view', message: '', slots: [], slotsState: 'loading', day: null, slot: null, busy: false };
  var statusEl = $('agenda-status'), booking = $('agenda-booking'), form = $('agenda-form');

  function tr(key, vars) {
    return t(key).replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] !== undefined ? vars[k] : m; });
  }
  function say(key) { statusEl.textContent = key ? t(key) : ''; statusEl.dataset.key = key || ''; }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function choice(cls, pressed, onClick) {
    var b = el('button', cls);
    b.type = 'button'; b.setAttribute('aria-pressed', String(pressed));
    b.addEventListener('click', onClick);
    return b;
  }
  function locale() { return window.currentLanguage === 'es' ? 'es-ES' : 'en-GB'; }
  function fmt(iso, opts) { return new Intl.DateTimeFormat(locale(), Object.assign({ timeZone: TZ }, opts)).format(new Date(iso)); }
  function parts(iso) {
    var out = {};
    new Intl.DateTimeFormat(locale(), { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).formatToParts(new Date(iso))
      .forEach(function (p) { out[p.type] = p.value.replace(/\.$/, ''); });
    return out;
  }
  function longDay(iso) { return fmt(iso, { weekday: 'long', day: 'numeric', month: 'long' }); }
  function fullLabel(iso) { return fmt(iso, { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }); }
  function timeLabel(iso) { return fmt(iso, { hour: '2-digit', minute: '2-digit' }); }
  function plusMinutes(iso, min) { return new Date(Date.parse(iso) + min * 60000).toISOString(); }
  function range(start, end) { return timeLabel(start) + '–' + timeLabel(end); }
  function minutes(n) { return n + ' ' + t('agenda.minutes'); }
  function focusQuietly(node) { if (node) { try { node.focus({ preventScroll: true }); } catch (e) { node.focus(); } } }
  function reveal(node) {
    if (!node || !node.scrollIntoView) return;
    var box = node.getBoundingClientRect();
    if (box.top < 80 || box.top > window.innerHeight * 0.6) node.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  }

  // ---------- progress: 01 choose, 02 confirm by email, 03 invitation ----------
  function setStage(stage) {
    var list = $('agenda-progress');
    list.hidden = !stage;
    Array.prototype.forEach.call(list.children, function (li) {
      if (li.getAttribute('data-stage') === stage) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
  }

  // ---------- day and time pickers (booking and rescheduling share them) ----------
  function daysOf(slots) {
    var seen = {}, out = [];
    slots.forEach(function (s) { if (!seen[s.day]) { seen[s.day] = true; out.push({ day: s.day, start: s.start }); } });
    return out;
  }
  function skeleton(box, count, cls) {
    clear(box);
    for (var i = 0; i < count; i++) { var s = el('span', 'agenda-skeleton ' + cls); s.setAttribute('aria-hidden', 'true'); box.appendChild(s); }
  }
  function renderPicker(daysBox, timesBox, p, duration, onPick) {
    if (p.slotsState === 'loading') { skeleton(daysBox, 5, 'agenda-day'); skeleton(timesBox, 6, 'agenda-time'); daysBox.scrollLeft = 0; syncStrip(daysBox); return; }
    clear(daysBox); clear(timesBox);
    daysOf(p.slots).forEach(function (d) {
      var b = choice('agenda-day', d.day === p.day, function () { p.day = d.day; p.slot = null; onPick(); });
      var x = parts(d.start);
      b.setAttribute('aria-label', longDay(d.start));
      b.appendChild(el('span', 'agenda-day-week', x.weekday));
      b.appendChild(el('span', 'agenda-day-num', x.day));
      b.appendChild(el('span', 'agenda-day-month', x.month));
      daysBox.appendChild(b);
    });
    p.slots.filter(function (s) { return s.day === p.day; }).forEach(function (s) {
      var b = choice('agenda-time', !!p.slot && p.slot.start === s.start, function () { p.slot = s; onPick(s); });
      b.appendChild(el('span', 'agenda-time-start', s.time));
      b.appendChild(el('span', 'agenda-time-end', '–' + timeLabel(plusMinutes(s.start, duration))));
      timesBox.appendChild(b);
    });
    keepChosenInView(daysBox);
  }
  // Dates scroll sideways in one row (there can be weeks of them); the arrows page through and the chosen date stays in view.
  function syncStrip(box) {
    var wrap = box.parentNode, max = box.scrollWidth - box.clientWidth;
    wrap.querySelector('.agenda-strip-prev').disabled = box.scrollLeft <= 2;
    wrap.querySelector('.agenda-strip-next').disabled = box.scrollLeft >= max - 2;
    wrap.classList.toggle('is-scrollable', max > 2);
  }
  function keepChosenInView(box) {
    var chosen = box.querySelector('[aria-pressed="true"]');
    if (chosen) {
      var left = chosen.offsetLeft - box.offsetLeft, right = left + chosen.offsetWidth;
      if (left < box.scrollLeft || right > box.scrollLeft + box.clientWidth) box.scrollLeft = left - 8;
    }
    syncStrip(box);
  }
  Array.prototype.forEach.call(document.querySelectorAll('.agenda-strip'), function (wrap) {
    var box = wrap.querySelector('.agenda-days');
    function page(dir) { box.scrollBy({ left: dir * Math.max(120, box.clientWidth * 0.8), behavior: reduceMotion ? 'auto' : 'smooth' }); }
    wrap.querySelector('.agenda-strip-prev').addEventListener('click', function () { page(-1); });
    wrap.querySelector('.agenda-strip-next').addEventListener('click', function () { page(1); });
    box.addEventListener('scroll', function () { syncStrip(box); }, { passive: true });
    window.addEventListener('resize', function () { syncStrip(box); });
  });
  function acceptSlots(p, data) {
    if (!data || !data.ok || !Array.isArray(data.slots)) throw new Error('bad');
    p.slots = data.slots.filter(function (s) { return s && typeof s.start === 'string' && typeof s.day === 'string' && typeof s.time === 'string'; });
    var first = daysOf(p.slots)[0];
    p.day = first ? first.day : null;
    p.slotsState = p.slots.length ? 'ready' : 'empty';
  }

  // ---------- step 1: choose format, length and time ----------
  function modality() { var m = form.elements.modality.value; return MODALITIES[m] ? m : ''; }
  function renderDurations() {
    var box = $('agenda-duration-list'); clear(box);
    DURATIONS.forEach(function (d) {
      var b = choice('agenda-duration', d === state.duration, function () { if (state.duration !== d) { state.duration = d; loadSlots(); } });
      b.appendChild(el('span', 'agenda-duration-num', String(d)));
      b.appendChild(el('span', 'agenda-duration-unit', ' ' + t('agenda.minutes')));
      box.appendChild(b);
    });
  }
  function renderSlotState() {
    var key = { loading: 'agenda.loading', empty: 'agenda.noSlots', error: 'agenda.errNetwork' }[state.slotsState] || '';
    var msg = $('agenda-slot-message');
    msg.textContent = key ? t(key) : ''; msg.dataset.key = key;
    $('agenda-retry').hidden = state.slotsState !== 'error';
    $('agenda-slot-mail').hidden = state.slotsState !== 'empty';
  }
  function renderSummary() {
    var s = state.slot, empty = t('agenda.pending');
    function put(id, value) { var dd = $(id); dd.textContent = value || empty; dd.classList.toggle('is-empty', !value); }
    put('agenda-sum-modality', modality() ? t(MODALITIES[modality()]) : '');
    put('agenda-sum-length', minutes(state.duration));
    put('agenda-sum-date', s ? longDay(s.start) : '');
    put('agenda-sum-time', s ? range(s.start, plusMinutes(s.start, state.duration)) : '');
    $('agenda-summary').classList.toggle('is-ready', !!s);
  }
  function render() {
    renderDurations(); renderSlotState();
    renderPicker($('agenda-day-list'), $('agenda-time-list'), state, state.duration, function (picked) {
      render();
      if (picked) { reveal($('agenda-details')); focusQuietly($('agenda-details-title')); }
    });
    $('agenda-details').hidden = !state.slot;
    renderSummary();
  }
  Array.prototype.forEach.call(form.elements.modality, function (r) { r.addEventListener('change', renderSummary); });

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
    state.slots = []; state.day = null; state.slot = null; state.slotsState = 'loading'; render();
    var wanted = state.duration;
    get(wanted).then(function (data) {
      if (wanted !== state.duration) return;
      acceptSlots(state, data);
      render();
    }).catch(function () { if (wanted === state.duration) { state.slotsState = 'error'; render(); } });
  }
  $('agenda-retry').addEventListener('click', loadSlots);

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

  function showError(key) { $('agenda-error').textContent = key ? t(key) : ''; $('agenda-error').dataset.key = key || ''; }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (state.busy || !state.slot) return;
    var name = $('agenda-name').value.trim(), email = $('agenda-email').value.trim();
    if (name.length < 2) { showError('agenda.errName'); $('agenda-name').focus(); return; }
    if (!form.elements.email.validity.valid || !email) { showError('agenda.errEmail'); $('agenda-email').focus(); return; }
    if (!modality()) { showError('agenda.errModality'); return; }
    showError('');
    state.busy = true; form.setAttribute('aria-busy', 'true');
    $('agenda-submit').disabled = true; $('agenda-submit').textContent = t('agenda.submitting');
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
      .then(function () {
        state.busy = false; form.removeAttribute('aria-busy');
        $('agenda-submit').disabled = false; $('agenda-submit').textContent = t('agenda.submit');
      });
  });

  // ---------- panels: provisional hold, confirmed, manage ----------
  function showPanel(id) {
    booking.hidden = true;
    ['agenda-check', 'agenda-done', 'agenda-manage'].forEach(function (p) { $(p).hidden = p !== id; });
    var panel = $(id), heading = panel && panel.querySelector('h2');
    if (panel) { panel.classList.remove('is-entering'); void panel.offsetWidth; panel.classList.add('is-entering'); }
    reveal(app); focusQuietly(heading);
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
  function when(s) { return fullLabel(s.start) + (s.end ? '–' + timeLabel(s.end) : ''); }
  function renderShown() {
    var s = state.shown;
    if (!s) return;
    if (s.panel === 'check') {
      $('agenda-check-time').textContent = when(s); $('agenda-check-until').textContent = timeLabel(s.expiresAt);
      renderMeeting('agenda-check', s);
    } else {
      $('agenda-done-time').textContent = when(s);
      renderMeeting('agenda-done', s);
      $('agenda-place').hidden = s.modality !== 'in_person';
      var note = Object.prototype.hasOwnProperty.call(MANAGE_NOTES, s.manageEmail) ? MANAGE_NOTES[s.manageEmail] : '';
      $('agenda-manage-note').textContent = note ? t(note) : '';
      $('agenda-manage-note').hidden = !note;
    }
  }
  // Step 1 done: nothing is booked or sent to a calendar until the visitor opens the link in the email.
  function showCheckEmail(data, payload) {
    var d = withMeeting(data, payload);
    state.shown = { panel: 'check', start: d.start, end: d.end, expiresAt: d.expiresAt, modality: d.modality, reason: d.reason };
    renderShown(); setStage('confirm'); showPanel('agenda-check'); say('');
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
    state.shown = { panel: 'done', start: data.start, end: data.end, modality: data.modality, reason: data.reason, manageEmail: data.manageEmail };
    renderShown(); setStage('done'); showPanel('agenda-done'); say('');
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
  function forgetFragment() {
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { location.hash = ''; }
  }
  function confirmFromLink(token) {
    forgetFragment();
    setStage('confirm'); say('agenda.confirming');
    post({ op: 'confirm', token: token })
      .then(function (data) {
        if (data && data.ok && data.status === 'confirmed') { showConfirmed(withMeeting(data, null), token); return; }
        say(ERRORS[data && data.error] || 'agenda.errGeneric');
        $('agenda-restart').hidden = false;
      })
      .catch(function () { say('agenda.errNetwork'); $('agenda-restart').hidden = false; });
  }

  // ---------- step 3: the guest manages a confirmed booking (#manage=..., emailed after confirming) ----------
  // Viewing is read-only. Cancelling asks first and sends confirm:true; rescheduling offers real free times of
  // the same length and the backend keeps the original time until the new one is validated.
  function manageError(key) { var e = $('agenda-manage-error'); e.textContent = key ? t(key) : ''; e.dataset.key = key || ''; }
  function renderManage() {
    var b = manage.booking;
    if (!b) return;
    var confirmed = b.status === 'confirmed', virtual = b.modality !== 'in_person';
    $('agenda-manage-title').textContent = t(confirmed ? 'agenda.manageTitle' : 'agenda.cancelledTitle');
    $('agenda-manage-message').textContent = manage.message ? t(manage.message) : '';
    $('agenda-manage').classList.toggle('is-cancelled', !confirmed);
    $('agenda-manage-time').textContent = when(b);
    $('agenda-manage-length').textContent = minutes(b.duration);
    renderMeeting('agenda-manage', { modality: MODALITIES[b.modality] ? b.modality : 'virtual', reason: b.reason || '' });
    $('agenda-manage-place').hidden = !confirmed || virtual;
    var meet = b.meet || {}, ready = confirmed && meet.status === 'ready' && typeof meet.link === 'string' && MEET_RE.test(meet.link);
    $('agenda-manage-meet').hidden = !ready;
    if (ready) $('agenda-manage-meet').href = meet.link;
    var hours = Math.round((Date.parse(b.start) - Date.parse(b.changeUntil)) / 3600000);
    $('agenda-manage-policy').textContent = !confirmed ? '' : b.canChange ? tr('agenda.changeUntil', { date: fullLabel(b.changeUntil) }) : tr('agenda.tooLateNote', { hours: hours });
    var open = confirmed && b.canChange;
    $('agenda-manage-actions').hidden = !open || manage.mode !== 'view';
    $('agenda-manage-move').hidden = !(b.reschedulesLeft > 0 && DURATIONS.indexOf(b.duration) !== -1);
    $('agenda-cancel-confirm').hidden = !open || manage.mode !== 'cancel';
    $('agenda-move').hidden = !open || manage.mode !== 'move';
    $('agenda-restart').hidden = confirmed;
    if (manage.mode === 'move') renderMove();
    var cancelling = manage.busy && manage.mode === 'cancel', moving = manage.busy && manage.mode === 'move';
    $('agenda-cancel-yes').disabled = manage.busy; $('agenda-cancel-yes').textContent = t(cancelling ? 'agenda.cancelling' : 'agenda.cancelYes');
    $('agenda-move-yes').disabled = manage.busy || !manage.slot; $('agenda-move-yes').textContent = t(moving ? 'agenda.moving' : 'agenda.moveConfirm');
  }
  function renderMove() {
    var b = manage.booking;
    $('agenda-move-hint').textContent = tr('agenda.moveHint', { n: b.duration });
    var key = { loading: 'agenda.loading', empty: 'agenda.noMoveSlots', error: 'agenda.errNetwork' }[manage.slotsState] || '';
    $('agenda-move-message').textContent = key ? t(key) : '';
    renderPicker($('agenda-move-days'), $('agenda-move-times'), manage, b.duration, function () { renderManage(); });
  }
  function setManageMode(mode, focusId) {
    manage.mode = mode; manageError('');
    renderManage();
    focusQuietly($(focusId));
  }
  function loadMoveSlots() {
    manage.slots = []; manage.day = null; manage.slot = null; manage.slotsState = 'loading'; renderManage();
    get(manage.booking.duration).then(function (data) {
      acceptSlots(manage, data);
      // The current time is still booked, so it is normally absent; never offer it as a "new" time.
      var current = manage.booking.start;
      manage.slots = manage.slots.filter(function (s) { return Date.parse(s.start) !== Date.parse(current); });
      if (!manage.slots.length) manage.slotsState = 'empty';
      renderManage();
    }).catch(function () { manage.slotsState = 'error'; renderManage(); });
  }
  function applyManaged(data, message) {
    manage.booking = data; manage.mode = 'view'; manage.message = message; manage.slot = null;
    renderManage(); focusQuietly($('agenda-manage-title'));
  }
  // An operation was refused: show why; when the booking changed meanwhile (cancelled, too late), re-read it.
  function manageRefused(data) {
    var code = data && data.error;
    manageError(MANAGE_ERRORS[code] || 'agenda.errGeneric');
    if (code === 'slot_unavailable') { loadMoveSlots(); return; }
    if (code === 'cancelled' || code === 'too_late' || code === 'reschedule_limit') {
      post({ op: 'manage', token: manage.token }).then(function (view) {
        if (view && view.ok) { manage.booking = view; manage.mode = 'view'; renderManage(); }
      }).catch(function () {});
    }
  }
  function manageOp(body, message) {
    if (manage.busy) return;
    manage.busy = true; manageError(''); renderManage();
    post(Object.assign({ token: manage.token }, body))
      .then(function (data) { manage.busy = false; if (data && data.ok) applyManaged(data, message); else { renderManage(); manageRefused(data); } })
      .catch(function () { manage.busy = false; renderManage(); manageError('agenda.errNetwork'); });
  }
  $('agenda-manage-cancel').addEventListener('click', function () { setManageMode('cancel', 'agenda-cancel-question'); });
  $('agenda-cancel-no').addEventListener('click', function () { setManageMode('view', 'agenda-manage-cancel'); });
  $('agenda-cancel-yes').addEventListener('click', function () { manageOp({ op: 'cancel', confirm: true }, 'agenda.cancelledBody'); });
  $('agenda-manage-move').addEventListener('click', function () { setManageMode('move', 'agenda-move-title'); loadMoveSlots(); });
  $('agenda-move-no').addEventListener('click', function () { setManageMode('view', 'agenda-manage-move'); });
  $('agenda-move-yes').addEventListener('click', function () {
    if (manage.slot) manageOp({ op: 'reschedule', start: manage.slot.start }, 'agenda.movedBody');
  });
  function manageFromLink(token) {
    forgetFragment();
    manage.token = token;
    setStage(null); say('agenda.loadingBooking');
    post({ op: 'manage', token: token })
      .then(function (data) {
        if (data && data.ok) { say(''); manage.booking = data; renderManage(); showPanel('agenda-manage'); return; }
        say(MANAGE_ERRORS[data && data.error] || 'agenda.errGeneric');
        $('agenda-restart').hidden = false;
      })
      .catch(function () { say('agenda.errNetwork'); $('agenda-restart').hidden = false; });
  }

  // Keep dynamic text in the chosen language when the visitor switches EN/ES (site.js announces it).
  document.addEventListener('lg:language', function () {
    if (statusEl.dataset.key) say(statusEl.dataset.key);
    if ($('agenda-error').dataset.key) showError($('agenda-error').dataset.key);
    if ($('agenda-manage-error').dataset.key) manageError($('agenda-manage-error').dataset.key);
    if (!booking.hidden) render();
    renderShown(); renderManage();
  });

  if (!ENDPOINT_RE.test(endpoint)) { setStage(null); say('agenda.notConfigured'); return; }
  var fromLink = TOKEN_RE.exec(location.hash || '');
  if (fromLink) { confirmFromLink(fromLink[1]); return; }
  var toManage = MANAGE_RE.exec(location.hash || '');
  if (toManage) { manageFromLink(toManage[1]); return; }
  setStage('choose');
  booking.hidden = false;
  loadSlots();
})();
