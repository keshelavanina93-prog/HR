import datetime as dt
import re
import threading
import socketserver
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from server import app, Base, engine, Local, User, Membership, Organization, Brief, Proposal, Job, AuthSession
from features.models import MailMessage, IdentityState, TeamInvite, utcnow
from test_flows import login, make_job


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def register(c, email='member@example.test'):
    r = c.post('/api/auth/register', json={'name': 'სატესტო წევრი', 'email': email, 'password': 'TestingOnly!234'})
    assert r.status_code == 200, r.text
    c.headers['X-SIVRCE-CSRF'] = r.json()['csrf']
    return r.json()


def mail_token(email, action):
    with Local() as db:
        mails = db.scalars(select(MailMessage).where(MailMessage.recipient == email).order_by(MailMessage.id.desc())).all()
        return next(re.search(r'#'+action+r'=([A-Za-z0-9_-]+)', m.body).group(1) for m in mails if '#'+action+'=' in m.body)


def apply(c):
    login(c, 'candidate@demo.sivrce.ge')
    r = c.post('/api/jobs/1/apply', json={'profile_url': 'https://example.test/portfolio', 'motivation': 'გამოცდილება და უნარები შეესაბამება ამ პოზიციის სამუშაო მიზნებს.'})
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_persistent_incomplete_draft_version_and_moderated_submission():
    with TestClient(app) as employer, TestClient(app) as provider:
        login(employer, 'company@demo.sivrce.ge'); login(provider, 'provider@demo.sivrce.ge')
        d = employer.post('/api/job-drafts', json={'org_id': 1, 'payload': {'title': 'დაუსრულებელი პოზიცია'}}).json()
        assert employer.post(f'/api/job-drafts/{d["id"]}/submit', json={'revision': 1}).status_code == 422
        payload = make_job(); payload.pop('org_id'); payload.pop('publish')
        assert employer.put(f'/api/job-drafts/{d["id"]}', json={'org_id': 1, 'payload': payload, 'revision': 1}).status_code == 200
        assert employer.put(f'/api/job-drafts/{d["id"]}', json={'org_id': 1, 'payload': payload, 'revision': 1}).status_code == 409
        assert provider.get('/api/organizations/1/drafts').status_code == 403
        result = employer.post(f'/api/job-drafts/{d["id"]}/submit', json={'revision': 2})
        assert result.status_code == 200, result.text
        assert result.json()['status'] == 'pending_review'
        assert employer.get(f'/api/jobs/{result.json()["id"]}').status_code == 404
        assert employer.post(f'/api/job-drafts/{d["id"]}/submit', json={'revision': 2}).json()['id'] == result.json()['id']


def test_draft_cannot_move_organizations_or_accept_arbitrary_fields():
    with TestClient(app) as c:
        login(c, 'company@demo.sivrce.ge')
        assert c.post('/api/job-drafts', json={'org_id': 1, 'payload': {'status': 'published'}}).status_code == 422
        d = c.post('/api/job-drafts', json={'org_id': 1, 'payload': {}}).json()
        assert c.put(f'/api/job-drafts/{d["id"]}', json={'org_id': 2, 'payload': {}, 'revision': 1}).status_code == 403


def test_internal_reviews_notifications_and_terminal_state():
    with TestClient(app) as candidate, TestClient(app) as employer, TestClient(app) as outsider:
        aid = apply(candidate); login(employer, 'company@demo.sivrce.ge'); login(outsider, 'provider@demo.sivrce.ge')
        note = {'body': 'კონკრეტული სამუშაო ქეისის განხილვა საჭიროა', 'rating': 4, 'criterion': 'SQL გამოცდილება'}
        assert employer.post(f'/api/applications/{aid}/notes', json=note).status_code == 200
        assert candidate.get(f'/api/applications/{aid}/review').status_code == 403
        assert outsider.get(f'/api/applications/{aid}/review').status_code == 403
        assert employer.patch(f'/api/applications/{aid}', json={'status': 'offer'}).status_code == 200
        history = employer.get(f'/api/applications/{aid}/review').json()['history']
        assert history[0]['previous'] == 'received' and history[0]['status'] == 'offer'
        inbox = candidate.get('/api/notifications').json()
        assert len(inbox) == 1 and not inbox[0]['read']
        assert outsider.post(f'/api/notifications/{inbox[0]["id"]}/read').status_code == 404
        assert candidate.post(f'/api/notifications/{inbox[0]["id"]}/read').status_code == 200
        assert employer.patch(f'/api/applications/{aid}', json={'status': 'hired'}).status_code == 200
        assert employer.patch(f'/api/applications/{aid}', json={'status': 'reviewing'}).status_code == 409


def test_invite_requires_email_proof_and_roles_block_candidate_access():
    with TestClient(app) as owner, TestClient(app) as member, TestClient(app) as outsider:
        login(owner, 'company@demo.sivrce.ge'); register(member)
        assert owner.post('/api/organizations/1/invites', json={'email': 'member@example.test', 'role': 'owner'}).status_code == 422
        sent = owner.post('/api/organizations/1/invites', json={'email': 'member@example.test', 'role': 'procurement'})
        assert sent.status_code == 200 and 'token' not in sent.json()
        invite_token = mail_token('member@example.test', 'invite')
        assert member.post('/api/team/accept', json={'token': invite_token}).status_code == 403
        verify_token = mail_token('member@example.test', 'verify')
        assert member.post('/api/auth/verify', json={'token': verify_token}).status_code == 200
        assert member.post('/api/team/accept', json={'token': invite_token}).status_code == 200
        assert member.post('/api/team/accept', json={'token': invite_token}).status_code == 410
        assert member.get('/api/organizations/1/applications').status_code == 403
        assert member.post('/api/jobs', json=make_job()).status_code == 403
        assert member.get('/api/organizations/1/proposals').status_code == 200
        assert member.get('/api/organizations/1/team').status_code == 403
        assert member.get('/api/organizations/2/proposals').status_code == 403


def test_invite_revocation_and_wrong_email_are_enforced():
    with TestClient(app) as owner, TestClient(app) as other:
        login(owner, 'company@demo.sivrce.ge'); register(other, 'wrong@example.test')
        sent = owner.post('/api/organizations/1/invites', json={'email': 'member@example.test', 'role': 'recruiter'}).json()
        token = mail_token('member@example.test', 'invite')
        assert other.post('/api/team/accept', json={'token': token}).status_code == 403
        assert owner.delete(f'/api/organizations/1/invites/{sent["id"]}').status_code == 200
        assert other.post('/api/team/accept', json={'token': token}).status_code == 410


def test_recovery_consumes_token_revokes_sessions_and_does_not_enumerate():
    with TestClient(app) as c, TestClient(app) as guest:
        login(c, 'candidate@demo.sivrce.ge')
        r1 = guest.post('/api/auth/recovery', json={'email': 'candidate@demo.sivrce.ge'})
        r2 = guest.post('/api/auth/recovery', json={'email': 'missing@example.test'})
        assert r1.json() == r2.json()
        token = mail_token('candidate@demo.sivrce.ge', 'reset')
        assert guest.post('/api/auth/reset', json={'token': token, 'password': 'NewTestingOnly!234'}).status_code == 200
        assert c.get('/api/me').json()['user'] is None
        assert guest.post('/api/auth/reset', json={'token': token, 'password': 'AnotherTesting!234'}).status_code == 410
        assert guest.post('/api/auth/login', json={'email': 'candidate@demo.sivrce.ge', 'password': 'NewTestingOnly!234'}).status_code == 200


def test_expired_verification_token_and_cross_origin_auth():
    from features.models import ActionToken
    with TestClient(app) as c:
        register(c)
        token = mail_token('member@example.test', 'verify')
        with Local() as db:
            row = db.scalar(select(ActionToken)); row.expires = utcnow()-dt.timedelta(seconds=1); db.commit()
        assert c.post('/api/auth/verify', json={'token': token}).status_code == 410
        assert c.post('/api/auth/recovery', headers={'Origin': 'https://attacker.test'}, json={'email': 'member@example.test'}).status_code == 403


def test_profile_export_and_support_are_private():
    with TestClient(app) as c, TestClient(app) as other:
        login(c, 'candidate@demo.sivrce.ge'); login(other, 'provider@demo.sivrce.ge')
        assert c.put('/api/profile', json={'headline': 'პროდუქტის დიზაინერი', 'skills': 'კვლევა, პროტოტიპირება'}).status_code == 200
        assert other.get('/api/profile').json()['headline'] == ''
        exported = c.get('/api/account/export').json()
        assert exported['profile']['headline'] == 'პროდუქტის დიზაინერი'
        assert 'pw_hash' not in str(exported) and 'token_hash' not in str(exported)
        assert c.post('/api/support', json={'category': 'deletion', 'message': 'გთხოვთ წაშალოთ ჩემი პირადი ანგარიში.'}).status_code == 200
        assert len(c.get('/api/support').json()) == 1 and other.get('/api/support').json() == []
        assert c.delete('/api/profile').status_code == 200


def brief_payload():
    return {'org_id': 1, 'title': 'კომუნიკაციის სასწავლო მოთხოვნა', 'goal': 'გუნდის ხელმძღვანელებისთვის რთული საუბრებისა და უკუკავშირის მართვის პრაქტიკა', 'audience': 12, 'budget': 4000, 'format': 'ადგილზე', 'deadline': '2026-12-31', 'visibility': 'private', 'publish': False}


def proposal_payload(org_id=2):
    return {'org_id': org_id, 'price': 1500, 'approach': 'პრაქტიკული ქეისების განხილვა და უკუკავშირი კონკრეტული სამუშაო მიზნების შესაბამისად', 'trainer': 'სატესტო ტრენერი', 'days': 2}


def test_private_brief_invitation_revision_history_award_and_completion():
    with TestClient(app) as buyer, TestClient(app) as provider:
        login(buyer, 'company@demo.sivrce.ge'); login(provider, 'provider@demo.sivrce.ge')
        bid = buyer.post('/api/briefs', json=brief_payload()).json()['id']
        assert buyer.post(f'/api/briefs/{bid}/publish').status_code == 200
        assert provider.post(f'/api/briefs/{bid}/proposals', json=proposal_payload()).status_code == 404
        assert bid not in [b['id'] for b in buyer.get('/api/briefs').json()]
        assert buyer.post(f'/api/briefs/{bid}/invites', json={'provider_id': 2}).status_code == 200
        assert bid in [b['id'] for b in provider.get('/api/organizations/2/opportunities').json()]
        pid = provider.post(f'/api/briefs/{bid}/proposals', json=proposal_payload()).json()['id']
        edit = {k: v for k, v in proposal_payload().items() if k != 'org_id'}; edit.update(price=1800, version=1)
        assert provider.put(f'/api/proposals/{pid}', json=edit).status_code == 200
        assert provider.put(f'/api/proposals/{pid}', json=edit).status_code == 409
        history = buyer.get(f'/api/proposals/{pid}/history').json()
        assert [r['snapshot']['price'] for r in history] == [1500, 1800]
        assert buyer.post(f'/api/proposals/{pid}/select').status_code == 200
        assert provider.put(f'/api/proposals/{pid}', json={**edit, 'version': 2}).status_code == 409
        r = buyer.post(f'/api/briefs/{bid}/complete', json={'rating': 4, 'outcomes': 'გუნდმა პრაქტიკაში გამოიყენა მიღებული ცოდნა და უკუკავშირის ჩარჩოები.'})
        assert r.status_code == 200 and r.json()['status'] == 'completed'


def test_interview_conflict_calendar_and_authorized_cancellation():
    with TestClient(app) as candidate, TestClient(app) as employer, TestClient(app) as other:
        aid = apply(candidate); login(employer, 'company@demo.sivrce.ge'); login(other, 'provider@demo.sivrce.ge')
        payload = {'scheduled_for': (dt.datetime.now()+dt.timedelta(days=2)).replace(microsecond=0).isoformat(), 'format': 'online', 'location_or_link': 'https://example.test/meeting', 'candidate_note': 'მოამზადე სამუშაო ქეისი'}
        r = employer.post(f'/api/applications/{aid}/interviews', json=payload)
        assert r.status_code == 200, r.text
        iid = r.json()['id']
        assert employer.post(f'/api/applications/{aid}/interviews', json=payload).status_code == 409
        cal = candidate.get(f'/api/interviews/{iid}/calendar')
        assert cal.status_code == 200 and 'BEGIN:VCALENDAR' in cal.text and 'DTSTART:' in cal.text
        assert all(len(line.encode()) <= 75 for line in cal.text.splitlines())
        assert other.get(f'/api/interviews/{iid}/calendar').status_code == 403
        assert candidate.delete(f'/api/interviews/{iid}').status_code == 403
        assert employer.delete(f'/api/interviews/{iid}').status_code == 200


def test_workspace_no_store_and_capabilities_do_not_claim_unconfigured_services():
    with TestClient(app) as c:
        assert c.get('/workspace').status_code == 200
        assert c.get('/account').status_code == 200
        assert c.get('/api/capabilities').json()['billing'] is False
        assert c.get('/api/me').headers['Cache-Control'] == 'no-store'
        assert c.get('/workspace').headers['X-Frame-Options'] == 'DENY'
        assert c.get('/static/operations.js').status_code == 200


def test_production_upload_scanner_fails_closed(monkeypatch):
    from features.files import scan_pdf
    from fastapi import HTTPException
    monkeypatch.setenv('APP_ENV', 'production'); monkeypatch.delenv('CLAMAV_HOST', raising=False)
    with pytest.raises(HTTPException) as exc: scan_pdf(b'%PDF-1.4')
    assert exc.value.status_code == 503


def test_outbox_real_local_smtp_delivery(monkeypatch):
    # A real local SMTP conversation; external provider delivery is a separate deployment check.
    captured = []
    class SMTPHandler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b'220 localhost ESMTP\r\n')
            while True:
                line = self.rfile.readline()
                if not line: break
                command = line.split(b' ', 1)[0].strip().upper()
                if command == b'DATA':
                    self.wfile.write(b'354 Continue\r\n'); body = b''
                    while True:
                        chunk = self.rfile.readline()
                        if chunk == b'.\r\n' or not chunk: break
                        body += chunk
                    captured.append(body); self.wfile.write(b'250 Accepted\r\n')
                elif command == b'QUIT': self.wfile.write(b'221 Bye\r\n'); break
                else: self.wfile.write(b'250 OK\r\n')
    with TestClient(app) as c:
        with socketserver.TCPServer(('127.0.0.1', 0), SMTPHandler) as smtp:
            thread = threading.Thread(target=smtp.serve_forever, daemon=True); thread.start()
            monkeypatch.setenv('SMTP_HOST', '127.0.0.1'); monkeypatch.setenv('SMTP_PORT', str(smtp.server_address[1]))
            monkeypatch.setenv('SMTP_FROM', 'sivrce@example.test'); monkeypatch.setenv('SMTP_STARTTLS', '0')
            monkeypatch.delenv('SMTP_USER', raising=False)
            c.post('/api/auth/recovery', json={'email': 'candidate@demo.sivrce.ge'})
            from mail_worker import deliver_one
            assert deliver_one()
            assert len(captured) == 1 and b'candidate@demo.sivrce.ge' in captured[0]
            with Local() as db: assert db.scalar(select(MailMessage)).status == 'sent'
            smtp.shutdown(); thread.join(timeout=2)


def test_provider_catalog_edits_are_moderated_and_private():
    with TestClient(app) as provider, TestClient(app) as employer:
        login(provider, 'provider@demo.sivrce.ge'); login(employer, 'company@demo.sivrce.ge')
        assert employer.get('/api/organizations/2/catalog').status_code == 403
        data = provider.get('/api/organizations/2/catalog').json()[0]
        cid = data.pop('id'); data.pop('cohorts'); data.pop('status'); data['publish'] = True
        data['price'] = 620
        response = provider.put(f'/api/courses/{cid}', json=data)
        assert response.status_code == 200 and response.json()['status'] == 'pending_review'
        assert cid not in [c['id'] for c in employer.get('/api/courses').json()]
        assert employer.put(f'/api/courses/{cid}', json=data).status_code == 403


def test_private_questions_only_buyer_and_questioning_provider_can_read():
    with TestClient(app) as buyer, TestClient(app) as provider, TestClient(app) as other:
        login(buyer, 'company@demo.sivrce.ge'); login(provider, 'provider@demo.sivrce.ge')
        register(other, 'outside@example.test')
        bid = buyer.post('/api/briefs', json=brief_payload()).json()['id']
        buyer.post(f'/api/briefs/{bid}/publish'); buyer.post(f'/api/briefs/{bid}/invites', json={'provider_id': 2})
        response = provider.post(f'/api/briefs/{bid}/questions', json={'provider_id': 2, 'question': 'რა პრაქტიკული შედეგები უნდა მივიღოთ ტრენინგის შემდეგ?'})
        assert response.status_code == 200, response.text
        qid = response.json()['id']
        assert other.get(f'/api/briefs/{bid}/questions').status_code == 403
        assert buyer.post(f'/api/questions/{qid}/answer', json={'answer': 'გუნდის ხელმძღვანელები გამოიყენებენ უკუკავშირის შეთანხმებულ ჩარჩოს.'}).status_code == 200
        assert buyer.post(f'/api/questions/{qid}/answer', json={'answer': 'ძველი პასუხის შეცვლა'}).status_code == 409
        assert provider.get(f'/api/briefs/{bid}/questions').json()[0]['answer']


def test_organization_identity_changes_require_reverification():
    with TestClient(app) as c:
        login(c, 'company@demo.sivrce.ge')
        settings = c.get('/api/organizations/1/settings').json()
        settings.pop('verified'); settings.pop('verification_requested')
        settings['name'] = 'სხვა სახელწოდება — DEMO'
        assert c.put('/api/organizations/1/settings', json=settings).json()['verified'] is False
        assert c.get('/api/jobs').json() == []
        assert c.post('/api/jobs', json=make_job()).status_code == 403


def test_withdrawal_removes_internal_notes_and_status_history():
    from features.models import ApplicantNote, ApplicationEvent
    with TestClient(app) as candidate, TestClient(app) as employer:
        aid = apply(candidate); login(employer, 'company@demo.sivrce.ge')
        employer.post(f'/api/applications/{aid}/notes', json={'body': 'შიდა შეფასების ჩანაწერი'})
        employer.patch(f'/api/applications/{aid}', json={'status': 'reviewing'})
        assert candidate.delete(f'/api/my-applications/{aid}').status_code == 200
        with Local() as db:
            assert db.scalar(select(ApplicantNote.id).where(ApplicantNote.application_id == aid)) is None
            assert db.scalar(select(ApplicationEvent.id).where(ApplicationEvent.application_id == aid)) is None


def test_auth_requests_are_throttled_without_email_enumeration():
    with TestClient(app) as c:
        for i in range(30):
            assert c.post('/api/auth/recovery', json={'email': 'missing@example.test'}).status_code == 200
        assert c.post('/api/auth/recovery', json={'email': 'missing@example.test'}).status_code == 429


def test_oversized_requests_are_rejected():
    with TestClient(app) as c:
        r = c.post('/api/auth/recovery', content=b'x'*(6*1024*1024+1), headers={'Content-Type': 'application/json'})
        assert r.status_code == 413


def test_journal_html_never_appears_inside_document_title():
    with TestClient(app) as c:
        for path in ['/journal', '/journal/job-transparency-is-a-product', '/careers', '/learn', '/voices']:
            response = c.get(path)
            title = re.search(r'<title>(.*?)</title>', response.text, re.S).group(1)
            assert '<' not in title and 'SIVRCE' in title


def test_support_admin_permissions_and_user_visible_status():
    with TestClient(app) as c, TestClient(app) as admin:
        login(c, 'candidate@demo.sivrce.ge'); login(admin, 'admin@demo.sivrce.ge')
        rid = c.post('/api/support', json={'category': 'privacy', 'message': 'მსურს ინფორმაცია ჩემი ანგარიშის მონაცემებზე.'}).json()['id']
        assert c.get('/api/admin/operations').status_code == 403
        assert admin.patch(f'/api/admin/support/{rid}', json={'status': 'in_progress'}).status_code == 200
        assert c.get('/api/support').json()[0]['status'] == 'in_progress'
        assert len(c.get('/api/notifications').json()) == 1


def test_csv_preview_has_no_side_effect_and_import_requires_rights():
    import io
    csv = ('title,category,format,description,outcomes,curriculum,trainer,price,duration\n'
           'Business Analytics,ანალიტიკა,ონლაინ,პრაქტიკული კურსი ბიზნესის მონაცემების ანალიზისთვის,'
           'მონაცემების ანალიზი და ვიზუალიზაცია პრაქტიკაში,ცხრილების მომზადება და მონაცემების ვიზუალიზაცია,'
           'სატესტო ტრენერი,250,8 საათი\n').encode()
    with TestClient(app) as c:
        login(c, 'provider@demo.sivrce.ge')
        before = len(c.get('/api/organizations/2/catalog').json())
        r = c.post('/api/organizations/2/courses/import-csv?preview=true', data={'rights_attested': 'true'}, files={'catalog': ('courses.csv', io.BytesIO(csv), 'text/csv')})
        assert r.status_code == 200, r.text
        assert r.json()['written'] == 0 and r.json()['count'] == 1
        assert len(c.get('/api/organizations/2/catalog').json()) == before
        r = c.post('/api/organizations/2/courses/import-csv', data={'rights_attested': 'true'}, files={'catalog': ('courses.csv', io.BytesIO(csv), 'text/csv')})
        assert r.status_code == 200 and r.json()['status'] == 'pending_review'


def test_mail_failure_is_retried_and_never_marked_sent(monkeypatch):
    import socket
    from mail_worker import deliver_one
    with TestClient(app) as c, socket.socket() as closed_listener:
        closed_listener.bind(('127.0.0.1', 0))
        monkeypatch.setenv('SMTP_HOST', '127.0.0.1'); monkeypatch.setenv('SMTP_PORT', str(closed_listener.getsockname()[1]))
        monkeypatch.setenv('SMTP_FROM', 'test@example.test'); monkeypatch.setenv('SMTP_STARTTLS', '0')
        c.post('/api/auth/recovery', json={'email': 'candidate@demo.sivrce.ge'})
        assert deliver_one()
        with Local() as db:
            message = db.scalar(select(MailMessage)); assert message.status == 'retry' and message.sent_at is None
            message.attempts = 4; message.available_at = utcnow()-dt.timedelta(seconds=1); db.commit()
        assert deliver_one()
        with Local() as db: assert db.scalar(select(MailMessage)).status == 'failed'


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL row-lock concurrency')
def test_concurrent_awards_cannot_select_two_providers():
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(app) as owner, TestClient(app) as second_owner:
        login(owner, 'company@demo.sivrce.ge'); login(second_owner, 'company@demo.sivrce.ge')
        with Local() as db:
            other = Organization(name='მეორე მომწოდებელი — DEMO', slug='provider-two-demo', kind='provider', verified=True, demo=True)
            db.add(other); db.flush()
            p1 = Proposal(brief_id=1, org_id=2, price=1200, approach='პირველი სატესტო შეთავაზება', trainer='ტრენერი 1', days=2)
            p2 = Proposal(brief_id=1, org_id=other.id, price=1400, approach='მეორე სატესტო შეთავაზება', trainer='ტრენერი 2', days=3)
            db.add_all([p1, p2]); db.commit(); ids = [p1.id, p2.id]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda pair: pair[0].post(f'/api/proposals/{pair[1]}/select'), zip([owner, second_owner], ids)))
        assert sorted(r.status_code for r in responses) == [200, 409]
        with Local() as db:
            selected = db.scalars(select(Proposal).where(Proposal.brief_id == 1, Proposal.status == 'selected')).all()
            assert len(selected) == 1
