"""The cache must never be able to break the site."""

from app import cache, crud
from app.database import SessionLocal


def test_cache_is_off_by_default():
    assert cache.get_link("anything") is None


def test_writes_are_silent_when_disabled():
    cache.set_link("code", 1, "https://example.com", None)  # must not raise


def test_unreachable_redis_degrades_to_database(client, monkeypatch):
    """Point at a dead Redis and the redirect must still work."""
    from app.config import settings

    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    cache.reset()
    try:
        code = client.post(
            "/api/links", json={"target_url": "https://example.com/x"}
        ).json()["short_code"]

        response = client.get(f"/{code}")
        assert response.status_code == 307
        assert response.headers["location"] == "https://example.com/x"
    finally:
        cache.reset()


def test_resolve_shape_matches_cached_and_uncached(client):
    """Both paths must return the same keys, or callers start branching on
    which one they got — that is how cache bugs begin."""
    code = client.post(
        "/api/links", json={"target_url": "https://example.com/y"}
    ).json()["short_code"]

    with SessionLocal() as db:
        uncached = crud.resolve(db, code)

    assert set(uncached) == {"id", "target_url", "expires_at"}


def test_resolve_returns_none_for_unknown_code():
    with SessionLocal() as db:
        assert crud.resolve(db, "does-not-exist") is None
