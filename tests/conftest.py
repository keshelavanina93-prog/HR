"""Select only explicitly named disposable test databases before importing server."""
import os
from pathlib import Path
import sys
import pytest
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
target = os.getenv('TEST_DATABASE_URL', 'sqlite:///'+str(Path(__file__).parent/'integration-test.db'))
url = make_url(target)
if url.get_backend_name() == 'postgresql' and not (url.database or '').startswith('sivrce_test'):
    raise RuntimeError('TEST_DATABASE_URL must name an isolated sivrce_test* database')
if url.get_backend_name() == 'sqlite' and Path(url.database or '').name != 'integration-test.db':
    raise RuntimeError('Tests may only reset integration-test.db')
os.environ['DATABASE_URL'] = target
os.environ['SEED_DEMO'] = '1'
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = '0'


@pytest.fixture(autouse=True)
def reset_limiter():
    from features.middleware import attempts
    attempts.clear()
