"""Réutilisation des seuls contextes RAG-021 gelés ; aucune recherche ni réassemblage."""

import json
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.context.validation import verify
from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.files import load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.contracts import GenerationInput, compact

PILOT = ("democratie-01", "fiscalite-02", "services_publics-06")


def prepare(root, directory, backend):
    contexts = root / "evaluation/local/rag021/development"
    verify(root, root / "evaluation/local/rag021/protocol", contexts)
    queries = {
        q["query_id"]: q
        for q in load_queries(root / "evaluation/queries.json")
        if q["split"] == "development"
    }
    selected = {}
    with (contexts / "contexts.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["method"] == "H1+R2" and row["configuration_id"] == "S2-P1-8192":
                if row["query_id"] not in queries or row["query_id"] in selected:
                    raise ValueError("Contexte réservé ou dupliqué.")
                selected[row["query_id"]] = row["context"]
    if set(selected) != set(queries) or len(selected) != 20:
        raise ValueError("Vingt contextes de développement requis.")
    configuration = backend.recipe()
    directory.mkdir(parents=True, exist_ok=False)
    entries = []
    with (directory / "inputs.jsonl").open("x", encoding="utf-8") as stream:
        for qid, context in sorted(selected.items()):
            item = GenerationInput(qid, queries[qid]["text"], compact(context))
            prompt = backend.prompt(item)
            tokens = backend.token_counts([item])[0]
            compact_tokens = len(
                backend.tokenizer(
                    canonical_json(item.document["sources"]),
                    add_special_tokens=False,
                    truncation=False,
                )["input_ids"]
            )
            if (
                compact_tokens > 8192
                or tokens > backend.config.max_input_tokens
                or tokens + backend.config.max_new_tokens > backend.spec.context_tokens
            ):
                raise ValueError("Prompt ou contexte compact hors fenêtre ; aucune troncature.")
            value = {
                "query_id": qid,
                "query": item.query,
                "document": item.document,
                "input_hash": item.input_hash,
                "prompt": prompt,
                "prompt_hash": digest(prompt),
                "prompt_tokens": tokens,
                "compact_tokens": compact_tokens,
            }
            stream.write(canonical_json(value) + "\n")
            entries.append(
                {
                    k: value[k]
                    for k in (
                        "query_id",
                        "input_hash",
                        "prompt_hash",
                        "prompt_tokens",
                        "compact_tokens",
                    )
                }
            )
    import shutil

    (directory / "code").mkdir()
    for source in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(source, directory / "code" / source.name)
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": configuration,
        "pilot_queries": list(PILOT),
        "entries": entries,
        "inputs_sha256": sha256_file(directory / "inputs.jsonl"),
        "historical_files": {
            str(p.resolve().relative_to(root.resolve())): sha256_file(p)
            for p in (
                contexts / "contexts.jsonl",
                contexts / "manifest.json",
                root / "evaluation/queries.json",
            )
        },
        "code": {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "judgments_used": False,
        "context_recipe": "H1+R2/S2-P1-8192/compact-fr-v1",
    }
    manifest["plan_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_plan(directory, root=None):
    value = json.loads((directory / "manifest.json").read_text())
    if (
        digest({k: v for k, v in value.items() if k != "plan_hash"}) != value["plan_hash"]
        or sha256_file(directory / "inputs.jsonl") != value["inputs_sha256"]
    ):
        raise ValueError("Plan de génération modifié.")
    if any(
        sha256_file(Path(__file__).parent / p) != h
        and (not (directory / "code" / p).exists() or sha256_file(directory / "code" / p) != h)
        for p, h in value["code"].items()
    ):
        raise ValueError("Code différent du plan figé.")
    if root is not None and any(
        sha256_file(root / p) != h for p, h in value["historical_files"].items()
    ):
        raise ValueError("Artefact historique modifié.")
    return value


def iter_inputs(directory, plan):
    with (directory / "inputs.jsonl").open(encoding="utf-8") as stream:
        for expected, line in zip(plan["entries"], stream, strict=True):
            row = json.loads(line)
            item = GenerationInput(row["query_id"], row["query"], row["document"])
            if (
                item.input_hash != row["input_hash"]
                or any(row[k] != v for k, v in expected.items())
                or digest(row["prompt"]) != row["prompt_hash"]
            ):
                raise ValueError("Entrée de génération incompatible.")
            yield item, row
