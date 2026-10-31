import os,sys,io,datetime as dt
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
os.environ['DATABASE_URL']=os.environ.get('TEST_DATABASE_URL','sqlite:///'+str(Path(__file__).resolve().parent/'integration-test.db'))
os.environ['SEED_DEMO']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import server
from server import app,engine,Base,Local,User,GoogleIdentity

@pytest.fixture(autouse=True)
def reset():
 Base.metadata.drop_all(engine)
 Base.metadata.create_all(engine)
 yield
 Base.metadata.drop_all(engine)

def login(c,email):
 r=c.post('/api/auth/login',json={'email':email,'password':'DemoOnly!234'}); assert r.status_code==200,r.text
 c.headers['X-SIVRCE-CSRF']=r.json()['csrf']
 return r.json()

def make_pdf():return io.BytesIO(b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF')

def test_original_georgian_journal_and_business():
 with TestClient(app) as c:
  for page in ['/journal','/journal/job-transparency-is-a-product','/business']:
   r=c.get(page);assert r.status_code==200,r.text[:300]
   assert 'SIVRCE' in r.text
  articles=c.get('/api/journal').json();assert len(articles)>=3
  assert all('title' in x for x in articles)
  # fictitious job data must not carry search-engine structured vacancies
  r=c.get('/careers/1');assert r.status_code==200;assert 'application/ld+json' not in r.text


def test_saved_jobs_and_candidate_right_to_withdraw(tmp_path):
 with TestClient(app) as c,TestClient(app) as company:
  login(c,'candidate@demo.sivrce.ge');login(company,'company@demo.sivrce.ge')
  assert c.post('/api/jobs/1/save').status_code==200
  assert c.post('/api/jobs/1/save').status_code==200
  assert len(c.get('/api/my-saved-jobs').json())==1
  assert c.delete('/api/jobs/1/save').json()=={'saved':False}
  assert c.get('/api/my-saved-jobs').json()==[]
  r=c.post('/api/jobs/1/apply-pdf',data={'motivation':'მე მაქვს შესაბამისი გამოცდილება და დაინტერესებული ვარ ამ ახალი შესაძლებლობით.'},files={'cv':('cv.pdf',make_pdf(),'application/pdf')});assert r.status_code==200,r.text
  aid=r.json()['id'];assert company.get(f'/api/applications/{aid}/cv').status_code==200
  assert company.delete(f'/api/my-applications/{aid}').status_code==403
  assert c.delete(f'/api/my-applications/{aid}').status_code==200
  assert c.get('/api/my-applications').json()==[]
  assert company.get(f'/api/applications/{aid}/cv').status_code==404


def test_interview_privacy_and_course_lead():
 with TestClient(app) as candidate,TestClient(app) as employer,TestClient(app) as provider:
  login(candidate,'candidate@demo.sivrce.ge');login(employer,'company@demo.sivrce.ge');login(provider,'provider@demo.sivrce.ge')
  r=candidate.post('/api/jobs/1/apply',json={'profile_url':'https://example.com/cv.pdf','motivation':'დაინტერესებული ვარ სამუშაოთი და მაქვს პოზიციისთვის შესაბამისი გამოცდილება.'});assert r.status_code==200,r.text
  aid=r.json()['id']
  future=(dt.datetime.now()+dt.timedelta(days=3)).replace(microsecond=0).isoformat()
  payload={'scheduled_for':future,'format':'online','location_or_link':'https://meet.example.org/one','candidate_note':'შეხვედრა'}
  assert provider.post(f'/api/applications/{aid}/interviews',json=payload).status_code==403
  r=employer.post(f'/api/applications/{aid}/interviews',json=payload)
  assert r.status_code==200,r.text
  assert r.json()['status']=='interview'
  meetings=candidate.get('/api/my-interviews').json();assert len(meetings)==1
  assert meetings[0]['company'].endswith('DEMO')
  r=candidate.post('/api/cohorts/1/interest',json={'note':'მაინტერესებს სასწავლო პროგრამის დეტალები.'});assert r.status_code==200,r.text
  assert r.json()['payment_collected'] is False
  assert candidate.post('/api/cohorts/1/interest',json={'note':'გამეორებული'}).status_code==409
  assert provider.get('/api/organizations/2/course-interests').json()[0]['email']=='candidate@demo.sivrce.ge'
  assert employer.get('/api/organizations/2/course-interests').status_code==403


def test_rights_permissions_and_pilot():
 with TestClient(app) as outsider, TestClient(app) as admin:
  login(outsider,'candidate@demo.sivrce.ge');login(admin,'admin@demo.sivrce.ge')
  data={'content_type':'episode','content_id':1,'source_url':'https://open.spotify.com/show/test','rights_holder':'Publisher','permitted_use':'licensed_dubbing','evidence':''}
  assert outsider.post('/api/admin/content-rights',json=data).status_code==403
  assert admin.post('/api/admin/content-rights',json=data).status_code==422
  data['evidence']='Rights owner granted license in signed written agreement dated 2026-10-10.'
  assert admin.post('/api/admin/content-rights',json=data).status_code==200
  assert admin.get('/api/admin/content-rights').json()[0]['permitted_use']=='licensed_dubbing'
  lead={'organization':'Company LLC','email':'hr@example.org','need':'both','message':'Interested in company pilot.'}
  assert outsider.post('/api/pilot-interest',json=lead).status_code==201
  assert len(admin.get('/api/admin/pilot-interest').json())==1
  assert outsider.get('/api/admin/pilot-interest').status_code==403


def test_google_login_security_and_link(monkeypatch):
 with TestClient(app) as c:
  monkeypatch.setattr(server,'GOOGLE_CLIENT_ID','test-client')
  def verify(token):return {'sub':token,'email':'newuser@example.org','name':'Google User','email_verified':True}
  monkeypatch.setattr(server,'verify_google_credential',verify)
  # Strict same-origin guard prevents login CSRF.
  assert c.post('/api/auth/google',json={'credential':'x'*50}).status_code==403
  r=c.post('/api/auth/google',headers={'origin':'http://testserver'},json={'credential':'a'*50})
  assert r.status_code==200,r.text
  assert c.get('/api/me').json()['user']['email']=='newuser@example.org'
  assert c.post('/api/auth/google',headers={'origin':'http://testserver'},json={'credential':'a'*50}).status_code==200
  # An existing password account must be explicitly linked rather than silently hijacked.
  monkeypatch.setattr(server,'verify_google_credential',lambda token:{'sub':'other-identity','email':'company@demo.sivrce.ge','name':'Wrong','email_verified':True})
  assert c.post('/api/auth/google',headers={'origin':'http://testserver'},json={'credential':'x'*50}).status_code==409

def test_provider_csv_import_requires_rights_and_moderation():
 csv_data=('title,category,format,description,outcomes,curriculum,trainer,price,duration\n'
           'Business Analytics Foundations,ანალიტიკა,ონლაინ,'
           'კურსის დეტალური აღწერა მონაცემთა ანალიზის პრაქტიკული გამოყენებისთვის,'
           'მონაცემების გაწმენდა და ვიზუალიზაცია პრაქტიკული ქეისებით,'
           'ცხრილების მომზადება და ვიზუალიზაცია პრაქტიკაში,ლექტორი ტესტი,120,8 საათი\n').encode('utf-8')
 with TestClient(app) as provider,TestClient(app) as admin:
  login(provider,'provider@demo.sivrce.ge');login(admin,'admin@demo.sivrce.ge')
  r=provider.post('/api/organizations/2/courses/import-csv',data={'rights_attested':'false'},files={'catalog':('catalog.csv',io.BytesIO(csv_data),'text/csv')})
  assert r.status_code==422
  r=provider.post('/api/organizations/2/courses/import-csv',data={'rights_attested':'true'},files={'catalog':('catalog.csv',io.BytesIO(csv_data),'text/csv')})
  assert r.status_code==200,r.text
  assert r.json()['status']=='pending_review'
  assert r.json()['imported']==1
  rid=r.json()['course_ids'][0]
  assert any(course['id']==rid for course in admin.get('/api/admin/review-queue').json()['courses'])
  assert admin.post(f'/api/admin/review/course/{rid}/approve').status_code==200
  assert any(course['id']==rid for course in provider.get('/api/courses').json())


def test_provider_confirmed_interest_and_job_closure():
 with TestClient(app) as candidate,TestClient(app) as provider,TestClient(app) as employer:
  login(candidate,'candidate@demo.sivrce.ge');login(provider,'provider@demo.sivrce.ge');login(employer,'company@demo.sivrce.ge')
  rid=candidate.post('/api/cohorts/1/interest',json={'note':''}).json()['id']
  assert candidate.patch(f'/api/course-interests/{rid}',json={'status':'confirmed'}).status_code==403
  assert provider.patch(f'/api/course-interests/{rid}',json={'status':'confirmed'}).status_code==200
  assert candidate.get('/api/my-course-interests').json()[0]['status']=='confirmed'
  assert employer.post('/api/jobs/1/close').status_code==200
  assert not any(j['id']==1 for j in candidate.get('/api/jobs').json())


def test_v5_business_experience_and_static_assets():
 with TestClient(app) as c:
  business=c.get('/business')
  assert business.status_code==200
  assert 'ადამიანებთან<br>დაკავშირებული საქმე' in business.text
  assert '/business/experience' in business.text
  assert 'საჩვენებელი მონაცემები' in business.text
  experience=c.get('/business/experience')
  assert experience.status_code==200
  for text in ('კანდიდატები','ვაკანსიის შექმნა','სწავლება და შესყიდვა','შედარება','საჩვენებელი მონაცემები'):
   assert text in experience.text
  assert 'workbench_v5.js' in experience.text
  assert c.get('/static/product_v5.css').status_code==200
  js=c.get('/static/workbench_v5.js')
  assert js.status_code==200
  assert 'function renderPipeline' in js.text
  assert 'function jobQuality' in js.text
  assert 'function renderCompare' in js.text
  assert c.get('/business/overview').status_code==200


def test_v5_public_demo_does_not_create_private_data():
 with TestClient(app) as c:
  before=c.get('/api/jobs').json()
  assert c.get('/business/experience').status_code==200
  assert c.get('/api/jobs').json()==before
  # A public visitor must not publish or alter a vacancy by direct API access.
  response=c.post('/api/jobs',json={})
  assert response.status_code==401


def test_v5_connected_company_onboarding_page():
 with TestClient(app) as c:
  page=c.get('/start')
  assert page.status_code==200
  assert 'შედი ან შექმენი ანგარიში' in page.text
  assert 'გადამოწმების მოთხოვნა' in page.text and 'data-role="provider"' in page.text
  assert '/static/onboarding_v5.js' in page.text
  js=c.get('/static/onboarding_v5.js')
  assert js.status_code==200
  assert '/api/auth/google/config' in js.text
  assert '/api/organizations/' in js.text
  assert '/api/auth/register' in js.text
