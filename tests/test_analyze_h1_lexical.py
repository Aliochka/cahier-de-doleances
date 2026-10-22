"""Offline P1 tests. All database and network connections are forbidden."""

import json
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import psycopg2 as dialect
from sqlalchemy.exc import DBAPIError

from scripts import analyze_h1_lexical as tool
from scripts import explain_h1_lexical as base
from tests.test_explain_h1_lexical import PLAN, FakeEngine, FakeRaw, Result


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    import psycopg2

    def forbidden(*args, **kwargs):
        pytest.fail("No real database or network permitted in local tests")

    monkeypatch.setattr(psycopg2, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def measured_plan(jit=True):
    result = deepcopy(PLAN)
    root = result[0]
    root.update(
        {
            "Planning Time": 0.5,
            "Execution Time": 90.0,
            "Planning": {"Shared Hit Blocks": 4, "Shared Read Blocks": 0},
            "JIT": {
                "Functions": 12,
                "Options": {"Inlining": True, "Optimization": True},
                "Timing": {
                    "Generation": 1.0,
                    "Inlining": 2.0,
                    "Optimization": 3.0,
                    "Emission": 4.0,
                    "Total": 10.0,
                },
            },
        }
    )
    root["Plan"].update(
        {
            "Actual Startup Time": 80.0,
            "Actual Total Time": 85.0,
            "Actual Rows": 50,
            "Actual Loops": 1,
            "Shared Hit Blocks": 10,
            "Shared Read Blocks": 2,
            "Temp Read Blocks": 3,
            "Temp Written Blocks": 4,
        }
    )
    gather = root["Plan"]["Plans"][0]
    gather.update({"Workers Launched": 1, "Actual Loops": 1, "Actual Rows": 50})
    sort = gather["Plans"][0]
    sort.update(
        {
            "Actual Startup Time": 75.0,
            "Actual Total Time": 76.0,
            "Sort Method": "external merge",
            "Sort Space Type": "Disk",
            "Sort Space Used": 500,
            "Workers": [
                {
                    "Worker Number": 0,
                    "Actual Rows": 50,
                    "Actual Loops": 1,
                    "Sort Method": "top-N heapsort",
                    "Sort Space Type": "Memory",
                    "Sort Space Used": 30,
                    "JIT": deepcopy(root["JIT"]),
                }
            ],
        }
    )
    scan = sort["Plans"][0]
    scan.update(
        {
            "Actual Rows": 100,
            "Actual Loops": 2,
            "Actual Total Time": 70.0,
            "Rows Removed by Filter": 200,
            "Rows Removed by Index Recheck": 2,
            "Shared Hit Blocks": 10,
            "Shared Read Blocks": 2,
            "I/O Read Time": 0.75,
            "Temp I/O Read Time": 0.1,
            "Exact Heap Blocks": 20,
            "Lossy Heap Blocks": 1,
            "Workers": [
                {
                    "Worker Number": 0,
                    "Actual Rows": 90,
                    "Actual Loops": 1,
                    "Shared Read Blocks": 1,
                    "JIT": deepcopy(root["JIT"]),
                }
            ],
        }
    )
    if not jit:

        def remove(value):
            if isinstance(value, dict):
                value.pop("JIT", None)
                for nested in value.values():
                    remove(nested)
            elif isinstance(value, list):
                for nested in value:
                    remove(nested)

        remove(result)
    return result


class QueryCancelled(Exception):
    pgcode = "57014"


class MeasureRaw(FakeRaw):
    def __init__(self, target, *, cancel=False, default_jit="on", **kwargs):
        super().__init__(target, **kwargs)
        self.cancel, self.default_jit = cancel, default_jit
        self.jit = default_jit
        self.timeout, self.lock = "1000ms", "500ms"

    def begin(self):
        tx = super().begin()
        before = self.jit
        tx.rollback.side_effect = lambda: setattr(self, "jit", before)
        return tx

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if sql.startswith(tool.EXPLAIN):
            self.calls.append((statement, parameters))
            if self.cancel:
                raise DBAPIError(sql, {"SECRET": "PASSWORD"}, QueryCancelled("SECRET_CITIZEN"))
            return Result(measured_plan(self.jit == "on"))
        if sql.startswith("SELECT set_config("):
            self.calls.append((statement, parameters))
            if "'statement_timeout'" in sql:
                self.timeout = parameters["value"] + "ms"
            elif "'lock_timeout'" in sql:
                self.lock = parameters["value"] + "ms"
            elif "'jit'" in sql:
                self.jit = "off"
            else:
                pytest.fail("Unexpected GUC change")
            return Result(None)
        if "AS read_only" in sql:
            self.calls.append((statement, parameters))
            return Result(
                {
                    "read_only": self.readonly,
                    "statement_timeout": self.timeout,
                    "lock_timeout": self.lock,
                    "jit": self.jit,
                }
            )
        if "FROM pg_settings" in sql:
            self.calls.append((statement, parameters))
            return Result(
                [
                    ("jit", self.jit),
                    ("jit_above_cost", "100000"),
                    ("work_mem", "4096"),
                    ("track_io_timing", "off"),
                    ("temp_file_limit", "-1"),
                    ("server_version_num", "170011"),
                ]
            )
        return super().execute(statement, parameters)


class MeasureEngine(FakeEngine):
    def __init__(self, target, **kwargs):
        super().__init__(target)
        self.raw = MeasureRaw(target, **kwargs)


@pytest.mark.parametrize("case,query_id,mode", tool.INITIAL)
def test_five_exact_measurements_readonly_and_rollback(case, query_id, mode, monkeypatch):
    source, target = MeasureEngine(False), MeasureEngine(True)
    monkeypatch.setattr(TunedSearch, "_results", MagicMock(side_effect=AssertionError("hydration")))
    query = base.read_cases(Path("rag/evaluation/performance-rag027.json"))[query_id]
    original_prefix = base.EXPLAIN
    plan, metadata = tool.collect_case(source, target, query, mode=mode)
    assert metadata["status"] == "ok" and metadata["code"] == "none"
    assert base.EXPLAIN == original_prefix and "ANALYZE" not in base.EXPLAIN
    assert base.digest(Path(base.__file__).read_bytes()) == tool.BASE_TOOL_SHA
    TunedSearch._results.assert_not_called()
    ranking = [(s, p) for s, p in target.raw.calls if str(s).startswith(tool.EXPLAIN)]
    assert len(ranking) == 1
    assert ranking[0][1]["limit"] == 50
    assert metadata["effective_limits"]["jit"] == ("on" if mode == "current" else "off")
    assert 10000 < base.timeout_ms(metadata["effective_limits"]["statement_timeout"]) <= 60000
    assert metadata["settings_before"]["jit"] == "on"
    assert ("JIT" in plan[0]) == (mode == "current")
    assert target.raw.jit == "on"  # Rollback restored the transaction-local change.
    for engine in (source, target):
        for tx in engine.raw.transactions:
            tx.rollback.assert_called_once()
            tx.commit.assert_not_called()
        for sql, params in engine.raw.calls:
            sql = str(sql)
            assert "SET LOCAL statement_timeout='30s'" not in sql
            assert "record FROM" not in sql
            if "FROM rag_full.documents" in sql:
                assert sql.startswith(tool.EXPLAIN)
            if "set_config('jit'" in sql:
                assert engine is target and mode == "off" and "true" in sql
    assert all(t["read_only"] == "on" and t["rollback"] == "done" for t in metadata["transactions"])


def test_identical_sql_parameters_bind_types_and_driver_compilation():
    class RecordingWire:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            if str(statement).startswith("SELECT d.document_id,"):
                self.calls.append((statement, parameters.copy()))
                return Result([])
            if str(statement) == "SET LOCAL statement_timeout='30s'":
                return None
            return raw.execute(statement, parameters)

    raw = MeasureRaw(True)
    wire = RecordingWire()

    class Store:
        space = "full"

        def __init__(self):
            self.guard = self

        def state(self):
            return raw.state

        @contextmanager
        def transaction(self):
            yield wire, None

    TunedSearch(Store(), statistics=True, prefilter=None).lexical("fiscal fraude", limit=50)
    original, original_params = wire.calls[0]
    source, target = MeasureEngine(False), MeasureEngine(True)
    _, metadata = tool.collect_case(source, target, "fiscal fraude", mode="off")
    explained, params = next((s, p) for s, p in target.raw.calls if str(s).startswith(tool.EXPLAIN))
    assert metadata["status"] == "ok"
    assert str(explained) == tool.EXPLAIN + str(original)
    assert original_params == params
    assert {k: type(v) for k, v in original_params.items()} == {
        k: type(v) for k, v in params.items()
    }
    compiler = dialect.dialect()
    assert str(explained.compile(dialect=compiler)) == tool.EXPLAIN + str(
        original.compile(dialect=compiler)
    )
    assert {k: type(v.type) for k, v in original._bindparams.items()} == {
        k: type(v.type) for k, v in explained._bindparams.items()
    }
    assert params["idf_coverage"] == 0.5 and params["term_coverage"] == 0.3
    assert params["frequency_proximity"] == 0.2
    assert all(params[k] is None for k in ("form", "kind", "split"))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT d.document_id,1 AS score FROM rag_full.documents d LIMIT 50",
        "SELECT count(*) FROM rag_full.documents_full",
        "SELECT record FROM rag_full.documents",
        "EXPLAIN ANALYZE SELECT * FROM rag_full.documents",
        "DELETE FROM rag_full.documents",
        "SET jit=off",
        "SET LOCAL statement_timeout='30s'",
    ],
)
def test_only_expected_call_can_execute_rank(sql):
    wire = MagicMock()
    guard = SimpleNamespace(halted=False, allowed=base.preparation_allowlist())
    connection = tool.AnalyzeConnection(wire, guard, target=True)
    with pytest.raises(base.Refused):
        connection.execute(text(sql))
    wire.execute.assert_not_called()


def test_changed_ranking_template_refused_before_execution(monkeypatch):
    monkeypatch.setitem(TunedSearch.lexical.__globals__, "FILTERS", "true")
    source, target = MeasureEngine(False), MeasureEngine(True)
    _, metadata = tool.collect_case(source, target, "fiscal fraude", mode="current")
    assert metadata["code"] == "unexpected_ranking"
    assert not any(str(s).startswith(tool.EXPLAIN) for s, _ in target.raw.calls)


@pytest.mark.parametrize(
    "settings", [{"readonly": "off"}, {"unsafe": True}, {"default_jit": "off"}]
)
def test_unsafe_connection_or_unexpected_current_jit_never_executes(settings):
    source, target = MeasureEngine(False), MeasureEngine(True, **settings)
    _, metadata = tool.collect_case(source, target, "fiscal fraude", mode="current")
    assert metadata["status"] == "error"
    assert not any(str(s).startswith(tool.EXPLAIN) for s, _ in target.raw.calls)
    for tx in target.raw.transactions:
        tx.rollback.assert_called_once()


def test_timeout_is_recorded_without_retry_or_leaking_exception():
    source, target = MeasureEngine(False), MeasureEngine(True, cancel=True)
    plan, metadata = tool.collect_case(source, target, "fiscal fraude", mode="current")
    assert plan is None and metadata["status"] == "timeout"
    assert metadata["code"] == "statement_timeout" and metadata["stage"] == "ranking"
    assert "SECRET" not in json.dumps(metadata)
    assert sum(str(s).startswith(tool.EXPLAIN) for s, _ in target.raw.calls) == 1
    for tx in target.raw.transactions:
        tx.rollback.assert_called_once()


def test_metrics_jit_workers_buffers_inclusive_times_and_privacy():
    summary = tool.summarize(measured_plan())
    assert summary["execution_ms"] == 90 and summary["planning_ms"] == 0.5
    assert summary["jit"]["Timing"] == {
        "Generation": 1,
        "Inlining": 2,
        "Optimization": 3,
        "Emission": 4,
        "Total": 10,
    }
    assert summary["shared_read_blocks"] == 2  # Not 4 after adding child counters.
    assert summary["workers_planned"] == 2 and summary["workers_launched"] == 1
    assert summary["candidate_rows_approx"] == 200
    scan = summary["nodes"][3]
    assert scan["Actual Loops"] == 2 and scan["I/O Read Time"] == 0.75
    assert scan["workers"][0]["jit"]["Timing"]["Total"] == 10
    assert summary["nodes"][2]["Sort Space Type"] == "Disk"
    assert summary["nodes"][2]["workers"][0]["Sort Space Type"] == "Memory"
    assert "SECRET" not in json.dumps(summary)
    assert "ts_rank_cd" not in json.dumps(summary)


def test_structure_comparison_ignores_runtime_and_jit_but_detects_scan_change():
    current = tool.summarize(measured_plan())
    off = tool.summarize(measured_plan(False))
    assert current["structure_sha256"] == off["structure_sha256"]
    changed = measured_plan(False)
    changed[0]["Plan"]["Plans"][0]["Plans"][0]["Plans"][0]["Node Type"] = "Seq Scan"
    assert current["structure_sha256"] != tool.summarize(changed)["structure_sha256"]


def test_schedules_are_explicit_and_alternating_not_automatic_retries():
    initial = tool.schedule("initial", 1, False)
    assert [r["case"] for r in initial] == list(tool.CASES)
    assert len(tool.schedule("democratie-02-off", 1, False)) == 1
    alternating = tool.schedule("democratie-pair", 3, True)
    assert [r["jit_mode"] for r in alternating] == [
        "current",
        "off",
        "off",
        "current",
        "current",
        "off",
    ]
    with pytest.raises(base.Refused):
        tool.schedule("democratie-02-off", 1, True)


def args(tmp_path, case="democratie-pair", name="run"):
    return SimpleNamespace(
        case=case,
        repeats=1,
        alternate_jit_order=False,
        queries=Path("rag/evaluation/performance-rag027.json"),
        reader_env=Path("unused"),
        output_dir=tmp_path / name,
        statement_timeout_ms=60000,
        lock_timeout_ms=200,
        case_deadline_seconds=90,
        max_output_mib=64,
        min_free_mib=64,
    )


def fake_runtime(monkeypatch, *, cancel=False):
    engines = []

    def create(url):
        engine = MeasureEngine(url == "target", cancel=cancel)
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


def test_run_files_permissions_table_and_pair_comparison(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch)
    arguments = args(tmp_path)
    assert tool.run(arguments) == 0
    summary = json.loads((arguments.output_dir / "summary.redacted.json").read_text())
    assert [r["status"] for r in summary["runs"]] == ["ok", "ok"]
    assert "SECRET" not in json.dumps(summary)
    comparison = json.loads((arguments.output_dir / "comparison.redacted.json").read_text())
    assert comparison["comparisons"] == [
        {"rows": [0, 1], "comparable": True, "structure_equal": True, "estimates_equal": True}
    ]
    assert "execution_ms" in comparison["table_markdown"]
    assert arguments.output_dir.stat().st_mode & 0o777 == 0o700
    assert len(list(arguments.output_dir.glob("*.json"))) == 7
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in arguments.output_dir.glob("*.json"))
    assert any("SECRET" in p.read_text() for p in arguments.output_dir.glob("*.plan.private.json"))
    for engine in engines:
        engine.dispose.assert_called_once()


def test_timeout_output_is_explicit_no_plan_and_no_retry(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch, cancel=True)
    arguments = args(tmp_path, "fiscalite-01-current")
    assert tool.run(arguments) == 1
    summary = json.loads((arguments.output_dir / "summary.redacted.json").read_text())
    assert summary["runs"][0]["status"] == "timeout"
    assert "SECRET" not in json.dumps(summary)
    assert not list(arguments.output_dir.glob("*.plan.private.json"))
    assert sum(str(s).startswith(tool.EXPLAIN) for e in engines for s, _ in e.raw.calls) == 1


def test_storage_checks_quota_free_space_and_plan_size(tmp_path, monkeypatch):
    storage = tool.Storage(tmp_path, maximum=64 * tool.MIB, minimum_free=0)
    storage.sizes["old"] = 40 * tool.MIB
    with pytest.raises(base.Refused, match="storage_limit"):
        storage.check_measurement()
    storage.sizes.clear()
    monkeypatch.setattr(tool.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    with pytest.raises(base.Refused, match="low_disk_space"):
        storage.check_measurement()
    with pytest.raises(base.Refused, match="plan_too_large"):
        storage.write("oversize.json", "X" * tool.PLAN_LIMIT, limit=tool.PLAN_LIMIT)
    assert not list(tmp_path.iterdir())


def test_disk_refusal_happens_before_any_database_call(tmp_path, monkeypatch):
    engines = fake_runtime(monkeypatch)
    monkeypatch.setattr(tool.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    with pytest.raises(base.Refused, match="low_disk_space"):
        tool.run(args(tmp_path))
    assert not engines


def test_shared_parent_lock_and_existing_output_refused(tmp_path):
    with tool.exclusive_output(tmp_path / "one"):
        with pytest.raises(base.Refused, match="another_collection_running"):
            with tool.exclusive_output(tmp_path / "two"):
                pytest.fail("Concurrent execution")
    with pytest.raises(FileExistsError):
        with tool.exclusive_output(tmp_path / "one"):
            pytest.fail("Existing output reused")


def test_offline_comparison_never_uses_credentials_or_database(tmp_path, monkeypatch):
    fake_runtime(monkeypatch)
    current = args(tmp_path, "democratie-02-current", "current")
    off = args(tmp_path, "democratie-02-off", "off")
    assert tool.run(current) == tool.run(off) == 0
    monkeypatch.setattr(tool, "load_settings", MagicMock(side_effect=AssertionError("credentials")))
    monkeypatch.setattr(tool, "create_search_engine", MagicMock(side_effect=AssertionError("DB")))
    compare = args(tmp_path, name="comparison")
    compare.compare = [current.output_dir, off.output_dir]
    assert tool.compare(compare) == 0
    report = json.loads((compare.output_dir / "comparison.redacted.json").read_text())
    assert report["comparisons"][0]["comparable"] is True
    tool.create_search_engine.assert_not_called()
    tool.load_settings.assert_not_called()


@pytest.mark.parametrize(
    "option,value",
    [
        ("--statement-timeout-ms", "300001"),
        ("--case-deadline-seconds", "361"),
        ("--lock-timeout-ms", "1001"),
        ("--repeats", "21"),
        ("--max-output-mib", "257"),
        ("--min-free-mib", "0"),
    ],
)
def test_cli_bounds_before_execution(option, value, tmp_path):
    with pytest.raises(SystemExit) as error:
        tool.main(
            [
                "--execute",
                "--case",
                "fiscalite-05-current",
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
    assert not (tmp_path / "out").exists()


def test_explicit_execution_required(tmp_path):
    with pytest.raises(SystemExit) as error:
        tool.main(["--case", "initial", "--output-dir", str(tmp_path / "out")])
    assert error.value.code == 2


def test_import_does_not_load_models_or_change_nonexecuting_tool():
    script = """from scripts import analyze_h1_lexical as a
import sys
assert 'torch' not in sys.modules and 'transformers' not in sys.modules
assert a.base.EXPLAIN == 'EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON) '
a.verify_sources()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("change", ["jit", "work_mem"])
def test_effective_jit_and_unchanged_other_settings_are_checked(change):
    source, target = MeasureEngine(False), MeasureEngine(True)
    execute = target.raw.execute

    def wrong(statement, parameters=None):
        result = execute(statement, parameters)
        if "set_config('jit'" in str(statement) and change == "jit":
            target.raw.jit = "on"
        if (
            "FROM pg_settings" in str(statement)
            and change == "work_mem"
            and target.raw.jit == "off"
        ):
            result.value = [(k, "8192" if k == "work_mem" else v) for k, v in result.value]
        return result

    target.raw.execute = wrong
    _, metadata = tool.collect_case(source, target, "fiscal fraude", mode="off")
    assert metadata["code"] == (
        "jit_setting_mismatch" if change == "jit" else "settings_changed_beyond_jit"
    )
    assert not any(str(s).startswith(tool.EXPLAIN) for s, _ in target.raw.calls)


def test_analyze_wire_respects_residual_case_deadline():
    from cahier_rag.search.service.control import Budget, SearchTimeout

    now = [0.0]
    budget = Budget(90, clock=lambda: now[0])
    raw = MeasureRaw(True)
    wire = tool.AnalyzeWire(raw, budget, 60000, 200)
    now[0] = 89.5
    wire.execute(text("SELECT set_config('lock_timeout', :value, true)"), {"value": "200"})
    assert wire.last_timeout_ms == 500
    now[0] = 91
    before = len(raw.calls)
    with pytest.raises(SearchTimeout):
        wire.execute(text("SELECT 1"))
    assert len(raw.calls) == before


def test_unexpected_io_keys_and_strings_not_exported():
    plan = measured_plan()
    plan[0]["Plan"]["Secret Label"] = "PERSONAL_DATA"
    plan[0]["Plan"]["Actual Total Time"] = "SECRET_VALUE"
    plan[0]["JIT"]["Timing"]["Injected"] = "PASSWORD"
    summary = tool.summarize(plan)
    assert all(
        token not in json.dumps(summary) for token in ("PERSONAL_DATA", "SECRET_VALUE", "PASSWORD")
    )
