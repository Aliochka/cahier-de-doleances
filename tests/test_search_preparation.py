"""Deployment preparation with synthetic documents; never opens working databases."""

import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomllib
import yaml
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.safety import DatabaseIdentity
from cahier_rag.search.publication import (
    Publication,
    PublicationError,
    logical_corpus,
    sample_ordinals,
    sign_publication,
)
from cahier_rag.search.service.control import Budget, SearchNotReady
from cahier_rag.search.service.reader import SearchReader, compatible_source_identity
from cahier_rag.sources.gdn import row_to_documents
from cahier_rag.vector.preparation import TokenConfig

from app import search_admin

KEY = "synthetic-publication-key-" * 3


def row():
    return dict(
        answer_id=1,
        contribution_id=2,
        question_id=3,
        questionnaire_id=4,
        question_form_id=4,
        contribution_form_id=4,
        answer_text="Texte original",
        question_type="text",
        value_json=None,
        answer_position=1,
        question_position=1,
        question_text="Pourquoi ?",
        questionnaire_name="Enquête",
        contribution_title=None,
        question_section=None,
        question_code="Q1",
        questionnaire_version="2019",
        questionnaire_source="source",
        contribution_source="source",
        external_contribution_id="original",
        submitted_at=None,
    )


@pytest.fixture
def corpus():
    origin = DatabaseIdentity(
        "local", 1, "cahier_doleances_local", "remove_runtime_caches"
    ).to_dict()
    source = DatabaseIdentity("wallace", 10, "cahier_doleances", "forms_statistics_v1").to_dict()
    target = DatabaseIdentity("wallace", 20, "cahier_search").to_dict()
    manifest = dict(
        audit_source=origin,
        corpus="gdn-2019",
        space="full",
        normalize=True,
        storage="float32",
        model=MODELS["bge-m3"].to_dict(),
        tokens=TokenConfig().to_dict(),
    )
    state = dict(
        manifest=manifest,
        recipe_hash=fingerprint(manifest),
        chain_hash="chain",
        documents=1,
        segments=1,
        expected_units=1,
        vector_cursor=1,
        verified=True,
        extraction_complete=True,
        vectors_complete=True,
    )
    document = row_to_documents(row(), "gdn-2019")[0]
    samples = search_admin.verify_sample([(1, document)], [row()])
    return state, source, target, samples


def write_publication(path, corpus, key=KEY):
    state, source, target, samples = corpus
    path.write_text(json.dumps(sign_publication(state, source, target, samples, key)))
    return Publication(path, key)


def test_logical_identity_is_distinct_from_installation(corpus):
    state, source, _, _ = corpus
    moved = deepcopy(state)
    moved["manifest"]["audit_source"] = source
    assert fingerprint(logical_corpus(state)) == fingerprint(logical_corpus(moved))
    moved["chain_hash"] = "different-data"
    assert fingerprint(logical_corpus(state)) != fingerprint(logical_corpus(moved))
    assert not compatible_source_identity(state["manifest"]["audit_source"], source)


def test_publication_preserves_origin_and_binds_both_databases(corpus, tmp_path):
    state, source, target, _ = corpus
    before = deepcopy(state)
    publication = write_publication(tmp_path / "publication.json", corpus)
    assert publication.validate(state, source, target)
    assert state == before
    for identity, other in ((source, target), (target, source)):
        for field in ("cluster_id", "database_oid", "database_name"):
            wrong = identity | {field: "unexpected"}
            with pytest.raises(PublicationError):
                if identity is source:
                    publication.validate(state, wrong, other)
                else:
                    publication.validate(state, other, wrong)


def test_tamper_wrong_key_changed_generation_and_empty_proof_fail(corpus, tmp_path):
    state, source, target, _ = corpus
    path = tmp_path / "publication.json"
    publication = write_publication(path, corpus)
    with pytest.raises(PublicationError):
        Publication(path, "wrong-key-" * 5).validate(state, source, target)
    with pytest.raises(PublicationError):
        publication.validate(state | {"chain_hash": "changed"}, source, target)
    envelope = json.loads(path.read_text())
    envelope["payload"]["source"] = source | {"cluster_id": "forged"}
    path.write_text(json.dumps(envelope))
    with pytest.raises(PublicationError):
        publication.validate(state, source, target)
    path.write_text(json.dumps(sign_publication(state, source, target, [], KEY)))
    with pytest.raises(PublicationError):
        publication.validate(state, source, target)


def test_future_schema_needs_explicit_review(corpus, tmp_path):
    state, source, target, _ = corpus
    publication = write_publication(tmp_path / "p.json", corpus)
    with pytest.raises(PublicationError):
        publication.validate(state, source | {"schema_revision": "unreviewed"}, target)
    original = source | {"schema_revision": "remove_runtime_caches"}
    assert compatible_source_identity(original, source)
    assert not compatible_source_identity(original, source | {"database_oid": 99})


@pytest.mark.parametrize("count", [1, 2, 96, 97, 5_172_356])
def test_sampling_is_bounded_deterministic_and_covers_extremities(count):
    ordinals = sample_ordinals(count)
    assert ordinals == sorted(set(ordinals))
    assert len(ordinals) == min(96, count)
    assert ordinals[0] == 1 and ordinals[-1] == count


@pytest.mark.parametrize(
    "field,value",
    [
        ("answer_text", "Autre contenu"),
        ("question_text", "Autre contexte"),
        ("contribution_id", 99),
        ("external_contribution_id", "different"),
    ],
)
def test_equal_counts_cannot_prove_content_or_provenance(field, value):
    original = row()
    indexed = row_to_documents(original, "gdn-2019")[0]
    with pytest.raises(ValueError, match="incompatible"):
        search_admin.verify_sample([(1, indexed)], [original | {field: value}])
    with pytest.raises(ValueError, match="incompatible"):
        search_admin.verify_sample([(1, indexed)], [])


def test_other_text_units_are_checked_individually():
    source = row() | {"question_type": "multi_choice", "value_json": '{"other_text":["A","B"]}'}
    units = row_to_documents(source, "gdn-2019")
    assert len(search_admin.verify_sample(list(enumerate(units, 1)), [source])) == 2
    with pytest.raises(ValueError):
        search_admin.verify_sample(
            [(1, units[1])], [source | {"value_json": '{"other_text":["B","A"]}'}]
        )


def test_reader_uses_publication_and_invalidates_generation_on_republication(
    corpus, tmp_path, monkeypatch
):
    state, source, target, _ = corpus
    path = tmp_path / "p.json"
    publication = write_publication(path, corpus)
    reader = SearchReader(None, None, publication=publication)
    connection = MagicMock()

    def execute(sql, parameters=None):
        result = MagicMock()
        if "rag_alembic_version" in str(sql):
            result.scalar_one.return_value = "rag_0007"
        elif "rag_tuning.statistics" in str(sql):
            result.mappings.return_value.one_or_none.return_value = {
                "version": 1,
                "documents": 1,
                "corpus_hash": "chain",
            }
        else:
            result.mappings.return_value.all.return_value = [
                {"amname": "gin", "relname": "gin", "indisvalid": True, "indisready": True},
                {
                    "amname": "hnsw",
                    "relname": "segments_full_hnsw",
                    "indisvalid": True,
                    "indisready": True,
                },
            ]
        return result

    connection.execute.side_effect = execute

    @contextmanager
    def transaction():
        yield connection, DatabaseIdentity(**source)

    store = MagicMock()
    store.guard.transaction = transaction
    store.state.return_value = state
    monkeypatch.setattr(reader, "store", lambda budget: store)
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    monkeypatch.setattr(
        "cahier_rag.search.service.reader.inspect_database", lambda c: DatabaseIdentity(**target)
    )
    first = reader.validate(Budget(5))
    assert reader.validate(Budget(5)) == first
    write_publication(path, corpus)
    with pytest.raises(SearchNotReady, match="génération"):
        reader.validate(Budget(5))


@pytest.mark.parametrize(
    "server,vector,revision",
    [
        ("170010", "0.8.7", "rag_0007"),
        ("180000", "0.8.7", "rag_0007"),
        ("170011", "0.8.6", "rag_0007"),
        ("170011", "0.8.7", "rag_0006"),
    ],
)
def test_postgres_extension_revision_gate(server, vector, revision):
    with pytest.raises(ValueError):
        search_admin.check_versions(server, vector, revision)


def test_postgres_supported_versions_and_exclusive_private_output(tmp_path):
    search_admin.check_versions("170011", "0.8.7", "rag_0007")
    path = tmp_path / "p.json"
    search_admin.exclusive_json(path, {"test": True})
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        search_admin.exclusive_json(path, {"test": False})


def test_admin_failure_does_not_disclose_url_or_secret(monkeypatch, capsys):
    def fail(args):
        raise ValueError("postgresql://private:DO_NOT_PRINT@host/db")

    monkeypatch.setattr(search_admin, "inspect_or_publish", fail)
    assert search_admin.main(["inspect", "--reader-env", "missing"]) == 1
    assert "DO_NOT_PRINT" not in capsys.readouterr().out


def test_cpu_lock_aligns_runtime_versions_without_cuda():
    root = tomllib.loads(Path("pyproject.toml").read_text())
    rag = tomllib.loads(Path("rag/pyproject.toml").read_text())
    cpu = tomllib.loads(Path("deploy/search-cpu/pyproject.toml").read_text())
    assert set(cpu["project"]["dependencies"]) == (
        set(root["project"]["dependencies"])
        | set(rag["project"]["optional-dependencies"]["embeddings"])
    )
    lock = tomllib.loads(Path("deploy/search-cpu/uv.lock").read_text())
    old = {p["name"]: p["version"] for p in tomllib.loads(Path("uv.lock").read_text())["package"]}
    for package in lock["package"]:
        assert not package["name"].startswith("nvidia-") and package["name"] != "triton"
        if package["name"] == "torch":
            assert package["version"] in {"2.10.0", "2.10.0+cpu"}
            assert package["source"]["registry"] == "https://download.pytorch.org/whl/cpu"
        elif package["name"] in old:
            assert package["version"] == old[package["name"]]


def test_opt_in_mounts_and_single_worker_preserve_disabled_deployment():
    base = yaml.safe_load(Path("compose.deploy.yml").read_text())
    overlay = yaml.safe_load(Path("compose.search.yml").read_text())
    assert "volumes" not in base["services"]["app"]
    service = overlay["services"]["app"]
    assert service["environment"]["SEARCH_DEVICE"] == "cpu"
    assert service["environment"]["SEARCH_PRECISION"] == "float32"
    assert "false" in service["environment"]["HYBRID_SEARCH_ENABLED"]
    assert all(v["read_only"] and not v["bind"]["create_host_path"] for v in service["volumes"])
    command = next(
        line[4:] for line in Path("Dockerfile").read_text().splitlines() if line.startswith("CMD ")
    )
    command = json.loads(command)
    assert command[command.index("-w") + 1] == "1"


@pytest.mark.parametrize("threads", ["1", "2", "4"])
def test_runtime_cpu_threads_are_passed_without_loading_model(threads, monkeypatch):
    from app import hybrid_runtime

    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SEARCH_CONFIG_FILE", "/nonexistent")
    monkeypatch.setenv("SEARCH_CURSOR_KEY", "cursor-test-" * 4)
    monkeypatch.setenv("SEARCH_CPU_THREADS", threads)
    monkeypatch.delenv("SEARCH_PUBLICATION_FILE", raising=False)
    monkeypatch.setattr(hybrid_runtime, "load_settings", lambda **kwargs: "settings")
    factory = MagicMock()
    monkeypatch.setattr(hybrid_runtime, "create_service", factory)
    monkeypatch.setattr(hybrid_runtime, "Hydrator", MagicMock())
    hybrid_runtime.build_backend()
    assert factory.call_args.kwargs["threads"] == int(threads)


def test_production_cannot_start_search_without_publication(monkeypatch):
    from app import hybrid_runtime

    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SEARCH_CONFIG_FILE", "/nonexistent")
    monkeypatch.setenv("SEARCH_CURSOR_KEY", "cursor-test-" * 4)
    monkeypatch.delenv("SEARCH_PUBLICATION_FILE", raising=False)
    with pytest.raises(ValueError, match="publication"):
        hybrid_runtime.build_backend()


def test_benchmark_reports_errors_and_refuses_implicit_execution(tmp_path):
    from scripts.benchmark_public_search import main, queries, summary

    assert len(queries("rag/evaluation/performance-rag027.json")) == 32

    result = summary(
        [
            {"seconds": 1, "status": 200},
            {"seconds": 2, "status": 200},
            {"seconds": 0.01, "status": 503},
        ],
        3,
    )
    assert result["success_p95_seconds"] == 2
    assert result["error_rate"] == pytest.approx(1 / 3)
    assert result["status_counts"] == {"200": 2, "503": 1}
    output = tmp_path / "not-created.json"
    with pytest.raises(SystemExit):
        main(["--mode", "encoding", "--cache-state", "warm", "--output", str(output)])
    assert not output.exists()


def test_archive_catalog_skips_only_preinstalled_vector_metadata():
    from scripts.search_archive_catalog import restore_catalog

    catalog = """1; 1 1 EXTENSION - vector owner
2; 0 0 COMMENT - EXTENSION vector owner
3; 0 0 TABLE DATA rag_full spaces owner
4; 0 0 TABLE DATA rag_full documents_full owner
5; 0 0 TABLE DATA rag_full segments_full owner
6; 0 0 TABLE DATA public rag_alembic_version owner
7; 0 0 TABLE DATA rag_tuning term_statistics owner
8; 1 1 INDEX rag_full segments_full_hnsw owner
9; 1 1 INDEX rag_full documents_full_search_vector_idx owner
"""
    filtered = restore_catalog(catalog)
    assert "EXTENSION" not in filtered
    assert filtered.splitlines() == catalog.splitlines()[2:]
    with pytest.raises(ValueError):
        restore_catalog(catalog.replace("INDEX rag_full segments_full_hnsw", "OTHER"))


def test_missing_model_snapshot_fails_offline(tmp_path, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("No network connection is permitted for a missing snapshot")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert search_admin.main(["model-check", "--models", str(tmp_path)]) == 1
