#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from pathlib import Path

# --- Réglages répertoires à ignorer ---
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    "venv", ".venv", "env", ".env", "node_modules", "dist", "build",
    ".idea", ".vscode", ".ruff_cache", ".tox", ".cache"
}

# --- Détection stdlib (3.10+) ---
try:
    STDLIB = set(sys.stdlib_module_names)  # type: ignore[attr-defined]
except Exception:
    # fallback minimaliste si indispo (old Python)
    STDLIB = {
        "abc","argparse","asyncio","base64","collections","concurrent","contextlib","copy",
        "csv","ctypes","dataclasses","datetime","decimal","enum","functools","fractions",
        "glob","gzip","hashlib","heapq","html","http","imaplib","inspect","io","ipaddress",
        "itertools","json","logging","math","multiprocessing","numbers","operator","os",
        "pathlib","pickle","platform","plistlib","queue","random","re","sched","secrets",
        "selectors","shlex","signal","socket","sqlite3","statistics","string","subprocess",
        "sys","tempfile","textwrap","threading","time","typing","unittest","urllib","uuid",
        "venv","warnings","weakref","xml","zipfile","zoneinfo"
    }

# --- Mapping import -> package PyPI ---
PKG_MAP = {
    # Web / API
    "fastapi": "fastapi",
    "starlette": "starlette",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "httpx": "httpx",
    "requests": "requests",
    "aiohttp": "aiohttp",

    # Data / SciPy
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "statsmodels": "statsmodels",

    # NLP / ML
    "spacy": "spacy",
    "nltk": "nltk",
    "transformers": "transformers",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",

    # Parsing / IO
    "yaml": "PyYAML",
    "toml": "toml",
    "ujson": "ujson",
    "orjson": "orjson",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "python_docx": "python-docx",
    "docx": "python-docx",
    "reportlab": "reportlab",
    "lxml": "lxml",
    "bs4": "beautifulsoup4",

    # Images / Vision
    "PIL": "Pillow",
    "cv2": "opencv-python",

    # Data viz
    "plotly": "plotly",
    "altair": "altair",

    # DB / ORM
    "sqlalchemy": "SQLAlchemy",
    "psycopg2": "psycopg2-binary",
    "psycopg": "psycopg[binary]",
    "pymongo": "pymongo",

    # Utils
    "tqdm": "tqdm",
    "python_dotenv": "python-dotenv",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "rich": "rich",
}

IMPORT_RE = re.compile(
    r'^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))',
    re.UNICODE
)

def top_level_module(name: str) -> str:
    return name.split(".")[0]

def is_ignored_dir(path: Path) -> bool:
    parts = set(p.name for p in path.parts)
    return bool(parts & IGNORE_DIRS)

def list_local_top_packages(project_root: Path) -> set:
    """Paquets/modules locaux (dossiers avec __init__.py ou .py top-level) à exclure."""
    locals_ = set()
    for p in project_root.iterdir():
        if p.name in IGNORE_DIRS:
            continue
        if p.is_dir() and (p / "__init__.py").exists():
            locals_.add(p.name)
        if p.is_file() and p.suffix == ".py":
            locals_.add(p.stem)
    return locals_

def scan_imports(project_root: Path) -> set:
    found = set()
    for root, dirs, files in os.walk(project_root):
        # Nettoyer dirs in-place pour ne pas descendre dedans
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        # Ignore chemins cachés
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for f in files:
            if not f.endswith(".py"):
                continue
            fp = Path(root) / f
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        m = IMPORT_RE.match(line)
                        if not m:
                            continue
                        mod = m.group(1) or m.group(2)
                        if not mod:
                            continue
                        found.add(top_level_module(mod))
            except Exception:
                # On saute les fichiers illisibles
                continue
    return found

def map_to_pypi(modules: set, locals_: set) -> list:
    reqs = set()
    for m in modules:
        if m in STDLIB:
            continue
        if m in locals_:
            continue
        pkg = PKG_MAP.get(m, m)  # par défaut, on suppose même nom
        reqs.add(pkg)
    return sorted(reqs, key=str.lower)

def main():
    root = Path(".").resolve()
    locals_ = list_local_top_packages(root)
    modules = scan_imports(root)
    requirements = map_to_pypi(modules, locals_)

    out = root / "requirements.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(requirements) + ("\n" if requirements else ""))
    print(f"✅ requirements.txt généré ({len(requirements)} paquets).")

if __name__ == "__main__":
    main()
