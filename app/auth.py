from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models.user import User
from .config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# Duración de la sesión: 400 días es el máximo que aceptan los navegadores
# para una cookie. Se renueva sola con el uso (ver refresh_session_cookie).
SESSION_DAYS = 400


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=SESSION_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def set_session_cookie(response, username: str) -> None:
    response.set_cookie(
        key="access_token",
        value=create_access_token(data={"sub": username}),
        httponly=True,
        max_age=60 * 60 * 24 * SESSION_DAYS,
        samesite="lax",
        secure=settings.https_only,
    )


def refresh_session_cookie(request: Request, response) -> None:
    """Renueva la sesión (como mucho una vez al día) mientras el usuario la use."""
    token = get_token_from_cookie(request)
    if not token:
        return
    if any(k == b"set-cookie" and v.startswith(b"access_token=") for k, v in response.raw_headers):
        return  # login/logout ya manejan la cookie
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return
    username = payload.get("sub")
    remaining = datetime.fromtimestamp(payload.get("exp", 0), timezone.utc) - datetime.now(timezone.utc)
    if username and remaining < timedelta(days=SESSION_DAYS - 1):
        set_session_cookie(response, username)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_token_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get("access_token")


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Devuelve el usuario actual si está autenticado, o None."""
    token = get_token_from_cookie(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None
    return get_user_by_username(db, username)


class NotAuthenticatedException(Exception):
    def __init__(self, next_url: str = "/"):
        self.next_url = next_url


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Devuelve el usuario actual o redirige al login."""
    user = get_current_user_optional(request, db)
    if not user:
        raise NotAuthenticatedException(next_url=request.url.path)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return user
