from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import median

from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc
from ..database import get_db
from ..models.setting import AppSetting
from ..models.user import User
from ..models.listing import Listing
from ..models.coin import Coin
from ..models.pregunta import Pregunta, Respuesta
from ..models.serie import Serie, SerieVariante, SeriePrecio
from ..auth import get_current_user
from .. import tipo_cambio


def _require_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(_require_admin)])


def require_admin(request, db):
    """Helper para obtener el usuario admin dentro de los handlers."""
    user = get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


def get_setting(db: Session, key: str, default=None):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)

    try:
        from ..models.blog import BlogPost, BlogComentario
        n_blog = db.query(func.count(BlogPost.id)).scalar()
        n_comentarios = db.query(func.count(BlogComentario.id)).scalar()
    except Exception:
        n_blog = n_comentarios = 0

    stats = {
        "usuarios":      db.query(func.count(User.id)).scalar(),
        "verificados":   db.query(func.count(User.id)).filter(User.is_verified == True).scalar(),
        "monedas":       db.query(func.count(Coin.id)).scalar(),
        "publicaciones": db.query(func.count(Listing.id)).scalar(),
        "preguntas":     db.query(func.count(Pregunta.id)).scalar(),
        "respuestas":    db.query(func.count(Respuesta.id)).scalar(),
        "blog":          n_blog,
        "comentarios":   n_comentarios,
    }

    usuarios_recientes = db.query(User).order_by(User.created_at.desc()).limit(5).all()

    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "user": user, "stats": stats, "usuarios_recientes": usuarios_recientes,
    })


# ── Usuarios ───────────────────────────────────────────────────────────────────

@router.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = require_admin(request, db)
    query = db.query(User)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(User.username.ilike(like) | User.email.ilike(like))
    users = query.order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(request, "admin/usuarios.html", {
        "user": user, "users": users, "q": q,
        "saved": request.query_params.get("saved"),
    })


@router.post("/usuarios/{uid}/verificar")
async def toggle_verificado(uid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(status_code=404)
    u.is_verified = not u.is_verified
    db.commit()
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=302)


@router.post("/usuarios/{uid}/admin")
async def toggle_admin(uid: int, request: Request, db: Session = Depends(get_db)):
    current = require_admin(request, db)
    if uid == current.id:
        raise HTTPException(status_code=400, detail="No podés quitarte el rol de admin a vos mismo.")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(status_code=404)
    u.is_admin = not u.is_admin
    db.commit()
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=302)


@router.post("/usuarios/{uid}/eliminar")
async def eliminar_usuario(uid: int, request: Request, db: Session = Depends(get_db)):
    current = require_admin(request, db)
    if uid == current.id:
        raise HTTPException(status_code=400, detail="No podés eliminarte a vos mismo.")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(status_code=404)
    db.delete(u)
    db.commit()
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=302)


# ── Mercado ────────────────────────────────────────────────────────────────────

@router.get("/mercado", response_class=HTMLResponse)
async def admin_mercado(request: Request, q: str = "", pagina: int = 1, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    PER_PAGE = 20
    query = db.query(Listing)
    if q.strip():
        query = query.filter(Listing.title.ilike(f"%{q.strip()}%"))
    total = query.count()
    total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    pagina = max(1, min(pagina, total_paginas))
    listings = query.order_by(Listing.created_at.desc()).offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()
    return templates.TemplateResponse(request, "admin/mercado.html", {
        "user": user, "listings": listings, "total": total,
        "q": q, "pagina": pagina, "total_paginas": total_paginas,
        "saved": request.query_params.get("saved"),
    })


@router.post("/mercado/{lid}/eliminar")
async def admin_eliminar_listing(lid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    l = db.query(Listing).filter(Listing.id == lid).first()
    if l:
        db.delete(l)
        db.commit()
    return RedirectResponse(url="/admin/mercado?saved=1", status_code=302)


# ── Preguntas ──────────────────────────────────────────────────────────────────

@router.get("/preguntas", response_class=HTMLResponse)
async def admin_preguntas(request: Request, q: str = "", pagina: int = 1, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    PER_PAGE = 20
    query = db.query(Pregunta)
    if q.strip():
        query = query.filter(Pregunta.titulo.ilike(f"%{q.strip()}%"))
    total = query.count()
    total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    pagina = max(1, min(pagina, total_paginas))
    preguntas = query.order_by(Pregunta.created_at.desc()).offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()
    return templates.TemplateResponse(request, "admin/preguntas.html", {
        "user": user, "preguntas": preguntas, "total": total,
        "q": q, "pagina": pagina, "total_paginas": total_paginas,
        "saved": request.query_params.get("saved"),
    })


@router.post("/preguntas/{pid}/eliminar")
async def admin_eliminar_pregunta(pid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    p = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse(url="/admin/preguntas?saved=1", status_code=302)


# ── Blog ───────────────────────────────────────────────────────────────────────

@router.get("/blog", response_class=HTMLResponse)
async def admin_blog(request: Request, q: str = "", pagina: int = 1, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    from ..models.blog import BlogPost, BlogComentario
    PER_PAGE = 20
    query = db.query(BlogPost)
    if q.strip():
        query = query.filter(BlogPost.titulo.ilike(f"%{q.strip()}%"))
    total = query.count()
    total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    pagina = max(1, min(pagina, total_paginas))
    posts = query.order_by(BlogPost.created_at.desc()).offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()
    return templates.TemplateResponse(request, "admin/blog.html", {
        "user": user, "posts": posts, "total": total,
        "q": q, "pagina": pagina, "total_paginas": total_paginas,
        "saved": request.query_params.get("saved"),
    })


@router.post("/blog/{pid}/eliminar")
async def admin_eliminar_post(pid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    from ..models.blog import BlogPost
    p = db.query(BlogPost).filter(BlogPost.id == pid).first()
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse(url="/admin/blog?saved=1", status_code=302)


# ── Colección ─────────────────────────────────────────────────────────────────

@router.get("/coleccion", response_class=HTMLResponse)
async def admin_coleccion(request: Request, uid: int = 0, q: str = "", pagina: int = 1, vacios: int = 0, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    users = db.query(User).order_by(User.username).all()

    PER_PAGE = 20
    monedas = []
    total = 0
    total_paginas = 1
    usuario_sel = None
    resumen = []
    resumen_total = {"usuarios_con": 0, "n_items": 0, "piezas": 0, "vacios": 0}

    if uid:
        usuario_sel = db.query(User).filter(User.id == uid).first()
        if not usuario_sel:
            return RedirectResponse(url="/admin/coleccion", status_code=302)
        query = db.query(Coin).filter(Coin.user_id == uid)
        if q.strip():
            query = query.filter(Coin.name.ilike(f"%{q.strip()}%"))
        total = query.count()
        total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        pagina = max(1, min(pagina, total_paginas))
        monedas = query.order_by(Coin.created_at.desc()).offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()
    else:
        # Resumen: qué usuarios tienen ítems guardados en su inventario y cuántos
        rq = (
            db.query(
                User.id.label("id"),
                User.username.label("username"),
                User.full_name.label("full_name"),
                User.email.label("email"),
                User.is_verified.label("is_verified"),
                User.is_admin.label("is_admin"),
                func.count(Coin.id).label("items"),
                func.coalesce(func.sum(Coin.quantity), 0).label("piezas"),
                func.coalesce(func.sum(case((Coin.id != None, case((func.coalesce(Coin.tipo, "moneda") == "billete", 0), else_=1)), else_=0)), 0).label("monedas"),
                func.coalesce(func.sum(case((Coin.tipo == "billete", 1), else_=0)), 0).label("billetes"),
                func.coalesce(func.sum(case((Coin.is_public == True, 1), else_=0)), 0).label("publicas"),
                func.max(Coin.created_at).label("ultima"),
            )
            .outerjoin(Coin, Coin.user_id == User.id)
            .group_by(User.id)
        )
        if q.strip():
            like = f"%{q.strip()}%"
            rq = rq.filter(User.username.ilike(like) | User.email.ilike(like) | User.full_name.ilike(like))
        resumen = rq.order_by(desc("items"), User.username).all()
        resumen_total = {
            "usuarios_con": sum(1 for r in resumen if r.items),
            "n_items":      sum(int(r.items or 0) for r in resumen),
            "piezas":       sum(int(r.piezas or 0) for r in resumen),
            "vacios":       sum(1 for r in resumen if not r.items),
        }
        if not vacios:
            resumen = [r for r in resumen if r.items]

    return templates.TemplateResponse(request, "admin/coleccion.html", {
        "user": user, "users": users, "monedas": monedas,
        "usuario_sel": usuario_sel, "uid": uid, "q": q,
        "total": total, "pagina": pagina, "total_paginas": total_paginas,
        "resumen": resumen, "resumen_total": resumen_total, "vacios": vacios,
    })


# ── Series ─────────────────────────────────────────────────────────────────────

FUENTES_PRECIO = ["eBay", "MercadoLibre", "Facebook Marketplace", "Grupo de Facebook",
                  "WhatsApp", "Numista", "Heritage Auctions", "Subasta", "Tienda numismática"]
ESTADOS_PRECIO = ["MC (G)", "BC (F)", "MBC (VF)", "EBC (XF)", "SC (UNC)", "Proof"]


def _responder(request: Request, url: str, **extra):
    """Los formularios con JS piden JSON (cabecera X-Fetch) para guardar sin
    recargar la página; sin JS se sigue redirigiendo como siempre."""
    if request.headers.get("x-fetch") == "1":
        return JSONResponse({"ok": True, **extra})
    return RedirectResponse(url=url, status_code=302)


def _en_usd(p: SeriePrecio, rate: float | None) -> float | None:
    monto = float(p.monto)
    if p.moneda == "USD":
        return monto
    return monto / rate if rate else None


def _resumen_precios(precios, rate: float | None) -> dict | None:
    """Estimativo en USD: la mediana de los precios vendidos si hay alguno
    (son el dato más fiel); si no, la de las ofertas publicadas."""
    vendidos = [x for x in (_en_usd(p, rate) for p in precios if p.tipo == "vendido") if x is not None]
    ofertas  = [x for x in (_en_usd(p, rate) for p in precios if p.tipo != "vendido") if x is not None]
    base = vendidos or ofertas
    if not base:
        return None
    todos = vendidos + ofertas
    return {
        "estimado": median(base),
        "base": "vendido" if vendidos else "oferta",
        "n_base": len(base),
        "n": len(todos),
        "min": min(todos),
        "max": max(todos),
    }


@router.get("/series", response_class=HTMLResponse)
async def admin_series(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    series = db.query(Serie).order_by(Serie.orden, Serie.nombre).all()
    conteos = dict(
        db.query(SerieVariante.serie_id, func.count(SerieVariante.id))
        .group_by(SerieVariante.serie_id).all()
    )
    rate = tipo_cambio.get_rate(db)
    por_serie: dict[int, list] = {}
    for p in db.query(SeriePrecio).all():
        por_serie.setdefault(p.serie_id, []).append(p)
    resumenes = {sid: _resumen_precios(ps, rate) for sid, ps in por_serie.items()}
    return templates.TemplateResponse(request, "admin/series.html", {
        "user": user, "series": series, "conteos": conteos,
        "resumenes": resumenes, "rate": rate,
        "total_variantes": sum(conteos.values()),
        "total_precios": sum(len(ps) for ps in por_serie.values()),
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.post("/series")
async def admin_crear_serie(
    request: Request,
    nombre: str = Form(""),
    descripcion: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse(url="/admin/series?error=nombre", status_code=302)
    if db.query(Serie).filter(func.lower(Serie.nombre) == nombre.lower()).first():
        return RedirectResponse(url="/admin/series?error=duplicado", status_code=302)
    # Las series nuevas van al final, como en el libro
    ultimo = db.query(func.max(Serie.orden)).scalar()
    serie = Serie(nombre=nombre, descripcion=descripcion.strip() or None,
                  orden=(ultimo + 1) if ultimo is not None else 100)
    db.add(serie)
    db.commit()
    db.refresh(serie)
    return RedirectResponse(url=f"/admin/series/{serie.id}?saved=1", status_code=302)


@router.get("/series/{sid}", response_class=HTMLResponse)
async def admin_serie_detalle(sid: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    from .coleccion import ASSAYER_GROUPS, MINTS_BOLIVIA
    assayer_values = [a for _, items in ASSAYER_GROUPS for a in items]

    # Anterior / siguiente según el mismo orden de la lista
    ids = [r[0] for r in db.query(Serie.id).order_by(Serie.orden, Serie.nombre).all()]
    i = ids.index(sid)
    anterior = db.get(Serie, ids[i - 1]) if i > 0 else None
    siguiente = db.get(Serie, ids[i + 1]) if i + 1 < len(ids) else None

    rate = tipo_cambio.get_rate(db)
    precios_var: dict[int, list] = {}
    precios_generales = []
    for p in serie.precios:
        if p.variante_id:
            precios_var.setdefault(p.variante_id, []).append(p)
        else:
            precios_generales.append(p)

    # Tras agregar una variante, el formulario nuevo arranca con el mismo
    # ensayador y ceca: en el libro suelen venir varias seguidas iguales.
    last = request.query_params.get("last")
    ultima = next((v for v in serie.variantes if str(v.id) == last), None)

    return templates.TemplateResponse(request, "admin/serie_detalle.html", {
        "user": user, "serie": serie,
        "assayer_groups": ASSAYER_GROUPS,
        "assayer_values": assayer_values,
        "mints_bolivia": MINTS_BOLIVIA,
        "anterior": anterior, "siguiente": siguiente,
        "posicion": i + 1, "total_series": len(ids),
        "rate": rate,
        "precios_var": precios_var,
        "precios_generales": precios_generales,
        "resumen_var": {vid: _resumen_precios(ps, rate) for vid, ps in precios_var.items()},
        "resumen_serie": _resumen_precios(serie.precios, rate),
        "resumen_generales": _resumen_precios(precios_generales, rate),
        "fuentes": FUENTES_PRECIO, "estados": ESTADOS_PRECIO,
        "hoy": date.today().isoformat(),
        "ultima": ultima,
        "abierta": request.query_params.get("open"),
        "saved": request.query_params.get("saved"),
    })


@router.post("/series/{sid}")
async def admin_editar_serie(
    sid: int,
    request: Request,
    nombre: str = Form(""),
    descripcion: str = Form(""),
    orden: int = Form(100),
    activo: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    nombre = nombre.strip()
    if nombre and nombre.lower() != serie.nombre.lower() and \
            db.query(Serie).filter(func.lower(Serie.nombre) == nombre.lower(), Serie.id != sid).first():
        if request.headers.get("x-fetch") == "1":
            return JSONResponse({"ok": False, "error": "Ya existe otra serie con ese nombre."}, status_code=400)
        return RedirectResponse(url=f"/admin/series/{sid}", status_code=302)
    if nombre:
        serie.nombre = nombre
    serie.descripcion = descripcion.strip() or None
    serie.orden = orden
    serie.activo = activo == "1"
    db.commit()
    return _responder(request, f"/admin/series/{sid}?saved=1")


@router.post("/series/{sid}/orden")
async def admin_reordenar_serie(
    sid: int,
    request: Request,
    orden: int = Form(100),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    serie.orden = orden
    db.commit()
    return _responder(request, "/admin/series?saved=1")


@router.post("/series/{sid}/eliminar")
async def admin_eliminar_serie(sid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if serie:
        db.delete(serie)
        db.commit()
    return RedirectResponse(url="/admin/series?saved=1", status_code=302)


def _datos_variante(anio, ensayador, ceca, mintage, nota) -> dict:
    return {
        "anio":      int(anio) if anio.strip().isdigit() else None,
        "ensayador": ensayador.strip() or None,
        "ceca":      ceca.strip() or None,
        "mintage":   mintage.strip() or None,
        "nota":      nota.strip() or None,
    }


@router.post("/series/{sid}/variantes")
async def admin_crear_variante(
    sid: int,
    request: Request,
    anio: str = Form(""),
    ensayador: str = Form(""),
    ceca: str = Form(""),
    mintage: str = Form(""),
    nota: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    v = SerieVariante(serie_id=sid, **_datos_variante(anio, ensayador, ceca, mintage, nota))
    db.add(v)
    db.commit()
    return RedirectResponse(url=f"/admin/series/{sid}?saved=1&last={v.id}#nueva-variante", status_code=302)


@router.post("/series/variantes/{vid}")
async def admin_editar_variante(
    vid: int,
    request: Request,
    anio: str = Form(""),
    ensayador: str = Form(""),
    ceca: str = Form(""),
    mintage: str = Form(""),
    nota: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    v = db.query(SerieVariante).filter(SerieVariante.id == vid).first()
    if not v:
        raise HTTPException(status_code=404)
    for campo, valor in _datos_variante(anio, ensayador, ceca, mintage, nota).items():
        setattr(v, campo, valor)
    db.commit()
    return _responder(request, f"/admin/series/{v.serie_id}?saved=1#v-{vid}")


@router.post("/series/variantes/{vid}/eliminar")
async def admin_eliminar_variante(vid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    v = db.query(SerieVariante).filter(SerieVariante.id == vid).first()
    sid = v.serie_id if v else 0
    if v:
        db.delete(v)
        db.commit()
    return RedirectResponse(url=f"/admin/series/{sid}?saved=1#variantes", status_code=302)


@router.post("/series/{sid}/precios")
async def admin_crear_precio(
    sid: int,
    request: Request,
    variante_id: str = Form(""),
    monto: str = Form(""),
    moneda: str = Form("USD"),
    tipo: str = Form("oferta"),
    estado: str = Form(""),
    fuente: str = Form(""),
    url: str = Form(""),
    fecha: str = Form(""),
    nota: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    vid = int(variante_id) if variante_id.isdigit() else None
    if vid and not db.query(SerieVariante).filter(SerieVariante.id == vid, SerieVariante.serie_id == sid).first():
        vid = None
    destino = f"/admin/series/{sid}?saved=1" + (f"&open={vid}#v-{vid}" if vid else "#precios")
    try:
        # Acepta "1.250,50", "1250.50" y "1,250.50"
        m = monto.strip().replace(" ", "")
        if "," in m and "." in m:
            m = m.replace(".", "").replace(",", ".") if m.rfind(",") > m.rfind(".") else m.replace(",", "")
        else:
            m = m.replace(",", ".")
        valor = Decimal(m)
    except (InvalidOperation, ValueError):
        return RedirectResponse(url=destino, status_code=302)
    if valor <= 0:
        return RedirectResponse(url=destino, status_code=302)
    try:
        f = date.fromisoformat(fecha) if fecha else None
    except ValueError:
        f = None
    db.add(SeriePrecio(
        serie_id    = sid,
        variante_id = vid,
        monto       = valor,
        moneda      = "BOB" if moneda == "BOB" else "USD",
        tipo        = "vendido" if tipo == "vendido" else "oferta",
        estado      = estado.strip()[:30] or None,
        fuente      = fuente.strip()[:100] or None,
        url         = url.strip()[:500] if url.strip().startswith(("http://", "https://")) else None,
        fecha       = f,
        nota        = nota.strip() or None,
    ))
    db.commit()
    return RedirectResponse(url=destino, status_code=302)


@router.post("/series/precios/{pid}/eliminar")
async def admin_eliminar_precio(pid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    p = db.query(SeriePrecio).filter(SeriePrecio.id == pid).first()
    if not p:
        raise HTTPException(status_code=404)
    sid, vid = p.serie_id, p.variante_id
    db.delete(p)
    db.commit()
    destino = f"/admin/series/{sid}?saved=1" + (f"&open={vid}#v-{vid}" if vid else "#precios")
    return RedirectResponse(url=destino, status_code=302)


# ── Configuración ──────────────────────────────────────────────────────────────

@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    return templates.TemplateResponse(request, "admin/configuracion.html", {
        "user": user, "rate_info": tipo_cambio.get_rate_info(db),
        "rate_mode": get_setting(db, tipo_cambio.KEY_MODE) or "auto",
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.post("/configuracion", response_class=HTMLResponse)
async def configuracion_post(
    request: Request,
    rate_mode: str = Form("auto"),
    usd_bob_rate: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    if rate_mode == "manual":
        try:
            rate = float(usd_bob_rate.strip())
            if rate <= 0:
                raise ValueError
            tipo_cambio.set_manual(db, rate)
        except (ValueError, AttributeError):
            return RedirectResponse(url="/admin/configuracion?error=tasa", status_code=302)
    else:
        tipo_cambio.set_auto(db)
    return RedirectResponse(url="/admin/configuracion?saved=1", status_code=302)
