"""Comptage réel et intersection commune, sans troncature ni sélection de pertinence."""

from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingError
from cahier_rag.embeddings.data import read_representations
from cahier_rag.evaluation.sampling import digest


def token_statistics(counts, limit):
    values = sorted(counts)
    return {
        "count": len(counts),
        "min": min(counts),
        "max": max(counts),
        "mean": sum(counts) / len(counts),
        "median": values[(len(values) - 1) // 2],
        "p95": values[min(len(values) - 1, (95 * len(values) + 99) // 100 - 1)],
        "overflow_count": sum(n > limit for n in counts),
        "effective_limit": limit,
    }


def create_plan(scope, directories, backends, output, *, c_directory=None):
    if set(directories) != {"A", "B", "D"} or not 2 <= len(backends) <= 3:
        raise EmbeddingError("Trois stratégies A/B/D et deux à trois modèles requis.")
    data = {key: read_representations(path, scope) for key, path in directories.items()}
    if any(m["configuration"]["strategy"] != key for key, (m, _) in data.items()):
        raise EmbeddingError("Stratégie différente du répertoire annoncé.")
    targets = [m["target_ids_hash"] for m, _ in data.values()]
    if len(set(targets)) != 1:
        raise EmbeddingError("Les modèles doivent utiliser les mêmes cibles primaires.")
    plan = {
        "version": 1,
        "sample_hash": scope.sample_hash,
        "models": {},
        "strategies": {},
        "comparison_policy": "common-valid-intersection-without-truncation",
        "C_reuse": "B embedding_text; preserve C representation IDs via primary+segment mapping",
    }
    for key, backend in backends.items():
        backend.load_tokenizer()
        plan["models"][key] = {
            "spec": backend.spec.to_dict(),
            "snapshot_hash": backend.snapshot_hash,
            "tokenizer_class": type(backend.tokenizer).__name__,
            "effective_limit": backend.max_tokens,
        }
    for strategy, (manifest, inputs) in data.items():
        common = {item.input_id for item in inputs}
        stats = {}
        for key, backend in backends.items():
            counts = EmbeddingEngine(backend).counts(inputs, role="document")
            rejected = [
                {"input_id": item.input_id, "tokens": n, "source_hash": item.source_hash}
                for item, n in zip(inputs, counts)
                if n > backend.max_tokens
            ]
            common -= {item["input_id"] for item in rejected}
            stats[key] = {
                "statistics": token_statistics(counts, backend.max_tokens),
                "rejected": rejected,
                "counts_hash": digest(list(zip((item.input_id for item in inputs), counts))),
            }
        accepted = [item.input_id for item in inputs if item.input_id in common]
        if not accepted:
            raise EmbeddingError("Aucune entrée commune ne respecte les trois fenêtres.")
        plan["strategies"][strategy] = {
            "directory": str(Path(directories[strategy]).resolve()),
            "source_manifest_hash": manifest["manifest_hash"],
            "preparation": manifest["configuration"],
            "original_representations": len(inputs),
            "original_primary_units": len(manifest["target_ids"]),
            "target_ids_hash": manifest["target_ids_hash"],
            "common_input_ids": accepted,
            "common_inputs_hash": digest(
                [item.fingerprint() for item in inputs if item.input_id in common]
            ),
            "common_representations": len(accepted),
            "common_primary_units": len(
                {item.primary_id for item in inputs if item.input_id in common}
            ),
            "tokenization": stats,
        }
    if c_directory is not None:
        c_manifest, c_inputs = read_representations(c_directory, scope)
        b_manifest, b_inputs = data["B"]
        b_config = dict(b_manifest["configuration"])
        c_config = dict(c_manifest["configuration"])
        b_config.pop("strategy")
        c_config.pop("strategy")
        if (
            c_manifest["configuration"]["strategy"] != "C"
            or b_config != c_config
            or len(b_inputs) != len(c_inputs)
        ):
            raise EmbeddingError("Représentation C différente de B.")
        aliases = []
        valid = set(plan["strategies"]["B"]["common_input_ids"])
        for b, c in zip(b_inputs, c_inputs):
            if b.primary_id != c.primary_id or b.text != c.text:
                raise EmbeddingError("Les textes de C et B diffèrent.")
            if b.input_id in valid:
                aliases.append({"C_id": c.input_id, "B_id": b.input_id, "primary_id": b.primary_id})
        plan["C_reuse"] = {
            "source_manifest_hash": c_manifest["manifest_hash"],
            "B_source_manifest_hash": b_manifest["manifest_hash"],
            "aliases": aliases,
            "excluded_with_B": len(b_inputs) - len(aliases),
            "recomputed_vectors": 0,
        }
    plan["plan_hash"] = digest(plan)
    with Path(output).open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(plan) + "\n")
    return plan


def validate_plan(plan):
    payload = dict(plan)
    expected = payload.pop("plan_hash")
    if digest(payload) != expected or plan["version"] != 1:
        raise EmbeddingError("Plan modifié ou incompatible.")


def inputs_for_plan(plan, strategy, scope):
    validate_plan(plan)
    record = plan["strategies"][strategy]
    manifest, inputs = read_representations(record["directory"], scope)
    if manifest["manifest_hash"] != record["source_manifest_hash"]:
        raise EmbeddingError("Artefact RAG-011 différent de celui du plan.")
    accepted = set(record["common_input_ids"])
    selected = [i for i in inputs if i.input_id in accepted]
    if [i.input_id for i in selected] != record["common_input_ids"] or digest(
        [i.fingerprint() for i in selected]
    ) != record["common_inputs_hash"]:
        raise EmbeddingError("Identifiants ou ordre d’entrée incompatibles.")
    return selected
