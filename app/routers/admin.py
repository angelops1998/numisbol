from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.setting import AppSetting
from ..models.user import User
from ..models.listing import Listing
from ..models.coin import Coin
from ..models.pregunta import Pregunta, Respuesta
from ..models.serie import Serie, SerieVariante
from ..auth import get_current_user


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
async def admin_coleccion(request: Request, uid: int = 0, q: str = "", pagina: int = 1, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    users = db.query(User).order_by(User.username).all()

    PER_PAGE = 20
    monedas = []
    total = 0
    total_paginas = 1
    usuario_sel = None

    if uid:
        usuario_sel = db.query(User).filter(User.id == uid).first()
        query = db.query(Coin).filter(Coin.user_id == uid)
        if q.strip():
            query = query.filter(Coin.name.ilike(f"%{q.strip()}%"))
        total = query.count()
        total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        pagina = max(1, min(pagina, total_paginas))
        monedas = query.order_by(Coin.created_at.desc()).offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()

    return templates.TemplateResponse(request, "admin/coleccion.html", {
        "user": user, "users": users, "monedas": monedas,
        "usuario_sel": usuario_sel, "uid": uid, "q": q,
        "total": total, "pagina": pagina, "total_paginas": total_paginas,
    })


# ── Series ─────────────────────────────────────────────────────────────────────

@router.get("/series", response_class=HTMLResponse)
async def admin_series(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    series = db.query(Serie).order_by(Serie.orden, Serie.nombre).all()
    conteos = dict(
        db.query(SerieVariante.serie_id, func.count(SerieVariante.id))
        .group_by(SerieVariante.serie_id).all()
    )
    return templates.TemplateResponse(request, "admin/series.html", {
        "user": user, "series": series, "conteos": conteos,
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
    serie = Serie(nombre=nombre, descripcion=descripcion.strip() or None)
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
    return templates.TemplateResponse(request, "admin/serie_detalle.html", {
        "user": user, "serie": serie,
        "assayer_groups": ASSAYER_GROUPS,
        "assayer_values": assayer_values,
        "mints_bolivia": MINTS_BOLIVIA,
        "saved": request.query_params.get("saved"),
    })


@router.post("/series/{sid}")
async def admin_editar_serie(
    sid: int,
    request: Request,
    nombre: str = Form(""),
    descripcion: str = Form(""),
    orden: int = Form(100),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if not serie:
        raise HTTPException(status_code=404)
    if nombre.strip():
        serie.nombre = nombre.strip()
    serie.descripcion = descripcion.strip() or None
    serie.orden = orden
    db.commit()
    return RedirectResponse(url=f"/admin/series/{sid}?saved=1", status_code=302)


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
    return RedirectResponse(url="/admin/series?saved=1", status_code=302)


@router.post("/series/{sid}/eliminar")
async def admin_eliminar_serie(sid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    serie = db.query(Serie).filter(Serie.id == sid).first()
    if serie:
        db.delete(serie)
        db.commit()
    return RedirectResponse(url="/admin/series?saved=1", status_code=302)


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
    v = SerieVariante(
        serie_id  = sid,
        anio      = int(anio) if anio.strip().isdigit() else None,
        ensayador = ensayador.strip() or None,
        ceca      = ceca.strip() or None,
        mintage   = mintage.strip() or None,
        nota      = nota.strip() or None,
    )
    db.add(v)
    db.commit()
    return RedirectResponse(url=f"/admin/series/{sid}?saved=1", status_code=302)


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
    v.anio      = int(anio) if anio.strip().isdigit() else None
    v.ensayador = ensayador.strip() or None
    v.ceca      = ceca.strip() or None
    v.mintage   = mintage.strip() or None
    v.nota      = nota.strip() or None
    db.commit()
    return RedirectResponse(url=f"/admin/series/{v.serie_id}?saved=1", status_code=302)


@router.post("/series/variantes/{vid}/eliminar")
async def admin_eliminar_variante(vid: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    v = db.query(SerieVariante).filter(SerieVariante.id == vid).first()
    sid = v.serie_id if v else 0
    if v:
        db.delete(v)
        db.commit()
    return RedirectResponse(url=f"/admin/series/{sid}?saved=1", status_code=302)


# ── Configuración ──────────────────────────────────────────────────────────────

@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    usd_rate = get_setting(db, "usd_bob_rate", "")
    return templates.TemplateResponse(request, "admin/configuracion.html", {
        "user": user, "usd_rate": usd_rate,
        "saved": request.query_params.get("saved"),
    })


@router.post("/configuracion", response_class=HTMLResponse)
async def configuracion_post(
    request: Request,
    usd_bob_rate: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    try:
        rate = float(usd_bob_rate.strip())
        if rate <= 0:
            raise ValueError
        set_setting(db, "usd_bob_rate", str(rate))
    except (ValueError, AttributeError):
        pass
    return RedirectResponse(url="/admin/configuracion?saved=1", status_code=302)
