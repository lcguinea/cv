#!/usr/bin/env node
// Local end-to-end environment for the class subscriptions, against the REAL Stripe API in TEST mode.
//
//   node tools/billing_dev_server.js --preview <dir built by build_formacion.py --preview> [--port 8792] [--state <file>]
//   stripe listen --forward-to http://127.0.0.1:8792/stripe/webhook      (in another terminal)
//
// What runs here:
//   /                 the site from the repository, with the preview pages (plans section, /alumnos/) laid over it
//   /exec             apps-script/Code.gs + Billing.gs (the production code) in a vm: Google services are the fakes of
//                     tests/support/billing_env.js (Sheets, Calendar, Mail...), UrlFetchApp is real HTTPS to Stripe
//   /stripe/webhook   workers/stripe-relay/worker.js (the production relay), forwarding to /exec
//   /__dev/...        helpers for the tests: mails, tables, hourly job, clock
//
// Secrets: none handled here. Stripe calls go through the logged-in Stripe CLI; the webhook secret comes from
// `stripe listen --print-secret` and stays in memory. Nothing secret is written to disk or logged. 127.0.0.1 only.
'use strict';
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawnSync, execFileSync } = require('child_process');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? acc.concat([[a.slice(2), all[i + 1]]]) : acc), []));
const PORT = Number(args.port || 8792);
const PREVIEW = args.preview ? path.resolve(args.preview) : null;
const STATE = args.state ? path.resolve(args.state) : null;

// The Stripe CLI (stripe login, sandbox "Luis Guinea Formacion (pruebas)") is the transport: it holds the credentials,
// so this server never sees or stores a key. A sandbox cannot move real money. Refuses to start on a live account.
function cli(args) {
  const r = spawnSync('stripe', args, { encoding: 'utf8', timeout: 60000 });
  const text = r.stdout || '';
  const at = text.indexOf('{');
  if (at < 0) throw new Error('stripe cli: ' + (r.stderr || text).slice(0, 200));
  return JSON.parse(text.slice(at));
}
const WHSEC = execFileSync('stripe', ['listen', '--print-secret'], { encoding: 'utf8' }).trim().split('\n').pop();
const RELAY_SECRET = crypto.randomBytes(32).toString('hex');
const PLACEHOLDER_KEY = 'rk_test_cli'; // satisfies the mode check of Billing.gs; never sent anywhere

// Synchronous Stripe calls for UrlFetchApp (Apps Script is synchronous), through the CLI.
function realFetch(url, o) {
  if (!/^https:\/\/api\.stripe\.com\/v1\//.test(url)) throw new Error('only the Stripe API is reachable from the dev backend');
  const [p, query] = url.replace('https://api.stripe.com', '').split('?');
  const params = (o.method === 'post' ? o.payload : query) || '';
  const args = [o.method === 'post' ? 'post' : 'get', p, '--stripe-version', o.headers['Stripe-Version']];
  params.split('&').filter(Boolean).forEach((kv) => { const [k, v] = kv.split('=').map(decodeURIComponent); args.push('-d', `${k}=${v}`); });
  if (o.headers['Idempotency-Key']) args.push('--idempotency', o.headers['Idempotency-Key']);
  const body = cli(args);
  if (body && body.livemode === true) throw new Error('live object received: stop');
  if (body && body.error) return { code: body.error.code === 'resource_missing' ? 404 : 400, body };
  return { code: 200, body };
}

const { makeEnv } = require(path.join(ROOT, 'tests', 'support', 'billing_env.js'));
const saved = STATE && fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : null;
const env = makeEnv({
  now: Date.now(),
  sheets: saved ? saved.sheets : { dev: {} },
  calendars: saved ? saved.calendars : undefined,
  props: {
    STRIPE_SECRET_KEY: PLACEHOLDER_KEY, STRIPE_MODE: 'test', LEDGER_SPREADSHEET_ID: 'dev', RELAY_SECRET,
    STRIPE_PRICE_WEEKLY: process.env.STRIPE_PRICE_WEEKLY || '', STRIPE_PRICE_BIWEEKLY: process.env.STRIPE_PRICE_BIWEEKLY || '',
    STRIPE_PORTAL_CONFIG: process.env.STRIPE_PORTAL_CONFIG || '',
    STUDENT_URL: `http://127.0.0.1:${PORT}/alumnos/`, PLANS_URL: `http://127.0.0.1:${PORT}/formacion/#planes`,
  },
  fetch: realFetch,
});
env.clockOffset = saved ? saved.clockOffset || 0 : 0;
function tick() { env.now = Date.now() + env.clockOffset; }
function persist() { if (STATE) fs.writeFileSync(STATE, JSON.stringify({ sheets: env.sheets, calendars: env.calendars, clockOffset: env.clockOffset }), { mode: 0o600 }); }

let relay = null;
import(pathToFileURL(path.join(ROOT, 'workers', 'stripe-relay', 'worker.js')).href).then((m) => { relay = m; });
const relayEnv = { STRIPE_WEBHOOK_SECRET: WHSEC, RELAY_SECRET, STRIPE_MODE: 'test', APPS_SCRIPT_URL: `http://127.0.0.1:${PORT}/exec` };

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.webp': 'image/webp',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.mp3': 'audio/mpeg', '.woff2': 'font/woff2', '.json': 'application/json', '.svg': 'image/svg+xml' };
function serveFile(req, res, urlPath) {
  let rel = decodeURIComponent(urlPath);
  if (rel.endsWith('/')) rel += 'index.html';
  const candidates = [PREVIEW && path.join(PREVIEW, rel), path.join(ROOT, rel)].filter(Boolean);
  const file = candidates.find((f) => (f.startsWith(ROOT + path.sep) || (PREVIEW && f.startsWith(PREVIEW + path.sep))) && fs.existsSync(f) && fs.statSync(f).isFile());
  if (!file) { res.writeHead(404); return res.end('Not found'); }
  const st = fs.statSync(file);
  const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (range && (range[1] !== '' || range[2] !== '')) {
    const start = range[1] === '' ? Math.max(0, st.size - Number(range[2])) : Number(range[1]);
    const end = range[1] !== '' && range[2] !== '' ? Math.min(Number(range[2]), st.size - 1) : st.size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${st.size}`, 'Content-Length': end - start + 1, 'Accept-Ranges': 'bytes' });
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store' });
  fs.createReadStream(file).pipe(res);
}
function json(res, obj, status = 200) { res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); }
function body(req) { return new Promise((ok) => { let b = ''; req.on('data', (c) => { b += c; }); req.on('end', () => ok(b)); }); }

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  try {
    tick();
    if (url.pathname === '/exec') {
      const out = req.method === 'POST' ? env.ctx.doPost({ postData: { contents: await body(req) } }) : env.ctx.doGet({ parameter: Object.fromEntries(url.searchParams) });
      persist();
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      return res.end(out.getContent());
    }
    if (url.pathname === '/stripe/webhook') {
      const raw = await body(req);
      const r = await relay.handle(new Request(url.href, { method: req.method, body: raw, headers: { 'stripe-signature': req.headers['stripe-signature'] || '' } }), relayEnv);
      res.writeHead(r.status, { 'Content-Type': 'text/plain' });
      return res.end(await r.text());
    }
    if (url.pathname === '/__dev/mails') return json(res, env.mails);
    if (url.pathname === '/__dev/table') return json(res, env.table(url.searchParams.get('name')));
    if (url.pathname === '/__dev/events') return json(res, env.events());
    if (url.pathname === '/__dev/hourly') { const r = env.hourly(); persist(); return json(res, r); }
    if (url.pathname === '/__dev/clock') {
      if (url.searchParams.get('set')) env.clockOffset = Number(url.searchParams.get('set')) - Date.now();
      if (url.searchParams.get('reset')) env.clockOffset = 0;
      tick(); persist();
      return json(res, { now: new Date(env.now).toISOString() });
    }
    if (url.pathname === '/__dev/props') {
      ['CREDIT_POLICY_ENFORCED', 'BILLING_CHECKOUT_ENABLED'].forEach((k) => { if (url.searchParams.has(k)) env.props[k] = url.searchParams.get(k); });
      return json(res, { CREDIT_POLICY_ENFORCED: env.props.CREDIT_POLICY_ENFORCED || 'false', BILLING_CHECKOUT_ENABLED: env.props.BILLING_CHECKOUT_ENABLED });
    }
    if (url.pathname === '/__dev/teacher-cancel') { env.deleteEvent(url.searchParams.get('event')); return json(res, { ok: true }); }
    return serveFile(req, res, url.pathname);
  } catch (e) {
    return json(res, { ok: false, error: 'dev_server', message: String(e.message).slice(0, 300) }, 500);
  }
}).listen(PORT, '127.0.0.1', () => console.log(`billing dev server on http://127.0.0.1:${PORT} (Stripe TEST mode)`));
