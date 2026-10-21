(function () {
  // Language: a manual choice (the EN/ES buttons) is saved and always wins, on every page and visit. Without one, the
  // browser decides: the first Spanish or English entry of navigator.languages, English when there is none. Earlier
  // versions saved 'en' on every visit without a click, so a saved 'en' only counts as a choice when it carries the
  // manual mark; a saved 'es' could only come from a click.
  function read(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function write(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  function detect() {
    const list = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''];
    for (const tag of list) { const base = String(tag).toLowerCase().split('-')[0]; if (base === 'es' || base === 'en') return base; }
    return 'en';
  }
  const saved = read('lg-language');
  const manual = saved === 'es' || (saved === 'en' && read('lg-language-manual') === '1');
  const lang = manual ? saved : detect();
  window.currentLanguage = lang;
  window.t = function (path) { return path.split('.').reduce((o, k) => o && o[k], STRINGS[window.currentLanguage]) || path; };
  window.setLanguage = function (next) { window.currentLanguage = next === 'es' ? 'es' : 'en'; document.documentElement.lang = window.currentLanguage; document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); }); document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); }); document.querySelectorAll('[data-lang]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.lang === window.currentLanguage))); };
  // The page is fully parsed (scripts load last), so a non-default language is applied now, before later
  // scripts load and the browser paints the English fallback; DOMContentLoaded repeats it with site.js's extras.
  if (lang !== 'en') window.setLanguage(lang);
  document.addEventListener('DOMContentLoaded', () => { setLanguage(lang); document.querySelectorAll('[data-lang]').forEach(el => el.addEventListener('click', () => { const next = el.dataset.lang === 'es' ? 'es' : 'en'; write('lg-language', next); write('lg-language-manual', '1'); setLanguage(next); })); });
})();
