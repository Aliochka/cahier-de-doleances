"""Contrôles des recettes gelées, aucun accès aux fichiers de jugements."""

import hashlib
import json
from pathlib import Path

from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.flexible import Method, configuration
from cahier_rag.search.lexical import Strategy
from cahier_rag.search.preparation import Preparation


def verify_frozen(path, scope, queries):
    frozen = json.loads(Path(path).read_text())
    payload = dict(frozen)
    checksum = payload.pop("frozen_hash")
    if (
        digest(payload) != checksum
        or frozen["sample_hash"] != scope.sample_hash
        or frozen["queries_hash"] != digest(queries)
        or frozen["configuration"] != configuration(Method.WEIGHTED, Strategy.ANSWER, Preparation())
    ):
        raise ValueError("Recette RAG-009 gelée incompatible.")
    root = Path(__file__).resolve().parent.parent
    expected_files = {
        "lexical.py",
        "preparation.py",
        "flexible.py",
        "experiments.py",
        "flexible_cli.py",
    }
    if set(frozen["implementation_hashes"]) != expected_files:
        raise ValueError("Empreintes d'implémentation gelée incomplètes.")
    for name, expected in frozen["implementation_hashes"].items():
        if name not in {
            "lexical.py",
            "preparation.py",
            "flexible.py",
            "experiments.py",
            "flexible_cli.py",
        }:
            raise ValueError("Fichier d'implémentation gelé inconnu.")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Implémentation RAG-009 différente de son gel.")
    return frozen
