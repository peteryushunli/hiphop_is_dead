/* Aggregate data only. No lyrics, tracking, dependencies, or network requests. */
(() => {
  'use strict';
  const D = window.HIPHOP_DATA;
  const el = id => document.getElementById(id);
  if (!D) { el('loading-error').hidden = false; return; }
  const fmt = n => Number(n).toLocaleString('en-US');
  const ns = 'http://www.w3.org/2000/svg';
  const color = {rap:'#68458a',other:'#ba542c',ink:'#252822',muted:'#62665d',line:'#cecec2'};
  const tip = el('tooltip');
  let selectedWord = 'money';
  let selectedArtist = D.artists.some(a=>a.artist==='Kendrick Lamar') ? 'Kendrick Lamar' : D.artists[0]?.artist;
  function node(tag, attrs={}, text) {
    const n = document.createElementNS(ns,tag);
    Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));
    if (text !== undefined) n.textContent=text;
    return n;
  }
  function add(svg,tag,attrs,text) {const n=node(tag,attrs,text);svg.append(n);return n;}
  function size(id, height) {const svg=el(id); const w=Math.max(280,svg.parentElement.clientWidth);svg.replaceChildren();svg.setAttribute('viewBox',`0 0 ${w} ${height}`);svg.style.height=`${height}px`;return {svg,w,h:height};}
  function showTip(event,text) {tip.textContent=text;tip.hidden=false;tip.style.left=`${Math.max(8,Math.min(event.clientX+14,innerWidth-tip.offsetWidth-12))}px`;tip.style.top=`${Math.max(8,Math.min(event.clientY+14,innerHeight-tip.offsetHeight-12))}px`;}
  function hideTip() {tip.hidden=true;}
  function hovered(n,text) {n.addEventListener('pointermove',e=>showTip(e,text));n.addEventListener('pointerleave',hideTip);}
  function line(svg,x1,y1,x2,y2,extra={}){return add(svg,'line',{x1,y1,x2,y2,...extra});}
  function option(select,value,label=value){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
  function yearTicks(w){return w<500 ? [1990,2000,2010,2020,2026] : [1990,1995,2000,2005,2010,2015,2020,2026];}
  function dateAxis(svg,w,h,left=54,right=16,bottom=38) {
    const x=y=>left+(y-1990)/36*(w-left-right);
    for(const year of yearTicks(w))add(svg,'text',{x:x(year),y:h-bottom+20,'text-anchor':year===1990?'start':year===2026?'end':'middle'},year);
    return x;
  }
  const S=D.status;
  el('build-state').textContent=S.complete?'Collected sample · exploratory':'Collection in progress · provisional';
  el('rap-count').textContent=fmt(S.rap_songs);el('other-count').textContent=fmt(S.other_songs);
  el('artist-count').textContent=fmt(S.artists_observed);el('token-count').textContent=(S.total_tokens/1e6).toFixed(1)+'m';
  el('coverage-notice').textContent=`${S.cohort_size} artists in the original-roster-plus-additions cohort. ${S.historical_shards_downloaded}/${S.historical_shards_expected} historical files and ${S.recent_artists_complete}/${S.recent_artists_expected} recent artist collections complete. ${S.missing_cohort_artists.length} cohort artists have no retained songs. Collection changes after 2022; all rankings describe this sample.`;
  el('provenance').textContent=`Built ${S.built_at.slice(0,10)} · source revision ${S.source_revision} · random seed 42 · ${D.artists.length} hip-hop artists qualify for the similarity map.`;

  function describeWord(r) {
    if(!r){el('word-detail').textContent='No eligible word selected.';return;}
    el('word-detail').textContent=`“${r.word}” · ${r.rap_per_10k.toFixed(2)} uses per 10,000 words in hip-hop, ${r.other_per_10k.toFixed(2)} elsewhere · ${fmt(r.rap_songs)} hip-hop songs across ${r.rap_artists} artists.`;
  }
  function drawWords() {
    const period=D.periods[el('period').value];
    const mode=el('ranking-mode').value;
    const ranked=[...period.words].filter(r=>r[mode]!==null).sort((a,b)=>b[mode]-a[mode]);
    el('word-list').replaceChildren();
    for(const r of ranked.slice(0,15)){
      const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.setAttribute('aria-pressed',r.word===selectedWord);
      const word=document.createElement('span');word.className='word';word.textContent=r.word;
      const ratio=document.createElement('span');ratio.className='ratio';ratio.textContent=r[mode].toFixed(1)+'×';
      button.append(word,ratio);button.addEventListener('click',()=>{selectedWord=r.word;describeWord(r);if([...el('trend-word').options].some(o=>o.value===r.word)){el('trend-word').value=r.word;drawTrend();}drawWords();});li.append(button);el('word-list').append(li);
    }
    el('support-note').textContent=`At least ${fmt(period.minimum_rap_count||0)} hip-hop occurrences, 10 songs and 5 artists. ${fmt(period.songs.rap||0)} hip-hop songs and ${fmt(period.songs.other||0)} comparison songs in this period. Ratios use 0.5-count smoothing.`;
    const {svg,w,h}=size('scatter',Math.min(430,Math.max(310,el('scatter').parentElement.clientWidth*.75)));
    const left=57,bottom=52,top=15,right=14;
    const max=Math.max(100,...period.words.flatMap(r=>[r.rap_per_10k,r.other_per_10k]));
    const lo=-3,hi=Math.ceil(Math.log10(max));
    const scale=v=>(Math.log10(Math.max(.001,v))-lo)/(hi-lo);
    const x=v=>left+scale(v)*(w-left-right),y=v=>h-bottom-scale(v)*(h-bottom-top);
    for(let p=lo;p<=hi;p++){
      const v=10**p;if(w<450&&p%2!==0)continue;
      line(svg,x(v),top,x(v),h-bottom,{class:'grid'});line(svg,left,y(v),w-right,y(v),{class:'grid'});
      add(svg,'text',{x:x(v),y:h-bottom+19,'text-anchor':'middle'},v>=1?fmt(v):String(v));
      add(svg,'text',{x:left-8,y:y(v)+4,'text-anchor':'end'},v>=1?fmt(v):String(v));
    }
    line(svg,x(.001),y(.001),x(10**hi),y(10**hi),{stroke:color.muted,'stroke-dasharray':'3 4'});
    const selected=period.words.find(r=>r.word===selectedWord);
    for(const r of period.words){
      const dot=add(svg,'circle',{cx:x(r.rap_per_10k),cy:y(r.other_per_10k),r:r.word===selectedWord?6:2.6,fill:r.word===selectedWord?color.orange:color.rap,opacity:r.word===selectedWord?1:.4});
      dot.dataset.word=r.word;
    }
    add(svg,'text',{x:(left+w-right)/2,y:h-7,'text-anchor':'middle',class:'axis-label'},'Hip-hop · occurrences per 10,000 words');
    add(svg,'text',{transform:`translate(13 ${(top+h-bottom)/2}) rotate(-90)`,'text-anchor':'middle',class:'axis-label'},'Other genres · per 10,000 words');
    const hit=add(svg,'rect',{x:left,y:top,width:w-left-right,height:h-bottom-top,fill:'transparent'});
    const nearest=e=>{const rect=svg.getBoundingClientRect(),px=(e.clientX-rect.left)*w/rect.width,py=(e.clientY-rect.top)*h/rect.height;let best=null,d=Infinity;for(const r of period.words){const dist=(x(r.rap_per_10k)-px)**2+(y(r.other_per_10k)-py)**2;if(dist<d){best=r;d=dist;}}return best;};
    hit.addEventListener('pointermove',e=>{const r=nearest(e);if(r)showTip(e,`${r.word} · hip-hop ${r.rap_per_10k.toFixed(2)} / other ${r.other_per_10k.toFixed(2)} per 10k`);});
    hit.addEventListener('pointerleave',hideTip);hit.addEventListener('click',e=>{const r=nearest(e);if(r){selectedWord=r.word;drawWords();}});
    describeWord(selected||ranked[0]);
  }
  const tracked=[...new Set(D.trends.map(r=>r.word))].sort();tracked.forEach(w=>option(el('trend-word'),w));el('trend-word').value=tracked.includes('money')?'money':tracked[0];
  function drawTrend(){
    const word=el('trend-word').value,rows=D.trends.filter(r=>r.word===word);
    const {svg,w,h}=size('trend',280),left=54,top=24,bottom=38;
    const x=dateAxis(svg,w,h),max=Math.max(1,...rows.map(r=>r.per_10k||0))*1.15,y=v=>h-bottom-v/max*(h-bottom-top);
    for(let i=0;i<5;i++){const v=max*i/4;line(svg,left,y(v),w-16,y(v),{class:'grid'});add(svg,'text',{x:left-9,y:y(v)+4,'text-anchor':'end'},v<10?v.toFixed(1):Math.round(v));}
    add(svg,'text',{x:left,y:12,class:'axis-label'},'Uses per 10,000 words');
    add(svg,'rect',{x:x(2022.5),y:top,width:x(2026)-x(2022.5),height:h-bottom-top,fill:color.orange,opacity:.07});
    let path='',pen=false;
    for(const r of rows){if(r.per_10k===null){pen=false;continue;}path+=`${pen?'L':'M'}${x(r.year)},${y(r.per_10k)} `;pen=true;}
    add(svg,'path',{d:path,fill:'none',stroke:color.rap,'stroke-width':2.5});
    for(const r of rows){if(r.per_10k===null)continue;add(svg,'circle',{cx:x(r.year),cy:y(r.per_10k),r:3,fill:color.rap});const hit=add(svg,'circle',{cx:x(r.year),cy:y(r.per_10k),r:12,fill:'transparent'});hovered(hit,`${r.year}: ${r.per_10k.toFixed(2)} per 10k · ${r.song_pct.toFixed(1)}% of ${fmt(r.songs)} songs contain “${word}”`);}
  }
  D.artists.forEach(a=>option(el('artist-select'),a.artist));el('artist-select').value=selectedArtist;
  function drawArtists(){
    const artist=D.artists.find(a=>a.artist===selectedArtist);if(!artist)return;
    const {svg,w,h}=size('artist-map',440),pad=32;
    const xs=D.artists.map(a=>a.x),ys=D.artists.map(a=>a.y),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
    const x=v=>pad+(v-xmin)/(xmax-xmin||1)*(w-2*pad),y=v=>pad+(v-ymin)/(ymax-ymin||1)*(h-2*pad);
    const close=new Set(artist.neighbors.map(a=>a.artist));
    for(const a of D.artists){if(close.has(a.artist))line(svg,x(artist.x),y(artist.y),x(a.x),y(a.y),{stroke:color.rap,opacity:.3,'stroke-width':1});}
    for(const a of D.artists){const active=a.artist===artist.artist,neighbor=close.has(a.artist);const dot=add(svg,'circle',{cx:x(a.x),cy:y(a.y),r:active?9:neighbor?6:4.5,fill:active?color.orange:color.rap,opacity:active||neighbor?1:.3});hovered(dot,`${a.artist} · ${fmt(a.songs)} songs`);dot.addEventListener('click',()=>{selectedArtist=a.artist;el('artist-select').value=selectedArtist;drawArtists();});}
    add(svg,'text',{x:Math.min(w-8,Math.max(8,x(artist.x))),y:y(artist.y)<38?y(artist.y)+26:y(artist.y)-15,'text-anchor':x(artist.x)>w*.7?'end':x(artist.x)<w*.3?'start':'middle',style:'fill:#252822;font-size:13px;font-weight:bold'},artist.artist);
    const side=el('artist-detail');side.replaceChildren();const h3=document.createElement('h3');h3.textContent=artist.artist;side.append(h3);const p=document.createElement('p');p.textContent=`${fmt(artist.songs)} songs · ${artist.first_year}–${artist.last_year} · ${fmt(artist.tokens)} words`;side.append(p);
    const title=document.createElement('h4');title.textContent='Signature vocabulary';side.append(title);const words=document.createElement('div');artist.words.forEach(w=>{const span=document.createElement('span');span.className='word-chip';span.textContent=w.word;words.append(span);});side.append(words);
    const heading=document.createElement('h4');heading.textContent='Closest vocabulary · cosine similarity';side.append(heading);const neighbors=document.createElement('div');neighbors.className='neighbors';artist.neighbors.forEach(a=>{const b=document.createElement('button');b.type='button';b.append(document.createTextNode(a.artist));const v=document.createElement('span');v.textContent=a.similarity.toFixed(3);b.append(v);b.addEventListener('click',()=>{selectedArtist=a.artist;el('artist-select').value=a.artist;drawArtists();});neighbors.append(b);});side.append(neighbors);
  }
  const coverage=Array.from({length:37},(_,i)=>{const year=1990+i,rows=S.coverage.filter(r=>r.year===year);return{year,rap:rows.filter(r=>r.genre==='rap').reduce((s,r)=>s+r.songs,0),other:rows.filter(r=>r.genre!=='rap').reduce((s,r)=>s+r.songs,0)};});
  for(const row of coverage){const tr=document.createElement('tr');[row.year,fmt(row.rap),fmt(row.other),row.year<=2022?'Historical dataset':'Recent supplement'+(row.year===2026?' · partial year':'')].forEach(t=>{const td=document.createElement('td');td.textContent=t;tr.append(td);});el('coverage-table').append(tr);}
  function drawCoverage(){const {svg,w,h}=size('coverage-chart',280),left=54,bottom=38,top=16,x=dateAxis(svg,w,h),max=Math.max(1,...coverage.flatMap(r=>[r.rap,r.other]))*1.08,y=v=>h-bottom-v/max*(h-bottom-top),bw=(w-left-16)/37*.35;
    for(let i=0;i<5;i++){const v=max*i/4;line(svg,left,y(v),w-16,y(v),{class:'grid'});add(svg,'text',{x:left-9,y:y(v)+4,'text-anchor':'end'},fmt(Math.round(v)));}
    coverage.forEach(r=>{for(const [g,offset,c]of[['rap',-bw,color.rap],['other',0,color.other]]){const bar=add(svg,'rect',{x:x(r.year)+offset,y:y(r[g]),width:Math.max(1,bw-1),height:h-bottom-y(r[g]),fill:c});hovered(bar,`${r.year}: ${fmt(r.rap)} hip-hop songs · ${fmt(r.other)} other songs`);}});
  }
  el('period').addEventListener('change',drawWords);el('ranking-mode').addEventListener('change',drawWords);el('trend-word').addEventListener('change',drawTrend);el('artist-select').addEventListener('change',()=>{selectedArtist=el('artist-select').value;drawArtists();});
  const redraw=()=>{hideTip();drawWords();drawTrend();drawArtists();drawCoverage();};
  let resize;addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(redraw,120);});redraw();
})();
