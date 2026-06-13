import secrets
from datetime import datetime, timedelta, timezone
from ..templates_config import templates
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..models.password_reset import PasswordResetToken
from ..auth import hash_password, get_current_user_optional

router = APIRouter(prefix="/auth", tags=["recovery"])

TOKEN_EXPIRE_HOURS = 2


def _cleanup_old_tokens(db: Session, user_id: int):
    """Elimina tokens anteriores del usuario."""
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id
    ).delete()
    db.commit()


# ── Paso 1: Solicitar recuperación ───────────────────────────
@router.get("/recuperar", response_class=HTMLResponse)
async def recuperar_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "auth/recuperar.html", {})


@router.post("/recuperar", response_class=HTMLResponse)
async def recuperar_post(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    # Siempre mostrar el mismo mensaje (no revelar si el email existe)
    success_msg = "Si ese correo está registrado, recibirás las instrucciones para recuperar tu contraseña."

    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user:
        return templates.TemplateResponse(request, "auth/recuperar.html", {
            "success": success_msg
        })

    # Generar token
    _cleanup_old_tokens(db, user.id)
    token_str = secrets.token_urlsafe(32)
    expires   = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)

    token = PasswordResetToken(
        user_id    = user.id,
        token      = token_str,
        expires_at = expires,
    )
    db.add(token)
    db.commit()

    # En producción aquí se enviaría un email.
    # Por ahora mostramos el enlace directamente en pantalla.
    reset_url = f"{request.base_url}auth/nueva-contrasena/{token_str}"

    return templates.TemplateResponse(request, "auth/recuperar.html", {
        "success": success_msg,
        "reset_url": reset_url,   # Solo para desarrollo — quitar en producción
        "user_name": user.full_name or user.username,
    })


# ── Paso 2: Nueva contraseña ──────────────────────────────────
@router.get("/nueva-contrasena/{token}", response_class=HTMLResponse)
async def nueva_contrasena_page(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    reset = _get_valid_token(db, token)
    if not reset:
        return templates.TemplateResponse(request, "auth/recuperar.html", {
            "error": "El enlace no es válido o ya expiró. Solicitá uno nuevo."
        })
    return templates.TemplateResponse(request, "auth/nueva_contrasena.html", {
        "token": token
    })


@router.post("/nueva-contrasena/{token}", response_class=HTMLResponse)
async def nueva_contrasena_post(
    token: str,
    request: Request,
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
):
    reset = _get_valid_token(db, token)
    if not reset:
        return templates.TemplateResponse(request, "auth/recuperar.html", {
            "error": "El enlace no es válido o ya expiró. Solicitá uno nuevo."
        })

    errors = []
    if len(password) < 8:
        errors.append("La contraseña debe tener al menos 8 caracteres.")
    if password != password2:
        errors.append("Las contraseñas no coinciden.")

    if errors:
        return templates.TemplateResponse(request, "auth/nueva_contrasena.html", {
            "token": token, "errors": errors
        })

    # Actualizar contraseña
    user = db.query(User).filter(User.id == reset.user_id).first()
    user.hashed_password = hash_password(password)

    # Marcar token como usado
    reset.used = True
    db.commit()

    return templates.TemplateResponse(request, "auth/nueva_contrasena.html", {
        "done": True
    })


def _get_valid_token(db: Session, token: str):
    now = datetime.now(timezone.utc)
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used  == False,       # noqa
        PasswordResetToken.expires_at > now,
    ).first()
    return reset
