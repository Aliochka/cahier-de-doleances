"""Offline P2 validation. No real PostgreSQL, network, model or experiment."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import psycopg2

from scripts import decompose_h1_lexical as tool
from tests.test_analyze_h1_lexical import MeasureEngine, MeasureRaw, measured_plan
from tests.test_explain_h1_lexical import Result


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    import psycopg2 as driver

    def forbidden(*args, **kwargs):
        pytest.fail("P2 local tests must not open a socket or database")

    monkeypatch.setattr(driver, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


class P2Raw(MeasureRaw):
    def __init__(self, target, *, memory=4, can_io=False, **kwargs):
        super().__init__(target, **kwargs)
        self.work_bytes = memory * tool.p1.MIB
        self.io = "off"
        self.can_io = can_io

    def begin(self):
        before_mem, before_io = self.work_bytes, self.io
        tx = super().begin()
        restore_jit = tx.rollback.side_effect

        def restore():
            restore_jit()
            self.work_bytes, self.io = before_mem, before_io

        tx.rollback.side_effect = restore
        return tx

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if sql == tool.CONTROL_SQL:
            self.calls.append((statement, parameters))
            return Result(
                {
                    "work_mem": f"{self.work_bytes // tool.p1.MIB}MB",
                    "work_mem_bytes": self.work_bytes,
                    "track_io_timing": self.io,
                    "can_set_io": self.can_io,
                }
            )
        if "set_config('work_mem'" in sql:
            self.calls.append((statement, parameters))
            self.work_bytes = int(parameters["value"][:-2]) * tool.p1.MIB
            return Result(None)
        if "set_config('track_io_timing'" in sql:
            assert self.can_io, "No privilege escalation or unauthorized SET allowed"
            self.calls.append((statement, parameters))
            self.io = "on"
            return Result(None)
        result = super().execute(statement, parameters)
        if "FROM pg_settings" in sql:
            result.value = [
                (
                    k,
                    str(self.work_bytes // 1024)
                    if k == "work_mem"
                    else self.io
                    if k == "track_io_timing"
                    else v,
                )
                for k, v in result.value
            ]
        return result


class P2Engine(MeasureEngine):
    def __init__(self, target, **kwargs):
        super().__init__(target)
        self.raw = P2Raw(target, **kwargs)


def collect(axis, variant, **kwargs):
    source, target = P2Engine(False), P2Engine(True, **kwargs)
    plan, metadata = tool.collect_case(source, target, "fiscal fraude", axis=axis, variant=variant)
    return source, target, plan, metadata


def test_source_fingerprints_verify_existing_tools_unchanged():
    tool.verify_sources()
    assert tool.base.digest(Path(tool.p1.__file__).read_bytes()) == tool.P1_SHA
    assert tool.base.EXPLAIN == "EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON) "


@pytest.mark.parametrize("variant", tool.COSTS)
def test_derived_sql_preserves_where_and_score_but_is_labelled_diagnostic(variant, monkeypatch):
    monkeypatch.setattr(TunedSearch, "_results", MagicMock(side_effect=AssertionError("hydration")))
    source, target, plan, metadata = collect("costs", variant)
    assert metadata["status"] == "ok"
    original, measured = metadata["h1_sql_template"], metadata["measured_sql_template"]
    predicate = original.split("FROM rag_full.documents d", 1)[1].split("ORDER BY", 1)[0].strip()
    assert predicate in measured
    statements = [(s, p) for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN)]
    assert len(statements) == 1
    sql, parameters = statements[0]
    assert parameters["limit"] == 50
    assert [parameters[k] for k in ("idf_coverage", "term_coverage", "frequency_proximity")] == [
        0.5,
        0.3,
        0.2,
    ]
    if variant == "top50":
        assert measured == original
        assert metadata["h1_sql_sha256"] == metadata["sql_sha256"]
        assert "LIMIT :limit" in measured
    else:
        assert metadata["h1_sql_sha256"] != metadata["sql_sha256"]
        assert "ORDER BY" not in measured and "LIMIT" not in measured
    if variant in ("filter", "filter-stream"):
        assert "ts_rank_cd" not in measured
    if variant == "score":
        assert "sum((:idf_coverage" in measured and "ts_rank_cd" in measured
    if variant == "filter":
        assert measured.startswith("SELECT count(*) AS matched")
    assert str(sql).startswith(tool.p1.EXPLAIN)
    for engine in (source, target):
        for tx in engine.raw.transactions:
            tx.rollback.assert_called_once()
            tx.commit.assert_not_called()
        assert engine.raw.work_bytes == 4 * tool.p1.MIB
        for stmt, _ in engine.raw.calls:
            if "FROM rag_full.documents" in str(stmt):
                assert str(stmt).startswith(tool.p1.EXPLAIN)
    TunedSearch._results.assert_not_called()


@pytest.mark.parametrize(
    "variant,memory", [("4MB", 4), ("16MB", 16), ("64MB", 64), ("current", 12)]
)
def test_memory_uses_exact_h1_sql_and_values_with_actual_reader_setting(variant, memory):
    _, target, _, metadata = collect("work-mem", variant, memory=12)
    assert metadata["status"] == "ok"
    assert metadata["controls_before"]["work_mem_bytes"] == 12 * tool.p1.MIB
    assert metadata["controls_after"]["work_mem_bytes"] == memory * tool.p1.MIB
    assert metadata["h1_sql_template"] == metadata["measured_sql_template"]
    assert metadata["sql_sha256"] == metadata["h1_sql_sha256"]
    explained, parameters = next(
        (s, p) for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN)
    )
    original = text(metadata["h1_sql_template"])
    dialect = psycopg2.dialect()
    assert str(explained.compile(dialect=dialect)) == tool.p1.EXPLAIN + str(
        original.compile(dialect=dialect)
    )
    assert explained.compile(dialect=dialect).construct_params(parameters) == original.compile(
        dialect=dialect
    ).construct_params(parameters)
    assert {k: type(v.type) for k, v in original._bindparams.items()} == {
        k: type(v.type) for k, v in explained._bindparams.items()
    }
    assert target.raw.work_bytes == 12 * tool.p1.MIB  # rollback restores original setting


def test_observe_records_reader_context_without_executing_ranking():
    _, target, plan, metadata = collect("work-mem", "observe", memory=12)
    assert metadata["status"] == "observed" and plan is None
    assert metadata["controls_before"]["work_mem_bytes"] == 12 * tool.p1.MIB
    assert metadata["controls_before"]["can_set_io"] is False
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls)
    assert not any("set_config('work_mem'" in str(s) for s, _ in target.raw.calls)


@pytest.mark.parametrize(
    "permitted,policy,enabled",
    [
        (False, "observe", False),
        (True, "observe", False),
        (False, "if-permitted", False),
        (True, "if-permitted", True),
    ],
)
def test_io_policy_never_sets_without_existing_privilege_or_opt_in(permitted, policy, enabled):
    source, target = P2Engine(False), P2Engine(True, can_io=permitted)
    _, metadata = tool.collect_case(
        source, target, "fiscal fraude", axis="costs", variant="top50", io_policy=policy
    )
    assert metadata["status"] == "ok"
    assert metadata["controls_after"]["track_io_timing"] == ("on" if enabled else "off")
    assert sum("set_config('track_io_timing'" in str(s) for s, _ in target.raw.calls) == int(
        enabled
    )
    assert target.raw.io == "off"
    if not permitted:
        assert metadata["io_timing_reason"] == "no_existing_set_privilege"


def test_unknown_sql_and_arbitrary_count_never_reach_transport():
    wire = MagicMock()
    guard = SimpleNamespace(halted=False, allowed=tool.base.preparation_allowlist())
    connection = tool.ExperimentConnection(wire, guard, target=True)
    for sql in (
        "SELECT count(*) FROM rag_full.documents",
        "SET work_mem='64MB'",
        "DELETE FROM rag_full.documents",
    ):
        with pytest.raises(tool.base.Refused):
            connection.execute(text(sql))
    wire.execute.assert_not_called()


@pytest.mark.parametrize("settings", [{"readonly": "off"}, {"unsafe": True}])
def test_reader_guards_rollback_on_refusal(settings):
    _, target, plan, metadata = collect("costs", "score", **settings)
    assert metadata["status"] == "error" and plan is None
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls)
    for tx in target.raw.transactions:
        tx.rollback.assert_called_once()


def test_timeout_no_retry_or_hydration():
    _, target, plan, metadata = collect("costs", "score", cancel=True)
    assert metadata["status"] == "timeout" and plan is None
    assert "SECRET" not in json.dumps(metadata)
    assert sum(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls) == 1
    assert all(t["rollback"] == "done" for t in metadata["transactions"])


def test_bitmap_metrics_are_not_double_counted_and_expressions_are_redacted():
    plan = measured_plan()
    scan = plan[0]["Plan"]["Plans"][0]["Plans"][0]["Plans"][0]
    scan["Output"] = ["ts_rank_cd(search_vector, 'SECRET'::tsquery)"]
    summary = tool.summarize(plan)
    assert summary["exact_heap_blocks"] == 20 and summary["lossy_heap_blocks"] == 1
    assert summary["recheck_rows_removed_approx"] == 4  # two rows * two loops
    assert summary["shared_read_blocks"] == 2
    assert summary["nodes"][3]["score_in_output"] is True
    assert "SECRET" not in json.dumps(summary)


def test_balanced_schedules_rotate_and_label_derived_experiments():
    records = tool.schedule("costs", "all", "democratie-02", 3, True)
    assert [r["variant"] for r in records] == [
        "filter",
        "score",
        "top50",
        "score",
        "top50",
        "filter",
        "top50",
        "filter",
        "score",
    ]
    assert [r["diagnostic_derived"] for r in records[:3]] == [True, True, False]
    memory = tool.schedule("work-mem", "all", "fiscalite-05", 3, True)
    assert [r["variant"] for r in memory][3:6] == ["16MB", "64MB", "4MB"]
    with pytest.raises(tool.base.Refused):
        tool.schedule("work-mem", "all", "fiscalite-01", 1, False)


def arguments(tmp_path, axis="work-mem", variant="all", name="out"):
    return SimpleNamespace(
        axis=axis,
        variant=variant,
        query="fiscalite-05",
        repeats=1,
        alternate=False,
        jit="current",
        io_timing="observe",
        reader_env=Path("unused"),
        queries=Path("rag/evaluation/performance-rag027.json"),
        output_dir=tmp_path / name,
        statement_timeout_ms=60000,
        case_deadline_seconds=90,
        lock_timeout_ms=200,
        max_output_mib=64,
        min_free_mib=64,
    )


def fake_runtime(monkeypatch):
    engines = []

    def create(url):
        engine = P2Engine(url == "target")
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


def test_reports_and_exact_sql_memory_comparison(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch)
    args = arguments(tmp_path)
    assert tool.run(args) == 0
    report = json.loads((args.output_dir / "comparison.redacted.json").read_text())
    assert len(report["rows"]) == 3 and len(report["comparisons"]) == 3
    assert all(r["controlled_conditions"] for r in report["comparisons"])
    summary = json.loads((args.output_dir / "summary.redacted.json").read_text())
    assert "SECRET" not in json.dumps(summary)
    assert summary["runs"][2]["work_mem_effective_bytes"] == 64 * tool.p1.MIB
    assert args.output_dir.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in args.output_dir.iterdir())
    assert len(list(args.output_dir.glob("*.plan.private.json"))) == 3
    for engine in engines:
        engine.dispose.assert_called_once()


def test_diagnostic_comparison_never_calls_difference_exact_cost(tmp_path, monkeypatch):
    fake_runtime(monkeypatch)
    args = arguments(tmp_path, "costs", "all")
    assert tool.run(args) == 0
    report = json.loads((args.output_dir / "comparison.redacted.json").read_text())
    assert len({r["sql_sha256"] for r in report["rows"]}) == 3
    assert all(
        r["interpretation"] == "observed_difference_not_exact_operation_cost"
        for r in report["comparisons"]
    )


def test_offline_comparison_does_not_read_credentials_or_query_database(tmp_path, monkeypatch):
    fake_runtime(monkeypatch)
    args = arguments(tmp_path)
    assert tool.run(args) == 0
    monkeypatch.setattr(tool, "load_settings", MagicMock(side_effect=AssertionError("credentials")))
    monkeypatch.setattr(tool, "create_search_engine", MagicMock(side_effect=AssertionError("SQL")))
    comparison = arguments(tmp_path, name="compare")
    comparison.compare = [args.output_dir]
    assert tool.compare(comparison) == 0
    tool.create_search_engine.assert_not_called()
    tool.load_settings.assert_not_called()


def test_low_space_prevents_even_first_connection(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch)
    monkeypatch.setattr(tool.p1.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    with pytest.raises(tool.base.Refused, match="low_disk_space"):
        tool.run(arguments(tmp_path))
    assert not engines


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--execute", "--statement-timeout-ms", "300001"],
        ["--execute", "--case-deadline-seconds", "361"],
        ["--execute", "--repeats", "21"],
    ],
)
def test_cli_requires_authorization_and_bounded_limits(tmp_path, extra):
    with pytest.raises(SystemExit) as result:
        tool.main(
            [
                "--axis",
                "costs",
                "--query",
                "fiscalite-01",
                "--variant",
                "score",
                "--reader-env",
                "unused",
                "--queries",
                "unused",
                "--output-dir",
                str(tmp_path / "out"),
                *extra,
            ]
        )
    assert result.value.code == 2
    assert not (tmp_path / "out").exists()


def test_setting_not_applied_refused_before_documentary_execution():
    source, target = P2Engine(False), P2Engine(True)
    execute = target.raw.execute

    def ignored(statement, parameters=None):
        before = target.raw.work_bytes
        result = execute(statement, parameters)
        if "set_config('work_mem'" in str(statement):
            target.raw.work_bytes = before
        return result

    target.raw.execute = ignored
    _, metadata = tool.collect_case(
        source, target, "fiscal fraude", axis="work-mem", variant="16MB"
    )
    assert metadata["code"] == "experiment_setting_mismatch"
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, _ in target.raw.calls)


def test_jit_off_stays_constant_across_derived_variants(tmp_path, monkeypatch):
    fake_runtime(monkeypatch)
    args = arguments(tmp_path, "costs", "all")
    args.jit = "off"
    assert tool.run(args) == 0
    summary = json.loads((args.output_dir / "summary.redacted.json").read_text())
    assert all(r["effective_jit"] == "off" and not r["jit"]["present"] for r in summary["runs"])


def test_fresh_import_does_not_load_model_libraries():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts import decompose_h1_lexical as p; "
            "import sys; assert 'torch' not in sys.modules; "
            "assert 'transformers' not in sys.modules; p.verify_sources()",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
