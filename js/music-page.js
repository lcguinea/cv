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
    renderList();
  }
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
    catalog.innerHTML=visible.map((i,at)=>{const x=tracks[i];return `<li><button type="button" class="pl-row" data-index="${i}" aria-current="false"><span class="pl-num">${pad(at+1)}</span><img class="pl-thumb" src="${P.artworkUrl(x.artwork)}" alt="" loading="lazy" width="56" height="56"><span class="pl-main"><span class="pl-title">${esc(x.title)}</span><span class="pl-artist">${[x.artist].concat(tags(x)).map(esc).join(' · ')}</span></span><span class="pl-roles">${x.roles.map(r=>`<span data-i18n="${roleKey(r)}">${esc(t(roleKey(r)))}</span>`).join(' · ')}</span><span class="pl-year">${x.year??''}</span><span class="pl-state"></span></button>${hasLinks(x)?`<ul class="pl-links">${platformLinks(x)}</ul>`:''}</li>`}).join('');
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
    if(!P.failed())statusLine.textContent=playing?t('music.playing')+': '+x.title+' · '+x.artist:(P.time()>0?t('music.paused')+': '+x.title:'');
    volume.value=String(P.muted()?0:P.volume());
    volume.setAttribute('aria-valuetext',t('player.percent').replace('{n}',Math.round((P.muted()?0:P.volume())*100)));
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
  if(artistFilter)artistFilter.addEventListener('change',renderList);
  if(sort)sort.addEventListener('change',renderList);
  Object.keys(chipBoxes).forEach(group=>{if(chipBoxes[group])chipBoxes[group].addEventListener('click',event=>{
    const chip=event.target.closest('.chip');if(!chip||chip.disabled)return;
    const id=chip.dataset.id;if(chosen[group].has(id))chosen[group].delete(id);else chosen[group].add(id);
    renderList();
  })});
  // Reset all returns to the initial state; focus moves to the first filter so it is not lost on a now-disabled button.
  if(clear){clear.hidden=false;clear.addEventListener('click',()=>{resetFilters(true);const first=[...document.querySelectorAll('.catalog-explore .chip')].find(chip=>!chip.disabled)||search;first.focus()})}
  const reset=$('reset');
  if(reset)reset.addEventListener('click',()=>{resetFilters();const row=catalog.querySelector('.pl-row');(row||search).focus()});
  P.on(type=>{if(type==='track')renderTrack();else if(type==='time')updateTime();else updatePlayer()});
  const cover=$('music-cover');
  function updateCover(){if(cover)cover.alt=t('music.coverAlt')}
  document.addEventListener('lg:language',()=>{updateCover();buildChips();buildArtists();renderList();updatePlayer()});
  $('total').textContent=tracks.length;
  updateCover();buildChips();buildArtists();renderList();renderTrack();
})();
