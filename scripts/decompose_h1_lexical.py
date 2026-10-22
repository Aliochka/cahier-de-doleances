"""P2 lexical experiments. Derived diagnostics are explicitly distinct from H1.

Uses P1 transport/storage unchanged. All execution is opt-in, reader-only and
transaction-local. No model initialization, hydration or arbitrary SQL input.
"""

import argparse
import json
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.config import load_settings
from cahier_rag.fullcorpus.search import FILTERS
from cahier_rag.search.service.control import Budget
from cahier_rag.search.service.reader import check_reader_role, create_search_engine
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text

if __package__:
    from . import analyze_h1_lexical as p1
else:
    import analyze_h1_lexical as p1

base = p1.base
P1_SHA = "3d3b9f4cba9530e57cf3cf6f58ce92f4ad4e76a3fe372c06c4f9316735b5e937"
COSTS = ("filter", "score", "top50", "filter-stream", "score-stream")
MEMORY = ("observe", "current", "4MB", "16MB", "64MB")
CONTROL_SQL = """SELECT current_setting('work_mem') AS work_mem,
    pg_size_bytes(current_setting('work_mem'))::bigint AS work_mem_bytes,
    current_setting('track_io_timing') AS track_io_timing,
    has_parameter_privilege(current_user, 'track_io_timing', 'SET') AS can_set_io"""
HASHES = (
    "h1_sql_sha256",
    "sql_sha256",
    "parameters_sha256",
    "generation_sha256",
    "settings_control_sha256",
    "access_sha256",
    "structure_sha256",
    "tool_sha256",
    "limits_sha256",
)
EXTRA_NUMBERS = (
    "work_mem_initial_bytes",
    "work_mem_effective_bytes",
    "exact_heap_blocks",
    "lossy_heap_blocks",
    "recheck_rows_removed_approx",
)
ERRORS = (
    *p1.ERROR_CODES,
    "experiment_setting_mismatch",
    "settings_changed_beyond_experiment",
    "invalid_measurement_limits",
)


def verify_sources():
    if base.digest(Path(p1.__file__).read_bytes()) != P1_SHA:
        raise base.Refused("p1_tool_mismatch")
    p1.verify_sources()


def derived_sql(original, score, variant):
    where = f"""FROM rag_full.documents d
                WHERE {FILTERS} AND d.search_vector @@ CAST(:query AS tsquery)"""
    expected = f"""SELECT d.document_id,{score} AS score {where}
                ORDER BY score DESC,d.document_id COLLATE "C" LIMIT :limit"""
    if original != expected:
        raise base.Refused("unexpected_ranking")
    if variant == "top50":
        return original
    if variant == "filter":
        return "SELECT count(*) AS matched " + where
    if variant == "score":
        # A used aggregate argument prevents the optimizer discarding the score.
        return f"SELECT count(*) AS matched, sum(({score})) AS score_sum " + where
    if variant == "filter-stream":
        return "SELECT d.document_id " + where
    if variant == "score-stream":
        return f"SELECT d.document_id,{score} AS score " + where
    raise base.Refused("unexpected_ranking")


class ExperimentWire(p1.AnalyzeWire):
    def configure_experiment(self, guard):
        metadata = self.configure_measurement(guard.mode, guard.measurement_ms)
        before = dict(self.execute(text(CONTROL_SQL)).mappings().one())
        if guard.axis == "work-mem" and guard.variant in ("4MB", "16MB", "64MB"):
            self.execute(
                text("SELECT set_config('work_mem', :value, true)"), {"value": guard.variant}
            )
        if (
            guard.io_policy == "if-permitted"
            and before["track_io_timing"] == "off"
            and before["can_set_io"] is True
        ):
            self.execute(text("SELECT set_config('track_io_timing', 'on', true)"))
        after = dict(self.execute(text(CONTROL_SQL)).mappings().one())
        requested = (
            int(guard.variant[:-2]) * p1.MIB
            if guard.axis == "work-mem" and guard.variant.endswith("MB")
            else before["work_mem_bytes"]
        )
        expected_io = (
            "on"
            if guard.io_policy == "if-permitted" and before["can_set_io"] is True
            else before["track_io_timing"]
        )
        if after["work_mem_bytes"] != requested or after["track_io_timing"] != expected_io:
            raise base.Refused("experiment_setting_mismatch")
        settings = dict(self.execute(text(p1.SETTING_SQL), {"names": list(p1.SETTINGS)}).all())
        allowed = {"work_mem"} if guard.axis == "work-mem" else set()
        if guard.io_policy == "if-permitted":
            allowed.add("track_io_timing")
        prior = metadata["settings_effective"]
        if {k: v for k, v in prior.items() if k not in allowed} != {
            k: v for k, v in settings.items() if k not in allowed
        }:
            raise base.Refused("settings_changed_beyond_experiment")
        # Retain JIT and I/O timing in cross-run controls. Only intended memory
        # differences in axis B are excluded, never the JIT thresholds.
        controlled = {
            k: v for k, v in settings.items() if not (guard.axis == "work-mem" and k == "work_mem")
        }
        metadata.update(
            settings_effective=settings,
            controls_before=before,
            controls_after=after,
            settings_control_sha256=p1.fingerprint(controlled),
        )
        metadata["io_timing_reason"] = (
            "enabled"
            if after["track_io_timing"] == "on"
            else "no_existing_set_privilege"
            if not before["can_set_io"]
            else "not_requested"
        )
        return metadata


class ExperimentConnection(base.ExplainConnection):
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
            variant = self.guard.variant if self.guard.axis == "costs" else "top50"
            measured = derived_sql(sql, caller.f_locals["score"], variant)
            self.guard.halted, self.guard.captures = True, 1
            self.guard.stage = "experiment_setup"
            self.guard.metadata.update(self.wire.configure_experiment(self.guard))
            self.guard.metadata.update(
                h1_sql_sha256=base.digest(sql.encode()),
                sql_sha256=base.digest(measured.encode()),
                parameters_sha256=p1.fingerprint(parameters),
                parameter_types={k: type(v).__name__ for k, v in parameters.items()},
                h1_sql_template=sql,
                measured_sql_template=measured,
            )
            if self.guard.variant == "observe":
                self.guard.stage = "observed_without_ranking"
                raise base.PlanCaptured(None)
            explained = text(p1.EXPLAIN + measured)
            # Preserve definitions for every bind that remains in derived SQL;
            # keep the original parameter dictionary, including unused entries.
            explained = explained.bindparams(
                *(v for k, v in statement._bindparams.items() if k in explained._bindparams)
            )
            self.guard.stage = "ranking"
            self.wire.last_timeout_ms = None
            try:
                plan = self.wire.execute(explained, parameters).scalar_one()
            finally:
                self.guard.metadata["ranking_statement_timeout_ms"] = self.wire.last_timeout_ms
            self.guard.stage = "plan_received"
            raise base.PlanCaptured(plan)
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and sql == "SET LOCAL statement_timeout='30s'"
        ):
            return None
        return super().execute(statement, parameters)


class ExperimentGuard(p1.AnalyzeGuard):
    def __init__(self, source, target, budget, *, axis, variant, io_policy, **kwargs):
        super().__init__(source, target, budget, **kwargs)
        self.axis, self.variant, self.io_policy = axis, variant, io_policy

    @contextmanager
    def _connect(self, engine):
        self.budget.check()
        with engine.connect() as raw:
            raw = raw.execution_options(postgresql_readonly=True)
            transaction = raw.begin()
            state = {"target": engine is self.target, "rollback": "pending"}
            self.metadata["transactions"].append(state)
            try:
                wire = ExperimentWire(raw, self.budget, 2000, self.lock_ms)
                state.update(wire.initialize())
                connection = ExperimentConnection(wire, self, target=engine is self.target)
                check_reader_role(connection)
                yield connection
            finally:
                transaction.rollback()
                state["rollback"] = "done"
        self.budget.check()


def validate(axis, variant, mode, io_policy, statement_ms, lock_ms, seconds):
    if (
        axis not in ("costs", "work-mem")
        or mode not in ("current", "off")
        or io_policy not in ("observe", "if-permitted")
        or variant not in (COSTS if axis == "costs" else MEMORY)
        or not 1 <= statement_ms <= 300000
        or not 1 <= lock_ms <= 1000
        or not 1 <= seconds <= 360
        or seconds * 1000 < statement_ms
    ):
        raise base.Refused("invalid_measurement_limits")


def collect_case(
    source,
    target,
    query,
    *,
    axis,
    variant,
    mode="current",
    io_policy="observe",
    statement_ms=60000,
    lock_ms=200,
    seconds=90,
):
    validate(axis, variant, mode, io_policy, statement_ms, lock_ms, seconds)
    guard = ExperimentGuard(
        source,
        target,
        Budget(seconds),
        axis=axis,
        variant=variant,
        mode=mode,
        io_policy=io_policy,
        statement_ms=statement_ms,
        lock_ms=lock_ms,
    )
    engine = TunedSearch(base.ExplainStore(guard), statistics=True, prefilter=None)
    guard.engine_recipe = engine
    start = time.monotonic()
    plan = None
    status, code = "error", "ranking_not_captured"
    try:
        with guard.budget.monitor(), guard.budget.phase("p2_collection"):
            try:
                engine.lexical(query, limit=50, questionnaire_id=None, unit_type=None, split=None)
            except base.PlanCaptured as captured:
                plan = captured.plan
                status, code = ("observed" if variant == "observe" else "ok"), "none"
    except Exception as error:
        status, code = p1.error_status(error)
        if isinstance(error, base.Refused) and error.args[0] in ERRORS:
            code = error.args[0]
    return plan, {
        "status": status,
        "code": code,
        "stage": guard.stage,
        "elapsed_seconds": time.monotonic() - start,
        **guard.metadata,
    }


def summarize(plan):
    summary = p1.summarize(plan)
    scans = []

    def visit(node):
        if node.get("Relation Name") == "documents_full":
            scans.append(
                {
                    k: node[k]
                    for k in (
                        "Node Type",
                        "Schema",
                        "Relation Name",
                        "Index Name",
                        "Parallel Aware",
                        "Scan Direction",
                        "Filter",
                        "Index Cond",
                        "Recheck Cond",
                    )
                    if k in node
                }
            )
        for child in node.get("Plans", []):
            visit(child)

    visit(plan[0]["Plan"])
    summary["access_sha256"] = p1.fingerprint(scans)
    # Do not add the same counters from parent, child and worker sections.
    document_scans = [n for n in summary["nodes"] if n.get("Relation Name") == "documents_full"]
    for output, key in (
        ("exact_heap_blocks", "Exact Heap Blocks"),
        ("lossy_heap_blocks", "Lossy Heap Blocks"),
    ):
        summary[output] = document_scans[0].get(key) if len(document_scans) == 1 else None
    summary["recheck_rows_removed_approx"] = None
    if len(document_scans) == 1:
        node = document_scans[0]
        if base.number(node.get("Rows Removed by Index Recheck")) and base.number(
            node.get("Actual Loops")
        ):
            summary["recheck_rows_removed_approx"] = (
                node["Rows Removed by Index Recheck"] * node["Actual Loops"]
            )
    # Export only presence, never SQL projection expressions.
    raw_nodes = []

    def projections(node):
        raw_nodes.append(
            any("ts_rank_cd" in value for value in node.get("Output", []) if isinstance(value, str))
        )
        for child in node.get("Plans", []):
            projections(child)

    projections(plan[0]["Plan"])
    for node, present in zip(summary["nodes"], raw_nodes, strict=True):
        node["score_in_output"] = present
    return summary


def schedule(axis, variant, query_id, repeats, alternate):
    choices = (
        (COSTS[:3] if axis == "costs" else MEMORY[2:])
        if variant == "all"
        else (COSTS[3:] if variant == "streams" and axis == "costs" else (variant,))
    )
    for choice in choices:
        validate(axis, choice, "current", "observe", 60000, 200, 90)
    if (
        query_id not in base.CASE_IDS
        or (axis == "work-mem" and query_id != "fiscalite-05")
        or not 1 <= repeats <= 20
        or (alternate and len(choices) < 2)
        or (variant == "observe" and repeats != 1)
    ):
        raise base.Refused("invalid_schedule")
    result = []
    for repetition in range(1, repeats + 1):
        offset = (repetition - 1) % len(choices) if alternate else 0
        for choice in choices[offset:] + choices[:offset]:
            result.append(
                {
                    "axis": axis,
                    "variant": choice,
                    "query_id": query_id,
                    "repetition": repetition,
                    "run_id": f"r{repetition:02d}-{query_id}-{choice}",
                    "diagnostic_derived": axis == "costs" and choice != "top50",
                    "status": "pending",
                    "code": "none",
                }
            )
    return result


def row(record):
    if (
        record.get("axis") not in ("costs", "work-mem")
        or record.get("query_id") not in base.CASE_IDS
        or record.get("variant") not in (COSTS if record["axis"] == "costs" else MEMORY)
        or record.get("status") not in (*p1.STATUSES, "observed")
        or type(record.get("repetition")) is not int
        or not 1 <= record["repetition"] <= 20
    ):
        raise base.Refused("invalid_summary")
    result = {k: record[k] for k in ("axis", "variant", "query_id", "repetition", "status")}
    result["code"] = record.get("code") if record.get("code") in ERRORS else "measurement_failed"
    for key in (*p1.TABLE_NUMBERS, *EXTRA_NUMBERS):
        result[key] = record.get(key) if base.number(record.get(key)) else None
    for key in HASHES:
        value = record.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            result[key] = value
    return result


def comparisons(rows):
    result = []
    for i, current in enumerate(rows):
        for j, prior in enumerate(rows[:i]):
            if (
                any(current[k] != prior[k] for k in ("axis", "query_id", "repetition"))
                or current["variant"] == prior["variant"]
            ):
                continue
            keys = (
                "h1_sql_sha256",
                "parameters_sha256",
                "generation_sha256",
                "settings_control_sha256",
                "tool_sha256",
                "limits_sha256",
            )
            if current["axis"] == "work-mem":
                keys += ("sql_sha256",)
            controlled = current["status"] == prior["status"] == "ok" and all(
                current.get(k) is not None and current.get(k) == prior.get(k) for k in keys
            )
            same_access = (
                current.get("access_sha256") == prior.get("access_sha256") if controlled else None
            )
            parallel = (
                all(current.get(k) == prior.get(k) for k in ("workers_planned", "workers_launched"))
                if controlled
                else None
            )
            result.append(
                {
                    "rows": [j, i],
                    "controlled_conditions": controlled,
                    "same_access_strategy": same_access,
                    "same_parallelism": parallel,
                    "same_cardinality_approx": current.get("candidate_rows_approx")
                    == prior.get("candidate_rows_approx")
                    if controlled
                    and all(base.number(r.get("candidate_rows_approx")) for r in (current, prior))
                    else None,
                    "same_full_structure": current.get("structure_sha256")
                    == prior.get("structure_sha256")
                    if controlled
                    else None,
                    "execution_delta_ms_second_minus_first": current["execution_ms"]
                    - prior["execution_ms"]
                    if controlled
                    else None,
                    "interpretation": "observed_difference_not_exact_operation_cost",
                }
            )
    return result


def table(rows):
    keys = (
        "axis",
        "query_id",
        "variant",
        "repetition",
        "status",
        "execution_ms",
        "work_mem_initial_bytes",
        "work_mem_effective_bytes",
        "candidate_rows_approx",
        "exact_heap_blocks",
        "lossy_heap_blocks",
        "recheck_rows_removed_approx",
        "shared_hit_blocks",
        "shared_read_blocks",
        "workers_launched",
    )
    return (
        "\n".join(
            [
                "| " + " | ".join(keys) + " |",
                "| " + " | ".join("---" for _ in keys) + " |",
                *(
                    "| "
                    + " | ".join(str(r.get(k)) if r.get(k) is not None else "n/a" for k in keys)
                    + " |"
                    for r in rows
                ),
            ]
        )
        + "\n"
    )


def save(storage, records, manifest):
    rows = [row(record) for record in records]
    manifest["outcomes"] = rows
    storage.write("manifest.private.json", manifest)
    storage.write("summary.redacted.json", {"format": "p2-v1", "runs": records})
    storage.write("comparison.redacted.json", {"rows": rows, "comparisons": comparisons(rows)})
    storage.write("comparison.redacted.md", table(rows), as_text=True)


def run(args):
    verify_sources()
    queries = base.read_cases(args.queries)
    settings = load_settings(env_file=args.reader_env, environ={})
    urls = settings.require_source_url(), settings.require_rag_url()
    records = schedule(args.axis, args.variant, args.query, args.repeats, args.alternate)
    limits = {
        "statement_ms": args.statement_timeout_ms,
        "lock_ms": args.lock_timeout_ms,
        "seconds": args.case_deadline_seconds,
    }
    manifest = {
        "base_commit": base.BASE_COMMIT,
        "tool_sha256": base.digest(Path(__file__).read_bytes()),
        "p1_sha256": P1_SHA,
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
        save(storage, records, manifest)
        engines = []
        stop, generation = False, None
        try:
            for url in urls:
                engines.append(create_search_engine(url))
            for record in records:
                if stop:
                    continue
                try:
                    storage.check_measurement()
                    record.update(
                        status="running", started_utc=datetime.now(timezone.utc).isoformat()
                    )
                    save(storage, records, manifest)
                    plan, meta = collect_case(
                        *engines,
                        queries[args.query],
                        axis=args.axis,
                        variant=record["variant"],
                        mode=args.jit,
                        io_policy=args.io_timing,
                        **limits,
                    )
                    record.update({k: meta[k] for k in ("status", "code", "elapsed_seconds")})
                    manifest["runs"].append({"run_id": record["run_id"], **meta})
                    if meta["status"] in ("ok", "observed"):
                        current = p1.fingerprint(meta["generation"])
                        if generation is not None and generation != current:
                            raise base.Refused("corpus_generation_changed")
                        generation = current
                        record.update(
                            {
                                k: meta[k]
                                for k in (
                                    "h1_sql_sha256",
                                    "sql_sha256",
                                    "parameters_sha256",
                                    "settings_control_sha256",
                                    "io_timing_reason",
                                )
                            }
                        )
                        record.update(
                            generation_sha256=generation,
                            limits_sha256=p1.fingerprint(limits),
                            tool_sha256=manifest["tool_sha256"],
                            work_mem_initial_bytes=meta["controls_before"]["work_mem_bytes"],
                            work_mem_effective_bytes=meta["controls_after"]["work_mem_bytes"],
                            effective_jit=meta["settings_effective"]["jit"],
                            io_timing_enabled=meta["controls_after"]["track_io_timing"] == "on",
                            can_set_io=meta["controls_before"]["can_set_io"],
                        )
                        if plan is not None:
                            safe = summarize(plan)
                            if args.jit == "off" and (
                                safe["jit"]["present"]
                                or any(
                                    n["jit"]["present"]
                                    or any(w["jit"]["present"] for w in n["workers"])
                                    for n in safe["nodes"]
                                )
                            ):
                                raise base.Refused("jit_off_plan_contains_jit")
                            storage.write(
                                record["run_id"] + ".plan.private.json", plan, limit=p1.PLAN_LIMIT
                            )
                            storage.write(
                                record["run_id"] + ".summary.redacted.json",
                                safe,
                                limit=p1.PLAN_LIMIT,
                            )
                            record.update({k: v for k, v in safe.items() if k != "nodes"})
                    stop = record["status"] == "error"
                except KeyboardInterrupt:
                    record.update(status="error", code="interrupted")
                    stop = True
                except Exception as error:
                    status, code = p1.error_status(error)
                    record.update(status=status, code=code)
                    stop = True
                record["completed_utc"] = datetime.now(timezone.utc).isoformat()
                save(storage, records, manifest)
        finally:
            for engine in engines:
                engine.dispose()
            for record in records:
                if record["status"] in ("pending", "running"):
                    record.update(status="skipped", code="not_run_after_error")
            save(storage, records, manifest)
    return 0 if all(r["status"] in ("ok", "observed") for r in records) else 1


def compare(args):
    rows = []
    for directory in args.compare:
        path = directory / "summary.redacted.json"
        if path.stat().st_size > p1.REPORT_LIMIT:
            raise base.Refused("invalid_summary")
        data = json.loads(path.read_bytes())
        if data.get("format") != "p2-v1" or len(data["runs"]) > 100:
            raise base.Refused("invalid_summary")
        rows.extend(row(record) for record in data["runs"])
    with p1.exclusive_output(args.output_dir):
        storage = p1.Storage(
            args.output_dir,
            maximum=args.max_output_mib * p1.MIB,
            minimum_free=args.min_free_mib * p1.MIB,
        )
        storage.write("comparison.redacted.json", {"rows": rows, "comparisons": comparisons(rows)})
        storage.write("comparison.redacted.md", table(rows), as_text=True)
    return 0


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--axis", choices=("costs", "work-mem"))
    group.add_argument("--compare", nargs="+", type=Path)
    cli.add_argument("--execute", action="store_true")
    cli.add_argument("--query", choices=base.CASE_IDS)
    cli.add_argument("--variant", choices=tuple(dict.fromkeys((*COSTS, *MEMORY, "all", "streams"))))
    cli.add_argument("--jit", choices=("current", "off"), default="current")
    cli.add_argument("--io-timing", choices=("observe", "if-permitted"), default="observe")
    cli.add_argument("--reader-env", type=Path)
    cli.add_argument("--queries", type=Path)
    cli.add_argument("--output-dir", type=Path, required=True)
    for name, maximum, default in (
        ("statement-timeout-ms", 300000, 60000),
        ("case-deadline-seconds", 360, 90),
        ("lock-timeout-ms", 1000, 200),
        ("repeats", 20, 1),
        ("max-output-mib", 256, 64),
        ("min-free-mib", 1048576, 512),
    ):
        cli.add_argument("--" + name, type=base.bounded_integer(maximum), default=default)
    cli.add_argument("--alternate", action="store_true")
    args = cli.parse_args(argv)
    if (
        args.max_output_mib < 32
        or args.min_free_mib < 64
        or args.case_deadline_seconds * 1000 < args.statement_timeout_ms
    ):
        cli.error("Invalid storage or deadline limits.")
    if args.axis:
        if not args.execute or any(
            getattr(args, k) is None for k in ("query", "variant", "reader_env", "queries")
        ):
            cli.error(
                "Execution requires --execute, --query, --variant, --reader-env and --queries."
            )
        try:
            schedule(args.axis, args.variant, args.query, args.repeats, args.alternate)
        except base.Refused:
            cli.error("Invalid experiment schedule.")
    elif len(args.compare) > 20:
        cli.error("At most 20 collections.")
    try:
        result = compare(args) if args.compare else run(args)
        print(json.dumps({"status": "ok" if result == 0 else "incomplete"}))
        return result
    except base.Refused as error:
        print(json.dumps({"status": "error", "code": error.args[0]}))
    except FileExistsError:
        print('{"status":"error","code":"output_already_exists"}')
    except Exception:
        print('{"status":"error","code":"diagnostic_failed"}')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
