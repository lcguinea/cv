// Runs in <head> before the first paint: flags that JavaScript runs and restores a saved dark theme without a light flash.
(function(){var root=document.documentElement;root.classList.add('js');try{if(localStorage.getItem('lg-theme')==='dark')root.dataset.theme='dark'}catch(e){}})();
