"""Plans aveugles immuables, référence humaine séparée du texte envoyé aux juges."""

import json
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.contracts import PROMPT_VERSION, JudgeInput
from cahier_rag.judges.protocols import plan_limit, resolve


def grouped_split(pairs, scope, *, seed=20261023):
    # Les mêmes contributions et textes exacts restent dans une seule sous-partition.
    groups = {pair: pair for pair in pairs}

    def find(key):
        while groups[key] != key:
            groups[key] = groups[groups[key]]
            key = groups[key]
        return key

    links = {}
    for pair in sorted(pairs):
        doc = scope.documents[pair[1]]
        for key in (
            ("parent", doc["corpus_id"], doc["contribution_id"]),
            ("text", doc["text_hash"]),
        ):
            other = links.setdefault(key, pair)
            a, b = find(pair), find(other)
            groups[max(a, b)] = min(a, b)
    components = {}
    for pair in sorted(pairs):
        components.setdefault(find(pair), []).append(pair)
    ordered = sorted(components.values(), key=lambda g: digest([seed, g]))
    target = max(1, len(pairs) // 4)
    chosen = []
    for component in ordered:
        if (
            len(chosen) + len(component) <= target
            and len(pairs) - len(chosen) - len(component) >= 20
        ):
            chosen.extend(component)
    holdout = set(chosen) if len(chosen) >= 10 else set()
    return {pair: ("validation" if pair in holdout else "calibration") for pair in pairs}


def prepare(
    directory,
    pairs,
    repository,
    queries,
    *,
    kind,
    source_hashes,
    seed=20261023,
    prompt_version=PROMPT_VERSION,
):
    pairs = sorted(set(pairs))
    if not pairs or len(pairs) > plan_limit(prompt_version):
        raise ValueError("Plan dépassant la limite de son protocole.")
    query_index = {q["query_id"]: q for q in queries}
    for qid, did in pairs:
        if (
            qid not in query_index
            or query_index[qid]["split"] != "development"
            or did not in repository.scope.documents
            or repository.scope.documents[did]["split"] != "development"
        ):
            raise ValueError("Couple inconnu ou hors développement.")
    splits = (
        grouped_split(pairs, repository.scope, seed=seed)
        if kind == "human60"
        else {p: "automatic" for p in pairs}
    )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    entries = []
    with (directory / "inputs.jsonl").open("x", encoding="utf-8") as output:
        for start in range(0, len(pairs), 25):
            batch = pairs[start : start + 25]
            docs = repository.fetch([did for _, did in batch])
            for qid, did in batch:
                doc = docs[did]
                item = JudgeInput(
                    qid,
                    did,
                    doc.content_hash,
                    query_index[qid]["text"],
                    doc.text,
                    doc.question_text,
                    doc.contribution_title,
                )
                output.write(canonical_json(item.to_dict()) + "\n")
                entries.append(
                    {
                        "query_id": qid,
                        "document_id": did,
                        "input_hash": item.input_hash,
                        "subset": splits[qid, did],
                        "source_hash": doc.content_hash,
                        "contribution_id": str(doc.contribution_id),
                    }
                )
    manifest = {
        "version": 1,
        "kind": kind,
        "sample_hash": repository.scope.sample_hash,
        "query_hash": digest(queries),
        "prompt_version": prompt_version,
        "prompt_hash": digest(resolve(prompt_version)),
        "source_hashes": source_hashes,
        "seed": seed,
        "split_policy": "by contribution and identical text; validation is not held-out queries",
        "entries": entries,
        "inputs_hash": sha256_file(directory / "inputs.jsonl"),
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_plan(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    body = dict(manifest)
    claimed = body.pop("manifest_hash")
    if (
        digest(body) != claimed
        or manifest["prompt_hash"] != digest(resolve(manifest["prompt_version"]))
        or sha256_file(directory / "inputs.jsonl") != manifest["inputs_hash"]
        or not 1 <= len(manifest["entries"]) <= plan_limit(manifest["prompt_version"])
    ):
        raise ValueError("Plan de jugement modifié ou incompatible.")
    return manifest


def iter_inputs(directory, manifest):
    expected = iter(manifest["entries"])
    with (Path(directory) / "inputs.jsonl").open(encoding="utf-8") as stream:
        while line := stream.readline(4000001):
            entry = next(expected, None)
            if entry is None or len(line) > 4000000:
                raise ValueError("Fichier de couples invalide ou trop volumineux.")
            item = JudgeInput(**json.loads(line))
            if (
                item.input_hash != entry["input_hash"]
                or item.query_id != entry["query_id"]
                or item.document_id != entry["document_id"]
            ):
                raise ValueError("Texte ou identité de couple modifié.")
            yield item
    if next(expected, None) is not None:
        raise ValueError("Plan incomplet.")
