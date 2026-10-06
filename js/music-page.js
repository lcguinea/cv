// /music/: the large player and the playlist are a view of the global engine (js/player.js); they hold no audio.
(function(){
  const P=window.LGPlayer;
  if(!P)return;
  const $=id=>document.getElementById(id);
  const catalog=$('catalog'),search=$('search'),role=$('role'),count=$('count'),empty=$('empty'),toggle=$('toggle'),seek=$('seek'),volume=$('np-volume'),statusLine=$('np-status');
  const tracks=P.tracks;
  let visible=[];
  function norm(value){return String(value||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
  function esc(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function roleKey(name){return 'music.role'+String(name).replace(/[^A-Za-z]/g,'')}
  function typeKey(name){return 'music.type'+String(name).replace(/[^A-Za-z]/g,'')}
  function pad(n){return String(n).padStart(2,'0')}
  function clock(seconds){const s=Math.max(0,Math.floor(Number.isFinite(seconds)?seconds:0));return Math.floor(s/60)+':'+pad(s%60)}
  // Composer is the public facet of a songwriting credit; the other facets match credits directly.
  function matchesRole(x,value){if(!value)return true;const credit=value==='Composer'?'Songwriter':value;return x.role===value||x.roles.includes(credit)}
  function matches(x,q){return !q||norm([x.title,x.artist,x.year,x.releaseType,x.role,x.roles.join(' '),x.roles.map(r=>t(roleKey(r))).join(' ')].join(' ')).includes(q)}
  function renderList(){
    const q=norm(search.value);
    visible=tracks.map((x,i)=>i).filter(i=>matchesRole(tracks[i],role.value)&&matches(tracks[i],q));
    count.textContent=visible.length;
    empty.hidden=visible.length>0;
    catalog.innerHTML=visible.map(i=>{const x=tracks[i];return `<li><button type="button" class="pl-row" data-index="${i}" aria-current="false"><span class="pl-num">${pad(i+1)}</span><img class="pl-thumb" src="${P.artworkUrl(x.artwork)}" alt="" loading="lazy" width="56" height="56"><span class="pl-main"><span class="pl-title">${esc(x.title)}</span><span class="pl-artist">${esc(x.artist)}</span></span><span class="pl-roles">${x.roles.map(r=>`<span data-i18n="${roleKey(r)}">${esc(t(roleKey(r)))}</span>`).join(' · ')}</span><span class="pl-year">${x.year}</span><span class="pl-state"></span></button></li>`}).join('');
    updateRows();
  }
  function updateRows(){
    const playing=P.isPlaying(),active=P.index();
    catalog.querySelectorAll('.pl-row').forEach(row=>{
      const current=Number(row.dataset.index)===active,state=row.querySelector('.pl-state');
      row.setAttribute('aria-current',String(current));
      row.classList.toggle('is-playing',current&&playing);
      const key=current?(playing?'music.playing':'music.selected'):'';
      if(key){state.setAttribute('data-i18n',key);state.textContent=t(key)}else{state.removeAttribute('data-i18n');state.textContent=''}
    });
  }
  function renderTrack(){
    const x=P.current();
    $('np-art').src=P.artworkUrl(x.artwork);
    $('np-index').textContent=pad(P.index()+1)+' / '+pad(tracks.length);
    $('np-title').textContent=x.title;
    $('np-artist').textContent=x.artist;
    $('np-year').textContent=x.year;
    updatePlayer();updateTime();
  }
  function updateLabels(){
    const x=P.current();
    toggle.setAttribute('aria-label',t(P.isPlaying()?'music.pause':'music.play')+': '+x.title);
    $('np-art').alt=t('music.artworkAlt')+': '+x.title;
    $('np-type').textContent=t(typeKey(x.releaseType));
    seek.setAttribute('aria-valuetext',clock(P.time())+' '+t('music.of')+' '+clock(P.duration()));
    $('np-roles').innerHTML=x.roles.map(r=>`<li data-i18n="${roleKey(r)}">${esc(t(roleKey(r)))}</li>`).join('');
    if(P.failed())statusLine.textContent=t('music.loadError');
  }
  function updatePlayer(){
    const x=P.current(),playing=P.isPlaying();
    toggle.dataset.state=playing?'playing':'paused';
    if(!P.failed())statusLine.textContent=playing?t('music.playing')+': '+x.title+' · '+x.artist:(P.time()>0?t('music.paused')+': '+x.title:'');
    volume.value=String(P.muted()?0:P.volume());
    volume.setAttribute('aria-valuetext',Math.round((P.muted()?0:P.volume())*100)+' %');
    updateLabels();
    updateRows();
  }
  function updateTime(){
    const duration=P.duration();
    seek.max=duration;seek.value=P.time()||0;seek.disabled=!duration;
    $('time-current').textContent=clock(P.time());$('time-total').textContent=clock(duration);
    seek.setAttribute('aria-valuetext',clock(P.time())+' '+t('music.of')+' '+clock(duration));
  }
  function step(delta){
    const list=visible.length?visible:tracks.map((x,i)=>i),at=list.indexOf(P.index());
    const next=at<0?list[delta>0?0:list.length-1]:list[(at+delta+list.length)%list.length];
    P.select(next,P.isPlaying());
  }
  toggle.addEventListener('click',()=>P.toggle());
  $('prev').addEventListener('click',()=>step(-1));
  $('next').addEventListener('click',()=>step(1));
  seek.addEventListener('input',()=>P.seek(seek.value));
  volume.addEventListener('input',()=>P.setVolume(volume.value));
  if(!P.volumeSupported)$('np-volume-field').hidden=true;
  catalog.addEventListener('click',event=>{const row=event.target.closest('.pl-row');if(!row)return;const i=Number(row.dataset.index);if(i===P.index()&&P.isPlaying())P.pause();else P.select(i,true)});
  catalog.addEventListener('keydown',event=>{
    const rows=[...catalog.querySelectorAll('.pl-row')],at=rows.indexOf(document.activeElement);
    const target={ArrowDown:at+1,ArrowUp:at-1,Home:0,End:rows.length-1}[event.key];
    if(at<0||target===undefined||!rows[target])return;
    event.preventDefault();rows[target].focus();
  });
  search.addEventListener('input',renderList);role.addEventListener('change',renderList);
  P.on(type=>{if(type==='track')renderTrack();else if(type==='time')updateTime();else updatePlayer()});
  document.addEventListener('lg:language',updatePlayer);
  $('total').textContent=tracks.length;
  renderList();renderTrack();
})();
