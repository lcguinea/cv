// Shared behaviour for every page: translated aria-labels, theme switch, mobile menu, active navigation and the experience filter.
(function(){
  const base=window.setLanguage;
  if(base)window.setLanguage=function(next){
    base(next);
    document.querySelectorAll('[data-i18n-label]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nLabel)));
    document.dispatchEvent(new CustomEvent('lg:language'));
  };
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

  // Mobile menu: a disclosure button that shows the navigation panel; Escape closes it and returns focus to the button.
  const header=document.querySelector('.site-header'),menuButton=document.querySelector('.menu-toggle'),menu=document.getElementById('site-menu');
  function isOpen(){return !!menuButton&&menuButton.getAttribute('aria-expanded')==='true'}
  function setMenu(open,focusButton){
    if(!menuButton)return;
    menuButton.setAttribute('aria-expanded',String(open));
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

  // Active section on the home page: the in-page links get aria-current="true" while their section is under the header.
  const spy=[...document.querySelectorAll('.nav a[href^="#"]')];
  if(spy.length&&header){
    const sections=[...document.querySelectorAll('main > section')];
    let queued=false;
    function update(){
      queued=false;
      const line=Math.max(header.getBoundingClientRect().height+32,window.innerHeight*.25);
      let current='';
      sections.forEach(s=>{if(s.getBoundingClientRect().top<=line)current=s.id||''});
      if(window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-2&&sections.length)current=sections[sections.length-1].id||current;
      spy.forEach(a=>{if(a.getAttribute('href')==='#'+current)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current')});
    }
    window.addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(update)}},{passive:true});
    window.addEventListener('resize',update);
    update();
  }

  const filter=document.querySelector('#experience-filter');
  if(filter)filter.addEventListener('change',()=>document.querySelectorAll('[data-facets]').forEach(x=>x.hidden=filter.value!=='all'&&!x.dataset.facets.split(' ').includes(filter.value)));
})();
