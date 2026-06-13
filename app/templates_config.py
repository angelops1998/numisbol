from fastapi.templating import Jinja2Templates
from markupsafe import Markup
import markdown as md
import json
import hmac
import hashlib

templates = Jinja2Templates(directory="app/templates")

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
