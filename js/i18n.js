(function () {
  const saved = localStorage.getItem('lg-language');
  const lang = saved === 'es' ? 'es' : 'en';
  window.currentLanguage = lang;
  window.t = function (path) { return path.split('.').reduce((o, k) => o && o[k], STRINGS[window.currentLanguage]) || path; };
  window.setLanguage = function (next) { window.currentLanguage = next === 'es' ? 'es' : 'en'; localStorage.setItem('lg-language', window.currentLanguage); document.documentElement.lang = window.currentLanguage; document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); }); document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); }); document.querySelectorAll('[data-lang]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.lang === window.currentLanguage))); };
  // The page is fully parsed (scripts load last), so a saved non-default language is applied now, before later
  // scripts load and the browser paints the English fallback; DOMContentLoaded repeats it with site.js's extras.
  if (lang !== 'en') window.setLanguage(lang);
  document.addEventListener('DOMContentLoaded', () => { setLanguage(lang); document.querySelectorAll('[data-lang]').forEach(el => el.addEventListener('click', () => setLanguage(el.dataset.lang))); });
})();
