"""Artefacts JSONL exclusifs, manifestes et vérification hors ligne en flux."""

import hashlib
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.contracts import CONTRACT_VERSION, canonical_json
from cahier_rag.evaluation.files import load_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.representations.contracts import REPRESENTATION_VERSION
from cahier_rag.representations.repository import LIMITS


def select_targets(scope, *, limit, split="development", seed=20261021):
    if type(limit) is not int or not 1 <= limit <= 20000:
        raise ValueError("Limite explicite entre 1 et 20 000 requise.")
    if split not in {"development", "evaluation", "all"} or type(seed) is not int:
        raise ValueError("Partition ou graine invalide.")
    ids = sorted(
        (did for did, item in scope.documents.items() if split == "all" or item["split"] == split),
        key=lambda did: (digest([seed, did]), did),
    )
    if len(ids) < limit:
        raise ValueError("Limite supérieure au nombre d’unités de cette partition.")
    return ids[:limit]


def implementation_hashes():
    folder = Path(__file__).parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.py"))}


def generate(
    repository,
    config,
    target_ids,
    output,
    *,
    selection,
    batch_size=50,
    corpus_version=None,
    source_manifest=None,
):
    if not target_ids:
        raise ValueError("Au moins une unité cible requise.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    # Le manifeste de succès est créé en dernier ; un dossier incomplet est conservé.
    started = time.perf_counter()
    histogram, segments = Counter(), Counter()
    length_bounds = (60, 200, 500, 1000, 2000, 4000, 8000, 20000, 100000, 1000000, 100000000)
    length_sum, minimum_length, maximum_length, total = 0, None, 0, 0
    enriched = set()
    target_set, splits, forms, kinds = set(), Counter(), Counter(), Counter()
    source_keys = set()
    expected_targets = set(target_ids)
    file_hash = hashlib.sha256()
    logical_hash = hashlib.sha256()
    with (output / "representations.jsonl").open("x", encoding="utf-8") as stream:
        os.chmod(stream.name, 0o600)
        for representation in repository.iter_prepared(target_ids, config, batch_size=batch_size):
            row = representation.to_dict()
            did = row["primary"]["document_id"]
            if did not in expected_targets or row["segment"]["index"] != segments[did]:
                raise ValueError("Cible inconnue ou segment dupliqué / désordonné.")
            target_set.add(did)
            length = len(row["embedding_text"])
            histogram[next(bound for bound in length_bounds if length < bound)] += 1
            length_sum += length
            minimum_length = length if minimum_length is None else min(minimum_length, length)
            maximum_length = max(maximum_length, length)
            total += 1
            segments[did] += 1
            splits[row["split"]] += 1
            forms[row["primary"]["questionnaire_id"]] += 1
            kinds[repository.scope.documents[did]["unit_type"]] += 1
            if row["enriched"]:
                enriched.add(did)
            for source in row["sources"]:
                source_keys.add(source["document_id"])
            line = canonical_json(row) + "\n"
            if len(line.encode()) > 32 * 1024 * 1024:
                raise ValueError("Représentation supérieure au plafond de 32 Mio.")
            stream.write(line)
            file_hash.update(line.encode())
            logical_hash.update(
                (row["representation_id"] + ":" + row["content_hash"] + "\n").encode()
            )
        stream.flush()
        os.fsync(stream.fileno())
    if target_set != set(target_ids):
        raise ValueError("Cibles manquantes dans la préparation.")

    def percentile(fraction):
        count = 0
        threshold = max(1, math.ceil(total * fraction))
        for length, number in sorted(histogram.items()):
            count += number
            if count >= threshold:
                return length

    stats = {
        "target_units": len(target_set),
        "representations": total,
        "segmented_units": sum(n > 1 for n in segments.values()),
        "additional_segments": total - len(target_set),
        "enriched_units": len(enriched),
        "enriched_fraction": len(enriched) / len(target_set),
        "length_chars": {
            "min": minimum_length,
            "median_upper_bound_exclusive": percentile(0.5),
            "p95_upper_bound_exclusive": percentile(0.95),
            "max": maximum_length,
            "mean": length_sum / total,
            "histogram_upper_bound_exclusive": {str(b): histogram[b] for b in length_bounds},
        },
        "by_split": dict(splits),
        "by_questionnaire": dict(forms),
        "by_unit_type": dict(kinds),
        "source_units_referenced": len(source_keys),
        "artifact_bytes": (output / "representations.jsonl").stat().st_size,
        "preparation_seconds": time.perf_counter() - started,
    }
    manifest = {
        "manifest_version": 1,
        "representation_version": REPRESENTATION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "corpus_version": corpus_version,
        "source_manifest": source_manifest,
        "sample_hash": repository.scope.sample_hash,
        "configuration": config.to_dict(),
        "config_hash": config.config_hash,
        "selection": selection,
        "target_ids": target_ids,
        "target_ids_hash": digest(target_ids),
        "source_refs_hash": digest(
            sorted((did, repository.scope.documents[did]["content_hash"]) for did in source_keys)
        ),
        "context_policy": "rag007-selected-only",
        "external_context_units": 0,
        "limits": LIMITS,
        "batch_size": batch_size,
        "data_sha256": file_hash.hexdigest(),
        "representations_hash": logical_hash.hexdigest(),
        "implementation_hashes": implementation_hashes(),
        "statistics": stats,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["manifest_hash"] = digest(manifest)
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        os.chmod(stream.name, 0o600)
        stream.write(canonical_json(manifest) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return manifest


def inspect_artifact(output, *, scope=None):
    output = Path(output)
    manifest = load_json(output / "manifest.json")
    expected_manifest_hash = manifest.pop("manifest_hash")
    if digest(manifest) != expected_manifest_hash:
        raise ValueError("Manifeste modifié.")
    manifest["manifest_hash"] = expected_manifest_hash
    if (
        manifest["context_policy"] != "rag007-selected-only"
        or manifest["external_context_units"] != 0
    ):
        raise ValueError("Politique de contexte inconnue.")
    if (
        manifest["config_hash"] != digest(manifest["configuration"])
        or digest(manifest["target_ids"]) != manifest["target_ids_hash"]
    ):
        raise ValueError("Paramètres ou cibles modifiés.")
    if scope is not None and manifest["sample_hash"] != scope.sample_hash:
        raise ValueError("Corpus différent.")
    file_hash, logical = hashlib.sha256(), hashlib.sha256()
    targets, segment_counts = set(), Counter()
    count = 0
    with (output / "representations.jsonl").open("rb") as stream:
        while line := stream.readline(32 * 1024 * 1024 + 1):
            if len(line) > 32 * 1024 * 1024:
                raise ValueError("Représentation trop volumineuse.")
            row = json.loads(line)
            expected = row.pop("content_hash")
            did = row["primary"]["document_id"]
            identity = [
                REPRESENTATION_VERSION,
                row["config_hash"],
                row["sample_hash"],
                did,
                row["segment"]["start"],
                row["segment"]["end"],
            ]
            expected_id = f"prepared:v1:{row['strategy']}:{digest(identity)}"
            if (
                digest(row) != expected
                or row["representation_id"] != expected_id
                or row["segment"]["index"] != segment_counts[did]
            ):
                raise ValueError("Représentation modifiée ou dupliquée.")
            if (
                row["config_hash"] != manifest["config_hash"]
                or row["sample_hash"] != manifest["sample_hash"]
            ):
                raise ValueError("Configuration incohérente.")
            if row["strategy"] != manifest["configuration"]["strategy"] or row["split"] not in {
                "development",
                "evaluation",
            }:
                raise ValueError("Stratégie ou partition incohérente.")
            if scope is not None:
                primary = scope.documents.get(did)
                if primary is None or primary["split"] != row["split"]:
                    raise ValueError("Cible hors corpus ou partition.")
                for parent_id in row["parent"]["unit_ids"]:
                    item = scope.documents.get(parent_id)
                    if (
                        item is None
                        or item["split"] != row["split"]
                        or item["contribution_id"] != row["primary"]["contribution_id"]
                        or item["corpus_id"] != row["primary"]["corpus_id"]
                    ):
                        raise ValueError("Parent hors corpus, contribution ou partition.")
                for source in row["sources"]:
                    item = scope.documents.get(source["document_id"])
                    if (
                        item is None
                        or item["content_hash"] != source["content_hash"]
                        or item["split"] != row["split"]
                        or source["contribution_id"] != row["primary"]["contribution_id"]
                        or source["corpus_id"] != row["primary"]["corpus_id"]
                    ):
                        raise ValueError("Contexte hors corpus, contribution ou partition.")
            segment_counts[did] += 1
            targets.add(row["primary"]["document_id"])
            logical.update((row["representation_id"] + ":" + expected + "\n").encode())
            file_hash.update(line)
            count += 1
    if (
        file_hash.hexdigest() != manifest["data_sha256"]
        or logical.hexdigest() != manifest["representations_hash"]
        or targets != set(manifest["target_ids"])
        or count != manifest["statistics"]["representations"]
    ):
        raise ValueError("Artefact incomplet ou empreintes incompatibles.")
    return manifest
