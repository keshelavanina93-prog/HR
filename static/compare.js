(()=>{'use strict';
const $=s=>document.querySelector(s);
let csrf='',data=null,canWrite=false;
const briefId=Number(document.body.dataset.brief)||null;
const DEFAULT_WEIGHTS={price:30,fit:30,method:25,trainer:15};
const WKEY='sivrce-develop-weights';
function el(tag,attrs={},...kids){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs)){if(v===false||v==null)continue;n.setAttribute(k,v===true?'':v)}n.append(...kids.filter(k=>k!=null&&k!==false));return n}
function status(s){$('#cmp-status').textContent=s||''}
async function call(path,method='GET',body){const r=await fetch(path,{method,credentials:'same-origin',headers:{'X-SIVRCE-CSRF':csrf,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});const b=await r.json().catch(()=>({}));if(!r.ok)throw Error(typeof b.detail==='string'?b.detail:'მოქმედება ვერ შესრულდა');return b}
const gel=n=>Number(n).toLocaleString('en-US')+' ₾';
function weights(){try{return{...DEFAULT_WEIGHTS,...JSON.parse(localStorage.getItem(WKEY)||'{}')}}catch{return{...DEFAULT_WEIGHTS}}}
function saveWeights(w){try{localStorage.setItem(WKEY,JSON.stringify(w))}catch{}}

/* Weighted score from the price formula and team averages. Missing team scores are reported, not invented. */
function score(p,w){
  const parts={price:p.price_score};for(const c of Object.keys(data.criteria))parts[c]=p.team[c].avg;
  const known=Object.entries(parts).filter(([,v])=>v!=null);const weightSum=known.reduce((s,[k])=>s+w[k],0);
  const total=weightSum?known.reduce((s,[k,v])=>s+v*w[k],0)/weightSum:0;
  return{total:Math.round(total*100)/100,missing:Object.entries(parts).filter(([,v])=>v==null).map(([k])=>k)}}

function renderWeights(){
  const w=weights(),box=$('#cmp-weight-list');box.replaceChildren();
  const labels={price:'ფასი',...data.criteria};
  for(const[k,label]of Object.entries(labels)){
    const out=el('output',{},w[k]+'%');
    const input=el('input',{type:'range',min:'0',max:'60',step:'5',value:String(w[k]),'aria-label':label+' — წონა'});
    input.oninput=()=>{const nw=weights();nw[k]=Number(input.value);saveWeights(nw);out.textContent=input.value+'%';renderMatrix()};
    box.append(el('label',{class:'cmp-weight'},el('span',{},label),input,out))}}

function cell(cls,...kids){return el('div',{class:'cmp-cell '+(cls||''),role:'cell'},...kids)}
function rowLabel(text,hint){return el('div',{class:'cmp-cell cmp-label',role:'rowheader'},el('b',{},text),hint?el('small',{},hint):null)}

function ratingControl(p,c){
  const wrap=el('div',{class:'cmp-rate',role:'group','aria-label':data.criteria[c]+' — ჩემი შეფასება'});
  for(let i=1;i<=5;i++){const b=el('button',{type:'button',class:p.mine[c]===i?'on':'','aria-pressed':String(p.mine[c]===i),disabled:!canWrite||p.status!=='submitted'?true:false},String(i));
    b.onclick=async()=>{try{await call(`/api/proposals/${p.id}/rating`,'PUT',{criterion:c,score:i});await load()}catch(e){status(e.message)}};wrap.append(b)}
  return wrap}

function renderMatrix(){
  const ps=data.proposals,w=weights(),m=$('#cmp-matrix');
  m.style.setProperty('--cols',ps.length);m.replaceChildren();
  if(!ps.length){m.append(el('p',{class:'pe-hint cmp-empty'},'ამ მოთხოვნაზე შეთავაზება ჯერ არ შემოსულა.'));return}
  const scores=ps.map(p=>score(p,w));const best=Math.max(...scores.map(s=>s.total));
  const minPrice=Math.min(...ps.map(p=>p.price)),maxBudgetShare=Math.max(100,...ps.map(p=>p.budget_share||0));
  const row=(...cells)=>m.append(el('div',{class:'cmp-row',role:'row'},...cells));
  row(el('div',{class:'cmp-cell cmp-corner',role:'columnheader'},el('small',{},`${ps.length} შეთავაზება`)),...ps.map((p,i)=>el('div',{class:'cmp-cell cmp-head'+(p.status==='selected'?' selected':''),role:'columnheader'},
    el('span',{class:'cmp-rank'},scores[i].total===best?'საუკეთესო ქულა':''),
    el('a',{href:'/organizations/'+p.provider_slug,target:'_blank',rel:'noopener'},el('b',{},p.provider)),
    el('small',{},(p.demo?'DEMO':p.verified?'● გადამოწმებული':'გადაუმოწმებელი')+' · ვერსია '+p.version))));
  row(rowLabel('ჯამური ფასი'),...ps.map(p=>cell(p.price===minPrice?'best':'',el('strong',{class:'cmp-big'},gel(p.price)))));
  row(rowLabel('ერთ მონაწილეზე',data.brief.audience+' მონაწილე'),...ps.map(p=>cell('',gel(p.per_person))));
  row(rowLabel('ბიუჯეტთან მიმართება',gel(data.brief.budget)),...ps.map(p=>cell(p.within_budget?'':'over',
    el('div',{class:'cmp-bar'},el('i',{style:`width:${Math.min(100,(p.budget_share/maxBudgetShare)*100)}%`}),el('em',{style:`left:${100/maxBudgetShare*100}%`,title:'ბიუჯეტი'})),
    el('small',{},p.budget_share+'% · '+(p.within_budget?'ბიუჯეტში':'აჭარბებს '+gel(p.price-data.brief.budget))))));
  row(rowLabel('ხანგრძლივობა'),...ps.map(p=>cell('',p.days+' დღე')));
  row(rowLabel('ტრენერი'),...ps.map(p=>cell('',p.trainer)));
  row(rowLabel('მიდგომა'),...ps.map(p=>{const d=el('details',{class:'cmp-approach'},el('summary',{},p.approach.slice(0,110)+(p.approach.length>110?'…':'')),el('p',{},p.approach));return cell('',p.approach.length>110?d:el('p',{class:'cmp-approach-text'},p.approach))}));
  for(const[c,label]of Object.entries(data.criteria)){
    row(rowLabel(label,'გუნდის საშუალო · ჩემი შეფასება'),...ps.map(p=>cell('',el('div',{class:'cmp-team'},el('strong',{},p.team[c].avg??'—'),el('small',{},p.team[c].count?`${p.team[c].count} შეფასება`:'ჯერ არავის შეუფასებია')),ratingControl(p,c))))}
  row(rowLabel('შეკითხვები მომწოდებელთან'),...ps.map(p=>cell('',p.questions?String(p.questions):'—')));
  row(rowLabel('შეწონილი ქულა','0–5, თქვენი წონებით'),...ps.map((p,i)=>{const s=scores[i];return cell(s.total===best?'best':'',
    el('strong',{class:'cmp-big'},s.total.toFixed(2)),el('div',{class:'cmp-bar score'},el('i',{style:`width:${s.total/5*100}%`})),
    s.missing.length?el('small',{class:'cmp-missing'},'აკლია: '+s.missing.map(k=>({price:'ფასი',...data.criteria})[k]).join(', ')):null)}));
  row(rowLabel('გადაწყვეტილება'),...ps.map(p=>{
    if(p.status==='selected')return cell('decision',el('span',{class:'me-status s-hired'},'შერჩეულია'));
    if(p.status==='not_selected')return cell('decision',el('span',{class:'me-status'},'არ შეირჩა'));
    if(!canWrite||data.brief.status!=='published')return cell('decision',el('small',{},'გადაწყვეტილების უფლება არ გაქვს'));
    const b=el('button',{type:'button',class:'st-primary'},'შეარჩიე →');
    b.onclick=async()=>{if(!confirm(`შევარჩიო „${p.provider}“? დანარჩენ მომწოდებლებს ეცნობებათ, რომ სხვა შეთავაზება შეირჩა. ამის გაუქმება შეუძლებელია.`))return;b.disabled=true;try{await call(`/api/proposals/${p.id}/select`,'POST',{});await load();status('მომწოდებელი შერჩეულია. ყველა მონაწილეს ეცნობა.')}catch(e){status(e.message);b.disabled=false}};
    return cell('decision',b)}))}

function renderBrief(){
  const b=data.brief;
  $('#cmp-brief-title').textContent=b.title;$('#cmp-brief-goal').textContent=b.goal;
  $('#cmp-brief-label').textContent='მოთხოვნა · '+({published:'შეთავაზებები მიიღება',awarded:'მომწოდებელი შერჩეულია',draft:'დრაფტი',completed:'დასრულებული'}[b.status]||b.status);
  $('#cmp-facts').replaceChildren(...[['მონაწილე',b.audience],['ბიუჯეტი',gel(b.budget)],['ფორმატი',b.format],['ვადა',b.deadline]].map(([k,v])=>el('div',{},el('dt',{},k),el('dd',{},String(v)))));
  $('#cmp-raters').textContent=data.raters?`შეფასებაში მონაწილეობდა ${data.raters} ადამიანი.`:'შეფასება ჯერ არავის დაუწყია.'}

async function load(){data=await call(`/api/briefs/${briefId}/comparison`);renderBrief();renderWeights();renderMatrix()}

async function init(){
  const me=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json()).catch(()=>({}));
  const blocked=$('#cmp-blocked');
  if(!me.user){blocked.hidden=false;blocked.append(el('h1',{},'Develop'),el('p',{},'შეთავაზებების შესადარებლად შედი კომპანიის ანგარიშით.'),el('a',{href:'/start',class:'st-primary'},'შესვლა →'));return}
  csrf=me.csrf||'';
  const orgs=me.memberships.filter(m=>m.kind==='company'&&['owner','procurement'].includes(m.role));
  if(!orgs.length){blocked.hidden=false;blocked.append(el('h1',{},'Develop'),el('p',{},'სასწავლო შესყიდვების ნახვა შეუძლია კომპანიის მფლობელს ან შესყიდვების როლს.'));return}
  canWrite=true;
  try{
    if(briefId){$('#cmp-view').hidden=false;await load();return}
    $('#cmp-list').hidden=false;
    const briefs=(await Promise.all(orgs.map(o=>call(`/api/organizations/${o.id}/briefs`)))).flat();
    $('#cmp-briefs').replaceChildren(...(briefs.length?briefs.map(b=>el('a',{href:'/workspace/develop/'+b.id,class:'cmp-brief-card'},el('span',{},({published:'მიიღება',awarded:'შერჩეულია',draft:'დრაფტი',completed:'დასრულდა'}[b.status]||b.status)+' · ვადა '+b.deadline),el('b',{},b.title),el('small',{},`${b.audience} მონაწილე · ${gel(b.budget)}`),el('strong',{},b.proposals+' შეთავაზება →'))):[el('p',{class:'pe-hint'},'სასწავლო მოთხოვნა ჯერ არ შეგიქმნია. შექმენი სამუშაო სივრციდან.')]))}
  catch(e){status(e.message)}}
init();
})();
