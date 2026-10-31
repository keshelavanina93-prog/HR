(()=>{'use strict';
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
let csrf=null,authMode='login',orgKind='company';
const STAGES=['auth','role','org','done','candidate'];
const TITLES=['ნაბიჯი 01 · ანგარიში','ნაბიჯი 02 · როლი','ნაბიჯი 03 · ორგანიზაცია','ნაბიჯი 04 · გადამოწმება','ნაბიჯი 02 · კანდიდატი'];
const STEP_OF={auth:0,role:1,org:2,done:3,candidate:1};

function feedback(s){$('#onboard-feedback').textContent=s||''}
function el(tag,attrs={},...kids){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);n.append(...kids);return n}
function stage(name){
  STAGES.forEach(x=>{$('#'+x+'-stage').hidden=x!==name});
  $('#stage-title').textContent=TITLES[STAGES.indexOf(name)];
  const current=STEP_OF[name];
  $$('#st-steps li').forEach(li=>{const n=Number(li.dataset.step);li.classList.toggle('done',n<current||(name==='done'&&n===3&&$('#done-stage').dataset.verified==='1'));li.classList.toggle('current',n===current);li.classList.toggle('skipped',name==='candidate'&&n>1)});
  feedback('');
  // Move focus to the new step for keyboard and screen-reader users, but not on first paint.
  const heading=$('#'+name+'-stage h2');if(heading&&stage.started){heading.tabIndex=-1;heading.focus({preventScroll:true})}
  stage.started=true}

async function req(path,method='GET',body){
  const opt={method,credentials:'same-origin',headers:{}};
  if(method!=='GET'){opt.headers['Content-Type']='application/json';if(csrf)opt.headers['X-SIVRCE-CSRF']=csrf;opt.body=JSON.stringify(body||{})}
  const r=await fetch(path,opt);let data;try{data=await r.json()}catch{data={}}
  if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?'შეამოწმე ველები: '+data.detail.map(d=>d.loc?.slice(-1)[0]).join(', '):'მოთხოვნა ვერ შესრულდა ('+r.status+')');
  return data}

function choose(mode){
  authMode=mode;$$('[data-auth]').forEach(x=>{x.classList.toggle('active',x.dataset.auth===mode);x.setAttribute('aria-selected',x.dataset.auth===mode)});
  $('#full-name-label').hidden=mode!=='register';$('#auth-form [name=name]').required=mode==='register';
  $('#auth-form [name=password]').autocomplete=mode==='login'?'current-password':'new-password';
  $('#auth-submit').textContent=mode==='login'?'შესვლა →':'ანგარიშის შექმნა →';feedback('')}

function showVerification(org){
  const verified=!!org.verified,requested=!!org.verification_requested;
  $('#done-stage').dataset.verified=verified?'1':'';
  $('#done-title').textContent=verified?'ორგანიზაცია გადამოწმებულია':requested?'გადამოწმება მიმდინარეობს':'გადამოწმება ჯერ არ არის მოთხოვნილი';
  $('#done-org').textContent=org.name+' · '+(org.kind==='provider'?'სასწავლო მომწოდებელი':'კომპანია');
  const steps=[
    ['done','ანგარიში შექმნილია','შენი ელფოსტა ან Google ანგარიში.'],
    ['done','ორგანიზაციის მონაცემები მიღებულია','დასახელება, საიდენტიფიკაციო კოდი, ვებსაიტი და აღწერა.'],
    [verified?'done':requested?'current':'todo','მოდერატორი ამოწმებს','საიდენტიფიკაციო კოდს საჯარო რეესტრში, ვებსაიტს და იმას, რომ შენ ამ ორგანიზაციის სახელით მოქმედებ.'],
    [verified?'done':'todo','საჯარო გამოქვეყნება იხსნება','ვაკანსიები და კურსები გამოქვეყნებამდე მაინც გადის ხარისხის შემოწმებას.']];
  $('#st-verify').replaceChildren(...steps.map(([state,title,text])=>el('li',{class:state},el('b',{},title),el('span',{},text))));
  const actions=org.kind==='provider'
    ?[['/workspace','კურსის დრაფტი','პროგრამა, შედეგები, ფასი და ჯგუფები.'],['/workspace/company-profile','ორგანიზაციის გვერდი','ვინ ასწავლის და როგორ.'],['/exchange','სასწავლო მოთხოვნები','ნახე, რა სჭირდებათ კომპანიებს.']]
    :[['/workspace','ვაკანსიის დრაფტი','ხელფასი, როლის მიზანი და შერჩევის ეტაპები.'],['/workspace/company-profile','კომპანიის გვერდი','სამუშაო დღე, ადამიანები, ფოტოები.'],['/workspace','გუნდის მოწვევა','რეკრუტერი, ხელმძღვანელი, შესყიდვები.']];
  $('#st-actions').replaceChildren(...actions.map(([href,title,text])=>el('a',{href,class:'st-action'},el('b',{},title+' →'),el('span',{},text))));
  if(verified)$('.st-sub').textContent='შემდეგი ნაბიჯები';
  stage('done')}

async function readyUser(){
  const data=await req('/api/me');csrf=data.csrf||csrf;
  if(!data.user){stage('auth');return}
  const org=data.memberships.find(x=>x.role==='owner')||data.memberships[0];
  if(org){showVerification(org);return}
  stage('role')}

async function initGoogle(){
  try{const conf=await req('/api/auth/google/config');
    if(!conf.enabled||!conf.client_id){$('#google-setup-message').textContent='Google-ით შესვლა ჩაირთვება, როცა Google Cloud-ის Client ID დაკონფიგურირდება.';return}
    const script=document.createElement('script');script.src='https://accounts.google.com/gsi/client';script.async=true;
    script.onload=()=>{if(!window.google?.accounts?.id)return;
      window.google.accounts.id.initialize({client_id:conf.client_id,callback:async r=>{try{feedback('Google ანგარიში მოწმდება...');const x=await req('/api/auth/google','POST',{credential:r.credential});csrf=x.csrf;await readyUser()}catch(err){feedback(err.message)}}});
      window.google.accounts.id.renderButton($('#google-login'),{theme:'outline',size:'large',text:'continue_with',width:320,locale:'ka'})};
    document.head.append(script)}
  catch(err){$('#google-setup-message').textContent='Google შესვლა ვერ ჩაიტვირთა: '+err.message}}

document.addEventListener('DOMContentLoaded',()=>{
  stage('auth');stage.started=false;
  $$('[data-auth]').forEach(x=>x.addEventListener('click',()=>choose(x.dataset.auth)));
  $('#auth-form').addEventListener('submit',async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(e.target).entries());const btn=$('#auth-submit');btn.disabled=true;feedback('მოწმდება...');
    try{const d=await req(authMode==='login'?'/api/auth/login':'/api/auth/register','POST',authMode==='login'?{email:v.email,password:v.password}:{name:v.name,email:v.email,password:v.password});csrf=d.csrf;await readyUser()}
    catch(err){feedback(err.message)}finally{btn.disabled=false}});
  $$('.st-role').forEach(b=>b.addEventListener('click',()=>{const role=b.dataset.role;
    if(role==='candidate'){stage('candidate');return}
    orgKind=role;$('#org-title').textContent=role==='provider'?'სასწავლო ორგანიზაციის მონაცემები':'კომპანიის მონაცემები';stage('org')}));
  const desc=$('#org-form [name=description]');desc.addEventListener('input',()=>{const n=desc.value.trim().length;$('#desc-count').textContent=n+(n<50?' / მინ. 50':' ✓')});
  $('#org-form').addEventListener('submit',async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(e.target).entries());const btn=e.target.querySelector('button');btn.disabled=true;feedback('ორგანიზაცია იქმნება...');
    try{const d=await req('/api/organizations','POST',{...v,kind:orgKind});
      let requested=true;try{await req('/api/organizations/'+d.id+'/request-verification','POST')}catch(er){requested=false;feedback('გადამოწმების მოთხოვნას შესწორება სჭირდება: '+er.message)}
      showVerification({id:d.id,name:d.name,kind:orgKind,verified:false,verification_requested:requested});if(!requested)feedback('გადამოწმების მოთხოვნას შესწორება სჭირდება.')}
    catch(err){feedback(err.message)}finally{btn.disabled=false}});
  readyUser().catch(e=>feedback(e.message));initGoogle()})})();
