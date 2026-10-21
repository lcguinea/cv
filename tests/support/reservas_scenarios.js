// Runs apps-script/Code.gs inside a vm with mocked Google services and prints {scenario: "ok" | failure}.
// Driven by tests/test_reservas.py. No network, no real Google account, no secrets.
// The mocks follow the documented limits and behaviour of the real services where the code depends on them:
// CacheService (keys <= 250 chars, values <= 100 KB), PropertiesService (values <= 9 KB), Calendar events with
// client-chosen ids (a second insert with the same id fails, deleted events keep their id) and Meet conferences
// that can be ready, pending or failed.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');

const CODE = fs.readFileSync(path.join(__dirname, '..', '..', 'apps-script', 'Code.gs'), 'utf8');
const Z = s => Date.parse(s);
const NOW = Z('2026-10-28T08:00:00Z');
const clone = o => JSON.parse(JSON.stringify(o));

function makeEnv(opts = {}) {
  const env = {
    now: opts.now || NOW,
    props: Object.assign({ AVAILABILITY_CALENDAR_ID: 'avail@group.calendar.google.com', BOOKING_CALENDAR_ID: 'owner@example.com',
      BUSY_CALENDAR_IDS: 'work@example.com,personal@example.com', BUFFER_MINUTES: '0', MIN_NOTICE_HOURS: '24', MAX_DAYS_AHEAD: '60' }, opts.props),
    availability: opts.availability || [],
    calendars: { 'owner@example.com': [], 'work@example.com': [], 'personal@example.com': [] },
    calendarLookups: [], freebusyCalls: 0, inserts: [], patches: [], removes: [], mails: [], invitations: [],
    lockHeld: false, lockCalls: 0, cache: {}, onInsert: null, busyError: null, insertError: null, patchError: null,
    loseInsertResponse: false, mailError: null, mailQuota: 100, meetMode: 'ready', cachePutError: null, logs: [],
  };
  const cacheApi = {
    get: k => (k in env.cache ? env.cache[k] : null),
    put: (k, v, ttl) => {
      if (env.cachePutError) throw new Error(env.cachePutError);
      if (k.length > 250) throw new Error('Argument too large: key');
      if (Buffer.byteLength(v) > 100 * 1024) throw new Error('Argument too large: value');
      if (ttl > 21600) throw new Error('Invalid expiration');
      env.cache[k] = v;
    },
    remove: k => { delete env.cache[k]; },
    removeAll: keys => keys.forEach(k => { delete env.cache[k]; }),
  };
  const propsApi = {
    getProperty: k => (k in env.props ? env.props[k] : null),
    setProperty: (k, v) => { if (Buffer.byteLength(String(v)) > 9 * 1024) throw new Error('Argument too large'); env.props[k] = String(v); return propsApi; },
    deleteProperty: k => { delete env.props[k]; return propsApi; },
    getProperties: () => Object.assign({}, env.props),
  };
  const FakeDate = class extends Date { static now() { return env.now; } };
  const findEvent = (calId, id) => (env.calendars[calId] || []).find(e => e.id === id);
  const applyMeet = ev => {
    if (env.meetMode === 'ready') { ev.hangoutLink = 'https://meet.google.com/abc-defg-hij'; ev.conferenceData.createRequest.status = { statusCode: 'success' }; }
    else ev.conferenceData.createRequest.status = { statusCode: env.meetMode === 'failure' ? 'failure' : 'pending' };
  };
  const noteInvitation = (ev, args) => {
    if (args && args.sendUpdates && args.sendUpdates !== 'none' && (ev.attendees || []).length) env.invitations.push(ev.attendees.map(a => a.email));
  };
  env.resolveMeet = () => Object.values(env.calendars).flat().forEach(ev => {
    if (ev.conferenceData && ev.conferenceData.createRequest) { ev.hangoutLink = 'https://meet.google.com/xyz-pend-ing'; ev.conferenceData.createRequest.status = { statusCode: 'success' }; }
  });
  const ctx = {
    Date: FakeDate, JSON, Math, Number, String, Object, Array, isFinite, Error, RegExp,
    PropertiesService: { getScriptProperties: () => propsApi },
    CacheService: { getScriptCache: () => cacheApi },
    LockService: { getScriptLock: () => ({
      tryLock: () => { env.lockCalls++; if (env.lockHeld) return false; env.lockHeld = true; return true; },
      releaseLock: () => { env.lockHeld = false; } }) },
    Utilities: {
      formatDate: (d, tz, fmt) => {
        const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit',
          day: '2-digit', hour: '2-digit', minute: '2-digit' }).formatToParts(d).map(x => [x.type, x.value]));
        return fmt === 'yyyy-MM-dd' ? `${p.year}-${p.month}-${p.day}` : `${p.hour}:${p.minute}`;
      },
      getUuid: () => crypto.randomUUID(),
      DigestAlgorithm: { SHA_256: 'SHA_256' },
      Charset: { UTF_8: 'UTF_8' },
      // Like Apps Script: an array of signed bytes.
      computeDigest: (alg, text) => Array.from(crypto.createHash('sha256').update(text, 'utf8').digest()).map(b => (b > 127 ? b - 256 : b)),
      newBlob: text => ({ getBytes: () => Array.from(Buffer.from(text, 'utf8')) }),
    },
    MailApp: {
      getRemainingDailyQuota: () => env.mailQuota,
      sendEmail: msg => { if (env.mailError) throw new Error(env.mailError); env.mailQuota--; env.mails.push(clone(msg)); },
    },
    Logger: { log: msg => { env.logs.push(msg); } },
    ContentService: { MimeType: { JSON: 'json' }, createTextOutput: t => ({ text: t, setMimeType() { return this; } }) },
    CalendarApp: { getCalendarById: id => {
      env.calendarLookups.push(id);
      if (id === env.props.BOOKING_CALENDAR_ID) return { getEvents: () => { throw new Error('the booking calendar is never listed'); } };
      if (id !== env.props.AVAILABILITY_CALENDAR_ID) return null;
      return { getEvents: (from, to) => env.availability.filter(w => w.start < to.getTime() && w.end > from.getTime()).map(w => ({
        isAllDayEvent: () => !!w.allDay, getStartTime: () => new Date(w.start), getEndTime: () => new Date(w.end) })) };
    } },
    Calendar: {
      Freebusy: { query: req => {
        env.freebusyCalls++;
        if (env.busyError) throw new Error(env.busyError);
        const calendars = {};
        req.items.forEach(({ id }) => {
          const evs = env.calendars[id];
          if (!evs) { calendars[id] = { errors: [{ reason: 'notFound' }] }; return; }
          // Like the real API: intervals only, never the title; cancelled events do not block.
          calendars[id] = { busy: evs.filter(e => e.status !== 'cancelled' && e.start < Date.parse(req.timeMax) && e.end > Date.parse(req.timeMin))
            .map(e => ({ start: new Date(e.start).toISOString(), end: new Date(e.end).toISOString() })) };
        });
        return { calendars };
      } },
      Events: {
        insert: (resource, calId, args) => {
          if (env.insertError) throw new Error(env.insertError);
          if (resource.id && findEvent(calId, resource.id)) throw new Error('The requested identifier already exists.');
          env.inserts.push(clone({ resource, calId, args }));
          const ev = Object.assign(clone(resource), { id: resource.id || 'ev' + env.inserts.length, status: 'confirmed',
            start: Date.parse(resource.start.dateTime), end: Date.parse(resource.end.dateTime) });
          if (ev.conferenceData && ev.conferenceData.createRequest) applyMeet(ev);
          env.calendars[calId].push(ev);
          noteInvitation(ev, args);
          if (env.onInsert) env.onInsert();
          if (env.loseInsertResponse) { env.loseInsertResponse = false; throw new Error('Timeout: response lost'); }
          return clone(ev);
        },
        get: (calId, id) => { const ev = findEvent(calId, id); if (!ev) throw new Error('Not Found'); return clone(ev); },
        patch: (resource, calId, id, args) => {
          if (env.patchError) throw new Error(env.patchError);
          const ev = findEvent(calId, id);
          if (!ev || ev.status === 'cancelled') throw new Error('Not Found');
          env.patches.push(clone({ resource, calId, id, args }));
          const sameConference = ev.conferenceData && resource.conferenceData &&
            ev.conferenceData.createRequest.requestId === resource.conferenceData.createRequest.requestId;
          if (!sameConference) Object.assign(ev, clone(resource));
          else Object.assign(ev, clone(Object.assign({}, resource, { conferenceData: undefined })));
          if (resource.conferenceData && !sameConference) applyMeet(ev);
          noteInvitation(ev, args);
          return clone(ev);
        },
        remove: (calId, id) => { const ev = findEvent(calId, id); if (!ev || ev.status === 'cancelled') throw new Error('Resource has been deleted'); ev.status = 'cancelled'; env.removes.push(id); },
      },
    },
  };
  vm.createContext(ctx);
  vm.runInContext(CODE, ctx);
  env.get = (params) => JSON.parse(vm.runInContext('doGet', ctx)({ parameter: params }).text);
  env.post = (body, raw) => JSON.parse(vm.runInContext('doPost', ctx)({ postData: { contents: raw !== undefined ? raw : JSON.stringify(body) } }).text);
  env.rawGet = (params) => vm.runInContext('doGet', ctx)({ parameter: params }).text;
  env.fn = name => vm.runInContext(name, ctx);
  env.book = over => env.post(goodBooking(over));
  env.token = (i = env.mails.length - 1) => /#confirm=([0-9a-f]{32}\.[0-9a-f]{64})\n/.exec(env.mails[i].body)[1];
  env.confirm = token => env.post({ op: 'confirm', token: token || env.token() });
  env.status = token => env.post({ op: 'status', token: token || env.token() });
  env.bookAndConfirm = over => { const b = env.book(over); assert.strictEqual(b.ok, true, JSON.stringify(b)); return env.confirm(); };
  env.live = calId => env.calendars[calId || 'owner@example.com'].filter(e => e.status !== 'cancelled');
  return env;
}

// Monday 2 Nov 2026 09:00-13:00 Madrid (CET) = 08:00Z-12:00Z.
const MONDAY = [{ start: Z('2026-11-02T08:00:00Z'), end: Z('2026-11-02T12:00:00Z') }];
const starts = r => r.slots.map(s => s.start.slice(11, 16));
const rid = () => 'req-' + crypto.randomUUID();
const goodBooking = (over = {}) => Object.assign({ op: 'book', requestId: rid(), name: 'Ana Pérez', email: 'Ana@Example.com', start: '2026-11-02T09:00:00.000Z', duration: 60, modality: 'virtual', notes: 'Hola' }, over);

const scenarios = {
  durations_30_60_120_180() {
    const env = makeEnv({ availability: MONDAY });
    const counts = [30, 60, 120, 180].map(d => env.get({ action: 'slots', duration: String(d) }).slots.length);
    assert.deepStrictEqual(counts, [8, 7, 5, 3]);
    const r = env.get({ action: 'slots', duration: '180' });
    assert.deepStrictEqual(starts(r), ['08:00', '08:30', '09:00']);
    assert.strictEqual(Date.parse(r.slots[0].end) - Date.parse(r.slots[0].start), 180 * 60000);
  },
  durations_30_60_120_180_book_and_confirm_end_to_end() {
    const env = makeEnv({ availability: [{ start: Z('2026-11-02T08:00:00Z'), end: Z('2026-11-02T20:00:00Z') }] });
    [[30, '08:00'], [60, '09:00'], [120, '11:00'], [180, '14:00']].forEach(([duration, hm], i) => {
      const start = `2026-11-02T${hm}:00.000Z`;
      const b = env.book({ duration, start, email: `p${i}@example.com` });
      assert.deepStrictEqual([b.ok, b.status, b.start, Date.parse(b.end) - Date.parse(b.start)], [true, 'verification_sent', start, duration * 60000]);
      const c = env.confirm();
      assert.deepStrictEqual([c.ok, c.status, c.emailVerified, c.meet.status], [true, 'confirmed', true, 'ready']);
    });
    assert.strictEqual(env.live().length, 4);
    assert.deepStrictEqual(env.invitations, [['p0@example.com'], ['p1@example.com'], ['p2@example.com'], ['p3@example.com']]);
  },
  slots_never_leave_the_window_and_are_on_the_half_hour() {
    const env = makeEnv({ availability: [{ start: Z('2026-11-02T08:10:00Z'), end: Z('2026-11-02T10:20:00Z') }] });
    const r = env.get({ action: 'slots', duration: '60' });
    assert.deepStrictEqual(starts(r), ['08:30', '09:00']);
  },
  all_day_events_are_ignored() {
    const env = makeEnv({ availability: [{ start: Z('2026-11-02T00:00:00Z'), end: Z('2026-11-03T00:00:00Z'), allDay: true }] });
    assert.strictEqual(env.get({ action: 'slots', duration: '30' }).slots.length, 0);
  },
  buffer_between_meetings() {
    const env = makeEnv({ availability: MONDAY, props: { BUFFER_MINUTES: '15' } });
    env.calendars['work@example.com'].push({ start: Z('2026-11-02T10:00:00Z'), end: Z('2026-11-02T11:00:00Z') });
    assert.deepStrictEqual(starts(env.get({ action: 'slots', duration: '30' })), ['08:00', '08:30', '09:00', '11:30']);
    assert.deepStrictEqual(starts(env.get({ action: 'slots', duration: '60' })), ['08:00', '08:30']);
  },
  conflicts_from_any_configured_calendar() {
    const env = makeEnv({ availability: MONDAY });
    env.calendars['personal@example.com'].push({ start: Z('2026-11-02T08:00:00Z'), end: Z('2026-11-02T09:00:00Z') });
    env.calendars['work@example.com'].push({ start: Z('2026-11-02T11:00:00Z'), end: Z('2026-11-02T12:00:00Z') });
    assert.deepStrictEqual(starts(env.get({ action: 'slots', duration: '60' })), ['09:00', '09:30', '10:00']);
    assert.strictEqual(env.book({ start: '2026-11-02T08:00:00.000Z' }).error, 'slot_unavailable');
    assert.strictEqual(env.book({ start: '2026-11-02T10:30:00.000Z' }).error, 'slot_unavailable');
    assert.strictEqual(env.inserts.length, 0);
  },
  private_event_details_never_leak_and_only_freebusy_is_read() {
    const env = makeEnv({ availability: MONDAY });
    env.calendars['work@example.com'].push({ start: Z('2026-11-02T10:00:00Z'), end: Z('2026-11-02T11:00:00Z'), title: 'SECRET-DOCTOR', attendees: ['x@y.z'] });
    const text = env.rawGet({ action: 'slots', duration: '30' });
    assert.ok(!/SECRET|doctor|x@y\.z/i.test(text));
    assert.deepStrictEqual(env.calendarLookups, ['avail@group.calendar.google.com']);
  },
  unreadable_busy_calendar_fails_closed() {
    const env = makeEnv({ availability: MONDAY, props: { BUSY_CALENDAR_IDS: 'work@example.com,missing@example.com' } });
    const r = env.get({ action: 'slots', duration: '30' });
    assert.deepStrictEqual([r.ok, r.error], [false, 'unavailable']);
    const b = env.book();
    assert.strictEqual(b.error, 'unavailable');
    assert.deepStrictEqual([env.inserts.length, env.mails.length], [0, 0]);
  },
  min_notice_and_max_ahead() {
    const env = makeEnv({ now: Z('2026-11-01T09:00:00Z'), availability: [{ start: Z('2026-11-01T00:00:00Z'), end: Z('2027-02-01T00:00:00Z') }],
      props: { MIN_NOTICE_HOURS: '24', MAX_DAYS_AHEAD: '3' } });
    const r = env.get({ action: 'slots', duration: '30' });
    assert.strictEqual(r.slots[0].start, '2026-11-02T09:00:00.000Z');
    assert.strictEqual(r.slots[r.slots.length - 1].end, '2026-11-04T09:00:00.000Z');
  },
  dst_autumn_change_keeps_real_durations_and_madrid_labels() {
    // 25 Oct 2026: 03:00 CEST becomes 02:00 CET at 01:00Z.
    const env = makeEnv({ now: Z('2026-10-20T00:00:00Z'), availability: [{ start: Z('2026-10-25T00:00:00Z'), end: Z('2026-10-25T04:00:00Z') }] });
    const r = env.get({ action: 'slots', duration: '180' });
    assert.deepStrictEqual(r.slots.map(s => s.time), ['02:00', '02:30', '02:00']);
    assert.ok(r.slots.every(s => s.day === '2026-10-25'));
    assert.ok(r.slots.every(s => Date.parse(s.end) - Date.parse(s.start) === 180 * 60000));
    assert.strictEqual(r.timeZone, 'Europe/Madrid');
  },
  dst_spring_change_skips_the_missing_hour() {
    // 28 Mar 2027: 02:00 CET becomes 03:00 CEST at 01:00Z.
    const env = makeEnv({ now: Z('2027-03-20T00:00:00Z'), availability: [{ start: Z('2027-03-28T00:00:00Z'), end: Z('2027-03-28T03:00:00Z') }] });
    const r = env.get({ action: 'slots', duration: '60' });
    assert.deepStrictEqual(r.slots.map(s => s.time), ['01:00', '01:30', '03:00', '03:30', '04:00']);
    assert.ok(r.slots.every(s => Date.parse(s.end) - Date.parse(s.start) === 3600000));
  },

  // ----- invitations only after the address is proven -----
  invitation_is_never_sent_before_the_email_is_verified() {
    const env = makeEnv({ availability: MONDAY });
    const b = env.book({ email: 'victim@example.org', name: 'Buy cheap pills now', reason: 'Visit http://spam.example', notes: 'http://spam.example' });
    assert.deepStrictEqual([b.ok, b.status, b.meet, b.meetLink], [true, 'verification_sent', undefined, undefined]);
    const { resource, args } = env.inserts[0];
    assert.strictEqual(resource.attendees, undefined);
    assert.strictEqual(resource.conferenceData, undefined);
    assert.strictEqual(args.sendUpdates, 'none');
    assert.deepStrictEqual(env.invitations, []);
    // The only message is the fixed-text confirmation email: none of the visitor's text reaches the recipient.
    assert.strictEqual(env.mails.length, 1);
    const mail = env.mails[0];
    assert.strictEqual(mail.to, 'victim@example.org');
    assert.ok(!/pills|spam/i.test(mail.subject + mail.body), 'visitor text must not be emailed');
    assert.ok(mail.body.includes('https://luisguinea.com/agenda/#confirm='));
    assert.ok(mail.body.includes('2026-11-02') && mail.body.includes('10:00'), 'Madrid local time in the email');
    // The secret is only stored hashed.
    const secret = env.token().split('.')[1];
    assert.ok(!JSON.stringify(env.props).includes(secret));
  },
  confirmation_adds_attendee_sends_invitation_and_requests_meet() {
    const env = makeEnv({ availability: MONDAY });
    env.book();
    const c = env.confirm();
    assert.deepStrictEqual([c.ok, c.status, c.emailVerified, c.start, c.end], [true, 'confirmed', true, '2026-11-02T09:00:00.000Z', '2026-11-02T10:00:00.000Z']);
    assert.deepStrictEqual(c.meet, { status: 'ready', link: 'https://meet.google.com/abc-defg-hij' });
    assert.strictEqual(env.patches.length, 1);
    const { resource, calId, args } = env.patches[0];
    assert.strictEqual(calId, 'owner@example.com');
    assert.deepStrictEqual(args, { conferenceDataVersion: 1, sendUpdates: 'all' });
    assert.strictEqual(resource.conferenceData.createRequest.conferenceSolutionKey.type, 'hangoutsMeet');
    assert.deepStrictEqual(resource.attendees, [{ email: 'ana@example.com', displayName: 'Ana Pérez' }]);
    assert.strictEqual(env.inserts[0].resource.start.timeZone, 'Europe/Madrid');
    assert.deepStrictEqual(env.invitations, [['ana@example.com']]);
    assert.strictEqual(env.lockHeld, false);
  },
  wrong_or_forged_token_is_rejected_without_side_effects() {
    const env = makeEnv({ availability: MONDAY });
    env.book();
    const [id, secret] = env.token().split('.');
    const bad = [id + '.' + 'f'.repeat(64), 'a'.repeat(32) + '.' + secret, id, '', 42, id + '.' + secret.toUpperCase()];
    bad.forEach(token => assert.strictEqual(env.post({ op: 'confirm', token }).error, 'invalid_token', String(token).slice(0, 20)));
    assert.strictEqual(env.post({ op: 'confirm', token: env.token(), extra: 1 }).error, 'invalid_token');
    assert.strictEqual(env.post({ op: 'status', token: id + '.' + 'f'.repeat(64) }).error, 'invalid_token');
    assert.deepStrictEqual([env.patches.length, env.invitations.length], [0, 0]);
  },
  unconfirmed_hold_expires_and_frees_the_slot_without_inviting() {
    const env = makeEnv({ availability: MONDAY, props: { HOLD_MINUTES: '30' } });
    const b = env.book();
    assert.strictEqual(b.expiresAt, new Date(NOW + 30 * 60000).toISOString());
    assert.ok(!starts(env.get({ action: 'slots', duration: '60' })).includes('09:00'), 'held slot is not offered');
    const token = env.token();
    assert.strictEqual(env.status(token).status, 'verification_sent');
    env.now += 31 * 60000;
    assert.ok(starts(env.get({ action: 'slots', duration: '60' })).includes('09:00'), 'expired hold is released on the next listing');
    assert.strictEqual(env.live().length, 0);
    assert.strictEqual(env.confirm(token).error, 'invalid_token');
    assert.deepStrictEqual(env.invitations, []);
  },
  confirm_after_expiry_before_any_sweep_reports_expired() {
    const env = makeEnv({ availability: MONDAY });
    env.book();
    env.now += 31 * 60000;
    assert.strictEqual(env.confirm().error, 'expired');
    assert.strictEqual(env.live().length, 0);
    assert.deepStrictEqual([env.patches.length, env.invitations.length], [0, 0]);
  },
  hold_deleted_by_owner_cannot_be_confirmed() {
    const env = makeEnv({ availability: MONDAY });
    env.book();
    env.live()[0].status = 'cancelled';
    assert.strictEqual(env.confirm().error, 'slot_unavailable');
    assert.strictEqual(env.invitations.length, 0);
  },
  email_failure_releases_the_hold_and_counts_nothing() {
    const env = makeEnv({ availability: MONDAY, props: { RATE_PER_EMAIL_HOUR: '1' } });
    env.mailError = 'Service invoked too many times';
    assert.strictEqual(env.book().error, 'unavailable');
    assert.strictEqual(env.live().length, 0);
    env.mailError = null;
    const b = env.book();
    assert.strictEqual(b.ok, true, 'the failed attempt did not use the quota');
    env.mailQuota = 0;
    assert.strictEqual(env.book({ email: 'z@example.com', start: '2026-11-02T11:00:00.000Z' }).error, 'unavailable');
  },

  // ----- modality: virtual (Google Meet) or in person (no conference, place to be agreed) -----
  virtual_booking_keeps_meet_and_carries_modality_and_reason() {
    const env = makeEnv({ availability: MONDAY });
    const b = env.book({ lang: 'es', reason: 'Colaborar en un disco', notes: 'Traigo maquetas' });
    assert.deepStrictEqual([b.ok, b.status, b.modality, b.reason], [true, 'verification_sent', 'virtual', 'Colaborar en un disco']);
    const hold = env.inserts[0].resource;
    assert.strictEqual(hold.summary, '[Pendiente de confirmar] Encuentro virtual con Ana Pérez');
    assert.strictEqual(hold.description, 'Modalidad: Virtual (Google Meet)\nMotivo: Colaborar en un disco\nNotas: Traigo maquetas');
    assert.deepStrictEqual([hold.location, hold.conferenceData, hold.attendees], [undefined, undefined, undefined]);
    assert.ok(env.mails[0].body.includes('un encuentro virtual (Google Meet)'));
    assert.ok(!/disco|maquetas/.test(env.mails[0].body), 'reason and notes are not emailed to an unverified address');
    const c = env.confirm();
    assert.deepStrictEqual([c.status, c.modality, c.reason, c.meet], ['confirmed', 'virtual', 'Colaborar en un disco', { status: 'ready', link: 'https://meet.google.com/abc-defg-hij' }]);
    const { resource, args } = env.patches[0];
    assert.deepStrictEqual(args, { conferenceDataVersion: 1, sendUpdates: 'all' });
    assert.strictEqual(resource.conferenceData.createRequest.conferenceSolutionKey.type, 'hangoutsMeet');
    assert.strictEqual(resource.summary, 'Encuentro virtual con Ana Pérez');
    const ev = env.live()[0];
    assert.strictEqual(ev.hangoutLink, 'https://meet.google.com/abc-defg-hij');
    assert.strictEqual(ev.description, hold.description, 'the invitation keeps format and reason');
    assert.strictEqual(ev.extendedProperties.private.lgModality, 'virtual');
    assert.deepStrictEqual(env.invitations, [['ana@example.com']]);
  },
  in_person_booking_sends_invitation_without_any_conference() {
    const env = makeEnv({ availability: MONDAY });
    const body = goodBooking({ modality: 'in_person', reason: 'Tomar un café' });
    const b = env.post(body);
    assert.deepStrictEqual([b.ok, b.status, b.modality, b.reason], [true, 'verification_sent', 'in_person', 'Tomar un café']);
    const hold = env.inserts[0].resource;
    assert.strictEqual(hold.summary, '[Awaiting confirmation] In-person meeting with Ana Pérez');
    assert.strictEqual(hold.location, 'To be agreed');
    assert.strictEqual(hold.description, 'Format: In person\nPlace: to be agreed. Luis will write to you to agree on it.\nReason: Tomar un café\nNotes: Hola');
    assert.strictEqual(hold.conferenceData, undefined);
    assert.ok(env.mails[0].body.includes('an in-person meeting of 60 minutes'));
    assert.ok(env.mails[0].body.includes('The place is still to be agreed'));
    assert.ok(!/café|Google Meet/.test(env.mails[0].body));
    // Same request id with another format is a different request, never a silent change of the booking.
    assert.strictEqual(env.post(Object.assign({}, body, { modality: 'virtual' })).error, 'invalid_request');
    const c = env.confirm();
    assert.deepStrictEqual([c.ok, c.status, c.emailVerified, c.modality, c.reason, c.meet], [true, 'confirmed', true, 'in_person', 'Tomar un café', { status: 'none' }]);
    const { resource, args } = env.patches[0];
    assert.deepStrictEqual(args, { sendUpdates: 'all' }, 'no conferenceDataVersion: Meet cannot be created');
    assert.strictEqual(resource.conferenceData, undefined);
    assert.strictEqual(resource.summary, 'In-person meeting with Ana Pérez');
    assert.deepStrictEqual(resource.attendees, [{ email: 'ana@example.com', displayName: 'Ana Pérez' }]);
    const ev = env.live()[0];
    assert.deepStrictEqual([ev.conferenceData, ev.hangoutLink, ev.location], [undefined, undefined, 'To be agreed']);
    assert.strictEqual(ev.extendedProperties.private.lgModality, 'in_person');
    assert.deepStrictEqual(env.invitations, [['ana@example.com']]);
    // Repeated clicks, status polls and retries never add a conference or a second invitation.
    assert.deepStrictEqual(env.confirm(), c);
    assert.deepStrictEqual(env.status().meet, { status: 'none' });
    assert.strictEqual(env.post(body).status, 'confirmed');
    assert.deepStrictEqual([env.inserts.length, env.patches.length, env.mails.length, env.invitations.length], [1, 1, 1, 1]);
    assert.ok(env.live().every(e => !e.conferenceData && !e.hangoutLink));
  },
  in_person_in_spanish_says_the_place_is_pending() {
    const env = makeEnv({ availability: MONDAY });
    env.book({ modality: 'in_person', lang: 'es', reason: '' });
    const hold = env.inserts[0].resource;
    assert.strictEqual(hold.summary, '[Pendiente de confirmar] Encuentro presencial con Ana Pérez');
    assert.strictEqual(hold.location, 'Pendiente de acordar');
    assert.strictEqual(hold.description, 'Modalidad: Presencial\nLugar: pendiente de acordar. Luis te escribirá para acordarlo.\nNotas: Hola');
    assert.ok(env.mails[0].body.includes('un encuentro presencial de 60 minutos'));
    assert.ok(env.mails[0].body.includes('El lugar está pendiente de acordar'));
    const c = env.confirm();
    assert.deepStrictEqual([c.modality, c.reason, c.meet], ['in_person', '', { status: 'none' }]);
    assert.strictEqual(env.patches[0].resource.conferenceData, undefined);
  },
  in_person_and_virtual_share_availability_holds_and_expiry() {
    const env = makeEnv({ availability: MONDAY });
    assert.strictEqual(env.book({ modality: 'in_person' }).ok, true);
    assert.strictEqual(env.book({ email: 'b@example.com', modality: 'virtual' }).error, 'slot_unavailable', 'an in-person hold blocks the time');
    assert.ok(!starts(env.get({ action: 'slots', duration: '60' })).includes('09:00'));
    const token = env.token();
    env.now += 31 * 60000;
    assert.strictEqual(env.confirm(token).error, 'expired');
    assert.deepStrictEqual([env.live().length, env.invitations.length], [0, 0]);
    assert.strictEqual(env.book({ email: 'b@example.com', modality: 'virtual' }).ok, true, 'the released time can be booked virtually');
  },

  // ----- duplicates, concurrency and retries -----
  duplicate_booking_of_same_or_overlapping_slot_is_rejected() {
    const env = makeEnv({ availability: MONDAY });
    assert.strictEqual(env.book().ok, true);
    // A pending hold already blocks the time for everybody else.
    assert.strictEqual(env.book({ email: 'other@example.com' }).error, 'slot_unavailable');
    env.confirm();
    assert.strictEqual(env.book({ email: 'o2@example.com', start: '2026-11-02T09:30:00.000Z', duration: 30 }).error, 'slot_unavailable');
    assert.strictEqual(env.book({ email: 'o3@example.com', start: '2026-11-02T08:30:00.000Z', duration: 60 }).error, 'slot_unavailable');
    assert.strictEqual(env.inserts.length, 1);
  },
  simultaneous_request_while_lock_is_held_gets_busy() {
    const env = makeEnv({ availability: MONDAY });
    let nested;
    env.onInsert = () => { env.onInsert = null; nested = env.book({ email: 'late@example.com' }); };
    assert.strictEqual(env.book().ok, true);
    assert.strictEqual(nested.error, 'busy');
    assert.strictEqual(env.inserts.length, 1);
    assert.strictEqual(env.lockHeld, false);
  },
  availability_is_rechecked_inside_the_lock_after_a_stale_listing() {
    const env = makeEnv({ availability: MONDAY });
    const listed = env.get({ action: 'slots', duration: '60' });
    assert.ok(starts(listed).includes('09:00'));
    env.calendars['work@example.com'].push({ start: Z('2026-11-02T09:00:00Z'), end: Z('2026-11-02T10:00:00Z') });
    // The cached listing still shows 09:00, but the booking re-reads the calendars inside the lock.
    assert.ok(starts(env.get({ action: 'slots', duration: '60' })).includes('09:00'));
    assert.strictEqual(env.book().error, 'slot_unavailable');
    assert.strictEqual(env.inserts.length, 0);
  },
  retry_with_the_same_request_id_returns_the_same_result_without_duplicates() {
    const env = makeEnv({ availability: MONDAY });
    const body = goodBooking();
    const first = env.post(body);
    const retry = env.post(body);
    assert.deepStrictEqual(retry, first);
    assert.deepStrictEqual([env.inserts.length, env.mails.length], [1, 1]);
    // Same id with different content is not a retry.
    assert.strictEqual(env.post(Object.assign({}, body, { start: '2026-11-02T10:00:00.000Z' })).error, 'invalid_request');
    // Retries after confirmation keep answering, still without new events or emails.
    env.confirm();
    assert.deepStrictEqual(env.post(body).status, 'confirmed');
    assert.deepStrictEqual([env.inserts.length, env.mails.length, env.patches.length], [1, 1, 1]);
  },
  retry_after_a_lost_calendar_response_reuses_the_event() {
    const env = makeEnv({ availability: MONDAY });
    const body = goodBooking();
    env.loseInsertResponse = true; // the event is created but the API call fails (timeout)
    const first = env.post(body);
    assert.deepStrictEqual([first.ok, first.status], [true, 'verification_sent'], 'the existing event with our id is reused');
    assert.strictEqual(env.live().length, 1);
    // A different booking can never take over that event id.
    env.loseInsertResponse = true;
    const other = env.book({ email: 'b@example.com', start: '2026-11-02T11:00:00.000Z' });
    assert.strictEqual(other.ok, true);
    assert.strictEqual(env.live().length, 2);
    assert.strictEqual(new Set(env.live().map(e => e.id)).size, 2);
  },
  retry_after_a_crash_before_the_email_left_sends_one_new_link() {
    const env = makeEnv({ availability: MONDAY });
    const body = goodBooking();
    env.post(body);
    // Rewind to the state of a run that stopped after storing the hold but before sending the email.
    const key = Object.keys(env.props).find(k => k.startsWith('bk:'));
    env.props[key] = JSON.stringify(Object.assign(JSON.parse(env.props[key]), { mailed: false }));
    const oldToken = env.token();
    env.mails = [];
    const retry = env.post(body);
    assert.deepStrictEqual([retry.ok, retry.status, env.mails.length, env.live().length, env.inserts.length], [true, 'verification_sent', 1, 1, 1]);
    assert.strictEqual(env.confirm(oldToken).error, 'invalid_token', 'a link that was never delivered is not valid');
    assert.strictEqual(env.post(body).status, 'verification_sent');
    assert.strictEqual(env.mails.length, 1, 'no further emails once one has left');
    assert.strictEqual(env.confirm().status, 'confirmed');
  },
  confirming_twice_patches_once_and_keeps_one_conference() {
    const env = makeEnv({ availability: MONDAY });
    env.book();
    const a = env.confirm();
    const b = env.confirm();
    assert.deepStrictEqual(b, a);
    assert.deepStrictEqual([env.patches.length, env.invitations.length], [1, 1]);
  },
  lock_is_released_when_calendar_fails() {
    const env = makeEnv({ availability: MONDAY });
    env.insertError = 'boom';
    assert.strictEqual(env.book().error, 'unavailable');
    assert.strictEqual(env.lockHeld, false);
    assert.strictEqual(env.mails.length, 0);
    env.insertError = null;
    env.book();
    env.patchError = 'boom';
    assert.strictEqual(env.confirm().error, 'unavailable');
    assert.strictEqual(env.lockHeld, false);
    env.patchError = null;
    assert.strictEqual(env.confirm().status, 'confirmed', 'the link still works after a transient failure');
  },
  slot_outside_availability_or_notice_is_rejected() {
    const env = makeEnv({ availability: MONDAY });
    assert.strictEqual(env.book({ start: '2026-11-02T13:00:00.000Z' }).error, 'slot_unavailable');
    assert.strictEqual(env.book({ start: '2026-11-02T11:30:00.000Z', duration: 60 }).error, 'slot_unavailable');
    const soon = makeEnv({ now: Z('2026-11-02T07:00:00Z'), availability: MONDAY });
    assert.strictEqual(soon.book().error, 'slot_unavailable');
  },
  strict_validation_rejects_bad_input_without_touching_calendars() {
    const env = makeEnv({ availability: MONDAY, props: { RATE_PER_EMAIL_HOUR: '1000', RATE_GLOBAL_HOUR: '1000' } });
    const bad = {
      invalid_email: [{ email: 'not-an-email' }, { email: 'a@b' }, { email: 'a@@b.com' }, { email: 'a b@c.com' }, { email: 'a..b@c.com' },
        { email: 'a@c.com\nBcc: x@y.z' }, { email: 123 }, { email: 'x'.repeat(250) + '@c.com' }],
      invalid_name: [{ name: '' }, { name: 'A' }, { name: 'x'.repeat(81) }, { name: 'Ana\u0000' }, { name: 'Ana‮' }, { name: 5 }, { name: ['Ana'] }],
      invalid_duration: [{ duration: 45 }, { duration: '60' }, { duration: 0 }, { duration: -60 }, { duration: null }],
      invalid_start: [{ start: '2026-11-02T09:15:00.000Z' }, { start: 'tomorrow' }, { start: '2026-11-02T09:00:00+01:00' }, { start: 12345 }, { start: '2026-13-45T09:00:00Z' }],
      invalid_notes: [{ notes: 'x'.repeat(501) }, { notes: 'a\u0007b' }, { notes: 42 }],
      invalid_modality: [{ modality: undefined }, { modality: '' }, { modality: 'Virtual' }, { modality: 'hybrid' }, { modality: 1 }, { modality: ['virtual'] }],
      invalid_reason: [{ reason: 'x'.repeat(151) }, { reason: 'a\u0007b' }, { reason: 3 }, { reason: null }],
      invalid_request: [{ extra: 'x' }, { __proto__x: 1, admin: true }, { requestId: undefined }, { requestId: 'short' }, { requestId: 'x'.repeat(65) },
        { requestId: 'bad id with spaces!' }, { op: 'delete' }, { token: 'x' }],
      rejected: [{ website: 'http://spam' }],
    };
    Object.keys(bad).forEach(error => bad[error].forEach(over => {
      const r = env.post(goodBooking(over));
      assert.deepStrictEqual([r.ok, r.error], [false, error], JSON.stringify(over).slice(0, 60));
    }));
    ['', '{', '[]', 'null', '"x"', '1'].forEach(raw => assert.strictEqual(env.post(null, raw).error, 'invalid_request', raw));
    assert.strictEqual(env.post(null, JSON.stringify(goodBooking({ notes: 'x'.repeat(5000) }))).error, 'invalid_request');
    assert.deepStrictEqual([env.inserts.length, env.mails.length, env.lockCalls, env.freebusyCalls], [0, 0, 0, 0]);
    assert.deepStrictEqual(env.calendarLookups, []);
  },
  get_validation() {
    const env = makeEnv({ availability: MONDAY });
    ['45', '060', '60.0', '', undefined, '1e2', '-30'].forEach(d => assert.strictEqual(env.get({ action: 'slots', duration: d }).error, 'invalid_duration', String(d)));
    assert.strictEqual(env.get({ action: 'nope' }).error, 'invalid_request');
    assert.deepStrictEqual(env.get({ action: 'config' }).durations, [30, 60, 120, 180]);
  },

  // ----- limits -----
  rate_limits_failed_or_invalid_requests_never_block_other_visitors() {
    const env = makeEnv({ availability: MONDAY, props: { RATE_PER_EMAIL_HOUR: '3', RATE_GLOBAL_HOUR: '5' } });
    for (let n = 0; n < 100; n++) {
      env.book({ email: `attacker${n}@example.com`, start: '2026-11-02T13:00:00.000Z' }); // slot_unavailable
      env.book({ email: 'victim@example.com', start: '2026-11-02T13:00:00.000Z' });
      env.book({ email: 'bad-email' });
    }
    const legit = env.book({ email: 'victim@example.com' });
    assert.deepStrictEqual([legit.ok, legit.status], [true, 'verification_sent']);
  },
  rate_limits_count_only_emails_actually_sent() {
    const env = makeEnv({ availability: [{ start: Z('2026-11-02T08:00:00Z'), end: Z('2026-11-02T20:00:00Z') }],
      props: { RATE_PER_EMAIL_HOUR: '2', RATE_GLOBAL_HOUR: '4', HOLD_MINUTES: '5' } });
    const at = h => `2026-11-02T${String(h).padStart(2, '0')}:00:00.000Z`;
    // Per address: a second request while one is unconfirmed is refused, and at most 2 emails per hour.
    assert.strictEqual(env.book({ email: 'a@example.com', start: at(8) }).ok, true);
    assert.strictEqual(env.book({ email: 'a@example.com', start: at(9) }).error, 'pending_exists');
    env.now += 6 * 60000; // first hold expires
    assert.strictEqual(env.book({ email: 'a@example.com', start: at(10) }).ok, true);
    env.now += 6 * 60000;
    assert.strictEqual(env.book({ email: 'a@example.com', start: at(11) }).error, 'rate_limited');
    // Globally: holds created this hour, whoever asked.
    assert.strictEqual(env.book({ email: 'b@example.com', start: at(12) }).ok, true);
    assert.strictEqual(env.book({ email: 'c@example.com', start: at(13) }).ok, true);
    assert.strictEqual(env.book({ email: 'd@example.com', start: at(14) }).error, 'rate_limited');
    assert.strictEqual(env.mails.length, 4);
    env.now += 3600000; // next hour
    assert.strictEqual(env.book({ email: 'd@example.com', start: at(15) }).ok, true);
  },
  pending_holds_are_capped_so_the_calendar_cannot_be_filled() {
    const env = makeEnv({ availability: MONDAY, props: { MAX_PENDING_HOLDS: '2', RATE_GLOBAL_HOUR: '100' } });
    assert.strictEqual(env.book({ email: 'a@example.com', start: '2026-11-02T08:00:00.000Z' }).ok, true);
    assert.strictEqual(env.book({ email: 'b@example.com', start: '2026-11-02T09:00:00.000Z' }).ok, true);
    assert.strictEqual(env.book({ email: 'c@example.com', start: '2026-11-02T10:00:00.000Z' }).error, 'busy');
    env.confirm(env.token(0));
    assert.strictEqual(env.book({ email: 'c@example.com', start: '2026-11-02T10:00:00.000Z' }).ok, true, 'confirmed bookings do not count');
  },
  confirm_and_status_are_never_rate_limited() {
    const env = makeEnv({ availability: MONDAY, props: { RATE_GLOBAL_HOUR: '1' } });
    env.book();
    assert.strictEqual(env.book({ email: 'x@example.com', start: '2026-11-02T11:00:00.000Z' }).error, 'rate_limited');
    assert.strictEqual(env.confirm().status, 'confirmed');
    assert.strictEqual(env.status().status, 'confirmed');
  },
  long_email_does_not_overflow_cache_keys() {
    const env = makeEnv({ availability: MONDAY });
    const email = 'a'.repeat(64) + '@' + 'b'.repeat(63) + '.' + 'c'.repeat(63) + '.' + 'd'.repeat(45) + '.com';
    assert.strictEqual(email.length, 242);
    assert.strictEqual(env.book({ email }).ok, true);
    assert.ok(Object.keys(env.cache).every(k => k.length <= 250));
  },

  // ----- cache -----
  slot_listing_is_cached_to_protect_quota() {
    const env = makeEnv({ availability: MONDAY });
    env.get({ action: 'slots', duration: '30' });
    const n = env.calendarLookups.length;
    env.get({ action: 'slots', duration: '30' });
    assert.strictEqual(env.calendarLookups.length, n);
  },
  listing_too_big_for_the_cache_is_served_but_not_cached() {
    const env = makeEnv({ availability: [{ start: Z('2026-10-29T00:00:00Z'), end: Z('2026-12-27T00:00:00Z') }] });
    const text = env.rawGet({ action: 'slots', duration: '30' });
    const r = JSON.parse(text);
    assert.strictEqual(r.ok, true);
    assert.ok(Buffer.byteLength(text) > 100 * 1024, 'the scenario really exceeds the CacheService limit');
    assert.strictEqual(env.cache['slots:30'], undefined);
    const smallEnv = makeEnv({ availability: MONDAY });
    assert.strictEqual(smallEnv.get({ action: 'slots', duration: '30' }).ok, true);
    assert.ok(Buffer.byteLength(smallEnv.cache['slots:30']) <= 100 * 1024, 'normal listings are still cached');
  },
  cache_failure_never_breaks_the_listing() {
    const env = makeEnv({ availability: MONDAY });
    env.cachePutError = 'Service error: cache';
    assert.strictEqual(env.get({ action: 'slots', duration: '60' }).ok, true);
  },
  held_or_booked_slot_disappears_from_every_cached_listing() {
    const env = makeEnv({ availability: MONDAY });
    [30, 60, 120, 180].forEach(d => env.get({ action: 'slots', duration: String(d) }));
    env.book();
    [30, 60, 120, 180].forEach(d => {
      const r = env.get({ action: 'slots', duration: String(d) });
      assert.ok(r.slots.every(s => Date.parse(s.end) <= Z('2026-11-02T09:00:00Z') || Date.parse(s.start) >= Z('2026-11-02T10:00:00Z')), `duration ${d}`);
    });
    env.confirm();
    assert.ok(!starts(env.get({ action: 'slots', duration: '60' })).includes('09:00'));
  },

  // ----- Google Meet -----
  meet_link_is_only_reported_once_it_exists() {
    const env = makeEnv({ availability: MONDAY });
    env.meetMode = 'pending';
    env.book();
    const c = env.confirm();
    assert.deepStrictEqual([c.ok, c.status, c.meet], [true, 'confirmed', { status: 'pending' }]);
    assert.strictEqual(env.status().meet.status, 'pending');
    env.resolveMeet();
    assert.deepStrictEqual(env.status().meet, { status: 'ready', link: 'https://meet.google.com/xyz-pend-ing' });
    assert.deepStrictEqual(env.confirm().meet, { status: 'ready', link: 'https://meet.google.com/xyz-pend-ing' });
    assert.strictEqual(env.patches.length, 1);
  },
  meet_failure_is_reported_not_hidden() {
    const env = makeEnv({ availability: MONDAY });
    env.meetMode = 'failure';
    env.book();
    const c = env.confirm();
    assert.deepStrictEqual([c.ok, c.meet], [true, { status: 'failed' }]);
    assert.deepStrictEqual(env.invitations, [['ana@example.com']], 'the invitation is still sent');
  },
  meet_link_that_is_not_a_meet_url_is_not_trusted() {
    const fn = makeEnv().fn('meetState_');
    assert.deepStrictEqual(clone(fn({ hangoutLink: 'https://evil.example/x' })), { status: 'pending' });
    assert.deepStrictEqual(clone(fn({ conferenceData: { entryPoints: [{ entryPointType: 'video', uri: 'https://meet.google.com/aaa-bbbb-ccc' }] } })),
      { status: 'ready', link: 'https://meet.google.com/aaa-bbbb-ccc' });
  },
  check_setup_reports_without_side_effects() {
    const env = makeEnv({ availability: MONDAY });
    const r = JSON.parse(JSON.stringify(env.fn('checkSetup')()));
    assert.deepStrictEqual(r.slots, { 30: 8, 60: 7, 120: 5, 180: 3 });
    assert.deepStrictEqual([r.availabilityWindows, r.busyCalendarsReadable, r.bookingCalendarFound, r.timeZone], [1, 3, true, 'Europe/Madrid']);
    assert.deepStrictEqual([env.inserts.length, env.patches.length, env.mails.length, env.logs.length], [0, 0, 0, 1]);
    const broken = makeEnv({ availability: MONDAY, props: { BUSY_CALENDAR_IDS: 'missing@example.com' } });
    assert.throws(() => broken.fn('checkSetup')(), /busy_calendar_unreadable/);
  },
  missing_configuration_is_reported_not_guessed() {
    const env = makeEnv({ props: { AVAILABILITY_CALENDAR_ID: '' } });
    assert.strictEqual(env.get({ action: 'slots', duration: '30' }).error, 'not_configured');
    assert.strictEqual(env.book().error, 'not_configured');
    const bad = makeEnv({ availability: MONDAY, props: { CONFIRM_URL: 'http://luisguinea.com/agenda/' } });
    assert.strictEqual(bad.book().error, 'not_configured');
  },
};

const results = {};
Object.keys(scenarios).forEach(name => {
  try { scenarios[name](); results[name] = 'ok'; } catch (e) { results[name] = String(e && e.stack || e).split('\n').slice(0, 4).join(' | '); }
});
process.stdout.write(JSON.stringify(results));
