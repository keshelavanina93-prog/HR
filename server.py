"""SIVRCE — functional local multi-user product beta. Not a production security certification."""
from __future__ import annotations
import os, re, secrets, hashlib, datetime as dt, json
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import create_engine, ForeignKey, String, Text, Integer, Boolean, DateTime, UniqueConstraint, select, desc, func, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ROOT=Path(__file__).resolve().parent
DB_URL=os.environ.get('DATABASE_URL',f'sqlite:///{ROOT}/sivrce.db')
engine=create_engine(DB_URL, connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {}, pool_pre_ping=True)
if DB_URL.startswith('sqlite'):
 @event.listens_for(engine,'connect')
 def sqlite_foreign_keys(connection,record):
  cursor=connection.cursor();cursor.execute('PRAGMA foreign_keys=ON');cursor.close()
Local=sessionmaker(engine, expire_on_commit=False)
PW=PasswordHasher(time_cost=2,memory_cost=16384,parallelism=1)
COOKIE_SECURE=os.environ.get('COOKIE_SECURE','0')=='1'

def utcnow():return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):pass
class User(Base):
 __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(100)); email:Mapped[str]=mapped_column(String(160),unique=True,index=True); pw_hash:Mapped[str]=mapped_column(String(300)); admin:Mapped[bool]=mapped_column(Boolean,default=False); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class AuthSession(Base):
 __tablename__='auth_sessions'; id:Mapped[int]=mapped_column(primary_key=True); token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); expires:Mapped[dt.datetime]=mapped_column(DateTime); csrf:Mapped[str]=mapped_column(String(80))
class Organization(Base):
 __tablename__='organizations'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(130)); slug:Mapped[str]=mapped_column(String(160),unique=True); kind:Mapped[str]=mapped_column(String(16)); description:Mapped[str]=mapped_column(Text,default=''); location:Mapped[str]=mapped_column(String(150),default='თბილისი'); website:Mapped[str]=mapped_column(String(220),default='');registration_code:Mapped[str]=mapped_column(String(30),default=''); verified:Mapped[bool]=mapped_column(Boolean,default=False); verification_requested:Mapped[bool]=mapped_column(Boolean,default=False); demo:Mapped[bool]=mapped_column(Boolean,default=False); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class Membership(Base):
 __tablename__='memberships'; id:Mapped[int]=mapped_column(primary_key=True); org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id')); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); role:Mapped[str]=mapped_column(String(16),default='owner'); __table_args__=(UniqueConstraint('org_id','user_id'),)
class Job(Base):
 __tablename__='jobs'; id:Mapped[int]=mapped_column(primary_key=True); org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id')); title:Mapped[str]=mapped_column(String(140)); department:Mapped[str]=mapped_column(String(100)); location:Mapped[str]=mapped_column(String(140)); work_mode:Mapped[str]=mapped_column(String(30)); employment:Mapped[str]=mapped_column(String(45)); salary_min:Mapped[int]=mapped_column(Integer); salary_max:Mapped[int]=mapped_column(Integer); salary_basis:Mapped[str]=mapped_column(String(15)); currency:Mapped[str]=mapped_column(String(6),default='GEL'); purpose:Mapped[str]=mapped_column(Text); responsibilities:Mapped[str]=mapped_column(Text); requirements:Mapped[str]=mapped_column(Text); benefits:Mapped[str]=mapped_column(Text,default=''); hiring_steps:Mapped[str]=mapped_column(Text); deadline:Mapped[str]=mapped_column(String(10)); status:Mapped[str]=mapped_column(String(16),default='draft'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class Application(Base):
 __tablename__='applications'; id:Mapped[int]=mapped_column(primary_key=True); job_id:Mapped[int]=mapped_column(ForeignKey('jobs.id')); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); cv_key:Mapped[Optional[str]]=mapped_column(String(100),nullable=True); profile_url:Mapped[str]=mapped_column(String(400),default=''); motivation:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(30),default='received'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow); __table_args__=(UniqueConstraint('job_id','user_id'),)
class Course(Base):
 __tablename__='courses'; id:Mapped[int]=mapped_column(primary_key=True); org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id')); title:Mapped[str]=mapped_column(String(180)); category:Mapped[str]=mapped_column(String(100)); format:Mapped[str]=mapped_column(String(30)); description:Mapped[str]=mapped_column(Text); outcomes:Mapped[str]=mapped_column(Text); curriculum:Mapped[str]=mapped_column(Text); trainer:Mapped[str]=mapped_column(String(140)); price:Mapped[int]=mapped_column(Integer); duration:Mapped[str]=mapped_column(String(60)); status:Mapped[str]=mapped_column(String(16),default='draft'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class Cohort(Base):
 __tablename__='cohorts'; id:Mapped[int]=mapped_column(primary_key=True); course_id:Mapped[int]=mapped_column(ForeignKey('courses.id')); starts:Mapped[str]=mapped_column(String(10)); capacity:Mapped[int]=mapped_column(Integer); location:Mapped[str]=mapped_column(String(140)); active:Mapped[bool]=mapped_column(Boolean,default=True)
class Brief(Base):
 __tablename__='briefs'; id:Mapped[int]=mapped_column(primary_key=True); org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id')); title:Mapped[str]=mapped_column(String(150)); goal:Mapped[str]=mapped_column(Text); audience:Mapped[int]=mapped_column(Integer); budget:Mapped[int]=mapped_column(Integer); format:Mapped[str]=mapped_column(String(40)); deadline:Mapped[str]=mapped_column(String(10)); visibility:Mapped[str]=mapped_column(String(16),default='public'); status:Mapped[str]=mapped_column(String(16),default='draft'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class Proposal(Base):
 __tablename__='proposals'; id:Mapped[int]=mapped_column(primary_key=True); brief_id:Mapped[int]=mapped_column(ForeignKey('briefs.id')); org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id')); price:Mapped[int]=mapped_column(Integer); approach:Mapped[str]=mapped_column(Text); trainer:Mapped[str]=mapped_column(String(150)); days:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(20),default='submitted'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow); __table_args__=(UniqueConstraint('brief_id','org_id'),)
class Episode(Base):
 __tablename__='episodes'; id:Mapped[int]=mapped_column(primary_key=True); publisher:Mapped[str]=mapped_column(String(140)); title:Mapped[str]=mapped_column(String(180)); topic:Mapped[str]=mapped_column(String(140)); summary:Mapped[str]=mapped_column(Text); spotify:Mapped[str]=mapped_column(String(260),unique=True); status:Mapped[str]=mapped_column(String(20),default='published'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class Audit(Base):
 __tablename__='audit'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); org_id:Mapped[Optional[int]]=mapped_column(Integer,nullable=True); action:Mapped[str]=mapped_column(String(90)); target:Mapped[str]=mapped_column(String(90)); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)


# vNext additions are intentionally separate tables to preserve existing beta data.
class GoogleIdentity(Base):
 __tablename__='google_identities'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),unique=True); google_sub:Mapped[str]=mapped_column(String(180),unique=True,index=True); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class SavedJob(Base):
 __tablename__='saved_jobs'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); job_id:Mapped[int]=mapped_column(ForeignKey('jobs.id')); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow); __table_args__=(UniqueConstraint('user_id','job_id'),)
class Interview(Base):
 __tablename__='interviews'; id:Mapped[int]=mapped_column(primary_key=True); application_id:Mapped[int]=mapped_column(ForeignKey('applications.id')); scheduled_for:Mapped[dt.datetime]=mapped_column(DateTime); format:Mapped[str]=mapped_column(String(20)); location_or_link:Mapped[str]=mapped_column(String(320)); candidate_note:Mapped[str]=mapped_column(Text,default=''); created_by:Mapped[int]=mapped_column(ForeignKey('users.id')); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class CourseInterest(Base):
 __tablename__='course_interests'; id:Mapped[int]=mapped_column(primary_key=True); cohort_id:Mapped[int]=mapped_column(ForeignKey('cohorts.id')); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); note:Mapped[str]=mapped_column(Text,default=''); status:Mapped[str]=mapped_column(String(25),default='requested'); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow); __table_args__=(UniqueConstraint('cohort_id','user_id'),)
class EditorialArticle(Base):
 __tablename__='editorial_articles'; id:Mapped[int]=mapped_column(primary_key=True); slug:Mapped[str]=mapped_column(String(180),unique=True); title:Mapped[str]=mapped_column(String(240)); section:Mapped[str]=mapped_column(String(100)); deck:Mapped[str]=mapped_column(Text); body:Mapped[str]=mapped_column(Text); author:Mapped[str]=mapped_column(String(120)); source_url:Mapped[str]=mapped_column(String(600),default=''); rights_basis:Mapped[str]=mapped_column(String(40),default='original'); status:Mapped[str]=mapped_column(String(20),default='draft'); published_at:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)
class RightsRecord(Base):
 __tablename__='content_rights'; id:Mapped[int]=mapped_column(primary_key=True); content_type:Mapped[str]=mapped_column(String(40)); content_id:Mapped[int]=mapped_column(Integer); source_url:Mapped[str]=mapped_column(String(600)); rights_holder:Mapped[str]=mapped_column(String(180)); permitted_use:Mapped[str]=mapped_column(String(35)); evidence:Mapped[str]=mapped_column(Text,default=''); checked_on:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow); checked_by:Mapped[int]=mapped_column(ForeignKey('users.id')); __table_args__=(UniqueConstraint('content_type','content_id'),)
class PilotLead(Base):
 __tablename__='pilot_leads'; id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(180)); organization:Mapped[str]=mapped_column(String(160)); need:Mapped[str]=mapped_column(String(30)); message:Mapped[str]=mapped_column(Text,default=''); created:Mapped[dt.datetime]=mapped_column(DateTime,default=utcnow)

@asynccontextmanager
async def lifespan(app:FastAPI):
 if os.getenv('APP_ENV')=='production' and (not COOKIE_SECURE or os.getenv('SEED_DEMO')=='1'):
  raise RuntimeError('Production requires COOKIE_SECURE=1 and SEED_DEMO=0')
 if os.getenv('APP_ENV')=='production':
  if not DB_URL.startswith('postgresql'):raise RuntimeError('Production requires PostgreSQL')
  if not os.getenv('PUBLIC_BASE_URL','').startswith('https://'):raise RuntimeError('Production requires an HTTPS PUBLIC_BASE_URL')
  from alembic.config import Config
  from alembic.script import ScriptDirectory
  from alembic.runtime.migration import MigrationContext
  with engine.connect() as connection:
   current_heads=set(MigrationContext.configure(connection).get_current_heads())
   expected_heads=set(ScriptDirectory.from_config(Config(str(ROOT/'alembic.ini'))).get_heads())
   if current_heads!=expected_heads:raise RuntimeError('Run alembic upgrade head before production startup')
  with Local() as db:
   if db.scalar(select(Organization.id).where(Organization.demo==True).limit(1)):raise RuntimeError('Remove demo data before production deployment')
 else:Base.metadata.create_all(engine)
 seed()
 seed_editorial()
 from features.showcase import seed_showcase
 seed_showcase()
 from features.develop import seed_develop
 seed_develop()
 yield
app=FastAPI(title='SIVRCE — Editorial Talent & Learning Exchange',lifespan=lifespan,docs_url='/dev/docs' if os.getenv('ENABLE_DOCS')=='1' else None)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
templates=Jinja2Templates(directory=str(ROOT/'templates'))

EPISODES=[
 {'id':'hbr','publisher':'Harvard Business Review','title':'HBR IdeaCast','topic':'Leadership / Strategy','summary':'მართვის, ორგანიზაციული ცვლილებებისა და სამუშაო სამყაროს შესახებ სარედაქციო შერჩეული შოუ.','spotify':'https://open.spotify.com/show/4gtSBBxIAE142ApX6LqsvN','cover':'','kind':'Spotify'},
 {'id':'adam','publisher':'TED','title':'WorkLife with Molly Graham','topic':'Psychology / Work','summary':'შრომის, კარიერის, ლიდერობისა და პროფესიული ზრდის სიღრმისეული საუბრები, რომელსაც Molly Graham უძღვება.','spotify':'https://open.spotify.com/show/4eylg9GZJOVvUhTynt4jjA','cover':'','kind':'Spotify'},
 {'id':'a16z','publisher':'a16z','title':'The a16z Show','topic':'Technology / AI','summary':'ტექნოლოგიების, ახალი ბიზნესმოდელებისა და ინოვაციის გრძელფორმატიანი განხილვები.','spotify':'https://open.spotify.com/show/5bC65RDvs3oxnLyqqvkUYX','cover':'','kind':'Spotify'},
]

def jsonerr(status, message):raise HTTPException(status_code=status,detail=message)
def sessdb():
 with Local() as db: yield db

def signed_user(request:Request,db:Session):
 token=request.cookies.get('sivrce_session')
 if not token:return None,None
 auth=db.scalar(select(AuthSession).where(AuthSession.token_hash==hashlib.sha256(token.encode()).hexdigest(),AuthSession.expires>utcnow()))
 return (db.get(User,auth.user_id),auth) if auth else (None,None)
def current(request:Request,db:Session=Depends(sessdb)):
 user,auth=signed_user(request,db)
 if not user:jsonerr(401,'შესვლა აუცილებელია')
 return user

def security(request:Request,db:Session=Depends(sessdb)):
 user,auth=signed_user(request,db)
 if not user:jsonerr(401,'შესვლა აუცილებელია')
 if request.method not in ('GET','HEAD','OPTIONS'):
  origin=request.headers.get('origin',''); host=request.headers.get('host','')
  if origin and not origin.endswith('://'+host):jsonerr(403,'Origin არ ემთხვევა')
  if request.headers.get('X-SIVRCE-CSRF')!=auth.csrf:jsonerr(403,'CSRF ტოკენი არასწორია')
 return user

def member(db:Session,user:User,org_id:int,kind:str|None=None,permission:str|None=None):
 m=db.scalar(select(Membership).where(Membership.org_id==org_id,Membership.user_id==user.id))
 org=db.get(Organization,org_id)
 if not m or not org or (kind and org.kind!=kind):jsonerr(403,'ამ ორგანიზაციაზე წვდომა არ გაქვთ')
 if permission:
  from features.services import ROLE_PERMISSIONS
  if permission not in ROLE_PERMISSIONS.get(m.role,set()):jsonerr(403,'ამ მოქმედებისთვის საჭირო უფლება არ გაქვს')
 return org

def log(db,user,org,action,target):db.add(Audit(user_id=user.id,org_id=org,action=action,target=target))
def slug(text):
 s=re.sub(r'[^a-z0-9]+','-',text.lower()).strip('-')
 return (s or 'org')+'-'+secrets.token_hex(3)

def seed():
 # The operator's moderator account is created in every mode, including the closed beta.
 email=os.getenv('ADMIN_EMAIL','').strip().lower()
 password=os.getenv('ADMIN_PASSWORD','')
 if email and len(password)>=14:
  with Local() as db:
   if not db.scalar(select(User).where(User.email==email)):
    db.add(User(name='SIVRCE Admin',email=email,pw_hash=PW.hash(password),admin=True));db.commit()
 if os.getenv('SEED_DEMO','0')!='1':return
 # Internet-facing demos must override the published default password.
 demo_password=os.getenv('DEMO_PASSWORD') or 'DemoOnly!234'
 with Local() as db:
  if db.scalar(select(User.id).where(User.email.like('%@demo.sivrce.ge')).limit(1)):return
  users=[('დემო კომპანია','company@demo.sivrce.ge'),('დემო მომწოდებელი','provider@demo.sivrce.ge'),('დემო კანდიდატი','candidate@demo.sivrce.ge'),('SIVRCE მოდერატორი','admin@demo.sivrce.ge')]
  objs=[]
  for name,email in users:
   u=User(name=name,email=email,pw_hash=PW.hash(demo_password),admin=email.startswith('admin@'));db.add(u);objs.append(u)
  db.flush()
  company=Organization(name='Atelier Collective · DEMO',slug='atelier-demo',kind='company',description='საჩვენებელი კომპანია, შექმნილი პროდუქტის ფუნქციების გასატესტად.',location='თბილისი',verified=True,demo=True)
  provider=Organization(name='Practice Institute · DEMO',slug='practice-demo',kind='provider',description='საჩვენებელი სასწავლო ორგანიზაცია.',location='თბილისი',verified=True,demo=True)
  db.add_all([company,provider]);db.flush()
  db.add_all([Membership(org_id=company.id,user_id=objs[0].id),Membership(org_id=provider.id,user_id=objs[1].id)])
  jobs=[('People & Culture Partner','People & Culture','თბილისი','ჰიბრიდული',3200,4400,'გუნდის განვითარების და თანამშრომლების გამოცდილების დიზაინი.','მართე თანამშრომლის გამოცდილების ინიციატივები\nიმუშავე ხელმძღვანელ გუნდთან\nშეაფასე პროცესების ხარისხი','HR ბიზნესპარტნიორობის 3+ წელი\nპროცესების ანალიტიკა','ჯანმრთელობის დაზღვევა\nსწავლის ბიუჯეტი','საწყისი განაცხადი → გასაუბრება → პრაქტიკული ქეისი'),('Product Design Lead','Product','თბილისი','ჰიბრიდული',5000,7200,'ციფრული სერვისების პროდუქტული მიმართულების გაძღოლა.','წარმართე დიზაინის კვლევა\nდიზაინის სისტემის განვითარება','პროდუქტის დიზაინის 5+ წელი\nმაღალი ხარისხის პორტფოლიო','მოქნილი სამუშაო გარემო','CV განხილვა → პორტფოლიოს მიმოხილვა → ინტერვიუ'),('Data Analyst','Intelligence','თბილისი','დისტანციური',2800,4100,'მონაცემების გარდაქმნა ორგანიზაციულ გადაწყვეტილებებად.','შექმენი გადაწყვეტილებისთვის გასაგები ანგარიშები\nგანავითარე მონაცემების ხარისხი','SQL და BI გამოცდილება','პროფესიული განვითარება','განაცხადი → ტექნიკური საუბარი → ფინალური შეხვედრა')]
  for title,dep,loc,mode,low,high,purpose,resp,req,benefits,steps in jobs:
   db.add(Job(org_id=company.id,title=title,department=dep,location=loc,work_mode=mode,employment='სრული განაკვეთი',salary_min=low,salary_max=high,salary_basis='gross',purpose=purpose,responsibilities=resp,requirements=req,benefits=benefits,hiring_steps=steps,deadline='2026-12-31',status='published'))
  courses=[('Strategic Leadership Lab','ლიდერობა','ადგილზე','ცვლილებების მართვა რეალური სამუშაო ქეისებით.','გუნდზე გავლენის გაზრდა\nგადაწყვეტილების ჩარჩოების დანერგვა','ლიდერობის ჩარჩოები\nქეისებზე მუშაობა\nუკუკავშირი','დემო ტრენერი',490,'2 დღე','2026-11-20'),('AI at Work — Applied','ტექნოლოგიები','ჰიბრიდული','AI პროცესები სამუშაოზე და მონაცემების დაცვა.','უსაფრთხო AI სამუშაო პროცესების შექმნა','ინსტრუმენტები\nშეფასება\nპროცესების ავტომატიზაცია','დემო ტრენერი',390,'6 საათი','2026-12-04')]
  db.flush()
  for title,cat,fmt,description,outcomes,curriculum,trainer,price,duration,date in courses:
   c=Course(org_id=provider.id,title=title,category=cat,format=fmt,description=description,outcomes=outcomes,curriculum=curriculum,trainer=trainer,price=price,duration=duration,status='published');db.add(c);db.flush()
   db.add(Cohort(course_id=c.id,starts=date,capacity=18,location='თბილისი'))
  for ep in EPISODES:
   db.add(Episode(publisher=ep['publisher'],title=ep['title'],topic=ep['topic'],summary=ep['summary'],spotify=ep['spotify'],status='published'))
  db.add(Brief(org_id=company.id,title='მენეჯერული კომუნიკაცია — 25 მონაწილე',goal='გუნდების ხელმძღვანელებისთვის რთული საუბრებისა და უკუკავშირის მართვის პრაქტიკული ტრენინგი',audience=25,budget=4000,format='ადგილზე',deadline='2026-11-20',visibility='public',status='published'))
  db.commit()

class RegisterIn(BaseModel):
 name:str=Field(min_length=2,max_length=100);email:str;password:str=Field(min_length=10,max_length=128)
class LoginIn(BaseModel):email:str=Field(max_length=180);password:str=Field(max_length=128)
class OrgIn(BaseModel):name:str=Field(min_length=3,max_length=130);kind:str;description:str=Field(default='',max_length=1500);location:str=Field(default='თბილისი',max_length=150);website:str=Field(default='',max_length=220);registration_code:str=Field(default='',max_length=30)
class JobIn(BaseModel):
 org_id:int;title:str=Field(min_length=5,max_length=140);department:str=Field(min_length=2,max_length=100);location:str=Field(min_length=2,max_length=140);work_mode:str;employment:str;salary_min:int=Field(gt=0);salary_max:int=Field(gt=0);salary_basis:str;purpose:str=Field(min_length=35);responsibilities:str=Field(min_length=45);requirements:str=Field(min_length=35);benefits:str='';hiring_steps:str=Field(min_length=20);deadline:str;publish:bool=False
 @model_validator(mode='after')
 def quality(self):
  if self.salary_min>self.salary_max:raise ValueError('ანაზღაურების დიაპაზონი არასწორია')
  if self.salary_basis not in ('gross','net'):raise ValueError('მიუთითეთ gross ან net')
  if self.work_mode not in ('ადგილზე','დისტანციური','ჰიბრიდული'):raise ValueError('არასწორი სამუშაო ფორმატი')
  try:
   if dt.date.fromisoformat(self.deadline)<dt.date.today():raise ValueError('განაცხადის ვადა გასულია')
  except ValueError:raise ValueError('მიუთითეთ მომავალი ვადა YYYY-MM-DD ფორმატში')
  return self
class ApplicationIn(BaseModel):profile_url:str=Field(min_length=8,max_length=400);motivation:str=Field(min_length=30,max_length=2500)
class AppStatus(BaseModel):status:str
class CourseIn(BaseModel):org_id:int;title:str=Field(min_length=6);category:str=Field(min_length=2);format:str;description:str=Field(min_length=30);outcomes:str=Field(min_length=25);curriculum:str=Field(min_length=25);trainer:str=Field(min_length=3);price:int=Field(ge=0);duration:str=Field(min_length=2);publish:bool=False
class CohortIn(BaseModel):starts:str;capacity:int=Field(gt=0);location:str=Field(min_length=2)
class BriefIn(BaseModel):org_id:int;title:str=Field(min_length=5);goal:str=Field(min_length=35);audience:int=Field(gt=0);budget:int=Field(gt=0);format:str;deadline:str;visibility:str='public';publish:bool=False
class ProposalIn(BaseModel):org_id:int;price:int=Field(gt=0);approach:str=Field(min_length=50);trainer:str=Field(min_length=3);days:int=Field(gt=0)
class EpisodeIn(BaseModel):title:str=Field(min_length=8,max_length=180);publisher:str=Field(min_length=2,max_length=140);topic:str=Field(min_length=3,max_length=140);summary:str=Field(min_length=50,max_length=1500);spotify:str

@app.post('/api/auth/register')
def register(data:RegisterIn,response:Response,db:Session=Depends(sessdb)):
 email=data.email.strip().lower()
 if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):jsonerr(422,'არასწორი ელფოსტა')
 if db.scalar(select(User).where(User.email==email)):jsonerr(409,'ელფოსტა უკვე რეგისტრირებულია')
 user=User(name=data.name.strip(),email=email,pw_hash=PW.hash(data.password));db.add(user);db.flush()
 from features.services import issue_token
 issue_token(db,user,'verify');db.commit();db.refresh(user)
 return session_create(db,user,response)
@app.post('/api/auth/login')
def login(data:LoginIn,response:Response,db:Session=Depends(sessdb)):
 u=db.scalar(select(User).where(User.email==data.email.strip().lower()))
 try:
  if not u or not PW.verify(u.pw_hash,data.password):jsonerr(401,'ელფოსტა ან პაროლი არასწორია')
 except VerifyMismatchError:jsonerr(401,'ელფოსტა ან პაროლი არასწორია')
 return session_create(db,u,response)
def session_create(db,user,response):
 token=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(24)
 db.add(AuthSession(user_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),csrf=csrf,expires=utcnow()+dt.timedelta(days=7)));db.commit()
 response.set_cookie('sivrce_session',token,httponly=True,samesite='lax',secure=COOKIE_SECURE,max_age=7*86400,path='/')
 return {'name':user.name,'email':user.email,'csrf':csrf}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response,u:User=Depends(security),db:Session=Depends(sessdb)):
 token=request.cookies.get('sivrce_session');auth=db.scalar(select(AuthSession).where(AuthSession.token_hash==hashlib.sha256(token.encode()).hexdigest())) if token else None
 if auth:db.delete(auth);db.commit()
 response.delete_cookie('sivrce_session');return {'ok':True}
@app.get('/api/me')
def me(request:Request,db:Session=Depends(sessdb)):
 u,auth=signed_user(request,db)
 if not u:return {'user':None,'memberships':[]}
 rows=db.execute(select(Membership,Organization).join(Organization,Membership.org_id==Organization.id).where(Membership.user_id==u.id)).all()
 return {'user':{'id':u.id,'name':u.name,'email':u.email,'admin':u.admin},'csrf':auth.csrf,'memberships':[{'id':org.id,'name':org.name,'kind':org.kind,'verified':org.verified,'verification_requested':org.verification_requested,'role':m.role} for m,org in rows]}

@app.post('/api/organizations')
def create_org(d:OrgIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 if d.kind not in ('company','provider'):jsonerr(422,'აირჩიეთ კომპანია ან მომწოდებელი')
 if d.website and not d.website.startswith(('https://','http://')):jsonerr(422,'ვებსაიტი უნდა იწყებოდეს https:// ან http://')
 org=Organization(name=d.name,slug=slug(d.name),kind=d.kind,description=d.description,location=d.location,website=d.website,registration_code=d.registration_code);db.add(org);db.flush();db.add(Membership(org_id=org.id,user_id=u.id));log(db,u,org.id,'create_organization',str(org.id));db.commit();return {'id':org.id,'name':org.name,'verified':False}
@app.post('/api/organizations/{oid}/request-verification')
def request_verify(oid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 org=member(db,u,oid,permission='org_write')
 if len(org.description.strip())<50 or not org.website or not re.fullmatch(r'\d{9}',org.registration_code):jsonerr(422,'გადამოწმებისთვის საჭიროა ვებსაიტი, კომპანიის 9-ნიშნა საიდენტიფიკაციო კოდი და მინიმუმ 50-ნიშნა აღწერა')
 org.verification_requested=True;log(db,u,oid,'request_verification',str(oid));db.commit();return {'ok':True}
@app.get('/api/admin/pending')
def admin_pending(u:User=Depends(current),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 return [{'id':o.id,'name':o.name,'kind':o.kind,'website':o.website,'description':o.description,'registration_code':o.registration_code} for o in db.scalars(select(Organization).where(Organization.verification_requested==True,Organization.verified==False))]
@app.post('/api/admin/verify/{oid}')
def admin_verify(oid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 o=db.get(Organization,oid)
 if not o:jsonerr(404,'ორგანიზაცია ვერ მოიძებნა')
 o.verified=True;o.verification_requested=False;log(db,u,oid,'verify_organization',str(oid));db.commit();return {'ok':True}

# Public read paths deliberately hide drafts/unverified real organizations.
def job_dict(db,j):
 o=db.get(Organization,j.org_id)
 return {'id':j.id,'org_id':o.id,'company':o.name,'slug':o.slug,'demo':o.demo,'verified':o.verified,'title':j.title,'department':j.department,'location':j.location,'work_mode':j.work_mode,'employment':j.employment,'salary_min':j.salary_min,'salary_max':j.salary_max,'salary_basis':j.salary_basis,'currency':j.currency,'purpose':j.purpose,'responsibilities':j.responsibilities,'requirements':j.requirements,'benefits':j.benefits,'hiring_steps':j.hiring_steps,'deadline':j.deadline,'status':j.status}
@app.get('/api/jobs')
def jobs(q:str='',db:Session=Depends(sessdb)):
 rows=db.scalars(select(Job).join(Organization,Job.org_id==Organization.id).where(Job.status=='published',Job.deadline>=dt.date.today().isoformat(),Organization.verified==True).order_by(desc(Job.created))).all()
 return [job_dict(db,x) for x in rows if q.lower() in (x.title+' '+x.department+' '+x.location).lower()]
@app.get('/api/jobs/{jid}')
def job(jid:int,db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j or j.status!='published' or not db.get(Organization,j.org_id).verified:jsonerr(404,'ვაკანსია არ არსებობს')
 return job_dict(db,j)
@app.post('/api/jobs')
def new_job(d:JobIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 org=member(db,u,d.org_id,'company',permission='hire_write')
 if d.publish and not org.verified:jsonerr(403,'გამოქვეყნებამდე საჭიროა ორგანიზაციის გადამოწმება')
 j=Job(**d.model_dump(exclude={'publish'}),status='pending_review' if d.publish else 'draft');db.add(j);db.flush();log(db,u,org.id,'create_job',str(j.id));db.commit();return {'id':j.id,'status':j.status}
@app.post('/api/jobs/{jid}/apply')
def apply(jid:int,d:ApplicationIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j or j.status!='published' or not db.get(Organization,j.org_id).verified:jsonerr(404,'ვაკანსია არ არსებობს')
 if dt.date.fromisoformat(j.deadline)<dt.date.today():jsonerr(410,'განაცხადის ვადა გასულია')
 if db.scalar(select(Application.id).where(Application.job_id==jid,Application.user_id==u.id)):jsonerr(409,'ამ ვაკანსიაზე განაცხადი უკვე გაგზავნილია')
 if not d.profile_url.startswith(('https://','http://')):jsonerr(422,'მიუთითეთ საჯარო CV/პორტფოლიოს ბმული')
 a=Application(job_id=jid,user_id=u.id,profile_url=d.profile_url,motivation=d.motivation);db.add(a);db.flush();log(db,u,None,'apply_job',str(jid));db.commit();return {'id':a.id,'status':'received'}
# Private CVs are never served from the public /static mount.
PRIVATE_FILES=Path(os.getenv('PRIVATE_UPLOAD_DIR') or str(ROOT/'private_uploads'))
@app.post('/api/jobs/{jid}/apply-pdf')
async def apply_pdf(jid:int,motivation:str=Form(...),cv:UploadFile=File(...),u:User=Depends(security),db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j or j.status!='published' or not db.get(Organization,j.org_id).verified:jsonerr(404,'ვაკანსია არ არსებობს')
 if dt.date.fromisoformat(j.deadline)<dt.date.today():jsonerr(410,'განაცხადის ვადა გასულია')
 if db.scalar(select(Application.id).where(Application.job_id==jid,Application.user_id==u.id)):jsonerr(409,'განაცხადი უკვე გაგზავნილია')
 if len(motivation.strip())<30 or len(motivation)>2500:jsonerr(422,'მოტივაცია უნდა იყოს 30–2500 სიმბოლო')
 if cv.content_type!='application/pdf':jsonerr(422,'CV უნდა იყოს PDF ფორმატში')
 content=await cv.read(5*1024*1024+1)
 if len(content)>5*1024*1024 or not content.startswith(b'%PDF-'):jsonerr(422,'PDF ფაილი არასწორია ან აღემატება 5 MB-ს')
 from features.files import scan_pdf
 scan_pdf(content)
 PRIVATE_FILES.mkdir(parents=True,exist_ok=True)
 key=secrets.token_hex(24)+'.pdf'
 path=PRIVATE_FILES/key
 with open(path,'xb') as handle:handle.write(content)
 os.chmod(path,0o600)
 a=Application(job_id=jid,user_id=u.id,cv_key=key,motivation=motivation.strip())
 db.add(a);db.flush();log(db,u,None,'apply_pdf',str(jid));db.commit()
 return {'id':a.id,'status':'received'}
@app.get('/api/applications/{aid}/cv')
def download_cv(aid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 a=db.get(Application,aid)
 if not a or not a.cv_key:jsonerr(404,'CV არ არსებობს')
 if a.user_id!=u.id:
  job=db.get(Job,a.job_id)
  member(db,u,job.org_id,'company',permission='hire_read')
 path=PRIVATE_FILES/a.cv_key
 if not path.is_file():jsonerr(404,'CV ვერ მოიძებნა')
 log(db,u,db.get(Job,a.job_id).org_id,'download_cv',str(aid));db.commit()
 return FileResponse(path,media_type='application/pdf',filename='candidate_cv.pdf',content_disposition_type='attachment',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/admin/review-queue')
def review_queue(u:User=Depends(current),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 js=db.scalars(select(Job).where(Job.status=='pending_review')).all()
 cs=db.scalars(select(Course).where(Course.status=='pending_review')).all()
 return {'jobs':[{'id':j.id,'title':j.title,'company':db.get(Organization,j.org_id).name,'salary':f'{j.salary_min}–{j.salary_max}','purpose':j.purpose,'responsibilities':j.responsibilities,'requirements':j.requirements} for j in js],
         'courses':[{'id':c.id,'title':c.title,'provider':db.get(Organization,c.org_id).name,'curriculum':c.curriculum,'outcomes':c.outcomes} for c in cs]}
@app.post('/api/admin/review/{kind}/{item_id}/{decision}')
def review_item(kind:str,item_id:int,decision:str,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 if kind not in ('job','course') or decision not in ('approve','reject'):jsonerr(422,'არასწორი მოქმედება')
 item=db.get(Job if kind=='job' else Course,item_id)
 if not item or item.status!='pending_review':jsonerr(404,'სარევიზიო ჩანაწერი ვერ მოიძებნა')
 if decision=='approve' and not db.get(Organization,item.org_id).verified:jsonerr(409,'ორგანიზაციის გადამოწმება აუცილებელია')
 item.status='published' if decision=='approve' else 'rejected'
 log(db,u,item.org_id,decision+'_'+kind,str(item_id));db.commit();return {'ok':True,'status':item.status}

@app.get('/api/my-applications')
def my_applications(u:User=Depends(current),db:Session=Depends(sessdb)):
 rows=db.scalars(select(Application).where(Application.user_id==u.id).order_by(desc(Application.created))).all()
 return [{'id':a.id,'title':db.get(Job,a.job_id).title,'cv_url':f'/api/applications/{a.id}/cv' if a.cv_key else None,'status':a.status,'created':a.created.isoformat()} for a in rows]
@app.get('/api/organizations/{oid}/applications')
def org_apps(oid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 member(db,u,oid,'company',permission='hire_read')
 rows=db.execute(select(Application,Job,User).join(Job,Application.job_id==Job.id).join(User,Application.user_id==User.id).where(Job.org_id==oid).order_by(desc(Application.created))).all()
 return [{'id':a.id,'candidate':usr.name,'email':usr.email,'cv_url':f'/api/applications/{a.id}/cv' if a.cv_key else None,'profile_url':a.profile_url,'motivation':a.motivation,'job':j.title,'status':a.status} for a,j,usr in rows]
@app.patch('/api/applications/{aid}')
def update_app(aid:int,d:AppStatus,u:User=Depends(security),db:Session=Depends(sessdb)):
 a=db.scalar(select(Application).where(Application.id==aid).with_for_update())
 if not a:jsonerr(404,'განაცხადი არ არსებობს')
 j=db.get(Job,a.job_id);member(db,u,j.org_id,'company',permission='hire_write')
 if d.status not in ('reviewing','interview','rejected','offer','hired'):jsonerr(422,'არასწორი სტატუსი')
 if a.status in ('hired','rejected','withdrawn'):jsonerr(409,'დასრულებული განაცხადის შეცვლა შეუძლებელია')
 if a.status==d.status:return {'ok':True}
 from features.models import ApplicationEvent
 from features.services import notify
 db.add(ApplicationEvent(application_id=aid,actor_id=u.id,previous=a.status,status=d.status))
 a.status=d.status
 labels={'reviewing':'განხილვა','interview':'გასაუბრება','rejected':'უარი','offer':'შეთავაზება','hired':'დაქირავებული'}
 notify(db,db.get(User,a.user_id),'განაცხადის ეტაპი განახლდა',j.title+' — '+labels[d.status])
 log(db,u,j.org_id,'update_application',str(aid));db.commit();return {'ok':True}

@app.get('/api/courses')
def courses(db:Session=Depends(sessdb)):
 rows=db.execute(select(Course,Organization).join(Organization,Course.org_id==Organization.id).where(Course.status=='published',Organization.verified==True).order_by(desc(Course.created))).all()
 return [{'id':c.id,'title':c.title,'category':c.category,'format':c.format,'description':c.description,'outcomes':c.outcomes,'curriculum':c.curriculum,'trainer':c.trainer,'price':c.price,'duration':c.duration,'provider':o.name,'demo':o.demo,'cohorts':[{'starts':co.starts,'capacity':co.capacity,'location':co.location} for co in db.scalars(select(Cohort).where(Cohort.course_id==c.id,Cohort.active==True)).all()]} for c,o in rows]
@app.post('/api/courses')
def create_course(d:CourseIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 org=member(db,u,d.org_id,'provider',permission='catalog_write')
 if d.publish and not org.verified:jsonerr(403,'მომწოდებლის გადამოწმება აუცილებელია')
 c=Course(**d.model_dump(exclude={'publish'}),status='pending_review' if d.publish else 'draft');db.add(c);db.flush();log(db,u,org.id,'create_course',str(c.id));db.commit();return {'id':c.id,'status':c.status}
@app.post('/api/courses/{cid}/cohorts')
def add_cohort(cid:int,d:CohortIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 c=db.get(Course,cid)
 if not c:jsonerr(404,'კურსი არ არსებობს')
 member(db,u,c.org_id,'provider',permission='catalog_write')
 try:starts=dt.date.fromisoformat(d.starts)
 except ValueError:jsonerr(422,'თარიღის ფორმატი არასწორია')
 if starts<dt.date.today():jsonerr(422,'თარიღი გასულია')
 co=Cohort(course_id=cid,**d.model_dump());db.add(co);log(db,u,c.org_id,'create_cohort',str(cid));db.commit();return {'ok':True}

@app.get('/api/briefs')
def briefs(db:Session=Depends(sessdb)):
 rows=db.execute(select(Brief,Organization).join(Organization,Brief.org_id==Organization.id).where(Brief.status=='published',Brief.visibility=='public',Organization.verified==True).order_by(desc(Brief.created))).all()
 return [{'id':b.id,'title':b.title,'goal':b.goal,'audience':b.audience,'budget':b.budget,'format':b.format,'deadline':b.deadline,'company':o.name,'demo':o.demo} for b,o in rows]
@app.post('/api/briefs')
def create_brief(d:BriefIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 org=member(db,u,d.org_id,'company',permission='develop_write')
 if d.publish and not org.verified:jsonerr(403,'ორგანიზაციის გადამოწმება აუცილებელია')
 if d.visibility not in ('public','private'):jsonerr(422,'არასწორი ხილვადობა')
 try:deadline=dt.date.fromisoformat(d.deadline)
 except ValueError:jsonerr(422,'თარიღის ფორმატი არასწორია')
 if deadline<dt.date.today():jsonerr(422,'ვადა გასულია')
 b=Brief(**d.model_dump(exclude={'publish'}),status='published' if d.publish else 'draft');db.add(b);db.flush();log(db,u,org.id,'create_brief',str(b.id));db.commit();return {'id':b.id,'status':b.status}
@app.post('/api/briefs/{bid}/proposals')
def proposal(bid:int,d:ProposalIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 org=member(db,u,d.org_id,'provider',permission='develop_write')
 b=db.get(Brief,bid)
 from features.routes import provider_can_read
 if not provider_can_read(db,org.id,b):jsonerr(404,'მოთხოვნა არ არსებობს')
 if b.deadline<dt.date.today().isoformat():jsonerr(410,'მოთხოვნის ვადა გასულია')
 if not org.verified:jsonerr(403,'მომწოდებლის გადამოწმება აუცილებელია')
 if db.scalar(select(Proposal.id).where(Proposal.brief_id==bid,Proposal.org_id==org.id)):jsonerr(409,'შეთავაზება უკვე გაგზავნილია')
 p=Proposal(brief_id=bid,**d.model_dump());db.add(p);db.flush();log(db,u,org.id,'submit_proposal',str(p.id));db.commit();return {'id':p.id,'status':'submitted'}
@app.get('/api/organizations/{oid}/proposals')
def my_proposals(oid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 org=member(db,u,oid,permission='develop_read')
 if org.kind=='company':
  rows=db.execute(select(Proposal,Brief,Organization).join(Brief,Proposal.brief_id==Brief.id).join(Organization,Proposal.org_id==Organization.id).where(Brief.org_id==oid)).all()
  return [{'id':p.id,'brief_id':b.id,'title':b.title,'provider':o.name,'price':p.price,'approach':p.approach,'trainer':p.trainer,'days':p.days,'version':proposal_version(db,p.id),'status':p.status} for p,b,o in rows]
 rows=db.execute(select(Proposal,Brief,Organization).join(Brief,Proposal.brief_id==Brief.id).join(Organization,Brief.org_id==Organization.id).where(Proposal.org_id==oid)).all()
 return [{'id':p.id,'brief_id':b.id,'version':proposal_version(db,p.id),'trainer':p.trainer,'days':p.days,'title':b.title,'company':o.name,'price':p.price,'approach':p.approach,'status':p.status} for p,b,o in rows]
@app.post('/api/proposals/{pid}/select')
def select_prop(pid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 p=db.get(Proposal,pid)
 if not p:jsonerr(404,'შეთავაზება არ არსებობს')
 b=db.scalar(select(Brief).where(Brief.id==p.brief_id).with_for_update());member(db,u,b.org_id,'company',permission='develop_write')
 if b.status=='awarded' and p.status=='selected':return {'ok':True}
 if b.status!='published' or p.status!='submitted':jsonerr(409,'ამ მოთხოვნაზე გადაწყვეტილება უკვე მიღებულია')
 b.status='awarded';p.status='selected'
 from features.services import notify
 for other in db.scalars(select(Proposal).where(Proposal.brief_id==b.id)):
  if other.id!=p.id:other.status='not_selected'
  for membership in db.scalars(select(Membership).where(Membership.org_id==other.org_id)):
   notify(db,db.get(User,membership.user_id),'ტრენინგის მოთხოვნაზე გადაწყვეტილება',b.title+' — '+('შერჩეულია' if other.id==p.id else 'სხვა შეთავაზება შეირჩა'),'/workspace')
 log(db,u,b.org_id,'select_proposal',str(pid));db.commit();return {'ok':True}
def episode_dict(ep):return {'id':ep.id,'publisher':ep.publisher,'title':ep.title,'topic':ep.topic,'summary':ep.summary,'spotify':ep.spotify,'kind':'Spotify'}
@app.get('/api/voices')
def voices(db:Session=Depends(sessdb)):
 return [episode_dict(e) for e in db.scalars(select(Episode).where(Episode.status=='published').order_by(Episode.id))]
@app.get('/api/admin/voices')
def all_voices(u:User=Depends(current),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 return [{'id':e.id,'title':e.title,'publisher':e.publisher,'status':e.status,'spotify':e.spotify} for e in db.scalars(select(Episode).order_by(Episode.id))]
@app.post('/api/admin/voices')
def new_voice(d:EpisodeIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 if not re.fullmatch(r'https://open\.spotify\.com/show/[A-Za-z0-9]+',d.spotify):jsonerr(422,'მხოლოდ Spotify-ის ოფიციალური show ბმულია დასაშვები')
 if db.scalar(select(Episode).where(Episode.spotify==d.spotify)):jsonerr(409,'ეს წყარო უკვე არსებობს')
 ep=Episode(**d.model_dump(),status='published');db.add(ep);db.flush();log(db,u,None,'curate_voice',str(ep.id));db.commit();return {'id':ep.id}
@app.post('/api/admin/voices/{eid}/archive')
def archive_voice(eid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მხოლოდ მოდერატორი')
 ep=db.get(Episode,eid)
 if not ep:jsonerr(404,'ჩანაწერი არ არსებობს')
 ep.status='archived';log(db,u,None,'archive_voice',str(eid));db.commit();return {'ok':True}

@app.get('/api/studio/{oid}')
def studio_data(oid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 org=member(db,u,oid)
 from features.services import ROLE_PERMISSIONS
 role=db.scalar(select(Membership.role).where(Membership.org_id==oid,Membership.user_id==u.id))
 permissions=ROLE_PERMISSIONS.get(role,set())
 jobs=[{'id':j.id,'title':j.title,'status':j.status,'salary':f'{j.salary_min}–{j.salary_max} ₾'} for j in db.scalars(select(Job).where(Job.org_id==oid)).all()] if org.kind=='company' and 'hire_read' in permissions else []
 courses=[{'id':c.id,'title':c.title,'status':c.status} for c in db.scalars(select(Course).where(Course.org_id==oid)).all()] if org.kind=='provider' and 'catalog_read' in permissions else []
 bs=[{'id':b.id,'title':b.title,'status':b.status} for b in db.scalars(select(Brief).where(Brief.org_id==oid)).all()] if org.kind=='company' and 'develop_read' in permissions else []
 return {'org':{'id':org.id,'name':org.name,'kind':org.kind,'verified':org.verified,'verification_requested':org.verification_requested},'jobs':jobs,'courses':courses,'briefs':bs}

# Server-rendered routes provide indexability and usable experiences without JS.
@app.get('/',response_class=HTMLResponse)
def home(request:Request,db:Session=Depends(sessdb)):
 j=db.scalar(select(Job).join(Organization,Job.org_id==Organization.id).where(Job.status=='published',Job.deadline>=dt.date.today().isoformat(),Organization.verified==True)); c=db.scalar(select(Course).join(Organization,Course.org_id==Organization.id).where(Course.status=='published',Organization.verified==True))
 return templates.TemplateResponse(request,'index.html',{'page':'home','job':job_dict(db,j) if j else None,'course':c})
@app.get('/careers',response_class=HTMLResponse)
def careers(request:Request,db:Session=Depends(sessdb)):
 jobs=[job_dict(db,j) for j in db.scalars(select(Job).where(Job.status=='published').order_by(desc(Job.created))).all() if db.get(Organization,j.org_id).verified and j.deadline>=dt.date.today().isoformat()]
 from features.showcase import accent_map
 return templates.TemplateResponse(request,'index.html',{'page':'careers','jobs':jobs,'accents':accent_map(db,[j['org_id'] for j in jobs])})
@app.get('/careers/{jid}',response_class=HTMLResponse)
def careers_detail(jid:int,request:Request,db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j or j.status!='published' or not db.get(Organization,j.org_id).verified:jsonerr(404,'ვაკანსია არ არსებობს')
 from features.showcase import job_context
 data=job_dict(db,j)
 return templates.TemplateResponse(request,'index.html',{'page':'job','job':data,'job_schema':job_schema(db,j,request),**job_context(db,data)})
@app.get('/organizations/{slug}',response_class=HTMLResponse)
def organization_profile(slug:str,request:Request,db:Session=Depends(sessdb)):
 from features.showcase import organization_context
 org=db.scalar(select(Organization).where(Organization.slug==slug,Organization.verified==True))
 if not org:jsonerr(404,'ორგანიზაცია ვერ მოიძებნა')
 return templates.TemplateResponse(request,'index.html',organization_context(db,org))

@app.get('/learn',response_class=HTMLResponse)
def learn(request:Request,db:Session=Depends(sessdb)):
 rows=db.execute(select(Course,Organization).join(Organization,Course.org_id==Organization.id).where(Course.status=='published',Organization.verified==True)).all()
 listings=[{'course':c,'org':o,'cohorts':db.scalars(select(Cohort).where(Cohort.course_id==c.id)).all()} for c,o in rows]
 return templates.TemplateResponse(request,'index.html',{'page':'learn','courses':listings})
@app.get('/learn/{cid}',response_class=HTMLResponse)
def learn_detail(cid:int,request:Request,db:Session=Depends(sessdb)):
 c=db.get(Course,cid)
 if not c or c.status!='published' or not db.get(Organization,c.org_id).verified:jsonerr(404,'კურსი არ არსებობს')
 from features.showcase import course_context
 provider=db.get(Organization,c.org_id)
 return templates.TemplateResponse(request,'index.html',{'page':'course','course':c,'provider':provider,'cohorts':db.scalars(select(Cohort).where(Cohort.course_id==cid)).all(),**course_context(db,c,provider)})
@app.get('/exchange',response_class=HTMLResponse)
def exchange(request:Request,db:Session=Depends(sessdb)):
 rows=db.execute(select(Brief,Organization).join(Organization,Brief.org_id==Organization.id).where(Brief.status=='published',Brief.visibility=='public',Organization.verified==True)).all()
 return templates.TemplateResponse(request,'index.html',{'page':'exchange','briefs':[{'brief':b,'org':o} for b,o in rows]})
@app.get('/voices',response_class=HTMLResponse)
def voices_page(request:Request,db:Session=Depends(sessdb)):
 from features.showcase import episode_covers
 episodes=[episode_dict(ep) for ep in db.scalars(select(Episode).where(Episode.status=='published').order_by(Episode.id))]
 return templates.TemplateResponse(request,'index.html',{'page':'voices','episodes':episodes,'covers':episode_covers(db)})
@app.get('/studio',response_class=HTMLResponse)
def studio_page(request:Request):return templates.TemplateResponse(request,'index.html',{'page':'studio'})
@app.get('/standards',response_class=HTMLResponse)
def standards_page(request:Request):return templates.TemplateResponse(request,'index.html',{'page':'standards'})
@app.get('/health')
def health():return {'status':'ok'}


# ---------- 2026 product upgrade: identity, verified opportunity workflows and original Georgian editorial ----------
GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID','').strip()
class GoogleCredentialIn(BaseModel):
 credential:str=Field(min_length=50,max_length=10000)
def verify_google_credential(token:str):
 if not GOOGLE_CLIENT_ID:jsonerr(503,'Google შესვლა არ არის ჩართული: საჭიროა GOOGLE_CLIENT_ID')
 try:
  from google.oauth2 import id_token
  from google.auth.transport import requests as google_requests
  info=id_token.verify_oauth2_token(token,google_requests.Request(),GOOGLE_CLIENT_ID)
  if info.get('iss') not in ('accounts.google.com','https://accounts.google.com') or not info.get('email_verified') or not info.get('sub'):
   jsonerr(401,'Google ანგარიშის იდენტობა არ არის დადასტურებული')
  return info
 except HTTPException:raise
 except Exception:jsonerr(401,'Google ავტორიზაცია ვერ გადამოწმდა')
def check_google_origin(request:Request):
 origin=request.headers.get('origin','')
 if not origin or origin.rstrip('/')!=(os.getenv('PUBLIC_BASE_URL') or str(request.base_url)).rstrip('/'):
  jsonerr(403,'არასწორი შესვლის წყარო')
@app.get('/api/auth/google/config')
def google_config():return {'enabled':bool(GOOGLE_CLIENT_ID),'client_id':GOOGLE_CLIENT_ID}
@app.post('/api/auth/google')
def google_login(d:GoogleCredentialIn,request:Request,response:Response,db:Session=Depends(sessdb)):
 check_google_origin(request);info=verify_google_credential(d.credential);sub=str(info['sub'])
 identity=db.scalar(select(GoogleIdentity).where(GoogleIdentity.google_sub==sub))
 if identity:user=db.get(User,identity.user_id)
 else:
  email=str(info['email']).strip().lower()
  if db.scalar(select(User).where(User.email==email)):
   jsonerr(409,'ეს ელფოსტა უკვე გამოიყენება. შედი არსებული ანგარიშით და My Studio-დან დააკავშირე Google.')
  user=User(name=(info.get('name') or email.split('@')[0])[:100],email=email,pw_hash=PW.hash(secrets.token_urlsafe(40)))
  db.add(user);db.flush();db.add(GoogleIdentity(user_id=user.id,google_sub=sub));db.commit()
 return session_create(db,user,response)
@app.post('/api/auth/google/link')
def google_link(d:GoogleCredentialIn,request:Request,u:User=Depends(security),db:Session=Depends(sessdb)):
 check_google_origin(request);info=verify_google_credential(d.credential)
 if db.scalar(select(GoogleIdentity).where(GoogleIdentity.google_sub==info['sub'])):jsonerr(409,'Google ანგარიში უკვე დაკავშირებულია')
 if db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id==u.id)):jsonerr(409,'მომხმარებელს Google ანგარიში უკვე დაკავშირებული აქვს')
 if str(info['email']).strip().lower()!=u.email:jsonerr(403,'დაკავშირებისთვის Google და SIVRCE ელფოსტები უნდა ემთხვეოდეს')
 db.add(GoogleIdentity(user_id=u.id,google_sub=str(info['sub'])));log(db,u,None,'google_link','identity');db.commit();return {'ok':True}

@app.post('/api/jobs/{jid}/save')
def save_job(jid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j or j.status!='published':jsonerr(404,'ვაკანსია მიუწვდომელია')
 if not db.scalar(select(SavedJob).where(SavedJob.job_id==jid,SavedJob.user_id==u.id)):
  db.add(SavedJob(job_id=jid,user_id=u.id));db.commit()
 return {'saved':True}
@app.delete('/api/jobs/{jid}/save')
def unsave_job(jid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 sj=db.scalar(select(SavedJob).where(SavedJob.job_id==jid,SavedJob.user_id==u.id))
 if sj:db.delete(sj);db.commit()
 return {'saved':False}
@app.get('/api/my-saved-jobs')
def saved_jobs(u:User=Depends(current),db:Session=Depends(sessdb)):
 rows=db.scalars(select(SavedJob).where(SavedJob.user_id==u.id).order_by(desc(SavedJob.created))).all()
 return [job_dict(db,j) for r in rows if (j:=db.get(Job,r.job_id)) and j.status=='published']
@app.delete('/api/my-applications/{aid}')
def withdraw_application(aid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 a=db.get(Application,aid)
 if not a:jsonerr(404,'განაცხადი ვერ მოიძებნა')
 if a.user_id!=u.id:jsonerr(403,'ეს თქვენი განაცხადი არ არის')
 cv=a.cv_key
 # Candidate controls their submitted application. Files are deleted only after DB commit.
 for meeting in db.scalars(select(Interview).where(Interview.application_id==aid)).all():db.delete(meeting)
 db.delete(a);log(db,u,None,'withdraw_application',str(aid));db.commit()
 if cv and re.fullmatch(r'[0-9a-f]{48}\.pdf',cv):
  try:(PRIVATE_FILES/cv).unlink(missing_ok=True)
  except OSError:pass
 return {'withdrawn':True}

class InterviewIn(BaseModel):
 scheduled_for:dt.datetime;format:str;location_or_link:str=Field(min_length=5,max_length=320);candidate_note:str=Field(default='',max_length=1200)
 @model_validator(mode='after')
 def validate(self):
  if self.format not in ('online','onsite','phone'):raise ValueError('არასწორი შეხვედრის ფორმატი')
  if self.scheduled_for.tzinfo:raise ValueError('მიუთითეთ თბილისის ადგილობრივი დრო UTC offset-ის გარეშე')
  if self.scheduled_for<dt.datetime.now(dt.timezone(dt.timedelta(hours=4))).replace(tzinfo=None)+dt.timedelta(minutes=10):raise ValueError('შეხვედრის თარიღი მომავალში უნდა იყოს')
  return self
@app.post('/api/applications/{aid}/interviews')
def schedule_interview(aid:int,d:InterviewIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 a=db.get(Application,aid)
 if not a:jsonerr(404,'განაცხადი ვერ მოიძებნა')
 j=db.get(Job,a.job_id);member(db,u,j.org_id,'company',permission='hire_write')
 if a.status in ('rejected','hired','withdrawn'):jsonerr(409,'დასრულებული განაცხადი')
 from sqlalchemy import or_
 for lock_user in sorted({u.id,a.user_id}):db.execute(select(User.id).where(User.id==lock_user).with_for_update())
 conflict=db.scalar(select(Interview.id).join(Application,Interview.application_id==Application.id).where(or_(Interview.created_by==u.id,Application.user_id==a.user_id),Interview.scheduled_for>d.scheduled_for-dt.timedelta(hours=1),Interview.scheduled_for<d.scheduled_for+dt.timedelta(hours=1)))
 if conflict:jsonerr(409,'ამ დროს უკვე ჩანიშნულია გასაუბრება; გამოყავი ერთი საათი')
 from features.models import ApplicationEvent
 from features.services import notify
 meeting=Interview(application_id=aid,created_by=u.id,**d.model_dump());db.add(meeting)
 if a.status!='interview':db.add(ApplicationEvent(application_id=aid,actor_id=u.id,previous=a.status,status='interview'))
 a.status='interview';db.flush()
 notify(db,db.get(User,a.user_id),'გასაუბრება ჩაინიშნა',j.title+' — '+d.scheduled_for.isoformat()+' (თბილისის დრო)')
 log(db,u,j.org_id,'schedule_interview',str(meeting.id));db.commit()
 return {'id':meeting.id,'status':a.status,'scheduled_for':d.scheduled_for.isoformat()}
@app.get('/api/my-interviews')
def my_interviews(u:User=Depends(current),db:Session=Depends(sessdb)):
 rows=db.execute(select(Interview,Application,Job,Organization).join(Application,Interview.application_id==Application.id).join(Job,Application.job_id==Job.id).join(Organization,Job.org_id==Organization.id).where(Application.user_id==u.id).order_by(desc(Interview.scheduled_for))).all()
 return [{'id':meet.id,'job':j.title,'company':o.name,'scheduled_for':meet.scheduled_for.isoformat(),'format':meet.format,'location_or_link':meet.location_or_link,'note':meet.candidate_note} for meet,a,j,o in rows]
@app.get('/api/organizations/{oid}/interviews')
def org_interviews(oid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 member(db,u,oid,'company',permission='hire_read')
 rows=db.execute(select(Interview,Application,Job,User).join(Application,Interview.application_id==Application.id).join(Job,Application.job_id==Job.id).join(User,Application.user_id==User.id).where(Job.org_id==oid).order_by(desc(Interview.scheduled_for))).all()
 return [{'id':meeting.id,'application_id':a.id,'candidate':person.name,'job':j.title,'scheduled_for':meeting.scheduled_for.isoformat(),'format':meeting.format,'location_or_link':meeting.location_or_link} for meeting,a,j,person in rows]

class InterestIn(BaseModel):note:str=Field(default='',max_length=1000)
@app.post('/api/cohorts/{coid}/interest')
def cohort_interest(coid:int,d:InterestIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 co=db.scalar(select(Cohort).where(Cohort.id==coid).with_for_update())
 if not co or not co.active:jsonerr(404,'ჯგუფი მიუწვდომელია')
 c=db.get(Course,co.course_id)
 if not c or c.status!='published' or not db.get(Organization,c.org_id).verified:jsonerr(404,'კურსი მიუწვდომელია')
 if co.starts<dt.date.today().isoformat():jsonerr(410,'ჯგუფის დაწყების თარიღი გასულია')
 if db.scalar(select(CourseInterest).where(CourseInterest.cohort_id==coid,CourseInterest.user_id==u.id)):jsonerr(409,'მოთხოვნა უკვე გაგზავნილია')
 total=db.scalar(select(func.count(CourseInterest.id)).where(CourseInterest.cohort_id==coid,CourseInterest.status.in_(('requested','confirmed'))))
 if total>=co.capacity:jsonerr(409,'ჯგუფის ადგილები შევსებულია')
 record=CourseInterest(cohort_id=coid,user_id=u.id,note=d.note);db.add(record);db.flush();log(db,u,c.org_id,'course_interest',str(record.id));db.commit();return {'id':record.id,'status':'requested','payment_collected':False}
@app.get('/api/my-course-interests')
def my_course_interests(u:User=Depends(current),db:Session=Depends(sessdb)):
 rows=db.execute(select(CourseInterest,Course,Cohort).join(Cohort,CourseInterest.cohort_id==Cohort.id).join(Course,Cohort.course_id==Course.id).where(CourseInterest.user_id==u.id)).all()
 return [{'id':r.id,'title':c.title,'starts':co.starts,'status':r.status} for r,c,co in rows]
@app.get('/api/organizations/{oid}/course-interests')
def course_interests(oid:int,u:User=Depends(current),db:Session=Depends(sessdb)):
 member(db,u,oid,'provider',permission='catalog_read')
 rows=db.execute(select(CourseInterest,Course,Cohort,User).join(Cohort,CourseInterest.cohort_id==Cohort.id).join(Course,Cohort.course_id==Course.id).join(User,CourseInterest.user_id==User.id).where(Course.org_id==oid)).all()
 return [{'id':r.id,'title':c.title,'starts':co.starts,'name':person.name,'email':person.email,'note':r.note,'status':r.status} for r,c,co,person in rows]

ORIGINAL_ARTICLES=[
 {'slug':'job-transparency-is-a-product','section':'CAREERS / STANDARD','title':'რატომ არის ხელფასის დიაპაზონი ვაკანსიის ნაწილი და არა საიდუმლო?','deck':'კანდიდატი დროის დახარჯვის სანაცვლოდ ინფორმაციას ელოდება. გამჭვირვალე ვაკანსია უკეთესი კომუნიკაციით იწყება.','body':'''კარგი ვაკანსია არ არის მხოლოდ მოთხოვნების ჩამონათვალი. ის არის შეთავაზება ორ მხარეს შორის — კომპანიასა და ადამიანთან, რომელიც გადაწყვეტილებას იღებს საკუთარი დროისა და კარიერის შესახებ.

თუ განცხადებაში კომპანია არ ჩანს, ანაზღაურება დამალულია და შერჩევის პროცესი გაურკვეველია, კანდიდატს ინფორმაციის ნაკლებობის შევსება გამოცნობით უწევს. ეს ზრდის არასწორი მოლოდინისა და დროის დაკარგვის რისკს.

SIVRCE-ის სტანდარტით, ვაკანსია არ გამოქვეყნდება კომპანიის იდენტობის, ანაზღაურების დიაპაზონის, სამუშაო ფორმატის, პასუხისმგებლობებისა და შერჩევის ეტაპების გარეშე. უნდა ჩანდეს, თანხა დარიცხულია თუ ხელზე ასაღები.

გამჭვირვალობა არ ნიშნავს, რომ ყველა ორგანიზაცია ერთნაირად გადაიხდის. ის ნიშნავს, რომ კანდიდატს აქვს საკმარისი ინფორმაცია გადაწყვეტილების მისაღებად. ეს არის ნდობის დასაწყისი — და არა მხოლოდ დიზაინის დეტალი.''','author':'SIVRCE Editorial'},
 {'slug':'hire-or-develop','section':'WORKFORCE / THINKING','title':'დაიქირაო თუ გადაამზადო? სწორი შეკითხვა შედეგიდან იწყება.','deck':'საკადრო პრობლემა ყოველთვის ვაკანსიას არ ნიშნავს; ზოგჯერ გუნდის უნარებისა და პროცესის გაუმჯობესება საკმარისია.','body':'''როდესაც ბიზნესს კონკრეტული კომპეტენცია აკლია, პირველი რეაქცია ხშირად ახალი ვაკანსიის გამოქვეყნებაა. მაგრამ მანამდე უნდა განისაზღვროს მიზანი: რა შედეგი გვჭირდება, რომელი სამუშაო ვერ სრულდება და რამდენად სწრაფად უნდა შეიცვალოს მდგომარეობა?

ახალი თანამშრომლის დაქირავება და არსებული გუნდის განვითარება განსხვავებული ინვესტიციებია. ორივე მოითხოვს დროს, ბიუჯეტს და მოლოდინების სწორად ჩამოყალიბებას.

სანამ გადაწყვეტილებას მივიღებთ, სასარგებლოა სამი შეკითხვა: (1) პრობლემა ცოდნის ნაკლებობაა თუ რესურსის? (2) აქვს თუ არა არსებულ გუნდს დრო და მოტივაცია ახალი კომპეტენციის გასავითარებლად? (3) როგორ გავზომავთ შედეგს 60 ან 90 დღეში?

SIVRCE-ის მიზანია ორივე გზის ერთად წარმოდგენა: ხარისხიანი ვაკანსიის შექმნა ან შესაბამისი სასწავლო პროგრამის მოძიება — ისე, რომ საბოლოო არჩევანი ადამიანმა და კომპანიამ მიიღონ.''','author':'SIVRCE Editorial'},
 {'slug':'voices-in-georgian','section':'VOICES / LANGUAGE','title':'მნიშვნელოვანი იდეები ქართულად — ავტორის უფლებების დაცვით.','deck':'ინგლისურენოვანი საუბარი შეიძლება გახდეს ქართული პროფესიული დისკუსიის ნაწილი, მაგრამ თარგმანი და დუბლირება სამართლებრივ საფუძველს მოითხოვს.','body':'''პროფესიული ცოდნის დიდი ნაწილი ინგლისურად ქვეყნდება, თუმცა ადამიანის მუშაობისთვის მთავარი ინფორმაცია მშობლიურ ენაზე ხელმისაწვდომი უნდა იყოს. ხელმისაწვდომობა მხოლოდ ტექსტის ავტომატურ გადათარგმნას არ ნიშნავს.

SIVRCE Voices-ში ჩვენი მიდგომა იწყება ოფიციალური წყაროთი. ორიგინალურ პოდკასტს მხოლოდ ნებადართული ჩაშენებული პლეიერით ვაჩვენებთ და ავტორს ვუთითებთ. მის ირგვლივ ვქმნით დამოუკიდებელ ქართულ სარედაქციო ანალიზს — რატომ არის საუბარი მნიშვნელოვანი, რომელი იდეები ღირს განხილვად და რას შეიძლება უკავშირდებოდეს ქართული სამუშაო გარემოსთვის.

სრული ტრანსკრიპტი, თარგმანი და ხმით დუბლირება სხვა საფეხურია: ამას შესაბამისი უფლებების მოპოვება, ხმაზე თანხმობა და ადამიანური ხარისხის კონტროლი სჭირდება.

AI გვეხმარება ენობრივი ბარიერის შემცირებაში, მაგრამ არ ცვლის ავტორის უფლებას და არ უნდა შექმნას მცდარი შთაბეჭდილება, თითქოს უცხოელი სტუმარი პირადად თანამშრომლობს SIVRCE-თან.''','author':'SIVRCE Editorial'},
]
def seed_editorial():
 with Local() as db:
  for item in ORIGINAL_ARTICLES:
   if not db.scalar(select(EditorialArticle.id).where(EditorialArticle.slug==item['slug'])):
    db.add(EditorialArticle(**item,status='published',rights_basis='original'))
  db.commit()

def article_summary(a):return {'id':a.id,'slug':a.slug,'title':a.title,'section':a.section,'deck':a.deck,'author':a.author,'published_at':a.published_at.isoformat()}
@app.get('/api/journal')
def journal_list(db:Session=Depends(sessdb)):
 return [article_summary(a) for a in db.scalars(select(EditorialArticle).where(EditorialArticle.status=='published').order_by(desc(EditorialArticle.published_at))).all()]
@app.get('/journal',response_class=HTMLResponse)
def journal_page(request:Request,db:Session=Depends(sessdb)):
 articles=db.scalars(select(EditorialArticle).where(EditorialArticle.status=='published').order_by(desc(EditorialArticle.published_at))).all()
 return templates.TemplateResponse(request,'index.html',{'page':'journal','articles':articles})
@app.get('/journal/{slug}',response_class=HTMLResponse)
def journal_detail(slug:str,request:Request,db:Session=Depends(sessdb)):
 a=db.scalar(select(EditorialArticle).where(EditorialArticle.slug==slug,EditorialArticle.status=='published'))
 if not a:jsonerr(404,'სტატია ვერ მოიძებნა')
 return templates.TemplateResponse(request,'index.html',{'page':'article','article':a})
class ArticleIn(BaseModel):
 slug:str=Field(pattern=r'^[a-z0-9-]{4,120}$');title:str=Field(min_length=20,max_length=240);section:str=Field(min_length=3,max_length=100);deck:str=Field(min_length=30,max_length=700);body:str=Field(min_length=250,max_length=20000);author:str=Field(min_length=3,max_length=120);source_url:str='';rights_basis:str='original'
@app.post('/api/admin/journal')
def publish_article(d:ArticleIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მოდერატორის უფლება აუცილებელია')
 if d.rights_basis!='original':jsonerr(422,'მესამე მხარის თარგმანი/რეპროდუქცია ნებართვისა და ჩანაწერის გარეშე ვერ გამოქვეყნდება')
 if db.scalar(select(EditorialArticle).where(EditorialArticle.slug==d.slug)):jsonerr(409,'URL უკვე არსებობს')
 a=EditorialArticle(**d.model_dump(),status='published');db.add(a);db.flush();log(db,u,None,'publish_editorial',str(a.id));db.commit();return article_summary(a)
class RightsIn(BaseModel):
 content_type:str;content_id:int;source_url:str=Field(min_length=10,max_length=600);rights_holder:str=Field(min_length=3,max_length=180);permitted_use:str; evidence:str=Field(default='',max_length=3000)
@app.post('/api/admin/content-rights')
def rights_record(d:RightsIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მოდერატორის უფლება აუცილებელია')
 if d.content_type not in ('episode','article','course','job') or d.permitted_use not in ('official_embed','original','licensed_excerpt','licensed_translation','licensed_dubbing'):jsonerr(422,'უფლების ან ტიპის არასათანადო ფორმატი')
 if d.permitted_use.startswith('licensed_') and len(d.evidence.strip())<30:jsonerr(422,'ლიცენზიის დამადასტურებელი ინფორმაცია აუცილებელია')
 existing=db.scalar(select(RightsRecord).where(RightsRecord.content_type==d.content_type,RightsRecord.content_id==d.content_id))
 if existing:
  for k,v in d.model_dump().items():setattr(existing,k,v)
  existing.checked_by=u.id;existing.checked_on=utcnow()
 else:db.add(RightsRecord(**d.model_dump(),checked_by=u.id))
 log(db,u,None,'rights_review',f'{d.content_type}:{d.content_id}');db.commit();return {'ok':True}
@app.get('/api/admin/content-rights')
def rights_list(u:User=Depends(current),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მოდერატორის უფლება აუცილებელია')
 return [{'content_type':r.content_type,'content_id':r.content_id,'permitted_use':r.permitted_use,'rights_holder':r.rights_holder,'source_url':r.source_url,'evidence':r.evidence} for r in db.scalars(select(RightsRecord))]

class LeadIn(BaseModel):
 email:str;organization:str=Field(min_length=2,max_length=160);need:str;message:str=Field(default='',max_length=1200)
@app.post('/api/pilot-interest',status_code=201)
def pilot_interest(d:LeadIn,db:Session=Depends(sessdb)):
 if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',d.email):jsonerr(422,'ელფოსტა არასწორია')
 if d.need not in ('hire','develop','both'):jsonerr(422,'აირჩიეთ მიმართულება')
 # Public pilot inquiries require anti-spam controls before internet exposure.
 if os.getenv('APP_ENV')=='production':jsonerr(503,'საჯარო მოთხოვნა ჩართვამდე უნდა დაემატოს anti-spam და შეტყობინებების რიგი')
 db.add(PilotLead(**d.model_dump()));db.commit();return {'received':True,'contact_not_automated':True}
@app.get('/api/admin/pilot-interest')
def pilot_list(u:User=Depends(current),db:Session=Depends(sessdb)):
 if not u.admin:jsonerr(403,'მოდერატორი აუცილებელია')
 return [{'id':x.id,'organization':x.organization,'email':x.email,'need':x.need,'message':x.message} for x in db.scalars(select(PilotLead).order_by(desc(PilotLead.created))).all()]

@app.get('/business',response_class=HTMLResponse)
def business_page(request:Request):return templates.TemplateResponse(request,'business_v5.html',{'page':'business-overview'})

# Structured JobPosting metadata is emitted for real, published, still-open jobs only.
# Demo jobs must not be indexed as genuine vacancies.
def job_schema(db:Session,j:Job,request:Request):
 org=db.get(Organization,j.org_id)
 if not org or org.demo or not org.verified or j.status!='published' or dt.date.fromisoformat(j.deadline)<dt.date.today():return None
 from html import escape
 text=''.join(f'<p>{escape(v)}</p>' for v in (j.purpose,j.responsibilities,j.requirements,j.benefits,j.hiring_steps))
 schema={'@context':'https://schema.org','@type':'JobPosting','title':j.title,'description':text,'datePosted':j.created.date().isoformat(),'validThrough':j.deadline+'T23:59:00+04:00','employmentType':'FULL_TIME' if j.employment=='სრული განაკვეთი' else 'OTHER','hiringOrganization':{'@type':'Organization','name':org.name,'sameAs':org.website or str(request.base_url)+'organizations/'+org.slug},'jobLocation':{'@type':'Place','address':{'@type':'PostalAddress','addressLocality':j.location,'addressCountry':'GE'}},'baseSalary':{'@type':'MonetaryAmount','currency':j.currency,'value':{'@type':'QuantitativeValue','minValue':j.salary_min,'maxValue':j.salary_max,'unitText':'MONTH'}},'identifier':{'@type':'PropertyValue','name':'SIVRCE','value':str(j.id)},'directApply':True}
 if j.work_mode=='დისტანციური':schema['jobLocationType']='TELECOMMUTE';schema['applicantLocationRequirements']={'@type':'Country','name':'Georgia'}
 return json.dumps(schema,ensure_ascii=False).replace('<','\u003c')


# Provider-owned catalog ingestion — explicit rights attestation; every import awaits editorial review.
@app.post('/api/organizations/{oid}/courses/import-csv')
async def import_provider_courses(oid:int,catalog:UploadFile=File(...),rights_attested:bool=Form(...),preview:bool=False,u:User=Depends(security),db:Session=Depends(sessdb)):
 import csv,io
 org=member(db,u,oid,'provider',permission='catalog_write')
 if not rights_attested:jsonerr(422,'უნდა დაადასტუროთ, რომ გაქვთ კატალოგის გამოქვეყნების უფლება')
 if not catalog.filename or not catalog.filename.lower().endswith('.csv'):jsonerr(422,'მხოლოდ UTF-8 CSV ფორმატი')
 raw=await catalog.read(256*1024+1)
 if len(raw)>256*1024:jsonerr(413,'ფაილი აღემატება 256 KB-ს')
 try:
  rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 except (UnicodeError,csv.Error):jsonerr(422,'CSV უნდა იყოს UTF-8 და სწორად ფორმატირებული')
 required={'title','category','format','description','outcomes','curriculum','trainer','price','duration'}
 if not rows or len(rows)>50 or any(not required.issubset(row) for row in rows):jsonerr(422,'საჭიროა 1–50 ჩანაწერი და შაბლონის ყველა სვეტი')
 validated=[]
 for idx,row in enumerate(rows,1):
  try:
   item=CourseIn.model_validate({'org_id':oid,**{key:(row.get(key) or '').strip() for key in required},'publish':True})
   validated.append(item)
  except Exception:jsonerr(422,f'სტრიქონი {idx}: აკლია სავალდებულო ინფორმაცია ან მონაცემი არასწორია')
 if preview:return {'preview':True,'rows':[item.model_dump(exclude={'org_id','publish'}) for item in validated],'count':len(validated),'written':0}
 imported=[]
 for item in validated:
  # CSV imports cannot bypass human moderation even for verified providers.
  data=item.model_dump(exclude={'publish','org_id'})
  record=Course(org_id=oid,**data,status='pending_review' if org.verified else 'draft')
  db.add(record);db.flush();imported.append(record.id)
 log(db,u,oid,'import_provider_courses',f'{len(imported)} items; rights attested');db.commit()
 return {'imported':len(imported),'course_ids':imported,'status':'pending_review' if org.verified else 'draft','paid':False}

class InterestStatusIn(BaseModel):
 status:str
@app.patch('/api/course-interests/{iid}')
def update_course_interest(iid:int,d:InterestStatusIn,u:User=Depends(security),db:Session=Depends(sessdb)):
 record=db.get(CourseInterest,iid)
 if not record:jsonerr(404,'კურსზე მოთხოვნა ვერ მოიძებნა')
 cohort=db.get(Cohort,record.cohort_id);course=db.get(Course,cohort.course_id)
 member(db,u,course.org_id,'provider',permission='catalog_write')
 if d.status not in ('confirmed','declined'):jsonerr(422,'არასწორი სტატუსი')
 if record.status!='requested':jsonerr(409,'ამ მოთხოვნაზე გადაწყვეტილება მიღებულია')
 record.status=d.status;log(db,u,course.org_id,'course_interest_status',str(iid));db.commit()
 return {'status':d.status,'payment_collected':False}
@app.post('/api/jobs/{jid}/close')
def close_job(jid:int,u:User=Depends(security),db:Session=Depends(sessdb)):
 j=db.get(Job,jid)
 if not j:jsonerr(404,'ვაკანსია ვერ მოიძებნა')
 member(db,u,j.org_id,'company',permission='hire_write')
 if j.status=='closed':return {'status':'closed'}
 if j.status!='published':jsonerr(409,'დახურვა შეიძლება მხოლოდ გამოქვეყნებული ვაკანსიისთვის')
 j.status='closed';log(db,u,j.org_id,'close_job',str(jid));db.commit();return {'status':'closed'}

# v5: Product-first company experience. Public preview never writes demo events
# into the multi-tenant database; authenticated companies use existing secured APIs.
@app.get('/business/experience',response_class=HTMLResponse)
def business_experience(request:Request):
 return templates.TemplateResponse(request,'workbench_v5.html',{'page':'business-experience'})

@app.get('/business/overview',response_class=HTMLResponse)
def business_overview(request:Request):
 return templates.TemplateResponse(request,'business_v5.html',{'page':'business-overview'})

@app.get('/start',response_class=HTMLResponse)
def organization_start(request:Request):
 return templates.TemplateResponse(request,'onboarding_v5.html',{'page':'start'})

def proposal_version(db,pid):
 from features.models import ProposalRevision
 return db.scalar(select(func.max(ProposalRevision.version)).where(ProposalRevision.proposal_id==pid)) or 1

# Register additive workflows after the original model definitions.
from features.routes import router as platform_router
app.include_router(platform_router)
from features.showcase import router as showcase_router
app.include_router(showcase_router)
from features.candidate import router as candidate_router
app.include_router(candidate_router)
from features.develop import router as develop_router
app.include_router(develop_router)
from features.middleware import install_middleware
install_middleware(app)

from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse
@app.exception_handler(IntegrityError)
async def integrity_conflict(request,error):
 return JSONResponse({'detail':'ჩანაწერი უკვე არსებობს ან დაკავშირებული ჩანაწერი შეიცვალა. განაახლე გვერდი.'},status_code=409)

@app.get('/ready')
def readiness():
 try:
  with engine.connect() as connection:connection.execute(select(1))
 except Exception:return JSONResponse({'status':'unavailable'},status_code=503)
 return {'status':'ok','database':'connected'}
