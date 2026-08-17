import os
import tempfile
from pathlib import Path

import pytest

# Point at a throwaway DB before any app module imports settings.
# Kept in the system temp dir — SQLite needs real file locking, which some
# network and container mounts don't provide.
_DB = Path(tempfile.gettempdir()) / "shortener-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["BASE_URL"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Codes are derived from row ids, and dropping the tables resets the
    # sequence — so test 2 gets the same code test 1 had. Without clearing
    # Redis between tests, a stale entry serves the previous test's target.
    #
    # Worth noting this isn't purely a test concern: restoring a database from
    # a backup resets ids the same way, and would serve stale targets to real
    # users until the TTL expired.
    _clear_cache()
    yield
    _clear_cache()


def _clear_cache():
    from app import cache

    cache.reset()
    client = cache._get_client()
    if client is not None:
        for key in client.scan_iter("link:*"):
            client.delete(key)
        client.delete("clicks:pending")


@pytest.fixture
def client():
    # follow_redirects=False so we can assert on the 307 itself.
    return TestClient(app, follow_redirects=False)
