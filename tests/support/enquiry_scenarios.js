// Runs apps-script/Code.gs plus the proposal apps-script/proposals/enquiry.gs in a vm with mocked Google services and
// prints {scenario: "ok" | failure}. Driven by tests/test_formacion.py. No network, no Google account, no secrets.
// doPost is wired exactly as the proposal documents: op "enquiry" goes to handleEnquiry_, anything else to Code.gs.
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');

const ROOT = path.join(__dirname, '..', '..');
const CODE = fs.readFileSync(path.join(ROOT, 'apps-script', 'Code.gs'), 'utf8');
const ENQUIRY = fs.readFileSync(path.join(ROOT, 'apps-script', 'proposals', 'enquiry.gs'), 'utf8');
const NOW = Date.parse('2026-11-10T10:00:00Z');

function makeEnv(opts = {}) {
  const env = { now: NOW, cache: {}, props: Object.assign({}, opts.props), mails: [], mailQuota: opts.mailQuota === undefined ? 100 : opts.mailQuota,
    mailError: opts.mailError || null };
  const ctx = {
    Date: class extends Date { static now() { return env.now; } }, JSON, Math, Number, String, Object, Array, isFinite, Error, RegExp,
    CacheService: { getScriptCache: () => ({ get: k => (k in env.cache ? env.cache[k] : null), put: (k, v) => { env.cache[k] = v; } }) },
    PropertiesService: { getScriptProperties: () => ({ getProperty: k => (k in env.props ? env.props[k] : null) }) },
    Session: { getEffectiveUser: () => ({ getEmail: () => 'owner@example.com' }) },
    Utilities: {
      DigestAlgorithm: { SHA_256: 'SHA_256' }, Charset: { UTF_8: 'UTF_8' },
      computeDigest: (alg, text) => Array.from(crypto.createHash('sha256').update(text, 'utf8').digest()).map(b => (b > 127 ? b - 256 : b)),
    },
    MailApp: {
      getRemainingDailyQuota: () => env.mailQuota,
      sendEmail: msg => { if (env.mailError) throw new Error(env.mailError); env.mailQuota--; env.mails.push(JSON.parse(JSON.stringify(msg))); },
    },
    ContentService: { MimeType: { JSON: 'json' }, createTextOutput: t => ({ text: t, setMimeType() { return this; } }) },
    Logger: { log() {} },
  };
  vm.createContext(ctx);
  vm.runInContext(CODE + '\n' + ENQUIRY, ctx);
  const original = vm.runInContext('doPost', ctx), handle = vm.runInContext('handleEnquiry_', ctx), json = vm.runInContext('json_', ctx);
  const doPost = e => {
    let raw = null;
    try { raw = JSON.parse(e.postData.contents); } catch (x) { return original(e); }
    if (raw && raw.op === 'enquiry') return json(handle(raw, env.now));
    return original(e);
  };
  env.post = body => JSON.parse(doPost({ postData: { contents: JSON.stringify(body) } }).text);
  return env;
}

const GOOD = { op: 'enquiry', area: 'piano', level: 'base', format: 'online', name: 'Ana Prueba', email: 'ana@example.org',
  message: 'Quiero acompañarme al piano.\nTengo un teclado.', website: '', lang: 'es' };

const scenarios = {
  sends_one_email_to_luis_with_the_visitor_as_reply_to() {
    const env = makeEnv();
    assert.deepStrictEqual(env.post(GOOD), { ok: true });
    assert.strictEqual(env.mails.length, 1);
    const m = env.mails[0];
    assert.strictEqual(m.to, 'owner@example.com');
    assert.strictEqual(m.replyTo, 'ana@example.org');
    assert.ok(m.subject.includes('Piano') && m.subject.includes('Ana Prueba'));
    assert.ok(m.body.includes('Nivel: Tiene algo de base') && m.body.includes('Modalidad: Online'));
    assert.ok(m.body.includes('Quiero acompañarme al piano.\nTengo un teclado.'), 'line breaks are kept');
  },
  configured_recipient_wins() {
    const env = makeEnv({ props: { ENQUIRY_TO: 'clases@example.com' } });
    env.post(GOOD);
    assert.strictEqual(env.mails[0].to, 'clases@example.com');
  },
  never_emails_the_visitor() {
    const env = makeEnv();
    env.post(Object.assign({}, GOOD, { email: 'victim@example.net' }));
    assert.ok(env.mails.every(m => m.to === 'owner@example.com' && !m.cc && !m.bcc));
  },
  honeypot_looks_successful_and_sends_nothing() {
    const env = makeEnv();
    assert.deepStrictEqual(env.post(Object.assign({}, GOOD, { website: 'http://spam.example' })), { ok: true });
    assert.strictEqual(env.mails.length, 0);
  },
  strict_validation() {
    const env = makeEnv();
    const bad = [
      [{ area: 'guitarra' }, 'invalid_area'], [{ area: '' }, 'invalid_area'], [{ name: '' }, 'invalid_name'],
      [{ name: 'x'.repeat(81) }, 'invalid_name'], [{ email: 'no-es-correo' }, 'invalid_email'], [{ email: '' }, 'invalid_email'],
      [{ message: 'x'.repeat(1001) }, 'invalid_message'], [{ message: 'hola‮adios' }, 'invalid_message'],
      [{ level: 'experto' }, 'invalid_request'], [{ format: 'casa' }, 'invalid_request'], [{ extra: 1 }, 'invalid_request'],
      [{ name: 42 }, 'invalid_name'], [{ website: 3 }, 'invalid_request'],
    ];
    bad.forEach(([patch, error]) => assert.deepStrictEqual(env.post(Object.assign({}, GOOD, patch)), { ok: false, error }, JSON.stringify(patch)));
    assert.strictEqual(env.mails.length, 0);
    // Optional fields may be left empty.
    assert.deepStrictEqual(env.post({ op: 'enquiry', area: 'nose', name: 'Leo', email: 'leo@example.org' }), { ok: true });
  },
  header_injection_is_impossible() {
    const env = makeEnv();
    env.post(Object.assign({}, GOOD, { name: 'Ana\r\nBcc: x@example.com' }));
    assert.ok(env.mails.length === 0 || !/[\r\n]/.test(env.mails[0].subject));
  },
  rate_limited_per_address_and_globally() {
    const env = makeEnv();
    assert.deepStrictEqual(env.post(GOOD), { ok: true });
    assert.deepStrictEqual(env.post(GOOD), { ok: true });
    assert.deepStrictEqual(env.post(GOOD), { ok: false, error: 'rate_limited' });
    for (let i = 0; i < 25; i++) env.post(Object.assign({}, GOOD, { email: `p${i}@example.org` }));
    assert.strictEqual(env.mails.length, 20, 'global cap of 20 an hour');
    env.now += 3600000;
    assert.deepStrictEqual(env.post(GOOD), { ok: true }, 'a new hour resets the limits');
  },
  mail_failure_and_quota_are_reported_not_hidden() {
    assert.deepStrictEqual(makeEnv({ mailError: 'Service invoked too many times' }).post(GOOD), { ok: false, error: 'unavailable' });
    assert.deepStrictEqual(makeEnv({ mailQuota: 0 }).post(GOOD), { ok: false, error: 'unavailable' });
  },
  bookings_still_go_to_code_gs() {
    const env = makeEnv();
    const r = env.post({ op: 'status', token: 'nope' });
    assert.strictEqual(r.ok, false);
    assert.strictEqual(env.mails.length, 0);
  },
};

const results = {};
Object.keys(scenarios).forEach(name => {
  try { scenarios[name](); results[name] = 'ok'; } catch (e) { results[name] = String(e && e.stack || e).split('\n').slice(0, 3).join(' | '); }
});
process.stdout.write(JSON.stringify(results));
