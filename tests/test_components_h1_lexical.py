"""Offline P3 tests: sockets and PostgreSQL connections are forbidden."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import psycopg2
from sqlalchemy.exc import DBAPIError

from scripts import components_h1_lexical as tool
from tests.test_analyze_h1_lexical import MeasureEngine, measured_plan
from tests.test_decompose_h1_lexical import P2Raw
from tests.test_explain_h1_lexical import Result


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    import psycopg2 as driver

    def forbidden(*args, **kwargs):
        pytest.fail("No real network or database in P3 tests")

    monkeypatch.setattr(driver, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


class ComponentRaw(P2Raw):
    def __init__(self, target, *, denied=False, **kwargs):
        super().__init__(target, **kwargs)
        self.denied = denied

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if sql in tool.OBSERVATIONS.values():
            self.calls.append((statement, parameters))
            if self.denied:
                raise DBAPIError(sql, {}, Exception("SECRET_TEXT_PASSWORD"))
            if sql == tool.OBSERVATIONS["counters"]:
                return Result(dict.fromkeys(tool.COUNTERS, 10))
            if sql == tool.OBSERVATIONS["reset"]:
                return Result({"server_started": "2026-01-01", "stats_reset": None})
            return Result(
                {
                    "toast_oid": 120,
                    "heap_bytes": 8000,
                    "index_bytes": 800,
                    "toast_total_bytes": 2500,
                    "avg_width": 256,
                    "storage": "x",
                    "compression": "",
                }
            )
        if sql.startswith("SELECT count(*) AS sampled"):
            self.calls.append((statement, parameters))
            return Result(
                {
                    "sampled": 7,
                    "compressed": 4,
                    "uncompressed": 3,
                    "pglz": 4,
                    "lz4": 0,
                    "stored_bytes_min": 40,
                    "stored_bytes_max": 600,
                    "stored_bytes_avg": 200.0,
                    "lexemes_avg": 20.0,
                }
            )
        result = super().execute(statement, parameters)
        if sql.startswith(tool.p1.EXPLAIN):
            # Simulate VERBOSE's consumed aggregate expression, without executing SQL.
            plan = result.value
            if " AS sink " in sql:
                expr = sql.split("sum((", 1)[1].split(")) AS sink", 1)[0]
                plan[0]["Plan"]["Node Type"] = "Aggregate"
                plan[0]["Plan"]["Output"] = ["count(*)", "sum((" + expr + "))"]
                plan[0]["Plan"]["Strategy"] = "Plain"
                plan[0]["Plan"]["Partial Mode"] = "Finalize"
            return Result(plan)
        return result


class ComponentEngine(MeasureEngine):
    def __init__(self, target, **kwargs):
        super().__init__(target)
        self.raw = ComponentRaw(target, **kwargs)


def collect(variant, **kwargs):
    source, target = ComponentEngine(False), ComponentEngine(True, **kwargs)
    payload, meta = tool.collect_case(source, target, "fiscal fraude", variant=variant)
    return source, target, payload, meta


def test_pinned_dependencies_unchanged():
    tool.verify_sources()
    assert tool.base.digest(Path(tool.p2.__file__).read_bytes()) == tool.P2_SHA
    assert "ANALYZE" not in tool.base.EXPLAIN


@pytest.mark.parametrize("variant", tool.VARIANTS)
def test_exact_interception_consumption_no_hydration_or_model(variant, monkeypatch):
    monkeypatch.setattr(TunedSearch, "_results", MagicMock(side_effect=AssertionError("hydration")))
    source, target, payload, meta = collect(variant)
    assert meta["status"] == ("observed" if variant == "observe" else "ok")
    TunedSearch._results.assert_not_called()
    original, measured = meta["h1_sql_template"], meta["measured_sql_template"]
    assert tool.WHERE in original
    if variant in (*tool.AGGREGATED, "touch"):
        assert measured.endswith(tool.WHERE)
        assert measured.startswith("SELECT count(*) AS matched, sum((")
        assert "LIMIT" not in measured and "MATERIALIZED" not in measured
        safe = tool.summarize(payload, variant, meta["lexeme_count"])
        assert safe["consumption_evidence"] == "sum_argument_present"
        assert safe["expression_placements"]
        assert "SECRET" not in json.dumps(safe)
    if variant == "full":
        score = original.split("SELECT d.document_id,", 1)[1].split(" AS score FROM", 1)[0]
        assert measured == f"SELECT count(*) AS matched, sum(({score})) AS sink " + tool.WHERE
    if variant in ("observe", "top50"):
        assert original == measured and meta["sql_sha256"] == meta["h1_sql_sha256"]
    if variant == "observe":
        assert payload is None
    if variant == "classify":
        assert "rag_full.documents_full d TABLESAMPLE SYSTEM (0.1) REPEATABLE (2703)" in measured
        assert "LIMIT 512" in measured
        assert tool.safe_classification(payload)["externalized_count"] is None
        assert meta["ranking_statement_timeout_ms"] <= 2000
    statements = [(s, p) for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN)]
    assert len(statements) == (0 if variant in ("classify", "observe") else 1)
    for engine in (source, target):
        for tx in engine.raw.transactions:
            tx.rollback.assert_called_once()
            tx.commit.assert_not_called()
        assert engine.raw.jit == "on" and engine.raw.work_bytes == 4 * tool.p1.MIB
        for stmt, _ in engine.raw.calls:
            assert "set_config('work_mem'" not in str(stmt)
            assert "set_config('track_io_timing'" not in str(stmt)
            if "FROM rag_full.documents" in str(stmt):
                assert str(stmt).startswith((tool.p1.EXPLAIN, "SELECT count(*) AS sampled"))
    assert meta["controls_before"] == meta["controls_after"]
    assert meta["effective_limits"]["read_only"] == "on"
    assert meta["settings_effective"]["jit"] == "off"


def test_original_binds_types_values_and_sql_retained_for_top50():
    _, target, _, meta = collect("top50")
    emitted, params = next(
        (s, p) for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN)
    )
    original = text(meta["h1_sql_template"])
    dialect = psycopg2.dialect()
    assert str(emitted.compile(dialect=dialect)) == tool.p1.EXPLAIN + str(
        original.compile(dialect=dialect)
    )
    assert emitted.compile(dialect=dialect).construct_params(params) == original.compile(
        dialect=dialect
    ).construct_params(params)
    assert {k: type(v.type) for k, v in emitted._bindparams.items()} == {
        k: type(v.type) for k, v in original._bindparams.items()
    }
    assert [params[k] for k in ("idf_coverage", "term_coverage", "frequency_proximity")] == [
        0.5,
        0.3,
        0.2,
    ]
    assert params["limit"] == 50 and params["w0"] == 1.25 and params["total_idf"] == 3.75


@pytest.mark.parametrize(
    "variant,cases,rank",
    [
        ("zero", 0, False),
        ("idf", 2, False),
        ("terms", 2, False),
        ("rank", 0, True),
        ("idf-terms", 4, False),
        ("idf-rank", 2, True),
        ("terms-rank", 2, True),
        ("full", 4, True),
    ],
)
def test_expected_function_occurrences_in_aggregate_argument(variant, cases, rank):
    _, _, _, meta = collect(variant)
    projection = meta["measured_sql_template"].split(" AS sink ")[0]
    assert projection.count("CASE WHEN") == cases
    assert ("ts_rank_cd" in projection) == rank
    assert projection.count("d.search_vector @@") == cases


@pytest.mark.parametrize("kwargs", [{"readonly": "off"}, {"unsafe": True}])
def test_refuse_unsafe_reader_and_rollback(kwargs):
    _, target, payload, meta = collect("full", **kwargs)
    assert meta["status"] == "error" and payload is None
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls)
    for tx in target.raw.transactions:
        tx.rollback.assert_called_once()


def test_timeout_no_retry_no_secrets():
    _, target, payload, meta = collect("full", cancel=True)
    assert meta["status"] == "timeout" and payload is None
    assert "SECRET" not in json.dumps(meta)
    assert sum(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls) == 1
    assert all(t["rollback"] == "done" for t in meta["transactions"])


def test_unknown_queries_never_forwarded():
    wire = MagicMock()
    guard = SimpleNamespace(halted=False, allowed=tool.base.preparation_allowlist())
    connection = tool.ComponentConnection(wire, guard, target=True)
    for sql in (
        "SELECT sum(length(search_vector)) FROM rag_full.documents",
        "DELETE FROM rag_full.documents",
        "SET work_mem='64MB'",
        "EXPLAIN ANALYZE SELECT 1",
    ):
        with pytest.raises(tool.base.Refused):
            connection.execute(text(sql))
    wire.execute.assert_not_called()
    with pytest.raises(tool.base.Refused):
        tool.observe(MagicMock(), "arbitrary SQL")


def test_recomposition_refuses_changed_formula_or_parameters():
    _, target, _, meta = collect("full")
    with pytest.raises(tool.base.Refused):
        tool.components([], {}, "SELECT SECRET")
    params = next(p for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN))
    terms = [
        {"query": "'fisc'", "idf": 1.25, "total": 3.75},
        {"query": "'fraud'", "idf": 2.5, "total": 3.75},
    ]
    score = TunedSearch.score_expression(terms, dict(params))
    with pytest.raises(tool.base.Refused, match="component_recomposition_mismatch"):
        tool.components(terms, params, score + " + 0")
    with pytest.raises(tool.base.Refused, match="component_recomposition_mismatch"):
        tool.components(terms, {**params, "idf_coverage": 0.9}, score)
    with pytest.raises(tool.base.Refused, match="unexpected_ranking"):
        tool.diagnostic_sql(meta["h1_sql_template"] + " -- changed", score, terms, params, "full")


@pytest.mark.parametrize("count", [1, 32])
def test_components_single_and_maximum_lexemes_exact_tree(count):
    terms = [{"query": f"'term{i}'", "idf": i + 0.25, "total": 1000.0} for i in range(count)]
    params = {}
    score = TunedSearch.score_expression(terms, params)
    a, b, c = tool.components(terms, params, score)
    assert a.count("CASE WHEN") == b.count("CASE WHEN") == count
    assert "ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)::float8" in c
    assert score == a + "\n            + " + b + "\n            + " + c


def test_removed_expression_is_not_claimed_consumed_and_placements_are_redacted():
    plan = measured_plan(False)
    plan[0]["Plan"]["Output"] = ["count(*)", "sum(0::float8)"]
    safe = tool.summarize(plan, "idf-rank", 2)
    assert safe["consumption_evidence"] == "unverified_expression_removed_or_rewritten"
    assert "SECRET" not in json.dumps(safe)
    plan[0]["Plan"]["Output"] = ["sum(ts_rank_cd(search_vector, 'SECRET'::tsquery,32))"]
    safe = tool.summarize(plan, "rank", 2)
    assert safe["consumption_evidence"] == "sum_argument_present"
    assert safe["parity"] == "not_tested_aggregate_sum_is_not_score_parity"
    plan[0]["Plan"]["Actual Loops"] = 0
    assert tool.summarize(plan, "rank", 2)["consumption_evidence"].startswith("unverified")
    plan[0]["Plan"]["Actual Loops"] = 1
    plan[0]["Plan"]["Output"] = ["sum('ts_rank_cd( CASE CASE'::text)"]
    assert tool.summarize(plan, "rank", 2)["consumption_evidence"].startswith("unverified")


def test_observations_fresh_readonly_transactions_denied_is_unavailable():
    engine = ComponentEngine(True)
    for name in tool.OBSERVATIONS:
        observed = tool.observe(engine, name)
        assert observed["status"] == "ok" and observed["rollback"] == "done"
    assert len(engine.raw.transactions) == 3
    for tx in engine.raw.transactions:
        tx.rollback.assert_called_once()
        tx.commit.assert_not_called()
    denied = tool.observe(ComponentEngine(True, denied=True), "storage")
    assert denied["status"] == "unavailable" and denied["rollback"] == "done"
    assert "SECRET" not in json.dumps(denied)
    unsafe = tool.observe(ComponentEngine(True, unsafe=True), "counters")
    assert unsafe["status"] == "unavailable"


def test_toast_counters_unavailable_reset_and_zero_never_mean_no_decompression():
    engine = ComponentEngine(True)
    before = {k: tool.observe(engine, k) for k in ("reset", "counters")}
    after = deepcopy(before)
    delta = tool.toast_delta(before, after)
    assert delta["blocks"]["toast_blks_hit"] == 0
    assert "not_decompression_counts" in delta["warning"]
    after["counters"]["values"]["toast_blks_hit"] -= 1
    assert tool.toast_delta(before, after)["status"] == "reset_detected"
    after = deepcopy(before)
    after["reset"]["values"]["stats_reset"] = "changed"
    assert tool.toast_delta(before, after)["status"] == "reset_detected"
    after["reset"]["status"] = "unavailable"
    assert tool.toast_delta(before, after)["status"] == "unavailable"


def arguments(tmp_path, variant="full", name="out"):
    return SimpleNamespace(
        variant=variant,
        query="democratie-02",
        jit="off",
        reader_env=Path("unused"),
        queries=Path("rag/evaluation/performance-rag027.json"),
        output_dir=tmp_path / name,
        statement_timeout_ms=60000,
        case_deadline_seconds=90,
        lock_timeout_ms=200,
        max_output_mib=64,
        min_free_mib=64,
    )


def fake_runtime(monkeypatch, **kwargs):
    engines = []

    def create(url):
        engine = ComponentEngine(url == "target", **kwargs)
        engines.append(engine)
        return engine

    monkeypatch.setattr(
        tool,
        "load_settings",
        lambda **k: SimpleNamespace(
            require_source_url=lambda: "source", require_rag_url=lambda: "target"
        ),
    )
    monkeypatch.setattr(tool, "create_search_engine", create)
    return engines


@pytest.mark.parametrize("variant", ["full", "top50", "observe", "classify", "touch"])
def test_reports_private_and_expurgated(tmp_path, monkeypatch, variant):
    engines = fake_runtime(monkeypatch)
    args = arguments(tmp_path, variant)
    assert tool.run(args) == 0
    summary = json.loads((args.output_dir / "summary.redacted.json").read_text())
    assert "SECRET" not in json.dumps(summary)
    assert "ts_rank_cd(" not in json.dumps(summary)
    assert "CASE WHEN" not in json.dumps(summary)
    assert (args.output_dir / "plan.private.json").exists() == (
        variant not in ("observe", "classify")
    )
    assert args.output_dir.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in args.output_dir.iterdir())
    for engine in engines:
        engine.dispose.assert_called_once()
        for tx in engine.raw.transactions:
            tx.rollback.assert_called_once()
    assert len(engines) == 2
    if variant == "observe":
        assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in engines[1].raw.calls)


def test_individual_timeout_persisted_and_not_retried(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch, cancel=True)
    args = arguments(tmp_path)
    assert tool.run(args) == 1
    summary = json.loads((args.output_dir / "summary.redacted.json").read_text())
    assert summary["runs"][0]["status"] == "timeout"
    assert sum(str(s).startswith(tool.p1.EXPLAIN) for s, _ in engines[1].raw.calls) == 1


def test_offline_comparison_reports_plan_and_parallel_changes(tmp_path, monkeypatch):
    fake_runtime(monkeypatch)
    first, second = arguments(tmp_path, "idf", "one"), arguments(tmp_path, "rank", "two")
    assert tool.run(first) == tool.run(second) == 0
    monkeypatch.setattr(tool, "load_settings", MagicMock(side_effect=AssertionError("secrets")))
    monkeypatch.setattr(tool, "create_search_engine", MagicMock(side_effect=AssertionError("SQL")))
    args = arguments(tmp_path, name="compare")
    args.compare = [first.output_dir, second.output_dir]
    assert tool.compare(args) == 0
    result = json.loads((args.output_dir / "comparison.redacted.json").read_text())
    pair = result["comparisons"][0]
    assert pair["controlled_conditions"]
    assert pair["same_parallelism"] and not pair["same_projection_placement"]
    assert pair["review_required"]
    rows = result["rows"]
    rows[1]["workers_launched"] = 0
    rows[1]["aggregation_sha256"] = "a" * 64
    rows[1]["access_sha256"] = "b" * 64
    pair = tool.comparison(rows)["comparisons"][0]
    assert (
        not pair["same_parallelism"]
        and not pair["same_aggregation"]
        and not pair["same_access_strategy"]
    )


def test_low_disk_no_first_connection(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch)
    monkeypatch.setattr(tool.p1.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    with pytest.raises(tool.base.Refused, match="low_disk_space"):
        tool.run(arguments(tmp_path))
    assert not engines


def test_output_limit_and_classification_never_accept_text(tmp_path):
    tmp_path.joinpath("storage").mkdir()
    storage = tool.p1.Storage(tmp_path / "storage", maximum=32 * tool.p1.MIB, minimum_free=0)
    with pytest.raises(tool.base.Refused, match="output_limit"):
        storage.write("plan.private.json", "x" * 100, limit=10)
    assert not list((tmp_path / "storage").iterdir())
    with pytest.raises(tool.base.Refused, match="classification_invalid"):
        tool.safe_classification(dict.fromkeys(tool.CLASSIFY_FIELDS, "SECRET"))
    observation = {
        "status": "ok",
        "values": {"SECRET": "SECRET", "storage": "SECRET", "toast_oid": 42},
    }
    assert "SECRET" not in json.dumps(tool.safe_observation("storage", observation))


def test_generation_change_fails_before_experiment():
    source, target = ComponentEngine(False), ComponentEngine(True)
    target.raw.state["chain_hash"] = "changed"
    payload, meta = tool.collect_case(source, target, "fiscal fraude", variant="full")
    assert meta["status"] == "error" and payload is None
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls)


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--execute", "--repeats", "3"],
        ["--execute", "--variant", "all"],
        ["--execute", "--statement-timeout-ms", "300001"],
        ["--execute", "--max-output-mib", "1"],
        ["--execute", "--case-deadline-seconds", "361"],
    ],
)
def test_cli_explicit_single_run_and_bounded_limits(tmp_path, extra):
    with pytest.raises(SystemExit) as error:
        tool.main(
            [
                "--variant",
                "full",
                "--query",
                "democratie-02",
                "--reader-env",
                "unused",
                "--queries",
                "unused",
                "--output-dir",
                str(tmp_path / "out"),
                *extra,
            ]
        )
    assert error.value.code == 2
    assert not (tmp_path / "out").exists()


def test_import_no_model_libraries():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts import components_h1_lexical as t; import sys; "
            "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules; t.verify_sources()",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
