"""Opt-in PostgreSQL tests create a NEW private cluster, never an existing DB.

Set SEARCH_DEPLOY_TEST_PG_BIN to PostgreSQL 17 binaries. No TCP listener, no model.
"""

import importlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cahier_rag.config import load_settings
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.store import chain, vector_hash
from cahier_rag.search.publication import Publication, logical_corpus
from cahier_rag.search.service import HybridSearch
from cahier_rag.search.service.reader import SearchReader, create_search_engine
from cahier_rag.storage import document_record
from cahier_rag.vector.preparation import TokenConfig
from sqlalchemy import create_engine, text

from app import search_admin

KEY = "synthetic-publication-key-" * 3

pytestmark = pytest.mark.search_deploy_pg


@pytest.fixture(scope="module")
def isolated_cluster(tmp_path_factory):
    configured = os.environ.get("SEARCH_DEPLOY_TEST_PG_BIN")
    if not configured:
        pytest.skip("Explicit opt-in required for a new private PostgreSQL test cluster")
    binary = Path(configured)
    root = tmp_path_factory.mktemp("search-pg")
    data, socket = root / "data", root / "socket"
    socket.mkdir()
    env = dict(os.environ, PGHOST=str(socket), PGPORT="55439", PGUSER="search_test_admin")
    subprocess.run(
        [
            str(binary / "initdb"),
            "-D",
            str(data),
            "-A",
            "trust",
            "--no-sync",
            "--username=search_test_admin",
            "--encoding=UTF8",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(binary / "pg_ctl"),
            "-D",
            str(data),
            "-l",
            str(root / "postgres.log"),
            "-o",
            f"-k {socket} -p 55439 -c listen_addresses='' -c fsync=off",
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
    )
    try:
        yield root, env
    finally:
        subprocess.run(
            [str(binary / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
            check=True,
            capture_output=True,
        )


def psql(env, sql):
    subprocess.run(
        ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
        input=sql,
        text=True,
        env=env,
        check=True,
        capture_output=True,
    )


def test_restore_roles_publication_reader_and_real_h1(isolated_cluster, monkeypatch):
    from cahier_rag.sources.gdn import ANSWER_SELECT, row_to_documents

    root, env = isolated_cluster
    psql(
        env,
        r"""
CREATE DATABASE cahier_doleances TEMPLATE template0;
\connect cahier_doleances
CREATE TABLE alembic_version(version_num text);
INSERT INTO alembic_version VALUES ('forms_statistics_v1');
CREATE TABLE forms(id bigint PRIMARY KEY,name text,version text,source text);
CREATE TABLE questions(id bigint PRIMARY KEY,form_id bigint,prompt text,position int,
    section text,type text,question_code text);
CREATE TABLE contributions(id bigint PRIMARY KEY,form_id bigint,title text,source text,
    source_contribution_id text,submitted_at timestamp);
CREATE TABLE answers(id bigint PRIMARY KEY,contribution_id bigint,question_id bigint,
    text text,value_json text,position int);
INSERT INTO forms VALUES(4,'Enquête','2019','source');
INSERT INTO questions VALUES(3,4,'Pourquoi ?',1,NULL,'text','Q1');
INSERT INTO contributions VALUES(2,4,NULL,'source','original',NULL);
INSERT INTO answers VALUES(1,2,3,'Texte original',NULL,1);
""",
    )
    psql(env, Path("deploy/postgres/create-search.sql").read_text())

    def url(database, user="search_test_admin"):
        return f"postgresql+psycopg2://{user}@/{database}?host={env['PGHOST']}&port={env['PGPORT']}"

    engine = create_engine(url("cahier_search"))
    manifest = dict(
        audit_source={
            "cluster_id": "original",
            "database_oid": 1,
            "database_name": "local",
            "schema_revision": "remove_runtime_caches",
        },
        space="full",
        corpus="gdn-2019",
        normalize=True,
        storage="float32",
        model=MODELS["bge-m3"].to_dict(),
        tokens=TokenConfig().to_dict(),
    )
    fixture_source = create_engine(url("cahier_doleances"))
    with fixture_source.connect() as connection:
        document = row_to_documents(
            connection.execute(text(ANSWER_SELECT)).mappings().one(), "gdn-2019"
        )[0]
    fixture_source.dispose()
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA rag"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for name in (
                "rag_0004_fullcorpus",
                "rag_0005_fullcorpus_ann",
                "rag_0006_fullcorpus_ann_full",
                "rag_0007_lexical_statistics",
            ):
                importlib.import_module("cahier_rag.migrations.versions." + name).upgrade()
        connection.execute(text("CREATE TABLE public.rag_alembic_version(version_num text)"))
        connection.execute(text("INSERT INTO public.rag_alembic_version VALUES ('rag_0007')"))
        connection.execute(
            text("""INSERT INTO rag_full.spaces
            (space_id,manifest,recipe_hash,expected_units,documents,segments,vector_cursor,
             chain_hash,verified,extraction_complete,vectors_complete)
            VALUES('full',CAST(:manifest AS jsonb),:hash,1,1,1,1,:chain,true,true,true)"""),
            {
                "manifest": json.dumps(manifest),
                "hash": fingerprint(manifest),
                "chain": chain("", [document]),
            },
        )
        connection.execute(
            text("""INSERT INTO rag_full.documents
            VALUES('full',:id,1,1,2,4,'open_answer',:hash,CAST(:record AS jsonb),
                   to_tsvector('pg_catalog.french','Texte original'),NULL)"""),
            {
                "id": document.document_id,
                "hash": document.content_hash,
                "record": json.dumps(document_record(document)),
            },
        )
        vector = "[1,-0," + ",".join(["0"] * 1022) + "]"
        connection.execute(
            text("""INSERT INTO rag_full.segments
            VALUES('full',:id,0,'representation',0,14,2,:hash,:vector_hash,CAST(:vector AS vector))"""),
            {
                "id": document.document_id,
                "hash": document.content_hash,
                "vector": vector,
                "vector_hash": vector_hash([1.0, -0.0] + [0.0] * 1022),
            },
        )
        connection.execute(
            text("""INSERT INTO rag_tuning.statistics
            (space_id,corpus_hash,documents,lexemes,version) VALUES('full',:chain,1,2,1)"""),
            {"chain": chain("", [document])},
        )
    psql(env, Path("deploy/postgres/grant-search-reader.sql").read_text())
    psql(env, Path("deploy/postgres/monitor-search-restore.sql").read_text())
    # Production count gate must refuse this tiny fixture, without changing data.
    with pytest.raises(subprocess.CalledProcessError):
        psql(
            env, "\\connect cahier_search\n" + Path("deploy/postgres/verify-search.sql").read_text()
        )
    with pytest.raises(subprocess.CalledProcessError):
        psql(env, Path("deploy/postgres/create-search.sql").read_text())
    maintenance = root / "maintenance.env"
    maintenance.write_text(
        f"RAG_SOURCE_DATABASE_URL={url('cahier_doleances')}\nRAG_DATABASE_URL={url('cahier_search')}\n"
    )
    with engine.connect() as connection:
        state = search_admin.checked_state(connection)
    args = SimpleNamespace(
        command="inspect",
        reader_env=str(maintenance),
        source_name="cahier_doleances",
        search_name="cahier_search",
        check_reader=False,
    )
    logical_id = search_admin.inspect_or_publish(args)["logical_id"]
    assert logical_id == fingerprint(logical_corpus(state))
    publication_file = root / "publication.json"
    monkeypatch.setenv("SEARCH_PUBLICATION_KEY", KEY)
    args.command, args.output = "publish", str(publication_file)
    args.approve_sampled_equivalence, args.expected_logical_id = True, logical_id
    assert search_admin.inspect_or_publish(args)["samples"] == 1
    private = root / "reader.env"
    private.write_text(
        f"RAG_SOURCE_DATABASE_URL={url('cahier_doleances', 'cahier_search_reader')}\n"
        f"RAG_DATABASE_URL={url('cahier_search', 'cahier_search_reader')}\n"
    )
    args.command, args.reader_env, args.check_reader = "inspect", str(private), True
    assert search_admin.inspect_or_publish(args)["logical_id"] == logical_id
    settings = load_settings(env_file=private)
    reader = SearchReader(
        create_search_engine(settings.source_url),
        create_search_engine(settings.rag_url),
        publication=Publication(publication_file, KEY),
    )

    class Encoder:
        def load(self):
            pass

        def close(self):
            pass

        def encode_queries(self, inputs):
            yield SimpleNamespace(vectors=[[1.0] + [0.0] * 1023])

    service = HybridSearch(reader, Encoder())
    try:
        service.start()
        ranking = service.retrieve("Texte original")
        assert ranking.recipe_version == "h1-public-v1"
        assert ranking.hits[0].document == document
    finally:
        service.close()
    # Small real logical roundtrip: new fixture database, same precreated extension.
    # Never dump a working local corpus or rebuild any existing index.
    archive, toc = root / "tiny.dump", root / "restore.toc"
    subprocess.run(
        ["pg_dump", "-Fc", "-d", "cahier_search", "-f", str(archive)],
        env=env,
        check=True,
        capture_output=True,
    )
    from scripts.search_archive_catalog import restore_catalog

    listing = subprocess.run(
        ["pg_restore", "--list", str(archive)], env=env, check=True, capture_output=True, text=True
    ).stdout
    toc.write_text(restore_catalog(listing))
    psql(
        env,
        "CREATE DATABASE cahier_search_restore_test OWNER cahier_search_owner "
        "TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'fr_FR.UTF-8' LC_CTYPE 'fr_FR.UTF-8';\n"
        "\\connect cahier_search_restore_test\nCREATE EXTENSION vector VERSION '0.8.7';",
    )
    for section in ("pre-data", "data", "post-data"):
        subprocess.run(
            [
                "pg_restore",
                "-d",
                "cahier_search_restore_test",
                "--role=cahier_search_owner",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--use-list",
                str(toc),
                "--section",
                section,
                str(archive),
            ],
            env=dict(
                env, PGOPTIONS="-c maintenance_work_mem=16MB -c max_parallel_maintenance_workers=0"
            ),
            check=True,
            capture_output=True,
        )
    restored = create_engine(url("cahier_search_restore_test"))
    with restored.connect() as connection:
        assert search_admin.checked_state(connection)["chain_hash"] == state["chain_hash"]
        search_admin.verify_vector_samples(connection, [{"document_id": document.document_id}])
        assert (
            connection.execute(text("SELECT count(*) FROM rag_full.segments_full")).scalar_one()
            == 1
        )
    restored.dispose()
    with engine.connect() as connection:
        assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "off"
    # Deliberate mutation of THIS NEW fixture DB only; no existing database is used.
    source = create_engine(url("cahier_doleances"))
    with source.begin() as connection:
        connection.execute(text("UPDATE answers SET text='Incompatible'"))
    args.command, args.reader_env, args.check_reader = "publish", str(maintenance), False
    args.output = str(root / "must-not-exist.json")
    with pytest.raises(ValueError, match="incompatible"):
        search_admin.inspect_or_publish(args)
    assert not Path(args.output).exists()
    source.dispose()
    engine.dispose()
