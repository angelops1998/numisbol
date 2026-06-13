from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.setting import AppSetting
from ..models.user import User
from ..auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def require_admin(request, db):
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


@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    usd_rate = get_setting(db, "usd_bob_rate", "")
    return templates.TemplateResponse(request, "admin/configuracion.html", {
        "user": user,
        "usd_rate": usd_rate,
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


@router.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    users = db.query(User).order_by(User.username).all()
    return templates.TemplateResponse(request, "admin/usuarios.html", {
        "user": user, "users": users,
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
