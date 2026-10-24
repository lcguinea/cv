// /music/: the large player and the playlist are a view of the global engine (js/player.js); they hold no audio.
(function(){
  const P=window.LGPlayer;
  if(!P)return;
  const $=id=>document.getElementById(id);
  const catalog=$('catalog'),search=$('search'),role=$('role'),count=$('count'),empty=$('empty'),toggle=$('toggle'),seek=$('seek'),volume=$('np-volume'),statusLine=$('np-status');
  const artistFilter=$('artist'),sort=$('sort'),clear=$('clear'),chipBoxes={mood:$('moods'),genre:$('genres')};
  const tracks=P.tracks;
  let visible=[];
  // Explore: mood and genre come only from the owner's human review (empty lists for works not yet reviewed) and
  // `artists` is the credited artist list. Chips of one group combine with OR (any selected mood, any selected
  // genre); groups combine with AND with each other and with artist, credit and search.
  const moodsOf=x=>Array.isArray(x.moods)?x.moods:[],genresOf=x=>Array.isArray(x.genres)?x.genres:[];
  const artistsOf=x=>Array.isArray(x.artists)&&x.artists.length?x.artists:[x.artist];
  const FACETS={mood:moodsOf,genre:genresOf};
  const chosen={mood:new Set(),genre:new Set()};
  function facetKey(group,id){return 'music.'+group+'_'+id}
  function collator(){return new Intl.Collator(window.currentLanguage==='es'?'es':'en',{sensitivity:'base',numeric:true})}
  // Chips follow the data: only values some recording has, the most frequent first, in a fixed order.
  function termsOf(group){
    const counts=new Map();
    tracks.forEach(x=>FACETS[group](x).forEach(id=>counts.set(id,(counts.get(id)||0)+1)));
    return [...counts].sort((a,b)=>b[1]-a[1]||(a[0]<b[0]?-1:1)).map(([id])=>id);
  }
  function buildChips(){
    Object.keys(chipBoxes).forEach(group=>{
      const box=chipBoxes[group];
      if(!box)return;
      box.innerHTML=termsOf(group).map(id=>`<button type="button" class="chip" data-group="${group}" data-id="${esc(id)}" aria-pressed="false"><span class="chip-label" data-i18n="${facetKey(group,id)}">${esc(t(facetKey(group,id)))}</span><span class="chip-count"></span></button>`).join('');
      box.closest('.explore-group').hidden=!box.children.length;
    });
    const reviewed=tracks.filter(x=>moodsOf(x).length||genresOf(x).length).length;
    const note=$('style-note');
    if(note){note.hidden=!reviewed;note.textContent=(reviewed<tracks.length?t('music.styleNote').replace('{n}',reviewed)+' ':'')+t('music.facetHint')}
  }
  function buildArtists(){
    if(!artistFilter)return;
    const counts=new Map();
    tracks.forEach(x=>artistsOf(x).forEach(name=>counts.set(name,(counts.get(name)||0)+1)));
    const c=collator(),current=artistFilter.value;
    artistFilter.innerHTML=`<option value="" data-i18n="music.allArtists">${esc(t('music.allArtists'))}</option>`+[...counts].sort((a,b)=>c.compare(a[0],b[0])).map(([name,n])=>`<option value="${esc(name)}">${esc(name)} (${n})</option>`).join('');
    artistFilter.value=current;
  }
  function matchesArtist(x){return !artistFilter||!artistFilter.value||artistsOf(x).includes(artistFilter.value)}
  function matchesGroup(x,group){return !chosen[group].size||[...chosen[group]].some(id=>FACETS[group](x).includes(id))}
  function matchesFacets(x,skip){return Object.keys(chosen).every(group=>group===skip||matchesGroup(x,group))}
  function filtering(){return !!(search.value.trim()||role.value||(artistFilter&&artistFilter.value)||chosen.mood.size||chosen.genre.size)}
  // Newest first by default; the curated selection and the other orders stay available in #sort.
  const DEFAULT_SORT='year-desc';
  if(sort)sort.value=DEFAULT_SORT;
  function changed(){return filtering()||!!(sort&&sort.value!==DEFAULT_SORT)}
  // Stable, predictable order: year or artist, then title, then the curated position. Undated recordings
  // (unreleased or self-published) close the list in both year directions.
  function ordered(list){
    const mode=sort?sort.value:DEFAULT_SORT,c=collator();
    const byTitle=(a,b)=>c.compare(tracks[a].title,tracks[b].title)||a-b;
    if(mode==='year-desc'||mode==='year-asc'){
      const dir=mode==='year-desc'?-1:1;
      return list.sort((a,b)=>{const ya=tracks[a].year,yb=tracks[b].year;return (ya==null)-(yb==null)||(ya!=null&&yb!=null?(ya-yb)*dir:0)||byTitle(a,b)});
    }
    if(mode==='artist-asc'||mode==='artist-desc'){
      const dir=mode==='artist-desc'?-1:1;
      return list.sort((a,b)=>c.compare(tracks[a].artist,tracks[b].artist)*dir||byTitle(a,b));
    }
    return list;
  }
  // A chip counts the recordings that carry it among those passing every other filter (its own group aside),
  // so under OR an unselected chip shows what it would contribute and is disabled only when that is nothing.
  function updateChips(base){
    Object.keys(chipBoxes).forEach(group=>{
      if(!chipBoxes[group])return;
      const pool=base.filter(i=>matchesFacets(tracks[i],group));
      chipBoxes[group].querySelectorAll('.chip').forEach(chip=>{
        const id=chip.dataset.id,on=chosen[group].has(id),n=pool.filter(i=>FACETS[group](tracks[i]).includes(id)).length;
        chip.setAttribute('aria-pressed',String(on));
        chip.disabled=!on&&n===0;
        chip.querySelector('.chip-count').textContent=n;
      });
    });
  }
  // «Show all recordings» clears the filters and keeps the chosen order; «Reset all» also restores the default order.
  function resetFilters(order){
    search.value='';role.value='';if(artistFilter)artistFilter.value='';
    chosen.mood.clear();chosen.genre.clear();
    if(order&&sort)sort.value=DEFAULT_SORT;
  }
  // Shareable state. The filters live in the query string with the catalogue's own values, never translated labels:
  // q (search), artist (credited name), credit (artist, producer, composer), mood and genre (comma-separated ids) and
  // sort (only when it is not the default). ?song=<work id> points at one recording: its preview's name without .mp3,
  // fixed by the catalogue and independent of order and titles. The language is the visitor's own and never travels in
  // the link; the hash (#jingles) and any other parameter are kept as they are. Without filters the URL stays /music/.
  const songId=x=>String(x.preview).replace(/\.mp3$/,'');
  const OWN=['song','q','artist','credit','mood','genre','sort'];
  const optionValues=select=>select?[...select.querySelectorAll('option')].map(o=>o.value).filter(Boolean):[];
  let linked=-1,notes=[],typing=false;
  function readUrl(){
    let params;
    try{params=new URLSearchParams(location.search)}catch(e){params=new URLSearchParams('')}
    const first=key=>{const value=params.getAll(key).map(v=>v.trim()).find(Boolean);return value||''};
    const state={q:first('q').slice(0,100),artist:'',credit:'',mood:[],genre:[],sort:DEFAULT_SORT,song:-1},ignored=[];
    const artist=first('artist');
    if(artist){
      // Exact name first; case and accents are forgiven only when that leaves one artist (Carla Calderon and Carla
      // Calderón are two people).
      const names=artistFilter?optionValues(artistFilter):[],only=list=>list.length===1?list[0]:'';
      state.artist=names.find(name=>name===artist)||only(names.filter(name=>name.toLowerCase()===artist.toLowerCase()))||only(names.filter(name=>norm(name)===norm(artist)));
      if(!state.artist)ignored.push('artist');
    }
    const credit=first('credit');
    if(credit){state.credit=optionValues(role).find(value=>value.toLowerCase()===credit.toLowerCase())||'';if(!state.credit)ignored.push('credit')}
    Object.keys(FACETS).forEach(group=>{
      const known=termsOf(group);
      params.getAll(group).join(',').split(',').map(v=>v.trim().toLowerCase()).filter(Boolean).forEach(id=>{
        if(known.includes(id)){if(!state[group].includes(id))state[group].push(id)}else ignored.push(group);
      });
    });
    const order=first('sort');
    if(order){if(optionValues(sort).includes(order))state.sort=order;else ignored.push('sort')}
    const song=first('song');
    if(song){state.song=tracks.findIndex(x=>songId(x)===song);if(state.song<0)state.missing=true}
    state.ignored=ignored;
    return state;
  }
  function applyState(state){
    search.value=state.q;role.value=state.credit;if(artistFilter)artistFilter.value=state.artist;
    Object.keys(chosen).forEach(group=>{chosen[group].clear();state[group].forEach(id=>chosen[group].add(id))});
    if(sort)sort.value=state.sort;
    linked=state.song;
  }
  const enc=encodeURIComponent;
  function filterQuery(){
    const parts=[];
    if(search.value.trim())parts.push('q='+enc(search.value.trim()));
    if(artistFilter&&artistFilter.value)parts.push('artist='+enc(artistFilter.value));
    if(role.value)parts.push('credit='+enc(role.value.toLowerCase()));
    Object.keys(chosen).forEach(group=>{if(chosen[group].size)parts.push(group+'='+[...chosen[group]].map(enc).join(','))});
    if(sort&&sort.value!==DEFAULT_SORT)parts.push('sort='+enc(sort.value));
    return parts;
  }
  function pageUrl(parts){const url=new URL(location.href);url.search=parts.length?'?'+parts.join('&'):'';url.hash='';return url.href}
  function writeUrl(replace){
    const parts=(linked>=0?['song='+enc(songId(tracks[linked]))]:[]).concat(filterQuery());
    let params;
    try{params=new URLSearchParams(location.search)}catch(e){params=new URLSearchParams('')}
    params.forEach((value,key)=>{if(!OWN.includes(key))parts.push(enc(key)+'='+enc(value))});
    const next=(parts.length?'?'+parts.join('&'):'')+location.hash;
    if(next===location.search+location.hash||!window.history||!history.pushState)return;
    try{history[replace?'replaceState':'pushState'](null,'',location.pathname+next)}catch(e){}
  }
  // A change made on the page leaves the shared link behind: the recording it pointed at and its notes. Typing in the
  // search box updates one history entry instead of adding one per key.
  function commit(fromSearch){
    const replace=!!fromSearch&&typing;
    typing=!!fromSearch;
    linked=-1;notes=[];renderList();showNotes();writeUrl(replace);
  }
  // Opening, reloading or stepping through history: the URL decides. A shared recording wins over filters that would
  // hide it (they are cleared and the notice says so); unknown values and recordings that are not (or no longer) in the
  // catalogue are left out and reported instead of producing a misleading list, and the URL is rewritten without them.
  function restore(initial){
    const state=readUrl();
    applyState(state);
    renderList();
    const cleared=linked>=0&&!visible.includes(linked);
    if(cleared){resetFilters(false);renderList()}
    notes=[];
    if(linked>=0)notes.push(['music.linkFound',linked]);
    if(cleared)notes.push(['music.linkCleared']);
    if(state.missing)notes.push(['music.linkMissing']);
    if(state.ignored.length)notes.push(['music.linkIgnored']);
    showNotes();
    if(initial)writeUrl(true);
    // The engine opened on the shared recording (js/player.js); a history step only selects it when nothing sounds.
    else if(linked>=0&&!P.isPlaying()&&P.index()!==linked)P.select(linked,false);
    return state;
  }
  const notice=$('link-notice');
  function showNotes(){
    if(!notice)return;
    const lines=notes.concat(prompt==='selection'?[['music.selectionBlocked']]:[]);
    notice.textContent=lines.map(([key,i])=>{const x=tracks[i];return t(key).replace('{title}',x?x.title:'').replace('{artist}',x?x.artist:'').replace('{n}',visible.length)}).join(' ');
    notice.hidden=!lines.length;
  }
  // Playing what a link points at. The filters are the queue: Next, Previous, the end of a preview and the random picks
  // of the engine stay among the recordings they show, and without filters the whole catalogue plays as usual. A
  // recording that stops matching keeps playing until it ends or the visitor moves on; the next one comes from the new
  // selection. An empty selection plays nothing more. Opening a link tries to start its recording (or the first of its
  // selection) at once; when the browser refuses sound without a gesture, the player stays on it and a Play button on
  // the cover (one recording) or beside the results (a selection) starts it with one press.
  let prompt='';
  const startSong=$('np-start'),startSelection=$('play-selection');
  function syncQueue(){P.setQueue(filtering()?visible.slice():null)}
  function updatePrompt(){
    if(prompt&&P.isPlaying()){prompt='';showNotes()}
    const x=P.current();
    if(startSong){startSong.hidden=prompt!=='song';startSong.setAttribute('aria-label',t('music.play')+': '+x.title)}
    if(startSelection){startSelection.hidden=prompt!=='selection'||!visible.length;startSelection.setAttribute('aria-label',t('music.playSelectionLabel').replace('{n}',visible.length))}
  }
  function openLink(state){
    if(!P.linkPending())return;
    const first=linked>=0?linked:filtering()&&visible.length?visible[0]:-1;
    // A recording that is not there, or a hash with its own destination, selects without playing.
    if(first<0||state.missing||location.hash){P.settleLink(first);return}
    P.openLink(first).then(ok=>{
      if(ok||P.isPlaying()||P.failed())return;
      prompt=linked>=0?'song':'selection';
      updatePlayer();showNotes();
    });
  }
  if(startSong)startSong.addEventListener('click',()=>P.play());
  if(startSelection)startSelection.addEventListener('click',()=>P.select(visible.includes(P.index())?P.index():visible[0],true));
  // Links with a preview: WhatsApp and social networks show the title, description and image of the URL itself without
  // running JavaScript, so a recording or a usual selection is shared as its own static page (js/share-pages.js, made by
  // tools/build_share_pages.js), which opens /music/ with the same parameters. Other selections (search text, rarer
  // combinations) are shared as they are and preview as /music/. The order travels with a page as ?sort=.
  const SHARE_PAGES=window.SHARE_PAGES||{},siteRoot=new URL('../',location.href);
  function shareKey(){
    if(search.value.trim())return '';
    const parts=[];
    if(artistFilter&&artistFilter.value)parts.push('artist='+enc(artistFilter.value));
    if(role.value)parts.push('credit='+enc(role.value.toLowerCase()));
    ['genre','mood'].forEach(group=>{if(chosen[group].size)parts.push(group+'='+[...chosen[group]].sort().map(enc).join(','))});
    return parts.join('&');
  }
  function viewLink(){
    const page=SHARE_PAGES[shareKey()];
    if(!page)return pageUrl(filterQuery());
    return new URL(page,siteRoot).href+(sort&&sort.value!==DEFAULT_SORT?'?sort='+enc(sort.value):'');
  }
  function songLink(id){const page=SHARE_PAGES['song='+enc(id)];return page?new URL(page,siteRoot).href:pageUrl(['song='+enc(id)])}
  // Share copies a link. Without a clipboard (an insecure origin, a refused permission, an older browser) the link
  // appears selected in a field to copy by hand. Copying is announced and shown on the button for a moment.
  const shareView=$('share-view'),shareStatus=$('share-status'),fallback=$('share-fallback'),fallbackUrl=$('share-url');
  const fallbackHome=fallback&&fallback.parentNode;
  let opener=null,statusTimer=0;
  function share(url,button){
    let copy;
    try{copy=navigator.clipboard&&navigator.clipboard.writeText&&window.isSecureContext!==false?Promise.resolve(navigator.clipboard.writeText(url)):Promise.reject(new Error('clipboard'))}catch(e){copy=Promise.reject(e)}
    return copy.then(()=>copied(button),()=>openFallback(url,button));
  }
  function copied(button){
    closeFallback(false);
    const text=button.querySelector('.share-text');
    button.dataset.state='copied';
    if(text)text.textContent=t('music.shareDone');
    if(shareStatus)shareStatus.textContent=t('music.shareCopied');
    clearTimeout(statusTimer);
    statusTimer=setTimeout(()=>{
      if(shareStatus)shareStatus.textContent='';
      document.querySelectorAll('[data-state="copied"]').forEach(b=>{delete b.dataset.state;const s=b.querySelector('.share-text');if(s)s.textContent=t('music.share')});
    },2500);
  }
  function openFallback(url,button){
    if(!fallback)return;
    opener=button;
    (button.closest('#catalog > li')||fallbackHome).appendChild(fallback);
    fallbackUrl.value=url;
    fallback.hidden=false;
    fallbackUrl.focus();
    if(fallbackUrl.select)fallbackUrl.select();
  }
  function closeFallback(refocus){
    if(!fallback)return;
    fallback.hidden=true;
    if(fallback.parentNode!==fallbackHome)fallbackHome.appendChild(fallback);
    if(refocus&&opener&&document.body.contains(opener))opener.focus();
    opener=null;
  }
  if(fallback){
    $('share-close').addEventListener('click',()=>closeFallback(true));
    fallback.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeFallback(true)}});
  }
  if(shareView){shareView.hidden=false;shareView.addEventListener('click',()=>share(viewLink(),shareView))}
  function norm(value){return String(value||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
  function esc(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function roleKey(name){return 'music.role'+String(name).replace(/[^A-Za-z]/g,'')}
  function typeKey(name){return 'music.type'+String(name).replace(/[^A-Za-z]/g,'')}
  function versionKey(name){return 'music.version'+String(name).replace(/[^A-Za-z]/g,'')}
  // The playlist line flags recordings without a commercial release (unreleased or self-published)
  // and versions; commercial releases show their year instead.
  const NON_COMMERCIAL=['Unreleased','SelfPublished'];
  function tags(x){return [NON_COMMERCIAL.includes(x.releaseType)?t(typeKey(x.releaseType)):'',x.version?t(versionKey(x.version)):''].filter(Boolean)}
  function pad(n){return String(n).padStart(2,'0')}
  function clock(seconds){const s=Math.max(0,Math.floor(Number.isFinite(seconds)?seconds:0));return Math.floor(s/60)+':'+pad(s%60)}
  // Composer gathers songwriting and co-writing credits, Producer production and co-production; Artist matches directly.
  const FACET_CREDITS={Composer:['Songwriter','Co-writer'],Producer:['Producer','Co-producer']};
  function matchesRole(x,value){if(!value)return true;const credits=FACET_CREDITS[value]||[value];return x.role===value||credits.some(c=>x.roles.includes(c))}
  function matches(x,q){return !q||norm([x.title,x.artist,x.year??'',x.releaseType,t(typeKey(x.releaseType)),x.version||'',x.version?t(versionKey(x.version)):'',x.role,x.roles.join(' '),x.roles.map(r=>t(roleKey(r))).join(' '),moodsOf(x).map(id=>t(facetKey('mood',id))).join(' '),genresOf(x).map(id=>t(facetKey('genre',id))).join(' ')].join(' ')).includes(q)}
  // Certified destinations in the public data: streaming releases and full recordings on YouTube or
  // SoundCloud. A platform without a URL gets no link.
  const PLATFORMS=[['spotify','Spotify'],['appleMusic','Apple Music'],['youtube','YouTube'],['soundcloud','SoundCloud']];
  function urlsOf(x){return {spotify:x.spotify,appleMusic:x.appleMusic,youtube:x.youtube,soundcloud:x.soundcloud}}
  function hasLinks(x){const urls=urlsOf(x);return PLATFORMS.some(([key])=>urls[key])}
  function platformLinks(x){
    const urls=urlsOf(x);
    return PLATFORMS.filter(([key])=>urls[key]).map(([key,name])=>{
      const url=urls[key];
      const label=t('music.platformLink').replace('{title}',x.title).replace('{artist}',x.artist).replace('{platform}',name)+t('ui.newTab');
      return `<li><a class="platform-link" href="${esc(url)}" target="_blank" rel="noopener" data-platform="${key}" aria-label="${esc(label)}">${name}<span aria-hidden="true"> ↗</span></a></li>`;
    }).join('');
  }
  function renderList(){
    const q=norm(search.value);
    const base=tracks.map((x,i)=>i).filter(i=>matchesRole(tracks[i],role.value)&&matches(tracks[i],q)&&matchesArtist(tracks[i]));
    visible=ordered(base.filter(i=>matchesFacets(tracks[i])));
    updateChips(base);
    count.textContent=visible.length;
    empty.hidden=visible.length>0;
    if(clear)clear.disabled=!changed();
    $('prev').disabled=$('next').disabled=!visible.length;
    syncQueue();
    if(fallback&&catalog.contains(fallback))closeFallback(false);
    catalog.innerHTML=visible.map((i,at)=>{const x=tracks[i];return `<li${i===linked?' class="is-linked"':''}><button type="button" class="pl-row" data-index="${i}" aria-current="false"><span class="pl-num">${pad(at+1)}</span><img class="pl-thumb" src="${P.artworkUrl(x.artwork)}" alt="" loading="lazy" width="56" height="56"><span class="pl-main"><span class="pl-title">${esc(x.title)}</span><span class="pl-artist">${[x.artist].concat(tags(x)).map(esc).join(' · ')}</span></span><span class="pl-roles">${x.roles.map(r=>`<span data-i18n="${roleKey(r)}">${esc(t(roleKey(r)))}</span>`).join(' · ')}</span><span class="pl-year">${x.year??''}</span><span class="pl-state"></span></button><ul class="pl-links">${platformLinks(x)}<li><button type="button" class="pl-share" data-song="${esc(songId(x))}" aria-label="${esc(t('music.shareSong').replace('{title}',x.title).replace('{artist}',x.artist))}"><span class="share-text">${esc(t('music.share'))}</span></button></li></ul></li>`}).join('');
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
    $('np-year').textContent=x.year??'';
    $('np-year-field').hidden=x.year==null;
    updatePlayer();updateTime();
  }
  function updateLabels(){
    const x=P.current();
    toggle.setAttribute('aria-label',t(P.isPlaying()?'music.pause':'music.play')+': '+x.title);
    $('np-art').alt=t('music.artworkAlt')+': '+x.title;
    $('np-type').textContent=t(typeKey(x.releaseType));
    $('np-version').textContent=x.version?t(versionKey(x.version)):'';
    $('np-version-field').hidden=!x.version;
    seek.setAttribute('aria-valuetext',clock(P.time())+' '+t('music.of')+' '+clock(P.duration()));
    $('np-roles').innerHTML=x.roles.map(r=>`<li data-i18n="${roleKey(r)}">${esc(t(roleKey(r)))}</li>`).join('');
    $('np-links').innerHTML=platformLinks(x);
    const style=genresOf(x).map(id=>facetKey('genre',id)).concat(moodsOf(x).map(id=>facetKey('mood',id)));
    $('np-style').innerHTML=style.map(key=>`<li data-i18n="${key}">${esc(t(key))}</li>`).join('');
    $('np-style-field').hidden=!style.length;
    $('np-links-field').hidden=!hasLinks(x);
    if(P.failed())statusLine.textContent=t('music.loadError');
  }
  function updatePlayer(){
    const x=P.current(),playing=P.isPlaying();
    toggle.dataset.state=playing?'playing':'paused';
    if(!P.failed())statusLine.textContent=playing?t('music.playing')+': '+x.title+' · '+x.artist:prompt?t('music.autoplayBlocked'):(P.time()>0?t('music.paused')+': '+x.title:'');
    volume.value=String(P.muted()?0:P.volume());
    volume.setAttribute('aria-valuetext',t('player.percent').replace('{n}',Math.round((P.muted()?0:P.volume())*100)));
    updateLabels();
    updateRows();
    updatePrompt();
  }
  function updateTime(){
    const duration=P.duration();
    seek.max=duration;seek.value=P.time()||0;seek.disabled=!duration;
    $('time-current').textContent=clock(P.time());$('time-total').textContent=clock(duration);
    seek.setAttribute('aria-valuetext',clock(P.time())+' '+t('music.of')+' '+clock(duration));
  }
  function step(delta){
    const list=visible,at=list.indexOf(P.index());
    if(!list.length)return;
    const next=at<0?list[delta>0?0:list.length-1]:list[(at+delta+list.length)%list.length];
    P.select(next,P.isPlaying());
  }
  toggle.addEventListener('click',()=>P.toggle());
  $('prev').addEventListener('click',()=>step(-1));
  $('next').addEventListener('click',()=>step(1));
  seek.addEventListener('input',()=>P.seek(seek.value));
  volume.addEventListener('input',()=>P.setVolume(volume.value));
  if(!P.volumeSupported)$('np-volume-field').hidden=true;
  catalog.addEventListener('click',event=>{const button=event.target.closest('.pl-share');if(button){share(songLink(button.dataset.song),button);return}const row=event.target.closest('.pl-row');if(!row)return;const i=Number(row.dataset.index);if(i===P.index()&&P.isPlaying())P.pause();else P.select(i,true)});
  catalog.addEventListener('keydown',event=>{
    const rows=[...catalog.querySelectorAll('.pl-row')],at=rows.indexOf(document.activeElement);
    const target={ArrowDown:at+1,ArrowUp:at-1,Home:0,End:rows.length-1}[event.key];
    if(at<0||target===undefined||!rows[target])return;
    event.preventDefault();rows[target].focus();
  });
  search.addEventListener('input',()=>commit(true));role.addEventListener('change',()=>commit());
  if(artistFilter)artistFilter.addEventListener('change',()=>commit());
  if(sort)sort.addEventListener('change',()=>commit());
  Object.keys(chipBoxes).forEach(group=>{if(chipBoxes[group])chipBoxes[group].addEventListener('click',event=>{
    const chip=event.target.closest('.chip');if(!chip||chip.disabled)return;
    const id=chip.dataset.id;if(chosen[group].has(id))chosen[group].delete(id);else chosen[group].add(id);
    commit();
  })});
  // Reset all returns to the initial state; focus moves to the first filter so it is not lost on a now-disabled button.
  if(clear){clear.hidden=false;clear.addEventListener('click',()=>{resetFilters(true);commit();const first=[...document.querySelectorAll('.catalog-explore .chip')].find(chip=>!chip.disabled)||search;first.focus()})}
  const reset=$('reset');
  if(reset)reset.addEventListener('click',()=>{resetFilters();commit();const row=catalog.querySelector('.pl-row');(row||search).focus()});
  P.on(type=>{if(type==='track')renderTrack();else if(type==='time')updateTime();else updatePlayer()});
  const cover=$('music-cover');
  function updateCover(){if(cover)cover.alt=t('music.coverAlt')}
  document.addEventListener('lg:language',()=>{updateCover();buildChips();buildArtists();renderList();updatePlayer();showNotes()});
  $('total').textContent=tracks.length;
  updateCover();buildChips();buildArtists();
  const opened=restore(true);renderTrack();openLink(opened);
  // Back and Forward between views of the catalogue restore them without reloading; what is playing is never interrupted.
  window.addEventListener('popstate',()=>{typing=false;restore(false)});
  // Where a link lands, once the layout is final and only when the link was just opened (a reload or a history step
  // keeps the position the browser restores, and a hash such as #jingles keeps its own destination): a recording opens
  // the large player on it, with the focus on Play; filters open their results.
  function reveal(){
    const entry=window.performance&&performance.getEntriesByType?performance.getEntriesByType('navigation')[0]:null;
    if(location.hash||(entry&&entry.type!=='navigate'))return;
    const target=linked>=0?$('player'):filtering()?$('playlist-heading'):null;
    if(!target)return;
    if(target.scrollIntoView)target.scrollIntoView({block:'start',behavior:'instant'});
    if(linked>=0)try{toggle.focus({preventScroll:true})}catch(e){toggle.focus()}
  }
  if(document.readyState==='complete')reveal();else window.addEventListener('load',()=>requestAnimationFrame(reveal));
  // Jingles (#jingles) use their own native players: one at a time. The engine already pauses when any of them plays.
  document.addEventListener('play',event=>{const own=event.target;if(!own.closest||!own.closest('.jingle'))return;document.querySelectorAll('.jingle audio').forEach(media=>{if(media!==own)media.pause()})},true);
})();
