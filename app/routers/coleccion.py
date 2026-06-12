import os, shutil, uuid
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from ..database import get_db
from ..models.coin import Coin, CustomOption
from ..auth import get_current_user, get_current_user_optional

router = APIRouter(prefix="/coleccion", tags=["coleccion"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "app/static/img/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CONDITIONS = [
    ("Circuladas", [
        "1 – Poor → Muy mala conservación (casi ilegible, desgaste extremo)",
        "2 – Fair → Regular (muy desgastada, diseño apenas reconocible)",
        "3 – About Good → Casi buena (contornos visibles, mucho desgaste)",
        "4 – Good → Buena (diseño principal visible, fuerte desgaste)",
        "6 – Very Good → Muy buena (detalles importantes aún claros)",
        "8 – Fine → Fina (desgaste medio, buen nivel de detalle)",
        "12 – Very Fine → Muy fina (desgaste leve, detalles completos en su mayoría)",
        "20 – Extremely Fine → Extremadamente fina (desgaste mínimo, casi todos los detalles visibles)",
    ]),
    ("Sin circular", [
        "40 – About Uncirculated → Casi sin circular (leve desgaste por manejo)",
        "50 – BU (Brilliant Uncirculated) → Sin circular brillante (sin desgaste de circulación, conserva brillo de ceca, puede tener pequeñas marcas de contacto)",
        "60 – Uncirculated → Sin circular (sin desgaste, acuñación intacta)",
        "63 – Choice Uncirculated → Sin circular selecta (excelente estado, mínimos defectos)",
        "65 – Gem Uncirculated → Gema sin circular (estado superior, casi perfecta)",
        "67 – Superb Gem → Gema superb (calidad excepcional, casi perfecta incluso bajo lupa)",
        "70 – Perfect Proof / Mint State → Perfecta (sin defectos visibles, máxima calidad)",
    ]),
]

ASSAYER_GROUPS = [
    ("Potosí", [
        "JM — Juan Palomo y Sierra; Diego Miguel López (1827-1829)",
        "J — Juan Palomo y Sierra (1830)",
        "JF — Juan Palomo y Sierra; Francisco José de Matos (1830-1831)",
        "JL — Juan Palomo y Sierra; Luis de Aguilar (1830-1852)",
        "L — Luis de Aguilar (1833)",
        "LM — Luis de Aguilar; Diego Miguel López (1833-1855)",
        "LR — Luis de Aguilar; Rafael Mariano Bustillos (1839-1844)",
        "R — Rafael Mariano Bustillos (1844-1847)",
        "M — Manuel Berrios (1848-1855)",
        "R — Manuel Telésforo Ramírez (1848)",
        "M — Fortunato Eguivar; Manuel Berrios (1848-1852)",
        "FR — Fortunato Eguivar; Manuel Telésforo Ramírez (1851)",
        "FP — Fortunato Eguivar; Pedro Zambrana (1852-1857)",
        "MF — Manuel Berrios; Fortunato Eguivar (1851-1855)",
        "MJ — Manuel Berrios; Joaquín Zenobraín (1852-1856)",
        "FS — Fortunato Eguivar; 2do ensayador desconocido (1855-1856)",
        "FJ — Fortunato Eguivar; Joaquín Zenobraín (1856-1862)",
        "FP — Fortunato Eguivar; Pedro Zambrana (1862-1871)",
        "FE — Fortunato Eguivar (1867-1890)",
        "ER — Fortunato Eguivar; Manuel Telésforo Ramírez (1870-1872)",
        "EF — Fortunato Eguivar (1871)",
        "CB — Carlos Bogen (1890-1893)",
        "ES — Edmundo Sleverlink (1894-1897)",
        "CB — Carlos Bogen (1896-1899)",
        "MM — Mariano Mattos (1898-1908)",
        "AB — Arturo Berrios (1905-1906)",
    ]),
    ("Oruro", [
        "JM — Joaquín Zenobraín; Manuel Berrios (1849)",
    ]),
    ("La Paz", [
        "J — Joaquín Zenobraín (1853)",
        "F — Fortunato Eguivar (1854-1855)",
        "P — Pedro Zambrana (1855-1859)",
    ]),
    ("La Plata", [
        "J — Joaquín Zenobraín (1853)",
    ]),
    ("La Paz-Potosí", [
        "CT — Clemente Torretti (1868; 1870)",
    ]),
]

ASSAYERS = [a for _, items in ASSAYER_GROUPS for a in items]

MATERIAL_GROUPS = [
    ("Metales puros", [
        "Plata", "Electro", "Platino", "Paladio", "Cobre", "Bronce", "Latón",
        "Níquel", "Aluminio", "Zinc", "Hierro", "Acero", "Acero inoxidable",
        "Estaño", "Plomo", "Titanio", "Magnesio", "Cobalto",
    ]),
    ("Aleaciones de dos metales", [
        "Oro y cobre", "Oro y plata", "Plata y cobre", "Plata y níquel",
        "Cobre y níquel", "Cobre y zinc", "Cobre y aluminio",
        "Níquel y latón", "Bronce de aluminio",
    ]),
    ("Aleaciones históricas", [
        "Billón", "Vellón", "Potín",
    ]),
    ("Aleaciones especiales", [
        "Cuproníquel", "Nordic Gold", "Alpaca", "Metal blanco",
    ]),
    ("Acero tratado", [
        "Acero niquelado", "Acero cobrizado", "Acero latonado", "Acero zincado",
    ]),
    ("Compuestas", [
        "Bimetálica", "Trimetálica",
    ]),
]

MATERIALS = [m for _, items in MATERIAL_GROUPS for m in items]

CATEGORY_GROUPS = [
    ("Tipo de emisión", [
        "Circulación", "Conmemorativa", "Coleccionista", "Bullion", "Inversión",
        "No circulada", "Proof", "BU", "Prooflike",
    ]),
    ("Período histórico", [
        "Colonial", "Virreinal", "Republicana", "Imperial", "Monárquica",
        "Moderna", "Contemporánea", "Antigua", "Medieval",
    ]),
    ("Composición especial", [
        "Bimetálica", "Trimetálica", "Colorizada",
    ]),
    ("Sustitutos monetarios", [
        "Token", "Ficha", "Jetón", "Vale", "Moneda local", "Dinero privado",
    ]),
    ("Medallas", [
        "Medalla", "Medalla religiosa", "Medalla militar", "Medalla deportiva",
    ]),
    ("Errores y variedades", [
        "Error", "Error de acuñación", "Error de cospel", "Error de troquel",
        "Error de centrado", "Doble acuñación", "Doble troquel",
        "Troquel roto", "Troquel desplazado", "Sobrefecha",
    ]),
    ("Marcas adicionales", [
        "Resello", "Contramarca", "Contramarcada",
    ]),
    ("Técnica de acuñación", [
        "Macuquina", "A martillo", "Mecanizada",
    ]),
    ("Patrones y pruebas", [
        "Patrón", "Pattern", "Prueba", "Ensayo", "Trial", "Experimental",
        "Prototipo", "Proyecto no emitido", "No emitida",
    ]),
    ("Acabado especial", [
        "UNC", "Brilliant Uncirculated", "Reverse Proof", "Matte Proof",
        "Specimen", "SMS", "Special Mint Set", "Antique Finish",
        "High Relief", "Ultra High Relief", "Low Relief",
    ]),
    ("Tratamiento superficial", [
        "Dorada", "Plateada", "Chapada", "Bañada en oro", "Bañada en plata",
        "Holográfica", "Con inserto", "Con gema", "Con cristal", "Con esmalte",
    ]),
    ("Forma y estructura", [
        "Multimetálica", "Perforada", "Recortada", "Poligonal", "Cuadrada",
        "Rectangular", "Ovalada", "Escalonada", "Piefort",
    ]),
    ("Proceso de fabricación", [
        "Sobreacuñación", "Reacuñada", "Regrabada", "Reutilizada",
        "Fundida", "A molino", "A volante", "A prensa",
    ]),
    ("Nivel gubernamental", [
        "Real", "Provincial", "Federal", "Nacional", "Estatal",
        "Municipal", "Local", "Autonómica",
    ]),
    ("Período numismático", [
        "Clásica", "Helenística", "Romana", "Bizantina", "Renacentista",
        "Feudal", "Principesca", "Ducal", "Eclesiástica", "Papal", "Cruzada",
    ]),
    ("Colonialismo", [
        "Colonial española", "Colonial portuguesa", "Colonial británica",
        "Colonial francesa", "Colonial neerlandesa",
    ]),
    ("Emergencia y conflicto", [
        "Ocupación", "Militar", "Campaña militar", "Asedio", "Emergencia",
        "Necesidad", "Guerra", "Posguerra", "Refugiados",
        "Campo de prisioneros", "Campo de concentración", "Gueto",
    ]),
    ("Emisores privados", [
        "Empresa", "Comercial", "Minera", "Ferroviaria", "Transporte",
        "Plantación", "Hacienda", "Cooperativa", "Sindical",
        "Casino", "Juego", "Apuesta",
    ]),
    ("Moneda alternativa", [
        "Voucher", "Bono monetario", "Moneda comunitaria",
        "Moneda alternativa", "Moneda complementaria", "Moneda digital física",
    ]),
    ("Coleccionismo moderno", [
        "Fantasía", "Fantasía numismática", "Réplica", "Copia",
        "Reproducción", "Restrike", "Nueva acuñación", "Reacuñación moderna",
    ]),
    ("Conmemorativas por tema", [
        "Conmemorativa deportiva", "Conmemorativa militar", "Conmemorativa religiosa",
        "Conmemorativa histórica", "Conmemorativa política", "Conmemorativa cultural",
    ]),
    ("Ocasiones especiales", [
        "Aniversario", "Jubileo", "Coronación", "Independencia",
        "Centenario", "Bicentenario", "Milenario", "Inaugural",
    ]),
    ("Propósito especial", [
        "Promocional", "Publicitaria", "Turística", "Educativa",
        "Benéfica", "Caritativa", "Propaganda",
    ]),
    ("Medallas especializadas", [
        "Medalla académica", "Medalla masónica", "Medalla de exposición",
        "Medalla de premio", "Medalla artística",
    ]),
    ("Objetos monetiformes", [
        "Decoración", "Insignia monetiforme",
    ]),
]

CATEGORIES = [c for _, items in CATEGORY_GROUPS for c in items]

CURRENCY_UNITS = [
    "Real", "Escudo", "Peso", "Sol", "Boliviano", "Dólar", "Cent", "Centavo", "Centésimo",
    "Euro", "Franco", "Centime", "Libra", "Pound", "Penny", "Pence", "Farthing", "Halfpenny",
    "Crown", "Shilling", "Guinea", "Sovereign", "Noble", "Angel", "Groat",
    "Florín", "Florin", "Gulden", "Guilder", "Ducat", "Ducado",
    "Thaler", "Taler", "Mark", "Marco", "Pfennig", "Fenig", "Groschen", "Grosz",
    "Kreuzer", "Heller", "Corona", "Krona", "Krone", "Koruna",
    "Rublo", "Kopek", "Denga", "Poltina", "Altyn", "Grivna", "Hryvnia",
    "Zloty", "Forint", "Lei", "Ban", "Lev", "Stotinka",
    "Dinar", "Dirham", "Fils", "Piastre", "Qirsh", "Kurus", "Para", "Akçe",
    "Riyal", "Halala", "Toman", "Rial", "Shekel", "Agora", "Agorot",
    "Rupia", "Rupee", "Paisa", "Anna", "Pice", "Pie", "Mohur", "Fanam", "Pagoda", "Cash",
    "Tael", "Liang", "Mace", "Candareen", "Yuan", "Renminbi", "Jiao", "Fen", "Wen",
    "Yen", "Sen", "Rin", "Mon", "Won", "Jeon", "Mun",
    "Dong", "Hao", "Xu", "Baht", "Satang", "Tical", "Kip", "Att",
    "Ringgit", "Pataca", "Avo", "Riel", "Santeem", "Kyat", "Pyas",
    "Ngultrum", "Chhertum", "Tenge", "Tiyn", "Som", "Tyiyn", "Manat", "Qepik",
    "Lari", "Tetri", "Afghani", "Pul",
    "Sucre", "Balboa", "Quetzal", "Colón", "Córdoba", "Guaraní",
    "Cruzeiro", "Cruzado", "Cruzado Novo", "Real Brasileiro", "Austral",
    "Peso Convertible", "Inti", "Nuevo Sol", "Sol Peruano",
    "Escudo Chileno", "Escudo Portugués", "Peseta",
    "Maravedí", "Blanca", "Cornado", "Ochavo", "Dobla", "Excelente", "Enrique",
    "Reale", "Lira", "Testone", "Scudo",
    "Denario", "Denier", "Livre", "Sou", "Liard", "Écu",
    "Dracma", "Lepton", "Obolo", "Estatero", "Tetradracma", "Didracma",
    "Denarius", "Sestercio", "Dupondio", "As", "Semis", "Quadrans",
    "Aureus", "Solidus", "Follis", "Tremissis", "Bezant", "Hyperpyron",
    "Prutah", "Daric", "Siglos",
    "Sapèque", "Mohar", "Pagode", "Fanon", "Pagoda de Oro", "Mohur de Oro",
    "Trade Dollar", "Straits Dollar", "Peso Fuerte", "Real de a Ocho",
    "Piece of Eight", "Patagón", "Lion Dollar", "Riksdaler", "Speciedaler",
    "Banco", "Mithqal", "Doblón", "Onza", "Escalin", "Stuiver", "Rappen",
    "Ore", "Öre", "Heller Austriaco", "Krajczár", "Pengő",
    "Mil", "Mils", "Fenin", "Fenin Bosnio", "Markka", "Penni",
    "Dalasi", "Butut", "Lempira", "Ariary", "Iraimbilanja",
    "Ouguiya", "Khoums", "Leone", "Cedi", "Pesewa",
    "Naira", "Kobo", "Rand", "Pula", "Thebe", "Metical",
    "Kwacha", "Tambala", "Ngwee",
]

DENOMINATIONS = [
    "1", "2", "3", "4", "5", "6", "8", "10", "12", "15",
    "20", "25", "30", "40", "50", "60", "75", "80",
    "100", "125", "200", "250", "500", "1000", "2000", "5000",
    "10000", "20000", "50000", "100000", "1000000",
    "1/2", "1/4", "1/8", "1/10", "1/12", "1/16", "3/4",
]

COUNTRIES = [
    "Afganistán", "Åland", "Albania", "Alemania", "Andorra", "Angola", "Anguila",
    "Antártida", "Antigua y Barbuda", "Arabia Saudita", "Argelia", "Argentina",
    "Armenia", "Aruba", "Australia", "Austria", "Azerbaiyán",
    "Bahamas", "Bangladés", "Barbados", "Baréin", "Bélgica", "Belice", "Benín",
    "Bermudas", "Bielorrusia", "Bolivia", "Bonaire, San Eustaquio y Saba",
    "Bosnia y Herzegovina", "Botsuana", "Brasil", "Brunéi", "Bulgaria",
    "Burkina Faso", "Burundi", "Bután",
    "Cabo Verde", "Camboya", "Camerún", "Canadá", "Catar", "Chad", "Chile",
    "China", "Chipre", "Colombia", "Comoras", "Corea del Norte", "Corea del Sur",
    "Costa de Marfil", "Costa Rica", "Croacia", "Cuba", "Curazao",
    "Dinamarca", "Dominica",
    "Ecuador", "Egipto", "El Salvador", "Emiratos Árabes Unidos", "Eritrea",
    "Eslovaquia", "Eslovenia", "España", "Estados Unidos", "Estonia", "Etiopía",
    "Filipinas", "Finlandia", "Fiyi", "Francia",
    "Gabón", "Gambia", "Georgia", "Ghana", "Gibraltar", "Granada", "Grecia",
    "Groenlandia", "Guadalupe", "Guam", "Guatemala", "Guayana Francesa",
    "Guernsey", "Guinea", "Guinea Ecuatorial", "Guinea-Bisáu", "Guyana",
    "Haití", "Honduras", "Hong Kong", "Hungría",
    "India", "Indonesia", "Irak", "Irán", "Irlanda", "Isla Bouvet",
    "Isla de Man", "Isla de Navidad", "Islandia", "Islas Caimán", "Islas Cocos",
    "Islas Cook", "Islas Feroe", "Islas Georgias del Sur y Sandwich del Sur",
    "Islas Heard y McDonald", "Islas Malvinas", "Islas Marianas del Norte",
    "Islas Marshall", "Islas Pitcairn", "Islas Salomón", "Islas Turcas y Caicos",
    "Islas ultramarinas de Estados Unidos", "Islas Vírgenes Británicas",
    "Islas Vírgenes de los Estados Unidos", "Israel", "Italia",
    "Jamaica", "Japón", "Jersey", "Jordania",
    "Kazajistán", "Kenia", "Kirguistán", "Kiribati", "Kuwait",
    "Laos", "Lesoto", "Letonia", "Líbano", "Liberia", "Libia", "Liechtenstein",
    "Lituania", "Luxemburgo",
    "Macao", "Macedonia", "Madagascar", "Malasia", "Malaui", "Maldivas", "Malí",
    "Malta", "Marruecos", "Martinica", "Mauricio", "Mauritania", "Mayotte",
    "México", "Micronesia", "Moldavia", "Mónaco", "Mongolia", "Montenegro",
    "Montserrat", "Mozambique", "Myanmar",
    "Namibia", "Nauru", "Nepal", "Nicaragua", "Níger", "Nigeria", "Niue",
    "Norfolk", "Noruega", "Nueva Caledonia", "Nueva Zelanda",
    "Omán",
    "Países Bajos", "Pakistán", "Palaos", "Palestina", "Panamá",
    "Papúa Nueva Guinea", "Paraguay", "Perú", "Polinesia Francesa", "Polonia",
    "Portugal", "Puerto Rico",
    "Reino Unido", "República Árabe Saharaui Democrática", "República Centroafricana",
    "República Checa", "República del Congo", "República Democrática del Congo",
    "República Dominicana", "Reunión", "Ruanda", "Rumania", "Rusia",
    "Samoa", "Samoa Americana", "San Bartolomé", "San Cristóbal y Nieves",
    "San Marino", "San Martín", "San Pedro y Miquelón",
    "San Vicente y las Granadinas", "Santa Elena, Ascensión y Tristán de Acuña",
    "Santa Lucía", "Santo Tomé y Príncipe", "Senegal", "Serbia", "Seychelles",
    "Sierra Leona", "Singapur", "Sint Maarten", "Siria", "Somalia", "Sri Lanka",
    "Suazilandia", "Sudáfrica", "Sudán", "Sudán del Sur", "Suecia", "Suiza",
    "Surinam", "Svalbard y Jan Mayen",
    "Tailandia", "Taiwán (República de China)", "Tanzania", "Tayikistán",
    "Territorio Británico del Océano Índico", "Tierras Australes y Antárticas Francesas",
    "Timor Oriental", "Togo", "Tokelau", "Tonga", "Trinidad y Tobago", "Túnez",
    "Turkmenistán", "Turquía", "Tuvalu",
    "Ucrania", "Uganda", "Uruguay", "Uzbekistán",
    "Vanuatu", "Vaticano, Ciudad del", "Venezuela", "Vietnam",
    "Wallis y Futuna",
    "Yemen", "Yibuti",
    "Zambia", "Zimbabue",
]

MINTS_BOLIVIA = [
    "Potosí",
    "Oruro",
    "La Paz",
    "La Paz - Potosí",
]

MINTS_WORLD = [
    "Lima", "México", "Bogotá", "Santiago", "Guatemala", "Santo Domingo",
    "Popayán", "Cuzco", "La Plata",
    "Madrid", "Sevilla", "Segovia", "Barcelona", "Granada", "Valencia",
    "Toledo", "Burgos", "Pamplona", "Zaragoza",
    "París", "Lyon", "Burdeos", "Lille", "Marsella", "Rouen",
    "Londres", "Tower Hill", "Birmingham", "Edimburgo", "Cardiff", "Dublín",
    "Berlín", "Múnich", "Hamburgo", "Dresde", "Stuttgart", "Karlsruhe",
    "Viena", "Praga", "Budapest",
    "Varsovia", "Cracovia",
    "Moscú", "San Petersburgo", "Ekaterimburgo",
    "Helsinki", "Estocolmo", "Oslo", "Copenhague",
    "Ámsterdam", "Utrecht", "Bruselas", "Amberes",
    "Lisboa", "Oporto",
    "Roma", "Milán", "Turín", "Nápoles", "Venecia", "Florencia", "Génova", "Palermo",
    "Atenas", "Constantinopla", "Antioquía", "Alejandría", "Cartago",
    "Nicomedia", "Tesalónica", "Tréveris", "Lugdunum",
    "Filadelfia", "Denver", "San Francisco", "West Point", "Carson City",
    "Nueva Orleans", "Charlotte", "Dahlonega",
    "Ottawa", "Winnipeg",
    "Perth", "Sídney", "Melbourne", "Canberra", "Wellington", "Auckland",
    "Pekín", "Shanghái", "Nankín", "Cantón", "Hong Kong",
    "Tokio", "Osaka", "Kioto", "Seúl", "Pyongyang", "Taipéi",
    "Bangkok", "Manila", "Yakarta", "Singapur",
    "Calcuta", "Mumbai", "Hyderabad", "Lahore", "Karachi", "Colombo",
    "El Cairo", "Pretoria", "Ciudad del Cabo", "Johannesburgo",
    "Casablanca", "Argel", "Túnez", "Addis Abeba",
    "México DF", "Buenos Aires", "Córdoba", "Montevideo", "Asunción",
    "Quito", "Caracas", "La Habana", "San José", "Panamá",
    "Managua", "Tegucigalpa", "Santiago de Chile",
    "Brasilia", "Río de Janeiro", "São Paulo", "Salvador", "Recife",
]


ALL_MINTS = set(MINTS_BOLIVIA) | set(MINTS_WORLD)
ALL_CURRENCY_UNITS = set(CURRENCY_UNITS)


def save_custom_option(db: Session, field_name: str, value: str, predefined: set):
    """Persiste un valor personalizado si no está en la lista predefinida."""
    if not value or value in predefined:
        return
    exists = db.query(CustomOption).filter_by(field_name=field_name, value=value).first()
    if not exists:
        db.add(CustomOption(field_name=field_name, value=value))


def get_custom_options(db: Session, field_name: str) -> list:
    return [
        r.value for r in
        db.query(CustomOption).filter_by(field_name=field_name)
        .order_by(CustomOption.value).all()
    ]


def save_upload(file: UploadFile) -> Optional[str]:
    """Guarda un archivo subido y devuelve la URL relativa."""
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return f"/static/img/uploads/{filename}"


PER_PAGE = 24

# ── Listar / filtrar ─────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def coleccion(
    request: Request,
    q: str = "",
    categoria: str = "",
    condicion: str = "",
    material: str = "",
    anio_desde: str = "",
    anio_hasta: str = "",
    orden: str = "reciente",
    pagina: int = 1,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    query = db.query(Coin).filter(Coin.user_id == user.id)

    if q:
        query = query.filter(
            or_(
                Coin.name.ilike(f"%{q}%"),
                Coin.denomination.ilike(f"%{q}%"),
                Coin.mint.ilike(f"%{q}%"),
                Coin.country.ilike(f"%{q}%"),
                Coin.description.ilike(f"%{q}%"),
                Coin.currency_unit.ilike(f"%{q}%"),
                Coin.material.ilike(f"%{q}%"),
            )
        )

    if categoria:
        query = query.filter(Coin.category == categoria)
    if condicion:
        query = query.filter(Coin.condition == condicion)
    if material:
        query = query.filter(Coin.material == material)
    if anio_desde.isdigit():
        query = query.filter(Coin.year >= int(anio_desde))
    if anio_hasta.isdigit():
        query = query.filter(Coin.year <= int(anio_hasta))

    if orden == "nombre":
        query = query.order_by(Coin.name)
    elif orden == "anio_asc":
        query = query.order_by(Coin.year.asc().nullslast())
    elif orden == "anio_desc":
        query = query.order_by(Coin.year.desc().nullslast())
    elif orden == "valor":
        query = query.order_by(Coin.estimated_value.desc().nullslast())
    else:
        query = query.order_by(Coin.created_at.desc())

    has_filters = any([q, categoria, condicion, material, anio_desde.isdigit(), anio_hasta.isdigit()])
    total_col = db.query(func.count(Coin.id)).filter(Coin.user_id == user.id).scalar()
    total_filtrado = query.count() if has_filters else total_col
    pagina = max(1, pagina)
    total_paginas = max(1, -(-total_filtrado // PER_PAGE))
    pagina = min(pagina, total_paginas)
    coins = query.offset((pagina - 1) * PER_PAGE).limit(PER_PAGE).all()

    filters = {
        "q": q, "categoria": categoria, "condicion": condicion,
        "material": material, "anio_desde": anio_desde,
        "anio_hasta": anio_hasta, "orden": orden,
    }

    flat_conditions = [c for _, items in CONDITIONS for c in items]
    flat_categories = [c for _, items in CATEGORY_GROUPS for c in items]

    return templates.TemplateResponse(request, "coleccion/lista.html", {
        "user": user,
        "coins": coins,
        "total": total_col,
        "total_filtrado": total_filtrado,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "filters": filters,
        "conditions": flat_conditions,
        "categories": flat_categories,
        "materials": MATERIALS,
    })


# ── Estadísticas ─────────────────────────────────────────────
@router.get("/estadisticas", response_class=HTMLResponse)
async def estadisticas(request: Request, tipo: str = "", db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    tipo_filter = tipo if tipo in ("moneda", "billete") else None

    def base():
        q = db.query(Coin).filter(Coin.user_id == user.id)
        if tipo_filter:
            q = q.filter(Coin.tipo == tipo_filter)
        return q

    def agg():
        q = db.query(func.count(Coin.id), func.sum(Coin.estimated_value)).filter(Coin.user_id == user.id)
        if tipo_filter:
            q = q.filter(Coin.tipo == tipo_filter)
        return q.one()

    def group_count(attr):
        col = getattr(Coin, attr)
        q = (db.query(col, func.count(Coin.id))
             .filter(Coin.user_id == user.id, col != None, col != ""))
        if tipo_filter:
            q = q.filter(Coin.tipo == tipo_filter)
        return q.group_by(col).order_by(func.count(Coin.id).desc()).all()

    # Totales por tipo (una sola query con GROUP BY tipo)
    tipo_rows = (db.query(Coin.tipo, func.count(Coin.id))
                 .filter(Coin.user_id == user.id)
                 .group_by(Coin.tipo).all())
    tipo_map = {(t or "moneda"): n for t, n in tipo_rows}
    total_monedas  = tipo_map.get("moneda", 0)
    total_billetes = tipo_map.get("billete", 0)

    total_raw, valor_sum = agg()
    total       = total_raw or 0
    total_valor = float(valor_sum or 0)
    valor_promedio = total_valor / total if total else 0

    por_pais      = group_count("country")
    por_material  = group_count("material")
    por_categoria = group_count("category")
    por_ceca      = group_count("mint")
    cond_raw      = group_count("condition")
    por_condicion = [(c.split(" → ")[0] if c else c, n) for c, n in cond_raw]

    # Distribución por siglo — GROUP BY en DB, no en Python
    siglo_rows = (db.query(
                     (Coin.year / 100 * 100).label("siglo"),
                     func.count(Coin.id))
                 .filter(Coin.user_id == user.id, Coin.year != None))
    if tipo_filter:
        siglo_rows = siglo_rows.filter(Coin.tipo == tipo_filter)
    siglo_rows = siglo_rows.group_by("siglo").order_by("siglo").all()
    por_siglo = [(int(s), n) for s, n in siglo_rows]

    sin_anio_q = db.query(func.count(Coin.id)).filter(Coin.user_id == user.id, Coin.year == None)
    if tipo_filter:
        sin_anio_q = sin_anio_q.filter(Coin.tipo == tipo_filter)
    sin_anio = sin_anio_q.scalar() or 0
    if sin_anio:
        por_siglo.append(("Sin año", sin_anio))

    return templates.TemplateResponse(request, "coleccion/estadisticas.html", {
        "user": user,
        "tipo": tipo,
        "total": total,
        "total_monedas": total_monedas,
        "total_billetes": total_billetes,
        "total_valor": total_valor,
        "valor_promedio": valor_promedio,
        "por_pais": por_pais,
        "por_material": por_material,
        "por_categoria": por_categoria,
        "por_condicion": por_condicion,
        "por_ceca": por_ceca,
        "por_siglo": por_siglo,
    })


# ── Países del mundo ─────────────────────────────────────────
@router.get("/paises", response_class=HTMLResponse)
async def paises(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    rows = (db.query(Coin.country, Coin.tipo, func.count(Coin.id))
            .filter(Coin.user_id == user.id, Coin.country != None, Coin.country != "")
            .group_by(Coin.country, Coin.tipo)
            .all())
    # tienen[country] = {"moneda": n, "billete": n, "total": n}
    tienen = {}
    for country, tipo, cnt in rows:
        t = tipo or "moneda"
        if country not in tienen:
            tienen[country] = {"moneda": 0, "billete": 0, "total": 0}
        tienen[country][t] = tienen[country].get(t, 0) + cnt
        tienen[country]["total"] += cnt
    return templates.TemplateResponse(request, "coleccion/paises.html", {
        "user": user,
        "countries": COUNTRIES,
        "tienen": tienen,
        "total_paises": len(COUNTRIES),
        "tienen_count": len(tienen),
    })


# ── API: búsqueda de monedas ─────────────────────────────────
@router.get("/api/search")
async def api_search_coins(request: Request, q: str = "", id: int = 0, limit: int = 15, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    base = db.query(Coin).filter(Coin.user_id == user.id, Coin.quantity > 0)
    if id:
        base = base.filter(Coin.id == id)
    else:
        q = q.strip()
        if q:
            filters = [Coin.name.ilike(f"%{q}%"), Coin.country.ilike(f"%{q}%")]
            if q.isdigit():
                filters.append(Coin.year == int(q))
            base = base.filter(or_(*filters))
    coins = base.order_by(Coin.name).limit(limit).all()
    return JSONResponse([{
        "id":        c.id,
        "name":      c.name,
        "year":      c.year,
        "country":   c.country or "",
        "condition": c.condition or "",
        "material":  c.material or "",
        "tipo":      c.tipo or "moneda",
        "img":       c.image_url or "",
    } for c in coins])


# ── Agregar ──────────────────────────────────────────────────
def _form_ctx(db: Session, extra: dict) -> dict:
    """Contexto base para el formulario de moneda."""
    return {
        "conditions": CONDITIONS,
        "assayer_groups": ASSAYER_GROUPS,
        "category_groups": CATEGORY_GROUPS,
        "materials": MATERIALS,
        "material_groups": MATERIAL_GROUPS,
        "denominations": DENOMINATIONS,
        "currency_units": CURRENCY_UNITS,
        "custom_currency_units": get_custom_options(db, "currency_unit"),
        "countries": COUNTRIES,
        "mints_bolivia": MINTS_BOLIVIA,
        "mints_world": MINTS_WORLD,
        "custom_mints": get_custom_options(db, "mint"),
        **extra,
    }


@router.get("/agregar", response_class=HTMLResponse)
async def agregar_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse(request, "coleccion/form.html",
        _form_ctx(db, {"user": user, "coin": None,
                       "action": "/coleccion/agregar", "title": "Agregar moneda"})
    )


@router.post("/agregar", response_class=HTMLResponse)
async def agregar(
    request: Request,
    tipo: str = Form("moneda"),
    name: str = Form(...),
    denomination: str = Form(""),
    currency_unit: str = Form(""),
    assayer: str = Form(""),
    year: str = Form(""),
    country: str = Form("Bolivia"),
    mint: str = Form(""),
    material: str = Form(""),
    condition: str = Form(""),
    category: str = Form(""),
    estimated_value: str = Form(""),
    purchase_price: str = Form(""),
    purchase_currency: str = Form("BOB"),
    purchase_usd_rate: str = Form(""),
    value_currency: str = Form("BOB"),
    quantity: str = Form("1"),
    description: str = Form(""),
    is_public: str = Form(""),
    image: UploadFile = File(None),
    image_back: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    errors = []

    if not name.strip():
        errors.append("El nombre es obligatorio.")

    def to_int(v): return int(v) if v.strip().isdigit() else None
    def to_decimal(v):
        try: return float(v.strip()) if v.strip() else None
        except: return None

    if errors:
        return templates.TemplateResponse(request, "coleccion/form.html",
            _form_ctx(db, {"user": user, "errors": errors, "action": "/coleccion/agregar",
                           "title": "Agregar moneda",
                           "coin": {
                               "tipo": tipo, "name": name, "denomination": denomination,
                               "currency_unit": currency_unit, "assayer": assayer,
                               "year": year, "country": country, "mint": mint,
                               "material": material, "condition": condition,
                               "category": category, "estimated_value": estimated_value,
                               "purchase_price": purchase_price,
                               "purchase_currency": purchase_currency,
                               "purchase_usd_rate": purchase_usd_rate,
                               "quantity": quantity,
                               "description": description, "is_public": bool(is_public),
                           }}),
            status_code=422)

    save_custom_option(db, "mint", mint.strip(), ALL_MINTS)
    save_custom_option(db, "currency_unit", currency_unit.strip(), ALL_CURRENCY_UNITS)

    es_billete = tipo == "billete"
    pc = purchase_currency if purchase_currency in ("BOB", "USD") else "BOB"
    coin = Coin(
        user_id          = user.id,
        tipo             = "billete" if es_billete else "moneda",
        name             = name.strip(),
        denomination     = denomination.strip() or None,
        currency_unit    = currency_unit.strip() or None,
        assayer          = None if es_billete else (assayer.strip() or None),
        year             = to_int(year),
        country          = country.strip() or "Bolivia",
        mint             = None if es_billete else (mint.strip() or None),
        material         = None if es_billete else (material.strip() or None),
        condition        = condition or None,
        category         = category or None,
        estimated_value  = to_decimal(estimated_value),
        purchase_price   = to_decimal(purchase_price),
        purchase_currency= pc,
        purchase_usd_rate= to_decimal(purchase_usd_rate) if pc == "USD" else None,
        value_currency   = value_currency if value_currency in ("BOB", "USD") else "BOB",
        quantity         = max(1, to_int(quantity) or 1),
        description      = description.strip() or None,
        is_public        = bool(is_public),
        image_url        = save_upload(image),
        image_back_url   = save_upload(image_back),
    )
    db.add(coin)
    db.commit()
    db.refresh(coin)
    return RedirectResponse(url="/coleccion", status_code=302)


# ── Ver detalle ───────────────────────────────────────────────
@router.get("/{coin_id}", response_class=HTMLResponse)
async def detalle(coin_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.user_id == user.id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada")
    return templates.TemplateResponse(request, "coleccion/detalle.html", {
        "user": user, "coin": coin,
    })


# ── Editar ────────────────────────────────────────────────────
@router.get("/{coin_id}/editar", response_class=HTMLResponse)
async def editar_page(coin_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.user_id == user.id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada")
    return templates.TemplateResponse(request, "coleccion/form.html",
        _form_ctx(db, {"user": user, "coin": coin,
                       "action": f"/coleccion/{coin_id}/editar",
                       "title": "Editar moneda"})
    )


@router.post("/{coin_id}/editar", response_class=HTMLResponse)
async def editar(
    coin_id: int,
    request: Request,
    tipo: str = Form("moneda"),
    name: str = Form(...),
    denomination: str = Form(""),
    currency_unit: str = Form(""),
    assayer: str = Form(""),
    year: str = Form(""),
    country: str = Form("Bolivia"),
    mint: str = Form(""),
    material: str = Form(""),
    condition: str = Form(""),
    category: str = Form(""),
    estimated_value: str = Form(""),
    purchase_price: str = Form(""),
    purchase_currency: str = Form("BOB"),
    purchase_usd_rate: str = Form(""),
    value_currency: str = Form("BOB"),
    quantity: str = Form("1"),
    description: str = Form(""),
    is_public: str = Form(""),
    image: UploadFile = File(None),
    image_back: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.user_id == user.id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada")

    def to_int(v): return int(v) if v.strip().isdigit() else None
    def to_decimal(v):
        try: return float(v.strip()) if v.strip() else None
        except: return None

    save_custom_option(db, "mint", mint.strip(), ALL_MINTS)
    save_custom_option(db, "currency_unit", currency_unit.strip(), ALL_CURRENCY_UNITS)

    es_billete = tipo == "billete"
    pc = purchase_currency if purchase_currency in ("BOB", "USD") else "BOB"
    coin.tipo            = "billete" if es_billete else "moneda"
    coin.name            = name.strip()
    coin.denomination    = denomination.strip() or None
    coin.currency_unit   = currency_unit.strip() or None
    coin.assayer         = None if es_billete else (assayer.strip() or None)
    coin.year            = to_int(year)
    coin.country         = country.strip() or "Bolivia"
    coin.mint            = None if es_billete else (mint.strip() or None)
    coin.material        = None if es_billete else (material.strip() or None)
    coin.condition       = condition or None
    coin.category        = category or None
    coin.estimated_value = to_decimal(estimated_value)
    coin.purchase_price  = to_decimal(purchase_price)
    coin.purchase_currency = pc
    coin.purchase_usd_rate = to_decimal(purchase_usd_rate) if pc == "USD" else None
    coin.value_currency  = value_currency if value_currency in ("BOB", "USD") else "BOB"
    coin.quantity       = max(1, to_int(quantity) or 1)
    coin.description    = description.strip() or None
    coin.is_public      = bool(is_public)

    new_img  = save_upload(image)
    new_back = save_upload(image_back)
    if new_img:  coin.image_url      = new_img
    if new_back: coin.image_back_url = new_back

    db.commit()
    return RedirectResponse(url=f"/coleccion/{coin_id}", status_code=302)


# ── Eliminar ──────────────────────────────────────────────────
@router.post("/{coin_id}/eliminar")
async def eliminar(coin_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.user_id == user.id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Moneda no encontrada")
    db.delete(coin)
    db.commit()
    return RedirectResponse(url="/coleccion", status_code=302)


# ── Toggle público ────────────────────────────────────────────
@router.post("/{coin_id}/toggle-publico")
async def toggle_publico(coin_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    coin = db.query(Coin).filter(Coin.id == coin_id, Coin.user_id == user.id).first()
    if not coin:
        raise HTTPException(status_code=404)
    coin.is_public = not coin.is_public
    db.commit()
    return RedirectResponse(url=f"/coleccion/{coin_id}", status_code=302)
