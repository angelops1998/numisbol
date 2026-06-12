from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .database import engine, Base
from .routers import auth, main as main_router, coleccion, recovery, mercado, perfil, anuncios, blog, moneda_publica
from . import models  # noqa: F401 – registra los modelos en Base
from .auth import NotAuthenticatedException

_templates = Jinja2Templates(directory="app/templates")

# Crear tablas (en producción usar Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NumisColect",
    description="Plataforma para coleccionistas de monedas",
    version="0.1.0",
)

@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url=f"/auth/login?next={exc.next_url}", status_code=302)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return _templates.TemplateResponse(request, "404.html", {}, status_code=404)

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
