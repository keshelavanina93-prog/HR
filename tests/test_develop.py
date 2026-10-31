import pytest
from fastapi.testclient import TestClient
from server import app, Base, engine, Local, Brief, Proposal
from sqlalchemy import select
from test_flows import login


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def demo_brief():
    with Local() as db:
        return db.scalar(select(Brief.id).where(Brief.title.like('ციფრული უნარები%')))


def test_comparison_is_private_to_buyer_and_computes_price_fields():
    with TestClient(app) as buyer, TestClient(app) as provider, TestClient(app) as anon:
        bid = demo_brief()
        assert anon.get(f'/api/briefs/{bid}/comparison').status_code == 401
        login(provider, 'provider@demo.sivrce.ge')
        assert provider.get(f'/api/briefs/{bid}/comparison').status_code == 403
        login(buyer, 'company@demo.sivrce.ge')
        d = buyer.get(f'/api/briefs/{bid}/comparison').json()
        prices = [p['price'] for p in d['proposals']]
        assert prices == sorted(prices) and len(prices) == 3
        cheapest = d['proposals'][0]
        assert cheapest['price_score'] == 5 and cheapest['per_person'] == round(cheapest['price']/40)
        assert any(not p['within_budget'] for p in d['proposals'])
        assert {b['id'] for b in buyer.get('/api/organizations/1/briefs').json()} >= {bid}


def test_team_ratings_validate_and_average_then_selection_closes_rating():
    with TestClient(app) as buyer, TestClient(app) as provider:
        bid = demo_brief(); login(buyer, 'company@demo.sivrce.ge'); login(provider, 'provider@demo.sivrce.ge')
        pid = buyer.get(f'/api/briefs/{bid}/comparison').json()['proposals'][0]['id']
        assert buyer.put(f'/api/proposals/{pid}/rating', json={'criterion': 'fit', 'score': 6}).status_code == 422
        assert buyer.put(f'/api/proposals/{pid}/rating', json={'criterion': 'price', 'score': 3}).status_code == 422
        assert provider.put(f'/api/proposals/{pid}/rating', json={'criterion': 'fit', 'score': 5}).status_code == 403
        assert buyer.put(f'/api/proposals/{pid}/rating', json={'criterion': 'fit', 'score': 2}).status_code == 200
        assert buyer.put(f'/api/proposals/{pid}/rating', json={'criterion': 'fit', 'score': 4}).status_code == 200  # update, not duplicate
        p = buyer.get(f'/api/briefs/{bid}/comparison').json()['proposals'][0]
        assert p['team']['fit'] == {'avg': 4.0, 'count': 1} and p['mine']['fit'] == 4
        assert buyer.post(f'/api/proposals/{pid}/select', json={}).status_code == 200
        statuses = sorted(x['status'] for x in buyer.get(f'/api/briefs/{bid}/comparison').json()['proposals'])
        assert statuses == ['not_selected', 'not_selected', 'selected']
        assert buyer.put(f'/api/proposals/{pid}/rating', json={'criterion': 'method', 'score': 3}).status_code == 409
        assert buyer.get(f'/workspace/develop/{bid}').status_code == 200
