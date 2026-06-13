from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..database import get_db
from ..models.user import User
from ..auth import get_current_user, get_current_user_optional, hash_password, verify_password
from ..routers.coleccion import save_upload   # reutilizamos la misma función

router = APIRouter(prefix="/perfil", tags=["perfil"])


# ── Mi perfil (ver + editar) ──────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def perfil_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    # estadísticas rápidas
    from ..models.coin import Coin
    from ..models.listing import Listing, ListingStatus
    total_monedas = db.query(Coin).filter(Coin.user_id == user.id).count()
    total_anuncios = db.query(Listing).filter(Listing.user_id == user.id).count()
    anuncios_activos = db.query(Listing).filter(
        Listing.user_id == user.id,
        Listing.status == ListingStatus.activo,
    ).count()
    return templates.TemplateResponse(request, "perfil/index.html", {
        "user": user,
        "total_monedas": total_monedas,
        "total_anuncios": total_anuncios,
        "anuncios_activos": anuncios_activos,
    })


# ── Editar información general ────────────────────────────────────────────────

@router.post("/editar", response_class=HTMLResponse)
async def perfil_editar(
    request: Request,
    full_name: str = Form(""),
    bio: str = Form(""),
    whatsapp: str = Form(""),
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    user.full_name = full_name.strip() or None
    user.bio = bio.strip() or None

    # Limpiar whatsapp
    wa = whatsapp.strip().lstrip("+").replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    user.whatsapp = wa or None

    # Avatar (imagen)
    if avatar and avatar.filename:
        url = save_upload(avatar)
        if url:
            user.avatar_url = url

    db.commit()

    # Flash + redirect
    response = RedirectResponse(url="/perfil?ok=1", status_code=302)
    return response


# ── Cambiar contraseña ────────────────────────────────────────────────────────

@router.post("/contrasena", response_class=HTMLResponse)
async def perfil_contrasena(
    request: Request,
    password_actual: str = Form(""),
    password_nuevo: str = Form(""),
    password_confirmar: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    errors = []
    if not password_actual:
        errors.append("Ingresá tu contraseña actual.")
    elif not verify_password(password_actual, user.hashed_password):
        errors.append("La contraseña actual es incorrecta.")
    if len(password_nuevo) < 8:
        errors.append("La nueva contraseña debe tener al menos 8 caracteres.")
    if password_nuevo != password_confirmar:
        errors.append("Las contraseñas nuevas no coinciden.")

    from ..models.coin import Coin
    from ..models.listing import Listing, ListingStatus
    total_monedas = db.query(Coin).filter(Coin.user_id == user.id).count()
    total_anuncios = db.query(Listing).filter(Listing.user_id == user.id).count()
    anuncios_activos = db.query(Listing).filter(
        Listing.user_id == user.id,
        Listing.status == ListingStatus.activo,
    ).count()

    if errors:
        return templates.TemplateResponse(request, "perfil/index.html", {
            "user": user,
            "total_monedas": total_monedas,
            "total_anuncios": total_anuncios,
            "anuncios_activos": anuncios_activos,
            "pw_errors": errors,
            "active_tab": "seguridad",
        }, status_code=422)

    user.hashed_password = hash_password(password_nuevo)
    db.commit()

    return RedirectResponse(url="/perfil?pw=1", status_code=302)
