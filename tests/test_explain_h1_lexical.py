"""Offline SQL interception tests: no sockets, working database or encoder."""

import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.search.service.control import Budget, SearchTimeout
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import psycopg2

from scripts import explain_h1_lexical as diagnostic


@pytest.fixture(autouse=True)
def forbid_database_and_network(monkeypatch):
    import socket

    import psycopg2 as driver

    def forbidden(*args, **kwargs):
        pytest.fail("Offline tests must not connect to a database or network")

    monkeypatch.setattr(driver, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


PLAN = [
    {
        "Plan": {
            "Node Type": "Limit",
            "Startup Cost": 1.2,
            "Total Cost": 9.5,
            "Plan Rows": 50,
            "Plan Width": 24,
            "Output": ["SECRET_CITIZEN_TEXT"],
            "Plans": [
                {
                    "Node Type": "Gather Merge",
                    "Workers Planned": 2,
                    "Plans": [
                        {
                            "Node Type": "Sort",
                            "Sort Key": [
                                "ts_rank_cd(search_vector, 'SECRET_QUERY'::tsquery) DESC",
                                'd.document_id COLLATE "C"',
                                "SECRET_OTHER_EXPRESSION",
                            ],
                            "Plans": [
                                {
                                    "Node Type": "Bitmap Heap Scan",
                                    "Schema": "rag_full",
                                    "Relation Name": "documents_full",
                                    "Plan Rows": 100000,
                                    "Filter": "SECRET_CITIZEN_TEXT",
                                    "Recheck Cond": "SECRET_QUERY",
                                    "Parallel Aware": True,
                                    "Plans": [
                                        {
                                            "Node Type": "Bitmap Index Scan",
                                            "Index Name": "documents_full_search_vector_idx",
                                            "Index Cond": "SECRET_QUERY",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        "Settings": {"search_path": "SECRET_PATH"},
        "JIT": {"Functions": 12, "Options": {"Inlining": True, "Secret": "SECRET"}},
    }
]


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def scalars(self):
        return self

    def one(self):
        return self.value

    def one_or_none(self):
        return self.value

    def all(self):
        return self.value


class FakeRaw:
    def __init__(self, target, *, unsafe=False, readonly="on", fail_explain=False):
        self.target, self.unsafe, self.readonly = target, unsafe, readonly
        self.fail_explain = fail_explain
        self.calls, self.transactions = [], []
        self.connection = SimpleNamespace(driver_connection=SimpleNamespace(cancel=MagicMock()))
        self.state = {
            "verified": True,
            "documents": 5172356,
            "manifest": {},
            "recipe_hash": fingerprint({}),
            "chain_hash": "corpus",
        }

    def execution_options(self, **options):
        assert options == {"postgresql_readonly": True}
        return self

    def begin(self):
        transaction = MagicMock()
        self.transactions.append(transaction)
        return transaction

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.calls.append((statement, parameters))
        if sql.startswith(diagnostic.EXPLAIN):
            if self.fail_explain:
                raise RuntimeError("SECRET_PASSWORD_AND_CITIZEN_TEXT")
            return Result(deepcopy(PLAN))
        if sql == "SET TRANSACTION READ ONLY" or sql.startswith("SELECT set_config("):
            return Result(None)
        if "AS read_only" in sql:
            return Result(
                {"read_only": self.readonly, "statement_timeout": "2s", "lock_timeout": "200ms"}
            )
        if "FROM pg_roles" in sql:
            return Result(self.unsafe)
        if "FROM pg_settings" in sql:
            return Result([("jit", "on"), ("server_version_num", "170011")])
        if "pg_control_system()" in sql:
            return Result(
                {
                    "cluster_id": "cluster",
                    "database_oid": 2 if self.target else 1,
                    "database_name": "rag" if self.target else "source",
                }
            )
        if "public.answers" in sql or "public.alembic_version" in sql:
            return Result(False)
        if sql == "SELECT * FROM rag_full.spaces WHERE space_id=:space":
            return Result(self.state)
        if sql.startswith("SELECT tsvector_to_array("):
            return Result(["fisc", "fraud"])
        if sql.startswith("SELECT quote_literal(t)"):
            return Result(["'fisc'", "'fraud'"])
        if sql.startswith("SELECT phraseto_tsquery("):
            return Result("'fisc' <-> 'fraud'")
        if sql.startswith("SELECT documents,corpus_hash"):
            return Result({"documents": 5172356, "corpus_hash": "corpus"})
        if sql.startswith("WITH term_stats AS ("):
            return Result(
                [
                    {"term": "fisc", "query": "'fisc'", "idf": 1.25, "total": 3.75},
                    {"term": "fraud", "query": "'fraud'", "idf": 2.5, "total": 3.75},
                ]
            )
        pytest.fail("Unexpected SQL reached fake transport")


class FakeEngine:
    def __init__(self, target, **kwargs):
        self.raw = FakeRaw(target, **kwargs)
        self.url = SimpleNamespace(database="rag" if target else "source")
        self.dispose = MagicMock()

    @contextmanager
    def connect(self):
        yield self.raw


def test_pinned_sources_queries_and_driver():
    diagnostic.verify_sources()
    cases = diagnostic.read_cases(Path("rag/evaluation/performance-rag027.json"))
    assert set(cases) == set(diagnostic.CASE_IDS)


@pytest.mark.parametrize("query_id", diagnostic.CASE_IDS)
def test_real_lexical_path_only_explains_ranking_and_rolls_back(query_id, monkeypatch):
    cases = diagnostic.read_cases(Path("rag/evaluation/performance-rag027.json"))
    source, target = FakeEngine(False), FakeEngine(True)
    monkeypatch.setattr(TunedSearch, "_results", MagicMock(side_effect=AssertionError("hydration")))
    plan, metadata = diagnostic.collect_case(source, target, cases[query_id])
    assert plan == PLAN
    TunedSearch._results.assert_not_called()
    ranking = [(s, p) for s, p in target.raw.calls if str(s).startswith(diagnostic.EXPLAIN)]
    assert len(ranking) == 1
    sql, params = ranking[0]
    assert params["limit"] == 50 and params["space"] == "full"
    assert [params[k] for k in ("form", "kind", "split")] == [None, None, None]
    assert [params[k] for k in ("idf_coverage", "term_coverage", "frequency_proximity")] == [
        0.5,
        0.3,
        0.2,
    ]
    assert params["total_idf"] == 3.75 and params["w0"] == 1.25
    assert "ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)::float8" in str(sql)
    assert 'ORDER BY score DESC,d.document_id COLLATE "C" LIMIT :limit' in str(sql)
    assert "CAST(:total_idf AS float8)" in str(sql)
    assert "CASE WHEN d.search_vector @@ CAST(:t0 AS tsquery)" in str(sql)
    assert "candidates" not in str(sql)
    assert metadata["generation"]["documents"] == 5172356
    assert metadata["session_settings"]["jit"] == "on"
    for engine in (source, target):
        for statement, _ in engine.raw.calls:
            statement_sql = str(statement)
            assert "ANALYZE" not in statement_sql.upper()
            assert "statement_timeout='30s'" not in statement_sql
            assert "record FROM" not in statement_sql
            if "FROM rag_full.documents" in statement_sql:
                assert statement_sql.startswith(diagnostic.EXPLAIN)
        assert engine.raw.transactions
        for tx in engine.raw.transactions:
            tx.rollback.assert_called_once()
            tx.commit.assert_not_called()
        assert sum(str(s) == "SET TRANSACTION READ ONLY" for s, _ in engine.raw.calls) == len(
            engine.raw.transactions
        )


def test_exact_sql_and_psycopg2_binds_match_unmodified_method():
    source, target = FakeEngine(False), FakeEngine(True)
    diagnostic.collect_case(source, target, "fiscal fraude")
    explained, explained_params = next(
        (s, p) for s, p in target.raw.calls if str(s).startswith(diagnostic.EXPLAIN)
    )
    original_calls = []
    raw = FakeRaw(True)

    class OriginalConnection:
        def execute(self, statement, parameters=None):
            if str(statement).startswith("SELECT d.document_id,"):
                original_calls.append((statement, parameters.copy()))
                return Result([])
            if str(statement) == "SET LOCAL statement_timeout='30s'":
                return None
            return raw.execute(statement, parameters)

    class OriginalStore:
        space = "full"

        def __init__(self):
            self.guard = self

        def state(self):
            return raw.state

        @contextmanager
        def transaction(self):
            yield OriginalConnection(), None

    assert (
        TunedSearch(OriginalStore(), statistics=True, prefilter=None).lexical(
            "fiscal fraude", limit=50
        )
        == []
    )
    original, params = original_calls[0]
    assert str(explained) == diagnostic.EXPLAIN + str(original)
    assert params == explained_params
    assert {k: type(v) for k, v in params.items()} == {
        k: type(v) for k, v in explained_params.items()
    }
    dialect = psycopg2.dialect()
    original_compiled = original.compile(dialect=dialect)
    explained_compiled = explained.compile(dialect=dialect)
    assert str(explained_compiled) == diagnostic.EXPLAIN + str(original_compiled)
    assert original_compiled.construct_params(params) == explained_compiled.construct_params(params)
    assert {k: type(v.type) for k, v in original._bindparams.items()} == {
        k: type(v.type) for k, v in explained._bindparams.items()
    }


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT d.document_id, 1 AS score FROM rag_full.documents d LIMIT 50",
        "SELECT document_id,record FROM rag_full.documents WHERE document_id=ANY(:ids)",
        "SELECT count(*) FROM rag_full.documents_full",
        "EXPLAIN ANALYZE SELECT * FROM rag_full.documents",
        "EXPLAIN (ANALYZE FALSE) SELECT * FROM rag_full.documents",
        "UPDATE rag_full.spaces SET documents=0",
        "SET LOCAL statement_timeout='30s'",
        "SELECT 1; DELETE FROM rag_full.spaces",
    ],
)
def test_unexpected_sql_never_reaches_transport(sql):
    wire = MagicMock()
    guard = SimpleNamespace(halted=False, allowed=diagnostic.preparation_allowlist())
    connection = diagnostic.ExplainConnection(wire, guard, target=True)
    with pytest.raises(diagnostic.Refused):
        connection.execute(text(sql))
    wire.execute.assert_not_called()


@pytest.mark.parametrize("options", [{"unsafe": True}, {"readonly": "off"}])
def test_rejects_unsafe_role_or_writable_transaction(options):
    source, target = FakeEngine(False), FakeEngine(True, **options)
    with pytest.raises(Exception):
        diagnostic.collect_case(source, target, "fiscal fraude")
    assert not any(str(s).startswith(diagnostic.EXPLAIN) for s, _ in target.raw.calls)
    for tx in target.raw.transactions:
        tx.rollback.assert_called_once()


def test_timeout_is_capped_by_residual_budget():
    now = [0.0]
    budget = Budget(10, clock=lambda: now[0])
    raw = FakeRaw(True)
    wire = diagnostic.Wire(raw, budget, 2000, 200)
    wire.initialize()
    now[0] = 9.75
    wire.execute(text("SELECT set_config('lock_timeout', :value, true)"), {"value": "200"})
    timeout_values = [
        p["value"] for s, p in raw.calls if "set_config('statement_timeout'" in str(s)
    ]
    assert timeout_values[-1] == "250"
    assert all(1 <= int(v) <= 2000 for v in timeout_values)
    now[0] = 10.1
    before = len(raw.calls)
    with pytest.raises(SearchTimeout):
        wire.execute(text("SELECT 1"))
    assert len(raw.calls) == before


def test_exception_during_explain_still_rolls_back():
    source, target = FakeEngine(False), FakeEngine(True, fail_explain=True)
    with pytest.raises(RuntimeError):
        diagnostic.collect_case(source, target, "fiscal fraude")
    for engine in (source, target):
        for transaction in engine.raw.transactions:
            transaction.rollback.assert_called_once()
            transaction.commit.assert_not_called()


def test_summary_is_positive_projection_without_expressions_or_settings():
    safe = diagnostic.summarize(PLAN)
    encoded = json.dumps(safe)
    assert "SECRET" not in encoded
    assert "ts_rank_cd" not in encoded
    assert "documents_full_search_vector_idx" in encoded
    assert safe["jit"] == {"present": True, "functions": 12, "options": {"Inlining": True}}
    assert safe["nodes"][1]["Workers Planned"] == 2
    assert safe["nodes"][2]["sort_keys"] == [
        "weighted_score",
        "document_id_collate_C",
        "expression_redacted",
    ]


def test_private_files_are_exclusive_and_mode_600(tmp_path):
    path = tmp_path / "private.json"
    diagnostic.private_json(path, PLAN)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        diagnostic.private_json(path, PLAN)


def arguments(tmp_path):
    return SimpleNamespace(
        queries=Path("rag/evaluation/performance-rag027.json"),
        reader_env=Path("unused"),
        output_dir=tmp_path / "new-collection",
        query_ids=diagnostic.CASE_IDS,
        statement_timeout_ms=2000,
        lock_timeout_ms=200,
        case_deadline_seconds=10,
    )


def test_run_outputs_private_plans_redacted_summary_and_manifest(tmp_path, monkeypatch):
    source, target = FakeEngine(False), FakeEngine(True)
    monkeypatch.setattr(
        diagnostic,
        "load_settings",
        lambda **k: SimpleNamespace(
            require_source_url=lambda: "source",
            require_rag_url=lambda: "target",
        ),
    )
    monkeypatch.setattr(
        diagnostic, "create_search_engine", lambda url: source if url == "source" else target
    )
    args = arguments(tmp_path)
    assert diagnostic.run(args) == 0
    assert args.output_dir.stat().st_mode & 0o777 == 0o700
    files = list(args.output_dir.iterdir())
    assert len(files) == 5
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in files)
    assert "SECRET" not in (args.output_dir / "summary.redacted.json").read_text()
    assert "SECRET" in (args.output_dir / "fiscalite-05.plan.json").read_text()
    manifest = json.loads((args.output_dir / "manifest.private.json").read_text())
    assert len(manifest["cases"]) == 3
    source.dispose.assert_called_once()
    target.dispose.assert_called_once()
    with pytest.raises(FileExistsError):
        diagnostic.run(args)


def test_main_sanitizes_failure_and_stops_collection(tmp_path, monkeypatch, capsys):
    source, target = FakeEngine(False), FakeEngine(True, fail_explain=True)
    monkeypatch.setattr(
        diagnostic,
        "load_settings",
        lambda **k: SimpleNamespace(
            require_source_url=lambda: "source",
            require_rag_url=lambda: "target",
        ),
    )
    monkeypatch.setattr(
        diagnostic, "create_search_engine", lambda url: source if url == "source" else target
    )
    output = tmp_path / "out"
    assert (
        diagnostic.main(
            [
                "--reader-env",
                "unused",
                "--queries",
                "rag/evaluation/performance-rag027.json",
                "--output-dir",
                str(output),
            ]
        )
        == 1
    )
    assert "SECRET" not in capsys.readouterr().out
    assert "SECRET" not in (output / "manifest.private.json").read_text()
    assert "SECRET" not in (output / "summary.redacted.json").read_text()
    assert len(json.loads((output / "summary.redacted.json").read_text())["cases"]) == 1


def test_source_and_query_mismatch_fail_before_connect(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    connect = MagicMock(side_effect=AssertionError("database access"))
    monkeypatch.setattr(diagnostic, "create_search_engine", connect)
    monkeypatch.setitem(diagnostic.SOURCE_HASHES, "tuning/lexical.py", "wrong")
    with pytest.raises(diagnostic.Refused, match="h1_source_mismatch"):
        diagnostic.run(args)
    connect.assert_not_called()
    assert not args.output_dir.exists()
    changed = tmp_path / "queries.json"
    changed.write_text('{"queries": []}')
    with pytest.raises(diagnostic.Refused, match="query_file_mismatch"):
        diagnostic.read_cases(changed)


@pytest.mark.parametrize(
    "option,value",
    [
        ("--statement-timeout-ms", "2001"),
        ("--statement-timeout-ms", "0"),
        ("--lock-timeout-ms", "201"),
        ("--lock-timeout-ms", "-1"),
        ("--case-deadline-seconds", "11"),
        ("--case-deadline-seconds", "0"),
    ],
)
def test_cli_cannot_relax_limits(option, value, tmp_path, monkeypatch):
    run = MagicMock(side_effect=AssertionError("must not run"))
    monkeypatch.setattr(diagnostic, "run", run)
    with pytest.raises(SystemExit) as error:
        diagnostic.main(
            [
                "--reader-env",
                "unused",
                "--queries",
                "unused",
                "--output-dir",
                str(tmp_path / "out"),
                option,
                value,
            ]
        )
    assert error.value.code == 2
    run.assert_not_called()


def test_halted_guard_blocks_all_further_sql():
    wire = MagicMock()
    guard = SimpleNamespace(halted=True)
    connection = diagnostic.ExplainConnection(wire, guard, target=True)
    with pytest.raises(diagnostic.Refused):
        connection.execute(text("SELECT * FROM rag_full.spaces WHERE space_id=:space"))
    wire.execute.assert_not_called()


@pytest.mark.parametrize(
    "name,value",
    [("statement_timeout", "0"), ("lock_timeout", "500ms"), ("statement_timeout", "30s")],
)
def test_checks_effective_server_timeouts(name, value):
    raw = FakeRaw(True)
    execute = raw.execute

    def changed(statement, parameters=None):
        result = execute(statement, parameters)
        if "AS read_only" in str(statement):
            result.value[name] = value
        return result

    raw.execute = changed
    with pytest.raises(diagnostic.Refused):
        diagnostic.Wire(raw, Budget(10), 2000, 200).initialize()


def test_import_does_not_load_model_libraries():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts import explain_h1_lexical; import sys; "
            "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
