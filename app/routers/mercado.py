import os, shutil, uuid, json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, extract
import sqlalchemy as sa
from ..database import get_db
from ..models.listing import Listing, ListingType, ListingStatus
from ..models.coin import Coin
from ..auth import get_current_user, get_current_user_optional
from ..routers.coleccion import COUNTRIES, CONDITIONS as CONDITION_GROUPS

router = APIRouter(prefix="/mercado", tags=["mercado"])
templates = Jinja2Templates(directory="app/templates")
PER_PAGE = 20

UPLOAD_DIR = "app/static/img/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CONDITIONS = [c for _, items in CONDITION_GROUPS for c in items]


def save_upload(file: UploadFile) -> Optional[str]:
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return f"/static/img/uploads/{filename}"


# ── Explorar mercado ─────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def mercado(
    request: Request,
    q: str = "",
    tipo: str = "",
    condicion: str = "",
    precio_max: str = "",
    pais: str = "",
    orden: str = "reciente",
    pagina: int = 1,
    db: Session = Depends(get_db),
):
    user = get_current_user_optional(request, db)
    if not user:
        return templates.TemplateResponse(request, "mercado/acceso_requerido.html", {
            "user": None,
        }, status_code=200)

    query = db.query(Listing).filter(Listing.status == ListingStatus.activo)

    if q:
        query = query.filter(or_(
            Listing.title.ilike(f"%{q}%"),
            Listing.coin_name.ilike(f"%{q}%"),
            Listing.coin_country.ilike(f"%{q}%"),
            Listing.description.ilike(f"%{q}%"),
        ))
    if tipo:
        query = query.filter(Listing.listing_type == tipo)
    if condicion:
        query = query.filter(Listing.coin_condition == condicion)
    if pais:
        query = query.filter(Listing.coin_country.ilike(f"%{pais}%"))
    if precio_max.replace(".", "").isdigit():
        query = query.filter(Listing.price <= float(precio_max))

    if orden == "precio_asc":
        query = query.order_by(Listing.price.asc().nullslast())
    elif orden == "precio_desc":
        query = query.order_by(Listing.price.desc().nullslast())
    else:
        query = query.order_by(Listing.created_at.desc())

    total = query.count()

    pagina = max(1, pagina)
    total_paginas = max(1, -(-total // PER_PAGE))
    pagina = min(pagina, total_paginas)
    listings = query.offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()

    filters = {"q": q, "tipo": tipo, "condicion": condicion,
               "precio_max": precio_max, "pais": pais, "orden": orden}

    return templates.TemplateResponse(request, "mercado/lista.html", {
        "user": user,
        "listings": listings,
        "total": total,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "filters": filters,
        "tipos": list(ListingType),
        "conditions": CONDITIONS,
        "countries": COUNTRIES,
    })


# ── Mis publicaciones ────────────────────────────────────────
@router.get("/mis-publicaciones", response_class=HTMLResponse)
async def mis_publicaciones(request: Request, pagina: int = 1, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    base = db.query(Listing).filter(Listing.user_id == user.id).order_by(Listing.created_at.desc())
    total = base.count()
    pagina = max(1, min(pagina, max(1, -(-total // PER_PAGE))))
    listings = base.offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()
    return templates.TemplateResponse(request, "mercado/mis_publicaciones.html", {
        "user": user, "listings": listings,
        "total": total, "pagina": pagina,
        "total_paginas": max(1, -(-total // PER_PAGE)),
    })


# ── Publicar anuncio ─────────────────────────────────────────
@router.get("/publicar", response_class=HTMLResponse)
async def publicar_page(request: Request, desde_coin: int = 0, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    coin_origen = None
    if desde_coin:
        coin_origen = db.query(Coin).filter(Coin.id == desde_coin, Coin.user_id == user.id).first()

    return templates.TemplateResponse(request, "mercado/form.html", {
        "user": user,
        "listing": None,
        "coin_origen": coin_origen,
        "conditions": CONDITION_GROUPS,
        "tipos": list(ListingType),
        "action": "/mercado/publicar",
        "title": "Publicar anuncio",
    })


@router.post("/publicar", response_class=HTMLResponse)
async def publicar_post(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    listing_type: str = Form("venta"),
    price: str = Form(""),
    currency: str = Form("BOB"),
    item_type: str = Form("moneda"),
    coin_id: str = Form(""),
    coin_name: str = Form(""),
    coin_year: str = Form(""),
    coin_country: str = Form(""),
    coin_condition: str = Form(""),
    coin_material: str = Form(""),
    image: UploadFile = File(None),
    image_back: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    errors = []

    if not title.strip():
        errors.append("El título es obligatorio.")
    if listing_type in ("venta", "ambos") and not price.strip():
        errors.append("El precio es obligatorio para publicaciones de venta.")

    if errors:
        class _Draft:
            pass
        draft = _Draft()
        draft.title         = title
        draft.description   = description
        draft.listing_type  = type('_', (), {'value': listing_type})()
        draft.price         = price
        draft.currency      = currency
        draft.item_type     = item_type
        draft.coin_name     = coin_name
        draft.coin_year     = coin_year
        draft.coin_country  = coin_country
        draft.coin_condition = coin_condition
        draft.coin_material  = coin_material
        draft.image_url      = None
        draft.image_back_url = None
        draft.status         = type('_', (), {'value': 'activo'})()
        coin_origen_draft = None
        if coin_id.strip():
            coin_origen_draft = db.query(Coin).filter(Coin.id == int(coin_id), Coin.user_id == user.id).first()
        return templates.TemplateResponse(request, "mercado/form.html", {
            "user": user, "errors": errors, "listing": draft,
            "coin_origen": coin_origen_draft, "conditions": CONDITION_GROUPS, "tipos": list(ListingType),
            "action": "/mercado/publicar", "title": "Publicar anuncio",
        }, status_code=422)

    def to_int(v): return int(v) if str(v).strip().isdigit() else None
    def to_dec(v):
        try: return float(str(v).strip()) if str(v).strip() else None
        except: return None

    # Si seleccionó una moneda de su colección, copiar datos
    linked_coin = None
    if coin_id and str(coin_id).isdigit():
        linked_coin = db.query(Coin).filter(Coin.id == int(coin_id), Coin.user_id == user.id).first()

    img_url  = save_upload(image)
    img_back = save_upload(image_back)

    item_type = item_type if item_type in ("moneda", "billete") else "moneda"
    listing = Listing(
        user_id        = user.id,
        coin_id        = linked_coin.id if linked_coin else None,
        item_type      = item_type,
        title          = title.strip(),
        description    = description.strip() or None,
        listing_type   = ListingType(listing_type) if listing_type in ListingType._value2member_map_ else ListingType.venta,
        price          = to_dec(price),
        currency       = currency if currency in ("BOB", "USD") else "BOB",
        coin_name      = (linked_coin.name if linked_coin else coin_name.strip()) or None,
        coin_year      = linked_coin.year if linked_coin else to_int(coin_year),
        coin_country   = (linked_coin.country if linked_coin else coin_country.strip()) or None,
        coin_condition = (linked_coin.condition if linked_coin and linked_coin.condition else coin_condition) or None,
        coin_material  = (linked_coin.material if linked_coin else coin_material.strip()) or None,
        image_url      = img_url or (linked_coin.image_url if linked_coin else None),
        image_back_url = img_back or (linked_coin.image_back_url if linked_coin else None),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return RedirectResponse(url=f"/mercado/{listing.id}", status_code=302)


# ── Detalle de anuncio ───────────────────────────────────────
@router.get("/{listing_id}", response_class=HTMLResponse)
async def detalle(listing_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    # Otros anuncios del vendedor
    otros = (db.query(Listing)
             .filter(Listing.user_id == listing.user_id,
                     Listing.id != listing_id,
                     Listing.status == ListingStatus.activo)
             .limit(4).all())
    return templates.TemplateResponse(request, "mercado/detalle.html", {
        "user": user, "listing": listing, "otros": otros,
        "es_dueno": user and user.id == listing.user_id,
    })


# ── Editar anuncio ───────────────────────────────────────────
@router.get("/{listing_id}/editar", response_class=HTMLResponse)
async def editar_page(listing_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.user_id == user.id).first()
    if not listing:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "mercado/form.html", {
        "user": user, "listing": listing,
        "coin_origen": None, "conditions": CONDITION_GROUPS, "tipos": list(ListingType),
        "action": f"/mercado/{listing_id}/editar", "title": "Editar anuncio",
    })


@router.post("/{listing_id}/editar", response_class=HTMLResponse)
async def editar_post(
    listing_id: int, request: Request,
    title: str = Form(""),
    description: str = Form(""),
    listing_type: str = Form("venta"),
    price: str = Form(""),
    currency: str = Form("BOB"),
    item_type: str = Form("moneda"),
    coin_name: str = Form(""),
    coin_year: str = Form(""),
    coin_country: str = Form(""),
    coin_condition: str = Form(""),
    coin_material: str = Form(""),
    status: str = Form("activo"),
    image: UploadFile = File(None),
    image_back: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.user_id == user.id).first()
    if not listing:
        raise HTTPException(status_code=404)

    if not title.strip():
        return templates.TemplateResponse(request, "mercado/form.html", {
            "user": user, "errors": ["El título es obligatorio."], "listing": listing,
            "coin_origen": None, "conditions": CONDITION_GROUPS, "tipos": list(ListingType),
            "action": f"/mercado/{listing_id}/editar", "title": "Editar anuncio",
        }, status_code=422)

    def to_int(v): return int(v) if str(v).strip().isdigit() else None
    def to_dec(v):
        try: return float(str(v).strip()) if str(v).strip() else None
        except: return None

    listing.title         = title.strip()
    listing.description   = description.strip() or None
    listing.listing_type  = ListingType(listing_type) if listing_type in ListingType._value2member_map_ else ListingType.venta
    listing.item_type     = item_type if item_type in ("moneda", "billete") else "moneda"
    listing.price         = to_dec(price)
    listing.currency      = currency if currency in ("BOB", "USD") else "BOB"
    listing.coin_name     = coin_name.strip() or None
    listing.coin_year     = to_int(coin_year)
    listing.coin_country  = coin_country.strip() or None
    listing.coin_condition= coin_condition or None
    listing.coin_material = coin_material.strip() or None
    listing.status        = ListingStatus(status) if status in ListingStatus._value2member_map_ else ListingStatus.activo

    new_img  = save_upload(image)
    new_back = save_upload(image_back)
    if new_img:  listing.image_url      = new_img
    if new_back: listing.image_back_url = new_back

    db.commit()
    return RedirectResponse(url=f"/mercado/{listing_id}", status_code=302)


# ── Cambiar estado ───────────────────────────────────────────
@router.post("/{listing_id}/estado")
async def cambiar_estado(
    listing_id: int, request: Request,
    nuevo_estado: str = Form(...),
    sale_price_actual: str = Form(""),
    sale_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.user_id == user.id).first()
    if not listing:
        raise HTTPException(status_code=404)
    if nuevo_estado in [s.value for s in ListingStatus]:
        listing.status = nuevo_estado
        if nuevo_estado == "vendido":
            listing.sold_at = datetime.now(timezone.utc)
            try:
                listing.sale_price_actual = float(sale_price_actual) if sale_price_actual.strip() else None
            except ValueError:
                listing.sale_price_actual = None
            listing.sale_notes = sale_notes.strip() or None
        db.commit()
    return RedirectResponse(url=f"/mercado/{listing_id}", status_code=302)


# ── Estadísticas mis publicaciones ──────────────────────────
@router.get("/mis-publicaciones/estadisticas", response_class=HTMLResponse)
async def mis_publicaciones_stats(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    base = db.query(Listing).filter(Listing.user_id == user.id)

    total     = base.count()
    activos   = base.filter(Listing.status == ListingStatus.activo).count()
    reservados= db.query(Listing).filter(Listing.user_id == user.id, Listing.status == ListingStatus.reservado).count()
    vendidos  = db.query(Listing).filter(Listing.user_id == user.id, Listing.status == ListingStatus.vendido).count()

    # Ingresos de vendidos (precio real si existe, sino precio publicado)
    sold_listings = db.query(Listing).filter(
        Listing.user_id == user.id, Listing.status == ListingStatus.vendido
    ).all()

    ingreso_bob = sum(
        float(l.sale_price_actual or l.price or 0)
        for l in sold_listings if (l.currency or "BOB") == "BOB"
    )
    ingreso_usd = sum(
        float(l.sale_price_actual or l.price or 0)
        for l in sold_listings if l.currency == "USD"
    )

    # Ventas por mes — los 12 meses del año actual
    anio_actual = datetime.now(timezone.utc).year
    MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    rows = (db.query(
                extract('month', Listing.sold_at).label('m'),
                func.count().label('n'),
                func.sum(sa.case(
                    (Listing.currency == "BOB", sa.func.coalesce(Listing.sale_price_actual, Listing.price, 0)),
                    else_=0
                )).label('bob'),
                func.sum(sa.case(
                    (Listing.currency == "USD", sa.func.coalesce(Listing.sale_price_actual, Listing.price, 0)),
                    else_=0
                )).label('usd'),
            )
            .filter(
                Listing.user_id == user.id,
                Listing.status == ListingStatus.vendido,
                Listing.sold_at != None,
                extract('year', Listing.sold_at) == anio_actual,
            )
            .group_by('m').all())

    mes_data = {int(r.m): {"n": r.n, "bob": float(r.bob or 0), "usd": float(r.usd or 0)} for r in rows}
    ventas_mes = [
        {"mes": MESES[i], "n": mes_data.get(i+1, {}).get("n", 0),
         "bob": mes_data.get(i+1, {}).get("bob", 0.0),
         "usd": mes_data.get(i+1, {}).get("usd", 0.0),
         "activo": (i+1) == datetime.now(timezone.utc).month}
        for i in range(12)
    ]

    def top_group(col, limit=7):
        rows = (db.query(col.label('k'), func.count().label('n'))
                .filter(Listing.user_id == user.id, col != None, col != '')
                .group_by(col).order_by(func.count().desc()).limit(limit).all())
        lbls = [r.k or "" for r in rows]
        vals = [r.n for r in rows]
        return {"labels_json": json.dumps(lbls, ensure_ascii=False),
                "values_json": json.dumps(vals),
                "has_data": bool(lbls)}

    por_item     = top_group(Listing.item_type)
    por_material = top_group(Listing.coin_material)

    # Últimos vendidos
    ultimos_vendidos = (db.query(Listing)
                        .filter(Listing.user_id == user.id, Listing.status == ListingStatus.vendido)
                        .order_by(Listing.sold_at.desc().nullslast())
                        .limit(10).all())

    return templates.TemplateResponse(request, "mercado/estadisticas.html", {
        "user": user,
        "total": total, "activos": activos, "reservados": reservados, "vendidos": vendidos,
        "ingreso_bob": ingreso_bob, "ingreso_usd": ingreso_usd,
        "ventas_mes": ventas_mes,
        "anio_actual": anio_actual,
        "por_item": por_item,
        "por_material": por_material,
        "ultimos_vendidos": ultimos_vendidos,
    })


# ── Eliminar ─────────────────────────────────────────────────
@router.post("/{listing_id}/eliminar")
async def eliminar(listing_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.user_id == user.id).first()
    if not listing:
        raise HTTPException(status_code=404)
    db.delete(listing)
    db.commit()
    return RedirectResponse(url="/mercado/mis-publicaciones", status_code=302)
