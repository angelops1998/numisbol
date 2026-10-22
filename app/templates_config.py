from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pathlib import Path
import markdown as md
import json
import hmac
import hashlib

templates = Jinja2Templates(directory="app/templates")

_STATIC_DIR = Path("app/static")
_static_versions: dict[str, str] = {}

def static_v(path: str) -> str:
    """URL de un estático con ?v=<mtime> para que el navegador no sirva caché vieja."""
    if path not in _static_versions:
        try:
            _static_versions[path] = str(int((_STATIC_DIR / path).stat().st_mtime))
        except OSError:
            _static_versions[path] = "0"
    return f"/static/{path}?v={_static_versions[path]}"

templates.env.globals["static_v"] = static_v

def _csrf_input(request) -> Markup:
    from .config import get_settings
    cookie_token = request.cookies.get("csrf_token", "")
    signed = hmac.new(get_settings().secret_key.encode(), cookie_token.encode(), hashlib.sha256).hexdigest()
    return Markup(f'<input type="hidden" name="csrf_token" value="{signed}">')

templates.env.globals["csrf_input"] = _csrf_input

_md = md.Markdown(extensions=["extra", "nl2br"])

def render_md(text: str) -> Markup:
    _md.reset()
    return Markup(_md.convert(text or ""))

def tojson_filter(value, indent=None):
    return Markup(json.dumps(value, ensure_ascii=False, default=str))

templates.env.filters["markdown"] = render_md
templates.env.filters["tojson"]   = tojson_filter
