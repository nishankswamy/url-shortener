"""Buffered click writes.

The unit tests run everywhere. The integration tests need a real Redis and skip
without one:

    REDIS_URL=redis://localhost:6379/0 pytest tests/test_clickbuffer.py
"""

import os

import pytest

from app import cache, clickbuffer, crud
from app.config import settings
from app.database import SessionLocal

REDIS_URL = os.getenv("REDIS_URL", "")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="no REDIS_URL configured")


def make_link() -> int:
    with SessionLocal() as db:
        return crud.create_link(db, target_url="https://example.com/buffered").id


# --- fallback behaviour, no Redis required ---------------------------------


def test_enqueue_writes_directly_when_buffer_is_off(clean_db):
    link_id = make_link()
    clickbuffer.enqueue(link_id, None, "Mozilla/5.0")

    with SessionLocal() as db:
        assert crud.count_clicks(db, link_id) == 1


def test_flush_is_a_noop_when_buffer_is_off():
    assert clickbuffer.flush() == 0
    assert clickbuffer.pending() == 0


def test_unreachable_redis_falls_back_to_direct_write(clean_db, monkeypatch):
    """A dead cache must cost a click's latency, not the click itself."""
    monkeypatch.setattr(settings, "click_buffer", True)
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    cache.reset()
    try:
        link_id = make_link()
        clickbuffer.enqueue(link_id, None, "Mozilla/5.0")

        with SessionLocal() as db:
            assert crud.count_clicks(db, link_id) == 1
    finally:
        cache.reset()


# --- integration ------------------------------------------------------------


@pytest.fixture
def buffered(monkeypatch):
    monkeypatch.setattr(settings, "click_buffer", True)
    monkeypatch.setattr(settings, "redis_url", REDIS_URL)
    cache.reset()
    client = cache._get_client()
    if client is not None:
        client.delete(clickbuffer.KEY)
    yield
    if client is not None:
        client.delete(clickbuffer.KEY)
    cache.reset()


@needs_redis
def test_clicks_buffer_before_they_land(clean_db, buffered):
    link_id = make_link()

    for _ in range(5):
        clickbuffer.enqueue(link_id, "https://news.ycombinator.com/x", "Mozilla/5.0")

    assert clickbuffer.pending() == 5
    with SessionLocal() as db:
        assert crud.count_clicks(db, link_id) == 0  # nothing written yet

    assert clickbuffer.flush() == 5
    assert clickbuffer.pending() == 0

    with SessionLocal() as db:
        assert crud.count_clicks(db, link_id) == 5


@needs_redis
def test_flush_respects_batch_size(clean_db, buffered, monkeypatch):
    monkeypatch.setattr(settings, "flush_batch_size", 3)
    link_id = make_link()
    for _ in range(7):
        clickbuffer.enqueue(link_id, None, "Mozilla/5.0")

    assert clickbuffer.flush() == 3
    assert clickbuffer.pending() == 4


@needs_redis
def test_buffered_clicks_keep_their_metadata(clean_db, buffered):
    link_id = make_link()
    clickbuffer.enqueue(link_id, "https://news.ycombinator.com/item?id=1", "Mozilla/5.0")
    clickbuffer.enqueue(link_id, None, "Googlebot/2.1")
    clickbuffer.flush()

    with SessionLocal() as db:
        assert crud.count_clicks(db, link_id) == 1  # the bot is excluded
        assert crud.count_bot_clicks(db, link_id) == 1
        assert crud.top_referrers(db, link_id) == [
            {"name": "news.ycombinator.com", "clicks": 1}
        ]


@needs_redis
def test_malformed_entries_are_dropped_not_fatal(clean_db, buffered):
    """One bad payload must not block every click behind it."""
    link_id = make_link()
    clickbuffer.enqueue(link_id, None, "Mozilla/5.0")
    cache._get_client().rpush(clickbuffer.KEY, "not json")
    clickbuffer.enqueue(link_id, None, "Mozilla/5.0")

    assert clickbuffer.flush() == 2
    with SessionLocal() as db:
        assert crud.count_clicks(db, link_id) == 2


@needs_redis
def test_flush_on_empty_buffer_is_free(clean_db, buffered):
    assert clickbuffer.flush() == 0
