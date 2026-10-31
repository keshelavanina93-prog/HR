"""SIVRCE Voices — the Georgian podcast index.

Shows are indexed from their public RSS feeds, exactly as every podcast app does:
audio plays from the publisher's own servers, artwork and descriptions are the
publisher's, and every page links back to the source. SIVRCE adds its own layer
on top — a Georgian brief, key points, chapters and (for shows claimed by their
publishers) a searchable transcript — and never republishes audio.
"""
import datetime as dt
import email.utils
import html
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, desc, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from server import (Base, Course, Episode, Job, Membership, Organization, current, episode_dict, job_dict, jsonerr, log,
                    member, security, sessdb, slug as make_slug, templates)
from features.models import utcnow

router = APIRouter()
USER_AGENT = 'SIVRCE Voices/1.0 (+https://beta.ncore.space/voices; podcast index)'
MAX_FEED_BYTES = 8*1024*1024
MAX_EPISODES_PER_SHOW = 300
NS = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd', 'content': 'http://purl.org/rss/1.0/modules/content/',
      'media': 'http://search.yahoo.com/mrss/', 'atom': 'http://www.w3.org/2005/Atom'}

# Editorial lanes. Order matters: it is the order on the index page.
TOPICS = [('work', 'საქმე და ბიზნესი'), ('science', 'მეცნიერება და ტექნოლოგია'), ('society', 'საზოგადოება'),
          ('culture', 'კულტურა და ისტორია'), ('growth', 'ზრდა და ჯანმრთელობა'), ('other', 'სხვა')]
TOPIC_LABEL = dict(TOPICS)
CATEGORY_TOPIC = {
    'business': 'work', 'careers': 'work', 'entrepreneurship': 'work', 'management': 'work', 'marketing': 'work', 'investing': 'work',
    'science': 'science', 'technology': 'science', 'education': 'science', 'natural sciences': 'science', 'astronomy': 'science',
    'society & culture': 'society', 'news': 'society', 'politics': 'society', 'social sciences': 'society', 'documentary': 'society',
    'personal journals': 'society', 'relationships': 'society', 'philosophy': 'society',
    'arts': 'culture', 'books': 'culture', 'history': 'culture', 'tv & film': 'culture', 'music': 'culture', 'film reviews': 'culture',
    'health & fitness': 'growth', 'mental health': 'growth', 'self-improvement': 'growth', 'medicine': 'growth', 'fitness': 'growth',
}
TOPIC_STEMS = {
    'work': ('ბიზნეს', 'კარიერ', 'მენეჯ', 'ლიდერ', 'მარკეტ', 'გაყიდ', 'სტარტაპ', 'hr', 'ფინანს', 'business', 'leadership'),
    'science': ('ტექნოლოგ', 'მეცნიერ', 'ai', 'ხელოვნურ', 'ინტელექტ', 'მონაცემ', 'პროგრამ', 'ინჟინერ'),
    'society': ('საზოგადო', 'პოლიტიკ', 'სოციალ', 'ეკონომიკ', 'განათლებ'),
    'culture': ('კულტურ', 'ისტორი', 'ლიტერატურ', 'კინო', 'მუსიკ', 'ხელოვნებ'),
    'growth': ('ფსიქოლოგ', 'ჯანმრთელ', 'მედიცინ', 'კომუნიკაც', 'ემოცი'),
}


class Show(Base):
    __tablename__ = 'shows'
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    author: Mapped[str] = mapped_column(String(200), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    feed_url: Mapped[str] = mapped_column(String(600), unique=True)
    site_url: Mapped[str] = mapped_column(String(600), default='')
    artwork_url: Mapped[str] = mapped_column(String(600), default='')
    language: Mapped[str] = mapped_column(String(12), default='ka')
    categories: Mapped[str] = mapped_column(String(240), default='')
    topic: Mapped[str] = mapped_column(String(20), default='other')
    status: Mapped[str] = mapped_column(String(16), default='listed')   # listed | hidden
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    claim_status: Mapped[str] = mapped_column(String(16), default='none')  # none | requested | claimed
    claim_org_id: Mapped[int | None] = mapped_column(ForeignKey('organizations.id'), nullable=True)
    apple_id: Mapped[str] = mapped_column(String(30), default='')
    last_fetched: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    fetch_error: Mapped[str] = mapped_column(String(300), default='')
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ShowEpisode(Base):
    __tablename__ = 'show_episodes'
    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey('shows.id'), index=True)
    guid: Mapped[str] = mapped_column(String(400))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default='')
    audio_url: Mapped[str] = mapped_column(String(700), default='')
    audio_type: Mapped[str] = mapped_column(String(60), default='')
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    artwork_url: Mapped[str] = mapped_column(String(600), default='')
    link: Mapped[str] = mapped_column(String(600), default='')
    season: Mapped[int] = mapped_column(Integer, default=0)
    number: Mapped[int] = mapped_column(Integer, default=0)
    # SIVRCE's own layer. Editors write it; the transcription worker can draft it.
    brief_ka: Mapped[str] = mapped_column(Text, default='')
    key_points: Mapped[str] = mapped_column(Text, default='')
    chapters: Mapped[list] = mapped_column(JSON, default=list)   # [{"t": 125, "title": "..."}]
    transcript: Mapped[str] = mapped_column(Text, default='')
    transcript_status: Mapped[str] = mapped_column(String(16), default='none')  # none | queued | done | failed
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default='listed')
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('show_id', 'guid'),)


# ---------- Feed fetching and parsing ----------

class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []
    def handle_data(self, d): self.parts.append(d)
    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'br', 'li', 'div', 'h1', 'h2', 'h3'): self.parts.append('\n')


def strip_html(s, limit=4000):
    if not s: return ''
    p = _Text(); p.feed(s)
    text = html.unescape(''.join(p.parts))
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
    return text[:limit]


def safe_public_url(url):
    """Only http(s) to public hosts: the fetcher must never reach the private network."""
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname: raise ValueError('ბმული უნდა იწყებოდეს http(s)://')
    try:
        for info in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError('ბმული შიდა ქსელისკენ მიუთითებს')
    except socket.gaierror:
        raise ValueError('ჰოსტი ვერ მოიძებნა')
    return url


def fetch(url, max_bytes=MAX_FEED_BYTES, timeout=25):
    safe_public_url(url)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        safe_public_url(r.geturl())
        data = r.read(max_bytes+1)
    if len(data) > max_bytes: raise ValueError('ფიდი ზედმეტად დიდია')
    return data


def _t(el, *paths):
    for p in paths:
        node = el.find(p, NS)
        if node is not None:
            if p.endswith('image') or p.endswith('image]'): return (node.get('href') or '').strip()
            if node.text: return node.text.strip()
    return ''


def _img(el):
    for p in ('itunes:image', 'image/url', 'media:thumbnail', 'media:content'):
        node = el.find(p, NS)
        if node is not None:
            v = node.get('href') or node.get('url') or (node.text or '')
            if v: return v.strip()
    return ''


def parse_duration(s):
    s = (s or '').strip()
    if not s: return 0
    if s.isdigit(): return int(s)
    parts = s.split(':')
    try:
        parts = [int(float(p)) for p in parts]
    except ValueError: return 0
    while len(parts) < 3: parts.insert(0, 0)
    return parts[0]*3600 + parts[1]*60 + parts[2]


def parse_date(s):
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = dt.datetime.fromisoformat((s or '').replace('Z', '+00:00'))
        except Exception: return None
    if d.tzinfo: d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return d


def parse_feed(data):
    root = ET.fromstring(data)
    channel = root.find('channel')
    if channel is None: raise ValueError('ეს არ არის RSS ფიდი')
    cats = []
    for c in channel.findall('itunes:category', NS):
        if c.get('text'): cats.append(c.get('text'))
        for sub in c.findall('itunes:category', NS):
            if sub.get('text'): cats.append(sub.get('text'))
    show = {
        'title': _t(channel, 'title')[:240], 'author': _t(channel, 'itunes:author', 'managingEditor')[:200],
        'description': strip_html(_t(channel, 'description', 'itunes:summary'), 3000),
        'site_url': _t(channel, 'link')[:600], 'artwork_url': _img(channel)[:600],
        'language': (_t(channel, 'language') or 'ka')[:12].lower(), 'categories': ', '.join(dict.fromkeys(cats))[:240],
    }
    episodes = []
    for item in channel.findall('item'):
        enc = item.find('enclosure')
        audio = (enc.get('url') if enc is not None else '') or ''
        guid = _t(item, 'guid') or audio or _t(item, 'link')
        if not guid or not audio: continue
        published = parse_date(_t(item, 'pubDate', 'published')) or utcnow()
        episodes.append({
            'guid': guid[:400], 'title': (_t(item, 'title') or 'უსათაურო ეპიზოდი')[:300],
            'description': strip_html(_t(item, 'content:encoded', 'description', 'itunes:summary')),
            'audio_url': audio[:700], 'audio_type': ((enc.get('type') if enc is not None else '') or '')[:60],
            'duration_sec': parse_duration(_t(item, 'itunes:duration')), 'published_at': published,
            'artwork_url': _img(item)[:600], 'link': _t(item, 'link')[:600],
            'season': int(_t(item, 'itunes:season') or 0) if _t(item, 'itunes:season').isdigit() else 0,
            'number': int(_t(item, 'itunes:episode') or 0) if _t(item, 'itunes:episode').isdigit() else 0,
        })
    episodes.sort(key=lambda e: e['published_at'], reverse=True)
    return show, episodes[:MAX_EPISODES_PER_SHOW]


def topic_for(categories, title=''):
    for c in [c.strip().lower() for c in (categories or '').split(',')]:
        if c in CATEGORY_TOPIC: return CATEGORY_TOPIC[c]
    low = title.lower()
    for topic, stems in TOPIC_STEMS.items():
        if any(s in low for s in stems): return topic
    return 'other'


GEO_LATIN = dict(zip('აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ',
                     ['a','b','g','d','e','v','z','t','i','k','l','m','n','o','p','zh','r','s','t','u','p','k','gh','q','sh','ch','ts','dz','ts','ch','kh','j','h']))


def slugify(title):
    latin = ''.join(GEO_LATIN.get(c, c) for c in title.lower())
    return re.sub(r'[^a-z0-9]+', '-', latin).strip('-')[:120]


def upsert_show(db, feed_url, topic=None, featured=None, apple_id=''):
    """Fetch a feed and create or update its Show and episodes. Returns (show, new_episode_count)."""
    data = fetch(feed_url)
    meta, items = parse_feed(data)
    show = db.scalar(select(Show).where(Show.feed_url == feed_url))
    if not show:
        base = slugify(meta['title']) or 'show'
        show = Show(feed_url=feed_url, slug=base if not db.scalar(select(Show.id).where(Show.slug == base)) else base+'-'+make_slug('x')[-6:], title=meta['title'] or feed_url,
                    topic=topic or topic_for(meta['categories'], meta['title']))
        db.add(show); db.flush()
    for k in ('title', 'author', 'description', 'site_url', 'artwork_url', 'language', 'categories'):
        if meta[k]: setattr(show, k, meta[k])
    if topic: show.topic = topic
    if featured is not None: show.featured = featured
    if apple_id: show.apple_id = apple_id
    show.last_fetched = utcnow(); show.fetch_error = ''
    existing = {e.guid: e for e in db.scalars(select(ShowEpisode).where(ShowEpisode.show_id == show.id))}
    new = 0
    for item in items:
        row = existing.get(item['guid'])
        if row:
            for k, v in item.items():
                if k != 'guid' and v: setattr(row, k, v)
        else:
            db.add(ShowEpisode(show_id=show.id, **item)); new += 1
    db.commit()
    return show, new


def refresh_all(db, max_age_minutes=50):
    cutoff = utcnow() - dt.timedelta(minutes=max_age_minutes)
    out = []
    for show in db.scalars(select(Show).where(Show.status != 'deleted')):
        if show.last_fetched and show.last_fetched > cutoff: continue
        try:
            _, new = upsert_show(db, show.feed_url); out.append((show.title, new))
        except Exception as error:
            db.rollback(); show.fetch_error = f'{type(error).__name__}: {error}'[:300]; show.last_fetched = utcnow(); db.commit()
            out.append((show.title, f'✗ {show.fetch_error}'))
    return out


# ---------- Presentation helpers ----------

def fmt_duration(sec):
    if not sec: return ''
    h, m = divmod(sec//60, 60)
    return f'{h} სთ {m} წთ' if h else f'{m} წთ'


MONTHS = ['იანვ', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ']


def fmt_date(d):
    if not d: return ''
    return f'{d.day} {MONTHS[d.month-1]}' + ('' if d.year == dt.date.today().year else f' {d.year}')


def https_only(url):
    """Pages are served over HTTPS; plain-http media would be blocked as mixed content."""
    return url if url.startswith('https://') else ''


def ep_view(e, show):
    return {'id': e.id, 'title': e.title, 'show': show.title, 'show_slug': show.slug, 'topic': show.topic,
            'artwork': https_only(e.artwork_url) or https_only(show.artwork_url), 'show_art': https_only(show.artwork_url) or https_only(e.artwork_url),
            'audio': https_only(e.audio_url),
            'duration': fmt_duration(e.duration_sec), 'duration_sec': e.duration_sec, 'date': fmt_date(e.published_at),
            'published': e.published_at.isoformat(), 'description': e.description, 'brief': e.brief_ka,
            'key_points': [l.strip() for l in e.key_points.split('\n') if l.strip()], 'chapters': e.chapters or [],
            'has_transcript': e.transcript_status == 'done', 'featured': e.featured, 'link': e.link, 'number': e.number,
            'claimed': show.claim_status == 'claimed'}


def show_view(s, episode_count=0, latest=None):
    return {'id': s.id, 'slug': s.slug, 'title': s.title, 'author': s.author, 'artwork': https_only(s.artwork_url),
            'topic': s.topic, 'topic_label': TOPIC_LABEL.get(s.topic, 'სხვა'), 'claimed': s.claim_status == 'claimed',
            'episodes': episode_count, 'latest': fmt_date(latest) if latest else '', 'description': s.description,
            'site_url': s.site_url if s.site_url.startswith('https://') else '', 'feed_url': s.feed_url,
            'apple_id': s.apple_id, 'featured': s.featured}


def listed_shows(db):
    return db.scalars(select(Show).where(Show.status == 'listed').order_by(desc(Show.featured), Show.title)).all()


def listed_episodes(db, limit=200, show_ids=None):
    q = (select(ShowEpisode, Show).join(Show, ShowEpisode.show_id == Show.id)
         .where(Show.status == 'listed', ShowEpisode.status == 'listed', ShowEpisode.audio_url.like('https://%'))
         .order_by(desc(ShowEpisode.published_at)).limit(limit))
    if show_ids is not None: q = q.where(Show.id.in_(show_ids or [0]))
    return [(e, s) for e, s in db.execute(q).all()]


def index_context(db):
    shows = listed_shows(db)
    counts = dict(db.execute(select(ShowEpisode.show_id, func.count(ShowEpisode.id)).group_by(ShowEpisode.show_id)).all())
    latest = dict(db.execute(select(ShowEpisode.show_id, func.max(ShowEpisode.published_at)).group_by(ShowEpisode.show_id)).all())
    recent = [ep_view(e, s) for e, s in listed_episodes(db, 160)]
    featured = db.execute(select(ShowEpisode, Show).join(Show, ShowEpisode.show_id == Show.id)
                          .where(ShowEpisode.featured == True, Show.status == 'listed').order_by(desc(ShowEpisode.published_at)).limit(1)).first()
    hero = ep_view(*featured) if featured else (next((r for r in recent if r['artwork']), recent[0]) if recent else None)
    lanes = []
    for key, label in TOPICS:
        eps = [r for r in recent if r['topic'] == key and (not hero or r['id'] != hero['id'])][:4]
        lane_shows = [show_view(s, counts.get(s.id, 0), latest.get(s.id)) for s in shows if s.topic == key]
        if eps or lane_shows: lanes.append({'key': key, 'label': label, 'episodes': eps, 'shows': lane_shows[:8]})
    week_ago = utcnow() - dt.timedelta(days=8)
    this_week = [r for r in recent if r['published'] >= week_ago.isoformat() and (not hero or r['id'] != hero['id'])][:10]
    if len(this_week) < 4: this_week = [r for r in recent if not hero or r['id'] != hero['id']][:10]
    return {'page': 'voices', 'hero': hero, 'this_week': this_week, 'lanes': lanes,
            'shows': [show_view(s, counts.get(s.id, 0), latest.get(s.id)) for s in shows],
            'global_shows': [episode_dict(e) for e in db.scalars(select(Episode).where(Episode.status == 'published').order_by(Episode.id))],
            'topics': TOPICS, 'stats': {'shows': len(shows), 'episodes': sum(counts.get(s.id, 0) for s in shows)}}


def related_for(db, text, limit=3):
    low = text.lower()
    stems = {s for stems in TOPIC_STEMS.values() for s in stems if s in low}
    if not stems: return [], []
    hit = lambda *t: any(s in ' '.join(t).lower() for s in stems)
    courses = [c for c, o in db.execute(select(Course, Organization).join(Organization, Course.org_id == Organization.id)
               .where(Course.status == 'published', Organization.verified == True)).all() if hit(c.title, c.category, c.description)][:limit]
    today = dt.date.today().isoformat()
    jobs = [job_dict(db, j) for j, o in db.execute(select(Job, Organization).join(Organization, Job.org_id == Organization.id)
            .where(Job.status == 'published', Job.deadline >= today, Organization.verified == True)).all() if hit(j.title, j.department, j.purpose)][:limit]
    return courses, jobs


# ---------- Public pages ----------

@router.get('/voices/show/{slug}', response_class=HTMLResponse)
def show_page(slug: str, request: Request, db: Session=Depends(sessdb)):
    s = db.scalar(select(Show).where(Show.slug == slug, Show.status == 'listed'))
    if not s: jsonerr(404, 'შოუ ვერ მოიძებნა')
    eps = [ep_view(e, s) for e, _ in listed_episodes(db, 300, [s.id])]
    org = db.get(Organization, s.claim_org_id) if s.claim_status == 'claimed' and s.claim_org_id else None
    latest = db.scalar(select(func.max(ShowEpisode.published_at)).where(ShowEpisode.show_id == s.id))
    return templates.TemplateResponse(request, 'index.html', {'page': 'show', 'show': show_view(s, len(eps), latest),
                                                              'episodes': eps, 'publisher_org': org, 'topics': TOPICS})


@router.get('/voices/ep/{eid}', response_class=HTMLResponse)
def podcast_episode_page(eid: int, request: Request, db: Session=Depends(sessdb)):
    row = db.execute(select(ShowEpisode, Show).join(Show, ShowEpisode.show_id == Show.id)
                     .where(ShowEpisode.id == eid, ShowEpisode.status == 'listed', Show.status == 'listed')).first()
    if not row: jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    e, s = row
    view = ep_view(e, s)
    more = [ep_view(x, s) for x, _ in listed_episodes(db, 6, [s.id]) if x.id != e.id][:5]
    courses, jobs = related_for(db, e.title + ' ' + e.description[:600] + ' ' + s.title)
    transcript = e.transcript if (e.transcript_status == 'done' and s.claim_status == 'claimed') else ''
    return templates.TemplateResponse(request, 'index.html', {
        'page': 'podcast_episode', 'ep': view, 'show': show_view(s), 'more': more, 'related_courses': courses, 'related_jobs': jobs,
        'transcript': transcript, 'topics': TOPICS})


@router.get('/api/voices/search')
def search(q: str = '', db: Session=Depends(sessdb)):
    q = q.strip()
    if len(q) < 2: return {'episodes': [], 'shows': []}
    like = f'%{q}%'
    eps = db.execute(select(ShowEpisode, Show).join(Show, ShowEpisode.show_id == Show.id)
                     .where(Show.status == 'listed', ShowEpisode.status == 'listed',
                            or_(ShowEpisode.title.ilike(like), ShowEpisode.description.ilike(like), ShowEpisode.transcript.ilike(like)))
                     .order_by(desc(ShowEpisode.published_at)).limit(20)).all()
    out = []
    for e, s in eps:
        v = ep_view(e, s); snippet = ''
        if e.transcript and q.lower() in e.transcript.lower():
            i = e.transcript.lower().index(q.lower()); snippet = '…' + e.transcript[max(0, i-80):i+120].replace('\n', ' ') + '…'
        out.append({'id': v['id'], 'title': v['title'], 'show': v['show'], 'artwork': v['artwork'], 'date': v['date'], 'snippet': snippet})
    shows = [{'slug': s.slug, 'title': s.title, 'artwork': https_only(s.artwork_url)}
             for s in db.scalars(select(Show).where(Show.status == 'listed', or_(Show.title.ilike(like), Show.author.ilike(like))).limit(8))]
    return {'episodes': out, 'shows': shows}


def resolve_audio(url, hops=5):
    """Follow the publisher's redirect chain (their play counters still fire) and return the final media URL."""
    current_url = url
    for _ in range(hops):
        safe_public_url(current_url)
        req = urllib.request.Request(current_url, method='HEAD', headers={'User-Agent': USER_AGENT, 'Range': 'bytes=0-0'})
        try:
            with _NoRedirect.opener.open(req, timeout=15) as r: status, location = r.status, r.headers.get('Location')
        except urllib.error.HTTPError as error:
            status, location = error.code, error.headers.get('Location')
        if status in (301, 302, 303, 307, 308) and location:
            current_url = urllib.parse.urljoin(current_url, location); continue
        if status >= 400: raise ValueError(f'HTTP {status}')
        return current_url
    raise ValueError('ძალიან ბევრი გადამისამართება')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
_NoRedirect.opener = urllib.request.build_opener(_NoRedirect)


@router.get('/api/voices/episodes/{eid}/stream')
def stream_url(eid: int, db: Session=Depends(sessdb)):
    e = db.get(ShowEpisode, eid)
    if not e or e.status != 'listed': jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    try: final = resolve_audio(e.audio_url)
    except (ValueError, OSError) as error: jsonerr(502, f'აუდიო ვერ მოიძებნა: {error}')
    if not final.startswith('https://'): jsonerr(502, 'გამომცემლის ფაილი მხოლოდ http-ზეა და ამ გვერდზე ვერ დაუკრავს')
    return {'url': final}


# ---------- Publisher claims ----------

@router.post('/api/shows/{sid}/claim')
def claim_show(sid: int, u=Depends(security), db: Session=Depends(sessdb)):
    s = db.get(Show, sid)
    if not s or s.status != 'listed': jsonerr(404, 'შოუ ვერ მოიძებნა')
    m = db.scalar(select(Membership).where(Membership.user_id == u.id, Membership.role == 'owner'))
    if not m: jsonerr(403, 'შოუს დასაკუთრებლად საჭიროა ორგანიზაციის მფლობელის ანგარიში')
    if s.claim_status == 'claimed': jsonerr(409, 'ეს შოუ უკვე დადასტურებულია')
    s.claim_status, s.claim_org_id = 'requested', m.org_id
    log(db, u, m.org_id, 'claim_show', str(sid)); db.commit()
    return {'ok': True, 'status': 'requested'}


# ---------- Moderation ----------

class ShowIn(BaseModel):
    feed_url: str = Field(min_length=12, max_length=600)
    topic: str | None = None
    featured: bool = False


class ShowPatch(BaseModel):
    topic: str | None = None
    featured: bool | None = None
    status: str | None = None
    claim: str | None = None   # approve | reject


class EpisodePatch(BaseModel):
    brief_ka: str | None = Field(default=None, max_length=6000)
    key_points: str | None = Field(default=None, max_length=2000)
    chapters: list[dict] | None = None
    featured: bool | None = None
    status: str | None = None


def admin_only(u):
    if not u.admin: jsonerr(403, 'მხოლოდ მოდერატორი')


@router.get('/api/admin/shows')
def admin_shows(u=Depends(current), db: Session=Depends(sessdb)):
    admin_only(u)
    counts = dict(db.execute(select(ShowEpisode.show_id, func.count(ShowEpisode.id)).group_by(ShowEpisode.show_id)).all())
    return [{**show_view(s, counts.get(s.id, 0)), 'status': s.status, 'claim_status': s.claim_status, 'claim_org_id': s.claim_org_id,
             'last_fetched': s.last_fetched.isoformat() if s.last_fetched else None, 'fetch_error': s.fetch_error}
            for s in db.scalars(select(Show).order_by(Show.title))]


@router.post('/api/admin/shows')
def admin_add_show(d: ShowIn, u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    if d.topic and d.topic not in TOPIC_LABEL: jsonerr(422, 'უცნობი თემა')
    try:
        show, new = upsert_show(db, d.feed_url.strip(), d.topic, d.featured)
    except (ValueError, ET.ParseError, OSError) as error:
        db.rollback(); jsonerr(422, f'ფიდი ვერ წავიკითხე: {error}')
    log(db, u, None, 'add_show', str(show.id)); db.commit()
    return {'id': show.id, 'slug': show.slug, 'title': show.title, 'new_episodes': new}


@router.post('/api/admin/shows/{sid}/refresh')
def admin_refresh(sid: int, u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    s = db.get(Show, sid)
    if not s: jsonerr(404, 'შოუ ვერ მოიძებნა')
    try: _, new = upsert_show(db, s.feed_url)
    except (ValueError, ET.ParseError, OSError) as error:
        db.rollback(); s.fetch_error = str(error)[:300]; db.commit(); jsonerr(422, f'ფიდი ვერ განახლდა: {error}')
    return {'new_episodes': new}


@router.patch('/api/admin/shows/{sid}')
def admin_patch_show(sid: int, d: ShowPatch, u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    s = db.get(Show, sid)
    if not s: jsonerr(404, 'შოუ ვერ მოიძებნა')
    if d.topic is not None:
        if d.topic not in TOPIC_LABEL: jsonerr(422, 'უცნობი თემა')
        s.topic = d.topic
    if d.featured is not None: s.featured = d.featured
    if d.status is not None:
        if d.status not in ('listed', 'hidden'): jsonerr(422, 'სტატუსი: listed ან hidden')
        s.status = d.status
    if d.claim == 'approve':
        if s.claim_status != 'requested': jsonerr(409, 'მოთხოვნა არ არის')
        s.claim_status = 'claimed'
    elif d.claim == 'reject':
        s.claim_status, s.claim_org_id = 'none', None
    log(db, u, None, 'moderate_show', str(sid)); db.commit()
    return {'ok': True}


@router.patch('/api/admin/episodes/{eid}')
def admin_patch_episode(eid: int, d: EpisodePatch, u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    e = db.get(ShowEpisode, eid)
    if not e: jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    if d.chapters is not None:
        clean = []
        for c in d.chapters[:60]:
            try: clean.append({'t': max(0, int(c['t'])), 'title': str(c['title'])[:140]})
            except (KeyError, TypeError, ValueError): jsonerr(422, 'თავი: {"t": წამი, "title": "..."}')
        e.chapters = sorted(clean, key=lambda c: c['t'])
    for k in ('brief_ka', 'key_points', 'featured'):
        if getattr(d, k) is not None: setattr(e, k, getattr(d, k).strip() if isinstance(getattr(d, k), str) else getattr(d, k))
    if d.status is not None:
        if d.status not in ('listed', 'hidden'): jsonerr(422, 'სტატუსი: listed ან hidden')
        e.status = d.status
    log(db, u, None, 'edit_episode', str(eid)); db.commit()
    return {'ok': True}


@router.post('/api/admin/episodes/{eid}/transcribe')
def admin_transcribe(eid: int, u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    e = db.get(ShowEpisode, eid)
    if not e: jsonerr(404, 'ეპიზოდი ვერ მოიძებნა')
    if e.transcript_status == 'done': return {'status': 'done'}
    e.transcript_status = 'queued'; log(db, u, None, 'queue_transcript', str(eid)); db.commit()
    return {'status': 'queued', 'note': 'ტრანსკრიფცია ხდება ფონურ პროცესში (python -m features.voices_cli transcribe)'}


@router.post('/api/admin/shows/import-starter')
def admin_import_starter(u=Depends(security), db: Session=Depends(sessdb)):
    admin_only(u)
    return {'results': import_starter(db)}


def import_starter(db):
    from features.voices_starter import STARTER
    out = []
    for item in STARTER:
        try:
            show, new = upsert_show(db, item['feed'], item.get('topic'), item.get('featured'), item.get('apple_id', ''))
            out.append({'title': show.title, 'new': new})
        except Exception as error:
            db.rollback(); out.append({'feed': item['feed'], 'error': f'{type(error).__name__}: {error}'[:200]})
    return out


# ---------- Transcription worker (ElevenLabs Scribe v2; Georgian is a high-accuracy language) ----------

def transcribe_one(db):
    key = os.getenv('ELEVENLABS_API_KEY')
    e = db.scalar(select(ShowEpisode).where(ShowEpisode.transcript_status == 'queued').order_by(ShowEpisode.id))
    if not e: return None
    if not key: raise RuntimeError('ELEVENLABS_API_KEY is not set')
    try:
        audio = fetch(e.audio_url, max_bytes=int(os.getenv('MAX_AUDIO_BYTES', str(250*1024*1024))), timeout=120)
        boundary = '----sivrce' + os.urandom(8).hex()
        body = b''.join([
            f'--{boundary}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\nscribe_v2\r\n'.encode(),
            f'--{boundary}\r\nContent-Disposition: form-data; name="language_code"\r\n\r\nkat\r\n'.encode(),
            f'--{boundary}\r\nContent-Disposition: form-data; name="diarize"\r\n\r\ntrue\r\n'.encode(),
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="episode.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
            audio, f'\r\n--{boundary}--\r\n'.encode()])
        req = urllib.request.Request('https://api.elevenlabs.io/v1/speech-to-text', data=body, method='POST',
                                     headers={'xi-api-key': key, 'Content-Type': f'multipart/form-data; boundary={boundary}'})
        with urllib.request.urlopen(req, timeout=900) as r: result = json.load(r)
        e.transcript = (result.get('text') or '').strip()[:400000]
        e.transcript_status = 'done' if e.transcript else 'failed'
    except Exception as error:
        e.transcript_status = 'failed'; e.transcript = f'[{type(error).__name__}] {str(error)[:200]}'
    db.commit()
    return e


def main(argv):
    from server import Local
    cmd = argv[1] if len(argv) > 1 else ''
    with Local() as db:
        if cmd == 'seed':
            for r in import_starter(db): print(r)
        elif cmd == 'refresh':
            for title, new in refresh_all(db, int(argv[2]) if len(argv) > 2 else 50): print(f'{title}: {new}')
        elif cmd == 'transcribe':
            while (e := transcribe_one(db)): print(f'#{e.id} {e.transcript_status}')
        else:
            print('usage: python -m features.voices_cli seed | refresh [max_age_minutes] | transcribe'); return 2
    return 0

