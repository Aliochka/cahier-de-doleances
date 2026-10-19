"""Vérification indépendante des sources, budgets, références, relations et artefacts."""

import json

from cahier_rag.context.assembly import model_block
from cahier_rag.context.contracts import ContextConfig, ContextSource
from cahier_rag.context.experiments import load_protocol
from cahier_rag.context.repository import ContextRepository
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest


def verify_context(context, query, ranks, repository, counter):
    if (
        context["query_id"] != query["query_id"]
        or query["split"] != "development"
        or context["query_hash"] != digest(query["text"])
        or context["sample_hash"] != repository.scope.sample_hash
        or context["tokenizer"] != counter.description
        or context["context_hash"]
        != digest({k: v for k, v in context.items() if k != "context_hash"})
    ):
        raise ValueError("Identité, partition ou empreinte du contexte invalide.")
    config = ContextConfig(**context["configuration"])
    rendered = json.loads(context["model_document_payload"])
    citations = context["citation_map"]
    refs = [s["reference"] for s in rendered["sources"]]
    if len(set(refs)) != len(refs) or set(refs) != set(citations):
        raise ValueError("Table de citations incohérente.")
    docs = (
        repository.fetch([s["metadata"]["document_id"] for s in citations.values()])
        if citations
        else {}
    )
    primaries = set()
    for block in rendered["sources"]:
        row = citations[block["reference"]]
        meta, tech = row["metadata"], row["technical"]
        u = docs[meta["document_id"]]
        source = ContextSource(
            u,
            context["sample_hash"],
            tech["excerpt"]["start"],
            tech["excerpt"]["end"],
            tech["retrieval"]["method"],
            tech["retrieval"]["rank"],
            tech["role"],
            tech["parent_document_id"],
        )
        expected = source.to_dict()
        plain = {k: v for k, v in row.items() if k != "technical"}
        base = {k: v for k, v in expected.items() if k != "technical"}
        actual_tech = {k: v for k, v in tech.items() if k != "observed_repetitions"}
        if (
            plain != base
            or actual_tech != expected["technical"]
            or block != model_block(source, config.parent_mode)
        ):
            raise ValueError("Texte, provenance ou référence modifié.")
        if tech["role"] == "primary":
            if (
                source.method != context["method"]
                or source.rank > len(ranks)
                or ranks[source.rank - 1] != u.document_id
            ):
                raise ValueError("Source principale absente du classement gelé.")
            primaries.add(u.document_id)
    for row in citations.values():
        if row["technical"]["role"] == "complementary":
            if config.parent_mode != "P2":
                raise ValueError("Expansion non autorisée.")
            parent = row["technical"]["parent_document_id"]
            if parent not in primaries:
                raise ValueError("Contexte complémentaire sans parent sélectionné.")
            a = docs[row["metadata"]["document_id"]]
            b = docs[parent]
            if (a.corpus_id, a.contribution_id, a.questionnaire_id) != (
                b.corpus_id,
                b.contribution_id,
                b.questionnaire_id,
            ):
                raise ValueError("Contributions mélangées.")
    used = counter.count(context["model_document_payload"])
    if used > config.document_budget or used != context["budget"]["document_used"]:
        raise ValueError("Budget de tokens invalide.")
    return len(citations)


def verify(root, protocol_directory, directory):
    protocol, ranks, scope, queries, counter = load_protocol(root, protocol_directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    stats = json.loads((directory / "statistics.json").read_text())
    if (
        manifest["protocol_hash"] != protocol["protocol_hash"]
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["manifest_hash"]
        != digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
        or sha256_file(directory / "contexts.jsonl") != manifest["contexts_sha256"]
        or digest(stats) != manifest["statistics_hash"]
    ):
        raise ValueError("Manifeste ou artefacts modifiés.")
    index = {q["query_id"]: q for q in queries}
    repository = ContextRepository(root / "evaluation/local/rag018/bm25-A.sqlite3", scope)
    count, source_count = 0, 0
    seen = set()
    with (directory / "contexts.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            q = record["query_id"]
            method = record["method"]
            name = record["configuration_id"]
            key = q, method, name
            if (
                key in seen
                or q not in manifest["queries"]
                or q not in index
                or method not in ranks
                or name not in protocol["configurations"]
                or record["context"]["configuration"] != protocol["configurations"][name]
            ):
                raise ValueError("Contexte dupliqué ou hors protocole.")
            seen.add(key)
            source_count += verify_context(
                record["context"], index[q], ranks[method][q], repository, counter
            )
            count += 1
    if count != manifest["contexts"] or count != len(manifest["queries"]) * len(ranks) * len(
        protocol["configurations"]
    ):
        raise ValueError("Expérience incomplète.")
    return {
        "contexts_verified": count,
        "sources_verified": source_count,
        "contexts_sha256": manifest["contexts_sha256"],
    }
