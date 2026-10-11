from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from starlette.datastructures import URL

from app.config import settings
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


templates.env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "default": _json_default}
templates.env.globals["BASE_URL"] = settings.BASE_URL
templates.env.globals["LOGIN_EMAIL_ENABLED"] = settings.LOGIN_EMAIL_ENABLED
templates.env.filters["clean_text_excerpt"] = clean_text_excerpt
templates.env.globals["now"] = lambda: datetime.now(ZoneInfo("Europe/Paris"))
