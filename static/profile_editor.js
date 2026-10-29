(()=>{'use strict';
const $=s=>document.querySelector(s);
let csrf='',org=null,photos=[];

function el(tag,attrs={},...kids){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs)){if(k==='class')n.className=v;else if(k in n&&typeof v!=='string')n[k]=v;else n.setAttribute(k,v)}for(const k of kids)n.append(k);return n}
function status(s){$('#pe-status').textContent=s||''}
function detail(b){if(typeof b.detail==='string')return b.detail;if(Array.isArray(b.detail))return b.detail.map(d=>(d.msg||'').replace(/^Value error, /,'')).join(' · ');return 'შეამოწმე შეყვანილი ინფორმაცია'}
async function call(path,opts={}){const headers={'X-SIVRCE-CSRF':csrf,...(opts.json?{'Content-Type':'application/json'}:{})};const r=await fetch(path,{credentials:'same-origin',method:opts.method||'GET',headers,body:opts.json?JSON.stringify(opts.json):opts.body});const b=await r.json().catch(()=>({}));if(!r.ok)throw Error(detail(b));return b}

/* ---------- Day & people rows ---------- */
function dayRow(d={}){
  const row=el('div',{class:'pe-row'},
    el('label',{class:'pe-time'},'დრო',el('input',{name:'time',type:'time',value:d.time||'09:00',required:true})),
    el('label',{},'რა ხდება',el('input',{name:'title',maxlength:'120',value:d.title||'',placeholder:'მაგ.: ცვლის გადაბარება'})),
    el('label',{class:'pe-wide'},'დეტალები',el('textarea',{name:'body',rows:'2',maxlength:'600'},d.body||'')),
    el('button',{type:'button',class:'pe-remove','aria-label':'მომენტის წაშლა'},'✕'));
  row.querySelector('.pe-remove').onclick=()=>{row.remove();check()};
  return row}
function personRow(p={}){
  const select=el('select',{name:'photo_id'},el('option',{value:''},'ფოტოს გარეშე'));
  for(const ph of photos.filter(x=>x.people_consent==='confirmed'))select.append(el('option',{value:String(ph.id)},ph.alt.slice(0,48)));
  select.value=p.photo_id?String(p.photo_id):'';
  const row=el('div',{class:'pe-row'},
    el('label',{},'სახელი',el('input',{name:'name',maxlength:'100',value:p.name||'',placeholder:'მაგ.: მარიამ ს.'})),
    el('label',{},'როლი',el('input',{name:'role',maxlength:'120',value:p.role||''})),
    el('label',{class:'pe-wide'},'მისი სიტყვებით (არასავალდებულო)',el('textarea',{name:'quote',rows:'2',maxlength:'500'},p.quote||'')),
    el('label',{},'ფოტო',select),
    el('label',{class:'pe-check pe-wide'},el('input',{type:'checkbox',name:'consent',checked:!!p.name}),' ეს ადამიანი თანახმაა, რომ მისი სახელი, როლი და სიტყვები გამოქვეყნდეს'),
    el('button',{type:'button',class:'pe-remove','aria-label':'ადამიანის წაშლა'},'✕'));
  row.querySelector('.pe-remove').onclick=()=>{row.remove();check()};
  return row}
function refreshPeopleSelects(){for(const row of document.querySelectorAll('#pe-people .pe-row')){const p=collectPerson(row);row.replaceWith(personRow({...p,photo_id:p.photo_id}))}}
function collectPerson(row){const v=n=>row.querySelector(`[name=${n}]`);return{name:v('name').value.trim(),role:v('role').value.trim(),quote:v('quote').value.trim(),photo_id:v('photo_id').value?Number(v('photo_id').value):null,consent:v('consent').checked}}

/* ---------- Photos ---------- */
const ROLE={cover:'მთავარი',gallery:'გარემო',person:'პორტრეტი'};
const ACCENT_NAMES={cobalt:'კობალტი',oxblood:'ღვინისფერი',ink:'მელანი',plum:'ქლიავისფერი',slate:'ფიქალი',clay:'თიხა',ochre:'ოხრა'};
function renderPhotos(){
  const list=$('#pe-photo-list');list.replaceChildren();
  if(!photos.length){list.append(el('p',{class:'pe-hint'},'ფოტო ჯერ არ არის ატვირთული.'));return}
  for(const ph of photos){
    const del=el('button',{type:'button',class:'pe-remove'},'წაშლა');
    del.onclick=async()=>{if(!confirm('წავშალო ფოტო? ის საჯარო გვერდიდანაც გაქრება.'))return;try{await call(`/api/organizations/${org.id}/photos/${ph.id}`,{method:'DELETE'});await load();status('ფოტო წაიშალა.')}catch(e){status(e.message)}};
    list.append(el('figure',{class:'pe-photo'},el('img',{src:ph.url,alt:ph.alt,loading:'lazy'}),el('figcaption',{},el('b',{},ROLE[ph.role]||ph.role),' · ',ph.credit,ph.people_consent==='confirmed'?' · თანხმობით':''),del))}}

/* ---------- Completeness ---------- */
function check(){
  const f=$('#pe-form'),g=n=>f.elements[n].value.trim();
  const items=[
    ['მოკლე აღწერა',g('tagline').length>=20],
    ['საქმის აღწერა (120+ სიმბოლო)',g('mission').length>=120],
    ['სამუშაო დღე (3+ მომენტი)',document.querySelectorAll('#pe-day .pe-row').length>=3],
    ['ადამიანები (2+)',document.querySelectorAll('#pe-people .pe-row').length>=2],
    ['რა არის რთული (2+ პუნქტი)',g('hard_parts').split('\n').filter(x=>x.trim()).length>=2],
    ['შერჩევის დაპირება',g('hiring_promise').length>=40],
    ['მთავარი ფოტო',photos.some(p=>p.role==='cover')]];
  const ul=$('#pe-checklist');ul.replaceChildren(...items.map(([t,ok])=>el('li',{class:ok?'done':''},(ok?'✓ ':'○ ')+t)));
  $('#pe-score').textContent=`${items.filter(i=>i[1]).length}/${items.length}`}

/* ---------- Load & save ---------- */
async function load(){
  const d=await call(`/api/organizations/${org.id}/story`);photos=d.photos;
  const f=$('#pe-form');
  for(const k of['tagline','team_size','founded','mission','hard_parts','culture','hiring_promise'])f.elements[k].value=d.fields[k]||'';
  const accents=$('#pe-accent-list');accents.replaceChildren();
  for(const[name,hex]of Object.entries(d.accents)){const input=el('input',{type:'radio',name:'accent',value:name,checked:(d.fields.accent||'ink')===name});accents.append(el('label',{class:'pe-swatch',style:`--sw:${hex}`,title:ACCENT_NAMES[name]||name},input,el('span',{},ACCENT_NAMES[name]||name)))}
  $('#pe-day').replaceChildren(...d.day.map(dayRow));
  $('#pe-people').replaceChildren(...d.people.map(personRow));
  renderPhotos();check();
  $('#pe-preview').href='/organizations/'+d.organization.slug;$('#pe-preview').hidden=!d.organization.verified}

async function save(e){
  e.preventDefault();const f=e.target,btn=f.querySelector('[type=submit]');btn.disabled=true;
  const payload={accent:(f.querySelector('[name=accent]:checked')||{}).value||'ink'};
  for(const k of['tagline','team_size','founded','mission','hard_parts','culture','hiring_promise'])payload[k]=f.elements[k].value.trim();
  payload.day=[...document.querySelectorAll('#pe-day .pe-row')].map(r=>({time:r.querySelector('[name=time]').value,title:r.querySelector('[name=title]').value.trim(),body:r.querySelector('[name=body]').value.trim()}));
  payload.people=[...document.querySelectorAll('#pe-people .pe-row')].map(collectPerson);
  try{await call(`/api/organizations/${org.id}/story`,{method:'PUT',json:payload});$('#pe-saved').textContent='შენახულია · '+new Date().toLocaleTimeString('ka-GE',{hour:'2-digit',minute:'2-digit',hour12:false});status('')}
  catch(err){status(err.message)}finally{btn.disabled=false}}

async function upload(e){
  e.preventDefault();const f=e.target,btn=f.querySelector('[type=submit]');btn.disabled=true;status('ფოტო იტვირთება...');
  const data=new FormData(f);if(!f.elements.rights_confirmed.checked)data.set('rights_confirmed','false');
  try{await call(`/api/organizations/${org.id}/photos`,{method:'POST',body:data});f.reset();await load();refreshPeopleSelects();status('ფოტო აიტვირთა.')}
  catch(err){status(err.message)}finally{btn.disabled=false}}

async function init(){
  try{
    const me=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json());csrf=me.csrf||'';
    const blocked=$('#pe-blocked');
    if(!me.user){blocked.hidden=false;blocked.append(el('p',{},'გვერდის რედაქტირებისთვის შედი ორგანიზაციის ანგარიშით. '),el('a',{href:'/start'},'შესვლა ↗'));return}
    const wanted=Number(new URLSearchParams(location.search).get('org'));
    const owned=me.memberships.filter(m=>m.role==='owner');
    org=owned.find(m=>m.id===wanted)||owned[0];
    if(!org){blocked.hidden=false;blocked.append(el('p',{},'გვერდის რედაქტირება შეუძლია ორგანიზაციის მფლობელს. სთხოვე მფლობელს უფლება ან შექმენი ორგანიზაცია. '),el('a',{href:'/start'},'ორგანიზაციის შექმნა ↗'));return}
    $('#pe-org-name').textContent=org.name+(org.verified?'':' · გადამოწმებას ელოდება');
    $('#pe-form').hidden=false;$('#pe-photos-card').hidden=false;
    $('#pe-form').addEventListener('submit',save);$('#pe-form').addEventListener('input',check);
    $('#pe-upload').addEventListener('submit',upload);
    $('#pe-add-day').onclick=()=>{if(document.querySelectorAll('#pe-day .pe-row').length<8){$('#pe-day').append(dayRow());check()}};
    $('#pe-add-person').onclick=()=>{if(document.querySelectorAll('#pe-people .pe-row').length<8){$('#pe-people').append(personRow());check()}};
    await load();
    if(!org.verified)status('ორგანიზაცია ჯერ არ არის გადამოწმებული: გვერდი საჯაროდ გამოჩნდება გადამოწმების შემდეგ.');
  }catch(err){status(err.message)}}
init();
})();
