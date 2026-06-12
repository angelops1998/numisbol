from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.anuncio import Anuncio
from ..auth import get_current_user
from ..routers.coleccion import save_upload

router = APIRouter(prefix="/admin/anuncios", tags=["anuncios"])
templates = Jinja2Templates(directory="app/templates")


def require_admin(request, db):
    user = get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


# ── Panel admin ───────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def admin_anuncios(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    anuncios = db.query(Anuncio).order_by(Anuncio.orden, Anuncio.id).all()
    return templates.TemplateResponse(request, "admin/anuncios.html", {
        "user": user,
        "anuncios": anuncios,
    })


@router.post("/crear", response_class=HTMLResponse)
async def crear_anuncio(
    request: Request,
    titulo: str = Form(""),
    descripcion: str = Form(""),
    orden: int = Form(0),
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)

    url = save_upload(imagen)
    if not url:
        anuncios = db.query(Anuncio).order_by(Anuncio.orden, Anuncio.id).all()
        user = get_current_user(request, db)
        return templates.TemplateResponse(request, "admin/anuncios.html", {
            "user": user,
            "anuncios": anuncios,
            "error": "Imagen inválida. Usá JPG, PNG o WebP.",
        }, status_code=422)

    anuncio = Anuncio(
        titulo=titulo.strip() or "Sin título",
        descripcion=descripcion.strip() or None,
        imagen_url=url,
        orden=orden,
    )
    db.add(anuncio)
    db.commit()
    return RedirectResponse(url="/admin/anuncios?ok=1", status_code=302)


@router.post("/{id}/toggle", response_class=HTMLResponse)
async def toggle_anuncio(request: Request, id: int, db: Session = Depends(get_db)):
    require_admin(request, db)
    anuncio = db.get(Anuncio, id)
    if anuncio:
        anuncio.activo = not anuncio.activo
        db.commit()
    return RedirectResponse(url="/admin/anuncios", status_code=302)


@router.post("/{id}/eliminar", response_class=HTMLResponse)
async def eliminar_anuncio(request: Request, id: int, db: Session = Depends(get_db)):
    require_admin(request, db)
    anuncio = db.get(Anuncio, id)
    if anuncio:
        db.delete(anuncio)
        db.commit()
    return RedirectResponse(url="/admin/anuncios", status_code=302)
