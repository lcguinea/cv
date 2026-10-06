// Global music engine shared by every page. It owns the only <audio> element, so the bottom bar and the large
// player on /music/ are two views of one state and never sound together. Track, position and play state survive
// page changes in sessionStorage; volume and mute live in localStorage. Nothing sounds without a user gesture:
// a session starts on a random, paused track, and resuming after a page change is only attempted and may be refused.
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
  let index=-1,failed=false,pendingTime=0,knownDuration=0,lastSave=0;
  function emit(type){listeners.forEach(fn=>fn(type))}
  function isPlaying(){return !audio.paused&&!audio.ended}
  function time(){return audio.readyState>0?audio.currentTime:pendingTime}
  function duration(){return Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:knownDuration}
  // A random index, never `exclude` when there is an alternative.
  function randomIndex(exclude){
    if(exclude<0||tracks.length<2)return Math.floor(Math.random()*tracks.length);
    const i=Math.floor(Math.random()*(tracks.length-1));
    return i>=exclude?i+1:i;
  }
  function save(){
    if(index<0)return;
    lastSave=Date.now();
    session.set(SESSION_KEY,JSON.stringify({preview:tracks[index].preview,time:time(),duration:duration(),playing:isPlaying(),tab}));
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
  ['play','pause'].forEach(type=>audio.addEventListener(type,()=>{save();emit('state')}));
  // A finished preview moves on to another random one; the element already holds the user's permission to play.
  audio.addEventListener('ended',()=>{select(randomIndex(index),true)});
  ['timeupdate','durationchange','loadedmetadata','emptied'].forEach(type=>audio.addEventListener(type,()=>{if(type==='timeupdate'&&Date.now()-lastSave>1000)save();emit('time')}));
  audio.addEventListener('error',()=>{if(audio.getAttribute('src')){failed=true;emit('state')}});
  window.addEventListener('pagehide',save);
  // Any other media element that starts on this page pauses the engine.
  document.addEventListener('play',event=>{if(event.target!==audio)audio.pause()},true);
  // Other tabs: whichever starts playing last is the only one that sounds.
  let channel=null;
  try{if(window.BroadcastChannel){channel=new BroadcastChannel('lg-player');channel.onmessage=event=>{if(event.data&&event.data.type==='play')audio.pause()}}}catch(e){channel=null}
  audio.addEventListener('play',()=>{if(channel)channel.postMessage({type:'play'})});

  // Restore this tab's session, or start a new one on a random track without sound.
  function readSaved(){
    let saved=null;
    try{saved=JSON.parse(session.get(SESSION_KEY)||'null')}catch(e){saved=null}
    const i=saved?tracks.findIndex(x=>x.preview===saved.preview):-1;
    return i>=0?{index:i,time:Math.max(0,Number(saved.time)||0),duration:Math.max(0,Number(saved.duration)||0),playing:saved.playing===true&&saved.tab===tab}:null;
  }
  function resume(saved){
    const policy=navigator.getAutoplayPolicy?navigator.getAutoplayPolicy('mediaelement'):'';
    if(saved.playing&&policy!=='disallowed'){audio.preload='auto';start()}else save();
  }
  const saved=readSaved();
  if(saved){load(saved.index,saved.time,saved.duration);resume(saved)}
  else{load(randomIndex(-1),0,0);save()}
  // Back/forward cache: this page comes back as it was left, so it catches up with what later pages saved.
  window.addEventListener('pageshow',event=>{
    if(!event.persisted)return;
    const latest=readSaved();
    if(!latest)return;
    if(latest.index!==index)load(latest.index,latest.time,latest.duration);
    else if(Math.abs(time()-latest.time)>.5)seek(latest.time);
    if(!latest.playing)audio.pause();
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
    volume.setAttribute('aria-valuetext',Math.round((P.muted()?0:P.volume())*100)+' %');
    if(!stage)status.textContent=P.failed()?t('music.loadError'):(playing?t('music.playing')+': '+x.title+' · '+x.artist:'');
  }
  function tick(){const d=P.duration();progress.style.width=(d?Math.min(100,P.time()/d*100):0)+'%'}
  toggle.addEventListener('click',()=>P.toggle());
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
