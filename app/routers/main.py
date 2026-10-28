from ..templates_config import templates
import re
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from ..database import get_db
from ..auth import get_current_user_optional
from ..models.anuncio import Anuncio
from ..models.coin import Coin
from ..models.user import User
from ..models.listing import Listing, ListingStatus
from ..models.pregunta import Pregunta

router = APIRouter(tags=["main"])


def _pg_estimate(db: Session, table: str) -> int:
    """Estimación rápida de filas vía pg_class (no hace full scan)."""
    row = db.execute(text(
        "SELECT reltuples::bigint FROM pg_class WHERE relname = :t"
    ), {"t": table}).fetchone()
    return int(row[0]) if row and row[0] > 0 else 0


# Épocas del catálogo para el inicio. El texto es fijo; los años y los
# conteos salen de las series cargadas, así crecen solos al sumar series.
_EPOCAS = [
    ("reales", "Reales bolivianos",
     "La historia numismática boliviana empieza con monedas que todavía llevan el busto de Fernando VII y el escudo de España.",
     {"medal": ["REALES", "1825", "FERNANDO VII"]}),
    ("primeros", "Los primeros soles",
     "La primera Ley Monetaria de la República sale de la Asamblea Constituyente del 17 de agosto de 1825. En 1830 llegan las monedas febles, con el año y los ensayadores congelados: se siguieron acuñando hasta 1853.",
     {"medal": ["8 S", "1827", "REPUBLICA BOLIVIANA"]}),
    ("potosi", "El siglo de Potosí",
     "Bolívar vestido de civil, la cabeza descubierta y el árbol abierto estilo Potosí. En esta época aparecen el cuartillo tipo llamita de 1852 y el sol de Oruro de 1849.",
     {"img": "img/home/sol_a.webp", "alt": "8 Soles 1841, Potosí"}),
    ("lapaz", "La casa de moneda de La Paz",
     "La Paz acuña con su propio cuño: cabeza descubierta, estilo Potosí, estilo La Paz y la famosa cabeza enojada.",
     {"medal": ["4 S", "LA PAZ", "REPUBLICA BOLIVIANA"]}),
    ("frias", "Tostones Frías",
     "Seis variedades en pocos años: con peso, sin peso, con Pº y dos mulas. Un capítulo corto, lleno de detalles para el ojo entrenado.",
     {"medal": ["8 S", "1859", "TOSTONES FRIAS"]}),
    ("decimal", "Bolivianos y centavos",
     "El boliviano y los centavos que circularon hasta comienzos del siglo XX cierran, por ahora, el catálogo.",
     {"medal": ["20 CTS", "1885", "REPUBLICA DE BOLIVIA"]}),
]

_RAREZAS = [("U", "Una conocida"), ("ER", "Extremadamente rara"), ("RR", "Rarísima"),
            ("MR", "Muy rara"), ("R", "Rara"), ("E", "Escasa"), ("C", "Común"), ("MC", "Muy común")]


def _epoca_de(nombre: str, anios: list[int]) -> str:
    n = nombre.upper()
    if n.startswith("REALES"):
        return "reales"
    if "TOSTONES FRIAS" in n:
        return "frias"
    if "LA PAZ" in n:
        return "lapaz"
    if "BOLIVIANO" in n or "CENTAVO" in n:
        return "decimal"
    if anios and min(anios) <= 1830:
        return "primeros"
    if anios and min(anios) > 1863:
        return "decimal"
    return "potosi"


def _catalogo(db: Session):
    """Series activas agrupadas en épocas, conteo de variantes y rarezas."""
    rows = db.execute(text("""
        SELECT s.nombre, count(v.id) AS n
        FROM series s LEFT JOIN serie_variantes v ON v.serie_id = s.id
        WHERE s.activo
        GROUP BY s.id
    """)).fetchall()
    grupos = {k: {"series": 0, "vars": 0, "anios": []} for k, *_ in _EPOCAS}
    for nombre, n in rows:
        anios = [int(a) for a in re.findall(r"\b1[89]\d\d\b", nombre)]
        g = grupos[_epoca_de(nombre, anios)]
        g["series"] += 1
        g["vars"] += n
        g["anios"] += anios
    epocas = []
    for key, titulo, texto, visual in _EPOCAS:
        g = grupos[key]
        if not g["series"]:
            continue
        a, b = (min(g["anios"]), max(g["anios"])) if g["anios"] else (None, None)
        cuando = "" if a is None else (str(a) if a == b else f"{a}–{b}")
        epocas.append({"cuando": cuando, "desde": str(a or ""), "titulo": titulo,
                       "texto": texto, "series": g["series"], "vars": g["vars"], **visual})

    # La rareza va como texto libre en la nota de cada variante.
    rar = dict(db.execute(text("""
        SELECT CASE
          WHEN nota ILIKE '%extremadamente%' THEN 'ER'
          WHEN nota ILIKE '%rar_sima%'       THEN 'RR'
          WHEN nota ILIKE '%muy rara%'       THEN 'MR'
          WHEN nota ILIKE '%rara%'           THEN 'R'
          WHEN nota ILIKE '%escasa%'         THEN 'E'
          WHEN nota ILIKE '%muy com%'        THEN 'MC'
          WHEN nota ILIKE '%com_n%'          THEN 'C'
          WHEN nota ILIKE '%una conocida%' OR nota ILIKE '%_nica%' THEN 'U'
          ELSE '-' END AS k, count(*)
        FROM serie_variantes GROUP BY 1
    """)).fetchall())
    tope = max([rar.get(c, 0) for c, _ in _RAREZAS] + [1])
    rarezas = [{"code": c, "name": n, "n": rar.get(c, 0),
                "pct": round(rar.get(c, 0) / tope * 100, 1)} for c, n in _RAREZAS]
    return {
        "epocas": epocas,
        "rarezas": rarezas,
        "series": len(rows),
        "variantes": sum(n for _, n in rows),
        "sin_grado": rar.get("-", 0),
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)

    anuncios = (
        db.query(Anuncio)
        .filter(Anuncio.activo == True)
        .order_by(Anuncio.orden, Anuncio.id)
        .all()
    )

    catalogo = _catalogo(db)
    stats = {
        "series":         catalogo["series"],
        "variantes":      catalogo["variantes"],
        "coleccionistas": db.query(func.count(User.id)).scalar(),
        "monedas":        db.query(func.count(Coin.id)).scalar(),
    }

    # Mercado y preguntas son solo para usuarios registrados: a las visitas
    # se les muestra un ejemplo en lugar de contenido real.
    listing = pregunta = respuesta = None
    if user:
        listing = (
            db.query(Listing)
            .filter(Listing.status == ListingStatus.activo, Listing.image_url.isnot(None))
            .order_by(Listing.created_at.desc())
            .first()
        )
        pregunta = (
            db.query(Pregunta)
            .filter(Pregunta.respuestas.any())
            .order_by(Pregunta.created_at.desc())
            .first()
        )
        if pregunta:
            respuesta = min(pregunta.respuestas, key=lambda r: (not r.is_best, r.created_at))

    return templates.TemplateResponse(request, "home.html", {
        "user": user,
        "anuncios": anuncios,
        "stats": stats,
        "catalogo": catalogo,
        "listing": listing,
        "pregunta": pregunta,
        "respuesta": respuesta,
    })
