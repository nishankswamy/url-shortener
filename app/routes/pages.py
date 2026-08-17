from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import clickbuffer, crud
from ..config import settings
from ..database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", include_in_schema=False)
def home(request: Request, db: Session = Depends(get_db)):
    links = [
        {
            "short_code": link.short_code,
            "short_url": f"{settings.base_url}/{link.short_code}",
            "target_url": link.target_url,
            "clicks": count,
            "created_at": link.created_at,
            "expired": link.is_expired,
        }
        for link, count in crud.list_links(db, limit=50)
    ]
    return templates.TemplateResponse(request, "index.html", {"links": links})


@router.get("/health", include_in_schema=False)
def health():
    """Reports which protections are live, so a deploy that forgot to set
    API_KEYS is visible rather than silently open."""
    return {
        "status": "ok",
        "auth": "enabled" if settings.api_keys else "open",
        "cache": "enabled" if settings.redis_url else "disabled",
        "click_buffer": "on" if settings.click_buffer else "off",
        "pending_clicks": clickbuffer.pending(),
    }


@router.get("/s/{code}", include_in_schema=False)
def stats_page(code: str, request: Request, db: Session = Depends(get_db)):
    link = crud.get_link_by_code(db, code)
    if link is None:
        raise HTTPException(status_code=404, detail="No such link.")
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "link": link,
            "short_url": f"{settings.base_url}/{link.short_code}",
            "total": crud.count_clicks(db, link.id),
            "bot_clicks": crud.count_bot_clicks(db, link.id),
            "by_day": crud.clicks_by_day(db, link.id),
            "referrers": crud.top_referrers(db, link.id),
        },
    )


@router.get("/{code}", include_in_schema=False)
def follow(
    code: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """The hot path.

    Two deliberate choices:

    1. Resolution goes through the cache, so a hot link never touches the DB.
    2. The click is recorded *after* the response is sent. Analytics are not
       worth making the user wait for, and a failed insert should not turn a
       working redirect into a 500.
    """
    link = crud.resolve(db, code)
    if link is None:
        raise HTTPException(status_code=404, detail="No such link.")

    if _expired(link["expires_at"]):
        raise HTTPException(status_code=410, detail="This link has expired.")

    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")

    if settings.click_mode == "sync":
        clickbuffer.enqueue(link["id"], referrer, user_agent)
    else:
        background.add_task(clickbuffer.enqueue, link["id"], referrer, user_agent)

    # 307 not 301: browsers cache permanent redirects, which would silently
    # kill your click tracking on repeat visits.
    return RedirectResponse(link["target_url"], status_code=307)


def _expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    parsed = datetime.fromisoformat(expires_at)
    if parsed.tzinfo is None:  # SQLite hands back naive datetimes
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed < datetime.now(timezone.utc)
