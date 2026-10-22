from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, func
from ..database import get_db
from ..models.coin import Coin
from ..models.coin_like import CoinLike
from ..models.user import User
from ..auth import get_current_user_optional

router = APIRouter(prefix="/moneda", tags=["moneda-publica"])
galeria_router = APIRouter(prefix="/monedas", tags=["monedas-publicas"])

PER_PAGE = 24


def _publicas(db: Session):
    """Base: ítems públicos de usuarios activos."""
    return (
        db.query(Coin)
        .join(User, Coin.user_id == User.id)
        .filter(Coin.is_public == True, User.is_active.isnot(False))
    )


def _opciones(db: Session, col):
    """Valores distintos de una columna entre los ítems públicos."""
    rows = (
        db.query(col)
        .join(User, Coin.user_id == User.id)
        .filter(
            Coin.is_public == True, User.is_active.isnot(False),
            col.isnot(None), col != "",
        )
        .distinct()
        .order_by(col)
        .all()
    )
    return [r[0] for r in rows]


def _likes(db: Session, coins, user):
    """Likes de una lista de piezas: {coin_id: total} y los ids que le gustan al usuario."""
    ids = [c.id for c in coins]
    if not ids:
        return {}, set()
    totales = dict(
        db.query(CoinLike.coin_id, func.count(CoinLike.id))
        .filter(CoinLike.coin_id.in_(ids))
        .group_by(CoinLike.coin_id)
        .all()
    )
    mios = set()
    if user:
        mios = {
            r[0] for r in db.query(CoinLike.coin_id).filter(
                CoinLike.coin_id.in_(ids), CoinLike.user_id == user.id
            )
        }
    return totales, mios


# ── Galería de monedas públicas ──────────────────────────────
@galeria_router.get("", response_class=HTMLResponse)
async def galeria(
    request: Request,
    q: str = "",
    pais: str = "",
    material: str = "",
    categoria: str = "",
    tipo: str = "",
    coleccionista: str = "",
    anio_desde: str = "",
    anio_hasta: str = "",
    orden: str = "reciente",
    pagina: int = 1,
    db: Session = Depends(get_db),
):
    user = get_current_user_optional(request, db)

    query = _publicas(db).options(joinedload(Coin.owner))

    if q:
        query = query.filter(or_(
            Coin.name.ilike(f"%{q}%"),
            Coin.denomination.ilike(f"%{q}%"),
            Coin.mint.ilike(f"%{q}%"),
            Coin.country.ilike(f"%{q}%"),
            Coin.description.ilike(f"%{q}%"),
            Coin.currency_unit.ilike(f"%{q}%"),
            Coin.material.ilike(f"%{q}%"),
            Coin.assayer.ilike(f"%{q}%"),
        ))
    if pais:
        query = query.filter(Coin.country == pais)
    if material:
        query = query.filter(Coin.material == material)
    if categoria:
        query = query.filter(Coin.category == categoria)
    if tipo in ("moneda", "billete"):
        query = query.filter(Coin.tipo == tipo)
    if coleccionista:
        query = query.filter(User.username == coleccionista)
    if anio_desde.isdigit():
        query = query.filter(Coin.year >= int(anio_desde))
    if anio_hasta.isdigit():
        query = query.filter(Coin.year <= int(anio_hasta))

    total_publicas = _publicas(db).count()
    total_filtrado = query.count()

    if orden == "nombre":
        query = query.order_by(Coin.name)
    elif orden == "anio_asc":
        query = query.order_by(Coin.year.asc().nullslast())
    elif orden == "anio_desc":
        query = query.order_by(Coin.year.desc().nullslast())
    elif orden == "likes":
        conteo = (
            db.query(CoinLike.coin_id.label("coin_id"), func.count(CoinLike.id).label("n"))
            .group_by(CoinLike.coin_id)
            .subquery()
        )
        query = (
            query.outerjoin(conteo, conteo.c.coin_id == Coin.id)
            .order_by(func.coalesce(conteo.c.n, 0).desc(), Coin.created_at.desc(), Coin.id.desc())
        )
    else:
        query = query.order_by(Coin.created_at.desc(), Coin.id.desc())

    pagina = max(1, pagina)
    total_paginas = max(1, -(-total_filtrado // PER_PAGE))
    pagina = min(pagina, total_paginas)
    coins = query.offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()

    likes, mis_likes = _likes(db, coins, user)

    coleccionistas = (
        db.query(User.username, func.count(Coin.id).label("n"))
        .join(Coin, Coin.user_id == User.id)
        .filter(Coin.is_public == True, User.is_active.isnot(False))
        .group_by(User.username)
        .order_by(func.count(Coin.id).desc(), User.username)
        .all()
    )

    filters = {
        "q": q, "pais": pais, "material": material, "categoria": categoria,
        "tipo": tipo, "coleccionista": coleccionista,
        "anio_desde": anio_desde, "anio_hasta": anio_hasta, "orden": orden,
    }

    return templates.TemplateResponse(request, "moneda/galeria.html", {
        "user": user,
        "coins": coins,
        "total_publicas": total_publicas,
        "total_filtrado": total_filtrado,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "filters": filters,
        "countries": _opciones(db, Coin.country),
        "materials": _opciones(db, Coin.material),
        "categories": _opciones(db, Coin.category),
        "coleccionistas": coleccionistas,
        "likes": likes,
        "mis_likes": mis_likes,
    })


# ── Detalle público de un ítem ───────────────────────────────
@router.get("/{coin_id}", response_class=HTMLResponse)
async def moneda_publica(coin_id: int, request: Request, db: Session = Depends(get_db)):
    coin = (
        db.query(Coin)
        .options(joinedload(Coin.owner))
        .filter(Coin.id == coin_id, Coin.is_public == True)
        .first()
    )
    if not coin or (coin.owner and coin.owner.is_active is False):
        raise HTTPException(status_code=404, detail="Moneda no encontrada o no es pública")
    user = get_current_user_optional(request, db)

    otras = (
        _publicas(db)
        .filter(Coin.user_id == coin.user_id, Coin.id != coin.id)
        .order_by(Coin.created_at.desc())
        .limit(6)
        .all()
    )
    total_del_dueno = _publicas(db).filter(Coin.user_id == coin.user_id).count()

    likes, mis_likes = _likes(db, [coin] + otras, user)

    return templates.TemplateResponse(request, "moneda/publica.html", {
        "coin": coin,
        "user": user,
        "otras": otras,
        "total_del_dueno": total_del_dueno,
        "likes": likes,
        "mis_likes": mis_likes,
    })


# ── Me gusta (toggle) ────────────────────────────────────────
@router.post("/{coin_id}/like")
async def toggle_like(coin_id: int, request: Request, db: Session = Depends(get_db)):
    """Pone o quita el like del usuario actual. Responde JSON para el front."""
    user = get_current_user_optional(request, db)
    if not user:
        return JSONResponse(
            {"error": "login", "login_url": f"/auth/login?next=/moneda/{coin_id}"},
            status_code=401,
        )

    coin = _publicas(db).filter(Coin.id == coin_id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada o no es pública")
    if coin.user_id == user.id:
        return JSONResponse({"error": "propia"}, status_code=400)

    like = (
        db.query(CoinLike)
        .filter(CoinLike.coin_id == coin_id, CoinLike.user_id == user.id)
        .first()
    )
    if like:
        db.delete(like)
        liked = False
    else:
        db.add(CoinLike(coin_id=coin_id, user_id=user.id))
        liked = True

    try:
        db.commit()
    except IntegrityError:
        # Doble clic / pestañas en paralelo: el like ya existía. No es un error.
        db.rollback()
        liked = True

    total = (
        db.query(func.count(CoinLike.id)).filter(CoinLike.coin_id == coin_id).scalar() or 0
    )
    return {"liked": liked, "likes": total}
