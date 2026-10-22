// Shared behaviour for every page: translated aria-labels, theme switch, mobile menu, active navigation and the experience filter.
// The social links are injected here so the same footer row is kept across every published page.
(function(){
  const base=window.setLanguage;
  if(base)window.setLanguage=function(next){
    base(next);
    document.querySelectorAll('[data-i18n-label]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nLabel)));
    // Articles published in both languages point to the version in the page language.
    const es=window.currentLanguage==='es';
    document.querySelectorAll('a[data-href-en][data-href-es]').forEach(a=>{a.setAttribute('href',es?a.dataset.hrefEs:a.dataset.hrefEn);a.setAttribute('hreflang',es?'es':'en')});
    document.dispatchEvent(new CustomEvent('lg:language'));
  };
})();
(function(){
  const footer=document.querySelector('.footer .footer-inner');
  if(!footer||footer.querySelector('.social-links'))return;
  const tab=t('ui.newTab'),labelKey='ui.footerSocial';
  footer.innerHTML += '<nav class="social-links" aria-label="Social and music links" data-i18n-label="'+labelKey+'"><ul>'+
    '<li><a href="https://www.facebook.com/soyluisguinea" target="_blank" rel="noopener">Facebook<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.instagram.com/soyluisguinea/" target="_blank" rel="noopener">Instagram<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.tiktok.com/@soyluisguinea" target="_blank" rel="noopener">TikTok<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.threads.com/@soyluisguinea" target="_blank" rel="noopener">Threads<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://x.com/soyluisguinea" target="_blank" rel="noopener">X<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.linkedin.com/in/lcguinea/" target="_blank" rel="noopener">LinkedIn<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.youtube.com/@MoctezumaMusic" target="_blank" rel="noopener">YouTube · Moctezuma Music<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://www.youtube.com/@LuisGuinea" target="_blank" rel="noopener">YouTube · Luis Guinea<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://open.spotify.com/artist/1WRKrGxFosVscUFGLRkW2L" target="_blank" rel="noopener">Spotify<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://music.apple.com/gb/artist/luis-guinea/869634170" target="_blank" rel="noopener">Apple Music<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>'+
    '<li><a href="https://medium.com/@soyluisguinea" target="_blank" rel="noopener">Medium<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li></ul></nav>';
})();
(function(){
  const root=document.documentElement;
  // Smooth scrolling only for in-page jumps: arriving from another page at index.html#experience lands at once.
  window.addEventListener('load',()=>requestAnimationFrame(()=>root.classList.add('smooth-scroll')));
  // Theme: two pressed-state buttons, like the language switch. theme-init.js already applied the saved choice.
  function syncTheme(){const dark=root.dataset.theme==='dark';document.querySelectorAll('[data-theme-choice]').forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.themeChoice==='dark')===dark)))}
  document.querySelectorAll('[data-theme-choice]').forEach(b=>b.addEventListener('click',()=>{
    const dark=b.dataset.themeChoice==='dark';
    if(dark)root.dataset.theme='dark';else delete root.dataset.theme;
    try{localStorage.setItem('lg-theme',dark?'dark':'light')}catch(e){}
    syncTheme();
  }));
  syncTheme();

  // Mobile menu: a disclosure button that shows the navigation panel and reads "Close" while open; Escape closes it and
  // returns focus to the button, choosing a destination closes it.
  const header=document.querySelector('.site-header'),menuButton=document.querySelector('.menu-toggle'),menu=document.getElementById('site-menu');
  function isOpen(){return !!menuButton&&menuButton.getAttribute('aria-expanded')==='true'}
  function labelMenu(){if(menuButton)menuButton.textContent=t(isOpen()?'ui.close':'ui.menu')}
  function setMenu(open,focusButton){
    if(!menuButton)return;
    menuButton.setAttribute('aria-expanded',String(open));
    menuButton.dataset.i18n=open?'ui.close':'ui.menu';
    labelMenu();
    root.classList.toggle('menu-open',open);
    if(open){const first=menu.querySelector('a,button');if(first)first.focus()}
    else if(focusButton)menuButton.focus();
  }
  if(menuButton&&menu){
    menuButton.addEventListener('click',()=>setMenu(!isOpen(),false));
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&isOpen()){event.preventDefault();setMenu(false,true)}});
    menu.addEventListener('click',event=>{if(event.target.closest('a'))setMenu(false,false)});
    header.addEventListener('focusout',event=>{if(isOpen()&&event.relatedTarget&&!header.contains(event.relatedTarget))setMenu(false,false)});
    if(window.matchMedia){const wide=window.matchMedia('(min-width: 701px)');const close=()=>{if(wide.matches&&isOpen())setMenu(false,false)};if(wide.addEventListener)wide.addEventListener('change',close)}
  }

  // Anchors land below the sticky header whatever its height (it wraps to two lines on narrow desktops): the
  // stylesheet reads --header-offset in scroll-margin-top. A page opened at index.html#education is placed again
  // once the real height is known; reloads and history navigation keep the position the browser restores.
  function measureHeader(){if(header&&root.style.setProperty)root.style.setProperty('--header-offset',Math.ceil(header.getBoundingClientRect().height)+'px')}
  measureHeader();
  window.addEventListener('resize',measureHeader);
  window.addEventListener('load',()=>{
    measureHeader();
    const entry=window.performance&&performance.getEntriesByType?performance.getEntriesByType('navigation')[0]:null;
    const target=location.hash&&document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if(target&&target.scrollIntoView&&(!entry||entry.type==='navigate'))target.scrollIntoView();
  });

  // Active location on Home: every part of the page declares the menu entry it belongs to (data-nav), so What I do,
  // Education and Skills mark Background; each part also marks its own entry in the Background index and the mobile menu.
  const spy=[...document.querySelectorAll('.site-header a[data-section],.section-index a[data-section]')];
  const marks=[...document.querySelectorAll('main [data-nav]')];
  if(spy.length&&marks.length&&header){
    let queued=false;
    function update(){
      queued=false;
      const line=Math.max(header.getBoundingClientRect().height+32,window.innerHeight*.25);
      let current='',part='';
      marks.forEach(m=>{
        const box=m.getBoundingClientRect();
        if(box.top>line)return;
        // A part laid out beside the previous one (Skills next to Education on wide screens) shares its row: it only
        // takes over when it is the chosen destination.
        if(m.dataset.beside&&box.left>window.innerWidth*.4&&location.hash!=='#'+m.id)return;
        current=m.dataset.nav;part=m.id||'';
      });
      const page=document.documentElement;
      if(typeof page.scrollHeight==='number'&&window.innerHeight+window.scrollY>=page.scrollHeight-2){current=marks[marks.length-1].dataset.nav;part=''}
      spy.forEach(a=>{if(a.dataset.section===current||(part&&a.dataset.section===part))a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')});
      // On narrow screens the Background index scrolls sideways: keep its current entry in view.
      const active=document.querySelector('.section-index a[aria-current]'),strip=active&&active.closest('ul');
      if(strip&&strip.scrollWidth>strip.clientWidth){const left=active.offsetLeft-strip.offsetLeft;if(left<strip.scrollLeft||left+active.offsetWidth>strip.scrollLeft+strip.clientWidth)strip.scrollLeft=left-16}
    }
    window.addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(update)}},{passive:true});
    window.addEventListener('resize',update);
    update();
  }
  document.addEventListener('lg:language',labelMenu);

  const filter=document.querySelector('#experience-filter');
  if(filter)filter.addEventListener('change',()=>document.querySelectorAll('[data-facets]').forEach(x=>x.hidden=filter.value!=='all'&&!x.dataset.facets.split(' ').includes(filter.value)));
})();
