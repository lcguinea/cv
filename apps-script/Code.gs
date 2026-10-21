/**
 * Booking backend for luisguinea.com (Google Apps Script web app).
 *
 * Reads bookable windows from a dedicated "availability" Google Calendar, subtracts the busy time of the
 * configured calendars (free/busy only: titles and details of private events are never read) and books in two
 * steps so that nobody can make this script send calendar invitations to an address they do not own:
 *
 *   1. op "book": the slot is re-checked inside the lock and held with an event that has NO attendees and sends
 *      nothing. The only message sent is a fixed-text email with a one-time confirmation link (no visitor text).
 *   2. op "confirm": whoever opens that link proves they read that mailbox. Only then is the visitor added as an
 *      attendee, the invitation sent and, for virtual meetings, the Google Meet conference requested. In-person
 *      meetings get no conference: the place is agreed afterwards. Unconfirmed holds expire.
 *   3. After confirming, the verified address receives a second private link (#manage=...) to see, cancel or
 *      reschedule the meeting (ops "manage", "cancel", "reschedule"; POST only, cancelling needs confirm:true).
 *      Changes are allowed until CHANGE_NOTICE_HOURS before the start. A reschedule moves the same event, so the
 *      invitation and the Meet link stay; the original time is kept until the new one is checked inside the lock.
 *
 * Every setting lives in Script Properties; nothing secret is stored in the repository. See apps-script/README.md.
 * Plain ES5-style JavaScript with no modules so the same file runs in Apps Script and in the Node tests
 * (tests/test_reservas.py), which replace the Google services with mocks.
 */

var DURATIONS = [30, 60, 120, 180];
var STEP_MINUTES = 30;
var MAX_BODY_BYTES = 4096;
var NAME_MAX = 80;
var NOTES_MAX = 500;
var REASON_MAX = 150;
var MODALITIES = ['virtual', 'in_person'];
var EMAIL_MAX = 254;
var EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
var CONTROL_RE = /[\u0000-\u001f\u007f-\u009f\u2028\u2029\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]/;
var REQUEST_ID_RE = /^[A-Za-z0-9-]{16,64}$/;
var TOKEN_RE = /^([0-9a-f]{32})\.([0-9a-f]{64})$/;
var MEET_RE = /^https:\/\/meet\.google\.com\/[a-z0-9-]+$/i;
var BOOK_FIELDS = ['op', 'requestId', 'name', 'email', 'start', 'duration', 'modality', 'reason', 'notes', 'website', 'lang'];
var TOKEN_FIELDS = ['op', 'token'];
// Booking management (link sent after confirmation). Exact field lists: anything else is rejected.
var MANAGE_FIELDS = { manage: ['op', 'token'], cancel: ['op', 'token', 'confirm'], reschedule: ['op', 'token', 'start'] };
var CACHE_VALUE_MAX = 90 * 1024; // CacheService rejects values over 100 KB; keep a margin.
var RECORD_PREFIX = 'bk:';
var DEFAULTS = {
  TIMEZONE: 'Europe/Madrid',
  CONFIRM_URL: 'https://luisguinea.com/agenda/',
  MIN_NOTICE_HOURS: 24,
  MAX_DAYS_AHEAD: 60,
  BUFFER_MINUTES: 15,
  HOLD_MINUTES: 30,
  MAX_PENDING_HOLDS: 10,
  RATE_PER_EMAIL_HOUR: 3,
  RATE_GLOBAL_HOUR: 20,
  CHANGE_NOTICE_HOURS: 12,
  MAX_RESCHEDULES: 3
};

// ---------- configuration ----------

function loadConfig_() {
  var p = PropertiesService.getScriptProperties();
  function num(key) {
    var raw = p.getProperty(key);
    var n = raw === null || raw === '' ? NaN : Number(raw);
    return isFinite(n) && n >= 0 ? n : DEFAULTS[key];
  }
  var availability = p.getProperty('AVAILABILITY_CALENDAR_ID');
  var booking = p.getProperty('BOOKING_CALENDAR_ID');
  if (!availability || !booking) throw new Error('not_configured');
  var busy = (p.getProperty('BUSY_CALENDAR_IDS') || '').split(',')
    .map(function (s) { return s.trim(); }).filter(Boolean);
  if (busy.indexOf(booking) === -1) busy.push(booking); // our own bookings and holds always block time
  var confirmUrl = p.getProperty('CONFIRM_URL') || DEFAULTS.CONFIRM_URL;
  if (!/^https:\/\/[^\s#?]+$/.test(confirmUrl)) throw new Error('not_configured');
  // Optional: where Luis is told about cancellations and reschedules (the organizer gets no Calendar email for them).
  var notify = (p.getProperty('NOTIFY_EMAIL') || '').trim();
  return {
    availabilityCalendarId: availability,
    bookingCalendarId: booking,
    busyCalendarIds: busy,
    timeZone: p.getProperty('TIMEZONE') || DEFAULTS.TIMEZONE,
    confirmUrl: confirmUrl,
    minNoticeMs: num('MIN_NOTICE_HOURS') * 3600000,
    maxAheadMs: num('MAX_DAYS_AHEAD') * 86400000,
    bufferMs: num('BUFFER_MINUTES') * 60000,
    holdMs: Math.max(5, num('HOLD_MINUTES')) * 60000,
    maxPendingHolds: num('MAX_PENDING_HOLDS'),
    ratePerEmail: num('RATE_PER_EMAIL_HOUR'),
    rateGlobal: num('RATE_GLOBAL_HOUR'),
    changeNoticeMs: num('CHANGE_NOTICE_HOURS') * 3600000,
    maxReschedules: num('MAX_RESCHEDULES'),
    notifyEmail: EMAIL_RE.test(notify) && !CONTROL_RE.test(notify) ? notify : ''
  };
}

// ---------- pure availability logic ----------

/**
 * Bookable slots for one duration. All times are epoch milliseconds (absolute instants), so daylight saving
 * changes cannot shift or stretch a slot. availability and busy are arrays of {start, end}.
 * A slot must sit inside one availability window, inside [now + minNotice, now + maxAhead], start on the
 * 30-minute grid and keep `buffer` free on both sides of every busy interval.
 */
function computeSlots_(availability, busy, durationMin, opts) {
  var dur = durationMin * 60000;
  var step = STEP_MINUTES * 60000;
  var earliest = opts.nowMs + opts.minNoticeMs;
  var latest = opts.nowMs + opts.maxAheadMs;
  var blocked = busy.map(function (b) { return { start: b.start - opts.bufferMs, end: b.end + opts.bufferMs }; });
  var seen = {};
  var out = [];
  availability.forEach(function (w) {
    var from = Math.max(w.start, earliest);
    var to = Math.min(w.end, latest);
    var s = Math.ceil(from / step) * step;
    for (; s + dur <= to; s += step) {
      if (seen[s]) continue;
      var e = s + dur;
      var clash = blocked.some(function (b) { return s < b.end && e > b.start; });
      if (!clash) { seen[s] = true; out.push({ start: s, end: e }); }
    }
  });
  out.sort(function (a, b) { return a.start - b.start; });
  return out;
}

// ---------- validation ----------

function cleanText_(value, max, required) {
  if (typeof value !== 'string') return null;
  var v = value.replace(/\s+/g, ' ').trim();
  if (CONTROL_RE.test(value.replace(/[\r\n\t]/g, ' '))) return null;
  if (required && !v) return null;
  if (v.length > max) return null;
  return v;
}

function onlyFields_(raw, allowed) {
  for (var k in raw) {
    if (Object.prototype.hasOwnProperty.call(raw, k) && allowed.indexOf(k) === -1) return false;
  }
  return true;
}

/** Returns {ok:true, value} or {ok:false, error}. Never trusts types, size or unknown fields. */
function validateBooking_(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) || !onlyFields_(raw, BOOK_FIELDS)) return { ok: false, error: 'invalid_request' };
  if (raw.op !== undefined && raw.op !== 'book') return { ok: false, error: 'invalid_request' };
  if (typeof raw.requestId !== 'string' || !REQUEST_ID_RE.test(raw.requestId)) return { ok: false, error: 'invalid_request' };
  if (raw.website !== undefined && raw.website !== '') return { ok: false, error: 'rejected' }; // honeypot
  var name = cleanText_(raw.name, NAME_MAX, true);
  if (name === null || name.length < 2) return { ok: false, error: 'invalid_name' };
  var email = typeof raw.email === 'string' ? raw.email.trim() : '';
  if (!email || email.length > EMAIL_MAX || CONTROL_RE.test(email) || !EMAIL_RE.test(email)) return { ok: false, error: 'invalid_email' };
  var local = email.split('@')[0];
  if (local.length > 64 || local.indexOf('..') !== -1 || local.charAt(0) === '.' || local.charAt(local.length - 1) === '.') return { ok: false, error: 'invalid_email' };
  var duration = raw.duration;
  if (typeof duration !== 'number' || DURATIONS.indexOf(duration) === -1) return { ok: false, error: 'invalid_duration' };
  var startMs = parseStart_(raw.start);
  if (startMs === null) return { ok: false, error: 'invalid_start' };
  if (typeof raw.modality !== 'string' || MODALITIES.indexOf(raw.modality) === -1) return { ok: false, error: 'invalid_modality' };
  var reason = raw.reason === undefined ? '' : cleanText_(raw.reason, REASON_MAX, false);
  if (reason === null) return { ok: false, error: 'invalid_reason' };
  var notes = raw.notes === undefined ? '' : cleanText_(raw.notes, NOTES_MAX, false);
  if (notes === null) return { ok: false, error: 'invalid_notes' };
  var lang = raw.lang === 'es' ? 'es' : 'en';
  return { ok: true, value: { requestId: raw.requestId, name: name, email: email.toLowerCase(), startMs: startMs, durationMin: duration,
    modality: raw.modality, reason: reason, notes: notes, lang: lang } };
}

/** UTC instant on the 30-minute grid ("2026-11-02T09:00:00.000Z"), as epoch ms, or null. */
function parseStart_(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00(?:\.000)?Z$/.test(value)) return null;
  var ms = Date.parse(value);
  return isFinite(ms) && ms % (STEP_MINUTES * 60000) === 0 ? ms : null;
}

/** {op:"confirm"|"status", token:"<32 hex id>.<64 hex secret>"}; management ops pass their own field list. */
function validateToken_(raw, fields) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) || !onlyFields_(raw, fields || TOKEN_FIELDS)) return null;
  var m = typeof raw.token === 'string' ? TOKEN_RE.exec(raw.token) : null;
  return m ? { op: raw.op, id: m[1], secret: m[2] } : null;
}

function validDuration_(raw) {
  var n = Number(raw);
  return DURATIONS.indexOf(n) !== -1 && String(n) === String(raw) ? n : null;
}

// ---------- small helpers ----------

function sha256Hex_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join('');
}

function randomHex_(chars) {
  var out = '';
  while (out.length < chars) out += Utilities.getUuid().replace(/-/g, '').toLowerCase();
  return out.slice(0, chars);
}

function bytes_(text) { return Utilities.newBlob(text).getBytes().length; }

function localParts_(ms, tz) {
  return {
    day: Utilities.formatDate(new Date(ms), tz, 'yyyy-MM-dd'),
    time: Utilities.formatDate(new Date(ms), tz, 'HH:mm')
  };
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function errorCode_(err) {
  return err && err.message === 'not_configured' ? 'not_configured' : 'unavailable';
}

// ---------- Google services ----------

function readAvailability_(cfg, fromMs, toMs) {
  var cal = CalendarApp.getCalendarById(cfg.availabilityCalendarId);
  if (!cal) throw new Error('availability_calendar_missing');
  return cal.getEvents(new Date(fromMs), new Date(toMs)).filter(function (ev) { return !ev.isAllDayEvent(); })
    .map(function (ev) { return { start: ev.getStartTime().getTime(), end: ev.getEndTime().getTime() }; });
}

/** Free/busy only: the API returns intervals, never titles, attendees or descriptions. */
function readBusy_(cfg, fromMs, toMs) {
  var res = Calendar.Freebusy.query({
    timeMin: new Date(fromMs).toISOString(),
    timeMax: new Date(toMs).toISOString(),
    timeZone: cfg.timeZone,
    items: cfg.busyCalendarIds.map(function (id) { return { id: id }; })
  });
  var out = [];
  var cals = res.calendars || {};
  cfg.busyCalendarIds.forEach(function (id) {
    var c = cals[id];
    if (!c || (c.errors && c.errors.length)) throw new Error('busy_calendar_unreadable'); // fail closed
    (c.busy || []).forEach(function (b) { out.push({ start: Date.parse(b.start), end: Date.parse(b.end) }); });
  });
  return out;
}

function slotsFor_(cfg, durationMin, nowMs) {
  var from = nowMs + cfg.minNoticeMs;
  var to = nowMs + cfg.maxAheadMs;
  var avail = readAvailability_(cfg, from, to);
  var busy = readBusy_(cfg, from - cfg.bufferMs - 4 * 3600000, to + cfg.bufferMs + 4 * 3600000);
  return computeSlots_(avail, busy, durationMin, { nowMs: nowMs, minNoticeMs: cfg.minNoticeMs, maxAheadMs: cfg.maxAheadMs, bufferMs: cfg.bufferMs });
}

function getEventOrNull_(cfg, eventId) {
  try { return Calendar.Events.get(cfg.bookingCalendarId, eventId); } catch (e) { return null; }
}

/** Meet state of an event. A link is only reported once Google has actually created it. */
function meetState_(ev) {
  var link = ev && ev.hangoutLink;
  var cd = (ev && ev.conferenceData) || {};
  if (!link) {
    (cd.entryPoints || []).forEach(function (p) { if (!link && p.entryPointType === 'video') link = p.uri; });
  }
  if (typeof link === 'string' && MEET_RE.test(link)) return { status: 'ready', link: link };
  var code = cd.createRequest && cd.createRequest.status && cd.createRequest.status.statusCode;
  return { status: code === 'failure' ? 'failed' : 'pending' };
}

// ---------- slot cache ----------

function invalidateSlots_() {
  CacheService.getScriptCache().removeAll(DURATIONS.map(function (d) { return 'slots:' + d; }));
}

/** Caches a listing only when it fits; a cache problem must never turn into an error for the visitor. */
function cacheSlots_(key, body) {
  if (bytes_(body) > CACHE_VALUE_MAX) return false;
  try { CacheService.getScriptCache().put(key, body, 60); return true; } catch (e) { return false; }
}

// ---------- booking records (Script Properties: durable, unlike CacheService) ----------

function records_() {
  var all = PropertiesService.getScriptProperties().getProperties();
  var out = [];
  Object.keys(all).forEach(function (k) {
    if (k.indexOf(RECORD_PREFIX) !== 0) return;
    try { out.push(JSON.parse(all[k])); } catch (e) { /* ignore corrupt entries */ }
  });
  return out;
}

function getRecord_(id) {
  var raw = PropertiesService.getScriptProperties().getProperty(RECORD_PREFIX + id);
  try { return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
}

function putRecord_(rec) { PropertiesService.getScriptProperties().setProperty(RECORD_PREFIX + rec.id, JSON.stringify(rec)); }

function deleteRecord_(id) { PropertiesService.getScriptProperties().deleteProperty(RECORD_PREFIX + id); }

/** Removes a hold from the calendar. True when the event is gone (removed now or already). */
function releaseHold_(cfg, rec) { return removeEvent_(cfg, rec, 'none'); }

/** Deletes the booking's event; `updates` is 'none' for holds (no attendees) and 'all' for a guest's cancellation. */
function removeEvent_(cfg, rec, updates) {
  try {
    Calendar.Events.remove(cfg.bookingCalendarId, rec.eventId, { sendUpdates: updates });
    return true;
  } catch (e) {
    var ev = getEventOrNull_(cfg, rec.eventId);
    return !ev || ev.status === 'cancelled';
  }
}

/** Frees expired holds and forgets old records. Must run inside the script lock. */
function sweep_(cfg, nowMs) {
  var freed = false;
  records_().forEach(function (rec) {
    if (rec.state === 'pending' && nowMs >= rec.expiresMs) {
      if (releaseHold_(cfg, rec)) { deleteRecord_(rec.id); freed = true; }
    } else if (rec.state !== 'pending' && nowMs >= rec.purgeMs) {
      deleteRecord_(rec.id);
    }
  });
  if (freed) invalidateSlots_();
}

function hasExpiredHolds_(nowMs) {
  return records_().some(function (r) { return r.state === 'pending' && nowMs >= r.expiresMs; });
}

// ---------- limits ----------

/**
 * Counters live in CacheService (best effort) and are only increased inside the lock, after a hold was
 * created and its email sent. Rejected, invalid or repeated requests never use up anybody's quota. The email
 * is hashed so long addresses cannot exceed the 250-character cache key limit.
 */
function counterKeys_(email, nowMs) {
  var hour = Math.floor(nowMs / 3600000);
  return { global: 'rl:g:' + hour, email: 'rl:e:' + hour + ':' + sha256Hex_(email).slice(0, 32) };
}

/** Error code when a new hold is not allowed now, otherwise null. */
function limitError_(cfg, email, nowMs) {
  var pending = records_().filter(function (r) { return r.state === 'pending' && nowMs < r.expiresMs; });
  if (pending.some(function (r) { return r.email === email; })) return 'pending_exists'; // one unconfirmed hold per address
  var cache = CacheService.getScriptCache();
  var keys = counterKeys_(email, nowMs);
  if (Number(cache.get(keys.global) || 0) >= cfg.rateGlobal) return 'rate_limited';
  if (Number(cache.get(keys.email) || 0) >= cfg.ratePerEmail) return 'rate_limited';
  if (pending.length >= cfg.maxPendingHolds) return 'busy';
  return null;
}

function countSuccess_(email, nowMs) {
  var cache = CacheService.getScriptCache();
  var keys = counterKeys_(email, nowMs);
  [keys.global, keys.email].forEach(function (k) {
    try { cache.put(k, String(Number(cache.get(k) || 0) + 1), 3700); } catch (e) { /* best effort */ }
  });
}

// ---------- web app entry points ----------

function doGet(e) {
  try {
    var params = (e && e.parameter) || {};
    var cfg = loadConfig_();
    if (params.action === 'config') {
      return json_({ ok: true, durations: DURATIONS, timeZone: cfg.timeZone });
    }
    if (params.action !== 'slots') return json_({ ok: false, error: 'invalid_request' });
    var duration = validDuration_(params.duration);
    if (duration === null) return json_({ ok: false, error: 'invalid_duration' });
    var now = Date.now();
    if (hasExpiredHolds_(now)) {
      // Expired holds only ever hide free time (they never expose busy time), so a failed sweep is safe.
      var lock = LockService.getScriptLock();
      if (lock.tryLock(2000)) { try { sweep_(cfg, now); } finally { lock.releaseLock(); } }
    }
    var key = 'slots:' + duration;
    var cached = CacheService.getScriptCache().get(key);
    if (cached) return ContentService.createTextOutput(cached).setMimeType(ContentService.MimeType.JSON);
    var slots = slotsFor_(cfg, duration, now).map(function (s) {
      var p = localParts_(s.start, cfg.timeZone);
      return { start: new Date(s.start).toISOString(), end: new Date(s.end).toISOString(), day: p.day, time: p.time };
    });
    var body = JSON.stringify({ ok: true, duration: duration, timeZone: cfg.timeZone, slots: slots });
    cacheSlots_(key, body);
    return ContentService.createTextOutput(body).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return json_({ ok: false, error: errorCode_(err) });
  }
}

function doPost(e) {
  try {
    var contents = e && e.postData && e.postData.contents;
    if (typeof contents !== 'string' || !contents || contents.length > MAX_BODY_BYTES) return json_({ ok: false, error: 'invalid_request' });
    var raw;
    try { raw = JSON.parse(contents); } catch (parseErr) { return json_({ ok: false, error: 'invalid_request' }); }
    var op = raw && typeof raw === 'object' ? raw.op : undefined;
    if (typeof op === 'string' && Object.prototype.hasOwnProperty.call(MANAGE_FIELDS, op)) {
      var mtok = validateToken_(raw, MANAGE_FIELDS[op]);
      if (!mtok) return json_({ ok: false, error: 'invalid_token' });
      if (op === 'cancel' && raw.confirm !== true) return json_({ ok: false, error: 'confirmation_required' });
      var newStart = op === 'reschedule' ? parseStart_(raw.start) : null;
      if (op === 'reschedule' && newStart === null) return json_({ ok: false, error: 'invalid_start' });
      var mcfg = loadConfig_();
      if (op === 'manage') return json_(manageView_(mcfg, mtok));
      return json_(op === 'cancel' ? cancelBooking_(mcfg, mtok) : rescheduleBooking_(mcfg, mtok, newStart));
    }
    if (op === 'confirm' || op === 'status') {
      var tok = validateToken_(raw);
      if (!tok) return json_({ ok: false, error: 'invalid_token' });
      var tcfg = loadConfig_();
      return json_(op === 'confirm' ? confirmBooking_(tcfg, tok) : bookingStatus_(tcfg, tok));
    }
    var v = validateBooking_(raw);
    if (!v.ok) return json_({ ok: false, error: v.error });
    return json_(requestBooking_(loadConfig_(), v.value));
  } catch (err) {
    return json_({ ok: false, error: errorCode_(err) });
  }
}

function withLock_(fn) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return { ok: false, error: 'busy' };
  try { return fn(); } finally { lock.releaseLock(); }
}

// ---------- step 1: hold the slot and send the confirmation link ----------

function bookingId_(requestId) { return sha256Hex_('booking:' + requestId).slice(0, 32); }

function fingerprint_(req) {
  return sha256Hex_([req.email, req.startMs, req.durationMin, req.modality, req.reason, req.name, req.notes, req.lang].join('\n'));
}

function pendingResponse_(rec) {
  return { ok: true, status: 'verification_sent', start: new Date(rec.startMs).toISOString(), end: new Date(rec.endMs).toISOString(),
    expiresAt: new Date(rec.expiresMs).toISOString(), modality: rec.modality, reason: rec.reason };
}

// ---------- wording shared by the calendar event and the emails ----------

var MEETING_TEXT = {
  es: { virtual: 'Encuentro virtual', in_person: 'Encuentro presencial', modality: 'Modalidad', reason: 'Motivo', notes: 'Notas',
    virtualDetail: 'Virtual (Google Meet)', inPersonDetail: 'Presencial', place: 'Pendiente de acordar',
    placeLine: 'Lugar: pendiente de acordar. Luis te escribirá para acordarlo.', with: ' con ', awaiting: '[Pendiente de confirmar] ' },
  en: { virtual: 'Virtual meeting', in_person: 'In-person meeting', modality: 'Format', reason: 'Reason', notes: 'Notes',
    virtualDetail: 'Virtual (Google Meet)', inPersonDetail: 'In person', place: 'To be agreed',
    placeLine: 'Place: to be agreed. Luis will write to you to agree on it.', with: ' with ', awaiting: '[Awaiting confirmation] ' }
};

function meetingText_(rec) { return MEETING_TEXT[rec.lang === 'es' ? 'es' : 'en']; }

function eventSummary_(rec, pending) {
  var tx = meetingText_(rec);
  return (pending ? tx.awaiting : '') + tx[rec.modality === 'in_person' ? 'in_person' : 'virtual'] + tx.with + rec.name;
}

/** Event description: format, place when in person, and the visitor's reason and notes when given. */
function eventDescription_(rec, notes) {
  var tx = meetingText_(rec);
  var lines = [tx.modality + ': ' + (rec.modality === 'in_person' ? tx.inPersonDetail : tx.virtualDetail)];
  if (rec.modality === 'in_person') lines.push(tx.placeLine);
  if (rec.reason) lines.push(tx.reason + ': ' + rec.reason);
  if (notes) lines.push(tx.notes + ': ' + notes);
  return lines.join('\n');
}

function requestBooking_(cfg, req) {
  return withLock_(function () {
    var now = Date.now();
    sweep_(cfg, now);
    var id = bookingId_(req.requestId);
    var fp = fingerprint_(req);
    var rec = getRecord_(id);
    if (rec) {
      // A retry of a request we already handled: never a second hold, never a second email once one went out.
      if (rec.fp !== fp) return { ok: false, error: 'invalid_request' };
      if (rec.state !== 'pending') return { ok: true, status: rec.state, start: new Date(rec.startMs).toISOString(), end: new Date(rec.endMs).toISOString() };
      if (!rec.mailed) return sendConfirmation_(cfg, rec, null);
      return pendingResponse_(rec);
    }
    var limited = limitError_(cfg, req.email, now);
    if (limited) return { ok: false, error: limited };
    if (MailApp.getRemainingDailyQuota() < 1) return { ok: false, error: 'unavailable' };

    // Re-check inside the lock against fresh calendar data: the slot list the visitor saw may be stale.
    var fresh = slotsFor_(cfg, req.durationMin, now);
    if (!fresh.some(function (s) { return s.start === req.startMs; })) return { ok: false, error: 'slot_unavailable' };

    var secret = randomHex_(64);
    rec = {
      id: id, eventId: 'lg' + id, fp: fp, state: 'pending', mailed: false,
      name: req.name, email: req.email, lang: req.lang, modality: req.modality, reason: req.reason,
      startMs: req.startMs, endMs: req.startMs + req.durationMin * 60000,
      expiresMs: now + cfg.holdMs, tokenHash: sha256Hex_(secret)
    };
    rec.purgeMs = rec.expiresMs;
    insertHold_(cfg, rec, req);
    putRecord_(rec);
    invalidateSlots_(); // the held slot must disappear from every cached listing right away
    return sendConfirmation_(cfg, rec, secret);
  });
}

/** Event with no attendees and no notifications: it only blocks the time until the email is confirmed. */
function insertHold_(cfg, rec, req) {
  var resource = {
    id: rec.eventId,
    summary: eventSummary_(rec, true),
    description: eventDescription_(rec, req.notes),
    start: { dateTime: new Date(rec.startMs).toISOString(), timeZone: cfg.timeZone },
    end: { dateTime: new Date(rec.endMs).toISOString(), timeZone: cfg.timeZone },
    transparency: 'opaque',
    guestsCanModify: false,
    guestsCanInviteOthers: false,
    extendedProperties: { private: { lgBooking: rec.id, lgModality: rec.modality } }
  };
  if (rec.modality === 'in_person') resource.location = meetingText_(rec).place;
  try {
    Calendar.Events.insert(resource, cfg.bookingCalendarId, { sendUpdates: 'none' });
  } catch (err) {
    // The deterministic id makes a retry after a timeout safe: if our event is already there, reuse it.
    var ev = getEventOrNull_(cfg, rec.eventId);
    var mine = ev && ev.status !== 'cancelled' && ev.extendedProperties && ev.extendedProperties.private &&
      ev.extendedProperties.private.lgBooking === rec.id;
    if (!mine) throw err;
  }
}

function sendConfirmation_(cfg, rec, secret) {
  if (!secret) {
    // The previous attempt stored the hold but the email never left: issue a fresh link.
    secret = randomHex_(64);
    rec.tokenHash = sha256Hex_(secret);
    putRecord_(rec);
  }
  var link = cfg.confirmUrl + '#confirm=' + rec.id + '.' + secret;
  var when = localParts_(rec.startMs, cfg.timeZone);
  var minutes = (rec.endMs - rec.startMs) / 60000;
  var until = localParts_(rec.expiresMs, cfg.timeZone);
  var es = rec.lang === 'es';
  var inPerson = rec.modality === 'in_person';
  // Fixed text only: the visitor's name, reason and notes are never echoed to the address they typed (that
  // address is not verified yet). The format is one of two fixed values, so it is safe to mention.
  var kind = es ? (inPerson ? 'un encuentro presencial' : 'un encuentro virtual (Google Meet)') : (inPerson ? 'an in-person meeting' : 'a virtual meeting (Google Meet)');
  var place = inPerson ? (es ? '\n\nEl lugar está pendiente de acordar: Luis te escribirá para acordarlo.' : '\n\nThe place is still to be agreed: Luis will write to you to agree on it.') : '';
  var body = es
    ? 'Se ha solicitado ' + kind + ' de ' + minutes + ' minutos con Luis Guinea el ' + when.day + ' a las ' + when.time +
      ' (hora de Madrid) usando esta dirección de correo.' + place + '\n\nPara confirmarlo y recibir la invitación de Google Calendar, abre este enlace antes de las ' +
      until.time + ' (hora de Madrid) del ' + until.day + ':\n' + link + '\n\nSi no has sido tú, ignora este mensaje: no se creará ninguna reserva y el horario se liberará solo.'
    : 'You requested ' + kind + ' of ' + minutes + ' minutes with Luis Guinea on ' + when.day + ' at ' + when.time +
      ' (Madrid time) using this email address.' + place + '\n\nTo confirm it and receive the Google Calendar invitation, open this link before ' +
      until.time + ' (Madrid time) on ' + until.day + ':\n' + link + '\n\nIf this was not you, ignore this message: no booking will be made and the time will be released automatically.';
  try {
    MailApp.sendEmail({ to: rec.email, subject: es ? 'Confirma tu reserva con Luis Guinea' : 'Confirm your booking with Luis Guinea', body: body, name: 'Luis Guinea' });
  } catch (err) {
    if (releaseHold_(cfg, rec)) deleteRecord_(rec.id); // otherwise the sweep frees it when it expires
    invalidateSlots_();
    return { ok: false, error: 'unavailable' };
  }
  rec.mailed = true;
  putRecord_(rec);
  countSuccess_(rec.email, Date.now());
  return pendingResponse_(rec);
}

// ---------- step 2: the mailbox owner confirms ----------

function checkToken_(tok) {
  var rec = getRecord_(tok.id);
  if (!rec || !rec.tokenHash || sha256Hex_(tok.secret) !== rec.tokenHash) return null;
  return rec;
}

/**
 * manageEmail tells the page whether the management link really went out, so it never claims an email that was not
 * sent: "sent", "failed" (not sent yet; opening the confirmation link again retries while changes are allowed) or
 * "too_late" (CHANGE_NOTICE_HOURS has started, so no link is issued). Never the link or its token.
 */
function manageEmailState_(cfg, rec) {
  if (rec.manageMailed) return 'sent';
  return Date.now() >= changeDeadline_(cfg, rec) ? 'too_late' : 'failed';
}

function confirmedResponse_(cfg, rec) {
  return { ok: true, status: 'confirmed', emailVerified: true, start: new Date(rec.startMs).toISOString(), end: new Date(rec.endMs).toISOString(),
    modality: rec.modality, reason: rec.reason, meet: rec.meet, manageEmail: manageEmailState_(cfg, rec) };
}

function confirmBooking_(cfg, tok) {
  return withLock_(function () {
    var now = Date.now();
    var rec = checkToken_(tok);
    if (!rec) return { ok: false, error: 'invalid_token' };
    if (rec.state === 'cancelled') return { ok: false, error: 'cancelled' };
    if (rec.state === 'confirmed') {
      // Repeated click or retry; it also re-sends the management link if that email never left.
      sendManageLink_(cfg, rec);
      return confirmedResponse_(cfg, refreshMeet_(cfg, rec));
    }
    if (now >= rec.expiresMs) {
      if (releaseHold_(cfg, rec)) deleteRecord_(rec.id);
      invalidateSlots_();
      return { ok: false, error: 'expired' };
    }
    var ev = getEventOrNull_(cfg, rec.eventId);
    if (!ev || ev.status === 'cancelled') { deleteRecord_(rec.id); return { ok: false, error: 'slot_unavailable' }; }
    // Ownership of the address is now proven: add the attendee and send the invitation. Virtual meetings ask
    // for Meet; the conference requestId is the booking id, so a retried patch cannot create a second one.
    // In-person meetings send no conference data at all (the place, "to be agreed", is already on the hold).
    var virtual = rec.modality !== 'in_person';
    var patch = {
      summary: eventSummary_(rec, false),
      attendees: [{ email: rec.email, displayName: rec.name }],
      extendedProperties: { private: { lgBooking: rec.id, lgModality: rec.modality, lgEmailVerified: 'true' } }
    };
    var options = { sendUpdates: 'all' };
    if (virtual) {
      patch.conferenceData = { createRequest: { requestId: rec.id, conferenceSolutionKey: { type: 'hangoutsMeet' } } };
      options.conferenceDataVersion = 1;
    }
    var updated = Calendar.Events.patch(patch, cfg.bookingCalendarId, rec.eventId, options);
    rec.state = 'confirmed';
    rec.meet = virtual ? meetState_(updated) : { status: 'none' };
    rec.purgeMs = rec.endMs + 86400000;
    putRecord_(rec);
    sendManageLink_(cfg, rec);
    return confirmedResponse_(cfg, rec);
  });
}

/** Re-reads the event while Meet is still pending, so the link is reported as soon as it exists. */
function refreshMeet_(cfg, rec) {
  if (rec.modality === 'in_person' || (rec.meet && rec.meet.status !== 'pending')) return rec;
  var ev = getEventOrNull_(cfg, rec.eventId);
  if (ev) rec.meet = meetState_(ev);
  return rec;
}

function bookingStatus_(cfg, tok) {
  var rec = checkToken_(tok);
  if (!rec) return { ok: false, error: 'invalid_token' };
  if (rec.state === 'cancelled') return { ok: false, error: 'cancelled' };
  if (rec.state !== 'confirmed') return Date.now() >= rec.expiresMs ? { ok: false, error: 'expired' } : pendingResponse_(rec);
  return confirmedResponse_(cfg, refreshMeet_(cfg, rec));
}

// ---------- step 3: the guest manages a confirmed booking ----------

/**
 * Sends the private management link to the address that just proved it is theirs. The secret is random (256 bits),
 * tied to this booking id, stored only as a hash and domain-separated from the confirmation secret, so neither link
 * works as the other. It is only ever emailed: never returned by the API, written to the event or logged.
 */
function sendManageLink_(cfg, rec) {
  if (rec.state !== 'confirmed' || rec.manageMailed) return;
  // Only while changes are allowed: an old confirmation link reopened later (legacy booking, or a management
  // email that failed) must not hand out management access once CHANGE_NOTICE_HOURS has started.
  if (Date.now() >= changeDeadline_(cfg, rec)) return;
  try { if (MailApp.getRemainingDailyQuota() < 1) return; } catch (e) { return; }
  var secret = randomHex_(64);
  rec.manageHash = sha256Hex_('manage:' + secret);
  putRecord_(rec); // stored before sending: a link that leaves is always valid
  var link = cfg.confirmUrl + '#manage=' + rec.id + '.' + secret;
  var when = localParts_(rec.startMs, cfg.timeZone);
  var minutes = (rec.endMs - rec.startMs) / 60000;
  var hours = Math.round(cfg.changeNoticeMs / 3600000);
  var es = rec.lang === 'es';
  var inPerson = rec.modality === 'in_person';
  var kind = es ? (inPerson ? 'encuentro presencial' : 'encuentro virtual (Google Meet)') : (inPerson ? 'in-person meeting' : 'virtual meeting (Google Meet)');
  var body = es
    ? 'Tu ' + kind + ' de ' + minutes + ' minutos con Luis Guinea está confirmado para el ' + when.day + ' a las ' + when.time +
      ' (hora de Madrid). La invitación de Google Calendar te llega por separado.\n\nSi necesitas cancelarlo o cambiarlo de horario, usa este enlace privado (no lo compartas):\n' +
      link + '\n\nPuedes hacerlo hasta ' + hours + ' horas antes del encuentro. Después, escríbeme por correo.'
    : 'Your ' + kind + ' of ' + minutes + ' minutes with Luis Guinea is confirmed for ' + when.day + ' at ' + when.time +
      ' (Madrid time). The Google Calendar invitation arrives separately.\n\nIf you need to cancel it or move it to another time, use this private link (do not share it):\n' +
      link + '\n\nYou can do so up to ' + hours + ' hours before the meeting. After that, write to me by email.';
  try {
    MailApp.sendEmail({ to: rec.email, subject: es ? 'Tu reserva con Luis Guinea' : 'Your booking with Luis Guinea', body: body, name: 'Luis Guinea' });
  } catch (err) {
    return; // the booking stays confirmed; opening the confirmation link again retries this email
  }
  rec.manageMailed = true;
  putRecord_(rec);
}

function checkManageToken_(tok) {
  var rec = getRecord_(tok.id);
  if (!rec || !rec.manageHash || sha256Hex_('manage:' + tok.secret) !== rec.manageHash) return null;
  return rec;
}

function changeDeadline_(cfg, rec) { return rec.startMs - cfg.changeNoticeMs; }

/** What the management page shows. Never contains the token, the email address or the guest's notes. */
function manageResponse_(cfg, rec, nowMs) {
  var confirmed = rec.state === 'confirmed';
  var deadline = changeDeadline_(cfg, rec);
  return { ok: true, status: rec.state, start: new Date(rec.startMs).toISOString(), end: new Date(rec.endMs).toISOString(),
    duration: (rec.endMs - rec.startMs) / 60000, modality: rec.modality === 'in_person' ? 'in_person' : 'virtual',
    reason: rec.reason || '', meet: confirmed ? rec.meet || { status: 'pending' } : { status: 'none' },
    changeUntil: new Date(deadline).toISOString(), canChange: confirmed && nowMs < deadline,
    reschedulesLeft: Math.max(0, cfg.maxReschedules - (rec.reschedules || 0)) };
}

/** Read-only view of the booking behind a management link. */
function manageView_(cfg, tok) {
  var rec = checkManageToken_(tok);
  if (!rec || (rec.state !== 'confirmed' && rec.state !== 'cancelled')) return { ok: false, error: 'invalid_token' };
  if (rec.state === 'confirmed') rec = refreshMeet_(cfg, rec);
  return manageResponse_(cfg, rec, Date.now());
}

/** Cancels on explicit request: deletes the event (Google notifies the guest) and frees the time at once. */
function cancelBooking_(cfg, tok) {
  return withLock_(function () {
    var now = Date.now();
    var rec = checkManageToken_(tok);
    if (!rec) return { ok: false, error: 'invalid_token' };
    if (rec.state === 'cancelled') return manageResponse_(cfg, rec, now); // retry after a lost response
    if (rec.state !== 'confirmed') return { ok: false, error: 'invalid_token' };
    if (now >= changeDeadline_(cfg, rec)) return { ok: false, error: 'too_late' };
    if (!removeEvent_(cfg, rec, 'all')) return { ok: false, error: 'unavailable' };
    rec.state = 'cancelled';
    rec.cancelledMs = now;
    putRecord_(rec);
    invalidateSlots_(); // the freed time is offered again right away
    notifyOwner_(cfg, rec, null);
    return manageResponse_(cfg, rec, now);
  });
}

/**
 * Moves the booking to another free start with the same duration. The new time is re-checked inside the lock
 * against fresh calendar data while the original event still blocks its own time; only then is that same event
 * moved (one patch: Google updates the invitation, the Meet link stays). If anything fails, nothing has changed.
 */
function rescheduleBooking_(cfg, tok, startMs) {
  return withLock_(function () {
    var now = Date.now();
    var rec = checkManageToken_(tok);
    if (!rec) return { ok: false, error: 'invalid_token' };
    if (rec.state === 'cancelled') return { ok: false, error: 'cancelled' };
    if (rec.state !== 'confirmed') return { ok: false, error: 'invalid_token' };
    if (startMs === rec.startMs) return manageResponse_(cfg, rec, now); // retry of a move that already happened
    if (now >= changeDeadline_(cfg, rec)) return { ok: false, error: 'too_late' };
    if ((rec.reschedules || 0) >= cfg.maxReschedules) return { ok: false, error: 'reschedule_limit' };
    var durationMin = (rec.endMs - rec.startMs) / 60000;
    var fresh = slotsFor_(cfg, durationMin, now);
    if (!fresh.some(function (s) { return s.start === startMs; })) return { ok: false, error: 'slot_unavailable' };
    var endMs = startMs + durationMin * 60000;
    try {
      Calendar.Events.patch({
        start: { dateTime: new Date(startMs).toISOString(), timeZone: cfg.timeZone },
        end: { dateTime: new Date(endMs).toISOString(), timeZone: cfg.timeZone }
      }, cfg.bookingCalendarId, rec.eventId, { sendUpdates: 'all' });
    } catch (err) {
      // A lost response: the event may already be at the new time. Anything else leaves the booking as it was.
      var ev = getEventOrNull_(cfg, rec.eventId);
      if (!ev || ev.status === 'cancelled') {
        rec.state = 'cancelled';
        putRecord_(rec);
        return { ok: false, error: 'cancelled' };
      }
      if (!ev.start || Date.parse(ev.start.dateTime) !== startMs) throw err;
    }
    var oldStart = rec.startMs;
    rec.startMs = startMs;
    rec.endMs = endMs;
    rec.purgeMs = endMs + 86400000;
    rec.reschedules = (rec.reschedules || 0) + 1;
    putRecord_(rec);
    invalidateSlots_(); // the old time is free again and the new one is taken
    notifyOwner_(cfg, rec, oldStart);
    return manageResponse_(cfg, rec, now);
  });
}

/** Optional email to Luis (NOTIFY_EMAIL) after a cancellation or reschedule. Best effort; never the link. */
function notifyOwner_(cfg, rec, oldStartMs) {
  if (!cfg.notifyEmail) return;
  var now = localParts_(rec.startMs, cfg.timeZone);
  var tx = meetingText_({ lang: 'es' });
  var what = rec.modality === 'in_person' ? tx.inPersonDetail : tx.virtualDetail;
  var subject, body;
  if (oldStartMs === null) {
    subject = 'Reserva cancelada: ' + rec.name;
    body = rec.name + ' <' + rec.email + '> ha cancelado el encuentro (' + what + ') del ' + now.day + ' a las ' + now.time +
      ' (hora de Madrid). El horario vuelve a estar disponible.';
  } else {
    var before = localParts_(oldStartMs, cfg.timeZone);
    subject = 'Reserva reprogramada: ' + rec.name;
    body = rec.name + ' <' + rec.email + '> ha movido el encuentro (' + what + ') del ' + before.day + ' a las ' + before.time +
      ' al ' + now.day + ' a las ' + now.time + ' (hora de Madrid). El evento de Google Calendar ya está actualizado.';
  }
  try { MailApp.sendEmail({ to: cfg.notifyEmail, subject: subject, body: body, name: 'Agenda luisguinea.com' }); } catch (e) { /* best effort */ }
}

/**
 * Run by hand from the editor after setting the properties (see README). Read-only: it creates no events and
 * sends no email. It logs whether every calendar can be read and how many slots each duration would offer.
 */
function checkSetup() {
  var cfg = loadConfig_();
  var now = Date.now();
  var report = {
    timeZone: cfg.timeZone,
    confirmUrl: cfg.confirmUrl,
    availabilityWindows: readAvailability_(cfg, now, now + cfg.maxAheadMs).length,
    busyCalendarsReadable: readBusy_(cfg, now, now + 86400000) && cfg.busyCalendarIds.length,
    bookingCalendarFound: !!CalendarApp.getCalendarById(cfg.bookingCalendarId),
    mailQuotaLeftToday: MailApp.getRemainingDailyQuota(),
    slots: {}
  };
  DURATIONS.forEach(function (d) { report.slots[d] = slotsFor_(cfg, d, now).length; });
  Logger.log(JSON.stringify(report, null, 2));
  return report;
}

/** Optional time-driven trigger (see README): frees expired holds even when nobody visits the page. */
function sweepExpiredHolds() {
  var cfg = loadConfig_();
  withLock_(function () { sweep_(cfg, Date.now()); return { ok: true }; });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { computeSlots_: computeSlots_, validateBooking_: validateBooking_, doGet: doGet, doPost: doPost, DURATIONS: DURATIONS };
}
