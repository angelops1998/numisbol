from fastapi.templating import Jinja2Templates
from markupsafe import Markup
import markdown as md
import json

templates = Jinja2Templates(directory="app/templates")

_md = md.Markdown(extensions=["extra", "nl2br"])

def render_md(text: str) -> Markup:
    _md.reset()
    return Markup(_md.convert(text or ""))

def tojson_filter(value, indent=None):
    return Markup(json.dumps(value, ensure_ascii=False, default=str))

templates.env.filters["markdown"] = render_md
templates.env.filters["tojson"]   = tojson_filter
