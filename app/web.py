from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.templating import Jinja2Templates

# Central Jinja2Templates instance for the whole app
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.globals["now"] = lambda: datetime.now(ZoneInfo("Europe/Paris"))