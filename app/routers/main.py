from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db
from ..auth import get_current_user_optional
from ..models.anuncio import Anuncio
from ..models.coin import Coin
from ..models.user import User
from ..models.listing import Listing, ListingStatus
from ..models.blog import BlogPost

router = APIRouter(tags=["main"])
templates = Jinja2Templates(directory="app/templates")


def _pg_estimate(db: Session, table: str) -> int:
    """Estimación rápida de filas vía pg_class (no hace full scan)."""
    row = db.execute(text(
        "SELECT reltuples::bigint FROM pg_class WHERE relname = :t"
    ), {"t": table}).fetchone()
    return int(row[0]) if row and row[0] > 0 else 0


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)

    anuncios = (
        db.query(Anuncio)
        .filter(Anuncio.activo == True)
        .order_by(Anuncio.orden, Anuncio.id)
        .all()
    )

    # Estimaciones vía pg_class — O(1) en vez de full scan
    stats = {
        "monedas":        _pg_estimate(db, "coins"),
        "coleccionistas": _pg_estimate(db, "users"),
        "en_venta":       db.query(Listing).filter(Listing.status == ListingStatus.activo).count(),
        "articulos":      db.query(BlogPost).filter(BlogPost.publicado == True).count(),
    }

    return templates.TemplateResponse(request, "home.html", {
        "user": user,
        "anuncios": anuncios,
        "stats": stats,
    })
