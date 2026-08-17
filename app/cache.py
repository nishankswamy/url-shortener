"""Redis cache for the redirect hot path.

Every design choice here is about one thing: the cache must never be able to
take the site down. If Redis is unreachable, slow, or returns garbage, the
request falls through to Postgres and the user sees a working redirect.

Cached values are immutable — a link's target never changes after creation —
so there is no invalidation problem. Expiry is handled by storing `expires_at`
alongside the target and checking it on read.
"""

import json
import logging

from .config import settings

log = logging.getLogger(__name__)

_client = None
_unavailable = False


def _get_client():
    """Lazily connect. One failure disables the cache for the process."""
    global _client, _unavailable

    if _unavailable or not settings.redis_url:
        return None
    if _client is not None:
        return _client

    try:
        import redis

        # Short timeouts on purpose: a slow cache is worse than no cache,
        # because it adds latency to a request that still has to hit the DB.
        _client = redis.Redis.from_url(
            settings.redis_url,
            socket_timeout=0.05,
            socket_connect_timeout=0.05,
            decode_responses=True,
        )
        _client.ping()
        return _client
    except Exception as exc:  # noqa: BLE001 — any failure means "no cache"
        log.warning("cache disabled: %s", exc)
        _unavailable = True
        return None


def get_link(code: str) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(f"link:{code}")
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        log.warning("cache read failed for %s: %s", code, exc)
        return None


def set_link(code: str, link_id: int, target_url: str, expires_at) -> None:
    client = _get_client()
    if client is None:
        return
    payload = {
        "id": link_id,
        "target_url": target_url,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    try:
        client.setex(f"link:{code}", settings.cache_ttl, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        log.warning("cache write failed for %s: %s", code, exc)


def reset() -> None:
    """Drop the connection. Used by tests to re-read config."""
    global _client, _unavailable
    _client = None
    _unavailable = False
