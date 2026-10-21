"""Explicit read-only search inspection/publication. Never migrate or write SQL.

Publication writes one exclusive 0600 signed file after checking sampled contents.
URLs and raw database exceptions are never printed.
"""

import argparse
import json
import os
from contextlib import ExitStack
from pathlib import Path

from cahier_rag.config import load_settings
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.store import FullStore, decode_vector_binary, vector_hash
from cahier_rag.safety import assert_distinct, inspect_database
from cahier_rag.search.publication import (
    logical_corpus,
    require_key,
    sample_ordinals,
    sign_publication,
)
from cahier_rag.search.service.reader import check_reader_role, create_search_engine
from cahier_rag.sources.gdn import ANSWER_SELECT, row_to_documents
from cahier_rag.storage import restore_document
from sqlalchemy import text


def check_versions(server_version, vector_version, revision):
    if not 170011 <= int(server_version) < 180000:
        raise ValueError("PostgreSQL 17.11 ou une révision corrective 17 ultérieure requise.")
    if vector_version != "0.8.7" or revision != "rag_0007":
        raise ValueError("pgvector 0.8.7 et rag_0007 requis.")


def checked_state(connection):
    if connection.execute(
        text("""SELECT to_regclass('public.answers') IS NOT NULL
        OR to_regclass('public.forms') IS NOT NULL
        OR to_regclass('public.alembic_version') IS NOT NULL""")
    ).scalar_one():
        raise ValueError("La destination ne doit pas contenir les tables applicatives.")
    state = FullStore(None, "full").state(connection)
    locale = connection.execute(
        text("""SELECT pg_encoding_to_char(encoding),datcollate,datctype
        FROM pg_database WHERE datname=current_database()""")
    ).one()
    if locale[0] != "UTF8" or any(
        value.lower().replace("-", "") != "fr_fr.utf8" for value in locale[1:]
    ):
        raise ValueError("Encodage/collation de la base spécialisée incompatible.")
    check_versions(
        connection.execute(text("SHOW server_version_num")).scalar_one(),
        connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar_one(),
        connection.execute(text("SELECT version_num FROM public.rag_alembic_version")).scalar_one(),
    )
    if (
        not all(state[k] for k in ("verified", "vectors_complete", "extraction_complete"))
        or state["documents"] != state["expected_units"]
        or state["documents"] != state["vector_cursor"]
        or state["segments"] < state["documents"]
    ):
        raise ValueError("Corpus incomplet.")
    stats = (
        connection.execute(
            text("""SELECT documents,corpus_hash,version
        FROM rag_tuning.statistics WHERE space_id='full'""")
        )
        .mappings()
        .one()
    )
    if (stats["documents"], stats["corpus_hash"], stats["version"]) != (
        state["documents"],
        state["chain_hash"],
        1,
    ):
        raise ValueError("Statistiques lexicales incompatibles.")
    indexes = (
        connection.execute(
            text("""SELECT i.indisvalid,i.indisready,
        pg_get_indexdef(c.oid) AS definition,c.relname
        FROM pg_class c JOIN pg_index i ON i.indexrelid=c.oid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='rag_full' AND c.relname IN
        ('segments_full_hnsw','documents_full_search_vector_idx')""")
        )
        .mappings()
        .all()
    )
    if len(indexes) != 2 or not all(i["indisvalid"] and i["indisready"] for i in indexes):
        raise ValueError("Index HNSW/GIN absents ou invalides.")
    for index in indexes:
        definition = index["definition"]
        if index["relname"] == "segments_full_hnsw" and not all(
            item in definition
            for item in ("USING hnsw", "vector_cosine_ops", "m='16'", "ef_construction='64'")
        ):
            raise ValueError("Paramètres HNSW incompatibles.")
        if index["relname"] == "documents_full_search_vector_idx" and "USING gin" not in definition:
            raise ValueError("Index lexical incompatible.")
    vector_type = connection.execute(
        text("""SELECT format_type(atttypid,atttypmod)
        FROM pg_attribute WHERE attrelid='rag_full.segments_full'::regclass
        AND attname='embedding' AND NOT attisdropped""")
    ).scalar_one()
    if vector_type not in {"vector(1024)", "public.vector(1024)"}:
        raise ValueError("Stockage float32 vector(1024) requis.")
    return state


def sample_documents(connection, state, form_ids):
    if len(form_ids) > 64:
        raise ValueError("Nombre de formulaires inattendu ; revoir le plan d'échantillonnage.")
    rows = (
        connection.execute(
            text("""SELECT ordinal,record FROM rag_full.documents
        WHERE space_id='full' AND ordinal=ANY(:ordinals) ORDER BY ordinal"""),
            {"ordinals": sample_ordinals(state["documents"])},
        )
        .mappings()
        .all()
    )
    if {r["ordinal"] for r in rows} != set(sample_ordinals(state["documents"])):
        raise ValueError("Ordinaux manquants.")
    selected = {r["ordinal"]: r for r in rows}
    # The composite space/form/type index bounds these probes; no corpus scan.
    for form_id in form_ids:
        for kind in ("open_answer", "other_text"):
            row = (
                connection.execute(
                    text("""SELECT ordinal,record FROM rag_full.documents
                WHERE space_id='full' AND questionnaire_id=:form AND unit_type=:kind
                LIMIT 1"""),
                    {"form": form_id, "kind": kind},
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                selected[row["ordinal"]] = row
    return [(ordinal, restore_document(row["record"])) for ordinal, row in sorted(selected.items())]


def verify_sample(documents, source_rows):
    originals = {}
    for row in source_rows:
        originals.update((d.document_id, d) for d in row_to_documents(row, "gdn-2019"))
    evidence = []
    for ordinal, indexed in documents:
        actual = originals.get(indexed.document_id)
        if actual is None or actual.to_dict() != indexed.to_dict():
            raise ValueError(
                "Échantillon incompatible : identité, contenu ou provenance différente."
            )
        evidence.append(
            {
                "ordinal": ordinal,
                "document_id": indexed.document_id,
                "content_hash": indexed.content_hash,
            }
        )
    return evidence


def verify_vector_samples(connection, samples):
    rows = (
        connection.execute(
            text("""SELECT document_id,vector_hash,
        public.vector_send(embedding) AS binary FROM rag_full.segments
        WHERE space_id='full' AND document_id=ANY(:ids) AND segment_index=0"""),
            {"ids": [s["document_id"] for s in samples]},
        )
        .mappings()
        .all()
    )
    hashes = {}
    for row in rows:
        if vector_hash(decode_vector_binary(row["binary"])) != row["vector_hash"]:
            raise ValueError("Vecteur transféré différent de son empreinte originale.")
        hashes[row["document_id"]] = row["vector_hash"]
    if set(hashes) != {s["document_id"] for s in samples}:
        raise ValueError("Segments vectoriels manquants.")
    return [sample | {"vector_hash": hashes[sample["document_id"]]} for sample in samples]


def exclusive_json(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")


def inspect_or_publish(args):
    if args.command == "publish":
        if not args.approve_sampled_equivalence:
            raise ValueError("Approbation explicite de la preuve échantillonnée requise.")
        require_key(os.environ.get("SEARCH_PUBLICATION_KEY", ""))
        if Path(args.output).exists():
            raise ValueError("La publication existe déjà ; utiliser un nouveau fichier.")
    settings = load_settings(env_file=args.reader_env)
    if (settings.require_source_url().database, settings.require_rag_url().database) != (
        args.source_name,
        args.search_name,
    ):
        raise ValueError("Noms de bases différents des identités attendues.")
    source = create_search_engine(settings.require_source_url())
    target = create_search_engine(settings.require_rag_url())
    try:
        with ExitStack() as stack:
            left = stack.enter_context(source.connect())
            right = stack.enter_context(target.connect())
            for connection in (left, right):
                stack.enter_context(connection.begin())
                connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                connection.execute(text("SET LOCAL statement_timeout='5s'"))
            origin = inspect_database(left, source=True)
            destination = inspect_database(right)
            assert_distinct(origin, destination)
            if origin.schema_revision != "forms_statistics_v1":
                raise ValueError("Révision applicative non approuvée pour la publication.")
            state = checked_state(right)
            logical_id = fingerprint(logical_corpus(state))
            if args.check_reader:
                check_reader_role(left)
                check_reader_role(right)
            result = {
                "logical_id": logical_id,
                "documents": state["documents"],
                "segments": state["segments"],
                "revision": "rag_0007",
            }
            if args.command == "publish":
                if logical_id != args.expected_logical_id:
                    raise ValueError("Empreinte logique différente de l'archive approuvée.")
                forms = (
                    left.execute(text("SELECT id FROM public.forms ORDER BY id")).scalars().all()
                )
                documents = sample_documents(right, state, forms)
                rows = (
                    left.execute(
                        text(ANSWER_SELECT + " WHERE a.id=ANY(:ids)"),
                        {"ids": sorted({d.answer_id for _, d in documents})},
                    )
                    .mappings()
                    .all()
                )
                samples = verify_vector_samples(right, verify_sample(documents, rows))
                envelope = sign_publication(
                    state,
                    origin.to_dict(),
                    destination.to_dict(),
                    samples,
                    os.environ["SEARCH_PUBLICATION_KEY"],
                )
                exclusive_json(args.output, envelope)
                result.update(samples=len(samples), assurance=envelope["payload"]["assurance"])
            return result
    finally:
        source.dispose()
        target.dispose()


def model_check(args):
    # No import of torch, Transformers or the model unless explicitly requested.
    from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
    from cahier_rag.embeddings.registry import MODELS
    from cahier_rag.embeddings.transformers_backend import TransformersBackend

    engine = EmbeddingEngine(
        TransformersBackend(
            MODELS["bge-m3"],
            Path(args.models),
            device="cpu",
            precision="float32",
            threads=args.threads,
        )
    )
    try:
        engine.load()
        if engine.backend.torch.version.cuda is not None:
            raise ValueError("Une distribution PyTorch CPU sans CUDA est requise.")
        vector = next(
            engine.encode_queries([EmbeddingInput("probe", "Transports publics", "probe")])
        ).vectors[0]
        if len(vector) != 1024:
            raise ValueError("Dimension inattendue.")
        return {"cpu": True, "dimensions": len(vector), "threads": args.threads}
    finally:
        engine.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--reader-env", required=True)
        command.add_argument("--source-name", default="cahier_doleances")
        command.add_argument("--search-name", default="cahier_search")
        command.add_argument("--check-reader", action="store_true")
        if name == "publish":
            command.add_argument("--output", required=True)
            command.add_argument("--expected-logical-id", required=True)
            command.add_argument("--approve-sampled-equivalence", action="store_true")
    command = commands.add_parser("model-check")
    command.add_argument("--models", required=True)
    command.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args(argv)
    try:
        result = model_check(args) if args.command == "model-check" else inspect_or_publish(args)
        print(json.dumps({"status": "ok", **result}))
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "code": "search_preparation_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
