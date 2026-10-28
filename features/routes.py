"""Organization-scoped application workflows. Every mutation requires CSRF."""
import datetime as dt
import os
import re
import secrets
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func, delete
from sqlalchemy.orm import Session
from server import (app, templates, sessdb, security, current, member, jsonerr, log, PW,
                    User, Membership, Organization, Job, JobIn, Application, AuthSession,
                    Brief, Proposal, EditorialArticle, Course, Interview, Audit, GoogleIdentity)
from features.models import (JobDraft, ApplicantNote, ApplicationEvent, Notification,
    MailMessage, ActionToken, IdentityState, TeamInvite, CandidateProfile, ConsentEvent,
    BriefAccess, ProposalRevision, BriefQuestion, TrainingEvaluation, SupportRequest, utcnow)
from features.services import digest, verified, issue_token, queue_mail, notify

router = APIRouter()


class DraftIn(BaseModel):
    org_id: int
    payload: dict
    revision: int = Field(default=1, ge=1)


def validate_draft(payload):
    allowed = set(JobIn.model_fields) - {'org_id', 'publish'}
    if set(payload) - allowed or len(str(payload)) > 18000:
        jsonerr(422, 'დრაფტის ველები არასწორია ან ტექსტი ზედმეტად დიდია')
    if any(not isinstance(v, (str, int, float)) or isinstance(v, bool) for v in payload.values()):
        jsonerr(422, 'დრაფტში გამოიყენე მხოლოდ ტექსტი და რიცხვები')


@router.get('/api/organizations/{oid}/drafts')
def drafts(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid, 'company', 'hire_read')
    return [{'id': d.id, 'payload': d.payload, 'revision': d.revision, 'job_id': d.job_id,
             'updated': d.updated.isoformat()} for d in db.scalars(select(JobDraft).where(JobDraft.org_id == oid).order_by(JobDraft.updated.desc()))]


@router.post('/api/job-drafts')
def create_draft(d: DraftIn, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, d.org_id, 'company', 'hire_write'); validate_draft(d.payload)
    draft = JobDraft(org_id=d.org_id, payload=d.payload)
    db.add(draft); db.flush(); log(db, u, d.org_id, 'create_job_draft', str(draft.id)); db.commit()
    return {'id': draft.id, 'revision': draft.revision}


@router.put('/api/job-drafts/{did}')
def save_draft(did: int, d: DraftIn, u=Depends(security), db: Session=Depends(sessdb)):
    draft = db.get(JobDraft, did)
    if not draft: jsonerr(404, 'დრაფტი ვერ მოიძებნა')
    member(db, u, draft.org_id, 'company', 'hire_write')
    if d.org_id != draft.org_id: jsonerr(403, 'ორგანიზაციის შეცვლა დაუშვებელია')
    if draft.job_id: jsonerr(409, 'გაგზავნილი დრაფტის შეცვლა შეუძლებელია')
    validate_draft(d.payload)
    changed = db.execute(update(JobDraft).where(JobDraft.id == did, JobDraft.revision == d.revision, JobDraft.job_id.is_(None))
        .values(payload=d.payload, revision=d.revision + 1, updated=utcnow()))
    if changed.rowcount != 1: jsonerr(409, 'დრაფტი სხვაგან შეიცვალა. განაახლე გვერდი და შეადარე ცვლილებები.')
    log(db, u, draft.org_id, 'update_job_draft', str(did)); db.commit()
    return {'id': did, 'revision': d.revision + 1}


class RevisionIn(BaseModel):
    revision: int = Field(ge=1)


@router.post('/api/job-drafts/{did}/submit')
def submit_draft(did: int, d: RevisionIn, u=Depends(security), db: Session=Depends(sessdb)):
    draft = db.scalar(select(JobDraft).where(JobDraft.id == did).with_for_update())
    if not draft: jsonerr(404, 'დრაფტი ვერ მოიძებნა')
    org = member(db, u, draft.org_id, 'company', 'hire_write')
    if draft.job_id: return {'id': draft.job_id, 'status': db.get(Job, draft.job_id).status}
    if draft.revision != d.revision: jsonerr(409, 'დრაფტი შეიცვალა. განაახლე გვერდი.')
    if not org.verified: jsonerr(403, 'ჯერ საჭიროა ორგანიზაციის გადამოწმება')
    try: data = JobIn.model_validate({**draft.payload, 'org_id': org.id, 'publish': True})
    except ValueError: jsonerr(422, 'დრაფტს აკლია სავალდებულო ველები ან მოქმედი ვადა')
    job = Job(**data.model_dump(exclude={'publish'}), status='pending_review')
    db.add(job); db.flush(); draft.job_id = job.id; draft.revision += 1
    log(db, u, org.id, 'submit_job_draft', str(job.id)); db.commit()
    return {'id': job.id, 'status': job.status}


class NoteIn(BaseModel):
    body: str = Field(min_length=5, max_length=4000)
    rating: int | None = Field(default=None, ge=1, le=5)
    criterion: str = Field(default='', max_length=100)


def employer_application(db, u, aid, write=False):
    a = db.get(Application, aid)
    if not a: jsonerr(404, 'განაცხადი ვერ მოიძებნა')
    job = db.get(Job, a.job_id)
    member(db, u, job.org_id, 'company', 'hire_write' if write else 'hire_read')
    return a, job


@router.get('/api/applications/{aid}/review')
def application_review(aid: int, u=Depends(current), db: Session=Depends(sessdb)):
    a, job = employer_application(db, u, aid)
    notes = db.scalars(select(ApplicantNote).where(ApplicantNote.application_id == aid).order_by(ApplicantNote.id)).all()
    events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == aid).order_by(ApplicationEvent.id)).all()
    log(db, u, job.org_id, 'read_application_review', str(aid)); db.commit()
    return {'notes': [{'id': n.id, 'author': db.get(User, n.author_id).name, 'body': n.body, 'rating': n.rating,
                       'criterion': n.criterion, 'created': n.created.isoformat()} for n in notes],
            'history': [{'previous': e.previous, 'status': e.status, 'created': e.created.isoformat()} for e in events]}


@router.post('/api/applications/{aid}/notes')
def add_note(aid: int, d: NoteIn, u=Depends(security), db: Session=Depends(sessdb)):
    a, job = employer_application(db, u, aid, True)
    if d.rating and not d.criterion.strip(): jsonerr(422, 'შეფასებას სჭირდება კონკრეტული კრიტერიუმი')
    n = ApplicantNote(application_id=aid, author_id=u.id, **d.model_dump()); db.add(n); db.flush()
    log(db, u, job.org_id, 'add_application_note', str(n.id)); db.commit()
    return {'id': n.id}


class InviteIn(BaseModel):
    email: str = Field(max_length=180)
    role: str


@router.get('/api/organizations/{oid}/team')
def team(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid, permission='team')
    rows = db.execute(select(Membership, User).join(User, Membership.user_id == User.id).where(Membership.org_id == oid)).all()
    invites = db.scalars(select(TeamInvite).where(TeamInvite.org_id == oid, TeamInvite.accepted_at.is_(None), TeamInvite.revoked_at.is_(None), TeamInvite.expires > utcnow())).all()
    return {'members': [{'id': m.id, 'name': usr.name, 'email': usr.email, 'role': m.role} for m, usr in rows],
            'invites': [{'id': i.id, 'email': i.email, 'role': i.role, 'expires': i.expires.isoformat()} for i in invites]}


@router.post('/api/organizations/{oid}/invites')
def invite(oid: int, d: InviteIn, u=Depends(security), db: Session=Depends(sessdb)):
    org = member(db, u, oid, permission='team')
    roles = {'recruiter', 'hiring_manager', 'procurement'} if org.kind == 'company' else {'provider_editor'}
    email = d.email.strip().lower()
    if d.role not in roles or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email): jsonerr(422, 'შეამოწმე ელფოსტა და როლი')
    if email == u.email: jsonerr(409, 'ეს ანგარიში უკვე ორგანიზაციის წევრია')
    for old in db.scalars(select(TeamInvite).where(TeamInvite.org_id == oid, TeamInvite.email == email, TeamInvite.accepted_at.is_(None))): old.revoked_at = utcnow()
    raw = secrets.token_urlsafe(40)
    record = TeamInvite(org_id=oid, email=email, role=d.role, token_hash=digest(raw), invited_by=u.id, expires=utcnow()+dt.timedelta(days=3))
    db.add(record); db.flush()
    base = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    queue_mail(db, email, 'SIVRCE — ორგანიზაციაში მოწვევა', f'{org.name}\n{base}/account#invite={raw}\nმოწვევის მისაღებად შედი ამ ელფოსტით და დაადასტურე ელფოსტა. ბმული მოქმედებს 3 დღე.')
    log(db, u, oid, 'invite_member', str(record.id)); db.commit()
    return {'id': record.id, 'email_status': 'queued'}


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


@router.post('/api/team/accept')
def accept_invite(d: TokenIn, u=Depends(security), db: Session=Depends(sessdb)):
    invite = db.scalar(select(TeamInvite).where(TeamInvite.token_hash == digest(d.token)).with_for_update())
    if not invite or invite.accepted_at or invite.revoked_at or invite.expires <= utcnow(): jsonerr(410, 'მოწვევა აღარ მოქმედებს')
    if invite.email != u.email or not verified(db, u): jsonerr(403, 'მოწვევის მისაღებად საჭიროა მითითებული ელფოსტის დადასტურება')
    if db.scalar(select(Membership).where(Membership.org_id == invite.org_id, Membership.user_id == u.id)): jsonerr(409, 'უკვე ხარ ორგანიზაციის წევრი')
    db.add(Membership(org_id=invite.org_id, user_id=u.id, role=invite.role)); invite.accepted_at = utcnow()
    log(db, u, invite.org_id, 'accept_invite', str(invite.id)); db.commit()
    return {'org_id': invite.org_id}


@router.delete('/api/organizations/{oid}/invites/{iid}')
def revoke_invite(oid: int, iid: int, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, oid, permission='team'); record = db.get(TeamInvite, iid)
    if not record or record.org_id != oid: jsonerr(404, 'მოწვევა ვერ მოიძებნა')
    record.revoked_at = utcnow(); log(db, u, oid, 'revoke_invite', str(iid)); db.commit(); return {'ok': True}


@router.delete('/api/organizations/{oid}/members/{mid}')
def remove_member(oid: int, mid: int, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, oid, permission='team'); record = db.get(Membership, mid)
    if not record or record.org_id != oid: jsonerr(404, 'წევრი ვერ მოიძებნა')
    if record.role == 'owner': jsonerr(409, 'მფლობელის წაშლა შეუძლებელია')
    db.delete(record); log(db, u, oid, 'remove_member', str(mid)); db.commit(); return {'ok': True}


class RoleIn(BaseModel):
    role: str


@router.patch('/api/organizations/{oid}/members/{mid}')
def change_role(oid: int, mid: int, d: RoleIn, u=Depends(security), db: Session=Depends(sessdb)):
    org = member(db, u, oid, permission='team')
    record = db.get(Membership, mid)
    if not record or record.org_id != oid: jsonerr(404, 'წევრი ვერ მოიძებნა')
    if record.role == 'owner': jsonerr(409, 'მფლობელის როლის შეცვლა შეუძლებელია')
    roles = {'recruiter', 'hiring_manager', 'procurement'} if org.kind == 'company' else {'provider_editor'}
    if d.role not in roles: jsonerr(422, 'როლი არასწორია')
    record.role = d.role; log(db, u, oid, 'change_member_role', str(mid)); db.commit()
    return {'role': record.role}


@router.get('/api/organizations/{oid}/settings')
def organization_settings(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    org = member(db, u, oid, permission='org_write')
    return {k: getattr(org, k) for k in ('name', 'description', 'location', 'website', 'registration_code', 'verified', 'verification_requested')}


class OrganizationEditIn(BaseModel):
    name: str = Field(min_length=3, max_length=130)
    description: str = Field(min_length=0, max_length=1500)
    location: str = Field(min_length=2, max_length=150)
    website: str = Field(default='', max_length=220)
    registration_code: str = Field(default='', max_length=30)


@router.put('/api/organizations/{oid}/settings')
def edit_organization(oid: int, d: OrganizationEditIn, u=Depends(security), db: Session=Depends(sessdb)):
    org = member(db, u, oid, permission='org_write')
    if d.website and not d.website.startswith(('https://', 'http://')): jsonerr(422, 'მიუთითე ვებსაიტის სრული ბმული')
    if any(getattr(org, k) != getattr(d, k) for k in ('name', 'website', 'registration_code')):
        org.verified = False; org.verification_requested = False
    for k, v in d.model_dump().items(): setattr(org, k, v.strip())
    log(db, u, oid, 'edit_organization', str(oid)); db.commit()
    return {'verified': org.verified}


class EmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=180)


@router.post('/api/auth/recovery')
def recovery(d: EmailIn, db: Session=Depends(sessdb)):
    user = db.scalar(select(User).where(User.email == d.email.strip().lower()))
    if user: issue_token(db, user, 'reset'); db.commit()
    return {'message': 'თუ ანგარიში არსებობს, ინსტრუქცია გაიგზავნება შენს ელფოსტაზე.'}


class ResetIn(TokenIn):
    password: str = Field(min_length=10, max_length=128)


def use_token(db, raw, purpose):
    token = db.scalar(select(ActionToken).where(ActionToken.token_hash == digest(raw), ActionToken.purpose == purpose).with_for_update())
    if not token or token.used_at or token.expires <= utcnow(): jsonerr(410, 'ბმული აღარ მოქმედებს')
    token.used_at = utcnow()
    return token


@router.post('/api/auth/reset')
def reset_password(d: ResetIn, db: Session=Depends(sessdb)):
    token = use_token(db, d.token, 'reset'); user = db.get(User, token.user_id)
    user.pw_hash = PW.hash(d.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    log(db, user, None, 'reset_password', str(user.id)); db.commit(); return {'ok': True}


@router.post('/api/auth/verification')
def request_verification(u=Depends(security), db: Session=Depends(sessdb)):
    if not verified(db, u): issue_token(db, u, 'verify'); db.commit()
    return {'email_status': 'queued' if not verified(db, u) else 'verified'}


@router.post('/api/auth/verify')
def verify_email(d: TokenIn, db: Session=Depends(sessdb)):
    token = use_token(db, d.token, 'verify')
    identity = db.get(IdentityState, token.user_id)
    if not identity: identity = IdentityState(user_id=token.user_id); db.add(identity)
    identity.verified_at = utcnow(); db.commit(); return {'ok': True}


class ProfileIn(BaseModel):
    headline: str = Field(default='', max_length=160)
    location: str = Field(default='', max_length=160)
    skills: str = Field(default='', max_length=3000)
    experience: str = Field(default='', max_length=8000)


@router.get('/api/profile')
def profile(u=Depends(current), db: Session=Depends(sessdb)):
    p = db.get(CandidateProfile, u.id)
    return {k: getattr(p, k, '') for k in ProfileIn.model_fields}


@router.put('/api/profile')
def save_profile(d: ProfileIn, u=Depends(security), db: Session=Depends(sessdb)):
    p = db.get(CandidateProfile, u.id)
    if not p: p = CandidateProfile(user_id=u.id); db.add(p)
    for key, value in d.model_dump().items(): setattr(p, key, value.strip())
    p.updated = utcnow(); db.commit(); return {'ok': True}


@router.delete('/api/profile')
def delete_profile(u=Depends(security), db: Session=Depends(sessdb)):
    db.execute(delete(CandidateProfile).where(CandidateProfile.user_id == u.id)); log(db, u, None, 'delete_profile', str(u.id)); db.commit()
    return {'ok': True}


@router.get('/api/account/export')
def export_account(u=Depends(current), db: Session=Depends(sessdb)):
    from server import my_applications, my_course_interests
    return {'user': {'name': u.name, 'email': u.email}, 'profile': profile(u, db),
            'applications': my_applications(u, db), 'course_interests': my_course_interests(u, db),
            'consent': [{'purpose': c.purpose, 'version': c.version, 'granted': c.granted, 'created': c.created.isoformat()}
                       for c in db.scalars(select(ConsentEvent).where(ConsentEvent.user_id == u.id))]}


@router.get('/api/notifications')
def notifications(u=Depends(current), db: Session=Depends(sessdb)):
    return [{'id': n.id, 'title': n.title, 'body': n.body, 'href': n.href, 'read': bool(n.read_at), 'created': n.created.isoformat()}
            for n in db.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(100))]


@router.post('/api/notifications/{nid}/read')
def read_notification(nid: int, u=Depends(security), db: Session=Depends(sessdb)):
    n = db.get(Notification, nid)
    if not n or n.user_id != u.id: jsonerr(404, 'შეტყობინება ვერ მოიძებნა')
    n.read_at = utcnow(); db.commit(); return {'ok': True}


@router.get('/api/organizations/{oid}/activity')
def activity(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid)
    # Audit targets contain identifiers, never applicant notes or credentials.
    return [{'id': a.id, 'action': a.action, 'target': a.target, 'created': a.created.isoformat()}
            for a in db.scalars(select(Audit).where(Audit.org_id == oid).order_by(Audit.id.desc()).limit(100))]


@router.get('/api/organizations/{oid}/analytics')
def analytics(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid, 'company', 'hire_read')
    counts = db.execute(select(Application.status, func.count(Application.id)).join(Job, Application.job_id == Job.id).where(Job.org_id == oid).group_by(Application.status)).all()
    stages = dict(counts); total = sum(stages.values())
    return {'applications': total, 'stages': stages, 'hired': stages.get('hired', 0),
            'hire_rate': stages.get('hired', 0) / total if total else None,
            'basis': 'მიმდინარე შენახული განაცხადები; გამოთხოვილი განაცხადები გამორიცხულია', 'roi': None}


class BriefInviteIn(BaseModel):
    provider_id: int


def buyer_brief(db, u, bid, write=False):
    b = db.get(Brief, bid)
    if not b: jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    member(db, u, b.org_id, 'company', 'develop_write' if write else 'develop_read')
    return b


@router.post('/api/briefs/{bid}/publish')
def publish_brief(bid: int, u=Depends(security), db: Session=Depends(sessdb)):
    b = buyer_brief(db, u, bid, True)
    if not db.get(Organization, b.org_id).verified: jsonerr(403, 'ორგანიზაცია გადამოწმებული უნდა იყოს')
    if b.status not in ('draft', 'published') or b.deadline < dt.date.today().isoformat(): jsonerr(409, 'მოთხოვნის გამოქვეყნება შეუძლებელია')
    b.status = 'published'; log(db, u, b.org_id, 'publish_brief', str(bid)); db.commit(); return {'status': b.status}


@router.post('/api/briefs/{bid}/invites')
def invite_provider(bid: int, d: BriefInviteIn, u=Depends(security), db: Session=Depends(sessdb)):
    b = buyer_brief(db, u, bid, True); provider = db.get(Organization, d.provider_id)
    if not provider or provider.kind != 'provider' or not provider.verified: jsonerr(422, 'აირჩიე გადამოწმებული მომწოდებელი')
    if not db.scalar(select(BriefAccess).where(BriefAccess.brief_id == bid, BriefAccess.provider_id == provider.id)):
        db.add(BriefAccess(brief_id=bid, provider_id=provider.id))
        for m in db.scalars(select(Membership).where(Membership.org_id == provider.id)):
            notify(db, db.get(User, m.user_id), 'ტრენინგის მოთხოვნაზე მოწვევა', b.title, '/workspace')
    log(db, u, b.org_id, 'invite_provider', str(bid)); db.commit(); return {'ok': True}


def provider_can_read(db, provider_id, b):
    return b and b.status == 'published' and (b.visibility == 'public' or bool(db.scalar(select(BriefAccess.id).where(BriefAccess.brief_id == b.id, BriefAccess.provider_id == provider_id))))


@router.get('/api/organizations/{oid}/opportunities')
def provider_opportunities(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid, 'provider', 'develop_read')
    return [{'id': b.id, 'title': b.title, 'goal': b.goal, 'budget': b.budget, 'audience': b.audience, 'deadline': b.deadline, 'visibility': b.visibility}
            for b in db.scalars(select(Brief).where(Brief.status == 'published', Brief.deadline >= dt.date.today().isoformat())) if provider_can_read(db, oid, b)]


class ProposalEditIn(BaseModel):
    version: int = Field(ge=1)
    price: int = Field(gt=0)
    approach: str = Field(min_length=50, max_length=8000)
    trainer: str = Field(min_length=3, max_length=150)
    days: int = Field(gt=0, le=365)


@router.put('/api/proposals/{pid}')
def revise_proposal(pid: int, d: ProposalEditIn, u=Depends(security), db: Session=Depends(sessdb)):
    p = db.scalar(select(Proposal).where(Proposal.id == pid).with_for_update())
    if not p: jsonerr(404, 'შეთავაზება ვერ მოიძებნა')
    member(db, u, p.org_id, 'provider', 'develop_write')
    b = db.get(Brief, p.brief_id)
    if b.status != 'published' or p.status != 'submitted' or b.deadline < dt.date.today().isoformat(): jsonerr(409, 'შეთავაზების ცვლილება აღარ შეიძლება')
    latest = db.scalar(select(func.max(ProposalRevision.version)).where(ProposalRevision.proposal_id == pid)) or 1
    if latest != d.version: jsonerr(409, 'შეთავაზება შეიცვალა. განაახლე გვერდი.')
    if latest == 1 and not db.scalar(select(ProposalRevision.id).where(ProposalRevision.proposal_id == pid)):
        db.add(ProposalRevision(proposal_id=pid, version=1, actor_id=u.id, snapshot={k: getattr(p, k) for k in ('price', 'approach', 'trainer', 'days')}))
    for k, v in d.model_dump(exclude={'version'}).items(): setattr(p, k, v)
    db.add(ProposalRevision(proposal_id=pid, version=latest+1, actor_id=u.id, snapshot=d.model_dump(exclude={'version'})))
    log(db, u, p.org_id, 'revise_proposal', str(pid)); db.commit(); return {'version': latest+1}


@router.get('/api/proposals/{pid}/history')
def proposal_history(pid: int, u=Depends(current), db: Session=Depends(sessdb)):
    p = db.get(Proposal, pid)
    if not p: jsonerr(404, 'შეთავაზება ვერ მოიძებნა')
    b = db.get(Brief, p.brief_id)
    if db.scalar(select(Membership).where(Membership.org_id == p.org_id, Membership.user_id == u.id)):
        member(db, u, p.org_id, 'provider', 'develop_read')
    else: buyer_brief(db, u, b.id)
    return [{'version': r.version, 'snapshot': r.snapshot, 'created': r.created.isoformat()}
            for r in db.scalars(select(ProposalRevision).where(ProposalRevision.proposal_id == pid).order_by(ProposalRevision.version))]


class EvaluationIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    outcomes: str = Field(min_length=30, max_length=5000)


@router.post('/api/briefs/{bid}/complete')
def complete_training(bid: int, d: EvaluationIn, u=Depends(security), db: Session=Depends(sessdb)):
    b = buyer_brief(db, u, bid, True)
    if b.status != 'awarded': jsonerr(409, 'ჯერ შეარჩიე მომწოდებელი')
    db.add(TrainingEvaluation(brief_id=bid, author_id=u.id, **d.model_dump())); b.status = 'completed'
    log(db, u, b.org_id, 'complete_training', str(bid)); db.commit(); return {'status': 'completed'}


class SupportIn(BaseModel):
    category: str = Field(pattern='^(support|deletion|privacy)$')
    message: str = Field(min_length=10, max_length=5000)


@router.post('/api/support')
def support(d: SupportIn, u=Depends(security), db: Session=Depends(sessdb)):
    r = SupportRequest(user_id=u.id, **d.model_dump()); db.add(r); db.flush(); db.commit()
    return {'id': r.id, 'status': r.status}


@router.get('/api/support')
def my_support(u=Depends(current), db: Session=Depends(sessdb)):
    return [{'id': r.id, 'category': r.category, 'message': r.message, 'status': r.status, 'created': r.created.isoformat()}
            for r in db.scalars(select(SupportRequest).where(SupportRequest.user_id == u.id).order_by(SupportRequest.id.desc()))]


@router.get('/api/capabilities')
def capabilities():
    return {'google': bool(os.getenv('GOOGLE_CLIENT_ID')), 'email': bool(os.getenv('SMTP_HOST')),
            'billing': False, 'voice_translation': False, 'automated_candidate_decisions': False}


class ConsentIn(BaseModel):
    purpose: str = Field(pattern='^(profile_processing|product_updates)$')
    granted: bool


@router.post('/api/consent')
def set_consent(d: ConsentIn, u=Depends(security), db: Session=Depends(sessdb)):
    db.add(ConsentEvent(user_id=u.id, purpose=d.purpose, version='2026-10-28', granted=d.granted)); db.commit()
    return {'ok': True}


@router.get('/api/organizations/{oid}/catalog')
def provider_catalog(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    from server import CourseIn, Cohort
    member(db, u, oid, 'provider', 'catalog_read')
    return [{**{k: getattr(c, k) for k in CourseIn.model_fields if k != 'publish'}, 'id': c.id, 'status': c.status,
             'cohorts': [{'id': co.id, 'starts': co.starts, 'location': co.location, 'capacity': co.capacity, 'active': co.active}
                         for co in db.scalars(select(Cohort).where(Cohort.course_id == c.id))]}
            for c in db.scalars(select(Course).where(Course.org_id == oid).order_by(Course.id.desc()))]


from server import CourseIn


@router.put('/api/courses/{cid}')
def edit_course(cid: int, d: CourseIn, u=Depends(security), db: Session=Depends(sessdb)):
    c = db.get(Course, cid)
    if not c: jsonerr(404, 'კურსი ვერ მოიძებნა')
    org = member(db, u, c.org_id, 'provider', 'catalog_write')
    if d.org_id != c.org_id: jsonerr(403, 'ორგანიზაციის შეცვლა შეუძლებელია')
    if d.publish and not org.verified: jsonerr(403, 'მომწოდებლის გადამოწმება აუცილებელია')
    for k, v in d.model_dump(exclude={'publish', 'org_id'}).items(): setattr(c, k, v)
    c.status = 'pending_review' if d.publish else 'draft'
    log(db, u, c.org_id, 'edit_course', str(cid)); db.commit(); return {'id': cid, 'status': c.status}


class QuestionIn(BaseModel):
    provider_id: int
    question: str = Field(min_length=10, max_length=3000)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=5, max_length=3000)


@router.post('/api/briefs/{bid}/questions')
def ask_question(bid: int, d: QuestionIn, u=Depends(security), db: Session=Depends(sessdb)):
    member(db, u, d.provider_id, 'provider', 'develop_write'); b = db.get(Brief, bid)
    if not provider_can_read(db, d.provider_id, b): jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    if b.deadline < dt.date.today().isoformat(): jsonerr(410, 'შეკითხვების ვადა გასულია')
    q = BriefQuestion(brief_id=bid, provider_id=d.provider_id, question=d.question); db.add(q); db.flush()
    log(db, u, d.provider_id, 'ask_brief_question', str(q.id)); db.commit(); return {'id': q.id}


@router.get('/api/briefs/{bid}/questions')
def brief_questions(bid: int, u=Depends(current), db: Session=Depends(sessdb)):
    b = db.get(Brief, bid)
    if not b: jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    owned = db.scalar(select(Membership).where(Membership.org_id == b.org_id, Membership.user_id == u.id))
    query = select(BriefQuestion).where(BriefQuestion.brief_id == bid)
    if owned: member(db, u, b.org_id, 'company', 'develop_read')
    else:
        memberships = db.scalars(select(Membership).where(Membership.user_id == u.id)).all()
        permitted = []
        for m in memberships:
            from features.services import ROLE_PERMISSIONS
            if 'develop_read' in ROLE_PERMISSIONS.get(m.role, set()) and db.get(Organization, m.org_id).kind == 'provider': permitted.append(m.org_id)
        if not permitted: jsonerr(403, 'წვდომა აკრძალულია')
        query = query.where(BriefQuestion.provider_id.in_(permitted))
    return [{'id': q.id, 'question': q.question, 'answer': q.answer, 'provider': db.get(Organization, q.provider_id).name}
            for q in db.scalars(query.order_by(BriefQuestion.id))]


@router.post('/api/questions/{qid}/answer')
def answer_question(qid: int, d: AnswerIn, u=Depends(security), db: Session=Depends(sessdb)):
    q = db.scalar(select(BriefQuestion).where(BriefQuestion.id == qid).with_for_update())
    if not q: jsonerr(404, 'შეკითხვა ვერ მოიძებნა')
    b = buyer_brief(db, u, q.brief_id, True)
    if q.answer: jsonerr(409, 'პასუხი უკვე დაფიქსირებულია')
    q.answer = d.answer
    for m in db.scalars(select(Membership).where(Membership.org_id == q.provider_id)):
        notify(db, db.get(User, m.user_id), 'შეკითხვაზე პასუხი მიღებულია', b.title, '/workspace#develop')
    log(db, u, b.org_id, 'answer_brief_question', str(qid)); db.commit(); return {'ok': True}


@router.get('/api/admin/operations')
def admin_operations(u=Depends(current), db: Session=Depends(sessdb)):
    if not u.admin: jsonerr(403, 'მოდერატორის უფლება აუცილებელია')
    return {'mail': dict(db.execute(select(MailMessage.status, func.count(MailMessage.id)).group_by(MailMessage.status)).all()),
            'requests': [{'id': r.id, 'email': db.get(User, r.user_id).email, 'category': r.category,
                          'message': r.message, 'status': r.status} for r in db.scalars(select(SupportRequest).order_by(SupportRequest.id.desc()).limit(100))]}


class SupportStatusIn(BaseModel):
    status: str = Field(pattern='^(open|in_progress|resolved)$')


@router.patch('/api/admin/support/{rid}')
def resolve_support(rid: int, d: SupportStatusIn, u=Depends(security), db: Session=Depends(sessdb)):
    if not u.admin: jsonerr(403, 'მოდერატორის უფლება აუცილებელია')
    r = db.get(SupportRequest, rid)
    if not r: jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    r.status = d.status; log(db, u, None, 'support_status', str(rid))
    notify(db, db.get(User, r.user_id), 'მოთხოვნის სტატუსი განახლდა', f'მოთხოვნა #{rid} — '+{'open':'ღია','in_progress':'მიმდინარეობს','resolved':'განხილვა დასრულებულია'}[d.status])
    db.commit(); return {'ok': True}


@router.get('/api/providers')
def providers(u=Depends(current), db: Session=Depends(sessdb)):
    return [{'id': o.id, 'name': o.name, 'demo': o.demo} for o in db.scalars(
        select(Organization).where(Organization.kind == 'provider', Organization.verified.is_(True)))]


@router.delete('/api/course-interests/{iid}')
def cancel_interest(iid: int, u=Depends(security), db: Session=Depends(sessdb)):
    from server import CourseInterest
    record = db.get(CourseInterest, iid)
    if not record or record.user_id != u.id: jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    if record.status not in ('requested', 'cancelled'): jsonerr(409, 'დადასტურებული მოთხოვნის შესაცვლელად დაუკავშირდი მომწოდებელს')
    record.status = 'cancelled'; db.commit(); return {'status': 'cancelled'}


@router.delete('/api/interviews/{iid}')
def cancel_interview(iid: int, u=Depends(security), db: Session=Depends(sessdb)):
    meeting = db.get(Interview, iid)
    if not meeting: jsonerr(404, 'გასაუბრება ვერ მოიძებნა')
    a, job = employer_application(db, u, meeting.application_id, True)
    notify(db, db.get(User, a.user_id), 'გასაუბრება გაუქმდა', job.title+' — '+meeting.scheduled_for.isoformat())
    db.delete(meeting); log(db, u, job.org_id, 'cancel_interview', str(iid)); db.commit(); return {'ok': True}


@router.get('/api/interviews/{iid}/calendar')
def interview_calendar(iid: int, u=Depends(current), db: Session=Depends(sessdb)):
    from zoneinfo import ZoneInfo
    meeting = db.get(Interview, iid)
    if not meeting: jsonerr(404, 'გასაუბრება ვერ მოიძებნა')
    a = db.get(Application, meeting.application_id); job = db.get(Job, a.job_id)
    if a.user_id != u.id: employer_application(db, u, a.id)
    def escape(text):
        return text.replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')
    start = meeting.scheduled_for.replace(tzinfo=ZoneInfo('Asia/Tbilisi')).astimezone(dt.timezone.utc)
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//SIVRCE//Interviews//KA', 'BEGIN:VEVENT',
             f'UID:interview-{iid}@sivrce', 'DTSTAMP:'+utcnow().strftime('%Y%m%dT%H%M%SZ'),
             'DTSTART:'+start.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:'+(start+dt.timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ'),
             'SUMMARY:'+escape(job.title), 'LOCATION:'+escape(meeting.location_or_link),
             'DESCRIPTION:'+escape(meeting.candidate_note), 'END:VEVENT', 'END:VCALENDAR']
    # Fold by UTF-8 octets, retaining whole Unicode code points (RFC 5545).
    folded = []
    for line in lines:
        part = ''
        for char in line:
            if len((part+char).encode()) > 73:
                folded.append(part); part = ' '+char
            else: part += char
        folded.append(part)
    return Response('\r\n'.join(folded)+'\r\n', media_type='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename="interview-{iid}.ics"', 'Cache-Control': 'no-store'})


@router.get('/workspace', response_class=HTMLResponse)
def operations_page(request: Request):
    return templates.TemplateResponse(request, 'operations.html', {})


@router.get('/account', response_class=HTMLResponse)
def account_page(request: Request):
    return templates.TemplateResponse(request, 'account.html', {})
