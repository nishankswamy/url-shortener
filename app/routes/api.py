import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api", tags=["links"])


def _to_out(link, click_count: int) -> schemas.LinkOut:
    return schemas.LinkOut(
        short_code=link.short_code,
        short_url=f"{settings.base_url}/{link.short_code}",
        target_url=link.target_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
        click_count=click_count,
    )


@router.post("/links", response_model=schemas.LinkOut, status_code=201)
def create_link(payload: schemas.LinkCreate, db: Session = Depends(get_db)):
    try:
        link = crud.create_link(
            db,
            target_url=str(payload.target_url),
            custom_alias=payload.custom_alias,
            expires_at=payload.expires_at,
        )
    except crud.AliasTaken:
        raise HTTPException(status_code=409, detail="That alias is already in use.")
    except crud.AliasReserved:
        raise HTTPException(status_code=400, detail="That alias is reserved.")
    return _to_out(link, 0)


@router.get("/links", response_model=list[schemas.LinkOut])
def list_links(db: Session = Depends(get_db)):
    return [_to_out(link, count) for link, count in crud.list_links(db)]


@router.get("/links/{code}/stats", response_model=schemas.LinkStats)
def link_stats(code: str, db: Session = Depends(get_db)):
    link = crud.get_link_by_code(db, code)
    if link is None:
        raise HTTPException(status_code=404, detail="No such link.")

    total = crud.count_clicks(db, link.id)
    return schemas.LinkStats(
        link=_to_out(link, total),
        total_clicks=total,
        clicks_by_day=crud.clicks_by_day(db, link.id),
        top_referrers=crud.top_referrers(db, link.id),
    )


@router.get("/links/{code}/qr.png", response_class=Response, responses={200: {"content": {"image/png": {}}}})
def link_qr(code: str, db: Session = Depends(get_db)):
    """QR for the short URL. Generated on the fly — it's a few ms and the
    result is fully determined by the code, so let the CDN cache it."""
    import qrcode

    if crud.get_link_by_code(db, code) is None:
        raise HTTPException(status_code=404, detail="No such link.")

    img = qrcode.make(f"{settings.base_url}/{code}", box_size=8, border=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return Response(
        buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
