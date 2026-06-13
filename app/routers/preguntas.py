from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.pregunta import Pregunta, Respuesta
from ..auth import get_current_user, get_current_user_optional
from ..templates_config import templates
from ..routers.coleccion import save_upload

router = APIRouter(prefix="/preguntas", tags=["preguntas"])

PER_PAGE    = 10
MAX_ACTIVAS = 5


def _base_ctx(request, db):
    return {"user": get_current_user_optional(request, db)}


# ── Lista ──────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista(request: Request, db: Session = Depends(get_db),
                q: str = "", pagina: int = 1):
    user = get_current_user_optional(request, db)
    if not user:
        return templates.TemplateResponse(request, "preguntas/acceso_requerido.html", {})

    query = db.query(Pregunta)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(Pregunta.titulo.ilike(like))

    total = query.count()
    total_paginas = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    pagina = max(1, min(pagina, total_paginas))
    preguntas = (query.order_by(Pregunta.created_at.desc())
                      .offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all())

    # Contar respuestas para cada pregunta de forma eficiente
    ids = [p.id for p in preguntas]
    resp_counts = {}
    if ids:
        rows = (db.query(Respuesta.pregunta_id, func.count().label("n"))
                  .filter(Respuesta.pregunta_id.in_(ids))
                  .group_by(Respuesta.pregunta_id).all())
        resp_counts = {r.pregunta_id: r.n for r in rows}

    return templates.TemplateResponse(request, "preguntas/lista.html", {
        "user": user, "preguntas": preguntas, "resp_counts": resp_counts,
        "q": q, "pagina": pagina, "total": total, "total_paginas": total_paginas,
    })


# ── Nueva ──────────────────────────────────────────────────────────────────────

@router.get("/nueva", response_class=HTMLResponse)
async def nueva_get(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    activas = db.query(func.count(Pregunta.id)).filter(
        Pregunta.user_id == user.id, Pregunta.is_closed == False
    ).scalar()
    return templates.TemplateResponse(request, "preguntas/form.html", {
        "user": user, "activas": activas, "max_activas": MAX_ACTIVAS,
        "error": None, "titulo": "", "cuerpo": "",
    })


@router.post("/nueva", response_class=HTMLResponse)
async def nueva_post(
    request: Request,
    titulo: str = Form(""),
    cuerpo: str = Form(""),
    foto1: UploadFile = File(None),
    foto2: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    activas = db.query(func.count(Pregunta.id)).filter(
        Pregunta.user_id == user.id, Pregunta.is_closed == False
    ).scalar()

    error = None
    if not titulo.strip():
        error = "El título de la pregunta es obligatorio."
    elif len(titulo.strip()) < 10:
        error = "El título debe tener al menos 10 caracteres."
    elif activas >= MAX_ACTIVAS:
        error = f"Ya tenés {MAX_ACTIVAS} preguntas activas. Cerrá alguna antes de publicar otra."

    if error:
        return templates.TemplateResponse(request, "preguntas/form.html", {
            "user": user, "activas": activas, "max_activas": MAX_ACTIVAS,
            "error": error, "titulo": titulo, "cuerpo": cuerpo,
        })

    img1 = save_upload(foto1)
    img2 = save_upload(foto2)
    pregunta = Pregunta(user_id=user.id, titulo=titulo.strip(),
                        cuerpo=cuerpo.strip() or None,
                        image_1_url=img1, image_2_url=img2)
    db.add(pregunta)
    db.commit()
    db.refresh(pregunta)
    return RedirectResponse(url=f"/preguntas/{pregunta.id}", status_code=302)


# ── Detalle ────────────────────────────────────────────────────────────────────

@router.get("/{pid}", response_class=HTMLResponse)
async def detalle(pid: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return templates.TemplateResponse(request, "preguntas/acceso_requerido.html", {})
    pregunta = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if not pregunta:
        raise HTTPException(status_code=404)

    pregunta.views = (pregunta.views or 0) + 1
    db.commit()

    return templates.TemplateResponse(request, "preguntas/detalle.html", {
        "user": user, "pregunta": pregunta,
        "es_autor": user and user.id == pregunta.user_id,
        "resp_error": None,
    })


# ── Responder ──────────────────────────────────────────────────────────────────

@router.post("/{pid}/responder", response_class=HTMLResponse)
async def responder(
    pid: int, request: Request,
    cuerpo: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    pregunta = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if not pregunta:
        raise HTTPException(status_code=404)
    if pregunta.is_closed:
        raise HTTPException(status_code=400, detail="La pregunta está cerrada.")

    if not cuerpo.strip():
        return templates.TemplateResponse(request, "preguntas/detalle.html", {
            "user": user, "pregunta": pregunta,
            "es_autor": user.id == pregunta.user_id,
            "resp_error": "La respuesta no puede estar vacía.",
        })

    db.add(Respuesta(pregunta_id=pid, user_id=user.id, cuerpo=cuerpo.strip()))
    db.commit()
    return RedirectResponse(url=f"/preguntas/{pid}#respuestas", status_code=302)


# ── Marcar mejor respuesta ─────────────────────────────────────────────────────

@router.post("/{pid}/mejor/{rid}", response_class=HTMLResponse)
async def marcar_mejor(pid: int, rid: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    pregunta = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if not pregunta or pregunta.user_id != user.id:
        raise HTTPException(status_code=403)

    db.query(Respuesta).filter(Respuesta.pregunta_id == pid).update({"is_best": False})
    respuesta = db.query(Respuesta).filter(Respuesta.id == rid, Respuesta.pregunta_id == pid).first()
    if respuesta:
        respuesta.is_best = True
    db.commit()
    return RedirectResponse(url=f"/preguntas/{pid}#respuestas", status_code=302)


# ── Cerrar/reabrir ─────────────────────────────────────────────────────────────

@router.post("/{pid}/cerrar")
async def cerrar(pid: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    pregunta = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if not pregunta or (pregunta.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=403)
    pregunta.is_closed = not pregunta.is_closed
    db.commit()
    return RedirectResponse(url=f"/preguntas/{pid}", status_code=302)


# ── Eliminar ───────────────────────────────────────────────────────────────────

@router.post("/{pid}/eliminar")
async def eliminar(pid: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    pregunta = db.query(Pregunta).filter(Pregunta.id == pid).first()
    if not pregunta or (pregunta.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=403)
    db.delete(pregunta)
    db.commit()
    return RedirectResponse(url="/preguntas", status_code=302)
