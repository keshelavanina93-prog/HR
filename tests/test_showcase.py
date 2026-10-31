import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from server import app, Base, engine, Local, Organization, RightsRecord
from test_flows import login

import features.showcase as showcase


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    monkeypatch.setattr(showcase, 'MEDIA_DIR', tmp_path/'media')
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def jpeg(size=(1200, 800), exif_gps=False):
    image = Image.new('RGB', size, (40, 40, 52))
    out = io.BytesIO()
    if exif_gps:
        exif = Image.Exif(); exif[0x8825] = {2: (41.0, 43.0, 0.0)}  # GPSInfo latitude
        image.save(out, 'JPEG', exif=exif)
    else:
        image.save(out, 'JPEG')
    return out.getvalue()


def upload(c, data=None, **fields):
    form = {'role': 'gallery', 'alt': 'გუნდი სამუშაო შეხვედრაზე', 'credit': 'კომპანიის არქივი',
            'rights_confirmed': 'true', 'people_consent': 'no_people', **fields}
    return c.post('/api/organizations/1/photos', data=form, files={'file': ('photo.jpg', data or jpeg(), 'image/jpeg')})


STORY = {'tagline': 'ვაშენებთ პროცესებს, რომლებიც ადამიანებს ეხმარება.', 'accent': 'cobalt',
         'mission': 'მისია ' * 30, 'hard_parts': 'დატვირთული სეზონი\nმივლინებები', 'hiring_promise': 'პასუხი 10 დღეში',
         'day': [{'time': '09:30', 'title': 'დაგეგმვა', 'body': 'გუნდი იკრიბება და ანაწილებს დღის ამოცანებს.'}],
         'people': [{'name': 'ანა კ.', 'role': 'ლიდი', 'quote': 'აქ რთულ საკითხებზე ღიად ვსაუბრობთ.', 'consent': True}]}


def test_company_page_renders_story_and_open_roles():
    with TestClient(app) as c:
        r = c.get('/organizations/atelier-demo')
        assert r.status_code == 200
        assert 'ჩვეულებრივი სამუშაო დღე' in r.text and 'რა არის აქ რთული' in r.text
        assert 'People &amp; Culture Partner' in r.text
        assert 'ფოტო ჯერ არ არის' in r.text and 'unsplash' not in r.text
        assert c.get('/organizations/practice-demo').status_code == 200
        assert c.get('/organizations/does-not-exist').status_code == 404


def test_story_edit_requires_owner_csrf_and_consent():
    with TestClient(app) as owner, TestClient(app) as provider, TestClient(app) as anonymous:
        assert anonymous.put('/api/organizations/1/story', json=STORY).status_code == 401
        login(provider, 'provider@demo.sivrce.ge')
        assert provider.put('/api/organizations/1/story', json=STORY).status_code == 403
        login(owner, 'company@demo.sivrce.ge')
        csrf = owner.headers.pop('X-SIVRCE-CSRF')
        assert owner.put('/api/organizations/1/story', json=STORY).status_code == 403
        owner.headers['X-SIVRCE-CSRF'] = csrf
        no_consent = {**STORY, 'people': [{**STORY['people'][0], 'consent': False}]}
        assert owner.put('/api/organizations/1/story', json=no_consent).status_code == 422
        assert owner.put('/api/organizations/1/story', json={**STORY, 'accent': 'green'}).status_code == 422
        assert owner.put('/api/organizations/1/story', json=STORY).status_code == 200
        page = owner.get('/organizations/atelier-demo').text
        assert STORY['tagline'] in page and '#3755E8' in page and 'ანა კ.' in page


def test_photo_upload_validates_rights_strips_metadata_and_moderates():
    with TestClient(app) as owner, TestClient(app) as admin, TestClient(app) as anonymous:
        login(owner, 'company@demo.sivrce.ge')
        assert upload(owner, rights_confirmed='false').status_code == 422
        assert upload(owner, role='person').status_code == 422  # portrait without consent
        assert upload(owner, data=jpeg((500, 400))).status_code == 422
        assert upload(owner, data=b'%PDF-1.4 not an image').status_code == 422
        r = upload(owner, data=jpeg(exif_gps=True), role='cover')
        assert r.status_code == 200, r.text
        photo = r.json()
        served = anonymous.get(photo['url'])
        assert served.status_code == 200 and served.headers['content-type'] == 'image/jpeg'
        assert not Image.open(io.BytesIO(served.content)).getexif()
        assert photo['url'] in anonymous.get('/organizations/atelier-demo').text
        # Portraits linked to people must carry consent.
        bad = {**STORY, 'people': [{**STORY['people'][0], 'photo_id': photo['id']}]}
        assert owner.put('/api/organizations/1/story', json=bad).status_code == 422
        portrait = upload(owner, role='person', people_consent='confirmed').json()
        good = {**STORY, 'people': [{**STORY['people'][0], 'photo_id': portrait['id']}]}
        assert owner.put('/api/organizations/1/story', json=good).status_code == 200
        login(admin, 'admin@demo.sivrce.ge')
        assert admin.post(f'/api/admin/photos/{portrait["id"]}/remove').status_code == 200
        assert anonymous.get(portrait['url']).status_code == 404
        assert owner.get('/api/organizations/1/story').json()['people'][0]['photo_id'] is None
        assert owner.delete(f'/api/organizations/1/photos/{photo["id"]}').status_code == 200
        assert anonymous.get(photo['url']).status_code == 404


def test_unverified_organization_photos_stay_private():
    with TestClient(app) as owner, TestClient(app) as anonymous:
        login(owner, 'company@demo.sivrce.ge')
        url = upload(owner).json()['url']
        with Local() as db:
            db.get(Organization, 1).verified = False; db.commit()
        assert anonymous.get(url).status_code == 404
        assert owner.get(url).status_code == 200


def test_episode_page_levels_follow_rights_registry():
    with TestClient(app) as c, TestClient(app) as admin:
        r = c.get('/voices/1')
        assert r.status_code == 200
        assert 'https://open.spotify.com/embed/show/' in r.text
        assert r.text.count('level-locked') == 2 and 'ანალიზი მზადდება' in r.text
        assert '/voices/1' in c.get('/voices').text
        assert c.get('/voices/999').status_code == 404
        login(admin, 'admin@demo.sivrce.ge')
        assert c.put('/api/admin/voices/1/editorial', json={'analysis': 'ა'*400, 'author': 'რედაქცია'}).status_code == 401
        assert admin.put('/api/admin/voices/1/editorial', json={'analysis': 'ტექსტი', 'author': 'რედაქცია'}).status_code == 422
        assert admin.put('/api/admin/voices/1/editorial', json={'analysis': 'ანალიზი '*60, 'key_points': 'პირველი\nმეორე', 'author': 'SIVRCE რედაქცია'}).status_code == 200
        assert admin.post('/api/admin/content-rights', json={'content_type': 'episode', 'content_id': 1, 'source_url': 'https://example.test/license',
                          'rights_holder': 'Example Publisher', 'permitted_use': 'licensed_translation', 'evidence': 'ხელშეკრულება №12, თარგმნის უფლება 2027 წლამდე'}).status_code == 200
        page = c.get('/voices/1').text
        assert 'SIVRCE რედაქცია' in page and 'Example Publisher' in page
        assert page.count('level-locked') == 1


def test_pay_view_converts_between_gross_and_net():
    assert showcase.pay_view({'salary_min': 1000, 'salary_max': 2000, 'salary_basis': 'gross'}) == \
        {'gross': (1000, 2000), 'net': (780, 1570), 'stated': 'gross'}
    assert showcase.pay_view({'salary_min': 784, 'salary_max': 1568, 'salary_basis': 'net'})['gross'] == (1000, 2000)
    assert showcase.hiring_steps('განაცხადი → ინტერვიუ → შეთავაზება') == ['განაცხადი', 'ინტერვიუ', 'შეთავაზება']


def test_job_page_shows_company_world_and_closes_after_deadline():
    from server import Job
    with TestClient(app) as c:
        page = c.get('/careers/1').text
        assert 'ხელზე' in page and 'დარიცხული' in page and 'შერჩევის გზა' in page
        assert 'როგორ მუშაობენ' in page and 'ვინ ნახავს ჩემს მონაცემებს' in page
        assert 'data-modal="apply"' in page
        with Local() as db:
            db.get(Job, 1).deadline = '2020-01-01'; db.commit()
        closed = c.get('/careers/1').text
        assert 'განაცხადის მიღება დასრულდა' in closed and 'data-modal="apply"' not in closed


def test_course_page_lists_outcomes_modules_and_cohorts():
    with TestClient(app) as c:
        page = c.get('/learn/1').text
        assert 'რას შეძლებ კურსის შემდეგ' in page and 'მოდული 1' in page
        assert 'data-course-interest=' in page and 'data-modal="brief-from-course"' in page
