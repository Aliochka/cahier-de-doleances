"""Offline P5 tests. No PostgreSQL, SSH, socket or model initialization."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import psycopg2

from scripts import compare_h1_rank as tool
from tests.test_analyze_h1_lexical import MeasureEngine, MeasureRaw


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    import psycopg2 as driver

    def forbidden(*args, **kwargs):
        pytest.fail("No real database or network in P5 tests")

    monkeypatch.setattr(driver, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(TunedSearch, "_results", forbidden)


def collect(variant="original", **kwargs):
    source, target = MeasureEngine(False), MeasureEngine(True, **kwargs)
    plan, meta = tool.collect_case(source, target, "fiscal fraude", variant=variant)
    return source, target, plan, meta


def test_pinned_sources_and_plan_without_connections(capsys):
    tool.verify_sources()
    assert tool.main(["plan", "--query", "democratie-02"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["executed"] is False
    assert len(payload["schedule"]) == 10


@pytest.mark.parametrize("jit", ["on", "off"])
@pytest.mark.parametrize("variant", tool.VARIANTS)
def test_read_only_rollback_no_planner_setting_changes_and_exact_substitution(variant, jit):
    source, target, plan, meta = collect(variant, default_jit=jit)
    assert meta["status"] == "ok" and plan
    assert all(t["rollback"] == "done" and t["read_only"] == "on" for t in meta["transactions"])
    assert meta["settings_before"] == meta["settings_effective"]
    assert meta["settings_effective"]["jit"] == jit
    assert meta["effective_limits"]["read_only"] == "on"
    assert 0 < meta["ranking_statement_timeout_ms"] <= 60000
    emitted, params = next(
        (s, p) for s, p in target.raw.calls if str(s).startswith(tool.p1.EXPLAIN)
    )
    original = meta["h1_sql_template"]
    expected = original if variant == "original" else original.replace("ts_rank_cd(", "ts_rank(")
    assert str(emitted) == tool.p1.EXPLAIN + expected
    dialect = psycopg2.dialect()
    assert emitted.compile(dialect=dialect).construct_params(params) == text(original).compile(
        dialect=dialect
    ).construct_params(params)
    assert {k: type(v.type) for k, v in emitted._bindparams.items()} == {
        k: type(v.type) for k, v in text(original)._bindparams.items()
    }
    assert params["frequency_proximity"] == 0.2
    for engine in (source, target):
        for stmt, values in engine.raw.calls:
            sql = str(stmt)
            if "set_config(" in sql:
                assert "'statement_timeout'" in sql or "'lock_timeout'" in sql
            assert "SET LOCAL statement_timeout='30s'" != sql
        assert all(tx.rollback.called for tx in engine.raw.transactions)


def test_unknown_sql_variants_and_recomposition_refused():
    _, _, _, meta = collect()
    original = meta["h1_sql_template"]
    # Complete template rejected before any driver call.
    with pytest.raises(tool.base.Refused):
        tool.diagnostic_sql(original + " LIMIT 1", "bad", [], {}, "ts_rank")
    with pytest.raises(tool.base.Refused):
        tool.collect_case(None, None, "x", variant="arbitrary")


def test_statement_timeout_has_no_fabricated_plan_and_rolls_back():
    source, target, plan, meta = collect("ts_rank", cancel=True)
    assert plan is None and meta["status"] == "timeout" and meta["code"] == "statement_timeout"
    assert meta["stage"] == "ranking"
    assert meta["ranking_client_seconds"] >= 0
    assert all(t["rollback"] == "done" for t in meta["transactions"])
    assert "SECRET" not in json.dumps({k: meta[k] for k in ("code", "status")})


def test_schedule_balanced_and_warmup_excluded():
    rows = tool.schedule("fiscalite-01", 4, 1)
    assert [(r["variant"], r["pair"]) for r in rows if r["phase"] == "measure"] == [
        ("original", 1),
        ("ts_rank", 1),
        ("ts_rank", 2),
        ("original", 2),
        ("original", 3),
        ("ts_rank", 3),
        ("ts_rank", 4),
        ("original", 4),
    ]
    report = tool.comparison(rows)
    assert report["groups"]["original"]["scheduled"] == 4
    assert report["paired"]["n"] == 0


def successful_rows():
    rows = tool.schedule("democratie-02", 2, 0)
    for row in rows:
        row.update(
            status="ok",
            execution_ms=100 if row["variant"] == "original" else 60,
            workers_planned=2,
            workers_launched=2,
            access_sha256="b" * 64,
        )
        row.update({key: "a" * 64 for key in tool.HASHES})
    return rows


def test_paired_gains_and_timeouts_not_counted_as_fast_successes():
    rows = successful_rows()
    report = tool.comparison(rows)
    assert report["paired"]["median_gain_percent"] == 40
    assert report["paired"]["n"] == 2
    rows[2].update(status="timeout", execution_ms=None)
    report = tool.comparison(rows)
    assert report["paired"]["n"] == 1
    assert report["groups"]["ts_rank"]["timeout"] == 1
    assert report["groups"]["ts_rank"]["successful_execution_ms"]["n"] == 1
    rows[1]["settings_control_sha256"] = "c" * 64
    assert tool.comparison(rows)["paired"]["n"] == 0


def test_redaction_uses_positive_projection_and_no_sql_or_secret():
    rows = successful_rows()
    for r in rows:
        r.update(Output="SECRET_CITIZEN", sql="PASSWORD", code="SECRET_ERROR", unexpected="SECRET")
    encoded = json.dumps(tool.comparison(rows)) + tool.markdown(tool.comparison(rows))
    assert "SECRET" not in encoded and "PASSWORD" not in encoded
    _, _, plan, _ = collect()
    plan[0]["Plan"]["Output"] = ["SECRET_CITIZEN"]
    assert "SECRET" not in json.dumps(tool.p2.summarize(plan))


def test_setting_drift_refused(monkeypatch):
    original = MeasureRaw.execute
    count = 0

    def changed(self, stmt, params=None):
        nonlocal count
        result = original(self, stmt, params)
        if self.target and "FROM pg_settings" in str(stmt):
            count += 1
            if count == 2:
                result.value = [(k, "9999" if k == "work_mem" else v) for k, v in result.value]
        return result

    monkeypatch.setattr(MeasureRaw, "execute", changed)
    _, _, plan, meta = collect()
    assert plan is None and meta["code"] == "settings_changed"


def test_run_requires_explicit_execute_flag():
    with pytest.raises(SystemExit):
        tool.main(
            ["run", "--query", "democratie-02", "--reader-env", "unused", "--output-dir", "unused"]
        )


def test_campaign_continues_scheduled_pairs_after_timeout_but_stops_on_error(tmp_path, monkeypatch):
    def campaign(error):
        engines = [MagicMock(), MagicMock()]
        monkeypatch.setattr(
            tool,
            "load_settings",
            lambda **kw: SimpleNamespace(
                require_source_url=lambda: "s", require_rag_url=lambda: "t"
            ),
        )
        monkeypatch.setattr(
            tool, "create_search_engine", lambda url: engines[0] if url == "s" else engines[1]
        )
        calls = []

        def measured(*args, **kwargs):
            calls.append(kwargs["variant"])
            if len(calls) == 1:
                return None, {
                    "status": error,
                    "code": "statement_timeout" if error == "timeout" else "database_error",
                    "elapsed_seconds": 1,
                }
            return None, {"status": "ok", "code": "none", "elapsed_seconds": 1}

        monkeypatch.setattr(tool, "collect_case", measured)
        out = tmp_path / error
        assert (
            tool.main(
                [
                    "run",
                    "--execute",
                    "--query",
                    "democratie-02",
                    "--reader-env",
                    "unused",
                    "--output-dir",
                    str(out),
                    "--warmups",
                    "0",
                    "--repeats",
                    "2",
                    "--min-free-mib",
                    "64",
                ]
            )
            == 1
        )
        report = json.loads((out / "comparison.redacted.json").read_text())
        assert out.stat().st_mode & 0o777 == 0o700
        assert all(p.stat().st_mode & 0o777 == 0o600 for p in out.iterdir())
        return calls, report

    calls, report = campaign("timeout")
    assert len(calls) == 4
    calls, report = campaign("error")
    assert len(calls) == 1
    assert sum(r["status"] == "skipped" for r in report["runs"]) == 3


@pytest.mark.parametrize("options", [{"unsafe": True}, {"readonly": "off"}])
def test_reader_or_readonly_refusal_before_ranking(options):
    _, target, plan, meta = collect(**options)
    assert meta["status"] == "error" and plan is None
    assert not any(str(s).startswith(tool.p1.EXPLAIN) for s, p in target.raw.calls)
    assert all(t["rollback"] == "done" for t in meta["transactions"])


def test_sql_outside_real_pinned_caller_refused():
    wire = MagicMock()
    guard = SimpleNamespace(halted=False, allowed=tool.base.preparation_allowlist())
    connection = tool.RankConnection(wire, guard, target=True)
    with pytest.raises(tool.base.Refused):
        connection.execute(
            text("SELECT ts_rank(search_vector, 'secret'::tsquery,32) FROM rag_full.documents")
        )
    wire.execute.assert_not_called()


def test_low_disk_refused_before_any_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tool,
        "load_settings",
        lambda **kw: SimpleNamespace(require_source_url=lambda: "s", require_rag_url=lambda: "t"),
    )
    factory = MagicMock()
    monkeypatch.setattr(tool, "create_search_engine", factory)
    monkeypatch.setattr(
        tool.p1.Storage,
        "check_measurement",
        lambda self: (_ for _ in ()).throw(tool.base.Refused("low_disk_space")),
    )
    assert (
        tool.main(
            [
                "run",
                "--execute",
                "--query",
                "fiscalite-01",
                "--reader-env",
                "unused",
                "--output-dir",
                str(tmp_path / "low"),
                "--min-free-mib",
                "64",
            ]
        )
        == 1
    )
    # Constructing lazy engines is allowed; no connect/SQL call is allowed.
    assert not factory.return_value.connect.called
    assert "low_disk_space" in (tmp_path / "low/comparison.redacted.json").read_text()


def test_structure_comparison_ignores_only_rank_name_and_exports_no_expression():
    _, _, plan, _ = collect()
    a = deepcopy(plan)
    a[0]["Plan"]["Output"] = ["ts_rank_cd(search_vector,'SECRET'::tsquery,32)"]
    b = deepcopy(a)
    b[0]["Plan"]["Output"] = ["ts_rank(search_vector,'SECRET'::tsquery,32)"]
    sa, sb = tool.summarize(a), tool.summarize(b)
    assert sa["rank_normalized_structure_sha256"] == sb["rank_normalized_structure_sha256"]
    assert sa["nodes"][0]["score_in_output"] and sb["nodes"][0]["score_in_output"]
    assert "SECRET" not in json.dumps(sb)
