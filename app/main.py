from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from .database import engine, SessionLocal
from .routers import auth, main as main_router, coleccion, recovery, mercado, perfil, anuncios, blog, moneda_publica, admin, preguntas
from .auth import NotAuthenticatedException
from .csrf import get_csrf_token, set_csrf_cookie, validate_csrf
import secrets, hmac, hashlib

_templates = Jinja2Templates(directory="app/templates")

app = FastAPI(
    title="NumisColect",
    description="Plataforma para coleccionistas de monedas",
    version="0.1.0",
)

# Rutas POST excluidas de CSRF (login/registro manejan su propio flujo)
_CSRF_EXEMPT = {"/auth/login", "/auth/registro", "/auth/token"}

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path not in _CSRF_EXEMPT:
            # Leer y cachear el body para que el router pueda leerlo después
            body = await request.body()
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            request._receive = receive

            from urllib.parse import parse_qs
            content_type = request.headers.get("content-type", "")
            form_token = ""
            if "application/x-www-form-urlencoded" in content_type:
                parsed = parse_qs(body.decode("utf-8", errors="replace"))
                form_token = parsed.get("csrf_token", [""])[0]
            elif "multipart/form-data" in content_type:
                # Buscar el token en el body crudo del multipart
                decoded = body.decode("utf-8", errors="replace")
                import re
                m = re.search(r'name="csrf_token"\r\n\r\n([^\r\n]+)', decoded)
                form_token = m.group(1) if m else ""

            try:
                validate_csrf(request, form_token)
            except HTTPException:
                return _templates.TemplateResponse(
                    request, "403.html", _error_ctx(request), status_code=403
                )

        response = await call_next(request)
        if "csrf_token" not in request.cookies:
            token = secrets.token_hex(32)
            set_csrf_cookie(response, token)
        return response

app.add_middleware(CSRFMiddleware)

@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url=f"/auth/login?next={exc.next_url}", status_code=302)

def _error_ctx(request: Request) -> dict:
    """Las páginas de error también muestran la barra con la sesión iniciada."""
    from .auth import get_current_user_optional
    db = SessionLocal()
    try:
        return {"user": get_current_user_optional(request, db)}
    except Exception:
        return {}
    finally:
        db.close()


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return _templates.TemplateResponse(request, "404.html", _error_ctx(request), status_code=404)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(main_router.router)
app.include_router(auth.router)
app.include_router(coleccion.router)
app.include_router(recovery.router)
app.include_router(mercado.router)
app.include_router(perfil.router)
app.include_router(anuncios.router)
app.include_router(blog.router)
app.include_router(moneda_publica.router)
app.include_router(moneda_publica.galeria_router)
app.include_router(admin.router)
app.include_router(preguntas.router)
