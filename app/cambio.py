"""Conversión Bs → US$ solo para cargar montos escritos en bolivianos.

Nada se guarda: la tasa se baja de una API pública, se cachea en memoria y, si
no hay red, se usa la última conocida o TASA_RESPALDO.
"""
import json
import threading
import time
import urllib.request

TASA_RESPALDO = 11.84
_TTL = 6 * 3600
_REINTENTO = 900

_lock = threading.Lock()
_rate = TASA_RESPALDO
_ok_at = 0.0
_try_at = 0.0


def _fetch() -> float | None:
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD",
                                     headers={"User-Agent": "NumisBol/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            rate = float(json.load(r)["rates"]["BOB"])
        return rate if 1 < rate < 100 else None
    except Exception:
        return None


def tasa() -> float:
    global _rate, _ok_at, _try_at
    now = time.time()
    if now - _ok_at > _TTL and now - _try_at > _REINTENTO and _lock.acquire(blocking=False):
        try:
            _try_at = now
            got = _fetch()
            if got:
                _rate, _ok_at = got, now
        finally:
            _lock.release()
    return _rate


def a_usd(monto: float | None, moneda: str) -> float | None:
    if monto is None or moneda != "BOB":
        return monto
    return round(monto / tasa(), 2)
