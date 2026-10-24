// Global music engine shared by every page. It owns the only <audio> element, so the bottom bar and the large
// player on /music/ are two views of one state and never sound together. Track, position and play state survive
// page changes in sessionStorage; volume and mute live in localStorage. A new session starts a random track on its
// own when the browser allows it; browsers usually refuse sound before the visitor interacts with the site, so until
// the first preview has played, the first click or tap outside the player starts it. Resuming after a page change is
// only attempted and may be refused.
(function(){
  const tracks=window.MUSIC_DATA||[];
  if(!tracks.length)return;
  const SESSION_KEY='lg-player',VOLUME_KEY='lg-volume',MUTED_KEY='lg-muted';
  const root=new URL('../',document.currentScript?document.currentScript.src:location.href);
  function previewUrl(name){return /^[a-z0-9][a-z0-9-]*\.mp3$/.test(String(name||''))?new URL('assets/audio/previews/'+encodeURIComponent(name),root).href:''}
  function artworkUrl(name){return new URL('assets/images/'+encodeURIComponent(name),root).href}
  function storage(area){return{get(k){try{return window[area].getItem(k)}catch(e){return null}},set(k,v){try{window[area].setItem(k,v)}catch(e){}}}}
  const session=storage('sessionStorage'),local=storage('localStorage');
  // window.name survives navigation inside one tab but not into a new tab, so it tells a page change in this tab
  // (resume) from a new tab that inherited a copy of sessionStorage (restore paused).
  const TAB_PREFIX='lg-tab-';
  if(!window.name)window.name=TAB_PREFIX+Date.now().toString(36);
  const tab=window.name.indexOf(TAB_PREFIX)===0?window.name:'';

  const audio=document.createElement('audio');
  audio.preload='none';
  const listeners=[];
  let index=-1,failed=false,pendingTime=0,knownDuration=0,lastSave=0,autostart=false,played=new Set();
  function emit(type){listeners.forEach(fn=>fn(type))}
  function isPlaying(){return !audio.paused&&!audio.ended}
  function time(){return audio.readyState>0?audio.currentTime:pendingTime}
  function duration(){return Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:knownDuration}
  // Random picks (start, end of a preview, next) work like a shuffle: a preview that already played in this round is
  // not picked again until every other one has played; then a new round starts. `exclude` is never picked when there
  // is an alternative. Orchestral pieces (genre cinematic_classical) are never picked at random; they stay in the
  // catalogue and play when chosen by hand. Choosing a song by hand can always repeat it.
  const shuffled=tracks.map((x,i)=>i).filter(i=>!(tracks[i].genres||[]).includes('cinematic_classical'));
  const automatic=shuffled.length?shuffled:tracks.map((x,i)=>i);
  function randomIndex(exclude){
    let pool=automatic.filter(i=>i!==exclude&&!played.has(i));
    if(!pool.length){played.clear();pool=automatic.filter(i=>i!==exclude)}
    if(!pool.length)pool=[automatic[0]];
    return pool[Math.floor(Math.random()*pool.length)];
  }
  function save(){
    if(index<0)return;
    lastSave=Date.now();
    session.set(SESSION_KEY,JSON.stringify({preview:tracks[index].preview,time:time(),duration:duration(),playing:isPlaying(),auto:autostart,played:[...played].map(i=>tracks[i].preview),tab}));
  }
  function load(i,at,length){
    audio.pause();
    index=i;failed=false;pendingTime=at||0;knownDuration=length||0;
    audio.src=previewUrl(tracks[i].preview);
    emit('track');emit('time');
  }
  function pauseOtherMedia(){document.querySelectorAll('audio,video').forEach(media=>{if(media!==audio)media.pause()})}
  function start(){
    pauseOtherMedia();
    let result;
    try{result=audio.play()}catch(error){result=Promise.reject(error)}
    return Promise.resolve(result).then(()=>true,error=>{
      // NotAllowedError: the browser refused playback without a gesture; AbortError: a newer request replaced this one.
      const name=error&&error.name;
      if(name!=='NotAllowedError'&&name!=='AbortError')failed=true;
      save();emit('state');
      return false;
    });
  }
  function select(i,play){
    i=Number(i);
    if(!(i>=0&&i<tracks.length))return Promise.resolve(false);
    if(i!==index||!audio.getAttribute('src'))load(i,0,0);
    if(play)return start();
    save();emit('state');
    return Promise.resolve(false);
  }
  function seek(seconds){
    const value=Math.max(0,Number(seconds)||0);
    if(audio.readyState>0)audio.currentTime=value;else pendingTime=value;
    save();emit('time');
  }
  const volumeSupported=(function(){const before=audio.volume;try{audio.volume=before===.5?.4:.5;const ok=audio.volume!==before;audio.volume=before;return ok}catch(e){return false}})();
  function setVolume(value){
    const v=Math.min(1,Math.max(0,Number(value)));
    if(!Number.isFinite(v))return;
    audio.volume=v;
    if(v>0&&audio.muted)audio.muted=false;
    local.set(VOLUME_KEY,String(v));local.set(MUTED_KEY,audio.muted?'1':'0');
    emit('volume');
  }
  function setMuted(muted){audio.muted=!!muted;local.set(MUTED_KEY,audio.muted?'1':'0');emit('volume')}

  // Persisted volume and mute.
  const storedVolume=parseFloat(local.get(VOLUME_KEY));
  if(Number.isFinite(storedVolume))audio.volume=Math.min(1,Math.max(0,storedVolume));
  audio.muted=local.get(MUTED_KEY)==='1';

  audio.addEventListener('loadedmetadata',()=>{
    if(pendingTime>0){const at=Math.min(pendingTime,Math.max(0,audio.duration-.25));pendingTime=0;try{audio.currentTime=at}catch(e){}}
    knownDuration=duration();
  });
  // Autostart: armed for a new session until the first preview plays. Clicks on the player itself (and on the jingle
  // players of /music/#jingles, which play their own audio) are left to their controls,
  // and utility controls (skip links, language, theme, menu, sharing a link) never start sound: they are often the first thing a keyboard or
  // screen reader user activates.
  const GESTURES=['click','touchend'],NO_AUTOSTART='#mini-player,#player,#catalog,.feature-play,[data-player-now],.skip-link,[data-lang],[data-theme-choice],.menu-toggle,.jingle,#share-view,#share-fallback';
  function onGesture(event){if(event.target&&event.target.closest&&event.target.closest(NO_AUTOSTART))return;if(!isPlaying())start()}
  function armAutostart(){
    if(!autostart){autostart=true;GESTURES.forEach(type=>document.addEventListener(type,onGesture,true))}
    audio.preload='auto';start();
  }
  function disarmAutostart(){if(autostart){autostart=false;GESTURES.forEach(type=>document.removeEventListener(type,onGesture,true))}}
  ['play','pause'].forEach(type=>audio.addEventListener(type,()=>{if(type==='play'){disarmAutostart();played.add(index)}save();emit('state')}));
  // A finished preview moves on to another random one; the element already holds the user's permission to play.
  audio.addEventListener('ended',()=>{select(randomIndex(index),true)});
  ['timeupdate','durationchange','loadedmetadata','emptied'].forEach(type=>audio.addEventListener(type,()=>{if(type==='timeupdate'&&Date.now()-lastSave>1000)save();emit('time')}));
  audio.addEventListener('error',()=>{if(audio.getAttribute('src')){failed=true;emit('state')}});
  window.addEventListener('pagehide',save);
  // Opening a streaming platform (it plays the full track in another tab) pauses the preview.
  ['click','auxclick'].forEach(type=>document.addEventListener(type,event=>{if(event.target&&event.target.closest&&event.target.closest('a[data-platform]'))audio.pause()},true));
  // Any other media element that starts on this page pauses the engine.
  document.addEventListener('play',event=>{if(event.target!==audio)audio.pause()},true);
  // Other tabs: whichever starts playing last is the only one that sounds.
  let channel=null;
  try{if(window.BroadcastChannel){channel=new BroadcastChannel('lg-player');channel.onmessage=event=>{if(event.data&&event.data.type==='play')audio.pause()}}}catch(e){channel=null}
  audio.addEventListener('play',()=>{if(channel)channel.postMessage({type:'play'})});

  // Restore this tab's session, or start a new one on a random track.
  function readSaved(){
    let saved=null;
    try{saved=JSON.parse(session.get(SESSION_KEY)||'null')}catch(e){saved=null}
    const i=saved?tracks.findIndex(x=>x.preview===saved.preview):-1;
    const done=i>=0&&Array.isArray(saved.played)?saved.played.map(name=>tracks.findIndex(x=>x.preview===name)).filter(j=>j>=0):[];
    return i>=0?{index:i,played:done,time:Math.max(0,Number(saved.time)||0),duration:Math.max(0,Number(saved.duration)||0),playing:saved.playing===true&&saved.tab===tab,auto:saved.auto===true}:null;
  }
  function resume(saved){
    const policy=navigator.getAutoplayPolicy?navigator.getAutoplayPolicy('mediaelement'):'';
    if(saved.playing&&policy!=='disallowed'){audio.preload='auto';start()}else save();
  }
  // A shared link to one recording (/music/?song=<work id>, its preview's name without .mp3) opens on that recording,
  // paused: the link never starts sound, so it neither resumes nor arms the autostart. js/music-page.js locates it.
  function linkedIndex(){
    if(!document.getElementById('catalog'))return -1;
    let id='';
    try{id=new URLSearchParams(location.search).get('song')||''}catch(e){id=''}
    return /^[a-z0-9][a-z0-9-]*$/.test(id)?tracks.findIndex(x=>x.preview===id+'.mp3'):-1;
  }
  const saved=readSaved(),linked=linkedIndex();
  if(linked>=0){if(saved)played=new Set(saved.played);const same=!!saved&&saved.index===linked;load(linked,same?saved.time:0,same?saved.duration:0);save()}
  else if(saved){played=new Set(saved.played);load(saved.index,saved.time,saved.duration);if(saved.auto&&!saved.playing)armAutostart();else resume(saved)}
  else{load(randomIndex(-1),0,0);armAutostart()}
  // Back/forward cache: this page comes back as it was left, so it catches up with what later pages saved.
  window.addEventListener('pageshow',event=>{
    if(!event.persisted)return;
    const latest=readSaved();
    if(!latest)return;
    played=new Set(latest.played);
    if(latest.index!==index)load(latest.index,latest.time,latest.duration);
    else if(Math.abs(time()-latest.time)>.5)seek(latest.time);
    if(!latest.playing)audio.pause();
    if(!latest.auto)disarmAutostart();
    resume(latest);
  });

  // Media Session: lock screen and hardware keys.
  const mediaSession=navigator.mediaSession;
  function updateMediaSession(){
    if(!mediaSession)return;
    try{
      const x=tracks[index];
      if(window.MediaMetadata)mediaSession.metadata=new MediaMetadata({title:x.title,artist:x.artist,album:'Luis Guinea',artwork:[{src:artworkUrl(x.artwork),type:'image/webp'}]});
      mediaSession.playbackState=isPlaying()?'playing':'paused';
    }catch(e){}
  }
  if(mediaSession){
    const actions={play:()=>start(),pause:()=>audio.pause(),nexttrack:()=>select(randomIndex(index),isPlaying()),seekto:details=>seek(details.seekTime)};
    Object.keys(actions).forEach(action=>{try{mediaSession.setActionHandler(action,actions[action])}catch(e){}});
    listeners.push(type=>{if(type==='track'||type==='state')updateMediaSession()});
    updateMediaSession();
  }

  window.LGPlayer={
    tracks,previewUrl,artworkUrl,volumeSupported,
    index:()=>index,current:()=>tracks[index],isPlaying,failed:()=>failed,time,duration,
    volume:()=>audio.volume,muted:()=>audio.muted,
    select,play:start,pause:()=>audio.pause(),
    toggle:()=>{if(isPlaying()){audio.pause();return Promise.resolve(false)}return start()},
    next:()=>select(randomIndex(index),isPlaying()),
    seek,setVolume,setMuted,
    on:fn=>{listeners.push(fn)},
  };
})();

// Bottom bar: present on every page; on /music/ it only appears while the large player is out of view.
(function(){
  const P=window.LGPlayer,bar=document.getElementById('mini-player');
  if(!P||!bar)return;
  const $=id=>document.getElementById(id);
  const toggle=$('mp-toggle'),mute=$('mp-mute'),volume=$('mp-volume'),progress=$('mp-progress'),status=$('mp-status');
  // The large player has its own live status; the bar only announces on the other pages.
  const stage=document.getElementById('player');
  function render(){
    const x=P.current();
    $('mp-art').src=P.artworkUrl(x.artwork);
    $('mp-title').textContent=x.title;
    $('mp-artist').textContent=x.artist;
    labels();
  }
  function labels(){
    const x=P.current(),playing=P.isPlaying();
    toggle.dataset.state=playing?'playing':'paused';
    toggle.setAttribute('aria-label',t(playing?'music.pause':'music.play')+': '+x.title);
    mute.setAttribute('aria-pressed',String(P.muted()));
    volume.value=String(P.muted()?0:P.volume());
    volume.setAttribute('aria-valuetext',t('player.percent').replace('{n}',Math.round((P.muted()?0:P.volume())*100)));
    if(!stage)status.textContent=P.failed()?t('music.loadError'):(playing?t('music.playing')+': '+x.title+' · '+x.artist:'');
  }
  function tick(){const d=P.duration();progress.style.width=(d?Math.min(100,P.time()/d*100):0)+'%'}
  toggle.addEventListener('click',()=>P.toggle());
  // "Skip to music player" lands on the play/pause button, so the audio can be paused in a couple of key presses.
  document.querySelectorAll('a[href="#mini-player"]').forEach(a=>a.addEventListener('click',event=>{event.preventDefault();toggle.focus()}));
  $('mp-next').addEventListener('click',()=>P.next());
  mute.addEventListener('click',()=>P.setMuted(!P.muted()));
  volume.addEventListener('input',()=>P.setVolume(volume.value));
  if(!P.volumeSupported)bar.dataset.volume='fixed';
  P.on(type=>{if(type==='track')render();else if(type==='time')tick();else labels()});
  document.addEventListener('lg:language',labels);
  render();tick();
  if(stage&&window.IntersectionObserver){
    bar.hidden=true;
    new IntersectionObserver(entries=>entries.forEach(entry=>{bar.hidden=entry.isIntersecting})).observe(stage);
  }else bar.hidden=false;
})();

// Featured recordings on Home: each play button is one more view of the engine, so a featured preview, the bottom bar
// and /music/ never sound together. The cards are plain HTML; the buttons stay hidden until their preview is found here.
(function(){
  const P=window.LGPlayer,buttons=[...document.querySelectorAll('.feature-play[data-feature]')];
  if(!P||!buttons.length)return;
  const indexOf=name=>P.tracks.findIndex(x=>x.preview===name);
  function render(){
    const playing=P.isPlaying(),active=P.index();
    buttons.forEach(button=>{
      const i=indexOf(button.dataset.feature),on=i>=0&&i===active&&playing;
      button.dataset.state=on?'playing':'paused';
      button.setAttribute('aria-label',t(on?'music.pause':'music.play')+': '+(i>=0?P.tracks[i].title:''));
      const card=button.closest('.feature');if(card)card.classList.toggle('is-playing',on);
    });
  }
  buttons.forEach(button=>{
    const i=indexOf(button.dataset.feature);
    if(i<0)return;
    button.hidden=false;
    button.addEventListener('click',()=>{if(P.index()===i&&P.isPlaying())P.pause();else P.select(i,true)});
  });
  P.on(type=>{if(type!=='time')render()});
  document.addEventListener('lg:language',render);
  render();
})();

// "Playing while you choose" on /agenda/: one more view of the engine, like the featured buttons on Home. It shows the
// current preview and its button plays or pauses it; it has no audio of its own.
(function(){
  const P=window.LGPlayer,box=document.querySelector('[data-player-now]');
  if(!P||!box)return;
  const art=box.querySelector('img'),title=box.querySelector('.agenda-now-title'),artist=box.querySelector('.agenda-now-artist'),button=box.querySelector('button');
  function render(){
    const x=P.current(),playing=P.isPlaying();
    art.src=P.artworkUrl(x.artwork);title.textContent=x.title;artist.textContent=x.artist;
    button.dataset.state=playing?'playing':'paused';
    button.setAttribute('aria-label',t(playing?'music.pause':'music.play')+': '+x.title);
    box.classList.toggle('is-playing',playing);
  }
  button.addEventListener('click',()=>P.toggle());
  P.on(type=>{if(type!=='time')render()});
  document.addEventListener('lg:language',render);
  render();
})();
