from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.coin import Coin
from ..auth import get_current_user_optional

router = APIRouter(prefix="/moneda", tags=["moneda-publica"])


@router.get("/{coin_id}", response_class=HTMLResponse)
async def moneda_publica(coin_id: int, request: Request, db: Session = Depends(get_db)):
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.is_public == True).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada o no es pública")
    user = get_current_user_optional(request, db)
    return templates.TemplateResponse(request, "moneda/publica.html", {
        "coin": coin,
        "user": user,
    })
