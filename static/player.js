/* SIVRCE Voices player. One <audio> per page, a sticky bar, position memory, Media Session, keyboard. */
(()=>{'use strict';
const KEY='sivrce-player';
const SPEEDS=[1,1.25,1.5,1.75,2];
let audio,bar,ui={},state=null,speedIndex=0,saveTimer=null;
const $=(s,r=document)=>r.querySelector(s);
const fmt=s=>{s=Math.max(0,Math.floor(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return (h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0')};
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'null')}catch{return null}}
function save(){if(!state)return;try{localStorage.setItem(KEY,JSON.stringify({...state,pos:audio.currentTime||state.pos||0,speed:SPEEDS[speedIndex]}))}catch{}}

function build(){
  bar=document.createElement('div');bar.id='sv-player';bar.hidden=true;bar.setAttribute('role','region');bar.setAttribute('aria-label','ფლეერი');
  bar.innerHTML=`<div class="sv-art"><img alt="" hidden><span class="sv-art-fallback" aria-hidden="true">V<b>.</b></span></div>
<div class="sv-meta"><a class="sv-title" href="#"></a><span class="sv-show"></span></div>
<div class="sv-controls">
  <button type="button" class="sv-skip" data-skip="-15" aria-label="15 წამით უკან">−15</button>
  <button type="button" class="sv-play" aria-label="დაკვრა"><span class="sv-ico-play">▶</span><span class="sv-ico-pause">❚❚</span></button>
  <button type="button" class="sv-skip" data-skip="30" aria-label="30 წამით წინ">+30</button>
</div>
<div class="sv-timeline"><span class="sv-cur">0:00</span><input type="range" class="sv-seek" min="0" max="1000" value="0" aria-label="პოზიცია"><span class="sv-dur">0:00</span></div>
<button type="button" class="sv-speed" aria-label="სიჩქარე">1×</button>
<button type="button" class="sv-close" aria-label="ფლეერის დახურვა">✕</button>`;
  document.body.append(bar);
  audio=new Audio();audio.preload='metadata';audio.hidden=true;bar.append(audio);
  ui={img:$('.sv-art img',bar),fb:$('.sv-art-fallback',bar),title:$('.sv-title',bar),show:$('.sv-show',bar),play:$('.sv-play',bar),seek:$('.sv-seek',bar),cur:$('.sv-cur',bar),dur:$('.sv-dur',bar),speed:$('.sv-speed',bar)};
  ui.play.onclick=toggle;
  bar.querySelectorAll('.sv-skip').forEach(b=>b.onclick=()=>{audio.currentTime=Math.max(0,audio.currentTime+Number(b.dataset.skip));save()});
  ui.speed.onclick=()=>{speedIndex=(speedIndex+1)%SPEEDS.length;audio.playbackRate=SPEEDS[speedIndex];ui.speed.textContent=SPEEDS[speedIndex]+'×';save()};
  $('.sv-close',bar).onclick=()=>{audio.pause();bar.hidden=true;document.body.classList.remove('has-player');try{localStorage.removeItem(KEY)}catch{};state=null;syncButtons()};
  ui.seek.oninput=()=>{if(audio.duration)audio.currentTime=audio.duration*ui.seek.value/1000};
  ui.seek.onchange=save;
  audio.addEventListener('timeupdate',()=>{ui.cur.textContent=fmt(audio.currentTime);if(audio.duration){ui.seek.value=Math.round(audio.currentTime/audio.duration*1000);ui.dur.textContent=fmt(audio.duration)}clearTimeout(saveTimer);saveTimer=setTimeout(save,2000)});
  audio.addEventListener('loadedmetadata',()=>{ui.dur.textContent=fmt(audio.duration)});
  audio.addEventListener('play',()=>{bar.classList.add('playing');syncButtons()});
  audio.addEventListener('pause',()=>{bar.classList.remove('playing');syncButtons();save()});
  audio.addEventListener('ended',()=>{bar.classList.remove('playing');syncButtons();if(state){state.pos=0;save()}});
  // Some hosts answer a media request with a redirect the browser refuses; ask the server for the final URL once.
  audio.addEventListener('error',async()=>{if(state&&!state.resolved&&state.id){state.resolved=true;try{const r=await fetch('/api/voices/episodes/'+state.id+'/stream');if(r.ok){const {url}=await r.json();const pos=audio.currentTime||state.pos||0;state.url=url;audio.src=url;audio.load();audio.addEventListener('loadedmetadata',()=>{if(pos>5)audio.currentTime=pos},{once:true});await audio.play().catch(()=>{});return}}catch{}}
    ui.show.textContent='ფაილი ვერ ჩაიტვირთა — სცადე პირველწყარო';bar.classList.remove('playing');syncButtons()});
  document.addEventListener('keydown',e=>{if(!state||bar.hidden||/input|textarea|select/i.test(e.target.tagName))return;if(e.code==='Space'&&!e.target.closest('button')){e.preventDefault();toggle()}if(e.key==='ArrowLeft')audio.currentTime=Math.max(0,audio.currentTime-15);if(e.key==='ArrowRight')audio.currentTime+=30});
  if('mediaSession' in navigator){const ms=navigator.mediaSession;ms.setActionHandler('play',()=>audio.play());ms.setActionHandler('pause',()=>audio.pause());ms.setActionHandler('seekbackward',()=>audio.currentTime=Math.max(0,audio.currentTime-15));ms.setActionHandler('seekforward',()=>audio.currentTime+=30)}
}

function show(s){
  state=s;ui.title.textContent=s.title;ui.title.href=s.href||'#';ui.show.textContent=s.show||'';
  if(s.art){ui.img.src=s.art;ui.img.hidden=false;ui.fb.hidden=true}else{ui.img.hidden=true;ui.fb.hidden=false}
  if(audio.src!==s.url){audio.src=s.url;audio.load();if(s.pos>5)audio.addEventListener('loadedmetadata',()=>{audio.currentTime=Math.min(s.pos,audio.duration-1||s.pos)},{once:true})}
  speedIndex=Math.max(0,SPEEDS.indexOf(s.speed||1));audio.playbackRate=SPEEDS[speedIndex];ui.speed.textContent=SPEEDS[speedIndex]+'×';
  ui.cur.textContent=fmt(s.pos||0);ui.dur.textContent=s.duration?fmt(s.duration):'';
  bar.hidden=false;document.body.classList.add('has-player');
  if('mediaSession' in navigator)navigator.mediaSession.metadata=new MediaMetadata({title:s.title,artist:s.show||'SIVRCE Voices',artwork:s.art?[{src:s.art,sizes:'512x512'}]:[]});
  syncButtons()}

function toggle(){if(!state)return;if(audio.paused)audio.play().catch(()=>{});else audio.pause()}

function syncButtons(){
  const playing=!audio.paused&&!audio.ended;
  ui.play.setAttribute('aria-label',playing?'პაუზა':'დაკვრა');
  document.querySelectorAll('[data-play]').forEach(b=>{const on=state&&b.dataset.play===state.id;b.classList.toggle('is-current',!!on);b.classList.toggle('is-playing',!!on&&playing);b.setAttribute('aria-pressed',String(!!on&&playing))});
  const cont=$('#sv-continue');if(cont){cont.hidden=!state;if(state){$('.svc-title',cont).textContent=state.title;$('.svc-show',cont).textContent=state.show+(state.pos>30?' · '+fmt(state.pos):'');const img=$('.svc-art',cont);if(img){img.src=state.art||'';img.hidden=!state.art}}}}

document.addEventListener('click',e=>{
  const b=e.target.closest('[data-play]');if(!b)return;e.preventDefault();
  if(state&&b.dataset.play===state.id){toggle();return}
  const saved=load();const pos=saved&&saved.id===b.dataset.play?saved.pos:0;
  show({id:b.dataset.play,url:b.dataset.url,title:b.dataset.title,show:b.dataset.show,art:b.dataset.art||'',href:b.dataset.href||location.pathname,duration:Number(b.dataset.duration||0),pos,speed:saved?.speed});
  audio.play().catch(()=>{});
});
document.addEventListener('click',e=>{const c=e.target.closest('[data-seek]');if(!c||!state)return;e.preventDefault();audio.currentTime=Number(c.dataset.seek);audio.play().catch(()=>{})});
document.addEventListener('click',e=>{const c=e.target.closest('#sv-continue [data-resume]');if(!c)return;e.preventDefault();toggle()});

document.addEventListener('DOMContentLoaded',()=>{build();const s=load();if(s&&s.url){show(s)}else syncButtons()});
})();
