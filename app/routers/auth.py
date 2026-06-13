from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..database import get_db
from ..models.user import User
from ..auth import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_current_user_optional,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "auth/registro.html", {"hide_footer": True})


@router.post("/registro", response_class=HTMLResponse)
async def registro(
    request: Request,
    username: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    full_name: str = Form(""),
    whatsapp: str = Form(""),
    db: Session = Depends(get_db),
):
    errors = []

    if not username.strip():
        errors.append("El nombre de usuario es obligatorio.")
    elif len(username.strip()) < 3:
        errors.append("El nombre de usuario debe tener al menos 3 caracteres.")
    if not email.strip():
        errors.append("El correo electrónico es obligatorio.")
    password = password.strip()
    if not password:
        errors.append("La contraseña es obligatoria.")
    elif len(password) < 8:
        errors.append("La contraseña debe tener al menos 8 caracteres.")

    if errors:
        return templates.TemplateResponse(
            request, "auth/registro.html",
            {"errors": errors, "form": {"username": username, "email": email, "full_name": full_name, "whatsapp": whatsapp}, "hide_footer": True},
            status_code=422,
        )

    # Limpiar número: solo dígitos y espacios, quitar + si lo pusieron
    wa_clean = whatsapp.strip().lstrip("+").replace("-", "").replace("(", "").replace(")", "") or None

    hashed = hash_password(password)
    new_user = User(
        username=username.lower().strip(),
        email=email.lower().strip(),
        hashed_password=hashed,
        full_name=full_name.strip() or None,
        whatsapp=wa_clean,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        errors.append("El nombre de usuario o email ya está en uso.")
        return templates.TemplateResponse(
            request, "auth/registro.html",
            {"errors": errors, "form": {"username": username, "email": email, "full_name": full_name}, "hide_footer": True},
            status_code=422,
        )

    token = create_access_token(data={"sub": new_user.username})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 días
        samesite="lax",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    next_url = request.query_params.get("next", "/")
    return templates.TemplateResponse(request, "auth/login.html", {"next": next_url, "hide_footer": True})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    # Validación manual para mostrar errores en HTML, no JSON
    password = password.strip()
    if not email.strip() or not password:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Completá el correo y la contraseña.", "next": next, "form": {"email": email}, "hide_footer": True},
            status_code=422,
        )

    user = authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Email o contraseña incorrectos.", "next": next, "form": {"email": email}, "hide_footer": True},
            status_code=401,
        )
    if not user.is_active:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Tu cuenta está desactivada.", "next": next, "hide_footer": True},
            status_code=401,
        )

    token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url=next or "/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 días
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response
