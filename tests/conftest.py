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
    yield


@pytest.fixture
def client():
    # follow_redirects=False so we can assert on the 307 itself.
    return TestClient(app, follow_redirects=False)
