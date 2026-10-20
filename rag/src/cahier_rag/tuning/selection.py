"""Sélection explicite, vérifiable et réversible du profil local RAG-027."""

import json
from dataclasses import asdict

from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.tuning.vector import PROFILES, AnnConfig
from cahier_rag.vector.preparation import atomic_json


def save_selection(directory, corpus_hash):
    data = {
        "version": 1,
        "corpus_hash": corpus_hash,
        "lexical": "equivalent-statistics",
        "ann": asdict(PROFILES["ef1000"]),
        "rrf_k": 60,
        "depth": 50,
        "qualified": False,
        "decision": "Measured compromise, not equivalent to exact; no tested ANN profile meets frozen thresholds.",
        "exact_available": True,
        "evidence": {
            name: fingerprint(json.loads((directory / name).read_text()))
            for name in ("lexical.json", "vector.json", "selection-policy.json")
        },
    }
    data["selection_hash"] = fingerprint(data)
    path = directory / "selection.json"
    if path.exists() and json.loads(path.read_text()) != data:
        raise ValueError("Sélection existante différente : nouvelle version requise.")
    atomic_json(path, data)
    return data


def load_selection(path, corpus_hash):
    data = json.loads(path.read_text())
    claimed = data.pop("selection_hash")
    if (
        fingerprint(data) != claimed
        or data["version"] != 1
        or data["corpus_hash"] != corpus_hash
        or data["lexical"] != "equivalent-statistics"
        or data["rrf_k"] != 60
        or data["depth"] != 50
    ):
        raise ValueError("Sélection RAG-027 incompatible ou modifiée.")
    AnnConfig(**data["ann"])
    return data | {"selection_hash": claimed}
