"""Réutilise les packages judges existants malgré leur lien Python /tmp expiré."""

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
# The working durable CPython 3.11 is invoked explicitly; no environment is edited.
sys.path[:0] = [
    str(ROOT / "rag/.cache/judges-venv/lib/python3.11/site-packages"),
    str(ROOT / "rag/src"),
]
for key, value in {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "4",
}.items():
    os.environ[key] = value
