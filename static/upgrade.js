/* SIVRCE 2026: real workflows integrated with server-enforced permissions. */
(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const escapeHTML=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function request(path,{method='GET',body=null}={}){
 const auth=await fetch('/api/me',{credentials:'same-origin'}).then(r=>r.json());
 const headers={};if(method!=='GET'&&auth.csrf)headers['X-SIVRCE-CSRF']=auth.csrf;
 if(body!==null)headers['Content-Type']='application/json';
 const r=await fetch(path,{method,credentials:'same-origin',headers,body:body===null?undefined:JSON.stringify(body)});
 let data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'მოქმედება ვერ შესრულდა');return data;
}
function feedback(text,success=true){let t=$('#toast');if(t){t.textContent=text;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),5000)}else alert(text)}
function requireSession(fn){request('/api/me').then(data=>{if(!data.user){location.assign('/studio');return}fn()}).catch(e=>feedback(e.message))}

function openTaskDialog({title,subtitle,fields,action}){
 const overlay=document.createElement('dialog');overlay.className='upgrade-dialog';
 overlay.innerHTML=`<div class="upgrade-dialog-inner"><div class="upgrade-dialog-top"><span>SIVRCE / WORKFLOW</span><button type="button" class="dialog-exit" aria-label="დახურვა">×</button></div><h2>${escapeHTML(title)}</h2><p>${escapeHTML(subtitle)}</p><form class="upgrade-task-form">${fields}<div role="alert" class="upgrade-error"></div><div class="upgrade-buttons"><button class="primary-btn" type="submit">გაგრძელება ↗</button><button class="secondary-btn cancel-task" type="button">გაუქმება</button></div></form></div>`;
 document.body.append(overlay);const close=()=>{overlay.close();overlay.remove()};$('.dialog-exit',overlay).onclick=close;$('.cancel-task',overlay).onclick=close;
 overlay.addEventListener('click',e=>{if(e.target===overlay)close()});
 $('.upgrade-task-form',overlay).addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget,err=$('.upgrade-error',overlay),b=$('[type=submit]',f);b.disabled=true;err.textContent='';
  try{await action(Object.fromEntries(new FormData(f).entries()));close()}catch(error){err.textContent=error.message}finally{b.disabled=false}
 });overlay.showModal();
}

const google={loaded:false,initialized:false,clientId:null};
function showGoogleButtons(){if(!google.clientId||!window.google?.accounts?.id)return;
 if(!google.initialized){window.google.accounts.id.initialize({client_id:google.clientId,callback:async response=>{
  try{let me=await request('/api/me');let mode=me.user?'link':'login';const r=await fetch(mode==='link'?'/api/auth/google/link':'/api/auth/google',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json',...(mode==='link'?{'X-SIVRCE-CSRF':me.csrf}:{})},body:JSON.stringify({credential:response.credential})});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Google შესვლა ვერ განხორციელდა');location.reload()}
  catch(e){feedback(e.message,false)}
 }});google.initialized=true}
 $$('.google-auth-slot').forEach(el=>{if(el.dataset.googlePainted)return;el.dataset.googlePainted='1';window.google.accounts.id.renderButton(el,{theme:'outline',size:'large',text:'continue_with',shape:'rectangular',width:270,locale:'ka'})});
}
async function initGoogle(){try{const cfg=await request('/api/auth/google/config');if(!cfg.enabled)return;google.clientId=cfg.client_id;const sdk=document.createElement('script');sdk.src='https://accounts.google.com/gsi/client';sdk.async=true;sdk.defer=true;sdk.onload=showGoogleButtons;document.head.append(sdk)}catch(e){/* local setup without Google is supported */}}
initGoogle();
const watch=new MutationObserver(()=>{if(google.initialized)showGoogleButtons();decorateStudio()});watch.observe(document.body,{childList:true,subtree:true});
// Save vacancies without pretending that it is an application.
document.addEventListener('click',e=>{
 const googleButton=e.target.closest('.google-auth-slot');if(googleButton)window.sivrceGoogleLink=googleButton.dataset.googleMode==='link';
 const close=e.target.closest('[data-close-job]');if(close){if(!confirm('დახურო ვაკანსია? ახალი განაცხადები აღარ მიიღება.'))return;requireSession(async()=>{try{await request('/api/jobs/'+close.dataset.closeJob+'/close',{method:'POST'});feedback('ვაკანსია დაიხურა');location.reload()}catch(err){feedback(err.message)}})}
 const save=e.target.closest('[data-save-job]');if(save){const id=Number(save.dataset.saveJob);requireSession(async()=>{try{await request(`/api/jobs/${id}/save`,{method:'POST'});save.textContent='★ შენახულია';save.disabled=true;feedback('ვაკანსია დაემატა შენახულებში')}catch(err){feedback(err.message)}})}
 const interest=e.target.closest('[data-course-interest]');if(interest){requireSession(()=>openTaskDialog({title:'სასწავლო ჯგუფზე დაინტერესება',subtitle:'გაგზავნე მოთხოვნა მომწოდებელთან. თანხა არ ჩამოგეჭრება და ადგილი ავტომატურად არ დასტურდება.',fields:`<label>შეტყობინება მომწოდებელს<textarea name="note" rows="4" maxlength="1000" placeholder="რას ისურვებდი ამ კურსის შესახებ იცოდე?"></textarea></label>`,action:async d=>{await request('/api/cohorts/'+interest.dataset.courseInterest+'/interest',{method:'POST',body:d});interest.textContent='მოთხოვნა გაგზავნილია';interest.disabled=true;feedback('დაინტერესება გაგზავნილია')}}))}
 const meeting=e.target.closest('.interview-action');if(meeting){requireSession(()=>openTaskDialog({title:'გასაუბრების ჩანიშვნა',subtitle:'კანდიდატი საკუთარ Studio-ში დაინახავს შეხვედრის დეტალებს. ელფოსტა ამ ეტაპზე არ იგზავნება.',fields:`<label>თარიღი და დრო · თბილისი<input type="datetime-local" name="scheduled_for" required></label><label>ფორმატი<select name="format"><option value="online">ონლაინ</option><option value="onsite">ადგილზე</option><option value="phone">ტელეფონი</option></select></label><label>ლინკი ან მისამართი<input name="location_or_link" minlength="5" maxlength="320" required></label><label>შეტყობინება კანდიდატს<textarea name="candidate_note" rows="3" maxlength="1200"></textarea></label>`,action:async d=>{await request(`/api/applications/${meeting.dataset.application}/interviews`,{method:'POST',body:d});feedback('გასაუბრება ჩაინიშნა. კანდიდატს დეტალები თავის ანგარიშში გამოუჩნდება')}}))}
 const status=e.target.closest('[data-interest-status]');if(status){requireSession(async()=>{try{await request('/api/course-interests/'+status.dataset.interestId,{method:'PATCH',body:{status:status.dataset.interestStatus}});feedback('კურსზე დაინტერესების სტატუსი განახლდა');status.closest('.studio-item')?.remove()}catch(err){feedback(err.message)}})}
 const withdraw=e.target.closest('[data-withdraw]');if(withdraw){if(!confirm('გსურს განაცხადის უკან გამოთხოვა? CV და განაცხადი წაიშლება ამ განაცხადიდან.'))return;requireSession(async()=>{try{await request('/api/my-applications/'+withdraw.dataset.withdraw,{method:'DELETE'});feedback('განაცხადი გამოთხოვილია');withdraw.closest('.studio-item')?.remove()}catch(err){feedback(err.message)}})}
});
// Dynamic studio widgets: applicant privacy, course leads, saved opportunities, interview dates.
let studioBuiltFor=null, studioLoading=false;
async function decorateStudio(){
 const parent=$('#candidate-data'), root=$('#studio-root');if(!parent||!root||studioLoading)return;
 if(parent.dataset.upgrade==='1')return;parent.dataset.upgrade='1';studioLoading=true;
 const box=document.createElement('div');box.className='app-utility-box';box.innerHTML='<h4>შენახული ვაკანსიები</h4><div class="sivrce-saved">იტვირთება...</div><h4 style="margin-top:28px">ჩემი გასაუბრებები</h4><div class="sivrce-interviews">იტვირთება...</div><h4 style="margin-top:28px">სასწავლო პროგრამებზე ინტერესი</h4><div class="sivrce-interests">იტვირთება...</div>';
 parent.append(box);
 try{
 const [saved,meetings,interests,apps]=await Promise.all([request('/api/my-saved-jobs'),request('/api/my-interviews'),request('/api/my-course-interests'),request('/api/my-applications')]);
 $('.sivrce-saved',box).innerHTML=saved.length?saved.map(j=>`<div class="studio-item"><a href="/careers/${j.id}">${escapeHTML(j.title)} / ${escapeHTML(j.company)} ↗</a></div>`).join(''):'<p>შენახული ვაკანსიები ჯერ არ გაქვს.</p>';
 $('.sivrce-interviews',box).innerHTML=meetings.length?meetings.map(x=>`<div class="studio-item"><div><strong>${escapeHTML(x.job)}</strong><small>${escapeHTML(x.company)} · ${escapeHTML(x.scheduled_for.replace('T',' '))} · ${escapeHTML(x.format)}</small><small>${escapeHTML(x.location_or_link)}</small></div></div>`).join(''):'<p>გასაუბრება ჯერ არ არის ჩანიშნული.</p>';
 $('.sivrce-interests',box).innerHTML=interests.length?interests.map(x=>`<div class="studio-item"><strong>${escapeHTML(x.title)}</strong><small>${escapeHTML(x.starts)} · ${escapeHTML(x.status)}</small></div>`).join(''):'<p>არცერთ სასწავლო ჯგუფზე მოთხოვნა არ გაქვს.</p>';
 const list=$('#my-apps');if(list&&apps.length){list.innerHTML=apps.map(a=>`<div class="studio-item"><div><strong>${escapeHTML(a.title)}</strong><small>${escapeHTML(a.status)} · ${escapeHTML(a.created.slice(0,10))}</small></div><button class="small-action" data-withdraw="${a.id}">გამოითხოვე</button></div>`).join('')}
 }catch(e){box.innerHTML='<p>მონაცემების ჩატვირთვა ვერ დასრულდა: '+escapeHTML(e.message)+'</p>'}
 finally{studioLoading=false}
 // Org dashboards may be inserted after this extension, and get extra workflow widgets below.
}
// Add organization-specific capabilities after the original studio renders.
let orgObserverPending=false;
const orgObserver=new MutationObserver(async()=>{
 if(orgObserverPending)return;
 const orgs=$$('[data-org]');if(!orgs.length)return;orgObserverPending=true;
 for(const el of orgs){const id=Number(el.dataset.org);const data=$('#data-'+id);if(!data||!data.querySelector('.studio-section')||data.dataset.extended==='1')continue;data.dataset.extended='1';
  const company=data.textContent.includes('კანდიდატები')||data.textContent.includes('ვაკანსიები');
  const pane=document.createElement('div');pane.className='app-utility-box';data.append(pane);
  try{
   const route=company?`/api/organizations/${id}/interviews`:`/api/organizations/${id}/course-interests`;
   const rows=await request(route);
   pane.innerHTML=company?`<h4>ჩანიშნული გასაუბრებები / ${rows.length}</h4>`+ (rows.map(x=>`<div class="studio-item"><div><strong>${escapeHTML(x.candidate)} · ${escapeHTML(x.job)}</strong><small>${escapeHTML(x.scheduled_for.replace('T',' '))} · ${escapeHTML(x.format)}</small></div></div>`).join('')||'<p>ჯერჯერობით არაფერი ჩანიშნულა.</p>'):`<h4>სასწავლო ჯგუფების მოთხოვნები / ${rows.length}</h4>`+ (rows.map(x=>`<div class="studio-item"><div><strong>${escapeHTML(x.name)} — ${escapeHTML(x.title)}</strong><small>${escapeHTML(x.email)} · ${escapeHTML(x.starts)} · ${escapeHTML(x.status)}</small><small>${escapeHTML(x.note)}</small></div>${x.status==='requested'?`<div><button class="small-action" data-interest-status="confirmed" data-interest-id="${x.id}">დაადასტურე</button><button class="small-action" data-interest-status="declined" data-interest-id="${x.id}">უარყავი</button></div>`:''}</div>`).join('')||'<p>რეგისტრაციის მოთხოვნები ჯერ არ არის.</p>')+`<form class="csv-import-form" data-org-id="${id}"><h4>სასწავლო პროგრამების CSV იმპორტი</h4><p>სავალდებულო ველები: title, category, format, description, outcomes, curriculum, trainer, price, duration. ყოველი ჩანაწერი გადის მოდერაციას.</p><input type="file" name="catalog" accept=".csv,text/csv" required><label style="display:block;margin-top:12px;font-size:12px"><input type="checkbox" name="rights_attested" value="true" required> ვადასტურებ, რომ კურსებისა და ტექსტების გამოქვეყნების უფლებას ვფლობ.</label><button type="submit" class="small-action">კატალოგის იმპორტი ↗</button><p class="import-status" role="status"></p></form>`;
  }catch(e){pane.textContent='დამატებითი მონაცემები ვერ ჩაიტვირთა: '+e.message}
 }
 orgObserverPending=false;
});orgObserver.observe(document.body,{childList:true,subtree:true});
document.addEventListener('submit',async e=>{
 const form=e.target.closest('.csv-import-form');if(!form)return;e.preventDefault();const out=$('.import-status',form);out.textContent='იტვირთება…';
 try{const me=await request('/api/me');if(!me.user)throw new Error('შესვლა აუცილებელია');
 const r=await fetch(`/api/organizations/${form.dataset.orgId}/courses/import-csv`,{method:'POST',credentials:'same-origin',headers:{'X-SIVRCE-CSRF':me.csrf},body:new FormData(form)});
 const data=await r.json();if(!r.ok)throw new Error(data.detail||'იმპორტი ვერ დასრულდა');out.textContent=`იმპორტირებულია ${data.imported} კურსი. სტატუსი: ${data.status}. საჯაროდ გამოჩნდება მოდერაციის შემდეგ.`;form.reset();
 }catch(error){out.textContent=error.message}
});
// Pilot requests are real local records; not mock billing or auto-messaging.
const pilot=$('#pilot-form');if(pilot)pilot.addEventListener('submit',async e=>{
 e.preventDefault();const b=$('button',pilot),f=$('#pilot-feedback');b.disabled=true;f.textContent='';
 try{const payload=Object.fromEntries(new FormData(pilot).entries());await request('/api/pilot-interest',{method:'POST',body:payload});f.textContent='დაინტერესება შენახულია. სერვისი ჯერ საპილოტე რეჟიმშია და ავტომატური პასუხი არ იგზავნება.';pilot.reset()}
 catch(err){f.textContent=err.message}finally{b.disabled=false}
});
})();
