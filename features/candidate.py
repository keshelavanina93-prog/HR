"""Candidate's personal space: applications as journeys, not rows."""
import datetime as dt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from server import (Application, Cohort, Course, CourseInterest, Interview, Job, Membership, Organization, SavedJob,
                    current, job_dict, sessdb, templates)
from features.models import ApplicationEvent, CandidateProfile, Notification
from features.showcase import OrgStory, accent_map

router = APIRouter()
STAGES = [('received', 'მიღებული'), ('reviewing', 'განხილვა'), ('interview', 'გასაუბრება'), ('offer', 'შეთავაზება'), ('hired', 'დაქირავება')]
LABELS = dict(STAGES) | {'rejected': 'დასრულდა'}
NOW_TEXT = {
    'received': 'განაცხადი მიღებულია. კომპანიას ეტაპი ჯერ არ შეუცვლია.',
    'reviewing': 'კომპანია განიხილავს შენს განაცხადს.',
    'interview': 'გასაუბრების ეტაპი. დრო და ადგილი ქვემოთ ჩანს.',
    'offer': 'კომპანიამ შეთავაზება გამოგიგზავნა. დეტალები შეტყობინებებში და ელფოსტაზე.',
    'hired': 'გილოცავ — შერჩევა დასრულდა და დაქირავებული ხარ.',
    'rejected': 'კომპანიამ ამ ეტაპზე სხვა კანდიდატი აირჩია. განაცხადი დახურულია.',
}


def stage_index(status, events):
    keys = [k for k, _ in STAGES]
    if status in keys: return keys.index(status)
    # Rejected: show how far the application got before it closed.
    reached = [keys.index(e.previous) for e in events if e.status == 'rejected' and e.previous in keys]
    return reached[-1] if reached else 0


def profile_view(p):
    fields = {'headline': p.headline if p else '', 'location': p.location if p else '',
              'skills': p.skills if p else '', 'experience': p.experience if p else ''}
    checks = [('headline', 'პროფესიული სათაური', len(fields['headline']) >= 6),
              ('location', 'ადგილმდებარეობა', len(fields['location']) >= 2),
              ('skills', 'უნარები', len([s for s in fields['skills'].replace('\n', ',').split(',') if s.strip()]) >= 3),
              ('experience', 'გამოცდილება', len(fields['experience']) >= 80)]
    return {'fields': fields, 'checks': [{'key': k, 'label': l, 'done': d} for k, l, d in checks],
            'score': sum(d for *_, d in checks), 'total': len(checks)}


@router.get('/api/me/overview')
def overview(u=Depends(current), db: Session=Depends(sessdb)):
    apps = db.scalars(select(Application).where(Application.user_id == u.id).order_by(Application.created.desc())).all()
    jobs = {a.job_id: db.get(Job, a.job_id) for a in apps}
    accents = accent_map(db, list({j.org_id for j in jobs.values()}))
    promises = dict(db.execute(select(OrgStory.org_id, OrgStory.hiring_promise).where(OrgStory.org_id.in_(list(accents) or [0]))).all())
    today = dt.date.today()
    out = []
    for a in apps:
        j = jobs[a.job_id]; org = db.get(Organization, j.org_id)
        events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == a.id).order_by(ApplicationEvent.id)).all()
        meetings = db.scalars(select(Interview).where(Interview.application_id == a.id).order_by(Interview.scheduled_for)).all()
        last = events[-1].created if events else a.created
        out.append({
            'id': a.id, 'job_id': j.id, 'title': j.title, 'company': org.name, 'slug': org.slug, 'accent': accents[org.id],
            'status': a.status, 'status_label': LABELS.get(a.status, a.status), 'now': NOW_TEXT.get(a.status, ''),
            'closed': a.status in ('rejected', 'hired'), 'stage': stage_index(a.status, events),
            'stages': [l for _, l in STAGES], 'created': a.created.date().isoformat(),
            'days_since_update': (today - last.date()).days, 'promise': promises.get(org.id, ''),
            'events': [{'label': LABELS.get(e.status, e.status), 'date': e.created.date().isoformat()} for e in events],
            'interviews': [{'id': m.id, 'when': m.scheduled_for.isoformat(timespec='minutes'), 'format': m.format,
                            'where': m.location_or_link, 'note': m.candidate_note, 'upcoming': m.scheduled_for >= dt.datetime.now(),
                            'ics': f'/api/interviews/{m.id}/calendar'} for m in meetings],
            'cv_url': f'/api/applications/{a.id}/cv' if a.cv_key else None,
        })
    saved_rows = db.scalars(select(SavedJob).where(SavedJob.user_id == u.id).order_by(SavedJob.created.desc())).all()
    saved = [job_dict(db, j) for r in saved_rows if (j := db.get(Job, r.job_id)) and j.status == 'published']
    saved_accents = accent_map(db, [s['org_id'] for s in saved])
    for s in saved: s['accent'] = saved_accents[s['org_id']]; s['open'] = s['deadline'] >= today.isoformat()
    interests = [{'id': r.id, 'course_id': c.id, 'title': c.title, 'starts': co.starts, 'status': r.status}
                 for r, c, co in db.execute(select(CourseInterest, Course, Cohort).join(Cohort, CourseInterest.cohort_id == Cohort.id)
                                            .join(Course, Cohort.course_id == Course.id).where(CourseInterest.user_id == u.id)).all()]
    upcoming = sorted((dict(i, title=a['title'], company=a['company']) for a in out for i in a['interviews'] if i['upcoming']), key=lambda i: i['when'])
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == u.id, Notification.read_at.is_(None)))
    notes = [{'title': n.title, 'body': n.body, 'href': n.href, 'read': bool(n.read_at), 'created': n.created.date().isoformat()}
             for n in db.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(5))]
    return {'user': {'name': u.name, 'email': u.email},
            'has_organization': bool(db.scalar(select(Membership.id).where(Membership.user_id == u.id).limit(1))),
            'counts': {'active': sum(not a['closed'] for a in out), 'interviews': len(upcoming), 'saved': len(saved)},
            'next_interview': upcoming[0] if upcoming else None,
            'applications': out, 'saved': saved, 'interests': interests,
            'profile': profile_view(db.get(CandidateProfile, u.id)), 'unread': unread, 'notifications': notes}


@router.get('/me', response_class=HTMLResponse)
def me_page(request: Request):
    return templates.TemplateResponse(request, 'me.html', {})
