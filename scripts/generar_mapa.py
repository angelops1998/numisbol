"""Genera app/static/img/mundo.svg desde world-atlas (Natural Earth, dominio público).

Uso (una sola vez, no corre en el servidor; necesita `pip install pycountry`):
    curl -sL -o geo/c110.json https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json
    curl -sL -o geo/c50.json  https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json
    python scripts/generar_mapa.py geo app/static/img/mundo.svg app/paises.py

Proyección Equal Earth. Cada país es <path data-iso="bo">. Los que no existen en
110m se toman de 50m; los diminutos además llevan un punto marcador.
"""
import json, math, sys, re
import pycountry

GEO = sys.argv[1]
OUT = sys.argv[2]
PAISES_PY = sys.argv[3]

W = 1000.0

src = open(PAISES_PY, encoding="utf-8").read()
app_isos = set(re.findall(r'":\s*\("([a-z]{2})"', src))

NOMBRES = {"Kosovo": "xk", "N. Cyprus": None, "Somaliland": None, "Antarctica": None}


def decode(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
            pts.extend(a if not pts else a[1:])
        return pts

    out = {}
    for g in topo["objects"]["countries"]["geometries"]:
        name = g["properties"].get("name", "")
        gid = g.get("id")
        iso = None
        if name in NOMBRES:
            iso = NOMBRES[name]
        elif gid:
            c = pycountry.countries.get(numeric=gid)
            iso = c.alpha_2.lower() if c else None
        if not iso:
            continue
        if g["type"] == "Polygon":
            polys = [[ring(r) for r in g["arcs"]]]
        elif g["type"] == "MultiPolygon":
            polys = [[ring(r) for r in p] for p in g["arcs"]]
        else:
            continue
        out.setdefault(iso, []).extend(polys)
    return out


# Equal Earth
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def ee(lon, lat):
    l, p = math.radians(lon), math.radians(lat)
    t = math.asin(M * math.sin(p))
    t2 = t * t; t6 = t2 * t2 * t2
    x = l * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


XMAX = ee(180, 0)[0]
YMAX = ee(0, 90)[1]
S = W / (2 * XMAX)
H = round(2 * YMAX * S * (84 + 60) / 180)  # recortamos: de 84°N a ~60°S
Y_TOP = ee(0, 84)[1]


def proj(lon, lat):
    x, y = ee(lon, lat)
    return (x + XMAX) * S, (Y_TOP - y) * S


H = math.ceil(proj(0, -60)[1]) + 1


def desenvolver(r):
    """Los anillos que cruzan el meridiano 180 saltan de +180 a -180: los volvemos
    continuos (pueden pasar de ±180) y devolvemos también la copia del otro lado.
    El recorte con el contorno del globo se encarga del resto."""
    out = [r[0]]
    for lon, lat in r[1:]:
        prev = out[-1][0]
        while lon - prev > 180: lon -= 360
        while lon - prev < -180: lon += 360
        out.append((lon, lat))
    lons = [p[0] for p in out]
    anillos = [out]
    if max(lons) > 180:
        anillos.append([(lo - 360, la) for lo, la in out])
    if min(lons) < -180:
        anillos.append([(lo + 360, la) for lo, la in out])
    return anillos


def path(polys, tol):
    d = []
    for poly in polys:
        for r in (a for ring in poly for a in desenvolver(ring)):
            pts = [proj(*p) for p in r]
            simp = [pts[0]]
            for p in pts[1:]:
                if abs(p[0] - simp[-1][0]) + abs(p[1] - simp[-1][1]) >= tol:
                    simp.append(p)
            if len(simp) < 3:
                continue
            px, py = round(simp[0][0], 1), round(simp[0][1], 1)
            seg = [f"M{px:g} {py:g}"]
            for x, y in simp[1:]:
                x, y = round(x, 1), round(y, 1)
                dx, dy = round(x - px, 1), round(y - py, 1)
                if dx or dy:
                    seg.append(f"l{dx:g} {dy:g}")
                px, py = x, y
            d.append("".join(seg) + "z")
    return "".join(d).replace(" -", "-")


def bbox_area(polys):
    xs, ys = [], []
    for poly in polys:
        for x, y in (proj(*p) for p in poly[0]):
            xs.append(x); ys.append(y)
    return (max(xs) - min(xs)) * (max(ys) - min(ys)), ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def mayor(polys):
    """Centro del polígono más grande (para el punto marcador)."""
    best = max(polys, key=lambda p: bbox_area([p])[0])
    return bbox_area([best])[1]


g110 = decode(json.load(open(f"{GEO}/c110.json")))
g50 = decode(json.load(open(f"{GEO}/c50.json")))

# La Guayana Francesa viene dentro de Francia: la separamos.
for g in (g110, g50):
    if "fr" in g:
        sud = [p for p in g["fr"] if p[0][0][0] < -30]
        g["fr"] = [p for p in g["fr"] if p[0][0][0] >= -30]
        if sud:
            g["gf"] = sud

# Territorios sin forma en Natural Earth: solo un punto (lon, lat).
EXTRA = {"cc": (96.83, -12.17), "gi": (-5.35, 36.14), "gp": (-61.55, 16.25),
         "mq": (-61.02, 14.64), "re": (55.53, -21.12), "tk": (-171.85, -9.2),
         "tv": (179.2, -8.5)}

paths, dots, faltan = [], [], []
for iso, (lon, lat) in EXTRA.items():
    if iso in app_isos and iso not in g110 and iso not in g50:
        cx, cy = proj(lon, lat)
        dots.append(f'<circle data-iso="{iso}" cx="{cx:.1f}" cy="{cy:.1f}" r="2.6"/>')
for iso in sorted(set(g110) | set(g50)):
    polys = g110.get(iso) or g50[iso]
    tol = 0.6 if iso in g110 else 0.25
    d = path(polys, tol)
    area, _ = bbox_area(polys)
    if d:
        paths.append(f'<path data-iso="{iso}" d="{d}"/>')
    if area < 14 and iso in app_isos:
        cx, cy = mayor(polys)
        dots.append(f'<circle data-iso="{iso}" cx="{cx:.1f}" cy="{cy:.1f}" r="2.6"/>')

for iso in sorted(app_isos - set(g110) - set(g50) - set(EXTRA)):
    faltan.append(iso)

def linea(pts, cerrar=False):
    pts = [proj(lo, la) for lo, la in pts]
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + ("z" if cerrar else "")

LAT0, LAT1 = -60, 84
borde = ([(-180, la) for la in range(LAT0, LAT1 + 1, 2)] + [(lo, LAT1) for lo in range(-180, 181, 10)]
         + [(180, la) for la in range(LAT1, LAT0 - 1, -2)] + [(lo, LAT0) for lo in range(180, -181, -10)])
grilla = [linea([(lo, la) for la in range(LAT0, LAT1 + 1, 4)]) for lo in range(-150, 151, 30)]
grilla += [linea([(lo, la) for lo in range(-180, 181, 6)]) for la in (-30, 0, 30, 60)]

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:g} {H}" class="mapa-svg" role="img" aria-label="Mapa del mundo">'
       f'<defs><clipPath id="mapaGlobo"><path d="{linea(borde, True)}"/></clipPath></defs>'
       f'<path class="mapa-globo" d="{linea(borde, True)}"/>'
       f'<path class="mapa-grilla" d="{"".join(grilla)}"/>'
       f'<g class="mapa-paises" clip-path="url(#mapaGlobo)">{"".join(paths)}</g>'
       f'<g class="mapa-puntos">{"".join(dots)}</g></svg>')
open(OUT, "w").write(svg)
print("bytes", len(svg), "paths", len(paths), "dots", len(dots), "H", H)
print("sin forma en el mapa:", faltan)
