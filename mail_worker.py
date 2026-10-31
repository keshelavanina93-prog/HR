"""Deliver the transactional outbox. Run separately; never send during HTTP requests."""
import argparse
import datetime as dt
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from sqlalchemy import select, update
from server import Local
from features.models import MailMessage, utcnow


def deliver_one():
    host = os.getenv('SMTP_HOST')
    if not host:
        raise RuntimeError('SMTP_HOST is required; queued messages have not been sent')
    with Local() as db:
        row = db.scalar(select(MailMessage).where(MailMessage.status.in_(('pending', 'retry')), MailMessage.available_at <= utcnow())
                        .order_by(MailMessage.id).with_for_update(skip_locked=True))
        if not row: return False
        # Lease supports recovery if the worker exits before reporting delivery.
        claimed = db.execute(update(MailMessage).where(MailMessage.id == row.id, MailMessage.status.in_(('pending', 'retry')))
                             .values(status='sending', attempts=MailMessage.attempts + 1, available_at=utcnow()+dt.timedelta(minutes=10)))
        if claimed.rowcount != 1: db.rollback(); return True
        db.commit(); db.refresh(row)
        try:
            message = EmailMessage()
            message['From'] = os.environ['SMTP_FROM']
            message['To'] = row.recipient
            message['Subject'] = row.subject
            message['Message-ID'] = f'<sivrce-outbox-{row.id}@{os.getenv("MAIL_MESSAGE_DOMAIN", "localhost")}>'
            message.set_content(row.body)
            with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=20) as smtp:
                if os.getenv('SMTP_STARTTLS', '1') == '1': smtp.starttls(context=ssl.create_default_context())
                elif os.getenv('APP_ENV') == 'production': raise RuntimeError('TLS required in production')
                if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                smtp.send_message(message)
            row.status = 'sent'; row.sent_at = utcnow(); row.error = ''
        except Exception as error:
            row.status = 'failed' if row.attempts >= 5 else 'retry'
            row.error = type(error).__name__  # Never persist credentials or provider error text.
            row.available_at = utcnow() + dt.timedelta(seconds=min(3600, 30 * 2 ** row.attempts))
        db.commit()
    return True


def recover_leases():
    with Local() as db:
        db.execute(update(MailMessage).where(MailMessage.status == 'sending', MailMessage.available_at < utcnow()).values(status='retry'))
        db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    while True:
        recover_leases()
        processed = deliver_one()
        if args.once: break
        if not processed: time.sleep(5)
