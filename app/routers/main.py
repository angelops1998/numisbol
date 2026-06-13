from ..templates_config import templates
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
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

    from ..models.user import User
    from ..models.coin import Coin
    from sqlalchemy import func
    stats = {
        "monedas":        db.query(func.count(Coin.id)).scalar(),
        "coleccionistas": db.query(func.count(User.id)).scalar(),
        "en_venta":       db.query(Listing).filter(Listing.status == ListingStatus.activo).count(),
        "articulos":      db.query(BlogPost).filter(BlogPost.publicado == True).count(),
    }

    return templates.TemplateResponse(request, "home.html", {
        "user": user,
        "anuncios": anuncios,
        "stats": stats,
    })
