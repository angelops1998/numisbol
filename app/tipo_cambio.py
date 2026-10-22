"""Tipo de cambio USD → BOB.

En modo automático (por defecto) la tasa se baja de APIs públicas y se guarda en
app_settings, así sobrevive reinicios y la comparten todos los workers. Si el valor
guardado está viejo se refresca en un hilo aparte, sin bloquear la petición.
En modo manual se usa la tasa que el admin escribió en Configuración.
"""
import json
import threading
import urllib.request
from datetime import datetime, timezone, timedelta

from .database import SessionLocal
from .models.setting import AppSetting

KEY_RATE    = "usd_bob_rate"
KEY_UPDATED = "usd_bob_rate_updated"   # ISO UTC de la última actualización automática
KEY_SOURCE  = "usd_bob_rate_source"
KEY_MODE    = "usd_bob_rate_mode"      # "auto" | "manual"

MAX_AGE = timedelta(hours=6)
RETRY_AFTER = timedelta(minutes=15)    # no reintentar en cada request si las APIs fallan

_SOURCES = [
    ("open.er-api.com", "https://open.er-api.com/v6/latest/USD",
     lambda d: d["rates"]["BOB"]),
    ("fawazahmed0/currency-api", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
     lambda d: d["usd"]["bob"]),
]

_lock = threading.Lock()
_last_attempt: datetime | None = None


def _fetch() -> tuple[float, str] | None:
    for name, url, extract in _SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NumisBol/1.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                rate = float(extract(json.load(r)))
            if 1 < rate < 100:   # descarta respuestas absurdas
                return round(rate, 4), name
        except Exception:
            continue
    return None


def _settings(db) -> dict:
    rows = db.query(AppSetting).filter(AppSetting.key.in_([KEY_RATE, KEY_UPDATED, KEY_SOURCE, KEY_MODE])).all()
    return {r.key: r.value for r in rows}


def _save(db, values: dict):
    for k, v in values.items():
        row = db.query(AppSetting).filter(AppSetting.key == k).first()
        if row:
            row.value = v
        else:
            db.add(AppSetting(key=k, value=v))
    db.commit()


def refresh(db=None) -> bool:
    """Baja la tasa y la guarda. Devuelve True si se actualizó."""
    global _last_attempt
    _last_attempt = datetime.now(timezone.utc)
    got = _fetch()
    if not got:
        return False
    rate, source = got
    own = db is None
    db = db or SessionLocal()
    try:
        _save(db, {KEY_RATE: str(rate), KEY_SOURCE: source,
                   KEY_UPDATED: datetime.now(timezone.utc).isoformat(timespec="seconds")})
    finally:
        if own:
            db.close()
    return True


def _refresh_bg():
    if not _lock.acquire(blocking=False):
        return
    def run():
        try:
            refresh()
        finally:
            _lock.release()
    threading.Thread(target=run, daemon=True).start()


def get_rate_info(db) -> dict | None:
    """{rate, mode, source, updated (datetime|None)} o None si no hay ninguna tasa."""
    s = _settings(db)
    mode = s.get(KEY_MODE) or "auto"
    updated = None
    if s.get(KEY_UPDATED):
        try:
            updated = datetime.fromisoformat(s[KEY_UPDATED])
        except ValueError:
            pass

    if mode == "auto":
        now = datetime.now(timezone.utc)
        stale = updated is None or now - updated > MAX_AGE
        recently_tried = _last_attempt and now - _last_attempt < RETRY_AFTER
        if stale and not recently_tried:
            if not s.get(KEY_RATE):
                # Primera vez sin ningún valor: vale la pena esperar
                with _lock:
                    refresh(db)
                s = _settings(db)
                updated = datetime.fromisoformat(s[KEY_UPDATED]) if s.get(KEY_UPDATED) else None
            else:
                _refresh_bg()

    try:
        rate = float(s.get(KEY_RATE) or 0)
    except ValueError:
        rate = 0
    if rate <= 0:
        return None
    if mode != "auto":
        updated = None
    return {"rate": rate, "mode": mode, "source": s.get(KEY_SOURCE) if mode == "auto" else "manual",
            "updated": updated,
            # Hora de Bolivia (UTC-4, sin horario de verano)
            "updated_local": (updated - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M") if updated else None}


def get_rate(db) -> float | None:
    info = get_rate_info(db)
    return info["rate"] if info else None


def set_manual(db, rate: float):
    _save(db, {KEY_RATE: str(rate), KEY_MODE: "manual"})


def set_auto(db):
    _save(db, {KEY_MODE: "auto"})
    refresh(db)
