import datetime as dt
import hashlib
import os
import secrets
from sqlalchemy import select
from features.models import ActionToken, IdentityState, MailMessage, Notification, utcnow


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def verified(db, user):
    from server import GoogleIdentity
    state = db.get(IdentityState, user.id)
    return bool(state and state.verified_at) or bool(db.scalar(select(GoogleIdentity.id).where(GoogleIdentity.user_id == user.id)))


def queue_mail(db, email, subject, body):
    db.add(MailMessage(recipient=email, subject=subject, body=body))


def notify(db, user, title, body, href='/studio'):
    db.add(Notification(user_id=user.id, title=title, body=body, href=href))
    queue_mail(db, user.email, title, body)


def issue_token(db, user, purpose):
    # Invalidate older outstanding tokens for the same action.
    for old in db.scalars(select(ActionToken).where(
        ActionToken.user_id == user.id, ActionToken.purpose == purpose,
        ActionToken.used_at.is_(None)
    )):
        old.used_at = utcnow()
    token = secrets.token_urlsafe(40)
    db.add(ActionToken(token_hash=digest(token), user_id=user.id, purpose=purpose,
                       expires=utcnow() + dt.timedelta(minutes=30)))
    base = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    queue_mail(db, user.email, 'SIVRCE — ანგარიშის დადასტურება' if purpose == 'verify' else 'SIVRCE — პაროლის აღდგენა',
               f'{base}/account#{purpose}={token}\nბმული მოქმედებს 30 წუთი. თუ მოთხოვნა შენ არ გამოგიგზავნია, უგულებელყავი.')


ROLE_PERMISSIONS = {
    'owner': {'team', 'hire_read', 'hire_write', 'develop_read', 'develop_write', 'catalog_read', 'catalog_write', 'org_write'},
    'recruiter': {'hire_read', 'hire_write'},
    'hiring_manager': {'hire_read', 'hire_write'},
    'procurement': {'develop_read', 'develop_write'},
    'provider_editor': {'catalog_read', 'catalog_write', 'develop_read', 'develop_write'},
}
