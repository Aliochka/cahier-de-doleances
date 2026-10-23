"""P5: bounded, opt-in ts_rank_cd/ts_rank comparison. No public recipe changes.

`plan` never opens a connection. `run --execute` executes EXPLAIN ANALYZE.
Reuses pinned P1/P2/P3 transport, allowlists, redaction and private storage.
"""

import argparse
import json
import re
import sys
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from cahier_rag.config import load_settings
from cahier_rag.search.service.control import Budget
from cahier_rag.search.service.reader import check_reader_role, create_search_engine
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text

if __package__:
    from . import components_h1_lexical as p3
else:
    import components_h1_lexical as p3

p2, p1, base = p3.p2, p3.p1, p3.base
P3_SHA = "56ed64dfb9d765609c29b34f4d8224bfc8971eb8115326b852bca50b67e97777"
QUERIES = ("democratie-02", "fiscalite-01")
VARIANTS = ("original", "ts_rank")
FUNCTION = "ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)"
EXTRA_ERRORS = (
    "p5_tool_mismatch",
    "rank_substitution_mismatch",
    "settings_changed",
    "invalid_schedule",
    "invalid_summary",
    "corpus_generation_changed",
)
HASHES = (
    "h1_sql_sha256",
    "parameters_sha256",
    "generation_sha256",
    "settings_control_sha256",
    "tool_sha256",
    "limits_sha256",
)


def verify_sources():
    if base.digest(Path(p3.__file__).read_bytes()) != P3_SHA:
        raise base.Refused("p5_tool_mismatch")
    p3.verify_sources()


def diagnostic_sql(original, score, terms, parameters, variant):
    # Independently verify the complete pinned H1 template and reconstructed score.
    p2.derived_sql(original, score, "top50")
    p3.components(terms, parameters, score)
    if variant not in VARIANTS or original.count(FUNCTION) != 1:
        raise base.Refused("rank_substitution_mismatch")
    if variant == "original":
        return original
    measured = original.replace(FUNCTION, FUNCTION.replace("ts_rank_cd(", "ts_rank("))
    if measured.replace("ts_rank(", "ts_rank_cd(") != original:
        raise base.Refused("rank_substitution_mismatch")
    return measured


class RankWire(p1.AnalyzeWire):
    def configure_measurement(self, statement_ms):
        # Observe ALL collected settings, including JIT/work_mem/I/O. No SET for
        # any planner option; only existing local statement/lock limits are set.
        before = dict(self.execute(text(p1.SETTING_SQL), {"names": list(p1.SETTINGS)}).all())
        self.statement_ms = statement_ms
        effective = dict(
            self.execute(
                text("""SELECT
            current_setting('transaction_read_only') AS read_only,
            current_setting('statement_timeout') AS statement_timeout,
            current_setting('lock_timeout') AS lock_timeout,
            current_setting('jit') AS jit""")
            )
            .mappings()
            .one()
        )
        after = dict(self.execute(text(p1.SETTING_SQL), {"names": list(p1.SETTINGS)}).all())
        if before != after or effective["jit"] != after.get("jit"):
            raise base.Refused("settings_changed")
        if effective["read_only"] != "on":
            raise base.Refused("transaction_not_read_only")
        if not (
            0 < base.timeout_ms(effective["statement_timeout"]) <= statement_ms
            and 0 < base.timeout_ms(effective["lock_timeout"]) <= self.lock_ms
        ):
            raise base.Refused("transaction_timeout_not_bounded")
        return {
            "settings_before": before,
            "settings_effective": after,
            "settings_control_sha256": p1.fingerprint(after),
            "effective_limits": effective,
        }


class RankConnection(base.ExplainConnection):
    def execute(self, statement, parameters=None):
        if self.guard.halted or not isinstance(statement, base.TextClause):
            raise base.Refused("unexpected_statement")
        caller = sys._getframe(1)
        sql = statement.text
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and caller.f_locals.get("sql") == sql
            and caller.f_locals.get("params") is parameters
        ):
            recipe = self.guard.engine_recipe
            if (
                not self.target
                or self.guard.captures
                or parameters["space"] != "full"
                or type(parameters["limit"]) is not int
                or parameters["limit"] != 50
                or any(parameters[k] is not None for k in ("form", "kind", "split"))
                or recipe.statistics is not True
                or recipe.prefilter is not None
            ):
                raise base.Refused("unexpected_ranking")
            measured = diagnostic_sql(
                sql,
                caller.f_locals["score"],
                caller.f_locals["terms"],
                parameters,
                self.guard.variant,
            )
            self.guard.halted, self.guard.captures = True, 1
            self.guard.stage = "measurement_setup"
            self.guard.metadata.update(self.wire.configure_measurement(self.guard.measurement_ms))
            self.guard.metadata.update(
                h1_sql_template=sql,
                measured_sql_template=measured,
                h1_sql_sha256=base.digest(sql.encode()),
                sql_sha256=base.digest(measured.encode()),
                parameters_sha256=p1.fingerprint(parameters),
                parameter_types={k: type(v).__name__ for k, v in parameters.items()},
                lexeme_count=len(caller.f_locals["terms"]),
            )
            explained = text(p1.EXPLAIN + measured).bindparams(*statement._bindparams.values())
            self.guard.stage = "ranking"
            self.wire.last_timeout_ms = None
            started = time.monotonic()
            try:
                plan = self.wire.execute(explained, parameters).scalar_one()
            finally:
                self.guard.metadata.update(
                    ranking_statement_timeout_ms=self.wire.last_timeout_ms,
                    ranking_client_seconds=time.monotonic() - started,
                )
            self.guard.stage = "plan_received"
            raise base.PlanCaptured(plan)
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and sql == "SET LOCAL statement_timeout='30s'"
        ):
            return None
        return super().execute(statement, parameters)


class RankGuard(base.ExplainGuard):
    def __init__(self, source, target, budget, *, variant, statement_ms, lock_ms):
        super().__init__(source, target, budget, statement_ms=2000, lock_ms=lock_ms)
        self.variant, self.measurement_ms = variant, statement_ms
        self.stage = "preparation"

    @contextmanager
    def _connect(self, engine):
        self.budget.check()
        with engine.connect() as raw:
            raw = raw.execution_options(postgresql_readonly=True)
            transaction = raw.begin()
            state = {"target": engine is self.target, "rollback": "pending"}
            self.metadata["transactions"].append(state)
            try:
                wire = RankWire(raw, self.budget, 2000, self.lock_ms)
                state.update(wire.initialize())
                connection = RankConnection(wire, self, target=engine is self.target)
                check_reader_role(connection)
                yield connection
            finally:
                transaction.rollback()
                state["rollback"] = "done"
        self.budget.check()


def validate(statement_ms, lock_ms, seconds):
    p2.validate("costs", "top50", "current", "observe", statement_ms, lock_ms, seconds)


def collect_case(source, target, query, *, variant, statement_ms=60000, lock_ms=200, seconds=90):
    validate(statement_ms, lock_ms, seconds)
    if variant not in VARIANTS:
        raise base.Refused("rank_substitution_mismatch")
    guard = RankGuard(
        source, target, Budget(seconds), variant=variant, statement_ms=statement_ms, lock_ms=lock_ms
    )
    engine = TunedSearch(base.ExplainStore(guard), statistics=True, prefilter=None)
    guard.engine_recipe = engine
    started, plan = time.monotonic(), None
    status, code = "error", "ranking_not_captured"
    try:
        with guard.budget.monitor(), guard.budget.phase("p5_collection"):
            try:
                engine.lexical(query, limit=50, questionnaire_id=None, unit_type=None, split=None)
            except base.PlanCaptured as captured:
                plan, status, code = captured.plan, "ok", "none"
    except Exception as error:
        status, code = p1.error_status(error)
        if isinstance(error, base.Refused) and error.args[0] in EXTRA_ERRORS:
            code = error.args[0]
    return plan, {
        "status": status,
        "code": code,
        "stage": guard.stage,
        "elapsed_seconds": time.monotonic() - started,
        **guard.metadata,
    }


def schedule(query_id, repeats, warmups):
    if (
        query_id not in QUERIES
        or type(repeats) is not int
        or not 1 <= repeats <= 20
        or type(warmups) is not int
        or not 0 <= warmups <= 2
    ):
        raise base.Refused("invalid_schedule")
    rows = []
    for phase, count in (("warmup", warmups), ("measure", repeats)):
        for pair in range(1, count + 1):
            for position, variant in enumerate(VARIANTS if pair % 2 else VARIANTS[::-1], 1):
                rows.append(
                    {
                        "run_id": f"{phase}-{pair:02}-{variant}",
                        "query_id": query_id,
                        "phase": phase,
                        "pair": pair,
                        "position": position,
                        "variant": variant,
                        "status": "pending",
                        "code": "none",
                    }
                )
    return rows


def safe_row(record):
    if (
        record.get("query_id") not in QUERIES
        or record.get("variant") not in VARIANTS
        or record.get("status") not in p1.STATUSES
        or record.get("phase") not in ("warmup", "measure")
        or type(record.get("pair")) is not int
        or not 1 <= record["pair"] <= 20
        or record.get("position") not in (1, 2)
    ):
        raise base.Refused("invalid_summary")
    row = {k: record[k] for k in ("query_id", "variant", "phase", "pair", "position", "status")}
    row["code"] = (
        record.get("code")
        if record.get("code") in (*p1.ERROR_CODES, *EXTRA_ERRORS)
        else "measurement_failed"
    )
    for k in (
        *p1.TABLE_NUMBERS,
        "ranking_client_seconds",
        "ranking_statement_timeout_ms",
        "lexeme_count",
    ):
        row[k] = record.get(k) if base.number(record.get(k)) else None
    for k in (
        *HASHES,
        "sql_sha256",
        "access_sha256",
        "structure_sha256",
        "rank_normalized_structure_sha256",
    ):
        value = record.get(k)
        row[k] = value if isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) else None
    return row


def summarize(plan):
    summary = p2.summarize(plan)
    normalized = deepcopy(plan)
    nodes = []

    def visit(node):
        nodes.append(node)
        for child in node.get("Plans", []):
            visit(child)

    visit(normalized[0]["Plan"])
    for safe, node in zip(summary["nodes"], nodes, strict=True):
        safe["score_in_output"] = any(
            re.search(r"\bts_rank(?:_cd)?\(", re.sub(r"'(?:''|[^'])*'", "''", s)) is not None
            for s in node.get("Output", [])
            if isinstance(s, str)
        )
        # A changed function name alone must not be reported as a plan change.
        for key in p1.STRUCTURAL_FIELDS:
            value = node.get(key)
            if isinstance(value, str):
                node[key] = value.replace("ts_rank_cd(", "ts_rank(")
            elif isinstance(value, list):
                node[key] = [
                    s.replace("ts_rank_cd(", "ts_rank(") if isinstance(s, str) else s for s in value
                ]
    summary["rank_normalized_structure_sha256"] = p1.summarize(normalized)["structure_sha256"]
    return summary


def comparison(records):
    rows = [safe_row(r) for r in records]
    measured = [r for r in rows if r["phase"] == "measure"]
    groups = {}
    for variant in VARIANTS:
        group = [r for r in measured if r["variant"] == variant]
        times = [
            r["execution_ms"]
            for r in group
            if r["status"] == "ok" and base.number(r["execution_ms"])
        ]
        groups[variant] = {
            "scheduled": len(group),
            "ok": sum(r["status"] == "ok" for r in group),
            "timeout": sum(r["status"] == "timeout" for r in group),
            "error": sum(r["status"] == "error" for r in group),
            "skipped": sum(r["status"] == "skipped" for r in group),
            "successful_execution_ms": {
                "n": len(times),
                "median": median(times) if times else None,
                "min": min(times) if times else None,
                "max": max(times) if times else None,
            },
            "successful_over_public_10s": sum(t > 10000 for t in times),
        }
    pairs = []
    for pair in sorted({r["pair"] for r in measured}):
        a, b = (
            next((r for r in measured if r["pair"] == pair and r["variant"] == v), {})
            for v in VARIANTS
        )
        controlled = bool(a and b and all(a.get(k) and a.get(k) == b.get(k) for k in HASHES))
        complete = (
            controlled
            and a.get("status") == b.get("status") == "ok"
            and all(base.number(r.get("execution_ms")) and r["execution_ms"] > 0 for r in (a, b))
        )
        pairs.append(
            {
                "pair": pair,
                "controlled_conditions": controlled,
                "complete_pair": complete,
                "original_first": a.get("position") == 1,
                "gain_percent": 100 * (1 - b["execution_ms"] / a["execution_ms"])
                if complete
                else None,
                "delta_ms": b["execution_ms"] - a["execution_ms"] if complete else None,
                "same_access_strategy": a.get("access_sha256") == b.get("access_sha256")
                if complete
                else None,
                "same_plan_structure_ignoring_rank_name": a.get("rank_normalized_structure_sha256")
                == b.get("rank_normalized_structure_sha256")
                if complete
                and a.get("rank_normalized_structure_sha256")
                and b.get("rank_normalized_structure_sha256")
                else None,
                "same_workers": all(
                    a.get(k) == b.get(k) for k in ("workers_planned", "workers_launched")
                )
                if complete
                and all(
                    r.get(k) is not None
                    for r in (a, b)
                    for k in ("workers_planned", "workers_launched")
                )
                else None,
            }
        )
    valid = [p for p in pairs if p["complete_pair"]]
    gains = [p["gain_percent"] for p in valid]
    return {
        "format": "p5-v1",
        "runs": rows,
        "groups": groups,
        "pairs": pairs,
        "paired": {
            "n": len(valid),
            "median_gain_percent": median(gains) if gains else None,
            "min_gain_percent": min(gains) if gains else None,
            "max_gain_percent": max(gains) if gains else None,
            "regressions": sum(p["delta_ms"] > 0 for p in valid),
            "median_gain_by_order": {
                str(first): median(g) if g else None
                for first in (True, False)
                for g in [[p["gain_percent"] for p in valid if p["original_first"] == first]]
            },
        },
        "warning": "EXPLAIN_ANALYZE_instrumented_SQL_only_successes_censored_timeouts_not_zero_no_cold_cache_or_significance_claim",
    }


def markdown(report):
    keys = (
        "query_id",
        "phase",
        "pair",
        "position",
        "variant",
        "status",
        "execution_ms",
        "planning_ms",
        "workers_planned",
        "workers_launched",
        "shared_hit_blocks",
        "shared_read_blocks",
        "temp_read_blocks",
        "temp_written_blocks",
    )
    return "\n".join(
        [
            "# P5 — ts_rank_cd / ts_rank",
            "",
            "Temps SQL instrumentés par EXPLAIN ANALYZE, hors préparation. Réchauffements exclus des agrégats. Timeouts censurés : aucun temps SQL inventé. Les temps dépassant 10 s sont seulement un repère, pas un test du budget public ni une mesure H1 bout en bout.",
            "",
            "| " + " | ".join(keys) + " |",
            "| " + " | ".join("---" for _ in keys) + " |",
            *("| " + " | ".join(str(r.get(k)) for k in keys) + " |" for r in report["runs"]),
            "",
            "## Agrégats et paires",
            "",
            "```json",
            json.dumps({k: report[k] for k in ("groups", "pairs", "paired")}, indent=2),
            "```",
            "",
            "Comparer les distributions, les deux ordres AB/BA, les buffers et workers. Une médiane sur les seuls succès peut être biaisée par les timeouts. Des réglages identiques ne prouvent pas des caches ou une activité concurrente identiques. Pas de conclusion de significativité sur quelques répétitions.",
            "",
        ]
    )


def save(storage, records, manifest):
    report = comparison(records)
    storage.write("manifest.private.json", manifest)
    storage.write("comparison.redacted.json", report)
    storage.write("comparison.redacted.md", markdown(report), as_text=True)


def run(args):
    verify_sources()
    queries = base.read_cases(args.queries)
    validate(args.statement_timeout_ms, args.lock_timeout_ms, args.case_deadline_seconds)
    records = schedule(args.query, args.repeats, args.warmups)
    settings = load_settings(env_file=args.reader_env, environ={})
    urls = settings.require_source_url(), settings.require_rag_url()
    limits = {
        "statement_ms": args.statement_timeout_ms,
        "lock_ms": args.lock_timeout_ms,
        "seconds": args.case_deadline_seconds,
    }
    manifest = {
        "tool_sha256": base.digest(Path(__file__).read_bytes()),
        "p3_sha256": P3_SHA,
        "h1_sources_sha256": base.SOURCE_HASHES,
        "queries_sha256": base.QUERY_SHA256,
        "limits": limits,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }
    with p1.exclusive_output(args.output_dir):
        storage = p1.Storage(
            args.output_dir,
            maximum=args.max_output_mib * p1.MIB,
            minimum_free=args.min_free_mib * p1.MIB,
        )
        engines, stopped, generation = [], False, None
        save(storage, records, manifest)
        try:
            for url in urls:
                engines.append(create_search_engine(url))
            for record in records:
                if stopped:
                    break
                try:
                    storage.check_measurement()
                    record.update(status="running")
                    save(storage, records, manifest)
                    plan, meta = collect_case(
                        *engines, queries[args.query], variant=record["variant"], **limits
                    )
                    manifest["runs"].append({"run_id": record["run_id"], **meta})
                    record.update({k: meta[k] for k in ("status", "code", "elapsed_seconds")})
                    for k in (
                        "h1_sql_sha256",
                        "sql_sha256",
                        "parameters_sha256",
                        "settings_control_sha256",
                        "ranking_client_seconds",
                        "ranking_statement_timeout_ms",
                        "lexeme_count",
                    ):
                        if k in meta:
                            record[k] = meta[k]
                    if "generation" in meta:
                        current = p1.fingerprint(meta["generation"])
                        if generation is not None and generation != current:
                            raise base.Refused("corpus_generation_changed")
                        generation = current
                        record["generation_sha256"] = current
                    record.update(
                        tool_sha256=manifest["tool_sha256"], limits_sha256=p1.fingerprint(limits)
                    )
                    if plan is not None and meta["status"] == "ok":
                        safe = summarize(plan)
                        storage.write(
                            record["run_id"] + ".plan.private.json", plan, limit=p1.PLAN_LIMIT
                        )
                        storage.write(
                            record["run_id"] + ".summary.redacted.json", safe, limit=p1.PLAN_LIMIT
                        )
                        record.update(safe)
                    stopped = record["status"] == "error"
                except KeyboardInterrupt:
                    record.update(status="error", code="interrupted")
                    stopped = True
                except Exception as error:
                    status, code = p1.error_status(error)
                    if isinstance(error, base.Refused) and error.args[0] in EXTRA_ERRORS:
                        code = error.args[0]
                    record.update(status=status, code=code)
                    stopped = True
                save(storage, records, manifest)
        finally:
            for engine in engines:
                engine.dispose()
            for record in records:
                if record["status"] in ("pending", "running"):
                    record.update(status="skipped", code="not_run_after_error")
            save(storage, records, manifest)
    return 0 if all(r["status"] == "ok" for r in records) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        command = commands.add_parser(name)
        command.add_argument("--query", choices=QUERIES, required=True)
        command.add_argument("--repeats", type=base.bounded_integer(20), default=4)
        command.add_argument("--warmups", type=int, choices=(0, 1, 2), default=1)
        command.add_argument(
            "--queries", type=Path, default=Path("rag/evaluation/performance-rag027.json")
        )
        command.add_argument(
            "--statement-timeout-ms", type=base.bounded_integer(300000), default=60000
        )
        command.add_argument("--case-deadline-seconds", type=base.bounded_integer(360), default=90)
        command.add_argument("--lock-timeout-ms", type=base.bounded_integer(1000), default=200)
    execute = commands.choices["run"]
    execute.add_argument("--execute", action="store_true", required=True)
    execute.add_argument("--reader-env", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    execute.add_argument("--max-output-mib", type=int, choices=range(32, 257), default=128)
    execute.add_argument("--min-free-mib", type=int, choices=range(64, 65537), default=512)
    args = parser.parse_args(argv)
    try:
        verify_sources()
        base.read_cases(args.queries)
        validate(args.statement_timeout_ms, args.lock_timeout_ms, args.case_deadline_seconds)
        if args.command == "plan":
            print(
                json.dumps(
                    {
                        "executed": False,
                        "schedule": schedule(args.query, args.repeats, args.warmups),
                        "limits": {
                            "statement_ms": args.statement_timeout_ms,
                            "case_seconds": args.case_deadline_seconds,
                            "lock_ms": args.lock_timeout_ms,
                        },
                    },
                    indent=2,
                )
            )
            return 0
        return run(args)
    except Exception as error:
        _, code = p1.error_status(error)
        if isinstance(error, base.Refused) and error.args[0] in EXTRA_ERRORS:
            code = error.args[0]
        print(code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
