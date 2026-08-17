from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import crud
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
    return {"status": "ok"}


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
            "by_day": crud.clicks_by_day(db, link.id),
            "referrers": crud.top_referrers(db, link.id),
        },
    )


@router.get("/{code}", include_in_schema=False)
def follow(code: str, request: Request, db: Session = Depends(get_db)):
    """The hot path. Keep it cheap — one indexed lookup, one insert."""
    link = crud.get_link_by_code(db, code)
    if link is None:
        raise HTTPException(status_code=404, detail="No such link.")
    if link.is_expired:
        raise HTTPException(status_code=410, detail="This link has expired.")

    crud.record_click(
        db,
        link,
        referrer=request.headers.get("referer"),
        user_agent=request.headers.get("user-agent"),
    )
    # 307 not 301: browsers cache permanent redirects, which would silently
    # kill your click tracking on repeat visits.
    return RedirectResponse(link.target_url, status_code=307)
