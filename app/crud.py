"""Database operations, kept out of the route handlers so they stay testable."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import bots, cache, models, shortcode
from .config import settings


class AliasTaken(Exception):
    pass


class AliasReserved(Exception):
    pass


def create_link(
    db: Session,
    target_url: str,
    custom_alias: str | None = None,
    expires_at: datetime | None = None,
) -> models.Link:
    if custom_alias:
        if custom_alias.lower() in settings.reserved:
            raise AliasReserved(custom_alias)
        if get_link_by_code(db, custom_alias) is not None:
            raise AliasTaken(custom_alias)

    link = models.Link(
        target_url=target_url,
        short_code=custom_alias or "",  # placeholder; real code needs the id
        is_custom=bool(custom_alias),
        expires_at=expires_at,
    )
    db.add(link)
    db.flush()  # assigns link.id without committing

    if not custom_alias:
        if settings.shortcode_mode == "sequential":
            link.short_code = shortcode.encode(link.id + settings.id_offset)
        else:
            link.short_code = shortcode.obfuscate(link.id)

    db.commit()
    db.refresh(link)
    return link


def get_link_by_code(db: Session, code: str) -> models.Link | None:
    return db.scalar(select(models.Link).where(models.Link.short_code == code))


def list_links(db: Session, limit: int = 100) -> list[tuple[models.Link, int]]:
    """Links newest-first, each with its click count. One query, no N+1."""
    stmt = (
        select(models.Link, func.count(models.Click.id))
        .outerjoin(
            models.Click,
            (models.Click.link_id == models.Link.id) & models.Click.is_bot.is_(False),
        )
        .group_by(models.Link.id)
        .order_by(models.Link.created_at.desc())
        .limit(limit)
    )
    return [(link, count) for link, count in db.execute(stmt).all()]


def record_click(db: Session, link: models.Link, referrer: str | None, user_agent: str | None) -> None:
    db.add(
        models.Click(
            link_id=link.id,
            referrer=_clean_referrer(referrer),
            user_agent=user_agent,
            is_bot=bots.is_bot(user_agent),
        )
    )
    db.commit()


def _human_only(stmt, include_bots: bool):
    return stmt if include_bots else stmt.where(models.Click.is_bot.is_(False))


def count_clicks(db: Session, link_id: int, include_bots: bool = False) -> int:
    stmt = select(func.count(models.Click.id)).where(models.Click.link_id == link_id)
    return db.scalar(_human_only(stmt, include_bots)) or 0


def count_bot_clicks(db: Session, link_id: int) -> int:
    return db.scalar(
        select(func.count(models.Click.id)).where(
            models.Click.link_id == link_id, models.Click.is_bot.is_(True)
        )
    ) or 0


def clicks_by_day(db: Session, link_id: int, days: int = 30, include_bots: bool = False) -> list[dict]:
    """Daily click counts, with zero-filled gaps so the chart doesn't lie."""
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    stmt = select(models.Click.clicked_at).where(
        models.Click.link_id == link_id, models.Click.clicked_at >= since
    )
    rows = db.execute(_human_only(stmt, include_bots)).all()

    counts = Counter(row[0].date().isoformat() for row in rows)
    start = since.date()
    return [
        {"date": (start + timedelta(days=i)).isoformat(),
         "clicks": counts.get((start + timedelta(days=i)).isoformat(), 0)}
        for i in range(days)
    ]


def top_referrers(db: Session, link_id: int, limit: int = 10, include_bots: bool = False) -> list[dict]:
    stmt = (
        select(models.Click.referrer, func.count(models.Click.id).label("n"))
        .where(models.Click.link_id == link_id)
        .group_by(models.Click.referrer)
        .order_by(func.count(models.Click.id).desc())
        .limit(limit)
    )
    if not include_bots:
        stmt = stmt.where(models.Click.is_bot.is_(False))
    return [{"name": ref or "direct", "clicks": n} for ref, n in db.execute(stmt).all()]


def _clean_referrer(referrer: str | None) -> str | None:
    """Store the host only. Full referrer URLs are noisy and leak more than you need."""
    if not referrer:
        return None
    from urllib.parse import urlparse

    host = urlparse(referrer).netloc
    return host or None


def resolve(db: Session, code: str) -> dict | None:
    """Look up a code for the redirect path, cache first.

    Returns a plain dict rather than a Link so the cached and uncached paths
    have the same shape — otherwise callers end up branching on which one
    they got, which is how cache bugs start.
    """
    cached = cache.get_link(code)
    if cached is not None:
        return cached

    link = get_link_by_code(db, code)
    if link is None:
        return None

    cache.set_link(code, link.id, link.target_url, link.expires_at)
    return {
        "id": link.id,
        "target_url": link.target_url,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


def record_click_by_id(link_id: int, referrer: str | None, user_agent: str | None) -> None:
    """Write a click using its own session.

    Called from a background task, after the response has been sent, so it
    cannot reuse the request's session — that one is already closed.
    """
    from .database import SessionLocal

    with SessionLocal() as db:
        db.add(
            models.Click(
                link_id=link_id,
                referrer=_clean_referrer(referrer),
                user_agent=user_agent,
                is_bot=bots.is_bot(user_agent),
            )
        )
        db.commit()
