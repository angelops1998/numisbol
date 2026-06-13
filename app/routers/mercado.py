import os, shutil, uuid, json
from typing import Optional
from datetime import datetime, timezone
from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, extract
import sqlalchemy as sa
from ..database import get_db
from ..models.listing import Listing, ListingType, ListingStatus
from ..models.coin import Coin
from ..models.user import User
from ..auth import get_current_user, get_current_user_optional
from ..routers.coleccion import COUNTRIES, CONDITIONS as CONDITION_GROUPS

router = APIRouter(prefix="/mercado", tags=["mercado"])
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
    verificado: str = "",
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
    if verificado == "1":
        query = query.join(User, Listing.user_id == User.id).filter(User.is_verified == True)

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
               "precio_max": precio_max, "pais": pais, "orden": orden, "verificado": verificado}

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
    base = db.query(Listing).filter(
        Listing.user_id == user.id,
        Listing.status != ListingStatus.vendido
    ).order_by(Listing.created_at.desc())
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
    usd_rate: str = Form(""),
    cost: str = Form(""),
    cost_currency: str = Form("BOB"),
    cost_usd_rate: str = Form(""),
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
        usd_rate       = to_dec(usd_rate),
        cost           = to_dec(cost),
        cost_currency  = cost_currency if cost_currency in ("BOB", "USD") else "BOB",
        cost_usd_rate  = to_dec(cost_usd_rate),
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
    return RedirectResponse(url="/mercado/mis-publicaciones", status_code=302)


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
    usd_rate: str = Form(""),
    cost: str = Form(""),
    cost_currency: str = Form("BOB"),
    cost_usd_rate: str = Form(""),
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
    listing.usd_rate      = to_dec(usd_rate)
    listing.cost          = to_dec(cost)
    listing.cost_currency = cost_currency if cost_currency in ("BOB", "USD") else "BOB"
    listing.cost_usd_rate = to_dec(cost_usd_rate)
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
    uid = user.id

    # ── Conteos (SQL COUNT) ──────────────────────────────────
    from sqlalchemy import case as sa_case
    counts = db.query(
        func.count().label("total"),
        func.count(sa_case((Listing.status == ListingStatus.activo,    1))).label("activos"),
        func.count(sa_case((Listing.status == ListingStatus.reservado, 1))).label("reservados"),
        func.count(sa_case((Listing.status == ListingStatus.vendido,   1))).label("vendidos"),
    ).filter(Listing.user_id == uid).one()
    total, activos, reservados, vendidos = counts.total, counts.activos, counts.reservados, counts.vendidos

    # ── Ingresos: SUM simple en SQL; per-rate en Python con columnas mínimas ──
    def _vp(l): return float(l.sale_price_actual or l.price or 0)

    sold_rows = db.query(
        Listing.currency, Listing.sale_price_actual, Listing.price,
        Listing.usd_rate, Listing.sold_at
    ).filter(Listing.user_id == uid, Listing.status == ListingStatus.vendido).all()

    ingreso_bob        = sum(_vp(l) for l in sold_rows if (l.currency or "BOB") == "BOB")
    ingreso_usd        = sum(_vp(l) for l in sold_rows if l.currency == "USD")
    ingreso_usd_en_bob = sum(_vp(l) * float(l.usd_rate) for l in sold_rows if l.currency == "USD" and l.usd_rate)
    ingreso_bob_en_usd = sum(_vp(l) / float(l.usd_rate) for l in sold_rows if (l.currency or "BOB") == "BOB" and l.usd_rate)
    ingreso_total_bob  = ingreso_bob + ingreso_usd_en_bob

    # ── Costos: SQL SUM para casos simples; per-rate en Python ──
    costo_bob = float(db.query(func.coalesce(func.sum(Listing.cost), 0)).filter(
        Listing.user_id == uid, Listing.cost != None,
        sa.or_(Listing.cost_currency == "BOB", Listing.cost_currency == None)
    ).scalar())
    costo_usd = float(db.query(func.coalesce(func.sum(Listing.cost), 0)).filter(
        Listing.user_id == uid, Listing.cost != None, Listing.cost_currency == "USD"
    ).scalar())

    cost_rows = db.query(
        Listing.cost, Listing.cost_currency, Listing.cost_usd_rate
    ).filter(Listing.user_id == uid, Listing.cost != None).all()

    costo_usd_en_bob = sum(float(l.cost) * float(l.cost_usd_rate) for l in cost_rows if l.cost_currency == "USD" and l.cost_usd_rate)
    costo_bob_en_usd = sum(float(l.cost) / float(l.cost_usd_rate) for l in cost_rows if (l.cost_currency or "BOB") == "BOB" and l.cost_usd_rate)
    costo_total_bob  = costo_bob + costo_usd_en_bob
    ganancia_bob     = ingreso_total_bob - costo_total_bob if (ingreso_total_bob or costo_total_bob) else None

    # Para compatibilidad con el resto del código que usa sold_listings
    sold_listings = sold_rows

    # Ventas por mes — los 12 meses del año actual
    anio_actual = datetime.now(timezone.utc).year
    MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

    # Calcular por mes desde sold_listings (para poder usar usd_rate individual)
    mes_data = {}
    for l in sold_listings:
        if not l.sold_at:
            continue
        sold_year = l.sold_at.year if hasattr(l.sold_at, 'year') else l.sold_at.date().year
        if sold_year != anio_actual:
            continue
        m = l.sold_at.month
        val = float(l.sale_price_actual or l.price or 0)
        if m not in mes_data:
            mes_data[m] = {"n": 0, "bob": 0.0, "usd": 0.0, "total_bob": 0.0}
        mes_data[m]["n"] += 1
        if (l.currency or "BOB") == "BOB":
            mes_data[m]["bob"] += val
            mes_data[m]["total_bob"] += val
        else:
            mes_data[m]["usd"] += val
            if l.usd_rate:
                mes_data[m]["total_bob"] += val * float(l.usd_rate)

    ventas_mes = [
        {"mes": MESES[i],
         "n":         mes_data.get(i+1, {}).get("n", 0),
         "bob":       mes_data.get(i+1, {}).get("bob", 0.0),
         "usd":       mes_data.get(i+1, {}).get("usd", 0.0),
         "total_bob": mes_data.get(i+1, {}).get("total_bob", 0.0),
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
        "ingreso_usd_en_bob": ingreso_usd_en_bob, "ingreso_total_bob": ingreso_total_bob,
        "ingreso_bob_en_usd": ingreso_bob_en_usd,
        "costo_bob": costo_bob, "costo_usd": costo_usd,
        "costo_usd_en_bob": costo_usd_en_bob, "costo_total_bob": costo_total_bob,
        "costo_bob_en_usd": costo_bob_en_usd,
        "ganancia_bob": ganancia_bob,
        "ventas_mes": ventas_mes,
        "anio_actual": anio_actual,
        "por_item": por_item,
        "por_material": por_material,
        "ultimos_vendidos": ultimos_vendidos,
    })


# ── Reporte de ventas ────────────────────────────────────────
@router.get("/mis-publicaciones/ventas", response_class=HTMLResponse)
async def reporte_ventas(
    request: Request,
    q: str = "",
    desde: str = "",
    hasta: str = "",
    moneda: str = "",
    pagina: int = 1,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    PER_VENTAS = 15

    query = db.query(Listing).filter(
        Listing.user_id == user.id,
        Listing.status == ListingStatus.vendido,
    )
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    if moneda in ("BOB", "USD"):
        query = query.filter(Listing.currency == moneda)
    if desde:
        try:
            query = query.filter(Listing.sold_at >= datetime.strptime(desde, "%Y-%m-%d"))
        except ValueError:
            pass
    if hasta:
        try:
            query = query.filter(Listing.sold_at <= datetime.strptime(hasta, "%Y-%m-%d").replace(hour=23, minute=59))
        except ValueError:
            pass

    has_filter = bool(q or desde or hasta or moneda)

    if not has_filter:
        return templates.TemplateResponse(request, "mercado/ventas.html", {
            "user": user, "ventas": [], "total": 0, "pagina": 1, "per_page": PER_VENTAS,
            "q": q, "desde": desde, "hasta": hasta, "moneda": moneda,
            "has_filter": False,
            "tot_bob": 0, "tot_usd": 0, "tot_usd_en_bob": 0,
            "tot_costo_bob": 0, "tot_costo_usd": 0, "tot_costo_usd_en_bob": 0,
            "tot_ingreso": 0, "tot_costo": 0, "tot_ganancia": None,
        })

    total = query.count()
    pagina = max(1, min(pagina, max(1, -(-total // PER_VENTAS))))
    ventas = query.order_by(Listing.sold_at.desc().nullslast()).offset((pagina - 1) * PER_VENTAS).limit(PER_VENTAS).all()

    # Totales con SQL SUM para los casos simples
    from sqlalchemy import case as sa_case
    price_expr = sa.func.coalesce(Listing.sale_price_actual, Listing.price, 0)

    tot_bob = float(query.filter(sa.or_(Listing.currency == "BOB", Listing.currency == None))
                   .with_entities(sa.func.coalesce(sa.func.sum(price_expr), 0)).scalar())
    tot_usd = float(query.filter(Listing.currency == "USD")
                   .with_entities(sa.func.coalesce(sa.func.sum(price_expr), 0)).scalar())
    tot_costo_bob = float(query.filter(Listing.cost != None, sa.or_(Listing.cost_currency == "BOB", Listing.cost_currency == None))
                         .with_entities(sa.func.coalesce(sa.func.sum(Listing.cost), 0)).scalar())
    tot_costo_usd = float(query.filter(Listing.cost != None, Listing.cost_currency == "USD")
                         .with_entities(sa.func.coalesce(sa.func.sum(Listing.cost), 0)).scalar())

    # Per-rate: solo columnas necesarias
    rate_rows = query.filter(sa.or_(Listing.currency == "USD", Listing.usd_rate != None))\
                     .with_entities(Listing.currency, Listing.sale_price_actual, Listing.price, Listing.usd_rate).all()
    cost_rate_rows = query.filter(Listing.cost != None, Listing.cost_usd_rate != None)\
                          .with_entities(Listing.cost, Listing.cost_currency, Listing.cost_usd_rate).all()

    tot_usd_en_bob     = sum(float(l.sale_price_actual or l.price or 0) * float(l.usd_rate) for l in rate_rows if l.currency == "USD" and l.usd_rate)
    tot_costo_usd_en_bob = sum(float(l.cost) * float(l.cost_usd_rate) for l in cost_rate_rows if l.cost_currency == "USD" and l.cost_usd_rate)

    tot_ingreso = tot_bob + tot_usd_en_bob
    tot_costo   = tot_costo_bob + tot_costo_usd_en_bob
    tot_ganancia = tot_ingreso - tot_costo if (tot_ingreso or tot_costo) else None

    return templates.TemplateResponse(request, "mercado/ventas.html", {
        "user": user,
        "ventas": ventas,
        "total": total, "pagina": pagina, "per_page": PER_VENTAS,
        "q": q, "desde": desde, "hasta": hasta, "moneda": moneda,
        "has_filter": True,
        "tot_bob": tot_bob, "tot_usd": tot_usd, "tot_usd_en_bob": tot_usd_en_bob,
        "tot_costo_bob": tot_costo_bob, "tot_costo_usd": tot_costo_usd,
        "tot_costo_usd_en_bob": tot_costo_usd_en_bob,
        "tot_ingreso": tot_ingreso, "tot_costo": tot_costo, "tot_ganancia": tot_ganancia,
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
