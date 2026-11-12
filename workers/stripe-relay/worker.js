// Stripe webhook relay for luisguinea.com (Cloudflare Worker, free plan, no dependencies).
//
// Why it exists: Google Apps Script web apps cannot read request headers (so they cannot check the Stripe-Signature
// header) and answer every POST to /exec with a 302 redirect, which Stripe counts as a failed delivery. This Worker is
// the public webhook endpoint registered in Stripe. It:
//
//   1. checks the Stripe-Signature header (HMAC-SHA256 of "<t>.<raw body>" with the endpoint's whsec_ secret,
//      constant-time comparison, 5-minute tolerance) and the mode (test or live) of the event;
//   2. forwards only the event id and type to the Apps Script backend, authenticated with its own HMAC
//      (RELAY_SECRET, shared only with Apps Script) over "<timestamp>.<event id>";
//   3. answers 200 only when the backend says it processed (or already had) the event; otherwise 500, so Stripe retries.
//
// The backend never trusts the forwarded data: it downloads the event from the Stripe API by id, and the invoice or
// subscription behind it, before changing anything. The Worker keeps no state and logs no payload or personal data.
//
// Secrets (wrangler secret put): STRIPE_WEBHOOK_SECRET (whsec_...), RELAY_SECRET (64 hex). Variables (wrangler.toml):
// APPS_SCRIPT_URL (https://script.google.com/macros/s/.../exec), STRIPE_MODE ("test" or "live").

const TOLERANCE_SECONDS = 300;
const MAX_BODY_BYTES = 512 * 1024;
const EVENT_ID_RE = /^evt_[A-Za-z0-9]{8,255}$/;
const TYPE_RE = /^[a-z_.]{3,100}$/;
const BACKEND_RE = /^(?:https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec|http:\/\/127\.0\.0\.1:\d+\/exec)$/;

const enc = new TextEncoder();

function hex(buf) {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

async function hmacHex(secret, message) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', key, enc.encode(message)));
}

function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Parses "t=123,v1=abc,v1=def,v0=..." into {t, v1: [...]}; null when malformed. */
export function parseSignatureHeader(header) {
  if (typeof header !== 'string' || header.length > 2048) return null;
  let t = null;
  const v1 = [];
  for (const part of header.split(',')) {
    const at = part.indexOf('=');
    if (at < 1) continue;
    const k = part.slice(0, at).trim();
    const v = part.slice(at + 1).trim();
    if (k === 't' && /^\d{1,12}$/.test(v)) t = Number(v);
    else if (k === 'v1' && /^[0-9a-f]{64}$/.test(v)) v1.push(v);
  }
  return t === null || !v1.length ? null : { t, v1 };
}

/** True when the header carries a valid v1 signature of the raw body made with `secret` within the tolerance. */
export async function verifyStripeSignature(rawBody, header, secret, nowSeconds) {
  const parsed = parseSignatureHeader(header);
  if (!parsed || typeof secret !== 'string' || !secret.startsWith('whsec_')) return false;
  if (Math.abs(nowSeconds - parsed.t) > TOLERANCE_SECONDS) return false;
  const expected = await hmacHex(secret, `${parsed.t}.${rawBody}`);
  return parsed.v1.some((sig) => safeEqual(sig, expected));
}

/** The authenticated message the backend accepts: {op, id, type, ts, sig}. */
export async function relayMessage(event, relaySecret, nowSeconds) {
  return { op: 'stripe_event', id: event.id, type: event.type, ts: nowSeconds,
    sig: await hmacHex(relaySecret, `${nowSeconds}.${event.id}`) };
}

function reply(status, text) {
  return new Response(text, { status, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
}

export async function handle(request, env, now = () => Date.now()) {
  const url = new URL(request.url);
  if (url.pathname !== '/stripe/webhook') return reply(404, 'not found');
  if (request.method !== 'POST') return reply(405, 'method not allowed');
  if (!env.STRIPE_WEBHOOK_SECRET || !/^[0-9a-f]{64}$/.test(env.RELAY_SECRET || '') || !BACKEND_RE.test(env.APPS_SCRIPT_URL || '') ||
      (env.STRIPE_MODE !== 'test' && env.STRIPE_MODE !== 'live')) {
    return reply(500, 'not configured');
  }
  const length = Number(request.headers.get('content-length') || 0);
  if (length > MAX_BODY_BYTES) return reply(413, 'too large');
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return reply(413, 'too large');
  const nowSeconds = Math.floor(now() / 1000);
  if (!(await verifyStripeSignature(raw, request.headers.get('stripe-signature'), env.STRIPE_WEBHOOK_SECRET, nowSeconds))) {
    return reply(400, 'invalid signature');
  }
  let event;
  try { event = JSON.parse(raw); } catch (e) { return reply(400, 'invalid json'); }
  if (!event || event.object !== 'event' || !EVENT_ID_RE.test(event.id || '') || !TYPE_RE.test(event.type || '')) {
    return reply(400, 'invalid event');
  }
  // An event of the other mode is acknowledged (so Stripe stops sending it) but never forwarded.
  if (event.livemode !== (env.STRIPE_MODE === 'live')) return reply(200, 'ignored: other mode');

  const message = await relayMessage(event, env.RELAY_SECRET, nowSeconds);
  let result;
  try {
    const res = await fetch(env.APPS_SCRIPT_URL, {
      method: 'POST',
      // text/plain, like the website: Apps Script reads e.postData.contents whatever the type.
      headers: { 'content-type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(message),
      redirect: 'follow',
      signal: AbortSignal.timeout(25000),
    });
    result = await res.json();
  } catch (e) {
    return reply(502, 'backend unavailable');
  }
  if (result && result.ok === true) return reply(200, 'ok');
  // invalid_event: the backend checked the event with Stripe and refuses it for good (other account or mode); a retry
  // cannot change that, so Stripe is told to stop. Anything else (busy, unavailable...) is retried by Stripe.
  if (result && result.error === 'invalid_event') return reply(200, 'refused');
  return reply(503, 'retry');
}

export default { fetch: (request, env) => handle(request, env) };
