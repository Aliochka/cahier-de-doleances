"""Entrées v2 copiées byte pour byte, schémas par requête et recette v3 distincte."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.constrained.schema import response_schema
from cahier_rag.generation.planning import iter_inputs
from cahier_rag.generation.planning import load_plan as load_baseline

PILOT = ("democratie-05", "fiscalite-04", "services_publics-03")


def prepare(root, directory, backend):
    old_directory = root / "evaluation/local/rag022/v2/plan"
    old = load_baseline(old_directory, root)
    recipe = backend.recipe()
    baseline_version = recipe["prompt_version"]
    if (
        baseline_version != old["backend"]["version"]
        or recipe["prompt_hash"] != old["backend"]["prompt_hash"]
    ):
        raise ValueError("Prompt différent de RAG-022 v2.")
    if (
        recipe["model"] != old["backend"]["model"]
        or recipe["inference"] != old["backend"]["inference"]
    ):
        raise ValueError("Modèle ou paramètres différents de la référence.")
    schemas = {}
    for item, row in iter_inputs(old_directory, old):
        if (
            backend.prompt(item) != row["prompt"]
            or backend.token_counts([item])[0] != row["prompt_tokens"]
        ):
            raise ValueError("Prompt/tokenization différents de v2.")
        schemas[item.query_id] = response_schema(item)
    if len(schemas) != 20 or not set(PILOT) <= set(schemas):
        raise ValueError("Périmètre de développement incomplet.")
    directory.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(old_directory / "inputs.jsonl", directory / "inputs.jsonl")
    atomic_json(directory / "schemas.json", schemas)
    files = [
        old_directory / "manifest.json",
        old_directory / "inputs.jsonl",
        old_directory.parent / "generation.sqlite3",
        root / "pyproject.toml",
        root / "uv.lock",
        root / "evaluation/queries.json",
        root / "evaluation/local/rag021/development/contexts.jsonl",
    ]
    (directory / "code").mkdir()
    for file in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(file, directory / "code" / file.name)
    manifest = {
        "version": 1,
        "backend": recipe,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_plan": old["plan_hash"],
        "entries": old["entries"],
        "pilot_queries": list(PILOT),
        "inputs_sha256": sha256_file(directory / "inputs.jsonl"),
        "schema_hashes": {q: digest(s) for q, s in schemas.items()},
        "schemas_sha256": sha256_file(directory / "schemas.json"),
        "historical_files": {
            str(p.resolve().relative_to(root.resolve())): sha256_file(p) for p in files
        },
        "code": {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "prompt_changed": False,
        "judgments_used": False,
        "context_recipe": old["context_recipe"],
    }
    manifest["plan_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_plan(directory, root=None):
    value = json.loads((directory / "manifest.json").read_text())
    if digest({k: v for k, v in value.items() if k != "plan_hash"}) != value["plan_hash"]:
        raise ValueError("Manifeste contraint modifié.")
    if (
        sha256_file(directory / "inputs.jsonl") != value["inputs_sha256"]
        or sha256_file(directory / "schemas.json") != value["schemas_sha256"]
    ):
        raise ValueError("Entrées ou schémas modifiés.")
    schemas = json.loads((directory / "schemas.json").read_text())
    if {q: digest(s) for q, s in schemas.items()} != value["schema_hashes"]:
        raise ValueError("Empreintes des schémas incompatibles.")
    if any(
        sha256_file(Path(__file__).parent / p) != h
        and (not (directory / "code" / p).exists() or sha256_file(directory / "code" / p) != h)
        for p, h in value["code"].items()
    ):
        raise ValueError("Code différent de la recette figée.")
    if root is not None and any(
        sha256_file(root / p) != h for p, h in value["historical_files"].items()
    ):
        raise ValueError("Références historiques modifiées.")
    for item, row in iter_inputs(directory, value):
        if digest(response_schema(item)) != value["schema_hashes"][item.query_id]:
            raise ValueError("Schéma documentaire incompatible.")
    return value
