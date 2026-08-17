"""Batched click writes.

One INSERT per redirect is the wrong shape at volume: the write is tiny, the
per-statement overhead is not, and a spike in traffic becomes a spike in
database connections. Buffering into a Redis list and flushing in batches turns
N inserts into N/batch_size, and the redirect path stops touching the database
entirely.

The trade is durability. A click sitting in the buffer when the process dies is
lost. That is an acceptable loss for analytics and an unacceptable one for
anything billable, which is exactly the distinction to be explicit about rather
than discover later.

Failure behaviour: if Redis is unreachable the click is written directly. The
buffer is an optimisation, never a dependency.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from . import bots, cache, crud
from .config import settings
from .database import SessionLocal
from .models import Click

log = logging.getLogger(__name__)

KEY = "clicks:pending"


def enqueue(link_id: int, referrer: str | None, user_agent: str | None) -> None:
    """Buffer a click, or write it directly if the buffer is unavailable."""
    client = cache._get_client() if settings.click_buffer else None

    if client is None:
        crud.record_click_by_id(link_id, referrer, user_agent)
        return

    payload = json.dumps(
        {
            "link_id": link_id,
            "referrer": referrer,
            "user_agent": user_agent,
            "clicked_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        client.rpush(KEY, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("buffer write failed, writing directly: %s", exc)
        crud.record_click_by_id(link_id, referrer, user_agent)


def flush() -> int:
    """Drain the buffer into the database. Returns rows written.

    Pops before inserting, so a crash mid-flush loses that batch rather than
    double-counting it. For analytics, under-counting beats double-counting —
    the reverse choice needs an idempotency key on every click.
    """
    client = cache._get_client() if settings.click_buffer else None
    if client is None:
        return 0

    try:
        pipe = client.pipeline()
        pipe.lrange(KEY, 0, settings.flush_batch_size - 1)
        pipe.ltrim(KEY, settings.flush_batch_size, -1)
        raw_items, _ = pipe.execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("buffer read failed: %s", exc)
        return 0

    if not raw_items:
        return 0

    clicks = []
    for raw in raw_items:
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("dropping malformed buffered click: %r", raw[:100])
            continue

        clicks.append(
            Click(
                link_id=item["link_id"],
                clicked_at=datetime.fromisoformat(item["clicked_at"]),
                referrer=crud._clean_referrer(item.get("referrer")),
                user_agent=item.get("user_agent"),
                is_bot=bots.is_bot(item.get("user_agent")),
            )
        )

    if not clicks:
        return 0

    with SessionLocal() as db:
        db.add_all(clicks)
        db.commit()

    return len(clicks)


def pending() -> int:
    client = cache._get_client() if settings.click_buffer else None
    if client is None:
        return 0
    try:
        return client.llen(KEY)
    except Exception:  # noqa: BLE001
        return 0


async def flush_loop(stop: asyncio.Event) -> None:
    """Background flusher. Runs until told to stop, then drains what's left."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.flush_interval)
        except asyncio.TimeoutError:
            pass

        try:
            # flush() is blocking; keep it off the event loop.
            written = await asyncio.to_thread(flush)
            if written:
                log.info("flushed %d clicks", written)
        except Exception as exc:  # noqa: BLE001 — the loop must never die
            log.exception("flush failed: %s", exc)

    # Drain on shutdown so a clean restart doesn't lose the buffer.
    while await asyncio.to_thread(flush):
        pass
