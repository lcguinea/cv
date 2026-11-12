// Billing scenarios: apps-script/Code.gs + Billing.gs with mocked Google services (billing_env.js) and an in-memory
// Stripe (fake_stripe.js). Prints {scenario: "ok" | failure message}. Driven by tests/test_billing.py.
'use strict';
const assert = require('assert');
const crypto = require('crypto');
const { makeEnv } = require('./billing_env');
const { makeStripe } = require('./fake_stripe');

const DAY = 86400000, HOUR = 3600000;
const rid = () => crypto.randomBytes(12).toString('hex');

function setup(o = {}) {
  const env = makeEnv(o);
  const stripe = makeStripe(env, o.stripe);
  env.fetch = stripe.fetch;
  return { env, stripe };
}
function deliver(env, events) { return events.map((e) => env.relay(e.id, e.type)); }
function checkout(env, plan = 'weekly', extra = {}) {
  return env.post(Object.assign({ op: 'checkout', plan, lang: 'es', requestId: rid(), acceptTerms: true, earlyStart: true }, extra));
}
function subscribe(env, stripe, plan = 'weekly', who = {}) {
  const co = checkout(env, plan);
  assert.strictEqual(co.ok, true, JSON.stringify(co));
  const sid = co.url.split('/').pop();
  const paid = stripe.pay(sid, who);
  return Object.assign({ sid }, paid);
}
function linkFor(env, email) {
  const m = env.mails.filter((x) => x.to === email && /#acceso=/.test(x.body)).pop();
  assert(m, 'no access link mailed to ' + email);
  return /#acceso=([0-9a-f]{32}\.[0-9a-f]{64})/.exec(m.body)[1];
}
function login(env, email) {
  const r = env.post({ op: 'stu_login', token: linkFor(env, email) });
  assert.strictEqual(r.ok, true, JSON.stringify(r));
  return r.session;
}
function relogin(env, email = 'ana@example.com') {
  env.post({ op: 'stu_link', email });
  return login(env, email);
}
function adjust(env, ...rows) {
  env.ctx.checkBillingSetup(); // creates every tab, as Luis does once after installing
  rows.forEach((r) => env.sheets.sheet1.ajustes.push(r));
}
function view(env, token) { const v = env.post({ op: 'stu_view', token }); assert.strictEqual(v.ok, true, JSON.stringify(v)); return v; }
function slots(env, token) { const r = env.post({ op: 'stu_slots', token }); assert.strictEqual(r.ok, true, JSON.stringify(r)); return r.slots.map((s) => s.start); }
function book(env, token, starts, requestId = rid()) { return env.post({ op: 'stu_book', token, requestId, starts }); }
/** n slots at least a day apart (one class per day). */
function spaced(list, n, fromIndex = 0) {
  const out = [];
  let last = -Infinity;
  for (let i = fromIndex; i < list.length && out.length < n; i++) {
    const t = Date.parse(list[i]);
    if (t - last >= DAY) { out.push(list[i]); last = t; }
  }
  return out;
}
function grants(env) { return env.table('movimientos').filter((m) => m.tipo === 'grant'); }
function ownerMails(env, re) { return env.mails.filter((m) => m.to === 'owner@example.com' && re.test(m.subject)); }
function newSubscriber(o = {}) {
  const ctx = setup(o);
  const s = subscribe(ctx.env, ctx.stripe, o.plan || 'weekly', o.who || {});
  deliver(ctx.env, s.events);
  const email = (o.who && o.who.email) || 'ana@example.com';
  return Object.assign(ctx, { s, email, token: login(ctx.env, email) });
}

const scenarios = {
  // 1, 3, 19
  weekly_plan_checkout_grants_four_credits_once_payment_is_confirmed() {
    const { env, stripe } = setup();
    const co = checkout(env, 'weekly');
    const sess = stripe.sessions[co.url.split('/').pop()];
    assert.strictEqual(sess.params.mode, 'subscription');
    assert.strictEqual(sess.params['line_items[0][price]'], 'price_weekly');
    assert.strictEqual(sess.params['line_items[0][quantity]'], '1');
    assert.strictEqual(sess.params.allow_promotion_codes, 'false');
    assert(!Object.keys(sess.params).some((k) => /trial|coupon|discount/.test(k)), 'no trials or discounts');
    assert(/cada 4 semanas por 148/.test(sess.params['custom_text[submit][message]']));
    assert(/\?checkout=\{CHECKOUT_SESSION_ID\}$/.test(sess.params.success_url));
    // Back from Stripe before any webhook and before paying: nothing is granted.
    assert.strictEqual(env.post({ op: 'checkout_status', session: sess.id }).state, 'open');
    assert.strictEqual(grants(env).length, 0);
    const paid = stripe.pay(sess.id);
    const st = env.post({ op: 'checkout_status', session: sess.id });
    assert.deepStrictEqual([st.state, st.plan, st.accessEmail], ['ready', 'weekly', 'sent']);
    assert.strictEqual(st.email, undefined, 'no personal data on the return page');
    deliver(env, paid.events);
    assert.strictEqual(grants(env).length, 4);
    const v = view(env, login(env, 'ana@example.com'));
    assert.strictEqual(v.plan.plan, 'weekly');
    assert.strictEqual(v.plan.intervalWeeks, 4);
    assert.strictEqual(v.plan.amount, 14800);
    assert.strictEqual(Date.parse(v.plan.renewsAt) - env.now, 28 * DAY);
    assert.strictEqual(v.counts.available, 4);
    assert.strictEqual(ownerMails(env, /Nueva suscripción/).length, 1);
  },
  // 2
  biweekly_plan_renews_every_eight_weeks() {
    const { env, token } = newSubscriber({ plan: 'biweekly' });
    const v = view(env, token);
    assert.strictEqual(v.plan.plan, 'biweekly');
    assert.strictEqual(v.plan.intervalWeeks, 8);
    assert.strictEqual(Date.parse(v.plan.renewsAt) - env.now, 56 * DAY);
    assert.strictEqual(v.counts.available, 4);
  },
  // 4
  declined_card_creates_no_credits_and_no_student() {
    const { env, stripe } = setup();
    const co = checkout(env);
    const sid = co.url.split('/').pop();
    const d = stripe.pay(sid, { declined: true });
    deliver(env, d.events);
    assert.strictEqual(env.post({ op: 'checkout_status', session: sid }).state, 'open');
    env.hourly();
    assert.strictEqual(env.mails.length, 0, 'no "payment failed" notice for a declined first payment');
    assert.strictEqual(env.table('suscripciones').length, 0);
    assert.strictEqual(grants(env).length, 0);
    assert.strictEqual(env.table('alumnos').length, 0);
  },
  checkout_requires_conditions_and_can_be_switched_off() {
    const { env } = setup();
    assert.strictEqual(checkout(env, 'weekly', { acceptTerms: false }).error, 'terms_required');
    assert.strictEqual(checkout(env, 'weekly', { earlyStart: false }).error, 'early_start_required');
    assert.strictEqual(checkout(env, 'monthly').error, 'invalid_plan');
    assert.strictEqual(checkout(env, 'weekly', { coupon: 'X' }).error, 'invalid_request');
    env.props.BILLING_CHECKOUT_ENABLED = 'false';
    assert.strictEqual(checkout(env).error, 'not_available');
  },
  live_key_with_test_mode_or_missing_prices_refuse_to_run() {
    const { env } = setup({ props: { STRIPE_SECRET_KEY: 'sk_live_REALKEY' } });
    assert.strictEqual(checkout(env).error, 'not_configured');
    const b = setup({ props: { STRIPE_PRICE_WEEKLY: '' } });
    assert.strictEqual(checkout(b.env).error, 'not_configured');
  },
  // 5
  renewal_after_four_weeks_grants_exactly_four_more() {
    const { env, stripe, s, token } = newSubscriber();
    env.now += 28 * DAY;
    const r = stripe.renew(s.sub.id);
    deliver(env, r.events);
    assert.strictEqual(grants(env).length, 8);
    const second = grants(env).filter((g) => JSON.parse(g.datos).factura === r.inv.id).map((g) => JSON.parse(g.datos));
    assert.strictEqual(second.length, 4);
    assert.strictEqual(second[0].fin - second[0].inicio, 28 * DAY);
    assert.strictEqual(view(env, token).counts.available, 8);
  },
  // 6
  renewal_after_eight_weeks_grants_exactly_four_more() {
    const { env, stripe, s } = newSubscriber({ plan: 'biweekly' });
    env.now += 56 * DAY;
    const r = stripe.renew(s.sub.id);
    deliver(env, r.events);
    const second = grants(env).filter((g) => JSON.parse(g.datos).factura === r.inv.id).map((g) => JSON.parse(g.datos));
    assert.strictEqual(second.length, 4);
    assert.strictEqual(second[0].fin - second[0].inicio, 56 * DAY);
  },
  // 7
  duplicate_webhooks_change_nothing() {
    const { env, stripe } = setup();
    const s = subscribe(env, stripe);
    deliver(env, s.events);
    const res = deliver(env, s.events.concat(s.events));
    assert(res.every((r) => r.ok), JSON.stringify(res));
    assert.strictEqual(grants(env).length, 4);
    assert.strictEqual(env.mails.filter((m) => /acceso a tu área/.test(m.subject)).length, 1);
    assert.strictEqual(ownerMails(env, /Nueva suscripción/).length, 1);
    assert.strictEqual(env.table('eventos').length, s.events.length);
  },
  // 8
  out_of_order_events_reach_the_same_state() {
    const a = setup();
    const sa = subscribe(a.env, a.stripe);
    deliver(a.env, sa.events.slice().reverse());
    assert.strictEqual(grants(a.env).length, 4);
    // A stale "updated" event delivered after the cancellation: the backend reads the subscription from Stripe now.
    const old = a.stripe.cancelAtPeriodEnd(sa.sub.id).events[0];
    const ended = a.stripe.endNow(sa.sub.id).events[0];
    deliver(a.env, [ended, old]);
    const row = a.env.table('suscripciones')[0];
    assert.strictEqual(row.estado, 'canceled');
    // invoice.paid of a renewal arriving before the subscription was ever seen
    const b = setup();
    const sb = subscribe(b.env, b.stripe);
    deliver(b.env, [sb.events.find((e) => e.type === 'invoice.paid')]);
    assert.strictEqual(grants(b.env).length, 4);
    assert.strictEqual(b.env.table('alumnos').length, 1);
  },
  // 9, 16
  cancellation_at_period_end_keeps_paid_credits_and_stops_renewals() {
    const { env, stripe, s, token } = newSubscriber();
    deliver(env, stripe.cancelAtPeriodEnd(s.sub.id).events);
    let v = view(env, token);
    assert.strictEqual(v.plan.renewsAt, null);
    assert.strictEqual(Date.parse(v.plan.endsAt), s.sub.current_period_end * 1000);
    assert.strictEqual(v.counts.available, 4);
    assert.strictEqual(ownerMails(env, /Cancelación programada/).length, 1);
    assert.strictEqual(env.mails.filter((m) => m.to === 'ana@example.com' && /Cancelación de tu suscripción/.test(m.subject)).length, 1);
    deliver(env, stripe.cancelAtPeriodEnd(s.sub.id).events); // repeated update: no second notice
    assert.strictEqual(ownerMails(env, /Cancelación programada/).length, 1);
    env.now = s.sub.current_period_end * 1000 + HOUR;
    deliver(env, stripe.endNow(s.sub.id).events);
    v = view(env, token);
    assert.strictEqual(v.plan.status, 'canceled');
    assert.strictEqual(v.credits.length, 4, 'pending credits survive the end of the subscription');
    assert.strictEqual(ownerMails(env, /Suscripción terminada/).length, 1);
  },
  immediate_cancellation_keeps_paid_credits_bookable() {
    const { env, stripe, s, token } = newSubscriber();
    deliver(env, stripe.endNow(s.sub.id).events);
    assert.strictEqual(view(env, token).counts.available, 4);
    const r = book(env, token, spaced(slots(env, token), 1));
    assert.strictEqual(r.ok, true, JSON.stringify(r));
    assert.strictEqual(env.mails.filter((m) => /Tu suscripción de clases ha terminado/.test(m.subject)).length, 1);
  },
  // 10
  student_books_four_classes_at_once_and_reschedules_with_notice() {
    const { env, token } = newSubscriber();
    const list = slots(env, token);
    const four = spaced(list, 4);
    const r = book(env, token, four);
    assert.strictEqual(r.ok, true, JSON.stringify(r));
    assert.strictEqual(r.booked, 4);
    assert.strictEqual(r.counts.available, 0);
    assert.strictEqual(r.counts.reserved, 4);
    assert.strictEqual(env.events().length, 4);
    assert(env.events().every((e) => e.attendees[0].email === 'ana@example.com' && e.location === 'Estudio de Luis, Valencia'));
    assert.strictEqual(ownerMails(env, /Nuevas clases reservadas/).length, 1, 'Luis keeps getting new booking notices');
    const target = r.bookings[0];
    const free = slots(env, token).filter((x) => !four.includes(x) && Math.abs(Date.parse(x) - Date.parse(four[1])) > 2 * HOUR);
    const moved = env.post({ op: 'stu_move', token, booking: target.id, start: free[free.length - 1] });
    assert.strictEqual(moved.ok, true, JSON.stringify(moved));
    assert.strictEqual(moved.bookings.find((b) => b.id === target.id).start, new Date(Date.parse(free[free.length - 1])).toISOString());
    assert.strictEqual(moved.counts.reserved, 4);
    // the event moved too
    assert(env.events().some((e) => e.start === Date.parse(free[free.length - 1])));
  },
  // 11
  changes_inside_twenty_four_hours_are_refused() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    const r = book(env, token, [first]);
    const id = r.bookings[0].id;
    env.now = Date.parse(first) - 23 * HOUR;
    assert.strictEqual(env.post({ op: 'stu_cancel', token, booking: id, confirm: true }).error, 'too_late');
    assert.strictEqual(env.post({ op: 'stu_move', token, booking: id, start: new Date(Date.parse(first) + 3 * DAY).toISOString().replace(/\.\d+Z$/, '.000Z') }).error, 'too_late');
    assert.strictEqual(view(env, token).counts.reserved, 1);
  },
  cancelling_with_notice_gives_the_credit_back() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    const id = book(env, token, [first]).bookings[0].id;
    assert.strictEqual(env.post({ op: 'stu_cancel', token, booking: id }).error, 'confirmation_required');
    const c = env.post({ op: 'stu_cancel', token, booking: id, confirm: true });
    assert.strictEqual(c.counts.available, 4);
    assert.strictEqual(env.events().length, 0);
    assert.strictEqual(env.post({ op: 'stu_cancel', token, booking: id, confirm: true }).counts.available, 4, 'retry is harmless');
    assert(slots(env, token).includes(first), 'the time is offered again');
  },
  // 12
  simultaneous_requests_cannot_share_a_credit_or_a_slot() {
    const { env, stripe, token } = newSubscriber();
    const list = slots(env, token);
    env.lockHeld = true; // another request is inside the lock
    assert.strictEqual(book(env, token, [list[0]]).error, 'busy');
    env.lockHeld = false;
    assert.strictEqual(env.events().length, 0);
    // a second student wants the same time
    const s2 = subscribe(env, stripe, 'weekly', { email: 'bea@example.com', name: 'Bea' });
    deliver(env, s2.events);
    const t2 = login(env, 'bea@example.com');
    assert.strictEqual(book(env, token, [list[0]]).ok, true);
    assert.strictEqual(book(env, t2, [list[0]]).error, 'slot_unavailable');
    // more classes than credits: nothing is booked
    const r = book(env, token, spaced(list, 4, 5));
    assert.strictEqual(r.error, 'no_credits');
    assert.strictEqual(view(env, token).counts.reserved, 1);
    // two classes that overlap in one request
    assert.strictEqual(book(env, t2, [list[2], new Date(Date.parse(list[2]) + 30 * 60000).toISOString()]).error, 'overlap');
    assert.strictEqual(book(env, t2, list.slice(0, 5)).error, 'invalid_request');
  },
  // 13
  one_or_two_unused_credits_carry_over_for_thirty_days() {
    for (const used of [3, 2]) {
      const { env, s, token } = newSubscriber();
      book(env, token, spaced(slots(env, token), used));
      env.now = s.sub.current_period_end * 1000 + HOUR;
      env.hourly();
      const v = view(env, token);
      const carried = v.credits.filter((c) => c.carried);
      assert.strictEqual(carried.length, 4 - used);
      assert(carried.every((c) => Date.parse(c.expiresAt) === s.sub.current_period_end * 1000 + 30 * DAY));
    }
  },
  // 14
  at_most_two_credits_carry_over() {
    const { env, s, token } = newSubscriber();
    book(env, token, spaced(slots(env, token), 1));
    env.now = s.sub.current_period_end * 1000 + HOUR;
    env.hourly();
    const rolls = env.table('movimientos').filter((m) => m.tipo === 'rollover').map((m) => JSON.parse(m.datos).traslado);
    assert.deepStrictEqual(rolls.sort(), [false, true, true]);
    const v = view(env, token);
    assert.strictEqual(v.credits.length, 3, 'nothing is deleted');
    // Policy not approved yet (default): the third credit is flagged but still usable.
    assert.strictEqual(v.credits.filter((c) => c.status === 'past_deadline').length, 1);
    assert.strictEqual(v.counts.available, 3);
    // Once Luis approves the policy, it is not self-bookable any more (kept for review).
    env.props.CREDIT_POLICY_ENFORCED = 'true';
    const w = view(env, token);
    assert.strictEqual(w.counts.available, 2);
    assert.strictEqual(w.credits.filter((c) => c.status === 'expired_review').length, 1);
  },
  // 15
  recovery_deadline_with_policy_on_blocks_booking_and_luis_can_extend() {
    let { env, s, token } = newSubscriber({ props: { CREDIT_POLICY_ENFORCED: 'true' } });
    book(env, token, spaced(slots(env, token), 2));
    const end = s.sub.current_period_end * 1000;
    env.now = end + HOUR;
    env.hourly();
    // a class after the carried credits' deadline cannot be paid with them
    const late = slots(env, token).filter((x) => Date.parse(x) > end + 30 * DAY);
    assert.strictEqual(book(env, token, [late[0]]).error, 'no_credits');
    env.now = end + 30 * DAY + HOUR;
    token = relogin(env);
    const v = view(env, token);
    assert.strictEqual(v.counts.available, 0);
    assert.strictEqual(v.credits.filter((c) => c.status === 'expired_review').length, 2);
    // Luis extends one in the "ajustes" tab
    const credit = env.table('movimientos').find((m) => m.tipo === 'rollover' && JSON.parse(m.datos).traslado).credito;
    adjust(env, ['', 'ampliar', '', credit, '2027-03-31', 'enfermedad', '', '']);
    env.hourly();
    assert.strictEqual(env.table('ajustes')[0].estado, 'hecho');
    assert.strictEqual(view(env, token).counts.available, 1);
  },
  deadline_warnings_only_once_the_policy_is_on() {
    const { env, s, token } = newSubscriber();
    env.now = s.sub.current_period_end * 1000 - 3 * DAY;
    env.hourly();
    assert.strictEqual(env.mails.filter((m) => /pendientes de reservar/.test(m.subject)).length, 0);
    env.props.CREDIT_POLICY_ENFORCED = 'true';
    env.hourly(); env.hourly();
    assert.strictEqual(env.mails.filter((m) => /pendientes de reservar/.test(m.subject)).length, 4, 'one per credit, once');
    void token;
  },
  // 17
  temporary_backend_failure_is_retried_without_side_effects() {
    const { env, stripe } = setup();
    const s = subscribe(env, stripe);
    stripe.down = true;
    const r = env.relay(s.events[1].id, s.events[1].type);
    assert.strictEqual(r.ok, false);
    assert.strictEqual(grants(env).length, 0);
    assert.strictEqual(env.table('eventos').length, 0, 'not marked as processed: Stripe will retry');
    stripe.down = false;
    assert.strictEqual(env.relay(s.events[1].id, s.events[1].type).ok, true);
    assert.strictEqual(grants(env).length, 4);
  },
  calendar_failure_half_way_books_nothing_and_takes_no_credit() {
    const { env, token } = newSubscriber();
    const four = spaced(slots(env, token), 3);
    const realInsert = env.ctx.Calendar.Events.insert;
    let n = 0;
    env.ctx.Calendar.Events.insert = (...a) => { if (++n === 3) throw new Error('Backend Error'); return realInsert(...a); };
    const r = book(env, token, four);
    assert.strictEqual(r.error, 'unavailable');
    env.ctx.Calendar.Events.insert = realInsert;
    assert.strictEqual(env.events().length, 0, 'the two created events were removed');
    assert.strictEqual(view(env, token).counts.available, 4);
  },
  // 18
  retried_requests_return_the_same_result() {
    const { env, stripe, token } = newSubscriber();
    const requestId = rid();
    const two = spaced(slots(env, token), 2);
    const a = book(env, token, two, requestId);
    const b = book(env, token, two, requestId);
    assert.strictEqual(a.ok && b.ok, true);
    assert.strictEqual(b.counts.reserved, 2);
    assert.strictEqual(env.events().length, 2);
    assert.strictEqual(book(env, token, [two[0]], requestId).error, 'invalid_request', 'same id, other content');
    const req = { op: 'checkout', plan: 'weekly', lang: 'es', requestId: rid(), acceptTerms: true, earlyStart: true };
    assert.strictEqual(env.post(req).url, env.post(req).url);
    void stripe;
  },
  // 20
  nobody_reaches_another_students_data() {
    const { env, stripe, token } = newSubscriber();
    const id = book(env, token, spaced(slots(env, token), 1)).bookings[0].id;
    const s2 = subscribe(env, stripe, 'weekly', { email: 'bea@example.com', name: 'Bea' });
    deliver(env, s2.events);
    const t2 = login(env, 'bea@example.com');
    assert.strictEqual(env.post({ op: 'stu_cancel', token: t2, booking: id, confirm: true }).error, 'not_found');
    assert.strictEqual(env.post({ op: 'stu_move', token: t2, booking: id, start: new Date(env.now + 5 * DAY).toISOString() }).error, 'not_found');
    const v2 = view(env, t2);
    assert.strictEqual(v2.bookings.length, 0);
    assert(!JSON.stringify(v2).includes('ana@example.com'));
    assert(!/cus_|sub_|in_|cs_/.test(JSON.stringify(v2)), 'no Stripe ids in the student view');
    // Knowing an email is not enough: the link goes to that mailbox, and the answer is the same for anyone.
    const before = env.mails.length;
    const a = env.post({ op: 'stu_link', email: 'ana@example.com' });
    const b = env.post({ op: 'stu_link', email: 'nadie@example.com' });
    assert.deepStrictEqual(a, b);
    assert.strictEqual(env.mails.length, before + 1);
    assert.strictEqual(env.mails[env.mails.length - 1].to, 'ana@example.com');
    // links work once; sessions can be closed; forged tokens fail
    const link = linkFor(env, 'ana@example.com');
    assert.strictEqual(env.post({ op: 'stu_login', token: link }).ok, true);
    assert.strictEqual(env.post({ op: 'stu_login', token: link }).error, 'invalid_token');
    assert.strictEqual(env.post({ op: 'stu_view', token: link }).error, 'invalid_token', 'a link is not a session');
    assert.strictEqual(env.post({ op: 'stu_view', token: token.slice(0, -1) + (token.endsWith('0') ? '1' : '0') }).error, 'invalid_token');
    env.post({ op: 'stu_logout', token });
    assert.strictEqual(env.post({ op: 'stu_view', token }).error, 'invalid_token');
    // a Stripe id is no credential
    assert.strictEqual(env.post({ op: 'stu_view', token: 'cus_123' }).error, 'invalid_token');
  },
  sessions_and_links_expire() {
    const { env, token } = newSubscriber();
    env.post({ op: 'stu_link', email: 'ana@example.com' });
    const link = linkFor(env, 'ana@example.com');
    env.now += 31 * DAY;
    assert.strictEqual(env.post({ op: 'stu_view', token }).error, 'invalid_token');
    assert.strictEqual(env.post({ op: 'stu_login', token: link }).error, 'invalid_token');
  },
  webhook_messages_must_come_from_the_relay_and_from_stripe() {
    const { env, stripe } = setup();
    const s = subscribe(env, stripe);
    const e = s.events[1];
    assert.strictEqual(env.relay(e.id, e.type, null, 'cd'.repeat(32)).error, 'invalid_request', 'wrong relay secret');
    assert.strictEqual(env.relay(e.id, e.type, Math.floor(env.now / 1000) - 600).error, 'invalid_request', 'replayed late');
    assert.strictEqual(env.relay('evt_doesnotexist123', 'invoice.paid').error, 'invalid_event', 'unknown to Stripe');
    assert.strictEqual(grants(env).length, 0);
    const live = setup({ stripe: { livemode: true } });
    const sl = subscribe(live.env, live.stripe);
    assert.strictEqual(live.env.relay(sl.events[1].id, 'invoice.paid').error, 'invalid_event', 'live event on the test backend');
    assert.strictEqual(grants(live.env).length, 0);
  },
  failed_renewal_grants_nothing_until_paid() {
    const { env, stripe, s, token } = newSubscriber();
    env.now += 28 * DAY;
    const r = stripe.renew(s.sub.id, { fail: true });
    deliver(env, r.events);
    deliver(env, r.events);
    assert.strictEqual(grants(env).length, 4);
    assert.strictEqual(ownerMails(env, /Pago fallido/).length, 1);
    assert.strictEqual(view(env, token).plan.status, 'past_due');
    env.hourly();
    assert.strictEqual(grants(env).length, 4);
    env.now += 2 * DAY;
    deliver(env, stripe.payLater(r.inv.id).events);
    assert.strictEqual(grants(env).length, 8);
    assert.strictEqual(view(env, relogin(env)).plan.status, 'active');
    void token;
  },
  lost_webhooks_are_recovered_by_the_hourly_reconciliation() {
    const { env, stripe } = setup();
    const s = subscribe(env, stripe); // no event delivered at all
    env.hourly();
    assert.strictEqual(grants(env).length, 4);
    env.now += 28 * DAY;
    stripe.renew(s.sub.id);
    env.hourly(); env.hourly();
    assert.strictEqual(grants(env).length, 8);
    assert.strictEqual(env.mails.filter((m) => /acceso a tu área/.test(m.subject)).length, 1);
  },
  refunds_and_disputes_open_an_incident_and_change_no_credit() {
    const { env, stripe, s } = newSubscriber();
    deliver(env, stripe.refund(s.inv.id).events);
    assert.strictEqual(env.table('incidencias').length, 1);
    assert.strictEqual(ownerMails(env, /Incidencia/).length, 1);
    assert.strictEqual(env.table('movimientos').filter((m) => m.tipo === 'void').length, 0);
    // Luis decides to void two credits in the "ajustes" tab
    const credits = grants(env).map((g) => g.credito);
    adjust(env, ['', 'anular', '', credits[0], '', 'reembolso', '', ''], ['', 'anular', '', credits[1], '', 'reembolso', '', '']);
    env.hourly();
    assert.deepStrictEqual(env.table('ajustes').map((a) => a.estado), ['hecho', 'hecho']);
    assert.strictEqual(view(env, relogin(env)).counts.available, 2);
  },
  other_products_of_the_account_are_ignored() {
    const { env, stripe } = setup();
    deliver(env, stripe.otherProduct().events);
    env.hourly();
    assert.strictEqual(env.table('alumnos').length, 0);
    assert.strictEqual(env.table('suscripciones').length, 0);
  },
  teacher_cancellation_in_calendar_restores_the_class_without_deadline() {
    const { env, token } = newSubscriber({ props: { CREDIT_POLICY_ENFORCED: 'true' } });
    const r = book(env, token, spaced(slots(env, token), 1));
    env.deleteEvent(env.events()[0].id);
    env.hourly();
    const v = view(env, token);
    assert.strictEqual(v.counts.available, 4);
    assert.strictEqual(v.credits.filter((c) => c.protected && c.expiresAt === null).length, 1);
    assert.strictEqual(v.bookings.find((b) => b.id === r.bookings[0].id).reason, 'profesor');
    assert.strictEqual(env.mails.filter((m) => /conservas la clase/.test(m.subject)).length, 1);
    env.hourly();
    assert.strictEqual(env.mails.filter((m) => /conservas la clase/.test(m.subject)).length, 1);
  },
  classes_are_consumed_after_the_end_plus_grace_and_follow_calendar_moves() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    book(env, token, [first]);
    const ev = env.events()[0];
    env.moveEvent(ev.id, ev.start + 2 * HOUR); // Luis drags it in Calendar
    env.hourly();
    assert.strictEqual(Date.parse(view(env, token).bookings[0].start), Date.parse(first) + 2 * HOUR);
    env.now = Date.parse(first) + 3 * HOUR + 47 * HOUR;
    env.hourly();
    assert.strictEqual(view(env, token).counts.done, 0);
    env.now += 2 * HOUR;
    env.hourly();
    const v = view(env, token);
    assert.strictEqual(v.counts.done, 1);
    assert.strictEqual(v.bookings[0].status, 'realizada');
  },
  reminder_is_sent_once_the_day_before() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    book(env, token, [first]);
    env.now = Date.parse(first) - 20 * HOUR;
    env.hourly(); env.hourly();
    assert.strictEqual(env.mails.filter((m) => /Recordatorio/.test(m.subject)).length, 1);
  },
  ledger_is_rebuilt_from_movements_only() {
    const { env, token } = newSubscriber();
    book(env, token, spaced(slots(env, token), 2));
    const rows = env.table('movimientos');
    assert(rows.every((m) => m.id && m.tipo));
    assert.strictEqual(new Set(rows.map((m) => m.id)).size, rows.length, 'movement ids are unique');
    const moves = rows.map((m) => ({ id: m.id, ts: m.ts, tipo: m.tipo, alumno: m.alumno, credito: m.credito, reserva: m.reserva, datos: JSON.parse(m.datos) }));
    const led = env.ctx.deriveLedger_(moves, { carryMs: 30 * DAY });
    assert.strictEqual(Object.values(led.credits).filter((c) => c.estado === 'reservado').length, 2);
    // Panel tab is regenerated and keeps no personal data outside the private Sheet
    assert(env.sheets.sheet1.panel.length > 3);
  },
  general_agenda_still_works_and_sees_class_bookings() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    const before = env.get({ action: 'slots', duration: '60' });
    assert.strictEqual(before.ok, true);
    assert(before.slots.some((s) => s.start === first));
    book(env, token, [first]);
    const after = env.get({ action: 'slots', duration: '60' });
    assert(!after.slots.some((s) => s.start === first), 'a class blocks the general agenda');
    const other = after.slots[0];
    const r = env.post({ op: 'book', requestId: rid(), name: 'Visitante', email: 'v@example.com', start: other.start, duration: 60, modality: 'virtual' });
    assert.strictEqual(r.ok, true, JSON.stringify(r));
    assert(!slots(env, token).includes(other.start), 'an agenda meeting blocks classes');
  },
};

// ---------- mission 05: commercial rules ----------
Object.assign(scenarios, {
  plan_change_weekly_to_biweekly_happens_at_renewal_without_extra_charges() {
    const { env, stripe, s, token } = newSubscriber();
    assert.strictEqual(env.post({ op: 'stu_plan', token, plan: 'biweekly' }).error, 'confirmation_required');
    const v = env.post({ op: 'stu_plan', token, plan: 'biweekly', confirm: true });
    assert.strictEqual(v.ok, true, JSON.stringify(v));
    assert.strictEqual(v.plan.plan, 'weekly');
    assert.strictEqual(v.plan.pendingPlan, 'biweekly');
    assert.strictEqual(Date.parse(v.plan.changeAt), s.sub.current_period_end * 1000);
    assert.strictEqual(Object.keys(stripe.invoices).length, 1, 'nothing is charged now');
    assert(!stripe.unsafeSchedule, 'every phase has proration_behavior none');
    assert.strictEqual(ownerMails(env, /Cambio de plan programado/).length, 1);
    env.now = s.sub.current_period_end * 1000 + HOUR;
    const r = stripe.renew(s.sub.id);
    assert.strictEqual(r.inv.billing_reason, 'subscription_update');
    deliver(env, r.events);
    assert.strictEqual(grants(env).length, 8, 'the plan-change invoice grants the new cycle');
    const second = grants(env).map((g) => JSON.parse(g.datos)).filter((d) => d.factura === r.inv.id);
    assert.strictEqual(second[0].fin - second[0].inicio, 56 * DAY);
    assert.strictEqual(second[0].plan, 'biweekly');
    const w = view(env, relogin(env));
    assert.strictEqual(w.plan.plan, 'biweekly');
    assert.strictEqual(w.plan.intervalWeeks, 8);
    assert.strictEqual(env.table('incidencias').length, 0);
    void token;
  },
  plan_change_biweekly_to_weekly_and_undo() {
    const { env, stripe, s, token } = newSubscriber({ plan: 'biweekly' });
    env.post({ op: 'stu_plan', token, plan: 'weekly', confirm: true });
    const u = env.post({ op: 'stu_plan_undo', token });
    assert.strictEqual(u.ok, true, JSON.stringify(u));
    assert.strictEqual(u.plan.pendingPlan, null);
    env.now = s.sub.current_period_end * 1000 + HOUR;
    const r = stripe.renew(s.sub.id);
    assert.strictEqual(r.inv.billing_reason, 'subscription_cycle', 'undone: plain renewal of the same plan');
    deliver(env, r.events);
    assert.strictEqual(grants(env).length, 8);
    // and the other direction for real
    const b = newSubscriber({ plan: 'biweekly', who: { email: 'bea@example.com', name: 'Bea' } });
    b.env.post({ op: 'stu_plan', token: b.token, plan: 'weekly', confirm: true });
    b.env.now = b.s.sub.current_period_end * 1000 + HOUR;
    const r2 = b.stripe.renew(b.s.sub.id);
    deliver(b.env, r2.events);
    const d = grants(b.env).map((g) => JSON.parse(g.datos)).filter((x) => x.factura === r2.inv.id)[0];
    assert.strictEqual(d.fin - d.inicio, 28 * DAY);
  },
  plan_change_is_refused_when_cancelling_or_inactive() {
    const { env, stripe, s, token } = newSubscriber();
    assert.strictEqual(env.post({ op: 'stu_plan', token, plan: 'monthly', confirm: true }).error, 'invalid_plan');
    deliver(env, stripe.cancelAtPeriodEnd(s.sub.id).events);
    assert.strictEqual(env.post({ op: 'stu_plan', token, plan: 'biweekly', confirm: true }).error, 'not_active');
    assert.strictEqual(view(env, token).plan.canChangePlan, false);
  },
  partial_and_total_refunds_are_recorded_and_change_no_credit() {
    const { env, stripe, s, token } = newSubscriber();
    deliver(env, stripe.refund(s.inv.id, 3700).events);
    let refunds = env.table('movimientos').filter((m) => m.tipo === 'refund').map((m) => JSON.parse(m.datos));
    assert.deepStrictEqual(refunds.map((r) => [r.reembolsado, r.total]), [[3700, false]]);
    assert.strictEqual(env.table('incidencias')[0].tipo, 'reembolso_parcial');
    assert(/Clases de esa factura sin usar: 4/.test(env.table('incidencias')[0].detalle));
    const again = stripe.refund(s.inv.id, 11100).events;
    deliver(env, again); deliver(env, again);
    refunds = env.table('movimientos').filter((m) => m.tipo === 'refund').map((m) => JSON.parse(m.datos));
    assert.deepStrictEqual(refunds.map((r) => [r.reembolsado, r.total]), [[3700, false], [14800, true]]);
    assert.strictEqual(view(env, token).counts.available, 4, 'no automatic denial or removal');
    assert(env.sheets.sheet1.panel.some((row) => row[0] === 'REEMBOLSOS'));
  },
  justified_absence_gives_the_class_back() {
    const { env, token } = newSubscriber();
    const [first] = spaced(slots(env, token), 1);
    book(env, token, [first]);
    env.now = Date.parse(first) + 60 * HOUR;
    env.hourly();
    let v = view(env, relogin(env));
    assert.strictEqual(v.counts.done, 1);
    const credit = env.table('movimientos').find((m) => m.tipo === 'consume').credito;
    adjust(env, ['', 'justificar', '', credit, '', 'enfermedad con aviso tardío', '', '']);
    env.hourly();
    assert.strictEqual(env.table('ajustes')[0].estado, 'hecho');
    v = view(env, relogin(env));
    assert.strictEqual(v.counts.done, 0);
    assert.strictEqual(v.counts.available, 4);
    assert.strictEqual(v.bookings[0].reason, 'justificada');
    assert(v.credits.some((c) => c.protected && c.expiresAt === null));
    void token;
  },
  no_available_times_is_reported_and_luis_can_extend_or_grant() {
    const { env, token } = newSubscriber({ availability: [] });
    assert.deepStrictEqual(slots(env, token), []);
    assert.strictEqual(book(env, token, [new Date(env.now + 3 * DAY).toISOString().replace(/T.*/, 'T09:00:00.000Z')]).error, 'slot_unavailable');
    adjust(env, ['', 'conceder', 'ana@example.com', '', '1', 'sin horarios este mes', '', '']);
    env.hourly();
    assert.strictEqual(view(env, relogin(env)).counts.available, 5);
    void token;
  },
  student_keeps_access_and_classes_after_the_subscription_ends() {
    const { env, stripe, s } = newSubscriber();
    deliver(env, stripe.cancelAtPeriodEnd(s.sub.id).events);
    env.now = s.sub.current_period_end * 1000 + 5 * DAY;
    deliver(env, stripe.endNow(s.sub.id).events);
    const t = relogin(env);
    const v = view(env, t);
    assert.strictEqual(v.plan.status, 'canceled');
    assert.strictEqual(v.credits.length, 4);
    assert.strictEqual(book(env, t, spaced(slots(env, t), 1)).ok, true, 'paid classes can still be booked');
  },
  reschedule_limit_never_blocks_a_class_luis_cancelled() {
    const { env, token } = newSubscriber();
    const list = slots(env, token);
    const id = book(env, token, [list[0]]).bookings[0].id;
    const free = spaced(list, 5, 10);
    for (let i = 0; i < 3; i++) assert.strictEqual(env.post({ op: 'stu_move', token, booking: id, start: free[i] }).ok, true);
    assert.strictEqual(env.post({ op: 'stu_move', token, booking: id, start: free[3] }).error, 'reschedule_limit');
    env.deleteEvent(env.events()[0].id); // Luis cancels it
    env.hourly();
    const t = relogin(env);
    const nid = book(env, t, [free[3]]).bookings.find((b) => b.status === 'reservada').id;
    assert.strictEqual(env.post({ op: 'stu_move', token: t, booking: nid, start: free[4] }).ok, true, 'a new booking, a new allowance');
  },
  make_up_classes_never_displace_other_bookings() {
    const { env, stripe, s, token } = newSubscriber();
    const b2 = subscribe(env, stripe, 'weekly', { email: 'bea@example.com', name: 'Bea' });
    deliver(env, b2.events);
    const t2 = login(env, 'bea@example.com');
    book(env, token, spaced(slots(env, token), 2));
    env.now = s.sub.current_period_end * 1000 + HOUR;
    env.hourly(); // Ana carries 2 classes over
    const t = relogin(env);
    const target = spaced(slots(env, t2), 1)[0];
    assert.strictEqual(book(env, t2, [target]).ok, true);
    assert.strictEqual(book(env, t, [target]).error, 'slot_unavailable', 'a make-up class takes only free time');
    assert.strictEqual(env.events().filter((e) => e.start === Date.parse(target)).length, 1);
    void stripe;
  },
  anonymising_a_student_keeps_the_ledger() {
    const { env, token } = newSubscriber();
    const before = env.table('movimientos').length;
    adjust(env, ['', 'anonimizar', 'ana@example.com', '', '', 'solicitud de supresión', '', '']);
    env.hourly();
    assert(env.table('alumnos').every((a) => a.email === '[suprimido]' && a.nombre === '[suprimido]'));
    assert.strictEqual(env.post({ op: 'stu_view', token }).error, 'invalid_token');
    assert.strictEqual(env.table('movimientos').length, before);
    assert(!JSON.stringify(env.sheets.sheet1.ajustes).includes('ana@example.com'));
  },
  students_get_our_own_renewal_and_failed_payment_notices() {
    const { env, stripe, s } = newSubscriber();
    env.now = s.sub.current_period_end * 1000 - 2 * DAY;
    env.hourly(); env.hourly();
    const renew = env.mails.filter((m) => m.to === 'ana@example.com' && /se renueva pronto/.test(m.subject));
    assert.strictEqual(renew.length, 1);
    assert(/148 €/.test(renew[0].body) && /cancelarlo antes/.test(renew[0].body));
    env.now = s.sub.current_period_end * 1000 + HOUR;
    deliver(env, stripe.renew(s.sub.id, { fail: true }).events);
    const failed = env.mails.filter((m) => m.to === 'ana@example.com' && /No hemos podido cobrar/.test(m.subject));
    assert.strictEqual(failed.length, 1);
    assert(!/santochilaquil/i.test(failed[0].body));
  },
  checkout_stays_closed_until_the_terms_are_approved() {
    const { env } = setup({ props: { TERMS_APPROVED_VERSION: '' } });
    assert.strictEqual(checkout(env).error, 'not_available');
    env.props.TERMS_APPROVED_VERSION = 'otra-version';
    assert.strictEqual(checkout(env).error, 'not_available');
  },
});

const results = {};
for (const [name, fn] of Object.entries(scenarios)) {
  try { fn(); results[name] = 'ok'; } catch (e) { results[name] = String(e && e.stack || e).split('\n').slice(0, 4).join(' | '); }
}
process.stdout.write(JSON.stringify(results, null, 1));
