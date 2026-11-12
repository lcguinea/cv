/**
 * Class subscriptions for luisguinea.com/formacion/ (same Apps Script project as Code.gs, which it reuses: config,
 * calendars, slots, script lock, validation helpers and owner notifications). See apps-script/BILLING.md.
 *
 * Sources of truth
 *   - Stripe: payments and subscriptions. Nothing here trusts the browser or a webhook payload: every change is made
 *     after downloading the event, invoice, subscription or Checkout Session from the Stripe API.
 *   - The ledger (Google Sheet, tab "movimientos"): append-only movements with unique ids. Credits, bookings and
 *     balances are always recomputed from it (deriveLedger_), never kept in an editable counter. A paid invoice
 *     grants its credits with ids "grant:<invoice>:<n>", so the same invoice can never grant twice.
 *
 * Everything that writes runs inside the script lock of Code.gs (withLock_), shared with the general agenda: two
 * simultaneous requests can never take the same credit or the same time.
 *
 * Plain ES5-style JavaScript with no modules, like Code.gs, so the Node tests (tests/test_billing.py) can run it with
 * mocked Google services and a fake Stripe.
 */

var STRIPE_API = 'https://api.stripe.com/v1';
var STRIPE_VERSION = '2024-06-20'; // pinned: the field names read below belong to this version
var PLANS = {
  weekly: { key: 'weekly', credits: 4, intervalWeeks: 4, amount: 14800, currency: 'eur', priceProp: 'STRIPE_PRICE_WEEKLY' },
  biweekly: { key: 'biweekly', credits: 4, intervalWeeks: 8, amount: 14800, currency: 'eur', priceProp: 'STRIPE_PRICE_BIWEEKLY' }
};
var CLASS_MINUTES = 60;
var MAX_CLASSES_PER_REQUEST = 4;
// Version of the contract conditions shown at checkout. Checkout stays closed until the Script Property
// TERMS_APPROVED_VERSION equals it, i.e. until Luis records that a lawyer approved exactly this text (launch gate).
var TERMS_VERSION = '2026-11-12-v1'; // = LEGAL_VERSION in tools/formacion_content.py (tests/test_billing.py)
var ACCESS_TOKEN_RE = /^([0-9a-f]{32})\.([0-9a-f]{64})$/;
var SESSION_ID_RE = /^cs_(test|live)_[A-Za-z0-9]{10,200}$/;
var BOOKING_ID_RE = /^[0-9a-f]{32}$/;
var EVENT_ID_RE_ = /^evt_[A-Za-z0-9]{8,255}$/;
var BILLING_DEFAULTS = {
  STUDENT_URL: 'https://luisguinea.com/alumnos/',
  PLANS_URL: 'https://luisguinea.com/formacion/#planes',
  STUDENT_CHANGE_HOURS: 24,
  CONSUME_GRACE_HOURS: 48,
  CARRY_MAX: 2,
  CARRY_DAYS: 30,
  LINK_HOURS: 72,
  SESSION_DAYS: 30,
  REMIND_HOURS: 24,
  EXPIRY_WARN_DAYS: 7,
  RATE_LINK_EMAIL_HOUR: 3,
  RATE_LINK_GLOBAL_HOUR: 30,
  RATE_CHECKOUT_HOUR: 30
};

// Exact field lists of every billing operation (anything else is rejected, like the agenda).
var BILLING_OPS = {
  checkout: ['op', 'plan', 'lang', 'requestId', 'acceptTerms', 'earlyStart', 'website'],
  checkout_status: ['op', 'session'],
  stu_link: ['op', 'email', 'lang', 'website'],
  stu_login: ['op', 'token'],
  stu_view: ['op', 'token'],
  stu_slots: ['op', 'token'],
  stu_book: ['op', 'token', 'requestId', 'starts'],
  stu_cancel: ['op', 'token', 'booking', 'confirm'],
  stu_move: ['op', 'token', 'booking', 'start'],
  stu_portal: ['op', 'token'],
  stu_logout: ['op', 'token'],
  stu_plan: ['op', 'token', 'plan', 'confirm'],
  stu_plan_undo: ['op', 'token'],
  stripe_event: ['op', 'id', 'type', 'ts', 'sig']
};

var TABLES = {
  movimientos: ['id', 'ts', 'tipo', 'alumno', 'credito', 'reserva', 'datos'],
  alumnos: ['cliente_stripe', 'alumno', 'email', 'nombre', 'idioma', 'creado'],
  suscripciones: ['suscripcion', 'alumno', 'cliente_stripe', 'plan', 'precio', 'estado', 'cancela_al_final', 'cancela_en',
    'fin_periodo', 'terminada_en', 'actualizada', 'cambio_plan', 'cambio_en', 'programacion'],
  eventos: ['evento', 'tipo', 'procesado', 'resultado'],
  accesos: ['id', 'hash', 'tipo', 'alumno', 'creado', 'expira', 'usado', 'revocado'],
  avisos: ['clave', 'ts'],
  incidencias: ['id', 'ts', 'tipo', 'alumno', 'detalle', 'estado'],
  ajustes: ['id', 'tipo', 'alumno', 'credito', 'valor', 'motivo', 'estado', 'procesado']
};

// ---------- configuration ----------

function billingConfig_() {
  var p = PropertiesService.getScriptProperties();
  function num(key) {
    var raw = p.getProperty(key);
    var n = raw === null || raw === '' ? NaN : Number(raw);
    return isFinite(n) && n >= 0 ? n : BILLING_DEFAULTS[key];
  }
  function url(key) {
    var v = p.getProperty(key) || BILLING_DEFAULTS[key];
    if (!/^https:\/\/[^\s?#]+(?:#[a-z-]+)?$/.test(v) && !/^http:\/\/127\.0\.0\.1:\d+\/[^\s?#]*(?:#[a-z-]+)?$/.test(v)) throw new Error('not_configured');
    return v;
  }
  var key = p.getProperty('STRIPE_SECRET_KEY') || '';
  var mode = p.getProperty('STRIPE_MODE') || '';
  var keyMode = /^(?:sk|rk)_test_/.test(key) ? 'test' : /^(?:sk|rk)_live_/.test(key) ? 'live' : '';
  // A key of the other mode is refused: test data can never mix with real charges.
  if (!keyMode || keyMode !== mode) throw new Error('not_configured');
  var prices = {};
  Object.keys(PLANS).forEach(function (k) {
    var id = p.getProperty(PLANS[k].priceProp) || '';
    if (!/^price_[A-Za-z0-9]+$/.test(id)) throw new Error('not_configured');
    prices[k] = id;
  });
  var relay = p.getProperty('RELAY_SECRET') || '';
  return {
    stripeKey: key,
    mode: mode,
    prices: prices,
    portalConfig: /^bpc_[A-Za-z0-9]+$/.test(p.getProperty('STRIPE_PORTAL_CONFIG') || '') ? p.getProperty('STRIPE_PORTAL_CONFIG') : '',
    relaySecret: /^[0-9a-f]{64}$/.test(relay) ? relay : '',
    spreadsheetId: p.getProperty('LEDGER_SPREADSHEET_ID') || '',
    checkoutEnabled: p.getProperty('BILLING_CHECKOUT_ENABLED') === 'true',
    termsApproved: p.getProperty('TERMS_APPROVED_VERSION') === TERMS_VERSION,
    policyEnforced: p.getProperty('CREDIT_POLICY_ENFORCED') === 'true',
    classAvailabilityId: p.getProperty('CLASS_AVAILABILITY_CALENDAR_ID') || '',
    classLocation: cleanText_(p.getProperty('CLASS_LOCATION') || '', 200, false) || '',
    studentUrl: url('STUDENT_URL'),
    plansUrl: url('PLANS_URL'),
    changeMs: num('STUDENT_CHANGE_HOURS') * 3600000,
    graceMs: num('CONSUME_GRACE_HOURS') * 3600000,
    carryMax: num('CARRY_MAX'),
    carryMs: num('CARRY_DAYS') * 86400000,
    linkMs: num('LINK_HOURS') * 3600000,
    sessionMs: num('SESSION_DAYS') * 86400000,
    remindMs: num('REMIND_HOURS') * 3600000,
    warnMs: num('EXPIRY_WARN_DAYS') * 86400000,
    rateLinkEmail: num('RATE_LINK_EMAIL_HOUR'),
    rateLinkGlobal: num('RATE_LINK_GLOBAL_HOUR'),
    rateCheckout: num('RATE_CHECKOUT_HOUR')
  };
}

function planForPrice_(bcfg, priceId) {
  var found = null;
  Object.keys(bcfg.prices).forEach(function (k) { if (bcfg.prices[k] === priceId) found = k; });
  return found;
}

// ---------- Stripe API (server to server; the key lives only in Script Properties) ----------

function formEncode_(obj, prefix, out) {
  out = out || [];
  Object.keys(obj).forEach(function (k) {
    var v = obj[k];
    var name = prefix ? prefix + '[' + k + ']' : k;
    if (v === undefined || v === null) return;
    if (typeof v === 'object') formEncode_(v, name, out);
    else out.push(encodeURIComponent(name) + '=' + encodeURIComponent(String(v)));
  });
  return out.join('&');
}

function stripe_(bcfg, method, path, params, idempotencyKey) {
  var headers = { Authorization: 'Bearer ' + bcfg.stripeKey, 'Stripe-Version': STRIPE_VERSION };
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  var opts = { method: method, headers: headers, muteHttpExceptions: true };
  var query = params ? formEncode_(params) : '';
  var target = STRIPE_API + path;
  if (method === 'post') { opts.payload = query; opts.contentType = 'application/x-www-form-urlencoded'; }
  else if (query) target += '?' + query;
  var res = UrlFetchApp.fetch(target, opts);
  var code = res.getResponseCode();
  var body;
  try { body = JSON.parse(res.getContentText()); } catch (e) { body = null; }
  if (code >= 200 && code < 300 && body) return body;
  var err = new Error('stripe_' + (code === 404 ? 'not_found' : 'error'));
  err.status = code;
  err.stripeCode = body && body.error && body.error.code;
  throw err;
}

function idOf_(x) { return x && typeof x === 'object' ? x.id : x || ''; }
function invoiceSubscription_(inv) {
  return idOf_(inv.subscription) || idOf_(inv.parent && inv.parent.subscription_details && inv.parent.subscription_details.subscription);
}
function linePrice_(line) { return idOf_(line.price) || idOf_(line.pricing && line.pricing.price_details && line.pricing.price_details.price); }
function subscriptionPeriodEnd_(sub) {
  if (sub.current_period_end) return sub.current_period_end * 1000;
  var item = sub.items && sub.items.data && sub.items.data[0];
  return item && item.current_period_end ? item.current_period_end * 1000 : 0;
}
function subscriptionPrice_(sub) {
  var item = sub.items && sub.items.data && sub.items.data[0];
  return item ? idOf_(item.price) : '';
}

// ---------- ledger store (Google Sheet; one tab per table, first row = headers) ----------

var DB_ = null;

function db_(bcfg) {
  if (DB_) return DB_;
  if (!bcfg.spreadsheetId) throw new Error('not_configured');
  var ss = SpreadsheetApp.openById(bcfg.spreadsheetId);
  var cache = {};
  function sheet(name) {
    var sh = ss.getSheetByName(name);
    if (!sh) {
      sh = ss.insertSheet(name);
      sh.appendRow(TABLES[name]);
    }
    return sh;
  }
  function load(name) {
    if (cache[name]) return cache[name];
    var values = sheet(name).getDataRange().getValues();
    var head = TABLES[name];
    var rows = [];
    for (var i = 1; i < values.length; i++) {
      var o = {};
      head.forEach(function (h, j) { o[h] = values[i][j] === undefined ? '' : values[i][j]; });
      o._row = i + 1;
      rows.push(o);
    }
    cache[name] = rows;
    return rows;
  }
  function toRow(name, obj) {
    return TABLES[name].map(function (h) { var v = obj[h]; return v === undefined || v === null ? '' : v; });
  }
  DB_ = {
    rows: load,
    find: function (name, field, value) {
      var rows = load(name);
      for (var i = 0; i < rows.length; i++) if (String(rows[i][field]) === String(value)) return rows[i];
      return null;
    },
    append: function (name, obj) {
      var rows = load(name);
      var sh = sheet(name);
      sh.appendRow(toRow(name, obj));
      var copy = {};
      Object.keys(obj).forEach(function (k) { copy[k] = obj[k]; });
      copy._row = rows.length + 2;
      rows.push(copy);
      return copy;
    },
    update: function (name, row, patch) {
      Object.keys(patch).forEach(function (k) { row[k] = patch[k]; });
      sheet(name).getRange(row._row, 1, 1, TABLES[name].length).setValues([toRow(name, row)]);
      return row;
    },
    sheet: sheet
  };
  return DB_;
}

function resetDb_() { DB_ = null; }

// ---------- movements and the derived ledger ----------

function movements_(db) {
  return db.rows('movimientos').map(function (m) {
    var data = {};
    try { data = m.datos ? JSON.parse(m.datos) : {}; } catch (e) { data = {}; }
    return { id: String(m.id), ts: Number(m.ts), tipo: String(m.tipo), alumno: String(m.alumno), credito: String(m.credito),
      reserva: String(m.reserva), datos: data };
  });
}

/** Appends a movement unless one with the same id exists. Returns true when it was written now. */
function addMovement_(db, mv) {
  if (db.find('movimientos', 'id', mv.id)) return false;
  db.append('movimientos', { id: mv.id, ts: mv.ts || Date.now(), tipo: mv.tipo, alumno: mv.alumno || '', credito: mv.credito || '',
    reserva: mv.reserva || '', datos: JSON.stringify(mv.datos || {}) });
  return true;
}

/**
 * Pure: credits and bookings from the movements, in the order they were written.
 *   credit: {id, alumno, factura, suscripcion, plan, inicio, fin, estado: disponible|reservado|consumido|anulado,
 *            reserva, protegido, traslado: true|false|null, expira (ms or null = no deadline), origen}
 *   booking: {id, alumno, credito, evento, inicio, fin, estado: reservada|realizada|cancelada, motivo, cambios}
 * Deadlines: a credit is meant for its own cycle (expira = cycle end). At the cycle end a "rollover" movement records
 * which unused credits move on (at most CARRY_MAX, deadline = cycle end + CARRY_DAYS) and which do not. A class Luis
 * cancels gives its credit back with no deadline (protegido). An "extend" movement (adjustment) sets a new deadline.
 * A credit freed by the student after its cycle ended, without a rollover decision, counts as carried over.
 */
function deriveLedger_(moves, policy) {
  var credits = {}, bookings = {};
  moves.forEach(function (m) {
    var c = credits[m.credito];
    switch (m.tipo) {
      case 'grant':
        if (credits[m.credito]) break;
        credits[m.credito] = { id: m.credito, alumno: m.alumno, factura: m.datos.factura || '', suscripcion: m.datos.suscripcion || '',
          plan: m.datos.plan || '', inicio: m.datos.inicio, fin: m.datos.fin, estado: 'disponible', reserva: '', protegido: !!m.datos.sinPlazo,
          traslado: null, expira: m.datos.sinPlazo ? null : m.datos.fin, origen: m.datos.origen || 'stripe', concedido: m.ts };
        break;
      case 'reserve':
        if (!c || c.estado !== 'disponible') break;
        c.estado = 'reservado'; c.reserva = m.reserva;
        bookings[m.reserva] = { id: m.reserva, alumno: m.alumno, credito: m.credito, evento: m.datos.evento, inicio: m.datos.inicio,
          fin: m.datos.fin, estado: 'reservada', motivo: '', cambios: 0, creada: m.ts, pedido: m.datos.pedido, total: m.datos.total };
        break;
      case 'move':
        if (bookings[m.reserva] && bookings[m.reserva].estado === 'reservada') {
          bookings[m.reserva].inicio = m.datos.inicio; bookings[m.reserva].fin = m.datos.fin;
          if (m.datos.porAlumno) bookings[m.reserva].cambios++;
        }
        break;
      case 'release':
        if (!c || c.estado !== 'reservado' || c.reserva !== m.reserva) break;
        c.estado = 'disponible'; c.reserva = '';
        if (bookings[m.reserva]) { bookings[m.reserva].estado = 'cancelada'; bookings[m.reserva].motivo = m.datos.motivo || ''; }
        if (m.datos.motivo === 'profesor') { c.protegido = true; c.expira = null; }
        else if (c.traslado === null && !c.protegido && c.origen === 'stripe' && m.ts >= c.fin) { c.traslado = true; c.expira = c.fin + policy.carryMs; }
        break;
      case 'consume':
        if (!c || c.estado !== 'reservado' || c.reserva !== m.reserva) break;
        c.estado = 'consumido';
        if (bookings[m.reserva]) bookings[m.reserva].estado = 'realizada';
        break;
      case 'rollover':
        if (!c || c.traslado !== null || c.protegido) break;
        c.traslado = !!m.datos.traslado;
        c.expira = c.traslado ? c.fin + policy.carryMs : c.fin;
        break;
      case 'restore':
        // Justified absence (adjustment "justificar"): the class counted as done goes back, with no deadline.
        if (!c || c.estado !== 'consumido') break;
        c.estado = 'disponible'; c.reserva = ''; c.protegido = true; c.expira = null;
        if (bookings[m.reserva]) { bookings[m.reserva].estado = 'cancelada'; bookings[m.reserva].motivo = 'justificada'; }
        break;
      case 'extend':
        if (c) { c.expira = m.datos.hasta; }
        break;
      case 'void':
        if (c && c.estado === 'disponible') c.estado = 'anulado';
        break;
    }
  });
  return { credits: credits, bookings: bookings };
}

function policy_(bcfg) { return { carryMs: bcfg.carryMs, carryMax: bcfg.carryMax, enforced: bcfg.policyEnforced }; }

/** Can this credit pay for a class starting at classStartMs? Deadlines only bind when CREDIT_POLICY_ENFORCED is on. */
function creditUsable_(c, nowMs, classStartMs, policy) {
  if (c.estado !== 'disponible') return false;
  if (!policy.enforced || c.expira === null || c.expira === '') return true;
  return nowMs < c.expira && classStartMs < c.expira;
}

/** Oldest first: earliest deadline, then oldest cycle, then credit id. Credits with no deadline go last. */
function sortCredits_(list) {
  return list.sort(function (a, b) {
    var ea = a.expira === null ? Infinity : a.expira, eb = b.expira === null ? Infinity : b.expira;
    if (ea !== eb) return ea - eb;
    if (a.inicio !== b.inicio) return a.inicio - b.inicio;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

function studentCredits_(ledger, alumno) {
  return Object.keys(ledger.credits).map(function (k) { return ledger.credits[k]; }).filter(function (c) { return c.alumno === alumno; });
}

function studentBookings_(ledger, alumno) {
  return Object.keys(ledger.bookings).map(function (k) { return ledger.bookings[k]; }).filter(function (b) { return b.alumno === alumno; });
}

/** Pure: assigns one usable credit to each class start (sorted ascending), oldest credit to the earliest class. */
function assignCredits_(credits, startsMs, nowMs, policy) {
  var pool = sortCredits_(credits.slice());
  var used = {};
  var out = [];
  for (var i = 0; i < startsMs.length; i++) {
    var pick = null;
    for (var j = 0; j < pool.length; j++) {
      if (!used[pool[j].id] && creditUsable_(pool[j], nowMs, startsMs[i], policy)) { pick = pool[j]; break; }
    }
    if (!pick) return null;
    used[pick.id] = true;
    out.push(pick);
  }
  return out;
}

// ---------- students and access links ----------

function studentId_(email) { return 'al_' + sha256Hex_('student:' + String(email).toLowerCase()).slice(0, 24); }

function studentByAlumno_(db, alumno) {
  var rows = db.rows('alumnos').filter(function (r) { return r.alumno === alumno; });
  return rows.length ? rows[rows.length - 1] : null;
}

/** Student row for a Stripe customer, created from the customer's email the first time it is seen. */
function ensureStudent_(bcfg, db, customerId, lang) {
  var row = db.find('alumnos', 'cliente_stripe', customerId);
  if (row) return row;
  var cus = stripe_(bcfg, 'get', '/customers/' + encodeURIComponent(customerId));
  var email = String(cus.email || '').trim().toLowerCase();
  if (!EMAIL_RE.test(email)) throw new Error('customer_without_email');
  var name = cleanText_(String(cus.name || ''), NAME_MAX, false) || '';
  return db.append('alumnos', { cliente_stripe: customerId, alumno: studentId_(email), email: email, nombre: name,
    idioma: lang === 'en' ? 'en' : 'es', creado: Date.now() });
}

function issueAccess_(bcfg, db, alumno, kind, nowMs) {
  var id = randomHex_(32), secret = randomHex_(64);
  db.append('accesos', { id: id, hash: sha256Hex_('access:' + kind + ':' + secret), tipo: kind, alumno: alumno, creado: nowMs,
    expira: nowMs + (kind === 'link' ? bcfg.linkMs : bcfg.sessionMs), usado: '', revocado: '' });
  return id + '.' + secret;
}

function checkAccess_(db, token, kind, nowMs) {
  var m = typeof token === 'string' ? ACCESS_TOKEN_RE.exec(token) : null;
  if (!m) return null;
  var row = db.find('accesos', 'id', m[1]);
  if (!row || row.tipo !== kind || row.revocado || Number(row.expira) <= nowMs) return null;
  if (row.hash !== sha256Hex_('access:' + kind + ':' + m[2])) return null;
  if (kind === 'link' && row.usado) return null;
  return row;
}

function sendAccessLink_(bcfg, db, student, reason) {
  var token = issueAccess_(bcfg, db, student.alumno, 'link', Date.now());
  var link = bcfg.studentUrl + '#acceso=' + token;
  var es = student.idioma !== 'en';
  var hours = Math.round(bcfg.linkMs / 3600000);
  var intro = reason === 'welcome'
    ? (es ? 'Gracias por contratar tus clases de música con Luis Guinea. Tu pago está confirmado y tus clases ya están disponibles.\n\n'
      : 'Thank you for subscribing to music lessons with Luis Guinea. Your payment is confirmed and your lessons are ready.\n\n')
    : '';
  var body = es
    ? intro + 'Entra en tu área de alumno para reservar tus clases, ver tus créditos y gestionar tu suscripción:\n' + link +
      '\n\nEl enlace es personal, sirve una sola vez y caduca en ' + hours + ' horas. Si no lo has pedido tú, ignora este correo.'
    : intro + 'Open your student area to book your lessons, see your credits and manage your subscription:\n' + link +
      '\n\nThe link is personal, works once and expires in ' + hours + ' hours. If you did not ask for it, ignore this email.';
  var subject = reason === 'welcome' ? (es ? 'Tus clases con Luis Guinea: acceso a tu área de alumno' : 'Your lessons with Luis Guinea: your student area')
    : (es ? 'Tu enlace de acceso · Clases con Luis Guinea' : 'Your access link · Lessons with Luis Guinea');
  MailApp.sendEmail({ to: student.email, subject: subject, body: body, name: 'Luis Guinea' });
}

// ---------- one-off notifications (each key is sent at most once) ----------

function onceKey_(db, key) {
  if (db.find('avisos', 'clave', key)) return false;
  db.append('avisos', { clave: key, ts: Date.now() });
  return true;
}

function mailOwner_(cfg, db, key, subject, lines) {
  if (key && db.find('avisos', 'clave', key)) return;
  var to = ownerEmail_(cfg);
  if (!to) return;
  try {
    MailApp.sendEmail({ to: to, subject: subject, body: lines.join('\n'), name: 'Clases luisguinea.com' });
    if (key) onceKey_(db, key);
  } catch (e) { /* best effort: retried by the next run while the key is missing */ }
}

function mailStudent_(db, key, student, subject, body) {
  if (!student || (key && db.find('avisos', 'clave', key))) return;
  try {
    MailApp.sendEmail({ to: student.email, subject: subject, body: body, name: 'Luis Guinea' });
    if (key) onceKey_(db, key);
  } catch (e) { /* best effort */ }
}

function incident_(cfg, db, id, tipo, alumno, detail) {
  if (db.find('incidencias', 'id', id)) return;
  db.append('incidencias', { id: id, ts: Date.now(), tipo: tipo, alumno: alumno || '', detalle: detail, estado: 'abierta' });
  mailOwner_(cfg, db, 'incident:' + id, 'Incidencia en las clases: ' + tipo, [
    'Hay una incidencia que requiere tu revisión en el sistema de clases de luisguinea.com.', '',
    'Tipo: ' + tipo, 'Alumno: ' + (alumno || 'sin identificar'), 'Detalle: ' + detail, '',
    'No se ha cambiado ningún crédito automáticamente. Revisa la pestaña "incidencias" de la hoja de clases y, si hace falta, ' +
    'registra un ajuste en la pestaña "ajustes".'
  ]);
}

function whenText_(cfg, ms) { var p = localParts_(ms, cfg.timeZone); return p.day + ' ' + p.time; }

// ---------- Stripe sync (idempotent; safe in any order and any number of times) ----------

/**
 * Grants the credits of one paid subscription invoice. Called from webhooks, from the confirmation page and from the
 * hourly reconciliation: whichever comes first grants, the others find the movements already there.
 */
function syncInvoice_(cfg, bcfg, db, invoiceId) {
  var inv = stripe_(bcfg, 'get', '/invoices/' + encodeURIComponent(invoiceId));
  var subId = invoiceSubscription_(inv);
  if (inv.livemode !== (bcfg.mode === 'live')) return { granted: 0, reason: 'other_mode' };
  if (!subId) return { granted: 0, reason: 'not_subscription' };
  if (inv.status !== 'paid') return { granted: 0, reason: 'not_paid' };
  var lines = (inv.lines && inv.lines.data) || [];
  var line = null, plan = null;
  lines.forEach(function (l) { var p = planForPrice_(bcfg, linePrice_(l)); if (p && !line && !l.proration) { line = l; plan = p; } });
  if (!line) return { granted: 0, reason: 'unknown_price' };
  var reason = inv.billing_reason;
  // A plan change scheduled for the end of the paid cycle (changePlan_) starts the new cycle with a
  // "subscription_update" invoice: verified with Stripe Test Clocks to be one full 148 EUR charge with no proration.
  // It counts as a renewal only when it is exactly that; anything with proration lines stays an incident.
  var cleanUpdate = reason === 'subscription_update' && lines.every(function (l) { return !l.proration; }) &&
    lines.filter(function (l) { return planForPrice_(bcfg, linePrice_(l)); }).length === 1 && Number(inv.amount_paid) === PLANS[plan].amount;
  if (reason !== 'subscription_create' && reason !== 'subscription_cycle' && !cleanUpdate) {
    incident_(cfg, db, 'invoice-reason:' + inv.id, 'factura_inesperada', '', 'La factura ' + inv.id + ' (' + reason +
      ') está pagada pero no es un alta ni una renovación: no se han concedido clases.');
    return { granted: 0, reason: 'unexpected_reason' };
  }
  var student = ensureStudent_(bcfg, db, idOf_(inv.customer), '');
  var qty = Number(line.quantity || 1);
  var count = PLANS[plan].credits * qty;
  var expected = PLANS[plan].amount * qty;
  if (qty !== 1 || Number(inv.amount_paid) !== expected || inv.currency !== PLANS[plan].currency) {
    incident_(cfg, db, 'invoice-amount:' + inv.id, 'importe_inesperado', student.alumno, 'La factura ' + inv.id + ' cobró ' +
      inv.amount_paid + ' ' + inv.currency + ' por ' + qty + ' unidad(es); se esperaban ' + expected + ' eur. Se han concedido ' + count + ' clases.');
  }
  var start = line.period && line.period.start ? line.period.start * 1000 : (inv.period_start || 0) * 1000;
  var end = line.period && line.period.end ? line.period.end * 1000 : (inv.period_end || 0) * 1000;
  var paidAt = inv.status_transitions && inv.status_transitions.paid_at ? inv.status_transitions.paid_at * 1000 : Date.now();
  var granted = 0;
  for (var n = 1; n <= count; n++) {
    if (addMovement_(db, { id: 'grant:' + inv.id + ':' + n, ts: Date.now(), tipo: 'grant', alumno: student.alumno, credito: inv.id + ':' + n,
      datos: { factura: inv.id, suscripcion: subId, plan: plan, inicio: start, fin: end, pagada: paidAt, origen: 'stripe' } })) granted++;
  }
  if (reason === 'subscription_create') {
    if (!db.find('avisos', 'clave', 'welcome:' + subId)) {
      try { sendAccessLink_(bcfg, db, student, 'welcome'); onceKey_(db, 'welcome:' + subId); } catch (e) { /* retried hourly */ }
    }
    mailOwner_(cfg, db, 'newsub:' + subId, 'Nueva suscripción: ' + (student.nombre || student.email) + ' · plan ' + planLabel_(plan), [
      'Nueva suscripción a las clases de luisguinea.com.', '',
      'Alumno: ' + (student.nombre || 'sin nombre') + ' <' + student.email + '>',
      'Plan: ' + planLabel_(plan) + ' (148 € cada ' + PLANS[plan].intervalWeeks + ' semanas, 4 clases)',
      'Ciclo pagado: ' + whenText_(cfg, start) + ' → ' + whenText_(cfg, end),
      'Clases concedidas: ' + count, '',
      'El alumno ha recibido el enlace a su área para reservar. Panel: pestaña "panel" de la hoja de clases.'
    ]);
  }
  return { granted: granted, reason: 'ok', alumno: student.alumno };
}

function planLabel_(plan) { return plan === 'biweekly' ? 'quincenal' : plan === 'weekly' ? 'semanal' : String(plan); }

/** Refreshes the snapshot of one subscription from Stripe and sends the notices of its state changes. */
function syncSubscription_(cfg, bcfg, db, subId) {
  var sub = stripe_(bcfg, 'get', '/subscriptions/' + encodeURIComponent(subId));
  if (sub.livemode !== (bcfg.mode === 'live')) return null;
  var plan = planForPrice_(bcfg, subscriptionPrice_(sub));
  if (!plan) return null; // another product of the account: not ours
  // A Checkout whose first payment has not gone through (declined card, abandoned 3-D Secure) leaves an "incomplete"
  // subscription in Stripe. It is nobody's plan yet: no student, no snapshot, no notice until Stripe says it is paid.
  var row0 = db.find('suscripciones', 'suscripcion', sub.id);
  if (!row0 && (sub.status === 'incomplete' || sub.status === 'incomplete_expired')) return null;
  var lang = sub.metadata && sub.metadata.lang === 'en' ? 'en' : 'es';
  var student = ensureStudent_(bcfg, db, idOf_(sub.customer), lang);
  var snap = { suscripcion: sub.id, alumno: student.alumno, cliente_stripe: idOf_(sub.customer), plan: plan, precio: subscriptionPrice_(sub),
    estado: sub.status, cancela_al_final: sub.cancel_at_period_end ? 'sí' : '', cancela_en: sub.cancel_at ? sub.cancel_at * 1000 : '',
    fin_periodo: subscriptionPeriodEnd_(sub), terminada_en: sub.ended_at ? sub.ended_at * 1000 : '', actualizada: Date.now(),
    cambio_plan: '', cambio_en: '', programacion: idOf_(sub.schedule) };
  var pending = pendingChange_(bcfg, sub, plan);
  if (pending) { snap.cambio_plan = pending.plan; snap.cambio_en = pending.at; }
  var row = db.find('suscripciones', 'suscripcion', sub.id);
  if (row) db.update('suscripciones', row, snap); else db.append('suscripciones', snap);
  var es = student.idioma !== 'en';
  var endsAt = sub.cancel_at ? sub.cancel_at * 1000 : subscriptionPeriodEnd_(sub);
  if ((sub.cancel_at_period_end || sub.cancel_at) && sub.status !== 'canceled') {
    var key = 'cancel:' + sub.id + ':' + endsAt;
    mailOwner_(cfg, db, key, 'Cancelación programada: ' + (student.nombre || student.email), [
      (student.nombre || student.email) + ' <' + student.email + '> ha cancelado la renovación de su plan ' + planLabel_(plan) + '.',
      'La suscripción termina el ' + whenText_(cfg, endsAt) + ' (no habrá más cobros).',
      'Las clases ya pagadas se conservan: no se ha borrado ningún crédito.'
    ]);
    mailStudent_(db, 'cancel-student:' + sub.id + ':' + endsAt, student,
      es ? 'Cancelación de tu suscripción confirmada' : 'Your subscription cancellation is confirmed',
      es ? 'Hemos registrado la cancelación de la renovación automática de tu plan de clases. No habrá más cobros a partir del ' +
          whenText_(cfg, endsAt) + ' (hora de Madrid).\n\nLas clases que ya has pagado siguen disponibles en tu área de alumno:\n' + bcfg.studentUrl
        : 'We have recorded the cancellation of your lesson plan\'s automatic renewal. There will be no further charges from ' +
          whenText_(cfg, endsAt) + ' (Madrid time).\n\nThe lessons you have already paid for are still available in your student area:\n' + bcfg.studentUrl);
  }
  if (sub.status === 'canceled') {
    mailOwner_(cfg, db, 'ended:' + sub.id, 'Suscripción terminada: ' + (student.nombre || student.email), [
      'La suscripción ' + planLabel_(plan) + ' de ' + (student.nombre || student.email) + ' <' + student.email + '> ha terminado' +
      (sub.ended_at ? ' el ' + whenText_(cfg, sub.ended_at * 1000) : '') + '.',
      'Sus clases pagadas y no usadas se conservan con sus fechas; revisa el panel por si quieres ofrecerle una alternativa.'
    ]);
    if (!db.find('avisos', 'clave', 'cancel-student:' + sub.id + ':' + endsAt)) {
      mailStudent_(db, 'ended-student:' + sub.id, student, es ? 'Tu suscripción de clases ha terminado' : 'Your lesson subscription has ended',
        es ? 'Tu suscripción de clases con Luis Guinea ha terminado y no habrá más cobros. Las clases pagadas que no hayas usado siguen en tu área de alumno:\n' + bcfg.studentUrl
          : 'Your lesson subscription with Luis Guinea has ended and there will be no further charges. Paid lessons you have not used are still in your student area:\n' + bcfg.studentUrl);
    }
  }
  if (sub.status === 'past_due' || sub.status === 'unpaid' || sub.status === 'incomplete_expired') {
    incident_(cfg, db, 'sub-status:' + sub.id + ':' + sub.status, 'suscripcion_' + sub.status, student.alumno,
      'La suscripción ' + sub.id + ' está en estado ' + sub.status + '. No se conceden clases hasta que se pague una factura.');
  }
  return snap;
}

/** Plan the subscription moves to at a future phase of its schedule, or null. */
function pendingChange_(bcfg, sub, currentPlan) {
  var schedId = idOf_(sub.schedule);
  if (!schedId) return null;
  var sch = stripe_(bcfg, 'get', '/subscription_schedules/' + encodeURIComponent(schedId));
  if (sch.status !== 'active' && sch.status !== 'not_started') return null;
  var now = Date.now() / 1000;
  var next = null;
  (sch.phases || []).forEach(function (ph) {
    var price = ph.items && ph.items[0] && idOf_(ph.items[0].price);
    var p = planForPrice_(bcfg, price);
    if (!next && ph.start_date > now && p && p !== currentPlan) next = { plan: p, at: ph.start_date * 1000 };
  });
  return next;
}

/** Processes one Stripe event (already downloaded from the API). Returns a short result for the "eventos" tab. */
function handleEvent_(cfg, bcfg, db, ev) {
  var obj = (ev.data && ev.data.object) || {};
  switch (ev.type) {
    case 'checkout.session.completed':
    case 'checkout.session.async_payment_succeeded':
      if (obj.mode !== 'subscription' || !obj.subscription) return 'ignored';
      syncSubscription_(cfg, bcfg, db, idOf_(obj.subscription));
      if (obj.invoice) syncInvoice_(cfg, bcfg, db, idOf_(obj.invoice));
      return 'ok';
    case 'invoice.paid':
    case 'invoice.payment_succeeded':
      var r = syncInvoice_(cfg, bcfg, db, obj.id);
      var s1 = invoiceSubscription_(obj);
      if (s1) syncSubscription_(cfg, bcfg, db, s1);
      return 'ok:' + r.reason + ':' + r.granted;
    case 'invoice.payment_failed':
      var s2 = invoiceSubscription_(obj);
      var snap = s2 ? syncSubscription_(cfg, bcfg, db, s2) : null;
      // Only renewals: a declined first payment is shown by Checkout itself and no subscription starts.
      if (snap && obj.billing_reason !== 'subscription_create') {
        var st = studentByAlumno_(db, snap.alumno);
        mailOwner_(cfg, db, 'failed:' + obj.id + ':' + (obj.attempt_count || 0), 'Pago fallido: ' + (st ? st.nombre || st.email : snap.alumno), [
          'Ha fallado el cobro de la renovación del plan ' + planLabel_(snap.plan) + ' de ' + (st ? (st.nombre || '') + ' <' + st.email + '>' : snap.alumno) + '.',
          'Factura: ' + obj.id + ' · intento ' + (obj.attempt_count || 1) + '.',
          'Stripe reintentará el cobro. El alumno ha recibido un aviso para actualizar su tarjeta. No se conceden clases nuevas hasta que se pague.'
        ]);
        // Our own notice: the account's Stripe emails are not used (their links would point to the restaurant's site).
        if (st) {
          var esF = st.idioma !== 'en';
          mailStudent_(db, 'failed-student:' + obj.id + ':' + (obj.attempt_count || 0), st,
            esF ? 'No hemos podido cobrar la renovación de tus clases' : 'We could not charge your lesson renewal',
            esF ? 'No se ha podido cobrar la renovación de tu plan de clases (148 €). Stripe volverá a intentarlo en los próximos días.\n\n' +
                'Para evitarlo, revisa o cambia tu tarjeta en tu área de alumno, apartado Facturación:\n' + bcfg.studentUrl +
                '\n\nTus clases ya pagadas siguen disponibles.'
              : 'Your lesson plan renewal (€148) could not be charged. Stripe will try again in the coming days.\n\n' +
                'To avoid problems, check or change your card in your student area, Billing section:\n' + bcfg.studentUrl +
                '\n\nYour paid lessons are still available.');
        }
      }
      return 'ok';
    case 'customer.subscription.created':
    case 'customer.subscription.updated':
    case 'customer.subscription.deleted':
    case 'customer.subscription.paused':
    case 'customer.subscription.resumed':
      syncSubscription_(cfg, bcfg, db, obj.id);
      return 'ok';
    case 'charge.refunded':
      recordRefund_(cfg, bcfg, db, obj.id);
      return 'refund';
    case 'charge.dispute.created':
    case 'charge.dispute.closed':
    case 'credit_note.created':
    case 'invoice.voided':
    case 'invoice.marked_uncollectible':
      incident_(cfg, db, 'event:' + ev.id, ev.type, '', 'Stripe ha comunicado ' + ev.type + ' sobre ' + (obj.id || '?') +
        (obj.invoice ? ' (factura ' + idOf_(obj.invoice) + ')' : '') + '. Decide si hay que anular o mantener clases (pestaña "ajustes").');
      return 'incident';
    default:
      return 'ignored';
  }
}

/**
 * Records a refund (total or partial) in the ledger with its invoice and amount, and tells Luis what it covers. Credits
 * are NOT changed automatically: whether a refund cancels lessons is decided by hand ("anular" in the "ajustes" tab).
 * The movement id carries the refunded total, so each new partial refund is recorded once.
 */
function recordRefund_(cfg, bcfg, db, chargeId) {
  var ch = stripe_(bcfg, 'get', '/charges/' + encodeURIComponent(chargeId));
  if (ch.livemode !== (bcfg.mode === 'live')) return;
  var invId = idOf_(ch.invoice);
  var student = ch.customer ? ensureStudent_(bcfg, db, idOf_(ch.customer), '') : null;
  var total = Number(ch.amount_refunded) >= Number(ch.amount);
  var unused = 0;
  if (invId) {
    var led = deriveLedger_(movements_(db), policy_(bcfg));
    Object.keys(led.credits).forEach(function (k) { var c = led.credits[k]; if (c.factura === invId && c.estado === 'disponible') unused++; });
  }
  var written = addMovement_(db, { id: 'refund:' + ch.id + ':' + ch.amount_refunded, tipo: 'refund', alumno: student ? student.alumno : '',
    datos: { cargo: ch.id, factura: invId, reembolsado: Number(ch.amount_refunded), cobrado: Number(ch.amount), total: total, moneda: ch.currency } });
  if (!written) return;
  incident_(cfg, db, 'refund:' + ch.id + ':' + ch.amount_refunded, total ? 'reembolso_total' : 'reembolso_parcial', student ? student.alumno : '',
    'Reembolso de ' + (Number(ch.amount_refunded) / 100).toFixed(2) + ' € de ' + (Number(ch.amount) / 100).toFixed(2) + ' € (factura ' + (invId || '?') +
    '). Clases de esa factura sin usar: ' + unused + '. No se ha anulado ninguna: si el reembolso las cubre, anúlalas en "ajustes".');
}

/** Webhook entry point (via the Worker relay): authenticated by RELAY_SECRET, then re-downloaded from Stripe. */
function stripeEvent_(cfg, bcfg, raw) {
  if (!bcfg.relaySecret || !EVENT_ID_RE_.test(String(raw.id || '')) || typeof raw.ts !== 'number' || typeof raw.sig !== 'string') {
    return { ok: false, error: 'invalid_request' };
  }
  if (Math.abs(Date.now() / 1000 - raw.ts) > 300) return { ok: false, error: 'invalid_request' };
  var expected = hmacHex_(bcfg.relaySecret, raw.ts + '.' + raw.id);
  if (!constantEq_(expected, raw.sig)) return { ok: false, error: 'invalid_request' };
  return withLock_(function () {
    var db = db_(bcfg);
    var done = db.find('eventos', 'evento', raw.id);
    if (done && /^(ok|ignored|incident)/.test(String(done.resultado))) return { ok: true, status: 'duplicate' };
    var ev;
    try { ev = stripe_(bcfg, 'get', '/events/' + encodeURIComponent(raw.id)); }
    catch (e) { return { ok: false, error: e.status === 404 ? 'invalid_event' : 'unavailable' }; }
    if (ev.livemode !== (bcfg.mode === 'live')) return { ok: false, error: 'invalid_event' };
    var result = handleEvent_(cfg, bcfg, db, ev);
    if (done) db.update('eventos', done, { procesado: Date.now(), resultado: result });
    else db.append('eventos', { evento: ev.id, tipo: ev.type, procesado: Date.now(), resultado: result });
    refreshPanel_(cfg, bcfg, db);
    return { ok: true, status: result };
  });
}

function hmacHex_(secret, message) {
  return Utilities.computeHmacSha256Signature(message, secret).map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join('');
}

function constantEq_(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  var diff = 0;
  for (var i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// ---------- checkout ----------

function rateHit_(key, limit) {
  var cache = CacheService.getScriptCache();
  var n = Number(cache.get(key) || 0);
  if (n >= limit) return true;
  try { cache.put(key, String(n + 1), 3700); } catch (e) { /* best effort */ }
  return false;
}

function createCheckout_(cfg, bcfg, raw) {
  // Launch gate: both switches, set by hand by Luis (see docs/lanzamiento/CHECKLIST-LANZAMIENTO.md).
  if (!bcfg.checkoutEnabled || !bcfg.termsApproved) return { ok: false, error: 'not_available' };
  if (raw.website !== undefined && raw.website !== '') return { ok: false, error: 'rejected' };
  if (!PLANS.hasOwnProperty(raw.plan)) return { ok: false, error: 'invalid_plan' };
  if (typeof raw.requestId !== 'string' || !REQUEST_ID_RE.test(raw.requestId)) return { ok: false, error: 'invalid_request' };
  if (raw.acceptTerms !== true) return { ok: false, error: 'terms_required' };
  if (raw.earlyStart !== true) return { ok: false, error: 'early_start_required' };
  var lang = raw.lang === 'en' ? 'en' : 'es';
  var plan = PLANS[raw.plan];
  var es = lang === 'es';
  var every = es ? 'cada ' + plan.intervalWeeks + ' semanas' : 'every ' + plan.intervalWeeks + ' weeks';
  if (rateHit_('rl:co:' + Math.floor(Date.now() / 3600000), bcfg.rateCheckout)) return { ok: false, error: 'rate_limited' };
  var params = {
    mode: 'subscription',
    line_items: { 0: { price: bcfg.prices[raw.plan], quantity: 1 } },
    success_url: bcfg.studentUrl + '?checkout={CHECKOUT_SESSION_ID}',
    cancel_url: bcfg.plansUrl,
    locale: lang,
    allow_promotion_codes: 'false',
    billing_address_collection: 'auto',
    tax_id_collection: { enabled: 'true' },
    payment_method_types: { 0: 'card' },
    // No client_reference_id: another integration of this Stripe account (the restaurant's shop) keys its orders on it.
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    metadata: { plan: raw.plan, lang: lang, terms: TERMS_VERSION, early_start: 'true', source: 'luisguinea.com' },
    subscription_data: { metadata: { plan: raw.plan, lang: lang, terms: TERMS_VERSION, early_start: 'true' } },
    custom_text: { submit: { message: es
      ? 'Clases de música de Luis Carlos Guinea Moctezuma (titular de la cuenta de cobro «Santo Chilaquil»). Se renovará automáticamente ' + every + ' por 148 € (4 clases presenciales de 60 minutos). Puedes cancelar la renovación cuando quieras desde tu área de alumno; tendrá efecto al final del periodo pagado.'
      : 'Music lessons by Luis Carlos Guinea Moctezuma (holder of the payment account "Santo Chilaquil"). Renews automatically ' + every + ' for €148 (4 in-person 60-minute lessons). You can cancel the renewal at any time from your student area; it takes effect at the end of the paid period.' } }
  };
  try {
    var session = stripe_(bcfg, 'post', '/checkout/sessions', params, 'checkout:' + raw.requestId);
    if (!/^https:\/\/checkout\.stripe\.com\//.test(session.url || '')) return { ok: false, error: 'unavailable' };
    return { ok: true, url: session.url };
  } catch (e) {
    return { ok: false, error: e.status === 400 && e.stripeCode === 'idempotency_key_in_use' ? 'busy' : 'unavailable' };
  }
}

/**
 * What the return page shows after Stripe Checkout. The session id only identifies a payment: it unlocks nothing and
 * returns no personal data. When Stripe says the first invoice is paid, its credits are granted here (idempotently),
 * so the student does not wait for the webhook; the access link always goes to the email address used in Checkout.
 */
function checkoutStatus_(cfg, bcfg, raw) {
  if (typeof raw.session !== 'string' || !SESSION_ID_RE.test(raw.session)) return { ok: false, error: 'invalid_request' };
  if (raw.session.indexOf('cs_' + bcfg.mode + '_') !== 0) return { ok: false, error: 'invalid_request' };
  var s;
  try { s = stripe_(bcfg, 'get', '/checkout/sessions/' + encodeURIComponent(raw.session)); }
  catch (e) { return { ok: false, error: e.status === 404 ? 'invalid_request' : 'unavailable' }; }
  var plan = s.metadata && PLANS.hasOwnProperty(s.metadata.plan) ? s.metadata.plan : null;
  if (s.mode !== 'subscription' || !plan) return { ok: false, error: 'invalid_request' };
  if (s.status === 'expired') return { ok: true, state: 'expired', plan: plan };
  if (s.status !== 'complete') return { ok: true, state: 'open', plan: plan };
  if (s.payment_status !== 'paid' || !s.invoice) return { ok: true, state: 'processing', plan: plan };
  return withLock_(function () {
    var db = db_(bcfg);
    var inv = idOf_(s.invoice);
    if (!db.find('movimientos', 'id', 'grant:' + inv + ':1')) {
      try {
        syncSubscription_(cfg, bcfg, db, idOf_(s.subscription));
        syncInvoice_(cfg, bcfg, db, inv);
        refreshPanel_(cfg, bcfg, db);
      } catch (e) { return { ok: true, state: 'processing', plan: plan }; }
    }
    var credited = !!db.find('movimientos', 'id', 'grant:' + inv + ':1');
    return { ok: true, state: credited ? 'ready' : 'processing', plan: plan,
      accessEmail: db.find('avisos', 'clave', 'welcome:' + idOf_(s.subscription)) ? 'sent' : 'pending' };
  });
}

// ---------- student area ----------

function sessionStudent_(bcfg, db, token) {
  var row = checkAccess_(db, token, 'session', Date.now());
  if (!row) return null;
  return studentByAlumno_(db, row.alumno);
}

function requestLink_(cfg, bcfg, raw) {
  if (raw.website !== undefined && raw.website !== '') return { ok: false, error: 'rejected' };
  var email = typeof raw.email === 'string' ? raw.email.trim().toLowerCase() : '';
  if (!email || email.length > EMAIL_MAX || CONTROL_RE.test(email) || !EMAIL_RE.test(email)) return { ok: false, error: 'invalid_email' };
  var hour = Math.floor(Date.now() / 3600000);
  if (rateHit_('rl:lk:g:' + hour, bcfg.rateLinkGlobal)) return { ok: false, error: 'rate_limited' };
  if (rateHit_('rl:lk:e:' + hour + ':' + sha256Hex_(email).slice(0, 32), bcfg.rateLinkEmail)) return { ok: false, error: 'rate_limited' };
  return withLock_(function () {
    var db = db_(bcfg);
    var student = studentByAlumno_(db, studentId_(email));
    // Same answer whether or not the address belongs to a student: the page never reveals who is a student.
    if (student) { try { sendAccessLink_(bcfg, db, student, 'login'); } catch (e) { return { ok: false, error: 'unavailable' }; } }
    return { ok: true, status: 'sent_if_student' };
  });
}

/** Exchanges a one-time email link for a session token (30 days by default, revocable). */
function login_(cfg, bcfg, raw) {
  return withLock_(function () {
    var db = db_(bcfg);
    var now = Date.now();
    var link = checkAccess_(db, raw.token, 'link', now);
    if (!link) return { ok: false, error: 'invalid_token' };
    db.update('accesos', link, { usado: now });
    var token = issueAccess_(bcfg, db, link.alumno, 'session', now);
    return { ok: true, session: token, expiresAt: new Date(now + bcfg.sessionMs).toISOString() };
  });
}

function logout_(bcfg, raw) {
  return withLock_(function () {
    var db = db_(bcfg);
    var row = checkAccess_(db, raw.token, 'session', Date.now());
    if (row) db.update('accesos', row, { revocado: Date.now() });
    return { ok: true };
  });
}

function iso_(ms) { return ms === null || ms === '' || ms === undefined ? null : new Date(Number(ms)).toISOString(); }

/** Everything the student area shows. Never another student's data, never Stripe ids or tokens. */
function studentView_(cfg, bcfg, db, student) {
  var now = Date.now();
  var policy = policy_(bcfg);
  var ledger = deriveLedger_(movements_(db), policy);
  var subs = db.rows('suscripciones').filter(function (s) { return s.alumno === student.alumno; })
    .sort(function (a, b) { return Number(b.fin_periodo) - Number(a.fin_periodo); });
  var credits = studentCredits_(ledger, student.alumno);
  var bookings = studentBookings_(ledger, student.alumno);
  var plan = subs.length ? subs[0] : null;
  return {
    ok: true,
    student: { name: student.nombre || '', lang: student.idioma },
    plan: plan ? { plan: plan.plan, pendingPlan: plan.cambio_plan || null, changeAt: iso_(plan.cambio_en || null),
      canChangePlan: plan.estado === 'active' && !plan.cancela_al_final, amount: PLANS[plan.plan] ? PLANS[plan.plan].amount : null, currency: 'eur',
      intervalWeeks: PLANS[plan.plan] ? PLANS[plan.plan].intervalWeeks : null, status: plan.estado,
      renewsAt: plan.cancela_al_final || plan.estado === 'canceled' ? null : iso_(plan.fin_periodo),
      endsAt: plan.cancela_al_final ? iso_(plan.cancela_en || plan.fin_periodo) : plan.estado === 'canceled' ? iso_(plan.terminada_en) : null } : null,
    credits: sortCredits_(credits.filter(function (c) { return c.estado === 'disponible'; })).map(function (c, i) {
      var expired = c.expira !== null && now >= c.expira;
      return { n: i + 1, expiresAt: iso_(c.expira), carried: c.traslado === true, protected: c.protegido,
        status: expired ? (policy.enforced ? 'expired_review' : 'past_deadline') : 'available' };
    }),
    counts: {
      available: credits.filter(function (c) { return c.estado === 'disponible' && creditUsable_(c, now, now, policy); }).length,
      reserved: credits.filter(function (c) { return c.estado === 'reservado'; }).length,
      done: credits.filter(function (c) { return c.estado === 'consumido'; }).length,
      carried: credits.filter(function (c) { return c.estado === 'disponible' && c.traslado === true; }).length
    },
    bookings: bookings.filter(function (b) { return b.estado !== 'cancelada' || b.inicio > now - 30 * 86400000; })
      .sort(function (a, b) { return a.inicio - b.inicio; }).map(function (b) {
        return { id: b.id, start: iso_(b.inicio), end: iso_(b.fin), status: b.estado, reason: b.motivo,
          modality: 'in_person', location: bcfg.classLocation || '', canChange: b.estado === 'reservada' && now < b.inicio - bcfg.changeMs,
          changeUntil: iso_(b.inicio - bcfg.changeMs) };
      }),
    policy: { changeHours: Math.round(bcfg.changeMs / 3600000), carryMax: bcfg.carryMax, carryDays: Math.round(bcfg.carryMs / 86400000),
      enforced: policy.enforced, maxPerRequest: MAX_CLASSES_PER_REQUEST }
  };
}

function classCfg_(cfg, bcfg) {
  if (!bcfg.classAvailabilityId) return cfg;
  var c = {};
  Object.keys(cfg).forEach(function (k) { c[k] = cfg[k]; });
  c.availabilityCalendarId = bcfg.classAvailabilityId;
  return c;
}

function classSlots_(cfg, bcfg, nowMs) { return slotsFor_(classCfg_(cfg, bcfg), CLASS_MINUTES, nowMs); }

function classEvent_(cfg, bcfg, student, bookingId, startMs) {
  var es = student.idioma !== 'en';
  var resource = {
    id: 'lc' + bookingId,
    summary: (es ? 'Clase de música con ' : 'Music lesson with ') + (student.nombre || student.email),
    description: (es ? 'Clase individual presencial de 60 minutos (plan de clases de luisguinea.com).\nGestiona tus clases en ' :
      'One-to-one in-person 60-minute lesson (luisguinea.com lesson plan).\nManage your lessons at ') + bcfg.studentUrl,
    start: { dateTime: new Date(startMs).toISOString(), timeZone: cfg.timeZone },
    end: { dateTime: new Date(startMs + CLASS_MINUTES * 60000).toISOString(), timeZone: cfg.timeZone },
    transparency: 'opaque', guestsCanModify: false, guestsCanInviteOthers: false,
    attendees: [{ email: student.email, displayName: student.nombre || student.email }],
    extendedProperties: { private: { lgClass: bookingId, lgStudent: student.alumno } }
  };
  resource.location = bcfg.classLocation || (es ? 'Pendiente de acordar' : 'To be agreed');
  return resource;
}

function insertClassEvent_(cfg, resource) {
  try {
    return Calendar.Events.insert(resource, cfg.bookingCalendarId, { sendUpdates: 'all' });
  } catch (err) {
    var ev = getEventOrNull_(cfg, resource.id); // a lost response: reuse our own event
    var mine = ev && ev.status !== 'cancelled' && ev.extendedProperties && ev.extendedProperties.private &&
      ev.extendedProperties.private.lgClass === resource.extendedProperties.private.lgClass;
    if (!mine) throw err;
    return ev;
  }
}

/**
 * Books up to four classes in one request. All or nothing: every start is re-checked inside the lock against fresh
 * calendar data, each class gets its own credit (oldest first), and if Google fails half way the classes already
 * created in this request are removed and their credits released, so a failed booking never takes a credit.
 * A retry with the same requestId returns the same classes.
 */
function bookClasses_(cfg, bcfg, raw) {
  if (typeof raw.requestId !== 'string' || !REQUEST_ID_RE.test(raw.requestId)) return { ok: false, error: 'invalid_request' };
  if (!Array.isArray(raw.starts) || !raw.starts.length || raw.starts.length > MAX_CLASSES_PER_REQUEST) return { ok: false, error: 'invalid_request' };
  var starts = [];
  for (var i = 0; i < raw.starts.length; i++) {
    var ms = parseStart_(raw.starts[i]);
    if (ms === null || starts.indexOf(ms) !== -1) return { ok: false, error: 'invalid_start' };
    starts.push(ms);
  }
  starts.sort(function (a, b) { return a - b; });
  for (var k = 1; k < starts.length; k++) {
    if (starts[k] - starts[k - 1] < CLASS_MINUTES * 60000 + cfg.bufferMs) return { ok: false, error: 'overlap' };
  }
  return withLock_(function () {
    var db = db_(bcfg);
    var student = sessionStudent_(bcfg, db, raw.token);
    if (!student) return { ok: false, error: 'invalid_token' };
    var now = Date.now();
    var ids = starts.map(function (s, n) { return sha256Hex_('class:' + student.alumno + ':' + raw.requestId + ':' + n).slice(0, 32); });
    var policy = policy_(bcfg);
    var ledger = deriveLedger_(movements_(db), policy);
    // A retry (same requestId, same starts) returns the classes it already booked; the same id with other content is refused.
    var seen = ids.filter(function (id) { return ledger.bookings[id]; });
    if (seen.length) {
      var same = seen.length === ids.length && ids.every(function (id, n) {
        return ledger.bookings[id].pedido === starts[n] && ledger.bookings[id].total === starts.length;
      });
      return same ? studentView_(cfg, bcfg, db, student) : { ok: false, error: 'invalid_request' };
    }
    var picks = assignCredits_(studentCredits_(ledger, student.alumno), starts, now, policy);
    if (!picks) return { ok: false, error: 'no_credits' };
    var fresh = classSlots_(cfg, bcfg, now);
    for (var s = 0; s < starts.length; s++) {
      if (!fresh.some(function (f) { return f.start === starts[s]; })) return { ok: false, error: 'slot_unavailable' };
    }
    var created = [];
    try {
      for (var n = 0; n < starts.length; n++) {
        var resource = classEvent_(cfg, bcfg, student, ids[n], starts[n]);
        var ev = insertClassEvent_(cfg, resource);
        addMovement_(db, { id: 'reserve:' + ids[n], ts: Date.now(), tipo: 'reserve', alumno: student.alumno, credito: picks[n].id, reserva: ids[n],
          datos: { evento: resource.id, inicio: starts[n], fin: starts[n] + CLASS_MINUTES * 60000, pedido: starts[n], total: starts.length,
            enlace: calendarLink_(ev) } });
        created.push({ id: ids[n], evento: resource.id, credito: picks[n].id, inicio: starts[n] });
      }
    } catch (err) {
      created.forEach(function (c) {
        removeEvent_(cfg, { eventId: c.evento }, 'all');
        addMovement_(db, { id: 'release:' + c.id, tipo: 'release', alumno: student.alumno, credito: c.credito, reserva: c.id, datos: { motivo: 'fallo' } });
      });
      invalidateSlots_();
      return { ok: false, error: 'unavailable' };
    }
    invalidateSlots_();
    mailOwner_(cfg, db, 'classes:' + ids[0], 'Nuevas clases reservadas: ' + (student.nombre || student.email), [
      (student.nombre || student.email) + ' <' + student.email + '> ha reservado ' + created.length + (created.length === 1 ? ' clase' : ' clases') +
      ' con su plan (créditos ya descontados):', ''
    ].concat(created.map(function (c) { return '· ' + whenText_(cfg, c.inicio) + ' (60 min, presencial)'; }))
      .concat(['', 'Si cancelas una de estas clases en Google Calendar, el alumno recupera su crédito automáticamente.']));
    refreshPanel_(cfg, bcfg, db);
    var view = studentView_(cfg, bcfg, db, student);
    view.booked = created.length;
    return view;
  });
}

function ownBooking_(bcfg, db, student, bookingId) {
  if (typeof bookingId !== 'string' || !BOOKING_ID_RE.test(bookingId)) return null;
  var ledger = deriveLedger_(movements_(db), policy_(bcfg));
  var b = ledger.bookings[bookingId];
  return b && b.alumno === student.alumno ? { booking: b, ledger: ledger } : null; // another student's id looks unknown
}

function cancelClass_(cfg, bcfg, raw) {
  if (raw.confirm !== true) return { ok: false, error: 'confirmation_required' };
  return withLock_(function () {
    var db = db_(bcfg);
    var student = sessionStudent_(bcfg, db, raw.token);
    if (!student) return { ok: false, error: 'invalid_token' };
    var own = ownBooking_(bcfg, db, student, raw.booking);
    if (!own) return { ok: false, error: 'not_found' };
    var b = own.booking, now = Date.now();
    if (b.estado === 'cancelada') return studentView_(cfg, bcfg, db, student); // retry after a lost response
    if (b.estado !== 'reservada') return { ok: false, error: 'not_found' };
    if (now >= b.inicio - bcfg.changeMs) return { ok: false, error: 'too_late' };
    if (!removeEvent_(cfg, { eventId: b.evento }, 'all')) return { ok: false, error: 'unavailable' };
    addMovement_(db, { id: 'release:' + b.id, tipo: 'release', alumno: student.alumno, credito: b.credito, reserva: b.id, datos: { motivo: 'alumno' } });
    invalidateSlots_();
    mailOwner_(cfg, db, 'class-cancel:' + b.id, 'Clase cancelada por el alumno: ' + (student.nombre || student.email), [
      (student.nombre || student.email) + ' <' + student.email + '> ha cancelado su clase del ' + whenText_(cfg, b.inicio) +
      ' con más de ' + Math.round(bcfg.changeMs / 3600000) + ' horas de antelación. Recupera el crédito y el horario queda libre.'
    ]);
    refreshPanel_(cfg, bcfg, db);
    return studentView_(cfg, bcfg, db, student);
  });
}

function moveClass_(cfg, bcfg, raw) {
  var startMs = parseStart_(raw.start);
  if (startMs === null) return { ok: false, error: 'invalid_start' };
  return withLock_(function () {
    var db = db_(bcfg);
    var student = sessionStudent_(bcfg, db, raw.token);
    if (!student) return { ok: false, error: 'invalid_token' };
    var own = ownBooking_(bcfg, db, student, raw.booking);
    if (!own) return { ok: false, error: 'not_found' };
    var b = own.booking, now = Date.now();
    if (b.estado !== 'reservada') return { ok: false, error: 'not_found' };
    if (b.inicio === startMs) return studentView_(cfg, bcfg, db, student); // retry of a move that already happened
    if (now >= b.inicio - bcfg.changeMs) return { ok: false, error: 'too_late' };
    if (b.cambios >= cfg.maxReschedules) return { ok: false, error: 'reschedule_limit' };
    var credit = own.ledger.credits[b.credito];
    var policy = policy_(bcfg);
    if (policy.enforced && credit && credit.expira !== null && startMs >= credit.expira) return { ok: false, error: 'after_deadline' };
    if (!classSlots_(cfg, bcfg, now).some(function (s) { return s.start === startMs; })) return { ok: false, error: 'slot_unavailable' };
    var endMs = startMs + CLASS_MINUTES * 60000;
    try {
      Calendar.Events.patch({ start: { dateTime: new Date(startMs).toISOString(), timeZone: cfg.timeZone },
        end: { dateTime: new Date(endMs).toISOString(), timeZone: cfg.timeZone } }, cfg.bookingCalendarId, b.evento, { sendUpdates: 'all' });
    } catch (err) {
      var ev = getEventOrNull_(cfg, b.evento);
      if (!ev || !ev.start || Date.parse(ev.start.dateTime) !== startMs) return { ok: false, error: 'unavailable' };
    }
    addMovement_(db, { id: 'move:' + b.id + ':' + (b.cambios + 1), tipo: 'move', alumno: student.alumno, credito: b.credito, reserva: b.id,
      datos: { inicio: startMs, fin: endMs, desde: b.inicio, porAlumno: true } });
    invalidateSlots_();
    mailOwner_(cfg, db, 'class-move:' + b.id + ':' + (b.cambios + 1), 'Clase reprogramada: ' + (student.nombre || student.email), [
      (student.nombre || student.email) + ' <' + student.email + '> ha movido su clase del ' + whenText_(cfg, b.inicio) + ' al ' +
      whenText_(cfg, startMs) + '. El evento de Google Calendar ya está actualizado.'
    ]);
    refreshPanel_(cfg, bcfg, db);
    return studentView_(cfg, bcfg, db, student);
  });
}

function portal_(cfg, bcfg, raw) {
  var db = db_(bcfg);
  var student = sessionStudent_(bcfg, db, raw.token);
  if (!student) return { ok: false, error: 'invalid_token' };
  var rows = db.rows('alumnos').filter(function (r) { return r.alumno === student.alumno; });
  if (!rows.length) return { ok: false, error: 'not_found' };
  var params = { customer: rows[rows.length - 1].cliente_stripe, return_url: bcfg.studentUrl, locale: student.idioma === 'en' ? 'en' : 'es' };
  if (bcfg.portalConfig) params.configuration = bcfg.portalConfig;
  try {
    var s = stripe_(bcfg, 'post', '/billing_portal/sessions', params);
    return /^https:\/\/billing\.stripe\.com\//.test(s.url || '') ? { ok: true, url: s.url } : { ok: false, error: 'unavailable' };
  } catch (e) { return { ok: false, error: 'unavailable' }; }
}

// ---------- plan change at the end of the paid cycle ----------

function activeSubscription_(db, student) {
  var subs = db.rows('suscripciones').filter(function (s) { return s.alumno === student.alumno && s.estado === 'active'; })
    .sort(function (a, b) { return Number(b.fin_periodo) - Number(a.fin_periodo); });
  return subs[0] || null;
}

/**
 * Weekly <-> every-two-weeks, only from the next renewal. A Stripe subscription schedule keeps the current price until
 * the end of the paid cycle and starts the new one there, with proration_behavior "none" everywhere: verified with
 * Test Clocks to produce no charge now and one 148 EUR invoice at the renewal date (billing_reason
 * "subscription_update", accepted by syncInvoice_). Nothing is charged or credited by this call.
 */
function changePlan_(cfg, bcfg, raw) {
  if (!PLANS.hasOwnProperty(raw.plan)) return { ok: false, error: 'invalid_plan' };
  if (raw.confirm !== true) return { ok: false, error: 'confirmation_required' };
  return withLock_(function () {
    var db = db_(bcfg);
    var student = sessionStudent_(bcfg, db, raw.token);
    if (!student) return { ok: false, error: 'invalid_token' };
    var row = activeSubscription_(db, student);
    if (!row) return { ok: false, error: 'not_active' };
    var sub = stripe_(bcfg, 'get', '/subscriptions/' + encodeURIComponent(row.suscripcion));
    var current = planForPrice_(bcfg, subscriptionPrice_(sub));
    if (sub.status !== 'active' || sub.cancel_at_period_end || sub.cancel_at) return { ok: false, error: 'not_active' };
    // Always start from a clean subscription: releasing a schedule changes neither the price nor the billing date.
    if (sub.schedule) stripe_(bcfg, 'post', '/subscription_schedules/' + encodeURIComponent(idOf_(sub.schedule)) + '/release', {});
    if (current !== raw.plan) {
      var sch = stripe_(bcfg, 'post', '/subscription_schedules', { from_subscription: sub.id });
      stripe_(bcfg, 'post', '/subscription_schedules/' + encodeURIComponent(sch.id), {
        end_behavior: 'release', proration_behavior: 'none',
        phases: {
          0: { items: { 0: { price: bcfg.prices[current], quantity: 1 } }, start_date: sch.phases[0].start_date, end_date: sub.current_period_end,
            proration_behavior: 'none' },
          1: { items: { 0: { price: bcfg.prices[raw.plan], quantity: 1 } }, iterations: 1, proration_behavior: 'none',
            metadata: { plan: raw.plan, lang: student.idioma === 'en' ? 'en' : 'es' } }
        }
      });
    }
    syncSubscription_(cfg, bcfg, db, sub.id);
    var at = sub.current_period_end * 1000;
    if (current !== raw.plan) {
      mailOwner_(cfg, db, 'planchange:' + sub.id + ':' + raw.plan + ':' + at, 'Cambio de plan programado: ' + (student.nombre || student.email), [
        (student.nombre || student.email) + ' <' + student.email + '> pasará del plan ' + planLabel_(current) + ' al ' + planLabel_(raw.plan) +
        ' el ' + whenText_(cfg, at) + ', al terminar su periodo pagado. No se cobra nada ahora ni hay prorrateo.'
      ]);
    }
    refreshPanel_(cfg, bcfg, db);
    return studentView_(cfg, bcfg, db, student);
  });
}

function undoPlanChange_(cfg, bcfg, raw) {
  return changePlan_(cfg, bcfg, { token: raw.token, confirm: true, plan: (function () {
    var db = db_(bcfg);
    var st = sessionStudent_(bcfg, db, raw.token);
    var row = st && activeSubscription_(db, st);
    return row ? row.plan : 'none';
  })() });
}

// ---------- entry point from doPost (Code.gs) ----------

function billingPost_(raw) {
  resetDb_();
  var op = raw.op;
  if (!onlyFields_(raw, BILLING_OPS[op])) return { ok: false, error: 'invalid_request' };
  var cfg = loadConfig_();
  var bcfg = billingConfig_();
  switch (op) {
    case 'stripe_event': return stripeEvent_(cfg, bcfg, raw);
    case 'checkout': return createCheckout_(cfg, bcfg, raw);
    case 'checkout_status': return checkoutStatus_(cfg, bcfg, raw);
    case 'stu_link': return requestLink_(cfg, bcfg, raw);
  }
  if (typeof raw.token !== 'string' || !ACCESS_TOKEN_RE.test(raw.token)) return { ok: false, error: 'invalid_token' };
  switch (op) {
    case 'stu_login': return login_(cfg, bcfg, raw);
    case 'stu_logout': return logout_(bcfg, raw);
    case 'stu_view':
      var db = db_(bcfg);
      var st = sessionStudent_(bcfg, db, raw.token);
      return st ? studentView_(cfg, bcfg, db, st) : { ok: false, error: 'invalid_token' };
    case 'stu_slots':
      var db2 = db_(bcfg);
      if (!sessionStudent_(bcfg, db2, raw.token)) return { ok: false, error: 'invalid_token' };
      return { ok: true, timeZone: cfg.timeZone, slots: classSlots_(cfg, bcfg, Date.now()).map(function (s) {
        return { start: new Date(s.start).toISOString(), end: new Date(s.end).toISOString() };
      }) };
    case 'stu_book': return bookClasses_(cfg, bcfg, raw);
    case 'stu_cancel': return cancelClass_(cfg, bcfg, raw);
    case 'stu_move': return moveClass_(cfg, bcfg, raw);
    case 'stu_portal': return portal_(cfg, bcfg, raw);
    case 'stu_plan': return changePlan_(cfg, bcfg, raw);
    case 'stu_plan_undo': return undoPlanChange_(cfg, bcfg, raw);
  }
  return { ok: false, error: 'invalid_request' };
}

// ---------- hourly maintenance (time-driven trigger) ----------

/**
 * Run by a time-driven trigger every hour (installBillingTriggers). Inside the lock:
 *   1. reconciliation with Stripe: subscriptions and paid invoices whose webhook never arrived;
 *   2. classes: a class whose Calendar event Luis deleted gives its credit back (no deadline); a class moved in Calendar
 *      by Luis follows the event; a class that ended CONSUME_GRACE_HOURS ago counts as done;
 *   3. rollover of finished cycles (bookkeeping; deadlines only bind with CREDIT_POLICY_ENFORCED);
 *   4. reminders and deadline warnings to students; 5. adjustments typed by Luis in the "ajustes" tab; 6. the panel.
 */
function billingHourly() {
  resetDb_();
  var cfg = loadConfig_();
  var bcfg = billingConfig_();
  return withLock_(function () {
    var db = db_(bcfg);
    var report = { reconciled: 0, consumed: 0, teacherCancelled: 0, rolled: 0, reminders: 0, warnings: 0, adjustments: 0 };
    try { report.reconciled = reconcile_(cfg, bcfg, db); } catch (e) { report.reconcileError = String(e.message); }
    classesMaintenance_(cfg, bcfg, db, report);
    report.rolled = rollover_(bcfg, db, Date.now());
    notices_(cfg, bcfg, db, report);
    report.adjustments = processAdjustments_(cfg, bcfg, db);
    refreshPanel_(cfg, bcfg, db);
    return { ok: true, report: report };
  });
}

function reconcile_(cfg, bcfg, db) {
  var n = 0;
  // Subscriptions to check: every one Stripe lists with our prices, plus every one already known to the ledger
  // (the list is capped at 100 and leaves out some, such as those on Test Clocks).
  var ids = {};
  var list = stripe_(bcfg, 'get', '/subscriptions', { status: 'all', limit: 100 });
  (list.data || []).forEach(function (sub) { if (planForPrice_(bcfg, subscriptionPrice_(sub))) ids[sub.id] = true; });
  db.rows('suscripciones').forEach(function (r) {
    var ended = r.estado === 'canceled' && Number(r.terminada_en) && Number(r.terminada_en) < Date.now() - 60 * 86400000;
    if (!ended) ids[r.suscripcion] = true;
  });
  Object.keys(ids).forEach(function (subId) {
    var snap = syncSubscription_(cfg, bcfg, db, subId);
    if (!snap) return;
    var invs = stripe_(bcfg, 'get', '/invoices', { subscription: subId, status: 'paid', limit: 10 });
    (invs.data || []).forEach(function (inv) {
      if (!db.find('movimientos', 'id', 'grant:' + inv.id + ':1') && !db.find('incidencias', 'id', 'invoice-reason:' + inv.id)) {
        n += syncInvoice_(cfg, bcfg, db, inv.id).granted;
      }
    });
  });
  return n;
}

function classesMaintenance_(cfg, bcfg, db, report) {
  var now = Date.now();
  var ledger = deriveLedger_(movements_(db), policy_(bcfg));
  Object.keys(ledger.bookings).forEach(function (id) {
    var b = ledger.bookings[id];
    if (b.estado !== 'reservada') return;
    var ev = getEventOrNull_(cfg, b.evento);
    var student = studentByAlumno_(db, b.alumno);
    if (!ev || ev.status === 'cancelled') {
      // Luis cancelled the class (deleted the event): the student keeps the right to it, with no deadline.
      addMovement_(db, { id: 'release:' + id, tipo: 'release', alumno: b.alumno, credito: b.credito, reserva: id, datos: { motivo: 'profesor' } });
      report.teacherCancelled++;
      var es = !student || student.idioma !== 'en';
      mailStudent_(db, 'tcancel:' + id, student, es ? 'Tu clase ha sido cancelada: conservas la clase' : 'Your lesson was cancelled: you keep it',
        es ? 'Luis ha tenido que cancelar tu clase del ' + whenText_(cfg, b.inicio) + ' (hora de Madrid). La clase vuelve a tu saldo, sin fecha límite, para que la reserves cuando te venga bien:\n' + bcfg.studentUrl
          : 'Luis had to cancel your lesson on ' + whenText_(cfg, b.inicio) + ' (Madrid time). The lesson is back in your balance, with no deadline, so you can book it whenever suits you:\n' + bcfg.studentUrl);
      return;
    }
    var evStart = ev.start && Date.parse(ev.start.dateTime);
    var evEnd = ev.end && Date.parse(ev.end.dateTime);
    if (isFinite(evStart) && isFinite(evEnd) && (evStart !== b.inicio || evEnd !== b.fin)) {
      addMovement_(db, { id: 'move:' + id + ':cal:' + evStart, tipo: 'move', alumno: b.alumno, credito: b.credito, reserva: id,
        datos: { inicio: evStart, fin: evEnd, desde: b.inicio, porAlumno: false } });
      b.inicio = evStart; b.fin = evEnd;
    }
    if (now >= b.fin + bcfg.graceMs) {
      addMovement_(db, { id: 'consume:' + id, tipo: 'consume', alumno: b.alumno, credito: b.credito, reserva: id, datos: { regla: 'fin+gracia' } });
      report.consumed++;
    }
  });
}

/** Records, once per finished cycle, which unused credits move on (oldest first, at most CARRY_MAX). Pure bookkeeping. */
function rollover_(bcfg, db, nowMs) {
  var policy = policy_(bcfg);
  var ledger = deriveLedger_(movements_(db), policy);
  var byInvoice = {};
  Object.keys(ledger.credits).forEach(function (k) {
    var c = ledger.credits[k];
    if (c.origen !== 'stripe' || c.fin > nowMs) return;
    (byInvoice[c.factura] = byInvoice[c.factura] || []).push(c);
  });
  var n = 0;
  Object.keys(byInvoice).forEach(function (inv) {
    var open = byInvoice[inv].filter(function (c) { return c.estado === 'disponible' && c.traslado === null && !c.protegido; })
      .sort(function (a, b) { return Number(a.id.split(':').pop()) - Number(b.id.split(':').pop()); });
    var already = byInvoice[inv].filter(function (c) { return c.traslado === true; }).length;
    open.forEach(function (c) {
      var carry = already < policy.carryMax;
      if (carry) already++;
      if (addMovement_(db, { id: 'rollover:' + c.id, ts: nowMs, tipo: 'rollover', alumno: c.alumno, credito: c.id, datos: { traslado: carry } })) n++;
    });
  });
  return n;
}

function notices_(cfg, bcfg, db, report) {
  var now = Date.now();
  var policy = policy_(bcfg);
  var ledger = deriveLedger_(movements_(db), policy);
  Object.keys(ledger.bookings).forEach(function (id) {
    var b = ledger.bookings[id];
    if (b.estado !== 'reservada' || b.inicio <= now || b.inicio - now > bcfg.remindMs) return;
    var st = studentByAlumno_(db, b.alumno);
    var es = !st || st.idioma !== 'en';
    var key = 'remind:' + id + ':' + b.inicio;
    if (db.find('avisos', 'clave', key)) return;
    mailStudent_(db, key, st, es ? 'Recordatorio: tu clase con Luis Guinea' : 'Reminder: your lesson with Luis Guinea',
      (es ? 'Te recordamos tu clase presencial de 60 minutos el ' + whenText_(cfg, b.inicio) + ' (hora de Madrid)' :
        'This is a reminder of your in-person 60-minute lesson on ' + whenText_(cfg, b.inicio) + ' (Madrid time)') +
      (bcfg.classLocation ? (es ? ' en ' : ' at ') + bcfg.classLocation : '') + '.\n\n' +
      (es ? 'Si no puedes venir, escribe a Luis cuanto antes respondiendo a la invitación de Google Calendar.' :
        'If you cannot come, please tell Luis as soon as possible by replying to the Google Calendar invitation.'));
    report.reminders++;
  });
  // Renewal reminder 3 days before each automatic charge (consumer transparency), once per period.
  db.rows('suscripciones').forEach(function (sub) {
    var at = Number(sub.fin_periodo);
    if (sub.estado !== 'active' || sub.cancela_al_final || !at || at <= now || at - now > 3 * 86400000) return;
    var st = studentByAlumno_(db, sub.alumno);
    var es = !st || st.idioma !== 'en';
    var plan = sub.cambio_plan || sub.plan;
    var weeks = PLANS[plan] ? PLANS[plan].intervalWeeks : '';
    mailStudent_(db, 'renew-notice:' + sub.suscripcion + ':' + at, st, es ? 'Tu plan de clases se renueva pronto' : 'Your lesson plan renews soon',
      es ? 'El ' + whenText_(cfg, at) + ' (hora de Madrid) se renovará tu plan de clases: 148 € por 4 clases para las próximas ' + weeks +
          ' semanas. No tienes que hacer nada.\n\nSi no quieres renovar, puedes cancelarlo antes de esa fecha en tu área de alumno, apartado Facturación:\n' +
          bcfg.studentUrl + '\nLas clases ya pagadas se conservan.'
        : 'On ' + whenText_(cfg, at) + ' (Madrid time) your lesson plan renews: €148 for 4 lessons for the next ' + weeks +
          ' weeks. You do not need to do anything.\n\nIf you do not want to renew, you can cancel before that date in your student area, Billing section:\n' +
          bcfg.studentUrl + '\nLessons already paid for are kept.');
  });
  if (!policy.enforced) return; // deadlines are informative until the policy is approved: no warning about them
  Object.keys(ledger.credits).forEach(function (k) {
    var c = ledger.credits[k];
    if (c.estado !== 'disponible' || c.expira === null || c.expira <= now || c.expira - now > bcfg.warnMs) return;
    var st = studentByAlumno_(db, c.alumno);
    var es = !st || st.idioma !== 'en';
    mailStudent_(db, 'warn:' + c.id + ':' + c.expira, st, es ? 'Tienes clases pendientes de reservar' : 'You have lessons left to book',
      es ? 'Tienes al menos una clase pagada sin reservar que debería usarse antes del ' + whenText_(cfg, c.expira) +
        ' (hora de Madrid). Resérvala en tu área de alumno:\n' + bcfg.studentUrl + '\n\nSi no encuentras un horario adecuado, escribe a Luis.'
        : 'You have at least one paid lesson left to book that should be used before ' + whenText_(cfg, c.expira) +
        ' (Madrid time). Book it in your student area:\n' + bcfg.studentUrl + '\n\nIf you cannot find a suitable time, write to Luis.');
    report.warnings++;
  });
}

/**
 * Adjustments typed by Luis in the "ajustes" tab (one per row, processed once):
 *   anular   credito        voids an unused credit (e.g. after a refund)
 *   ampliar  credito, valor  new deadline (yyyy-mm-dd, end of that day in Madrid)
 *   conceder alumno, valor   grants `valor` extra credits with no deadline (alumno = email)
 *   revocar  alumno          closes every open session of that student
 */
function processAdjustments_(cfg, bcfg, db) {
  var n = 0;
  db.rows('ajustes').forEach(function (row) {
    if (row.estado || !row.tipo) return;
    if (!row.id) db.update('ajustes', row, { id: randomHex_(16) });
    var result = applyAdjustment_(cfg, bcfg, db, row);
    db.update('ajustes', row, { estado: result, procesado: Date.now() });
    n++;
  });
  return n;
}

function applyAdjustment_(cfg, bcfg, db, row) {
  var ledger = deriveLedger_(movements_(db), policy_(bcfg));
  var tipo = String(row.tipo).trim().toLowerCase();
  var email = String(row.alumno || '').trim().toLowerCase();
  var alumno = email ? studentId_(email) : '';
  var c = row.credito ? ledger.credits[String(row.credito).trim()] : null;
  var motivo = cleanText_(String(row.motivo || ''), 300, false) || '';
  if (tipo === 'anular') {
    if (!c) return 'error: crédito desconocido';
    if (c.estado !== 'disponible') return 'error: el crédito no está disponible (' + c.estado + ')';
    addMovement_(db, { id: 'void:' + c.id + ':' + row.id, tipo: 'void', alumno: c.alumno, credito: c.id, datos: { motivo: motivo, ajuste: row.id } });
    return 'hecho';
  }
  if (tipo === 'ampliar') {
    if (!c) return 'error: crédito desconocido';
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(row.valor).trim());
    if (!m) return 'error: valor debe ser una fecha aaaa-mm-dd';
    var until = Date.parse(m[0] + 'T23:59:00Z');
    addMovement_(db, { id: 'extend:' + c.id + ':' + row.id, tipo: 'extend', alumno: c.alumno, credito: c.id, datos: { hasta: until, motivo: motivo, ajuste: row.id } });
    return 'hecho';
  }
  if (tipo === 'conceder') {
    var count = Number(row.valor);
    if (!studentByAlumno_(db, alumno)) return 'error: alumno desconocido (usa su correo)';
    if (!(count >= 1 && count <= 8 && Math.floor(count) === count)) return 'error: valor debe ser un número de 1 a 8';
    for (var i = 1; i <= count; i++) {
      addMovement_(db, { id: 'grant:adj:' + row.id + ':' + i, tipo: 'grant', alumno: alumno, credito: 'adj:' + row.id + ':' + i,
        datos: { origen: 'ajuste', sinPlazo: true, inicio: Date.now(), fin: Date.now(), motivo: motivo } });
    }
    return 'hecho';
  }
  if (tipo === 'justificar') {
    if (!c) return 'error: crédito desconocido (columna credito, ver "CLASES RECIENTES" en el panel)';
    if (c.estado !== 'consumido') return 'error: esa clase no consta como realizada (' + c.estado + ')';
    addMovement_(db, { id: 'restore:' + c.reserva, tipo: 'restore', alumno: c.alumno, credito: c.id, reserva: c.reserva, datos: { motivo: motivo, ajuste: row.id } });
    return 'hecho';
  }
  if (tipo === 'anonimizar') {
    // Right to erasure: personal data leave the Sheet; the pseudonymous id stays for the accounting record.
    if (!alumno) return 'error: falta el correo del alumno';
    var rowsA = db.rows('alumnos').filter(function (a) { return a.alumno === alumno; });
    if (!rowsA.length) return 'error: alumno desconocido';
    rowsA.forEach(function (a) { db.update('alumnos', a, { email: '[suprimido]', nombre: '[suprimido]' }); });
    db.rows('accesos').forEach(function (a) { if (a.alumno === alumno && !a.revocado) db.update('accesos', a, { revocado: Date.now() }); });
    db.update('ajustes', row, { alumno: '[suprimido]' });
    return 'hecho: borra también el cliente en Stripe si ya no hay obligación de conservarlo';
  }
  if (tipo === 'revocar') {
    if (!alumno) return 'error: falta el correo del alumno';
    db.rows('accesos').forEach(function (a) { if (a.alumno === alumno && !a.revocado) db.update('accesos', a, { revocado: Date.now() }); });
    return 'hecho';
  }
  return 'error: tipo desconocido (anular, ampliar, conceder, justificar, revocar, anonimizar)';
}

// ---------- admin panel (tab "panel" of the same private Sheet) ----------

function refreshPanel_(cfg, bcfg, db) {
  try {
    var now = Date.now();
    var policy = policy_(bcfg);
    var ledger = deriveLedger_(movements_(db), policy);
    var students = {};
    db.rows('alumnos').forEach(function (s) { students[s.alumno] = s; });
    var subs = db.rows('suscripciones');
    var out = [['Panel de clases · actualizado ' + whenText_(cfg, now) + ' (Madrid) · política de plazos: ' +
      (policy.enforced ? 'APLICADA' : 'solo informativa'), '', '', '', '', '', '', '']];
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['ALUMNOS', 'Correo', 'Plan', 'Estado', 'Próxima renovación / fin', 'Disponibles', 'Reservadas', 'Fuera de plazo']);
    subs.slice().sort(function (a, b) { return String(a.estado).localeCompare(String(b.estado)); }).forEach(function (s) {
      var st = students[s.alumno] || {};
      var mine = studentCredits_(ledger, s.alumno);
      out.push([st.nombre || '', st.email || '', planLabel_(s.plan) + (s.cambio_plan ? ' → ' + planLabel_(s.cambio_plan) : ''),
        s.estado + (s.cancela_al_final ? ' (cancela al final)' : ''),
        whenText_(cfg, Number(s.cancela_al_final ? (s.cancela_en || s.fin_periodo) : s.fin_periodo)),
        mine.filter(function (c) { return c.estado === 'disponible'; }).length,
        mine.filter(function (c) { return c.estado === 'reservado'; }).length,
        mine.filter(function (c) { return c.estado === 'disponible' && c.expira !== null && now >= c.expira; }).length]);
    });
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['PRÓXIMAS CLASES', 'Correo', 'Inicio (Madrid)', 'Crédito', 'Trasladado', '', '', '']);
    Object.keys(ledger.bookings).map(function (k) { return ledger.bookings[k]; })
      .filter(function (b) { return b.estado === 'reservada'; }).sort(function (a, b) { return a.inicio - b.inicio; })
      .forEach(function (b) {
        var st = students[b.alumno] || {};
        var c = ledger.credits[b.credito] || {};
        out.push([st.nombre || '', st.email || '', whenText_(cfg, b.inicio), b.credito, c.traslado ? 'sí' : '', '', '', '']);
      });
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['CRÉDITOS SIN USAR', 'Correo', 'Crédito', 'Fecha límite', 'Trasladado', 'Sin plazo', 'Estado', '']);
    Object.keys(ledger.credits).map(function (k) { return ledger.credits[k]; }).filter(function (c) { return c.estado === 'disponible'; })
      .sort(function (a, b) { return (a.expira === null ? Infinity : a.expira) - (b.expira === null ? Infinity : b.expira); })
      .forEach(function (c) {
        var st = students[c.alumno] || {};
        out.push([st.nombre || '', st.email || '', c.id, c.expira === null ? '' : whenText_(cfg, c.expira), c.traslado ? 'sí' : '',
          c.protegido ? 'sí' : '', c.expira !== null && now >= c.expira ? (policy.enforced ? 'vencido: revisar' : 'fuera de plazo (informativo)') : 'disponible', '']);
      });
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['CLASES RECIENTES (30 días)', 'Correo', 'Inicio (Madrid)', 'Crédito', 'Estado', 'Motivo', '', '']);
    Object.keys(ledger.bookings).map(function (k) { return ledger.bookings[k]; })
      .filter(function (b) { return b.estado !== 'reservada' && b.inicio > now - 30 * 86400000 && b.inicio <= now; })
      .sort(function (a, b) { return b.inicio - a.inicio; })
      .forEach(function (b) {
        var st = students[b.alumno] || {};
        out.push([st.nombre || '', st.email || '', whenText_(cfg, b.inicio), b.credito, b.estado, b.motivo || '', '', '']);
      });
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['REEMBOLSOS', 'Correo', 'Fecha', 'Factura', 'Importe', 'Total', '', '']);
    movements_(db).filter(function (m) { return m.tipo === 'refund'; }).forEach(function (m) {
      var st = students[m.alumno] || {};
      out.push([st.nombre || '', st.email || '', whenText_(cfg, m.ts), m.datos.factura, (m.datos.reembolsado / 100).toFixed(2) + ' €', m.datos.total ? 'sí' : 'parcial', '', '']);
    });
    out.push(['', '', '', '', '', '', '', '']);
    out.push(['INCIDENCIAS ABIERTAS', 'Tipo', 'Fecha', 'Detalle', '', '', '', '']);
    db.rows('incidencias').filter(function (i) { return i.estado !== 'cerrada'; }).forEach(function (i) {
      var st = students[i.alumno] || {};
      out.push([st.email || '', i.tipo, whenText_(cfg, Number(i.ts)), i.detalle, '', '', '', '']);
    });
    var sh = db.sheet('panel');
    sh.clearContents();
    sh.getRange(1, 1, out.length, 8).setValues(out);
  } catch (e) { /* the panel is a convenience: never fail a request because of it */ }
}

// ---------- setup helpers (run by hand from the editor) ----------

/** Read-only: checks the Stripe key, the two prices (148 €, every 4 and 8 weeks), the Sheet and the relay secret. */
function checkBillingSetup() {
  resetDb_();
  var bcfg = billingConfig_();
  var report = { mode: bcfg.mode, prices: {}, sheet: false, relaySecret: !!bcfg.relaySecret, checkoutEnabled: bcfg.checkoutEnabled,
    policyEnforced: bcfg.policyEnforced };
  Object.keys(PLANS).forEach(function (k) {
    var pr = stripe_(bcfg, 'get', '/prices/' + bcfg.prices[k]);
    var ok = pr.active && pr.unit_amount === PLANS[k].amount && pr.currency === 'eur' && pr.type === 'recurring' &&
      pr.recurring.interval === 'week' && pr.recurring.interval_count === PLANS[k].intervalWeeks && pr.livemode === (bcfg.mode === 'live');
    report.prices[k] = ok ? 'ok' : 'MAL: revisa importe, moneda e intervalo';
  });
  var db = db_(bcfg);
  Object.keys(TABLES).forEach(function (t) { db.sheet(t); });
  db.sheet('panel');
  report.sheet = true;
  Logger.log(JSON.stringify(report, null, 2));
  return report;
}

/** Installs the hourly maintenance trigger once (needs the script.scriptapp permission). */
function installBillingTriggers() {
  var handlers = ScriptApp.getProjectTriggers().map(function (t) { return t.getHandlerFunction(); });
  if (handlers.indexOf('billingHourly') === -1) ScriptApp.newTrigger('billingHourly').timeBased().everyHours(1).create();
  if (handlers.indexOf('billingWeeklyBackup') === -1) ScriptApp.newTrigger('billingWeeklyBackup').timeBased().everyWeeks(1).create();
}

/**
 * Weekly copy of the whole ledger Sheet (same Drive, same owner, private like the original), so a mistaken edit or
 * deletion can be undone beyond Sheets' own version history. Needs no permission beyond "spreadsheets".
 */
function billingWeeklyBackup() {
  resetDb_();
  var bcfg = billingConfig_();
  var ss = SpreadsheetApp.openById(bcfg.spreadsheetId);
  var name = 'Copia de seguridad clases ' + Utilities.formatDate(new Date(), 'Europe/Madrid', 'yyyy-MM-dd');
  ss.copy(name);
  return name;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { deriveLedger_: deriveLedger_, assignCredits_: assignCredits_ };
}
