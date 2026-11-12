// In-memory Stripe for the billing scenarios: the endpoints apps-script/Billing.gs calls (API version 2024-06-20
// shapes) plus helpers that play what Stripe would do on its side (complete a Checkout, renew, fail, cancel, refund).
// Events are created like Stripe's (one per change, with an id the backend downloads again from GET /events/:id).
'use strict';

const WEEK = 7 * 86400;

function makeStripe(env, opts = {}) {
  const s = { customers: {}, subs: {}, invoices: {}, events: {}, sessions: {}, schedules: {}, charges: {}, eventOrder: [], seq: 0, idem: {}, livemode: !!opts.livemode,
    prices: {
      price_weekly: { id: 'price_weekly', object: 'price', active: true, unit_amount: 14800, currency: 'eur', type: 'recurring', livemode: false, recurring: { interval: 'week', interval_count: 4 } },
      price_biweekly: { id: 'price_biweekly', object: 'price', active: true, unit_amount: 14800, currency: 'eur', type: 'recurring', livemode: false, recurring: { interval: 'week', interval_count: 8 } },
      price_other: { id: 'price_other', object: 'price', active: true, unit_amount: 999, currency: 'eur', type: 'recurring', livemode: false, recurring: { interval: 'month', interval_count: 1 } },
    } };
  const id = (p) => `${p}_${String(++s.seq).padStart(6, '0')}fake${Math.random().toString(36).slice(2, 8)}`;
  const nowS = () => Math.floor(env.now / 1000);
  const copy = (o) => JSON.parse(JSON.stringify(o));
  function emit(type, obj) {
    const ev = { id: id('evt'), object: 'event', type, livemode: s.livemode, created: nowS(), data: { object: copy(obj) } };
    s.events[ev.id] = ev;
    s.eventOrder.push(ev.id);
    return ev;
  }
  function decode(body) {
    const out = {};
    (body || '').split('&').filter(Boolean).forEach((kv) => {
      const [k, v] = kv.split('=').map(decodeURIComponent);
      out[k] = v;
    });
    return out;
  }
  function invoiceFor(sub, reason, status, start) {
    const price = s.prices[sub.items.data[0].price.id];
    const end = start + price.recurring.interval_count * WEEK;
    const inv = { id: id('in'), object: 'invoice', livemode: s.livemode, customer: sub.customer, subscription: sub.id, billing_reason: reason,
      status, amount_paid: status === 'paid' ? price.unit_amount : 0, amount_due: price.unit_amount, currency: 'eur', attempt_count: status === 'paid' ? 1 : 1,
      period_start: start, period_end: start, status_transitions: { paid_at: status === 'paid' ? nowS() : null },
      lines: { data: [{ id: id('il'), price: { id: price.id }, quantity: 1, proration: false, period: { start, end } }] } };
    s.invoices[inv.id] = inv;
    if (status === 'paid') chargeFor(inv);
    return inv;
  }
  function chargeFor(inv) {
    const ch = { id: id('ch'), object: 'charge', livemode: s.livemode, invoice: inv.id, customer: inv.customer, amount: inv.amount_paid, amount_refunded: 0, currency: 'eur' };
    s.charges[ch.id] = ch;
    inv.charge = ch.id;
    return ch;
  }
  const api = {
    get: (path, q) => {
      let m;
      if ((m = /^\/events\/(.+)$/.exec(path))) return s.events[m[1]];
      if ((m = /^\/invoices\/(.+)$/.exec(path))) return s.invoices[m[1]];
      if ((m = /^\/subscriptions\/(.+)$/.exec(path))) return s.subs[m[1]];
      if ((m = /^\/customers\/(.+)$/.exec(path))) return s.customers[m[1]];
      if ((m = /^\/checkout\/sessions\/(.+)$/.exec(path))) return s.sessions[m[1]];
      if ((m = /^\/prices\/(.+)$/.exec(path))) return s.prices[m[1]];
      if ((m = /^\/charges\/(.+)$/.exec(path))) return s.charges[m[1]];
      if ((m = /^\/subscription_schedules\/(.+)$/.exec(path))) return s.schedules[m[1]];
      if (path === '/subscriptions') return { object: 'list', data: Object.values(s.subs) };
      if (path === '/invoices') return { object: 'list', data: Object.values(s.invoices).filter((i) => i.subscription === q.subscription && (!q.status || i.status === q.status)) };
      return undefined;
    },
    post: (path, p, idem) => {
      if (idem && s.idem[idem]) return s.idem[idem];
      let out;
      if (path === '/checkout/sessions') {
        const sid = `cs_test_${id('x').replace(/_/g, '')}`;
        out = { id: sid, object: 'checkout.session', mode: p.mode, status: 'open', payment_status: 'unpaid', url: `https://checkout.stripe.com/c/pay/${sid}`,
          metadata: { plan: p['metadata[plan]'], lang: p['metadata[lang]'] }, price: p['line_items[0][price]'], params: p, subscription: null, invoice: null, customer: null };
        s.sessions[sid] = out;
      } else if (path === '/subscription_schedules') {
        const sub = s.subs[p.from_subscription];
        if (sub.schedule) return { error: { message: 'already has a schedule' } };
        out = { id: id('sub_sched'), object: 'subscription_schedule', status: 'active', subscription: sub.id, end_behavior: 'release',
          phases: [{ start_date: sub.current_period_start, end_date: sub.current_period_end, items: [{ price: sub.items.data[0].price.id, quantity: 1 }] }] };
        s.schedules[out.id] = out;
        sub.schedule = out.id;
      } else if (/^\/subscription_schedules\/[^/]+\/release$/.test(path)) {
        out = s.schedules[path.split('/')[2]];
        out.status = 'released';
        s.subs[out.subscription].schedule = null;
      } else if (/^\/subscription_schedules\/[^/]+$/.test(path)) {
        out = s.schedules[path.split('/')[2]];
        const phases = [];
        Object.keys(p).forEach((k) => {
          const m = /^phases\[(\d+)\]\[(.+)\]$/.exec(k);
          if (!m) return;
          const ph = (phases[+m[1]] = phases[+m[1]] || { items: [{}] });
          if (m[2] === 'items][0][price') ph.items[0].price = p[k];
          else if (m[2] === 'start_date' || m[2] === 'end_date' || m[2] === 'iterations') ph[m[2]] = Number(p[k]);
          else if (m[2] === 'proration_behavior') ph.proration_behavior = p[k];
          else if (m[2] === 'metadata][plan') ph.plan = p[k];
        });
        if (p.proration_behavior !== 'none' || phases.some((ph) => ph.proration_behavior !== 'none')) s.unsafeSchedule = true;
        if (phases[1] && !phases[1].start_date) phases[1].start_date = phases[0].end_date;
        out.phases = phases;
      } else if (path === '/billing_portal/sessions') {
        out = { id: id('bps'), object: 'billing_portal.session', customer: p.customer, url: `https://billing.stripe.com/p/session/test_${s.seq}` };
      }
      if (idem) s.idem[idem] = out;
      return out;
    },
  };
  // UrlFetchApp-compatible transport.
  s.fetch = (url, o) => {
    if (s.down) throw new Error('timeout');
    if (!/^https:\/\/api\.stripe\.com\/v1\//.test(url) || !/^Bearer rk_test_/.test(o.headers.Authorization)) return { code: 401, body: { error: { message: 'bad auth' } } };
    const [p, query] = url.replace('https://api.stripe.com/v1', '').split('?');
    const body = o.method === 'post' ? api.post(p, decode(o.payload), o.headers['Idempotency-Key']) : api.get(p, decode(query));
    return body ? { code: 200, body: copy(body) } : { code: 404, body: { error: { code: 'resource_missing' } } };
  };

  // ---- what happens on Stripe's side ----
  s.pay = (sessionId, { email = 'ana@example.com', name = 'Ana Pérez', declined = false } = {}) => {
    const cs = s.sessions[sessionId];
    if (declined) {
      // Like the real API: the customer and an "incomplete" subscription with an open first invoice exist, the
      // session stays open, and Stripe emits subscription.created and invoice.payment_failed.
      const c = { id: id('cus'), object: 'customer', email, name }; s.customers[c.id] = c;
      const p0 = s.prices[cs.price];
      const sub0 = { id: id('sub'), object: 'subscription', livemode: s.livemode, customer: c.id, status: 'incomplete', cancel_at_period_end: false,
        cancel_at: null, ended_at: null, current_period_start: nowS(), current_period_end: nowS() + p0.recurring.interval_count * WEEK,
        metadata: { plan: cs.metadata.plan, lang: cs.metadata.lang }, items: { data: [{ price: { id: p0.id }, quantity: 1 }] } };
      s.subs[sub0.id] = sub0;
      const inv0 = invoiceFor(sub0, 'subscription_create', 'open', nowS());
      return { sub: sub0, inv: inv0, events: [emit('customer.subscription.created', sub0), emit('invoice.payment_failed', inv0)] };
    }
    let cus = Object.values(s.customers).find((c) => c.email === email && opts.reuseCustomers);
    if (!cus) { cus = { id: id('cus'), object: 'customer', email, name }; s.customers[cus.id] = cus; }
    const start = nowS();
    const price = s.prices[cs.price];
    const sub = { id: id('sub'), object: 'subscription', livemode: s.livemode, customer: cus.id, status: 'active', cancel_at_period_end: false, cancel_at: null,
      ended_at: null, current_period_start: start, current_period_end: start + price.recurring.interval_count * WEEK,
      metadata: { plan: cs.metadata.plan, lang: cs.metadata.lang }, items: { data: [{ price: { id: price.id }, quantity: 1 }] } };
    s.subs[sub.id] = sub;
    const inv = invoiceFor(sub, 'subscription_create', 'paid', start);
    Object.assign(cs, { status: 'complete', payment_status: 'paid', subscription: sub.id, invoice: inv.id, customer: cus.id });
    const events = [emit('customer.subscription.created', sub), emit('invoice.paid', inv), emit('invoice.payment_succeeded', inv), emit('checkout.session.completed', cs)];
    return { cs, sub, inv, cus, events };
  };
  s.renew = (subId, { fail = false } = {}) => {
    const sub = s.subs[subId];
    const start = sub.current_period_end;
    // A scheduled plan change starts at the renewal: new price, new period, billing_reason "subscription_update",
    // one full charge and no proration (as observed with Stripe Test Clocks).
    const sch = sub.schedule && s.schedules[sub.schedule];
    const next = sch && sch.phases.find((ph) => ph.start_date === start && ph.items[0].price !== sub.items.data[0].price.id);
    if (next) { sub.items.data[0].price = { id: next.items[0].price }; if (next.plan) sub.metadata.plan = next.plan; }
    const inv = invoiceFor(sub, next ? 'subscription_update' : 'subscription_cycle', fail ? 'open' : 'paid', start);
    const events = [];
    if (fail) {
      sub.status = 'past_due';
      events.push(emit('invoice.payment_failed', inv), emit('customer.subscription.updated', sub));
    } else {
      sub.current_period_start = start;
      sub.current_period_end = inv.lines.data[0].period.end;
      events.push(emit('invoice.paid', inv), emit('customer.subscription.updated', sub));
    }
    return { inv, events };
  };
  s.payLater = (invId) => {
    const inv = s.invoices[invId];
    const sub = s.subs[inv.subscription];
    Object.assign(inv, { status: 'paid', amount_paid: inv.amount_due, attempt_count: 2, status_transitions: { paid_at: nowS() } });
    sub.status = 'active';
    sub.current_period_start = inv.lines.data[0].period.start;
    sub.current_period_end = inv.lines.data[0].period.end;
    return { events: [emit('invoice.paid', inv), emit('customer.subscription.updated', sub)] };
  };
  s.cancelAtPeriodEnd = (subId) => {
    const sub = s.subs[subId];
    Object.assign(sub, { cancel_at_period_end: true, cancel_at: sub.current_period_end });
    return { events: [emit('customer.subscription.updated', sub)] };
  };
  s.endNow = (subId) => {
    const sub = s.subs[subId];
    Object.assign(sub, { status: 'canceled', ended_at: nowS() });
    return { events: [emit('customer.subscription.deleted', sub)] };
  };
  s.refund = (invId, amount) => {
    const ch = s.charges[s.invoices[invId].charge];
    ch.amount_refunded += amount === undefined ? ch.amount - ch.amount_refunded : amount;
    return { events: [emit('charge.refunded', ch)] };
  };
  s.otherProduct = () => {
    const cus = { id: id('cus'), object: 'customer', email: 'otro@example.com', name: 'Otro' };
    s.customers[cus.id] = cus;
    const sub = { id: id('sub'), object: 'subscription', livemode: s.livemode, customer: cus.id, status: 'active', current_period_end: nowS() + 30 * 86400,
      metadata: {}, items: { data: [{ price: { id: 'price_other' }, quantity: 1 }] } };
    s.subs[sub.id] = sub;
    return { events: [emit('customer.subscription.created', sub)] };
  };
  return s;
}

module.exports = { makeStripe };
