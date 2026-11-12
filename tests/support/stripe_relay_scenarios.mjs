// Scenarios for workers/stripe-relay/worker.js. Signatures are made exactly as Stripe documents them
// (v1 = HMAC-SHA256 of "<t>.<raw body>" with the endpoint secret). The Apps Script backend is a fake fetch.
// Prints {scenario: "ok" | failure}. Driven by tests/test_billing.py.
import assert from 'node:assert';
import crypto from 'node:crypto';
import { handle, parseSignatureHeader } from '../../workers/stripe-relay/worker.js';

const WHSEC = 'whsec_testsecretfortheworker';
const RELAY = 'ab'.repeat(32);
const NOW = Date.parse('2026-11-16T08:00:00Z');
const env = { STRIPE_WEBHOOK_SECRET: WHSEC, RELAY_SECRET: RELAY, STRIPE_MODE: 'test',
  APPS_SCRIPT_URL: 'https://script.google.com/macros/s/AKfakeIdForTests_123/exec' };

function event(over = {}) { return Object.assign({ id: 'evt_1TestEvent0001', object: 'event', type: 'invoice.paid', livemode: false, data: { object: { id: 'in_1' } } }, over); }
function sign(body, t = Math.floor(NOW / 1000), secret = WHSEC) {
  return `t=${t},v1=${crypto.createHmac('sha256', secret).update(`${t}.${body}`).digest('hex')}`;
}
function request(body, header, path = '/stripe/webhook', method = 'POST') {
  return new Request('https://relay.example.workers.dev' + path, { method, body: method === 'POST' ? body : undefined,
    headers: header ? { 'stripe-signature': header } : {} });
}
let calls = [];
function backend(answer) {
  calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init, body: JSON.parse(init.body) });
    if (answer === 'throw') throw new Error('network');
    return new Response(JSON.stringify(answer), { status: 200 });
  };
}
const run = (req, e = env) => handle(req, e, () => NOW);

const scenarios = {
  async valid_event_is_forwarded_with_relay_hmac_and_200() {
    backend({ ok: true });
    const body = JSON.stringify(event());
    const res = await run(request(body, sign(body)));
    assert.strictEqual(res.status, 200);
    assert.strictEqual(calls.length, 1);
    const m = calls[0].body;
    assert.deepStrictEqual(Object.keys(m).sort(), ['id', 'op', 'sig', 'ts', 'type']);
    assert.strictEqual(m.op, 'stripe_event');
    assert.strictEqual(m.sig, crypto.createHmac('sha256', RELAY).update(`${m.ts}.${m.id}`).digest('hex'));
    assert(!calls[0].init.body.includes('in_1'), 'the payload itself is not forwarded');
    assert.strictEqual(calls[0].init.headers['content-type'], 'text/plain;charset=utf-8');
  },
  async bad_or_missing_signature_is_rejected_without_forwarding() {
    backend({ ok: true });
    const body = JSON.stringify(event());
    for (const h of [null, 'garbage', sign(body, undefined, 'whsec_other'), sign(body + ' ')]) {
      const res = await run(request(body, h));
      assert.strictEqual(res.status, 400, String(h));
    }
    assert.strictEqual(calls.length, 0);
  },
  async old_or_future_timestamps_are_rejected() {
    backend({ ok: true });
    const body = JSON.stringify(event());
    assert.strictEqual((await run(request(body, sign(body, Math.floor(NOW / 1000) - 301)))).status, 400);
    assert.strictEqual((await run(request(body, sign(body, Math.floor(NOW / 1000) + 301)))).status, 400);
    assert.strictEqual(calls.length, 0);
  },
  async any_valid_v1_among_several_is_accepted() {
    backend({ ok: true });
    const body = JSON.stringify(event());
    const t = Math.floor(NOW / 1000);
    const header = `t=${t},v1=${'0'.repeat(64)},${sign(body).split(',')[1]},v0=abc`;
    assert.strictEqual((await run(request(body, header))).status, 200);
  },
  async other_mode_is_acknowledged_but_not_forwarded() {
    backend({ ok: true });
    const body = JSON.stringify(event({ livemode: true }));
    assert.strictEqual((await run(request(body, sign(body)))).status, 200);
    assert.strictEqual(calls.length, 0);
  },
  async backend_failures_make_stripe_retry() {
    const body = JSON.stringify(event());
    backend({ ok: false, error: 'busy' });
    assert.strictEqual((await run(request(body, sign(body)))).status, 503);
    backend('throw');
    assert.strictEqual((await run(request(body, sign(body)))).status, 502);
    backend({ ok: false, error: 'invalid_event' });
    assert.strictEqual((await run(request(body, sign(body)))).status, 200, 'refused for good: no endless retries');
  },
  async wrong_route_method_or_configuration() {
    backend({ ok: true });
    const body = JSON.stringify(event());
    assert.strictEqual((await run(request(body, sign(body), '/other'))).status, 404);
    assert.strictEqual((await run(request(body, sign(body), '/stripe/webhook', 'GET'))).status, 405);
    assert.strictEqual((await run(request(body, sign(body)), Object.assign({}, env, { APPS_SCRIPT_URL: 'https://evil.example/exec' }))).status, 500);
    assert.strictEqual((await run(request(body, sign(body)), Object.assign({}, env, { RELAY_SECRET: 'short' }))).status, 500);
    assert.strictEqual(calls.length, 0);
  },
  async malformed_events_are_rejected() {
    backend({ ok: true });
    for (const ev of [{ id: 'nope', object: 'event', type: 'x.y', livemode: false }, { id: 'evt_12345678', object: 'charge', type: 'a.b', livemode: false }]) {
      const body = JSON.stringify(ev);
      assert.strictEqual((await run(request(body, sign(body)))).status, 400);
    }
    const bad = 'not json';
    assert.strictEqual((await run(request(bad, sign(bad)))).status, 400);
    assert.strictEqual(calls.length, 0);
  },
  async header_parser_is_strict() {
    assert.strictEqual(parseSignatureHeader('t=1'), null);
    assert.strictEqual(parseSignatureHeader('v1=' + 'a'.repeat(64)), null);
    assert.deepStrictEqual(parseSignatureHeader('t=5,v1=' + 'a'.repeat(64)), { t: 5, v1: ['a'.repeat(64)] });
  },
};

const results = {};
for (const [name, fn] of Object.entries(scenarios)) {
  try { await fn(); results[name] = 'ok'; } catch (e) { results[name] = String(e && e.stack || e).split('\n').slice(0, 3).join(' | '); }
}
process.stdout.write(JSON.stringify(results, null, 1));
