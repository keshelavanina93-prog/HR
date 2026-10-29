"""Organization worlds and Voices episode pages.

Companies describe their own working world (story, a working day, people,
honest difficulties) and upload their own photographs. Every photo carries a
rights confirmation and, when people are visible, their consent. SIVRCE never
fills these pages with stock or generated imagery.
"""
import datetime as dt
import io
import os
import re
import secrets
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from server import (ROOT, Base, Course, Episode, Job, Membership, Organization, RightsRecord, User,
                    current, job_dict, jsonerr, log, member, security, sessdb, signed_user, templates)
from features.models import utcnow

router = APIRouter()
MEDIA_DIR = Path(os.getenv('PUBLIC_MEDIA_DIR') or str(ROOT/'media'))
MAX_PHOTO_BYTES = 5*1024*1024
MAX_PHOTOS = 24
ACCENTS = {'cobalt': '#3755E8', 'oxblood': '#702B42', 'ink': '#15151B', 'plum': '#55366B',
           'slate': '#3B4658', 'clay': '#94472F', 'ochre': '#9A6A12'}
PHOTO_ROLES = ('cover', 'gallery', 'person')


class OrgStory(Base):
    __tablename__ = 'org_stories'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), unique=True)
    tagline: Mapped[str] = mapped_column(String(200), default='')
    accent: Mapped[str] = mapped_column(String(16), default='ink')
    mission: Mapped[str] = mapped_column(Text, default='')
    culture: Mapped[str] = mapped_column(Text, default='')
    hard_parts: Mapped[str] = mapped_column(Text, default='')
    hiring_promise: Mapped[str] = mapped_column(Text, default='')
    team_size: Mapped[str] = mapped_column(String(40), default='')
    founded: Mapped[str] = mapped_column(String(4), default='')
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class OrgDayEntry(Base):
    __tablename__ = 'org_day_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    time: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)


class OrgPhoto(Base):
    __tablename__ = 'org_photos'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(12), default='gallery')
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    alt: Mapped[str] = mapped_column(String(240))
    caption: Mapped[str] = mapped_column(String(240), default='')
    credit: Mapped[str] = mapped_column(String(140))
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    people_consent: Mapped[str] = mapped_column(String(16), default='no_people')
    status: Mapped[str] = mapped_column(String(16), default='published')
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class OrgPerson(Base):
    __tablename__ = 'org_people'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(120))
    quote: Mapped[str] = mapped_column(Text, default='')
    photo_id: Mapped[int | None] = mapped_column(ForeignKey('org_photos.id'), nullable=True)


class EpisodeEditorial(Base):
    __tablename__ = 'episode_editorials'
    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey('episodes.id'), unique=True)
    analysis: Mapped[str] = mapped_column(Text)
    key_points: Mapped[str] = mapped_column(Text, default='')
    author: Mapped[str] = mapped_column(String(120))
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ---------- Organization story ----------

class DayIn(BaseModel):
    time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=20, max_length=600)


class PersonIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    role: str = Field(min_length=2, max_length=120)
    quote: str = Field(default='', max_length=500)
    photo_id: int | None = None
    consent: bool

    @field_validator('consent')
    @classmethod
    def must_consent(cls, value):
        if not value: raise ValueError('ადამიანის გამოქვეყნება საჭიროებს მის თანხმობას')
        return value


class StoryIn(BaseModel):
    tagline: str = Field(default='', max_length=200)
    accent: str = 'ink'
    mission: str = Field(default='', max_length=2000)
    culture: str = Field(default='', max_length=2000)
    hard_parts: str = Field(default='', max_length=1500)
    hiring_promise: str = Field(default='', max_length=1500)
    team_size: str = Field(default='', max_length=40)
    founded: str = Field(default='', pattern=r'^(\d{4})?$')
    day: list[DayIn] = Field(default_factory=list, max_length=8)
    people: list[PersonIn] = Field(default_factory=list, max_length=8)

    @field_validator('accent')
    @classmethod
    def known_accent(cls, value):
        if value not in ACCENTS: raise ValueError('ფერი უნდა იყოს SIVRCE-ის პალიტრიდან')
        return value


def photo_url(photo):
    return f'/media/org/{photo.key}' if photo else ''


def photo_dict(p):
    return {'id': p.id, 'url': photo_url(p), 'role': p.role, 'alt': p.alt, 'caption': p.caption, 'credit': p.credit,
            'width': p.width, 'height': p.height, 'people_consent': p.people_consent}


def story_payload(db, org):
    story = db.scalar(select(OrgStory).where(OrgStory.org_id == org.id))
    photos = db.scalars(select(OrgPhoto).where(OrgPhoto.org_id == org.id, OrgPhoto.status == 'published').order_by(OrgPhoto.id)).all()
    by_id = {p.id: p for p in photos}
    day = db.scalars(select(OrgDayEntry).where(OrgDayEntry.org_id == org.id).order_by(OrgDayEntry.position)).all()
    people = db.scalars(select(OrgPerson).where(OrgPerson.org_id == org.id).order_by(OrgPerson.position)).all()
    cover = next((p for p in reversed(photos) if p.role == 'cover'), None)
    return {
        'story': story,
        'accent': ACCENTS.get(story.accent if story else 'ink', ACCENTS['ink']),
        'accent_name': story.accent if story else 'ink',
        'day': [{'time': d.time, 'title': d.title, 'body': d.body} for d in day],
        'people': [{'name': p.name, 'role': p.role, 'quote': p.quote, 'photo_id': p.photo_id,
                    'photo': photo_dict(by_id[p.photo_id]) if p.photo_id in by_id else None} for p in people],
        'cover': photo_dict(cover) if cover else None,
        'gallery': [photo_dict(p) for p in photos if p.role == 'gallery'],
        'photos': [photo_dict(p) for p in photos],
        'hard_parts': [line.strip() for line in (story.hard_parts if story else '').split('\n') if line.strip()],
    }


@router.get('/api/organizations/{oid}/story')
def read_story(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    org = member(db, u, oid)
    data = story_payload(db, org); story = data.pop('story')
    data['fields'] = {k: getattr(story, k) for k in ('tagline', 'accent', 'mission', 'culture', 'hard_parts',
                      'hiring_promise', 'team_size', 'founded')} if story else {}
    data['organization'] = {'id': org.id, 'name': org.name, 'slug': org.slug, 'kind': org.kind, 'verified': org.verified}
    data['accents'] = ACCENTS
    return data


@router.put('/api/organizations/{oid}/story')
def save_story(oid: int, d: StoryIn, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, oid, None, 'org_write')
    photo_ids = {p.photo_id for p in d.people if p.photo_id}
    if photo_ids:
        allowed = set(db.scalars(select(OrgPhoto.id).where(OrgPhoto.org_id == oid, OrgPhoto.status == 'published',
                                                           OrgPhoto.id.in_(photo_ids), OrgPhoto.people_consent == 'confirmed')))
        if photo_ids - allowed: jsonerr(422, 'ადამიანის ფოტოს მისაბმელად საჭიროა ამ ორგანიზაციის ფოტო, რომელზეც თანხმობა დადასტურებულია')
    story = db.scalar(select(OrgStory).where(OrgStory.org_id == oid)) or OrgStory(org_id=oid)
    for key, value in d.model_dump(exclude={'day', 'people'}).items(): setattr(story, key, value.strip())
    story.updated = utcnow(); db.add(story)
    for row in db.scalars(select(OrgDayEntry).where(OrgDayEntry.org_id == oid)): db.delete(row)
    for row in db.scalars(select(OrgPerson).where(OrgPerson.org_id == oid)): db.delete(row)
    for i, e in enumerate(sorted(d.day, key=lambda e: e.time)):
        db.add(OrgDayEntry(org_id=oid, position=i, time=e.time, title=e.title.strip(), body=e.body.strip()))
    for i, p in enumerate(d.people):
        db.add(OrgPerson(org_id=oid, position=i, name=p.name.strip(), role=p.role.strip(), quote=p.quote.strip(), photo_id=p.photo_id))
    log(db, u, oid, 'update_org_story', str(oid)); db.commit()
    return {'ok': True}


# ---------- Photographs ----------

def normalize_photo(raw):
    """Decode, orient, downscale and re-encode. Re-encoding drops EXIF, including GPS."""
    if len(raw) > MAX_PHOTO_BYTES: jsonerr(413, 'ფოტო 5 MB-ზე დიდი არ უნდა იყოს')
    Image.MAX_IMAGE_PIXELS = 40_000_000
    try:
        probe = Image.open(io.BytesIO(raw))
        if probe.format not in ('JPEG', 'PNG', 'WEBP'): jsonerr(415, 'დასაშვებია JPEG, PNG ან WebP')
        probe.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        jsonerr(422, 'ფაილი არ არის სწორი გამოსახულება')
    if min(image.size) < 600: jsonerr(422, 'ფოტოს მოკლე მხარე მინიმუმ 600px უნდა იყოს')
    image = image.convert('RGB')
    image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=84, optimize=True, progressive=True)
    return out.getvalue(), image.size


@router.post('/api/organizations/{oid}/photos')
async def upload_photo(oid: int, file: UploadFile=File(...), role: str=Form('gallery'), alt: str=Form(...),
                       caption: str=Form(''), credit: str=Form(...), rights_confirmed: bool=Form(False),
                       people_consent: str=Form('no_people'), u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, oid, None, 'org_write')
    if role not in PHOTO_ROLES: jsonerr(422, 'ფოტოს ტიპი არასწორია')
    if not rights_confirmed: jsonerr(422, 'დაადასტურე, რომ ორგანიზაციას აქვს ამ ფოტოს გამოყენების უფლება')
    if people_consent not in ('no_people', 'confirmed'): jsonerr(422, 'ფოტოზე ადამიანების თანხმობა უნდა დადასტურდეს')
    if role == 'person' and people_consent != 'confirmed': jsonerr(422, 'ადამიანის პორტრეტს სჭირდება მისი თანხმობა')
    alt, caption, credit = alt.strip(), caption.strip(), credit.strip()
    if not 8 <= len(alt) <= 240: jsonerr(422, 'აღწერე ფოტო 8–240 სიმბოლოთი (ეკრანის წამკითხველისთვის)')
    if not 2 <= len(credit) <= 140 or len(caption) > 240: jsonerr(422, 'მიუთითე ფოტოს ავტორი; წარწერა მაქსიმუმ 240 სიმბოლოა')
    count = db.scalar(select(func.count(OrgPhoto.id)).where(OrgPhoto.org_id == oid, OrgPhoto.status == 'published'))
    if count >= MAX_PHOTOS: jsonerr(409, f'ერთ ორგანიზაციას მაქსიმუმ {MAX_PHOTOS} ფოტო შეიძლება ჰქონდეს')
    data, (width, height) = normalize_photo(await file.read(MAX_PHOTO_BYTES+1))
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(16)+'.jpg'
    (MEDIA_DIR/key).write_bytes(data)
    if role == 'cover':
        for old in db.scalars(select(OrgPhoto).where(OrgPhoto.org_id == oid, OrgPhoto.role == 'cover', OrgPhoto.status == 'published')):
            old.role = 'gallery'
    photo = OrgPhoto(org_id=oid, key=key, role=role, width=width, height=height, alt=alt, caption=caption, credit=credit,
                     rights_confirmed=True, people_consent=people_consent, uploaded_by=u.id)
    db.add(photo); db.flush(); log(db, u, oid, 'upload_org_photo', str(photo.id)); db.commit()
    return photo_dict(photo)


def remove_photo(db, photo):
    photo.status = 'removed'
    for person in db.scalars(select(OrgPerson).where(OrgPerson.photo_id == photo.id)): person.photo_id = None
    (MEDIA_DIR/photo.key).unlink(missing_ok=True)


@router.delete('/api/organizations/{oid}/photos/{pid}')
def delete_photo(oid: int, pid: int, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, oid, None, 'org_write')
    photo = db.get(OrgPhoto, pid)
    if not photo or photo.org_id != oid or photo.status != 'published': jsonerr(404, 'ფოტო ვერ მოიძებნა')
    remove_photo(db, photo); log(db, u, oid, 'delete_org_photo', str(pid)); db.commit()
    return {'ok': True}


@router.post('/api/admin/photos/{pid}/remove')
def moderate_photo(pid: int, u=Depends(security), db: Session=Depends(sessdb)):
    if not u.admin: jsonerr(403, 'მხოლოდ მოდერატორი')
    photo = db.get(OrgPhoto, pid)
    if not photo or photo.status != 'published': jsonerr(404, 'ფოტო ვერ მოიძებნა')
    remove_photo(db, photo); log(db, u, photo.org_id, 'moderate_org_photo', str(pid)); db.commit()
    return {'ok': True}


@router.get('/media/org/{key}')
def serve_photo(key: str, request: Request, db: Session=Depends(sessdb)):
    if not re.fullmatch(r'[0-9a-f]{32}\.jpg', key): jsonerr(404, 'ფაილი ვერ მოიძებნა')
    photo = db.scalar(select(OrgPhoto).where(OrgPhoto.key == key, OrgPhoto.status == 'published'))
    org = db.get(Organization, photo.org_id) if photo else None
    if not photo or not org: jsonerr(404, 'ფაილი ვერ მოიძებნა')
    public = org.verified
    if not public:
        # Members may preview photos before their organization is verified.
        user, _ = signed_user(request, db)
        if not user or not db.scalar(select(Membership.id).where(Membership.org_id == org.id, Membership.user_id == user.id)):
            jsonerr(404, 'ფაილი ვერ მოიძებნა')
    path = MEDIA_DIR/key
    if not path.is_file(): jsonerr(404, 'ფაილი ვერ მოიძებნა')
    return FileResponse(path, media_type='image/jpeg',
                        headers={'Cache-Control': 'public, max-age=86400' if public else 'private, no-store'})


# ---------- Organization page ----------

def organization_context(db, org):
    today = dt.date.today().isoformat()
    jobs = [job_dict(db, j) for j in db.scalars(select(Job).where(Job.org_id == org.id, Job.status == 'published',
                                                                    Job.deadline >= today))] if org.kind == 'company' else []
    courses = db.scalars(select(Course).where(Course.org_id == org.id, Course.status == 'published')).all() if org.kind == 'provider' else []
    return {'page': 'organization', 'organization': org, 'jobs': jobs, 'courses': courses, 'world': story_payload(db, org)}


@router.get('/workspace/company-profile', response_class=HTMLResponse)
def profile_editor(request: Request):
    return templates.TemplateResponse(request, 'profile_editor.html', {})


# ---------- Voices episode pages ----------

TOPIC_STEMS = {
    'leadership': ('ლიდერ', 'მენეჯ', 'leadership'), 'strategy': ('სტრატეგ', 'ლიდერ', 'strategy'),
    'technology': ('ტექნოლოგ', 'ai', 'technology'), 'ai': ('ai', 'ტექნოლოგ'),
    'psychology': ('ფსიქოლოგ', 'კომუნიკაც', 'people'), 'work': ('people', 'კარიერ', 'hr', 'culture'),
}
COVER_TONES = {'leadership': 'ink', 'technology': 'cobalt', 'ai': 'cobalt', 'psychology': 'oxblood', 'work': 'oxblood'}


class EditorialIn(BaseModel):
    analysis: str = Field(min_length=300, max_length=12000)
    key_points: str = Field(default='', max_length=2000)
    author: str = Field(min_length=3, max_length=120)


def topic_keys(topic):
    return [t.strip().lower() for t in re.split(r'[/·,]', topic) if t.strip()]


def episode_cover(ep, number):
    keys = topic_keys(ep.topic)
    tone = next((COVER_TONES[k] for k in keys if k in COVER_TONES), 'porcelain')
    return {'tone': tone, 'variant': ep.id % 4, 'number': f'{number:02d}', 'topic': ' · '.join(t.strip() for t in ep.topic.split('/'))}


def access_levels(editorial, rights):
    use = rights.permitted_use if rights else 'official_embed'
    translated = use in ('licensed_translation', 'licensed_dubbing')
    return [
        {'key': 'original', 'title': 'ორიგინალი', 'state': 'open',
         'note': 'ოფიციალური პლეიერი, სრული ორიგინალური საუბარი და პირველწყაროს ბმული.'},
        {'key': 'analysis', 'title': 'ქართული ანალიზი', 'state': 'open' if editorial else 'pending',
         'note': 'SIVRCE-ის დამოუკიდებლად დაწერილი ტექსტი — არა სხვისი ტრანსკრიპტის თარგმანი.' if editorial else 'ანალიზი მზადდება. გამოქვეყნდება რედაქტორის შემოწმების შემდეგ.'},
        {'key': 'subtitles', 'title': 'ქართული სუბტიტრები', 'state': 'open' if translated else 'locked',
         'note': 'ლიცენზირებული თარგმანი.' if translated else 'ჩაკეტილია, სანამ ავტორთან თარგმნის ლიცენზია არ გაფორმდება.'},
        {'key': 'dubbing', 'title': 'ქართული გახმოვანება', 'state': 'open' if use == 'licensed_dubbing' else 'locked',
         'note': 'ლიცენზირებული გახმოვანება ხმის მფლობელის თანხმობით.' if use == 'licensed_dubbing' else 'ჩაკეტილია: საჭიროა ავტორის ლიცენზია და ხმის მფლობელის დადასტურებული თანხმობა.'},
    ]


def related_for(db, ep):
    stems = {s for k in topic_keys(ep.topic) for s in TOPIC_STEMS.get(k, ())}
    if not stems: return [], []
    def hit(*texts): return any(s in ' '.join(texts).lower() for s in stems)
    courses = [c for c, o in db.execute(select(Course, Organization).join(Organization, Course.org_id == Organization.id)
               .where(Course.status == 'published', Organization.verified == True)).all() if hit(c.title, c.category, c.description)][:3]
    today = dt.date.today().isoformat()
    jobs = [job_dict(db, j) for j, o in db.execute(select(Job, Organization).join(Organization, Job.org_id == Organization.id)
            .where(Job.status == 'published', Job.deadline >= today, Organization.verified == True)).all()
            if hit(j.title, j.department, j.purpose)][:3]
    return courses, jobs


def spotify_embed(url):
    m = re.fullmatch(r'https://open\.spotify\.com/(show|episode)/([A-Za-z0-9]+)', url or '')
    return f'https://open.spotify.com/embed/{m.group(1)}/{m.group(2)}' if m else ''


@router.get('/voices/{eid}', response_class=HTMLResponse)
def episode_page(eid: int, request: Request, db: Session=Depends(sessdb)):
    ep = db.get(Episode, eid)
    if not ep or ep.status != 'published': jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    published = db.scalars(select(Episode).where(Episode.status == 'published').order_by(Episode.id)).all()
    index = [e.id for e in published].index(ep.id)
    editorial = db.scalar(select(EpisodeEditorial).where(EpisodeEditorial.episode_id == ep.id))
    rights = db.scalar(select(RightsRecord).where(RightsRecord.content_type == 'episode', RightsRecord.content_id == ep.id))
    courses, jobs = related_for(db, ep)
    neighbours = [published[i] for i in (index-1, index+1) if 0 <= i < len(published)]
    return templates.TemplateResponse(request, 'index.html', {
        'page': 'episode', 'episode': ep, 'cover': episode_cover(ep, index+1), 'editorial': editorial,
        'key_points': [l.strip() for l in (editorial.key_points if editorial else '').split('\n') if l.strip()],
        'rights': rights, 'levels': access_levels(editorial, rights), 'embed': spotify_embed(ep.spotify),
        'related_courses': courses, 'related_jobs': jobs,
        'others': [{'id': e.id, 'title': e.title, 'cover': episode_cover(e, published.index(e)+1)} for e in neighbours]})


@router.put('/api/admin/voices/{eid}/editorial')
def save_editorial(eid: int, d: EditorialIn, u=Depends(security), db: Session=Depends(sessdb)):
    if not u.admin: jsonerr(403, 'მხოლოდ მოდერატორი')
    if not db.get(Episode, eid): jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    row = db.scalar(select(EpisodeEditorial).where(EpisodeEditorial.episode_id == eid)) or EpisodeEditorial(episode_id=eid)
    row.analysis, row.key_points, row.author, row.updated = d.analysis.strip(), d.key_points.strip(), d.author.strip(), utcnow()
    db.add(row); log(db, u, None, 'episode_editorial', str(eid)); db.commit()
    return {'ok': True}


def episode_covers(db):
    """Cover specs for the Voices index, keyed by episode id."""
    published = db.scalars(select(Episode).where(Episode.status == 'published').order_by(Episode.id)).all()
    return {e.id: episode_cover(e, i+1) for i, e in enumerate(published)}


# ---------- Demo content (local development only, clearly labelled) ----------

def seed_showcase():
    if os.getenv('SEED_DEMO', '0') != '1': return
    from server import Local
    with Local() as db:
        org = db.scalar(select(Organization).where(Organization.slug == 'atelier-demo', Organization.demo == True))
        if not org or db.scalar(select(OrgStory.id).where(OrgStory.org_id == org.id)): return
        db.add(OrgStory(org_id=org.id, accent='oxblood', team_size='40–60 · DEMO', founded='2019',
            tagline='საჩვენებელი კომპანია: ასე გამოიყურება სამყარო, როცა კომპანია თავად ყვება საკუთარ საქმეზე.',
            mission='ვეხმარებით ორგანიზაციებს, რომ თანამშრომლის გამოცდილება იყოს დაგეგმილი და არა შემთხვევითი: პირველი დღიდან განვითარების საუბრებამდე. ეს ტექსტი საჩვენებელია და აჩვენებს, რა ინფორმაციას ელოდება კანდიდატი.',
            culture='გადაწყვეტილებებს წერილობით ვაფიქსირებთ, რომ გუნდმა იცოდეს რატომ და არა მხოლოდ რა. შეხვედრებს აქვს დღის წესრიგი და დასრულების დრო. სამშაბათი და ხუთშაბათი ოფისში ერთად ვართ, დანარჩენ დღეებს გუნდი თავად გეგმავს.',
            hard_parts='ნოემბერ-დეკემბერში კლიენტების წლიური შეფასებების გამო დატვირთვა იზრდება.\nზოგიერთი პროექტი მოითხოვს რეგიონებში მოკლე მივლინებებს.\nპროცესებს ჯერ ვაშენებთ — ყველაფერი დოკუმენტირებული არ არის.',
            hiring_promise='ყველა კანდიდატი პასუხს იღებს 10 სამუშაო დღეში. შერჩევა სამ ეტაპად მიმდინარეობს და პრაქტიკული დავალება ანაზღაურებადია, თუ ორ საათზე მეტს მოითხოვს.'))
        for i, (time, title, body) in enumerate([
            ('09:30', 'დღის დაგეგმვა', 'გუნდი 15 წუთით იკრიბება: რა დასრულდა გუშინ, რა იბლოკება და ვის რა დახმარება სჭირდება.'),
            ('11:00', 'სამუშაო კლიენტთან', 'People & Culture Partner-ი ხელმძღვანელთან ერთად განიხილავს ახალი თანამშრომლების ადაპტაციის შედეგებს.'),
            ('14:00', 'ღრმა მუშაობის საათები', 'შეხვედრების გარეშე ბლოკი: ანალიზი, დოკუმენტები და პროცესების აღწერა.'),
            ('17:30', 'დღის დახურვა', 'მოკლე წერილობითი შეჯამება საერთო არხში. საღამოს შეტყობინებებზე პასუხს არ ველით.'),
        ]):
            db.add(OrgDayEntry(org_id=org.id, position=i, time=time, title=title, body=body))
        for i, (name, role, quote) in enumerate([
            ('ანა კ. · DEMO', 'People & Culture Lead', 'აქ ყველაზე მეტად ის მომწონს, რომ რთულ საკითხზე საუბარი ნორმალურად ითვლება.'),
            ('გიორგი მ. · DEMO', 'ანალიტიკოსი', 'პირველ კვირაში უკვე მქონდა რეალური დავალება და ადამიანი, ვისაც შემეძლო ყველაფერი მეკითხა.'),
            ('თამარ ლ. · DEMO', 'პროექტის მენეჯერი', 'მივლინებები ხანდახან დამღლელია, მაგრამ წინასწარ ვიცით და გეგმაში ჩანს.'),
        ]):
            db.add(OrgPerson(org_id=org.id, position=i, name=name, role=role, quote=quote))
        db.commit()
