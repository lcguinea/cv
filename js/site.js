// Shared behaviour for every page: translated aria-labels, theme switch, mobile menu, active navigation and the experience filter.
(function(){
  const socials=[
    {id:'facebook',name:'Facebook',url:'https://www.facebook.com/soyluisguinea',icon:'M24 2.5C12.1 2.5 2.5 12.1 2.5 24S12.1 45.5 24 45.5h.2V30.7h-5v-6h5v-4.4c0-5 3-7.8 7.5-7.8 2.1 0 4.2.4 4.2.4v5.3h-2.7c-2.5 0-3.2 1.2-3.2 3v3.6h5.6l-.9 6h-4.7v14.3C39.1 42.8 45.5 34.2 45.5 24 45.5 12.1 35.9 2.5 24 2.5Z'},
    {id:'instagram',name:'Instagram',url:'https://www.instagram.com/soyluisguinea/',icon:'M16 3h16c7.2 0 13 5.8 13 13v16c0 7.2-5.8 13-13 13H16C8.8 45 3 39.2 3 32V16C3 8.8 8.8 3 16 3Zm0 5.2A7.8 7.8 0 0 0 8.2 16v16a7.8 7.8 0 0 0 7.8 7.8h16a7.8 7.8 0 0 0 7.8-7.8V16a7.8 7.8 0 0 0-7.8-7.8H16Zm8 4.5A11.3 11.3 0 1 1 12.7 24 11.3 11.3 0 0 1 24 12.7Zm0 5.2a6.1 6.1 0 1 0 6.1 6.1 6.1 6.1 0 0 0-6.1-6.1Zm11.8-6.1a2.7 2.7 0 1 1-2.7 2.7 2.7 2.7 0 0 1 2.7-2.7Z'},
    {id:'tiktok',name:'TikTok',url:'https://www.tiktok.com/@soyluisguinea',icon:'M31.3 3h7.1c.5 5 3.3 8.1 8.1 8.4v7.2c-2.8.3-5.5-.6-8-2.2v14.8c0 9.6-6.4 14.9-14 14.9-7.2 0-12.5-5.1-12.5-12.1 0-7.4 5.7-12.9 14.1-12.9.6 0 1.2.1 1.8.2v7.4a8.3 8.3 0 0 0-1.8-.2c-3.4 0-5.9 2.1-5.9 5.2 0 2.8 2.1 4.8 5 4.8 3.2 0 6.1-2.1 6.1-7.2V3Z'},
    {id:'threads',name:'Threads',url:'https://www.threads.com/@soyluisguinea',icon:'M24 3C11.8 3 4 10.5 4 22.8 4 35.5 11.7 45 24.1 45c10.6 0 16.8-5.6 16.8-14.2 0-7.4-5.2-12.7-13.8-13.7-.5-2.5-2.3-3.8-5.3-3.8-3.3 0-5.7 1.9-6.4 5.1h5.3c.4-.7.9-1 1.5-1 1.2 0 1.9.5 2.3 1.5C16.9 19 12 22.2 12 28.1 12 33.6 16.3 37 22 37c5.9 0 10-3.5 10-8.6 0-1.2-.2-2.3-.6-3.3 3.1 1.3 4.5 3.3 4.5 6.1 0 5.7-4.1 9.3-11.8 9.3-9.5 0-15.2-6.5-15.2-17.7C8.9 12.9 14.5 7 24 7c8 0 13.1 3.5 15 10h-5.2C32.4 11.9 28.8 10 24 10c-7.4 0-12.2 4.7-12.2 12.8 0 8 4.6 12.7 11.9 12.7 4.5 0 7.5-2.3 7.5-5.8 0-2.5-1.5-4.1-4.6-4.9-.1 4.4-1.9 6.5-5 6.5-2.5 0-4.2-1.3-4.2-3.3 0-2.6 2.5-4.3 6.5-4.3 1.2 0 2.5.1 3.6.3-.4-2.6-2.2-4-5.3-4-4.9 0-8.2 3-8.2 7.7 0 4.7 3.5 7.4 8.6 7.4 5.1 0 8.5-3.1 8.5-7.8 0-1.1-.2-2.1-.6-3Z'},
    {id:'x',name:'X',url:'https://x.com/soyluisguinea',icon:'M7 4h8.2l6.9 9.2L30 4h4l-9.7 11.1L36 36h-8.2l-7.5-10-8.8 10h-4l11.7-11.9L7 4Zm5.3 3.2 16 25.6h2.4L14.7 7.2h-2.4Z'},
    {id:'linkedin',name:'LinkedIn',url:'https://www.linkedin.com/in/lcguinea/',icon:'M7 8h7v23H7V8Zm3.5-6a4.1 4.1 0 1 1 0 8.2A4.1 4.1 0 0 1 10.5 2ZM18 8h6.7v3.2h.1c.9-1.7 3.1-3.8 6.8-3.8 7.3 0 8.7 4.8 8.7 11v12.6h-7V19.8c0-2.7-.1-6.1-3.7-6.1s-4.2 2.9-4.2 5.9V31h-7V8Z'},
    {id:'youtube-moctezuma',name:'YouTube · Moctezuma Music',url:'https://www.youtube.com/@MoctezumaMusic',icon:'M42.4 10.5a5.5 5.5 0 0 0-3.9-3.9C35.1 5.7 24 5.7 24 5.7S12.9 5.7 9.5 6.6a5.5 5.5 0 0 0-3.9 3.9C4.7 13.9 4.7 24 4.7 24s0 10.1.9 13.5a5.5 5.5 0 0 0 3.9 3.9c3.4.9 14.5.9 14.5.9s11.1 0 14.5-.9a5.5 5.5 0 0 0 3.9-3.9c.9-3.4.9-13.5.9-13.5s0-10.1-.9-13.5ZM20 31V17l12 7-12 7Z'},
    {id:'youtube-luis',name:'YouTube · Luis Guinea',url:'https://www.youtube.com/@LuisGuinea',icon:'M42.4 10.5a5.5 5.5 0 0 0-3.9-3.9C35.1 5.7 24 5.7 24 5.7S12.9 5.7 9.5 6.6a5.5 5.5 0 0 0-3.9 3.9C4.7 13.9 4.7 24 4.7 24s0 10.1.9 13.5a5.5 5.5 0 0 0 3.9 3.9c3.4.9 14.5.9 14.5.9s11.1 0 14.5-.9a5.5 5.5 0 0 0 3.9-3.9c.9-3.4.9-13.5.9-13.5s0-10.1-.9-13.5ZM20 31V17l12 7-12 7Z'},
    {id:'spotify',name:'Spotify',url:'https://open.spotify.com/artist/1WRKrGxFosVscUFGLRkW2L',icon:'M24 3C12.4 3 3 12.4 3 24s9.4 21 21 21 21-9.4 21-21S35.6 3 24 3Zm9.6 30.3a1.5 1.5 0 0 1-2.1.5c-5.7-3.5-12.8-4.3-21.2-2.3a1.6 1.6 0 1 1-.7-3c9.2-2.1 17.1-1.3 23.5 2.6.9.5 1 1.6.5 2.2Zm2.8-6.2c-.7.9-1.9 1.1-2.8.5-6.5-4-16.4-5.2-24.1-2.8a2 2 0 1 1-1.2-3.8c8.8-2.7 19.7-1.4 27.2 3.2.9.6 1.2 1.9.9 2.9Zm.2-6.5c-7.8-4.6-20.7-5-28.2-2.7a2.4 2.4 0 1 1-1.4-4.6c8.9-2.7 23.6-2.2 32.8 3.2a2.4 2.4 0 0 1-3.2 4.1Z'},
    {id:'apple-music',name:'Apple Music',url:'https://music.apple.com/gb/artist/luis-guinea/869634170',icon:'M36.4 4.1c-5.5.3-10.7 3.1-13.5 6.7-2.6-3.9-7.3-6.7-12.2-6.8-.5 4.8 1.3 9.5 4.4 12.5-3.4 2-5.6 5.8-5.6 10.1C9.5 33.5 15 39 21.9 39c4.1 0 7.6-2 9.7-5.1 2.1 3.1 5.7 5.1 9.8 5.1 6.9 0 12.4-5.5 12.4-12.4 0-4.3-2.2-8.1-5.6-10.1 3.1-3 4.9-7.5 4.4-12.3-4.8.1-9.4 2.8-12.2 6.5Z'},
    {id:'medium',name:'Medium',url:'https://medium.com/@soyluisguinea',icon:'M6 11h36v26H6V11Zm6 5v16l10 5V21l-10-5Zm13 2v14l10 5V23l-10-5Z'}
  ];
  window.LG_SOCIALS=socials;
  const base=window.setLanguage;
  if(base)window.setLanguage=function(next){
    base(next);
    document.querySelectorAll('[data-i18n-label]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nLabel)));
    document.querySelectorAll('[data-social-label]').forEach(el=>el.setAttribute('aria-label',el.dataset.socialName+t('ui.newTab')));
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
  footer.innerHTML += '<nav class="social-links" aria-label="Social and music links" data-i18n-label="'+labelKey+'"><ul>'+window.LG_SOCIALS.map(s=>'<li><a href="'+s.url+'" target="_blank" rel="noopener" data-social-name="'+s.name+'">'+s.name+'<span class="sr-only" data-i18n="ui.newTab">'+tab+'</span></a></li>').join('')+'</ul></nav>';
})();
(function(){
  const image=document.querySelector('.hero-image');
  if(!image||image.querySelector('.hero-socials'))return;
  const tab=t('ui.newTab');
  image.innerHTML += '<nav class="hero-socials" aria-label="Social and music links" data-i18n-label="ui.footerSocial"><ul>'+window.LG_SOCIALS.map(s=>'<li><a href="'+s.url+'" target="_blank" rel="noopener noreferrer" aria-label="'+s.name+tab+'" data-social-label data-social-name="'+s.name+'"><svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path d="'+s.icon+'"></path></svg><span class="sr-only">'+s.name+'</span></a></li>').join('')+'</ul></nav>';
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
