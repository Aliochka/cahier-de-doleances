from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.templating import Jinja2Templates
import json
from datetime import date
from decimal import Decimal
from starlette.datastructures import URL
from app.i18n import _, ngettext_template, get_current_language, LANGUAGES
from app.helpers import clean_text_excerpt

# Central Jinja2Templates instance for the whole app
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _json_default(o):
    if isinstance(o, URL):
        return str(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Decimal):
        return float(o)
    # dernier recours : string
    return str(o)


templates.env.filters["tojson"] = lambda v: json.dumps(
    v, ensure_ascii=False, separators=(",", ":"), default=_json_default
)
templates.env.filters["clean_text_excerpt"] = clean_text_excerpt
templates.env.globals["now"] = lambda: datetime.now(ZoneInfo("Europe/Paris"))

# Add i18n functions to templates
templates.env.globals["_"] = _
templates.env.globals["ngettext"] = ngettext_template
templates.env.globals["get_current_language"] = get_current_language
templates.env.globals["LANGUAGES"] = LANGUAGES