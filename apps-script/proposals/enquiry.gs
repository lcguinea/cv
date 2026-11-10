/**
 * PROPOSAL, NOT DEPLOYED (mission 02, 2026-11-10): op "enquiry" for the form of https://luisguinea.com/formacion/.
 *
 * Why here: the booking web app already runs as Luis with MailApp permission (script.send_mail), costs nothing and
 * accepts the same simple text/plain POST. No new service, account or dependency.
 *
 * What it does: validates the enquiry strictly, rate-limits it and sends ONE plain-text email to Luis, with the visitor
 * as Reply-To. It never writes to the visitor, so the form cannot be used to make Luis's account email third parties,
 * and it stores nothing (no Script Properties, no Sheets): the email is the only record.
 *
 * To activate it (Luis, by hand, after approval):
 *   1. Copy this file into the Apps Script project next to Code.gs (or `clasp push` with it moved to apps-script/).
 *   2. In Code.gs, doPost, just before `var v = validateBooking_(raw);`, add:
 *        if (op === 'enquiry') return json_(handleEnquiry_(raw, Date.now()));
 *   3. Optional Script Property ENQUIRY_TO (defaults to the account that deploys the web app).
 *   4. Deploy a new version of the existing web app (same /exec URL).
 *   5. Set ENQUIRY_ENDPOINT in tools/formacion_content.py to that /exec URL and run python3 tools/build_formacion.py.
 * Tested with mocked Google services in tests/support/enquiry_scenarios.js (tests/test_formacion.py).
 */
var ENQUIRY_FIELDS = ['op', 'area', 'level', 'format', 'name', 'email', 'message', 'website', 'lang'];
var ENQUIRY_AREAS = ['piano', 'composicion', 'produccion', 'armonia', 'carrera', 'mentoria', 'nose'];
var ENQUIRY_LEVELS = ['', 'inicio', 'base', 'avanzado'];
var ENQUIRY_FORMATS = ['', 'presencial', 'online', 'mentoria', 'igual'];
var ENQUIRY_MESSAGE_MAX = 1000;
var ENQUIRY_RATE_GLOBAL_HOUR = 20;
var ENQUIRY_RATE_PER_EMAIL_HOUR = 2;
var ENQUIRY_LABELS = {
  area: { piano: 'Piano', composicion: 'Composición y songwriting', produccion: 'Producción musical',
    armonia: 'Armonía y teoría aplicada', carrera: 'Carrera artística y negocio musical', mentoria: 'Mentoría', nose: 'Aún no lo sabe' },
  level: { '': 'Sin indicar', inicio: 'Empieza desde cero', base: 'Tiene algo de base', avanzado: 'Nivel avanzado' },
  format: { '': 'Sin indicar', presencial: 'Presencial en Valencia', online: 'Online', mentoria: 'Mentoría', igual: 'Le da igual' }
};

/** Multi-line text: keeps line breaks, rejects other control and bidirectional characters. */
function cleanMessage_(value) {
  if (value === undefined || value === '') return '';
  if (typeof value !== 'string') return null;
  var v = value.replace(/\r\n?/g, '\n').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  if (CONTROL_RE.test(v.replace(/\n/g, ' '))) return null;
  if (v.length > ENQUIRY_MESSAGE_MAX) return null;
  return v;
}

/** Returns {ok:true, value} or {ok:false, error}. Same strictness as validateBooking_: types, sizes, known fields. */
function validateEnquiry_(raw) {
  if (!raw || typeof raw !== 'object' || !onlyFields_(raw, ENQUIRY_FIELDS)) return { ok: false, error: 'invalid_request' };
  var pick = function (value, list) { var v = value === undefined ? '' : value; return list.indexOf(v) === -1 ? null : v; };
  var area = pick(raw.area, ENQUIRY_AREAS);
  if (!area) return { ok: false, error: 'invalid_area' };
  var level = pick(raw.level, ENQUIRY_LEVELS), format = pick(raw.format, ENQUIRY_FORMATS);
  if (level === null || format === null) return { ok: false, error: 'invalid_request' };
  var name = cleanText_(raw.name, NAME_MAX, true);
  if (!name) return { ok: false, error: 'invalid_name' };
  var email = typeof raw.email === 'string' ? raw.email.trim() : '';
  if (!email || email.length > EMAIL_MAX || !EMAIL_RE.test(email)) return { ok: false, error: 'invalid_email' };
  var message = cleanMessage_(raw.message);
  if (message === null) return { ok: false, error: 'invalid_message' };
  if (raw.website !== undefined && typeof raw.website !== 'string') return { ok: false, error: 'invalid_request' };
  var lang = raw.lang === 'en' ? 'en' : 'es';
  return { ok: true, value: { area: area, level: level, format: format, name: name, email: email, message: message,
    website: raw.website || '', lang: lang } };
}

function enquiryLimit_(email, nowMs) {
  var cache = CacheService.getScriptCache(), hour = Math.floor(nowMs / 3600000);
  var keys = { global: 'eq:g:' + hour, email: 'eq:e:' + hour + ':' + sha256Hex_(email.toLowerCase()).slice(0, 32) };
  var over = Number(cache.get(keys.global) || 0) >= ENQUIRY_RATE_GLOBAL_HOUR ||
    Number(cache.get(keys.email) || 0) >= ENQUIRY_RATE_PER_EMAIL_HOUR;
  return { over: over, count: function () {
    [keys.global, keys.email].forEach(function (k) {
      try { cache.put(k, String(Number(cache.get(k) || 0) + 1), 3700); } catch (e) { /* best effort */ }
    });
  } };
}

function enquiryRecipient_() {
  var configured = PropertiesService.getScriptProperties().getProperty('ENQUIRY_TO');
  if (configured && EMAIL_RE.test(configured)) return configured;
  return Session.getEffectiveUser().getEmail();
}

/** Entry point for op "enquiry". Never echoes the visitor's data back and never emails the visitor. */
function handleEnquiry_(raw, nowMs) {
  var v = validateEnquiry_(raw);
  if (!v.ok) return { ok: false, error: v.error };
  var e = v.value;
  if (e.website) return { ok: true }; // honeypot: look successful, send nothing
  var limit = enquiryLimit_(e.email, nowMs);
  if (limit.over) return { ok: false, error: 'rate_limited' };
  if (MailApp.getRemainingDailyQuota() < 1) return { ok: false, error: 'unavailable' };
  var body = [
    'Nueva consulta desde luisguinea.com/formacion/', '',
    'Área: ' + ENQUIRY_LABELS.area[e.area],
    'Nivel: ' + ENQUIRY_LABELS.level[e.level],
    'Modalidad: ' + ENQUIRY_LABELS.format[e.format],
    'Idioma de la página: ' + (e.lang === 'en' ? 'inglés' : 'español'), '',
    'Nombre: ' + e.name,
    'Correo: ' + e.email, '',
    'Mensaje:', e.message || '(sin mensaje)', '',
    'Responde a este correo para contestar directamente.'
  ].join('\n');
  try {
    MailApp.sendEmail({ to: enquiryRecipient_(), replyTo: e.email, name: 'luisguinea.com',
      subject: 'Consulta de formación: ' + ENQUIRY_LABELS.area[e.area] + ' · ' + e.name, body: body });
  } catch (err) {
    return { ok: false, error: 'unavailable' };
  }
  limit.count();
  return { ok: true };
}
