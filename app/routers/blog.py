from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, extract, func as sqlfunc
from typing import List, Optional
from ..database import get_db
from ..models.blog import BlogPost, BlogCategoria, BlogPostImagen, blog_post_categorias, slugify
from ..models.user import User
from ..auth import get_current_user, get_current_user_optional
from ..routers.coleccion import save_upload

from ..templates_config import templates
router = APIRouter(prefix="/blog", tags=["blog"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def unique_slug(db: Session, titulo: str, exclude_id: int = None) -> str:
    base = slugify(titulo)
    slug = base
    n = 1
    while True:
        q = db.query(BlogPost).filter(BlogPost.slug == slug)
        if exclude_id:
            q = q.filter(BlogPost.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{n}"
        n += 1


def get_categorias(db: Session):
    return db.query(BlogCategoria).order_by(BlogCategoria.nombre).all()


# ── Lista pública ─────────────────────────────────────────────────────────────

POSTS_POR_PAGINA = 9
_TRGM_AVAILABLE: bool | None = None  # se detecta en el primer request

def _check_trgm(db: Session) -> bool:
    global _TRGM_AVAILABLE
    if _TRGM_AVAILABLE is None:
        from sqlalchemy import text
        try:
            db.execute(text("SELECT word_similarity('a','a')"))
            _TRGM_AVAILABLE = True
        except Exception:
            db.rollback()
            _TRGM_AVAILABLE = False
    return _TRGM_AVAILABLE

@router.get("", response_class=HTMLResponse)
async def blog_index(
    request: Request,
    q: str = "",
    categoria: str = "",
    anio: int = None,
    mes: int = 0,
    pagina: int = 1,
    db: Session = Depends(get_db),
):
    from datetime import date
    if anio is None:
        anio = date.today().year
    user = get_current_user_optional(request, db)

    # Top 5 más leídos
    mas_leidos = (
        db.query(BlogPost)
        .filter(BlogPost.publicado == True, BlogPost.vistas > 0)
        .order_by(BlogPost.vistas.desc())
        .limit(5).all()
    )

    # El destacado es el artículo más reciente.
    # Si hay filtros activos, solo se muestra si coincide con ellos.
    hay_filtro = bool(q.strip() or categoria or anio or mes)

    def _apply_cat_filter(qry, cat_slug):
        if cat_slug == "__sin_categoria__":
            return qry.filter(~BlogPost.categorias.any())
        cat_obj = db.query(BlogCategoria).filter(BlogCategoria.slug == cat_slug).first()
        if cat_obj:
            return qry.filter(BlogPost.categorias.any(BlogCategoria.id == cat_obj.id))
        return qry

    destacado_q = db.query(BlogPost).filter(BlogPost.publicado == True)
    if hay_filtro:
        if q.strip():
            term = f"%{q.strip()}%"
            destacado_q = destacado_q.filter(
                or_(BlogPost.titulo.ilike(term), BlogPost.extracto.ilike(term),
                    BlogPost.contenido.ilike(term))
            )
        if categoria:
            destacado_q = _apply_cat_filter(destacado_q, categoria)
        if anio:
            destacado_q = destacado_q.filter(extract("year", BlogPost.created_at) == anio)
        if mes:
            destacado_q = destacado_q.filter(extract("month", BlogPost.created_at) == mes)

    destacado = destacado_q.order_by(BlogPost.created_at.desc()).first()

    # Query filtrada para la grilla
    posts_q = db.query(BlogPost).filter(BlogPost.publicado == True)

    if q.strip():
        term = f"%{q.strip()}%"
        ilike_filter = or_(
            BlogPost.titulo.ilike(term),
            BlogPost.extracto.ilike(term),
            BlogPost.categorias.any(BlogCategoria.nombre.ilike(term)),
            BlogPost.autor.has(or_(
                User.full_name.ilike(term),
                User.username.ilike(term),
            )),
        )
        if _check_trgm(db):
            TRGM_MIN = 0.35
            posts_q = posts_q.filter(
                or_(
                    ilike_filter,
                    sqlfunc.word_similarity(q.strip(), BlogPost.titulo) >= TRGM_MIN,
                )
            ).order_by(
                sqlfunc.word_similarity(q.strip(), BlogPost.titulo).desc(),
                BlogPost.created_at.desc()
            )
        else:
            posts_q = posts_q.filter(ilike_filter)
    if categoria:
        posts_q = _apply_cat_filter(posts_q, categoria)
    if anio:
        posts_q = posts_q.filter(extract("year", BlogPost.created_at) == anio)
    if mes:
        posts_q = posts_q.filter(extract("month", BlogPost.created_at) == mes)

    if not q.strip():
        posts_q = posts_q.order_by(BlogPost.created_at.desc())
    total = posts_q.count()

    # Excluir el destacado de la grilla por ID para no repetirlo
    total_grilla = total

    if destacado:
        posts_q      = posts_q.filter(BlogPost.id != destacado.id)
        total_grilla = max(0, total - 1)
        # Pág 1 tiene 8 slots (destacado ocupa 1), pág 2+ tiene 9
        # total_paginas = 1 + ceil((total_grilla - 8) / 9)  si total_grilla > 8
        if total_grilla <= POSTS_POR_PAGINA - 1:
            total_paginas = 1
        else:
            total_paginas = 1 + (-(-(total_grilla - (POSTS_POR_PAGINA - 1)) // POSTS_POR_PAGINA))
        pagina = max(1, min(pagina, total_paginas))
        if pagina == 1:
            skip, limit = 0, POSTS_POR_PAGINA - 1
        else:
            skip  = (POSTS_POR_PAGINA - 1) + (pagina - 2) * POSTS_POR_PAGINA
            limit = POSTS_POR_PAGINA
    else:
        total_paginas = max(1, -(-total_grilla // POSTS_POR_PAGINA))
        pagina        = max(1, min(pagina, total_paginas))
        skip, limit   = (pagina - 1) * POSTS_POR_PAGINA, POSTS_POR_PAGINA

    grilla = posts_q.offset(skip).limit(limit).all()
    categorias = get_categorias(db)

    # Años disponibles para el filtro
    anios_raw = (
        db.query(sqlfunc.extract("year", BlogPost.created_at).label("y"))
        .filter(BlogPost.publicado == True)
        .distinct()
        .order_by(sqlfunc.extract("year", BlogPost.created_at).desc())
        .all()
    )
    anios = [int(r.y) for r in anios_raw]

    MESES = ["", "Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    def page_url(p):
        params = []
        if q:         params.append(f"q={q}")
        if categoria: params.append(f"categoria={categoria}")
        if anio:      params.append(f"anio={anio}")
        if mes:       params.append(f"mes={mes}")
        params.append(f"pagina={p}")
        return "/blog?" + "&".join(params)

    return templates.TemplateResponse(request, "blog/index.html", {
        "user": user,
        "destacado": destacado,
        "grilla": grilla,
        "categorias": categorias,
        "q": q,
        "cat_activa": categoria,
        "anio": anio,
        "mes": mes,
        "anios": anios,
        "meses": MESES,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "total": total,
        "page_url": page_url,
        "hay_filtro": hay_filtro,
        "mas_leidos": mas_leidos,
        "autores_leidos": db.query(User).join(BlogPost, BlogPost.autor_id == User.id).filter(BlogPost.publicado == True).distinct().order_by(User.username).all(),
    })


# ── Más leídos por categoría (AJAX) ──────────────────────────────────────────

@router.get("/mas-leidos", response_class=HTMLResponse)
async def mas_leidos_fragment(
    request: Request,
    categoria: str = "",
    autor: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(BlogPost).filter(BlogPost.publicado == True, BlogPost.vistas > 0)
    if categoria == "__sin_categoria__":
        q = q.filter(~BlogPost.categorias.any())
    elif categoria:
        cat = db.query(BlogCategoria).filter(BlogCategoria.slug == categoria).first()
        if cat:
            q = q.filter(BlogPost.categorias.any(BlogCategoria.id == cat.id))
    if autor:
        a = db.query(User).filter(User.username == autor).first()
        if a:
            q = q.filter(BlogPost.autor_id == a.id)
    posts = q.order_by(BlogPost.vistas.desc()).limit(5).all()
    html = ""
    for i, post in enumerate(posts, 1):
        img = f'<img src="{post.portada_url}" alt="">' if post.portada_url else "<span>📰</span>"
        titulo = post.titulo
        html += f'''<a href="/blog/{post.slug}" class="blog-leido-item">
            <span class="blog-leido-num">{i}</span>
            <div class="blog-leido-img">{img}</div>
            <div class="blog-leido-info">
                <span class="blog-leido-titulo">{titulo}</span>
                <span class="blog-leido-vistas">👁 {post.vistas} vistas</span>
            </div>
        </a>'''
    if not html:
        html = '<p class="blog-leidos-empty">Sin artículos leídos en esta categoría.</p>'
    return HTMLResponse(html)


# ── Comentarios ──────────────────────────────────────────────────────────────

from ..models.blog import BlogComentario

@router.post("/{slug}/comentar", response_class=RedirectResponse)
async def comentar(
    slug: str,
    request: Request,
    contenido: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.publicado == True).first()
    if not post:
        raise HTTPException(status_code=404)
    texto = contenido.strip()
    if texto:
        db.add(BlogComentario(post_id=post.id, autor_id=user.id, contenido=texto))
        db.commit()
    return RedirectResponse(url=f"/blog/{slug}#comentarios", status_code=302)


@router.post("/{slug}/comentarios/{comentario_id}/eliminar", response_class=RedirectResponse)
async def eliminar_comentario(
    slug: str,
    comentario_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    c = db.query(BlogComentario).filter(BlogComentario.id == comentario_id).first()
    if c and (c.autor_id == user.id or user.is_admin or (c.post and c.post.autor_id == user.id)):
        db.delete(c)
        db.commit()
    return RedirectResponse(url=f"/blog/{slug}#comentarios", status_code=302)


# ── Crear artículo ────────────────────────────────────────────────────────────

@router.get("/nuevo/articulo", response_class=HTMLResponse)
async def blog_nuevo_get(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Solo usuarios verificados pueden publicar artículos.")
    categorias = get_categorias(db)
    return templates.TemplateResponse(request, "blog/form.html", {
        "user": user, "categorias": categorias, "post": None,
    })


@router.post("/nuevo/articulo", response_class=HTMLResponse)
async def blog_nuevo_post(
    request: Request,
    titulo: str = Form(""),
    extracto: str = Form(""),
    contenido: str = Form(""),
    categoria_ids: List[str] = Form(default=[]),
    publicado: str = Form("si"),
    portada: UploadFile = File(None),
    imagenes: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Solo usuarios verificados pueden publicar artículos.")
    categorias = get_categorias(db)
    errors = []
    if not titulo.strip():    errors.append("El título es obligatorio.")
    if not contenido.strip(): errors.append("El contenido no puede estar vacío.")

    if errors:
        return templates.TemplateResponse(request, "blog/form.html", {
            "user": user, "categorias": categorias, "post": None,
            "errors": errors,
            "form": {"titulo": titulo, "extracto": extracto,
                     "contenido": contenido, "categoria_ids": categoria_ids},
        }, status_code=422)

    portada_url = None
    if portada and portada.filename:
        portada_url = save_upload(portada)

    cats = db.query(BlogCategoria).filter(
        BlogCategoria.id.in_([int(i) for i in categoria_ids if i])
    ).all()

    post = BlogPost(
        titulo=titulo.strip(),
        slug=unique_slug(db, titulo),
        extracto=extracto.strip() or None,
        contenido=contenido.strip(),
        portada_url=portada_url,
        autor_id=user.id,
        publicado=(publicado == "si"),
        categorias=cats,
    )
    db.add(post)
    db.flush()

    for i, img in enumerate(imagenes):
        if img and img.filename:
            url = save_upload(img)
            if url:
                db.add(BlogPostImagen(post_id=post.id, url=url, orden=i))

    db.commit()
    db.refresh(post)
    return RedirectResponse(url=f"/blog/{post.slug}", status_code=302)


# ── Editar artículo ───────────────────────────────────────────────────────────

@router.get("/{slug}/editar", response_class=HTMLResponse)
async def blog_editar_get(request: Request, slug: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post or (user.id != post.autor_id and not user.is_admin):
        raise HTTPException(status_code=403, detail="Sin permiso")
    categorias = get_categorias(db)
    return templates.TemplateResponse(request, "blog/form.html", {
        "user": user, "post": post, "categorias": categorias,
    })


@router.post("/{slug}/editar", response_class=HTMLResponse)
async def blog_editar_post(
    request: Request,
    slug: str,
    titulo: str = Form(""),
    extracto: str = Form(""),
    contenido: str = Form(""),
    categoria_ids: List[str] = Form(default=[]),
    publicado: str = Form("si"),
    portada: UploadFile = File(None),
    imagenes: List[UploadFile] = File(default=[]),
    eliminar_imagenes: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post or (user.id != post.autor_id and not user.is_admin):
        raise HTTPException(status_code=403, detail="Sin permiso")

    categorias = get_categorias(db)
    errors = []
    if not titulo.strip():    errors.append("El título es obligatorio.")
    if not contenido.strip(): errors.append("El contenido no puede estar vacío.")

    if errors:
        return templates.TemplateResponse(request, "blog/form.html", {
            "user": user, "post": post, "categorias": categorias,
            "errors": errors,
        }, status_code=422)

    if portada and portada.filename:
        url = save_upload(portada)
        if url:
            post.portada_url = url

    for img_id in eliminar_imagenes:
        img = db.get(BlogPostImagen, int(img_id))
        if img and img.post_id == post.id:
            db.delete(img)

    orden_base = len(post.imagenes)
    for i, img in enumerate(imagenes):
        if img and img.filename:
            url = save_upload(img)
            if url:
                db.add(BlogPostImagen(post_id=post.id, url=url, orden=orden_base + i))

    cats = db.query(BlogCategoria).filter(
        BlogCategoria.id.in_([int(i) for i in categoria_ids if i])
    ).all()

    post.titulo     = titulo.strip()
    post.slug       = unique_slug(db, titulo, exclude_id=post.id)
    post.extracto   = extracto.strip() or None
    post.contenido  = contenido.strip()
    post.categorias = cats
    post.publicado  = (publicado == "si")
    db.commit()
    return RedirectResponse(url=f"/blog/{post.slug}", status_code=302)


# ── Eliminar artículo ─────────────────────────────────────────────────────────

@router.post("/{slug}/eliminar", response_class=HTMLResponse)
async def blog_eliminar(request: Request, slug: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post or (user.id != post.autor_id and not user.is_admin):
        raise HTTPException(status_code=403, detail="Sin permiso")
    db.delete(post)
    db.commit()
    return RedirectResponse(url="/blog", status_code=302)


# ── Gestión de categorías (admin) ─────────────────────────────────────────────

@router.post("/admin/categoria")
async def crear_categoria(
    request: Request,
    nombre: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    nombre = nombre.strip().upper()
    if not nombre:
        raise HTTPException(status_code=422, detail="Nombre requerido")
    slug = slugify(nombre)
    existing = db.query(BlogCategoria).filter(BlogCategoria.slug == slug).first()
    if not existing:
        cat = BlogCategoria(nombre=nombre, slug=slug)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return {"id": cat.id, "nombre": cat.nombre, "slug": cat.slug}
    return {"id": existing.id, "nombre": existing.nombre, "slug": existing.slug}


# ── Artículos por autor ───────────────────────────────────────────────────────

@router.get("/autor/{username}", response_class=HTMLResponse)
async def blog_por_autor(request: Request, username: str, pagina: int = 1, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    autor = db.query(User).filter(User.username == username).first()
    if not autor:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    q = db.query(BlogPost).filter(BlogPost.autor_id == autor.id, BlogPost.publicado == True)
    total = q.count()
    por_pagina = 8
    total_paginas = max(1, -(-total // por_pagina))
    pagina = max(1, min(pagina, total_paginas))
    posts = q.order_by(BlogPost.created_at.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return templates.TemplateResponse(request, "blog/autor.html", {
        "user": user, "autor": autor, "posts": posts,
        "pagina": pagina, "total_paginas": total_paginas, "total": total,
        "username": username,
    })


# ── Detalle de un post (va AL FINAL para no capturar rutas estáticas) ─────────

@router.get("/{slug}", response_class=HTMLResponse)
async def blog_detalle(request: Request, slug: str, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post or (not post.publicado and (not user or user.id != post.autor_id)):
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    post.vistas = (post.vistas or 0) + 1
    db.commit()

    relacionados = []
    if post.categorias:
        cat_ids = [c.id for c in post.categorias]
        relacionados = (
            db.query(BlogPost)
            .filter(BlogPost.publicado == True,
                    BlogPost.categorias.any(BlogCategoria.id.in_(cat_ids)),
                    BlogPost.id != post.id)
            .order_by(BlogPost.created_at.desc())
            .limit(3).all()
        )
    if not relacionados:
        relacionados = (
            db.query(BlogPost)
            .filter(BlogPost.publicado == True,
                    BlogPost.id != post.id)
            .order_by(BlogPost.created_at.desc())
            .limit(3).all()
        )

    comentarios = (
        db.query(BlogComentario)
        .filter(BlogComentario.post_id == post.id)
        .order_by(BlogComentario.created_at.asc())
        .all()
    )

    return templates.TemplateResponse(request, "blog/detalle.html", {
        "user": user, "post": post, "relacionados": relacionados,
        "comentarios": comentarios,
    })
