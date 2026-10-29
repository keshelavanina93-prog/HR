"""Develop: compare training proposals side by side and decide as a team.

The comparison is transparent: price figures are computed from the
proposals, everything else is scored by people on the buyer's team.
SIVRCE never picks a provider; a person with develop_write does.
"""
import datetime as dt
import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from server import (Base, Brief, Organization, Proposal, User, current, jsonerr, log, member, proposal_version,
                    security, sessdb, templates)
from features.models import BriefQuestion, utcnow

router = APIRouter()
CRITERIA = {'fit': 'შესაბამისობა მიზანთან', 'method': 'მეთოდოლოგია და პრაქტიკა', 'trainer': 'ტრენერის გამოცდილება'}


class ProposalRating(Base):
    __tablename__ = 'proposal_ratings'
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey('proposals.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    criterion: Mapped[str] = mapped_column(String(16))
    score: Mapped[int] = mapped_column(Integer)
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('proposal_id', 'user_id', 'criterion'),)


class RatingIn(BaseModel):
    criterion: str
    score: int = Field(ge=1, le=5)


def owned_brief(db, u, bid, permission):
    brief = db.get(Brief, bid)
    if not brief: jsonerr(404, 'მოთხოვნა ვერ მოიძებნა')
    member(db, u, brief.org_id, 'company', permission)
    return brief


@router.get('/api/briefs/{bid}/comparison')
def comparison(bid: int, u=Depends(current), db: Session=Depends(sessdb)):
    brief = owned_brief(db, u, bid, 'develop_read')
    rows = db.execute(select(Proposal, Organization).join(Organization, Proposal.org_id == Organization.id)
                      .where(Proposal.brief_id == bid).order_by(Proposal.price)).all()
    cheapest = min((p.price for p, _ in rows), default=0)
    proposals = []
    for p, o in rows:
        ratings = db.scalars(select(ProposalRating).where(ProposalRating.proposal_id == p.id)).all()
        team, mine = {}, {}
        for c in CRITERIA:
            scores = [r.score for r in ratings if r.criterion == c]
            team[c] = {'avg': round(sum(scores)/len(scores), 1) if scores else None, 'count': len(scores)}
            mine[c] = next((r.score for r in ratings if r.criterion == c and r.user_id == u.id), None)
        proposals.append({
            'id': p.id, 'provider': o.name, 'provider_slug': o.slug, 'verified': o.verified, 'demo': o.demo,
            'price': p.price, 'per_person': round(p.price/brief.audience) if brief.audience else None,
            'budget_share': round(p.price/brief.budget*100) if brief.budget else None, 'within_budget': p.price <= brief.budget,
            'price_score': round(cheapest/p.price*5, 2) if p.price else 0,
            'days': p.days, 'trainer': p.trainer, 'approach': p.approach, 'status': p.status,
            'version': proposal_version(db, p.id), 'team': team, 'mine': mine,
            'questions': db.scalar(select(func.count(BriefQuestion.id)).where(BriefQuestion.brief_id == bid, BriefQuestion.provider_id == o.id)),
        })
    return {'brief': {'id': brief.id, 'title': brief.title, 'goal': brief.goal, 'audience': brief.audience, 'budget': brief.budget,
                      'format': brief.format, 'deadline': brief.deadline, 'status': brief.status, 'visibility': brief.visibility},
            'criteria': CRITERIA, 'proposals': proposals,
            'raters': db.scalar(select(func.count(func.distinct(ProposalRating.user_id))).join(Proposal, ProposalRating.proposal_id == Proposal.id)
                                .where(Proposal.brief_id == bid))}


@router.put('/api/proposals/{pid}/rating')
def rate(pid: int, d: RatingIn, u=Depends(security), db: Session=Depends(sessdb)):
    p = db.get(Proposal, pid)
    if not p: jsonerr(404, 'შეთავაზება ვერ მოიძებნა')
    brief = owned_brief(db, u, p.brief_id, 'develop_write')
    if brief.status != 'published': jsonerr(409, 'გადაწყვეტილება უკვე მიღებულია; შეფასება დახურულია')
    if d.criterion not in CRITERIA: jsonerr(422, 'შეფასების კრიტერიუმი არასწორია')
    row = db.scalar(select(ProposalRating).where(ProposalRating.proposal_id == pid, ProposalRating.user_id == u.id,
                                                 ProposalRating.criterion == d.criterion))
    if not row: row = ProposalRating(proposal_id=pid, user_id=u.id, criterion=d.criterion); db.add(row)
    row.score, row.updated = d.score, utcnow()
    log(db, u, None, 'rate_proposal', f'{pid}:{d.criterion}'); db.commit()
    return {'ok': True}


@router.get('/api/organizations/{oid}/briefs')
def org_briefs(oid: int, u=Depends(current), db: Session=Depends(sessdb)):
    member(db, u, oid, 'company', 'develop_read')
    counts = dict(db.execute(select(Proposal.brief_id, func.count(Proposal.id)).group_by(Proposal.brief_id)).all())
    return [{'id': b.id, 'title': b.title, 'status': b.status, 'audience': b.audience, 'budget': b.budget, 'deadline': b.deadline,
             'proposals': counts.get(b.id, 0)} for b in db.scalars(select(Brief).where(Brief.org_id == oid).order_by(Brief.id.desc()))]


@router.get('/workspace/develop', response_class=HTMLResponse)
@router.get('/workspace/develop/{bid}', response_class=HTMLResponse)
def develop_page(request: Request, bid: int | None = None):
    return templates.TemplateResponse(request, 'compare.html', {'brief_id': bid})


def seed_develop():
    """A DEMO brief with three DEMO providers, so the comparison has something to compare."""
    if os.getenv('SEED_DEMO', '0') != '1': return
    from server import Local
    title = 'ციფრული უნარები — 40 თანამშრომელი · DEMO'
    with Local() as db:
        company = db.scalar(select(Organization).where(Organization.slug == 'atelier-demo', Organization.demo == True))
        if not company or db.scalar(select(Brief.id).where(Brief.title == title)): return
        brief = Brief(org_id=company.id, title=title, audience=40, budget=12000, format='ჰიბრიდული', deadline='2026-12-15',
                      visibility='public', status='published',
                      goal='ოპერაციების გუნდის 40 თანამშრომელს სჭირდება ცხრილებთან, ანგარიშებთან და AI ინსტრუმენტებთან უსაფრთხო მუშაობა. შედეგი: ყოველკვირეული ანგარიში ხელით 6 საათის ნაცვლად 2 საათში.')
        db.add(brief); db.flush()
        offers = [
            ('practice-demo', None, 9800, 4, 'დემო ტრენერი', 'ოთხი ნახევარდღიანი სესია მონაწილეების რეალურ ცხრილებზე. თითოეულ სესიას მოსდევს დავალება, ბოლოს — ანგარიშის ავტომატიზაციის პროექტი და შედეგის გაზომვა კომპანიასთან ერთად.'),
            ('mentora-demo', 'Mentora Lab · DEMO', 7200, 3, 'ორი ტრენერი, ანალიტიკის პრაქტიკოსები', 'სამი სრული დღე ადგილზე. ზოგადი პროგრამა Excel-ისა და AI ინსტრუმენტების შესახებ, მზა სავარჯიშოებით. შემდგომი მხარდაჭერა არ შედის.'),
            ('kvali-demo', 'Kvali Academy · DEMO', 13400, 6, 'სერტიფიცირებული ტრენერი + მენტორი', 'ექვსკვირიანი ჰიბრიდული პროგრამა: კვირაში ერთი სესია და მენტორის კონსულტაცია. ყველა მონაწილე ასრულებს საკუთარი ანგარიშის ავტომატიზაციას; ბოლოს შეფასება კომპანიის KPI-ით.'),
        ]
        for slug_, name, price, days, trainer, approach in offers:
            provider = db.scalar(select(Organization).where(Organization.slug == slug_))
            if not provider:
                provider = Organization(name=name, slug=slug_, kind='provider', location='თბილისი', verified=True, demo=True,
                                        description='საჩვენებელი სასწავლო ორგანიზაცია შედარების ეკრანისთვის.')
                db.add(provider); db.flush()
            db.add(Proposal(brief_id=brief.id, org_id=provider.id, price=price, days=days, trainer=trainer, approach=approach))
        db.commit()
