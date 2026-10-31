import datetime as dt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from server import app, Base, engine, Local
from test_flows import login

import features.voices as voices
from features.voices import Show, ShowEpisode, parse_feed, parse_duration, slugify, topic_for

FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>სატესტო პოდკასტი</title><link>https://example.test/show</link><language>ka</language>
<itunes:author>სატესტო რედაქცია</itunes:author><description><![CDATA[<p>საუბრები <b>სამუშაოზე</b> და ბიზნესზე.</p>]]></description>
<itunes:image href="https://example.test/art.jpg"/><itunes:category text="Business"><itunes:category text="Careers"/></itunes:category>
<item><title>ეპიზოდი 2: ლიდერობა და HR</title><guid>ep-2</guid><pubDate>Tue, 28 Oct 2026 08:00:00 +0400</pubDate>
<enclosure url="https://example.test/ep2.mp3" type="audio/mpeg" length="1"/><itunes:duration>01:02:03</itunes:duration>
<content:encoded><![CDATA[<p>რას ნიშნავს კარგი მენეჯმენტი.</p><p>სტუმარი: ანა.</p>]]></content:encoded><itunes:episode>2</itunes:episode></item>
<item><title>ეპიზოდი 1</title><guid>ep-1</guid><pubDate>Mon, 20 Oct 2026 08:00:00 +0400</pubDate>
<enclosure url="http://example.test/ep1.mp3" type="audio/mpeg"/><itunes:duration>1800</itunes:duration><description>პირველი.</description></item>
<item><title>ვიდეო ანონსი</title><guid>no-audio</guid></item>
</channel></rss>'''


@pytest.fixture(autouse=True)
def reset_database(monkeypatch):
    monkeypatch.setattr(voices, 'fetch', lambda url, **kw: FEED.encode())
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_feed_parsing_and_helpers():
    meta, eps = parse_feed(FEED.encode())
    assert meta['title'] == 'სატესტო პოდკასტი' and meta['author'] == 'სატესტო რედაქცია'
    assert meta['description'] == 'საუბრები სამუშაოზე და ბიზნესზე.' and meta['categories'] == 'Business, Careers'
    assert [e['guid'] for e in eps] == ['ep-2', 'ep-1']  # newest first, item without audio skipped
    assert eps[0]['duration_sec'] == 3723 and eps[0]['number'] == 2 and 'სტუმარი: ანა.' in eps[0]['description']
    assert parse_duration('45:10') == 2710 and parse_duration('') == 0
    assert topic_for('Business, Careers') == 'work' and topic_for('', 'საუბრები ხელოვნურ ინტელექტზე') == 'science'
    assert slugify('შემდეგი პოდკასტი') == 'shemdegi-podkasti'


def test_fetch_refuses_private_hosts():
    with pytest.raises(ValueError): voices.safe_public_url('http://127.0.0.1:8000/feed')
    with pytest.raises(ValueError): voices.safe_public_url('http://10.0.0.5/feed')
    with pytest.raises(ValueError): voices.safe_public_url('ftp://example.com/feed')


def test_index_show_episode_pages_and_https_only_audio():
    with TestClient(app) as c, TestClient(app) as admin:
        login(admin, 'admin@demo.sivrce.ge')
        assert c.post('/api/admin/shows', json={'feed_url': 'https://example.test/feed.xml'}).status_code == 401
        r = admin.post('/api/admin/shows', json={'feed_url': 'https://example.test/feed.xml', 'featured': True})
        assert r.status_code == 200, r.text
        assert r.json()['slug'] == 'satesto-podkasti' and r.json()['new_episodes'] == 2
        assert admin.post('/api/admin/shows', json={'feed_url': 'https://example.test/feed.xml'}).json()['new_episodes'] == 0  # idempotent
        page = c.get('/voices').text
        assert 'სატესტო პოდკასტი' in page and 'ლიდერობა და HR' in page and 'საქმე და ბიზნესი' in page
        assert 'ep1.mp3' not in page  # plain-http audio is never offered on an https page
        assert c.get('/voices/show/satesto-podkasti').status_code == 200
        with Local() as db: eid = db.scalar(select(ShowEpisode.id).where(ShowEpisode.guid == 'ep-2'))
        ep = c.get(f'/voices/ep/{eid}').text
        assert 'კონსპექტი ჯერ არ აქვს' in ep and 'https://example.test/ep2.mp3' in ep
        assert c.get('/voices/ep/999').status_code == 404
        assert c.get('/api/voices/search?q=ლიდერ').json()['episodes'][0]['id'] == eid
        assert c.get('/voices/1').status_code == 200  # curated global shows keep their pages


def test_editorial_layer_claims_and_transcript_visibility():
    with TestClient(app) as c, TestClient(app) as admin, TestClient(app) as owner, TestClient(app) as cand:
        login(admin, 'admin@demo.sivrce.ge'); login(owner, 'company@demo.sivrce.ge'); login(cand, 'candidate@demo.sivrce.ge')
        sid = admin.post('/api/admin/shows', json={'feed_url': 'https://example.test/feed.xml'}).json()['id']
        with Local() as db:
            eid = db.scalar(select(ShowEpisode.id).where(ShowEpisode.guid == 'ep-2'))
            e = db.get(ShowEpisode, eid); e.transcript = 'სრული ტექსტი ეპიზოდისა რომელშიც ლაპარაკობენ ბიუჯეტზე'; e.transcript_status = 'done'; db.commit()
        assert admin.patch(f'/api/admin/episodes/{eid}', json={'chapters': [{'t': 'x'}]}).status_code == 422
        assert admin.patch(f'/api/admin/episodes/{eid}', json={'brief_ka': 'მოკლე კონსპექტი.', 'key_points': 'ერთი\nორი',
                           'chapters': [{'t': 600, 'title': 'ბიუჯეტი'}, {'t': 30, 'title': 'შესავალი'}]}).status_code == 200
        page = c.get(f'/voices/ep/{eid}').text
        assert 'მოკლე კონსპექტი.' in page and 'data-seek="30"' in page and 'ბიუჯეტი' in page
        assert 'სრული ტექსტი ეპიზოდისა' not in page and 'ძებნაშია ჩართული' in page   # unclaimed: transcript only powers search
        assert c.get('/api/voices/search?q=ბიუჯეტზე').json()['episodes'][0]['snippet']
        assert cand.post(f'/api/shows/{sid}/claim').status_code == 403
        assert owner.post(f'/api/shows/{sid}/claim').status_code == 200
        assert admin.patch(f'/api/admin/shows/{sid}', json={'claim': 'approve'}).status_code == 200
        page = c.get(f'/voices/ep/{eid}').text
        assert 'სრული ტექსტი ეპიზოდისა' in page and 'გამომცემლის თანხმობით' in page
        assert '✓ დადასტურებული გამომცემელი' in c.get('/voices/show/satesto-podkasti').text
        assert admin.patch(f'/api/admin/shows/{sid}', json={'status': 'hidden'}).status_code == 200
        assert c.get('/voices/show/satesto-podkasti').status_code == 404
        assert admin.post(f'/api/admin/episodes/{eid}/transcribe').json()['status'] == 'done'


def test_refresh_marks_broken_feeds(monkeypatch):
    with TestClient(app) as admin:
        login(admin, 'admin@demo.sivrce.ge')
        sid = admin.post('/api/admin/shows', json={'feed_url': 'https://example.test/feed.xml'}).json()['id']
        def boom(url, **kw): raise ValueError('ფიდი გაქრა')
        monkeypatch.setattr(voices, 'fetch', boom)
        assert admin.post(f'/api/admin/shows/{sid}/refresh').status_code == 422
        with Local() as db:
            db.get(Show, sid).last_fetched = dt.datetime(2020, 1, 1); db.commit()
            out = voices.refresh_all(db)
            assert 'ფიდი გაქრა' in str(out) and db.get(Show, sid).fetch_error.startswith('ValueError')
