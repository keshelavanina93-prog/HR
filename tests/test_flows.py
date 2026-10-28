import os,sys,io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Use a completely isolated test database, never modify the user's dev database.
TEST_ROOT=Path(__file__).resolve().parent
os.environ['DATABASE_URL']='sqlite:///'+str(TEST_ROOT/'integration-test.db')
os.environ['SEED_DEMO']='1'
sys.path.insert(0,str(TEST_ROOT.parent))
from server import app,engine,Base,Local,User,Membership,Organization,Job

@pytest.fixture(autouse=True)
def db_reset():
 Base.metadata.drop_all(engine)
 Base.metadata.create_all(engine)
 yield
 Base.metadata.drop_all(engine)

def login(client,email,password='DemoOnly!234'):
 r=client.post('/api/auth/login',json={'email':email,'password':password})
 assert r.status_code==200,r.text
 client.headers['X-SIVRCE-CSRF']=r.json()['csrf']
 return r.json()

def make_job(org_id=1):
 return {'org_id':org_id,'title':'Senior People Operations Specialist','department':'Human Resources','location':'თბილისი','work_mode':'ჰიბრიდული','employment':'სრული განაკვეთი','salary_min':3000,'salary_max':4500,'salary_basis':'gross','purpose':'გუნდის განვითარების და თანამშრომლის გამოცდილების შედეგების გაუმჯობესება.','responsibilities':'მართე სამუშაო პროცესების დახვეწა და გუნდის მიზნების შეფასება; შექმენი შედეგების გაზომვის სისტემა.','requirements':'მინიმუმ სამი წლის გამოცდილება, მონაცემების გაანალიზების უნარი და პროცესების მართვა.','benefits':'ჯანმრთელობის დაზღვევა','hiring_steps':'განაცხადების მიმოხილვა → გასაუბრება → საბოლოო გადაწყვეტილება','deadline':'2026-12-31','publish':True}

def test_public_pages_and_demo_labels():
 with TestClient(app) as c:
  for path in ['/','/careers','/careers/1','/learn','/learn/1','/exchange','/voices','/standards','/studio']:
   r=c.get(path);assert r.status_code==200,(path,r.text[:400])
   assert 'SIVRCE' in r.text
  jobs=c.get('/api/jobs').json();assert len(jobs)==3
  assert all(j['salary_min']>0 and j['salary_max'] and j['demo'] for j in jobs)
  assert c.get('/api/briefs').json()[0]['demo'] is True

def test_candidates_upload_pdf_and_cross_tenant_privacy(tmp_path):
 with TestClient(app) as candidate,TestClient(app) as employer,TestClient(app) as other:
  login(candidate,'candidate@demo.sivrce.ge')
  pdf=b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'
  r=candidate.post('/api/jobs/1/apply-pdf',data={'motivation':'ეს არის კონკრეტული მოტივაცია სამუშაოზე რეალური გამოცდილებით.'},files={'cv':('curriculum.pdf',io.BytesIO(pdf),'application/pdf')})
  assert r.status_code==200,r.text
  aid=r.json()['id']
  assert candidate.get(f'/api/applications/{aid}/cv').status_code==200
  assert other.get(f'/api/applications/{aid}/cv').status_code==401
  login(other,'provider@demo.sivrce.ge')
  assert other.get(f'/api/applications/{aid}/cv').status_code==403
  assert other.get('/api/organizations/1/applications').status_code==403
  login(employer,'company@demo.sivrce.ge')
  apps=employer.get('/api/organizations/1/applications').json();assert len(apps)==1
  assert apps[0]['cv_url']==f'/api/applications/{aid}/cv'
  assert employer.get(f'/api/applications/{aid}/cv').status_code==200
  assert employer.patch(f'/api/applications/{aid}',json={'status':'interview'}).status_code==200
  assert candidate.get('/api/my-applications').json()[0]['status']=='interview'
  assert candidate.post('/api/jobs/1/apply',json={'profile_url':'https://example.org/cv','motivation':'სერიოზული გამოცდილება და სურვილი მაქვს ამ როლისთვის.'}).status_code==409

def test_verification_then_human_content_review():
 with TestClient(app) as c,TestClient(app) as admin:
  assert c.post('/api/jobs',json=make_job()).status_code==401
  login(c,'candidate@demo.sivrce.ge')
  r=c.post('/api/organizations',json={'name':'Test Talent Partners LLC','kind':'company','website':'https://example.org','registration_code':'123456789','description':'ეს არის სატესტო კომპანიის დეტალური აღწერა და მინიმალური საჭირო ინფორმაცია.'})
  assert r.status_code==200,r.text;org=r.json()['id']
  assert c.post('/api/jobs',json=make_job(org)).status_code==403
  assert c.post(f'/api/organizations/{org}/request-verification',json={}).status_code==200
  login(admin,'admin@demo.sivrce.ge')
  assert any(o['id']==org for o in admin.get('/api/admin/pending').json())
  assert admin.post(f'/api/admin/verify/{org}',json={}).status_code==200
  r=c.post('/api/jobs',json=make_job(org));assert r.status_code==200,r.text
  jid=r.json()['id'];assert r.json()['status']=='pending_review'
  assert not any(j['id']==jid for j in c.get('/api/jobs').json())
  queue=admin.get('/api/admin/review-queue').json();assert any(j['id']==jid for j in queue['jobs'])
  assert c.post(f'/api/admin/review/job/{jid}/approve',json={}).status_code==403
  assert admin.post(f'/api/admin/review/job/{jid}/approve',json={}).status_code==200
  assert any(j['id']==jid for j in c.get('/api/jobs').json())

def test_salary_and_content_quality_are_enforced():
 with TestClient(app) as c:
  login(c,'company@demo.sivrce.ge')
  b=make_job();b['salary_min']=0
  assert c.post('/api/jobs',json=b).status_code==422
  b=make_job();b['salary_max']=10
  assert c.post('/api/jobs',json=b).status_code==422
  b=make_job();b['purpose']='კარგი სამუშაო'
  assert c.post('/api/jobs',json=b).status_code==422
  b=make_job();b['deadline']='2020-01-01'
  assert c.post('/api/jobs',json=b).status_code==422
  c.headers.pop('X-SIVRCE-CSRF')
  assert c.post('/api/jobs',json=make_job()).status_code==403

def test_training_proposals_are_private_and_selectable():
 with TestClient(app) as buyer,TestClient(app) as supplier,TestClient(app) as candidate:
  login(buyer,'company@demo.sivrce.ge')
  login(supplier,'provider@demo.sivrce.ge')
  login(candidate,'candidate@demo.sivrce.ge')
  r=supplier.post('/api/briefs/1/proposals',json={'org_id':2,'price':3300,'days':2,'trainer':'დემო ტრენერი','approach':'ორი დღის განმავლობაში მონაწილეები გაივლიან პრაქტიკულ ქეისებს და მიიღებენ უკუკავშირს წინასწარ განსაზღვრული შედეგებით.'})
  assert r.status_code==200,r.text
  propid=r.json()['id']
  assert supplier.get('/api/organizations/2/proposals').status_code==200
  assert candidate.get('/api/organizations/1/proposals').status_code==403
  assert buyer.get('/api/organizations/1/proposals').json()[0]['id']==propid
  assert supplier.post(f'/api/proposals/{propid}/select',json={}).status_code==403
  assert buyer.post(f'/api/proposals/{propid}/select',json={}).status_code==200
  assert supplier.get('/api/organizations/2/proposals').json()[0]['status']=='selected'

def test_podcast_and_no_autoplay():
 with TestClient(app) as c:
  episodes=c.get('/api/voices').json()
  assert all(ep['spotify'].startswith('https://open.spotify.com/show/') for ep in episodes)
  js=c.get('/static/app.js').text
  assert 'start-embed' in js and 'open.spotify.com/embed/show/' in js

def test_voices_editorial_moderation():
 with TestClient(app) as c,TestClient(app) as editor:
  login(c,'candidate@demo.sivrce.ge'); login(editor,'admin@demo.sivrce.ge')
  data={'title':'The Professional Signals Podcast','publisher':'Editorial Network','topic':'Work / Research','summary':'პროფესიული განვითარების შესახებ დადასტურებულ კვლევებზე დაფუძნებული საუბრები და პრაქტიკული მაგალითები.','spotify':'https://open.spotify.com/show/AB123TESTONLY'}
  assert c.post('/api/admin/voices',json=data).status_code==403
  assert editor.post('/api/admin/voices',json={**data,'spotify':'javascript:alert(1)'}).status_code==422
  r=editor.post('/api/admin/voices',json=data);assert r.status_code==200,r.text
  eid=r.json()['id'];assert any(v['id']==eid for v in c.get('/api/voices').json())
  assert c.post(f'/api/admin/voices/{eid}/archive',json={}).status_code==403
  assert editor.post(f'/api/admin/voices/{eid}/archive',json={}).status_code==200
  assert not any(v['id']==eid for v in c.get('/api/voices').json())

def test_invalid_files_and_external_member_do_not_leak():
 with TestClient(app) as c,TestClient(app) as employer:
  login(c,'candidate@demo.sivrce.ge');login(employer,'company@demo.sivrce.ge')
  assert c.post('/api/jobs/1/apply-pdf',data={'motivation':'ეს არის CV-ზე მოტივაციის საკმარისად დიდი ტექსტი.'},files={'cv':('wrong.pdf',io.BytesIO(b'not a pdf'),'application/pdf')}).status_code==422
  assert c.get('/api/organizations/2/proposals').status_code==403
  assert employer.post('/api/jobs/1/apply-pdf',data={'motivation':'ეს არის CV-ზე მოტივაციის საკმარისად დიდი ტექსტი.'},files={'cv':('wrong.exe',io.BytesIO(b'evil'),'application/octet-stream')}).status_code==422
