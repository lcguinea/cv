// Runs apps-script/Code.gs + apps-script/Billing.gs in a Node vm with the Google services they use replaced by
// in-memory fakes: PropertiesService, CacheService, LockService, Utilities, SpreadsheetApp (the ledger Sheet),
// CalendarApp/Calendar (availability, free/busy and events with client ids), MailApp, Session, ContentService,
// UrlFetchApp and ScriptApp. UrlFetchApp is pluggable: tests/support/fake_stripe.js for the scenarios, or real HTTPS
// to the Stripe test API for tools/billing_dev_server.js. No secret is ever written to disk by this module.
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.join(__dirname, '..', '..');
const SOURCES = ['Code.gs', 'Billing.gs'].map((f) => fs.readFileSync(path.join(ROOT, 'apps-script', f), 'utf8')).join('\n;\n');
const clone = (o) => JSON.parse(JSON.stringify(o));
const signed = (buf) => Array.from(buf).map((b) => (b > 127 ? b - 256 : b));

/** Availability windows (epoch ms) for `days` days from `fromMs`: weekdays 10:00-14:00 and 16:00-20:00 in Madrid. */
function weekdayWindows(fromMs, days) {
  const out = [];
  for (let d = 0; d < days; d++) {
    const day = new Date(fromMs + d * 86400000);
    const ymd = day.toISOString().slice(0, 10);
    const wd = new Date(ymd + 'T12:00:00Z').getUTCDay();
    if (wd === 0 || wd === 6) continue;
    for (const [a, b] of [[10, 14], [16, 20]]) out.push({ start: madrid(ymd, a), end: madrid(ymd, b) });
  }
  return out;
}

/** Epoch ms of yyyy-mm-dd hh:00 in Europe/Madrid. */
function madrid(ymd, hour) {
  const guess = Date.parse(`${ymd}T${String(hour).padStart(2, '0')}:00:00Z`);
  for (const off of [1, 2]) {
    const ms = guess - off * 3600000;
    const h = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Madrid', hour: '2-digit', hourCycle: 'h23' }).format(new Date(ms)));
    if (h === hour) return ms;
  }
  return guess - 3600000;
}

function makeSheets(env) {
  const books = env.sheets; // {spreadsheetId: {sheetName: [[...row]]}}
  function sheetApi(book, name) {
    return {
      appendRow: (row) => { if (env.sheetError) throw new Error(env.sheetError); book[name].push(row.map((v) => (v === undefined ? '' : v))); },
      getDataRange: () => ({ getValues: () => clone(book[name].length ? book[name] : [[]]) }),
      getRange: (r, c, nr, nc) => ({
        setValues: (vals) => {
          if (env.sheetError) throw new Error(env.sheetError);
          for (let i = 0; i < nr; i++) {
            while (book[name].length < r + i) book[name].push([]);
            const row = book[name][r - 1 + i];
            for (let j = 0; j < nc; j++) row[c - 1 + j] = vals[i][j];
          }
        },
      }),
      clearContents: () => { book[name] = []; },
    };
  }
  return {
    openById: (id) => {
      if (!books[id]) throw new Error('Spreadsheet not found');
      const book = books[id];
      return {
        getSheetByName: (n) => (book[n] ? sheetApi(book, n) : null),
        insertSheet: (n) => { book[n] = []; return sheetApi(book, n); },
      };
    },
  };
}

function makeEnv(opts = {}) {
  const env = {
    now: opts.now || Date.parse('2026-11-16T08:00:00Z'),
    props: Object.assign({
      AVAILABILITY_CALENDAR_ID: 'avail@group.calendar.google.com', BOOKING_CALENDAR_ID: 'owner@example.com',
      BUSY_CALENDAR_IDS: 'owner@example.com', BUFFER_MINUTES: '0', MIN_NOTICE_HOURS: '24', MAX_DAYS_AHEAD: '60',
      NOTIFY_EMAIL: 'owner@example.com', STRIPE_MODE: 'test', STRIPE_SECRET_KEY: 'rk_test_FAKEKEYFORTESTSONLY',
      STRIPE_PRICE_WEEKLY: 'price_weekly', STRIPE_PRICE_BIWEEKLY: 'price_biweekly', RELAY_SECRET: 'ab'.repeat(32),
      TERMS_APPROVED_VERSION: '2026-11-12-v1',
      LEDGER_SPREADSHEET_ID: 'sheet1', BILLING_CHECKOUT_ENABLED: 'true', CLASS_LOCATION: 'Estudio de Luis, Valencia',
    }, opts.props),
    sheets: opts.sheets || { sheet1: {} },
    availability: opts.availability || null,
    calendars: opts.calendars || { 'owner@example.com': [] },
    mails: [], logs: [], cache: {}, lockHeld: false, insertError: null, removeError: null, patchError: null, sheetError: null,
    fetch: opts.fetch || null, fetches: [], triggers: [],
  };
  const availability = () => env.availability || weekdayWindows(env.now - 86400000, 70);
  const cacheApi = {
    get: (k) => (k in env.cache ? env.cache[k] : null),
    put: (k, v) => { if (k.length > 250) throw new Error('key'); env.cache[k] = v; },
    remove: (k) => { delete env.cache[k]; },
    removeAll: (keys) => keys.forEach((k) => { delete env.cache[k]; }),
  };
  const propsApi = {
    getProperty: (k) => (k in env.props ? env.props[k] : null),
    setProperty: (k, v) => { env.props[k] = String(v); return propsApi; },
    deleteProperty: (k) => { delete env.props[k]; return propsApi; },
    getProperties: () => Object.assign({}, env.props),
  };
  const FakeDate = class extends Date {
    constructor(...a) { if (a.length) super(...a); else super(env.now); }
    static now() { return env.now; }
  };
  const cal = (id) => (env.calendars[id] = env.calendars[id] || []);
  const apiShape = (ev) => Object.assign(clone(ev), { start: { dateTime: new Date(ev.start).toISOString() }, end: { dateTime: new Date(ev.end).toISOString() },
    htmlLink: 'https://www.google.com/calendar/event?eid=' + Buffer.from(ev.id).toString('base64url') });
  const Calendar = {
    Freebusy: {
      query: (req) => {
        const from = Date.parse(req.timeMin), to = Date.parse(req.timeMax);
        const calendars = {};
        req.items.forEach(({ id }) => {
          calendars[id] = { busy: cal(id).filter((e) => e.status !== 'cancelled' && e.transparency !== 'transparent' && e.start < to && e.end > from)
            .map((e) => ({ start: new Date(e.start).toISOString(), end: new Date(e.end).toISOString() })) };
        });
        return { calendars };
      },
    },
    Events: {
      insert: (res, calId) => {
        if (env.insertError) { const e = env.insertError; if (typeof e === 'number') { if (--env.insertError === 0) env.insertError = null; } throw new Error('Calendar insert failed'); }
        if (cal(calId).some((e) => e.id === res.id)) throw new Error('The requested identifier already exists.');
        const ev = Object.assign(clone(res), { start: Date.parse(res.start.dateTime), end: Date.parse(res.end.dateTime), status: 'confirmed' });
        cal(calId).push(ev);
        return apiShape(ev);
      },
      get: (calId, id) => { const ev = cal(calId).find((e) => e.id === id); if (!ev) throw new Error('Not Found'); return apiShape(ev); },
      patch: (patch, calId, id) => {
        if (env.patchError) throw new Error(env.patchError);
        const ev = cal(calId).find((e) => e.id === id && e.status !== 'cancelled');
        if (!ev) throw new Error('Not Found');
        if (patch.start) ev.start = Date.parse(patch.start.dateTime);
        if (patch.end) ev.end = Date.parse(patch.end.dateTime);
        return apiShape(ev);
      },
      remove: (calId, id) => {
        if (env.removeError) throw new Error(env.removeError);
        const ev = cal(calId).find((e) => e.id === id && e.status !== 'cancelled');
        if (!ev) throw new Error('Resource has been deleted');
        ev.status = 'cancelled';
      },
    },
  };
  // Luis deleting or moving a class by hand in Google Calendar.
  env.deleteEvent = (id) => { cal(env.props.BOOKING_CALENDAR_ID).find((e) => e.id === id).status = 'cancelled'; };
  env.moveEvent = (id, startMs) => { const e = cal(env.props.BOOKING_CALENDAR_ID).find((x) => x.id === id); const d = e.end - e.start; e.start = startMs; e.end = startMs + d; };
  env.events = () => cal(env.props.BOOKING_CALENDAR_ID).filter((e) => e.status !== 'cancelled');

  const ctx = {
    Date: FakeDate, JSON, Math, Number, String, Object, Array, isFinite, Error, RegExp, Infinity, encodeURIComponent,
    PropertiesService: { getScriptProperties: () => propsApi },
    CacheService: { getScriptCache: () => cacheApi },
    LockService: { getScriptLock: () => ({
      tryLock: () => { if (env.lockHeld) return false; env.lockHeld = true; return true; },
      releaseLock: () => { env.lockHeld = false; } }) },
    Utilities: {
      formatDate: (d, tz, fmt) => {
        const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit',
          day: '2-digit', hour: '2-digit', minute: '2-digit' }).formatToParts(d).map((x) => [x.type, x.value]));
        return fmt === 'yyyy-MM-dd' ? `${p.year}-${p.month}-${p.day}` : `${p.hour}:${p.minute}`;
      },
      getUuid: () => crypto.randomUUID(),
      DigestAlgorithm: { SHA_256: 'SHA_256' },
      Charset: { UTF_8: 'UTF_8' },
      computeDigest: (alg, text) => signed(crypto.createHash('sha256').update(text, 'utf8').digest()),
      computeHmacSha256Signature: (value, key) => signed(crypto.createHmac('sha256', key).update(value, 'utf8').digest()),
      newBlob: (text) => ({ getBytes: () => Array.from(Buffer.from(text, 'utf8')) }),
    },
    SpreadsheetApp: makeSheets(env),
    CalendarApp: { getCalendarById: (id) => (id === env.props.AVAILABILITY_CALENDAR_ID || id === env.props.CLASS_AVAILABILITY_CALENDAR_ID ? {
      getEvents: (from, to) => availability().filter((w) => w.start < to.getTime() && w.end > from.getTime()).map((w) => ({
        isAllDayEvent: () => false, getStartTime: () => new Date(w.start), getEndTime: () => new Date(w.end) })) } : (env.calendars[id] ? {} : null)) },
    Calendar,
    MailApp: {
      sendEmail: (m) => { if (env.mailError) throw new Error(env.mailError); env.mails.push(clone(m)); },
      getRemainingDailyQuota: () => 100,
    },
    Session: { getEffectiveUser: () => ({ getEmail: () => 'owner@example.com' }) },
    ContentService: { MimeType: { JSON: 'json' }, createTextOutput: (s) => ({ content: s, setMimeType() { return this; }, getContent() { return this.content; } }) },
    UrlFetchApp: { fetch: (url, o) => {
      env.fetches.push({ url, method: o.method });
      if (env.stripeDown) throw new Error('Address unavailable: ' + url);
      const r = env.fetch(url, o);
      return { getResponseCode: () => r.code, getContentText: () => JSON.stringify(r.body) };
    } },
    // Like the real service: a weekly time trigger must name its weekday before create() (Apps Script throws otherwise).
    ScriptApp: {
      WeekDay: { MONDAY: 'MONDAY' },
      getProjectTriggers: () => env.triggers.map((t) => ({ getHandlerFunction: () => t.handler })),
      newTrigger: (handler) => ({ timeBased: () => {
        const t = { handler };
        const done = { create: () => { env.triggers.push(t); return t; } };
        const atHour = (h) => { t.hour = h; return done; };
        return {
          everyHours: (n) => { t.everyHours = n; return done; },
          everyWeeks: (n) => { t.everyWeeks = n; return {
            create: () => { throw new Error('You tried to create a weekly trigger, but did not specify which day in the week.'); },
            onWeekDay: (d) => { t.weekDay = d; return Object.assign({ atHour }, done); } }; },
        };
      } }),
    },
    Logger: { log: (s) => env.logs.push(s) },
  };
  vm.createContext(ctx);
  vm.runInContext(SOURCES, ctx, { filename: 'apps-script' });
  env.ctx = ctx;
  env.post = (body) => JSON.parse(ctx.doPost({ postData: { contents: typeof body === 'string' ? body : JSON.stringify(body) } }).getContent());
  env.get = (params) => JSON.parse(ctx.doGet({ parameter: params }).getContent());
  env.hourly = () => ctx.billingHourly();
  env.table = (name) => {
    const rows = (env.sheets[env.props.LEDGER_SPREADSHEET_ID] || {})[name] || [];
    const [head, ...rest] = rows;
    return rest.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
  };
  env.relay = (eventId, type, tsOverride, secret) => {
    const ts = tsOverride || Math.floor(env.now / 1000);
    const sig = crypto.createHmac('sha256', secret || env.props.RELAY_SECRET).update(`${ts}.${eventId}`).digest('hex');
    return env.post({ op: 'stripe_event', id: eventId, type, ts, sig });
  };
  return env;
}

module.exports = { makeEnv, weekdayWindows, madrid };
