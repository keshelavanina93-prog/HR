"""Additive tables: existing beta records are preserved."""
import datetime as dt
from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from server import Base


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class JobDraft(Base):
    __tablename__ = 'job_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    job_id: Mapped[int | None] = mapped_column(ForeignKey('jobs.id'), nullable=True)
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ApplicantNote(Base):
    __tablename__ = 'applicant_notes'
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criterion: Mapped[str] = mapped_column(String(100), default='')
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ApplicationEvent(Base):
    __tablename__ = 'application_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    previous: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    href: Mapped[str] = mapped_column(String(300), default='/studio')
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class MailMessage(Base):
    __tablename__ = 'mail_outbox'
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient: Mapped[str] = mapped_column(String(180))
    subject: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(100), default='')
    available_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class IdentityState(Base):
    __tablename__ = 'identity_state'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class ActionToken(Base):
    __tablename__ = 'action_tokens'
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    purpose: Mapped[str] = mapped_column(String(20))
    expires: Mapped[dt.datetime] = mapped_column(DateTime)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class TeamInvite(Base):
    __tablename__ = 'team_invites'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    email: Mapped[str] = mapped_column(String(180))
    role: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires: Mapped[dt.datetime] = mapped_column(DateTime)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class CandidateProfile(Base):
    __tablename__ = 'candidate_profiles'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    headline: Mapped[str] = mapped_column(String(160), default='')
    location: Mapped[str] = mapped_column(String(160), default='')
    skills: Mapped[str] = mapped_column(Text, default='')
    experience: Mapped[str] = mapped_column(Text, default='')
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ConsentEvent(Base):
    __tablename__ = 'consent_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    purpose: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(30))
    granted: Mapped[bool] = mapped_column(default=True)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class BriefAccess(Base):
    __tablename__ = 'brief_access'
    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey('briefs.id'))
    provider_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    __table_args__ = (UniqueConstraint('brief_id', 'provider_id'),)


class ProposalRevision(Base):
    __tablename__ = 'proposal_revisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey('proposals.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('proposal_id', 'version'),)


class BriefQuestion(Base):
    __tablename__ = 'brief_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey('briefs.id'), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class TrainingEvaluation(Base):
    __tablename__ = 'training_evaluations'
    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey('briefs.id'), unique=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    rating: Mapped[int] = mapped_column(Integer)
    outcomes: Mapped[str] = mapped_column(Text)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SupportRequest(Base):
    __tablename__ = 'support_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    category: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='open')
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
