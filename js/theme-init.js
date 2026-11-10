// Runs in <head> before the first paint: flags that JavaScript runs and restores the theme without a light flash.
// A shared link can set it with ?theme=dark or ?theme=light: it wins for this tab (kept in sessionStorage, so internal
// navigation keeps it) without replacing the visitor's own saved choice. A click on the theme buttons wins over both.
(function(){var root=document.documentElement,t=null;root.classList.add('js');try{t=new URLSearchParams(location.search).get('theme')}catch(e){}t=t==='dark'||t==='light'?t:null;try{if(t)sessionStorage.setItem('lg-theme-link',t);else t=sessionStorage.getItem('lg-theme-link')}catch(e){}if(t!=='dark'&&t!=='light'){try{t=localStorage.getItem('lg-theme')}catch(e){}}if(t==='dark')root.dataset.theme='dark'})();
