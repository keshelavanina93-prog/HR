(()=>{'use strict';
const $=s=>document.querySelector(s);
let csrf='';
function el(tag,attrs={},...kids){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs)){if(v===false||v==null)continue;n.setAttribute(k,v===true?'':v)}n.append(...kids.filter(k=>k!=null&&k!==false));return n}
function status(s){$('#me-status').textContent=s||''}
async function call(path,method='GET',body){const r=await fetch(path,{method,credentials:'same-origin',headers:{'X-SIVRCE-CSRF':csrf,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});const b=await r.json().catch(()=>({}));if(!r.ok)throw Error(typeof b.detail==='string'?b.detail:'მოქმედება ვერ შესრულდა');return b}
// Format dates ourselves so Georgian month names don't depend on the browser's locale data.
const MONTHS=['იანვარი','თებერვალი','მარტი','აპრილი','მაისი','ივნისი','ივლისი','აგვისტო','სექტემბერი','ოქტომბერი','ნოემბერი','დეკემბერი'];
const fmtDate=s=>{const d=new Date(s);return isNaN(d)?s:`${d.getDate()} ${MONTHS[d.getMonth()]}`};
const fmtWhen=s=>{const d=new Date(s);return isNaN(d)?s:`${fmtDate(s)}, ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`};
const FORMAT={online:'ონლაინ',onsite:'ადგილზე',phone:'ტელეფონით'};
const money=(a,b)=>`${a.toLocaleString('en-US')}–${b.toLocaleString('en-US')} ₾`;

function track(a){
  return el('ol',{class:'me-track'+(a.status==='rejected'?' is-closed':''),'aria-label':'შერჩევის ეტაპები'},...a.stages.map((label,i)=>
    el('li',{class:i<a.stage?'done':i===a.stage?(a.status==='rejected'?'stopped':'current'):'',...(i===a.stage?{'aria-current':'step'}:{})},el('span',{},label))))}

function appCard(a){
  const withdraw=a.closed?null:el('button',{type:'button',class:'me-link danger'},'განაცხადის გამოთხოვა');
  if(withdraw)withdraw.onclick=async()=>{if(!confirm(`გამოვითხოვო განაცხადი „${a.title}“-ზე? CV წაიშლება და კომპანია მას ვეღარ ნახავს.`))return;try{await call('/api/my-applications/'+a.id,'DELETE');await load();status('განაცხადი გამოთხოვილია.')}catch(e){status(e.message)}};
  const interviews=a.interviews.length?el('div',{class:'me-interviews'},...a.interviews.map(i=>el('div',{class:'me-interview'+(i.upcoming?' upcoming':'')},
    el('b',{},(i.upcoming?'გასაუბრება · ':'ჩატარდა · ')+fmtWhen(i.when)),el('span',{},`${FORMAT[i.format]||i.format} · ${i.where}`),i.note?el('p',{},i.note):null,
    i.upcoming?el('a',{href:i.ics,class:'me-link'},'კალენდარში დამატება ↓'):null))):null;
  const waiting=!a.closed&&a.days_since_update>=7?el('p',{class:'me-wait'},`${a.days_since_update} დღეა ეტაპი არ შეცვლილა.`+(a.promise?` კომპანიის დაპირება: ${a.promise}`:'')):null;
  return el('article',{class:'me-app'+(a.closed?' closed':''),style:`--org-accent:${a.accent}`},
    el('div',{class:'me-app-head'},
      el('div',{},el('a',{href:'/organizations/'+a.slug,class:'me-company'},a.company),el('h3',{},el('a',{href:'/careers/'+a.job_id},a.title)),el('small',{},'გაგზავნილია '+fmtDate(a.created))),
      el('span',{class:'me-status s-'+a.status},a.status_label)),
    track(a),
    el('p',{class:'me-now'},a.now),
    waiting,interviews,
    el('div',{class:'me-app-actions'},el('a',{href:'/careers/'+a.job_id,class:'me-link'},'ვაკანსია ↗'),a.cv_url?el('a',{href:a.cv_url,class:'me-link'},'ჩემი CV ↓'):null,withdraw))}

function render(d){
  $('#me-hello').textContent='გამარჯობა, '+d.user.name.split(' ')[0];
  $('#c-active').textContent=d.counts.active;$('#c-interviews').textContent=d.counts.interviews;$('#c-saved').textContent=d.counts.saved;
  $('#me-org-link').hidden=!d.has_organization;
  const next=$('#me-next');next.replaceChildren();
  if(d.next_interview){const i=d.next_interview;next.append(el('span',{class:'org-label'},'შემდეგი ნაბიჯი'),el('h2',{},'გასაუბრება · '+fmtWhen(i.when)),el('p',{},`${i.title} · ${i.company} · ${FORMAT[i.format]||i.format} · ${i.where}`),el('a',{href:i.ics,class:'st-primary'},'კალენდარში დამატება ↓'));next.hidden=false}
  else if(d.profile.score<d.profile.total){next.append(el('span',{class:'org-label'},'შემდეგი ნაბიჯი'),el('h2',{},'შეავსე პროფილი'),el('p',{},'კომპანია განაცხადთან ერთად ხედავს შენს პროფესიულ სათაურს, უნარებს და გამოცდილებას.'),el('a',{href:'#profile',class:'st-primary'},'პროფილზე გადასვლა ↓'));next.hidden=false}
  else next.hidden=true;
  $('#me-apps').replaceChildren(...(d.applications.length?d.applications.map(appCard):[el('div',{class:'me-empty'},el('p',{},'ჯერ არცერთი განაცხადი არ გაგიგზავნია.'),el('a',{href:'/careers',class:'st-primary'},'ვაკანსიების ნახვა →'))]));
  $('#me-saved').replaceChildren(...(d.saved.length?d.saved.map(s=>el('a',{href:'/careers/'+s.id,class:'me-saved-card'+(s.open?'':' closed'),style:`--org-accent:${s.accent}`},el('span',{},s.company),el('b',{},s.title),el('small',{},money(s.salary_min,s.salary_max)+' · '+(s.open?'ვადა '+s.deadline:'მიღება დასრულდა')))):[el('p',{class:'pe-hint'},'ვაკანსიის გვერდზე „☆ შეინახე“ — და აქ გამოჩნდება.')]));
  $('#interests-section').hidden=!d.interests.length;
  $('#me-interests').replaceChildren(...d.interests.map(i=>el('a',{href:'/learn/'+i.course_id,class:'me-saved-card'},el('span',{},'ჯგუფი '+i.starts),el('b',{},i.title),el('small',{},i.status==='requested'?'მოთხოვნა გაგზავნილია':i.status))));
  $('#me-unread').hidden=!d.unread;$('#me-unread').textContent=d.unread;
  $('#me-notes').replaceChildren(...(d.notifications.length?d.notifications.map(n=>el('li',{class:n.read?'':'unread'},el('b',{},n.title),el('span',{},n.body),el('small',{},fmtDate(n.created)))):[el('li',{class:'pe-hint'},'შეტყობინებები ჯერ არ არის.')]));
  const f=$('#profile-form');for(const[k,v]of Object.entries(d.profile.fields))f.elements[k].value=v;
  $('#profile-score').textContent=`${d.profile.score}/${d.profile.total}`;
  $('#profile-checks').replaceChildren(...d.profile.checks.map(c=>el('li',{class:c.done?'done':''},(c.done?'✓ ':'○ ')+c.label)))}

async function load(){const d=await call('/api/me/overview');render(d)}

async function init(){
  const me=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json()).catch(()=>({}));
  if(!me.user){$('#me-signin').hidden=false;return}
  csrf=me.csrf||'';$('#me-app').hidden=false;
  $('#profile-form').addEventListener('submit',async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;
    try{await call('/api/profile','PUT',Object.fromEntries(new FormData(e.target).entries()));await load();$('#profile-saved').textContent='შენახულია.'}catch(err){status(err.message)}finally{btn.disabled=false}});
  $('#delete-profile').onclick=async()=>{if(!confirm('გავასუფთავო პროფესიული პროფილი?'))return;try{await call('/api/profile','DELETE');await load();status('პროფილი გასუფთავდა.')}catch(e){status(e.message)}};
  try{await load()}catch(e){status(e.message)}}
init();
})();
