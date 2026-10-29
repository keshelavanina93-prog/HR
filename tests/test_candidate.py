import pytest
from fastapi.testclient import TestClient
from server import app, Base, engine
from test_flows import login

MOTIVATION = {'profile_url': 'https://example.test/portfolio', 'motivation': 'გამოცდილება და უნარები შეესაბამება ამ პოზიციის სამუშაო მიზნებს.'}


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_overview_tracks_stages_rejections_and_is_private():
    with TestClient(app) as cand, TestClient(app) as emp, TestClient(app) as other, TestClient(app) as anon:
        assert anon.get('/api/me/overview').status_code == 401
        assert anon.get('/me').status_code == 200
        login(cand, 'candidate@demo.sivrce.ge'); login(emp, 'company@demo.sivrce.ge')
        a1 = cand.post('/api/jobs/1/apply', json=MOTIVATION).json()['id']
        a2 = cand.post('/api/jobs/2/apply', json=MOTIVATION).json()['id']
        assert cand.post('/api/jobs/3/save').status_code == 200
        assert emp.patch(f'/api/applications/{a1}', json={'status': 'reviewing'}).status_code == 200
        assert emp.patch(f'/api/applications/{a2}', json={'status': 'reviewing'}).status_code == 200
        assert emp.patch(f'/api/applications/{a2}', json={'status': 'rejected'}).status_code == 200
        d = cand.get('/api/me/overview').json()
        apps = {a['id']: a for a in d['applications']}
        assert apps[a1]['stage'] == 1 and not apps[a1]['closed'] and apps[a1]['status_label'] == 'განხილვა'
        assert apps[a2]['closed'] and apps[a2]['stage'] == 1  # stopped at review
        assert d['counts'] == {'active': 1, 'interviews': 0, 'saved': 1}
        assert d['profile']['score'] == 0 and d['unread'] >= 3
        assert cand.put('/api/profile', json={'headline': 'მონაცემთა ანალიტიკოსი', 'location': 'თბილისი', 'skills': 'SQL, BI, სტატისტიკა', 'experience': 'ა'*90}).status_code == 200
        assert cand.get('/api/me/overview').json()['profile']['score'] == 4
        # Another user sees only their own space.
        login(other, 'provider@demo.sivrce.ge')
        assert other.get('/api/me/overview').json()['applications'] == []
        assert other.delete(f'/api/my-applications/{a1}').status_code == 403
