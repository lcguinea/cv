// Formación Musical pages (/formacion/): italics of the headline across language switches, area preselection and the
// enquiry form. With data-endpoint (the Apps Script web app, op "enquiry") the form sends the enquiry itself, as a
// simple text/plain POST like /agenda/; without it, or when sending fails, it writes the email in the visitor's mail
// app and offers the same text to copy. Nothing is stored by the site.
(function () {
  'use strict';
  var EMAIL = 'lguinea@berklee.edu';
  var ENDPOINT_RE = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/;
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  // Headlines carry data-accent: the word set in italics, as in "Aprende música <em>haciendo</em> música."
  function accents() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-accent]'), function (h) {
      var title = t(h.getAttribute('data-i18n')), word = t(h.getAttribute('data-accent')), at = title.lastIndexOf(word);
      if (at < 0) { h.textContent = title; return; }
      h.innerHTML = esc(title.slice(0, at)) + '<em>' + esc(word) + '</em>' + esc(title.slice(at + word.length));
    });
  }
  document.addEventListener('lg:language', accents);

  var form = document.getElementById('learn-form');
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var area = $('learn-area'), error = $('learn-error'), status = $('learn-status'), sent = $('learn-sent');
  var copyText = $('learn-copytext'), copyButton = $('learn-copy'), copyStatus = $('learn-copy-status');
  var submit = form.querySelector('button[type="submit"]');
  var endpoint = form.getAttribute('data-endpoint') || '';
  if (!ENDPOINT_RE.test(endpoint)) endpoint = '';

  function pick(value) {
    if (value && area.querySelector('option[value="' + String(value).replace(/[^a-z]/g, '') + '"]')) area.value = value;
  }
  // ?area=piano from the subpages and the "Request information" links; same-page links preselect on click.
  try { pick(new URLSearchParams(location.search).get('area')); } catch (e) {}
  Array.prototype.forEach.call(document.querySelectorAll('a[data-area]'), function (a) {
    a.addEventListener('click', function () { pick(a.getAttribute('data-area')); });
  });

  function label(select) {
    var option = select.options[select.selectedIndex];
    return select.value && option ? option.textContent.trim() : '';
  }
  function fieldName(id) { return form.querySelector('label[for="' + id + '"]').textContent.trim(); }
  function values() {
    return {
      area: area.value, areaName: label(area), level: $('learn-level').value, levelName: label($('learn-level')),
      format: $('learn-format').value, formatName: label($('learn-format')), name: $('learn-name').value.trim(),
      email: $('learn-email').value.trim(), message: $('learn-message').value.trim(), website: $('learn-website').value
    };
  }
  function compose(v) {
    var lines = [t('learn.form.mailHello'), '', t('learn.form.mailArea') + ': ' + v.areaName];
    if (v.levelName) lines.push(fieldName('learn-level') + ': ' + v.levelName);
    if (v.formatName) lines.push(fieldName('learn-format') + ': ' + v.formatName);
    if (v.message) lines.push('', t('learn.form.mailMessage') + ':', v.message);
    lines.push('', v.name + (v.email ? ' <' + v.email + '>' : ''));
    return { subject: t('learn.form.mailSubject').replace('{area}', v.areaName), body: lines.join('\n') };
  }
  function invalid(field, key) {
    error.textContent = t(key);
    field.setAttribute('aria-invalid', 'true');
    field.focus();
    return false;
  }
  function validate(v) {
    Array.prototype.forEach.call(form.querySelectorAll('[aria-invalid]'), function (f) { f.removeAttribute('aria-invalid'); });
    error.textContent = '';
    if (!v.area) return invalid(area, 'learn.form.errArea');
    if (!v.name) return invalid($('learn-name'), 'learn.form.errName');
    if (!EMAIL_RE.test(v.email)) return invalid($('learn-email'), 'learn.form.errEmail');
    return true;
  }
  function offerMail(v, openApp) {
    var mail = compose(v);
    copyText.textContent = mail.subject + '\n\n' + mail.body;
    copyStatus.textContent = '';
    sent.hidden = false;
    if (openApp) window.location.href = 'mailto:' + EMAIL + '?subject=' + encodeURIComponent(mail.subject) + '&body=' + encodeURIComponent(mail.body);
  }
  function busy(on) {
    submit.disabled = on;
    submit.textContent = t(on ? 'learn.form.sending' : 'learn.form.send');
  }

  form.addEventListener('change', function (event) {
    if (event.target.getAttribute('aria-invalid') && event.target.value) event.target.removeAttribute('aria-invalid');
  });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var v = values();
    if (!validate(v)) return;
    if (v.website) return; // honeypot: a bot filled the hidden field
    status.textContent = '';
    if (!endpoint) { offerMail(v, true); return; }
    busy(true);
    var payload = { op: 'enquiry', area: v.area, level: v.level, format: v.format, name: v.name, email: v.email,
      message: v.message, website: v.website, lang: window.currentLanguage === 'en' ? 'en' : 'es' };
    fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        busy(false);
        if (!data || data.ok !== true) throw new Error((data && data.error) || 'failed');
        form.reset();
        sent.hidden = true;
        status.textContent = t('learn.form.sent');
      })
      .catch(function () {
        busy(false);
        error.textContent = t('learn.form.errSend');
        offerMail(v, false);
      });
  });

  copyButton.addEventListener('click', function () {
    var text = copyText.textContent;
    function done(ok) { copyStatus.textContent = t(ok ? 'learn.form.copied' : 'learn.form.copyFailed'); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    else done(false);
  });
})();
