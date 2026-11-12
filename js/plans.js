// Class plans on /formacion/ (#planes): sends the chosen plan and the two consents to the Apps Script web app
// (op "checkout", a simple text/plain POST like /agenda/) and opens the Stripe Checkout page it returns. The browser
// never decides whether anybody has paid: the backend grants lessons only after Stripe confirms the payment.
(function () {
  'use strict';
  var form = document.getElementById('plans-form');
  if (!form) return;
  var ENDPOINT_RE = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/;
  // Local development only (tools/billing_dev_server.js): a page served from 127.0.0.1 may call a backend on 127.0.0.1.
  var LOCAL_RE = /^http:\/\/127\.0\.0\.1:\d+\/exec$/;
  var endpoint = form.getAttribute('data-endpoint') || '';
  if (!(ENDPOINT_RE.test(endpoint) || (location.hostname === '127.0.0.1' && LOCAL_RE.test(endpoint)))) endpoint = '';
  var $ = function (id) { return document.getElementById(id); };
  var error = $('plans-error'), status = $('plans-status');
  var submit = form.querySelector('button[type="submit"]');
  var requestId = null, lastKey = '', busy = false;
  var ERRORS = { terms_required: 'learn.plans.errTerms', early_start_required: 'learn.plans.errEarly', invalid_plan: 'learn.plans.errPlan',
    not_available: 'learn.plans.errOff', not_configured: 'learn.plans.errOff' };

  function say(el, key) { el.textContent = key ? t(key) : ''; el.dataset.key = key || ''; }
  function plan() { var c = form.querySelector('input[name="plan"]:checked'); return c ? c.value : ''; }
  function newId() {
    var a = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }
  try {
    var pre = new URLSearchParams(location.search).get('plan');
    if (pre === 'weekly' || pre === 'biweekly') $('plan-' + pre).checked = true;
  } catch (e) {}

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (busy) return;
    say(error, ''); say(status, '');
    if (!plan()) { say(error, 'learn.plans.errPlan'); form.querySelector('input[name="plan"]').focus(); return; }
    if (!$('plans-accept').checked) { say(error, 'learn.plans.errTerms'); $('plans-accept').focus(); return; }
    if (!$('plans-early').checked) { say(error, 'learn.plans.errEarly'); $('plans-early').focus(); return; }
    if (!endpoint) { say(error, 'learn.plans.errOff'); return; }
    // The same choice keeps its requestId, so a double click or a retry opens the same Checkout session.
    var key = plan() + '|' + window.currentLanguage;
    if (!requestId || key !== lastKey) { requestId = newId(); lastKey = key; }
    busy = true; submit.disabled = true; say(status, 'learn.plans.redirecting');
    fetch(endpoint, { method: 'POST', credentials: 'omit', redirect: 'follow', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify({ op: 'checkout', plan: plan(), lang: window.currentLanguage === 'en' ? 'en' : 'es', requestId: requestId,
        acceptTerms: true, earlyStart: true, website: $('plans-website').value }) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res && res.ok && /^https:\/\/checkout\.stripe\.com\//.test(res.url || '')) { location.assign(res.url); return; }
        throw new Error((res && res.error) || 'unavailable');
      })
      .catch(function (e) {
        busy = false; submit.disabled = false; say(status, '');
        say(error, ERRORS[e && e.message] || 'learn.plans.errGeneric');
      });
  });
  document.addEventListener('lg:language', function () {
    if (error.dataset.key) say(error, error.dataset.key);
    if (status.dataset.key) say(status, status.dataset.key);
  });
  // Back from Stripe with the browser's Back button: the page may come from the bfcache with the button disabled.
  window.addEventListener('pageshow', function () { busy = false; submit.disabled = false; say(status, ''); });
})();
