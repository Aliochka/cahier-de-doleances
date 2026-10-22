"""P3: one bounded lexical diagnostic per invocation; no public H1 changes.

Only pinned H1's final call may be intercepted. Raw plans are private. Expression
evidence in EXPLAIN is not a physical function-call or decompression counter.
"""

import argparse
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cahier_rag.config import load_settings
from cahier_rag.search.service.control import Budget
from cahier_rag.search.service.reader import check_reader_role, create_search_engine
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text

if __package__:
    from . import decompose_h1_lexical as p2
else:
    import decompose_h1_lexical as p2

p1, base = p2.p1, p2.base
P2_SHA = "0c4474464e8389cd537ccb82533d87f1678b3dc87c5c968c77e434d4b803039d"
AGGREGATED = ("zero", "idf", "terms", "rank", "idf-terms", "idf-rank", "terms-rank", "full")
VARIANTS = (*AGGREGATED, "top50", "touch", "classify", "observe")
WHERE = f"FROM rag_full.documents d\n                WHERE {p2.FILTERS} AND d.search_vector @@ CAST(:query AS tsquery)"
COUNTERS = (
    "heap_blks_hit",
    "heap_blks_read",
    "idx_blks_hit",
    "idx_blks_read",
    "toast_blks_hit",
    "toast_blks_read",
    "tidx_blks_hit",
    "tidx_blks_read",
)
OBSERVATIONS = {
    "counters": """SELECT heap_blks_hit, heap_blks_read, idx_blks_hit, idx_blks_read,
        toast_blks_hit, toast_blks_read, tidx_blks_hit, tidx_blks_read
        FROM pg_statio_all_tables WHERE relid='rag_full.documents_full'::regclass""",
    "reset": """SELECT pg_postmaster_start_time()::text AS server_started,
        stats_reset::text AS stats_reset FROM pg_stat_database WHERE datname=current_database()""",
    "storage": """SELECT c.reltoastrelid::bigint AS toast_oid,
        pg_relation_size(c.oid) AS heap_bytes, pg_indexes_size(c.oid) AS index_bytes,
        CASE WHEN c.reltoastrelid<>0 THEN pg_total_relation_size(c.reltoastrelid) END AS toast_total_bytes,
        a.attstorage::text AS storage, a.attcompression::text AS compression,
        (SELECT avg_width FROM pg_stats WHERE schemaname='rag_full'
         AND tablename='documents_full' AND attname='search_vector' LIMIT 1) AS avg_width
        FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE c.oid='rag_full.documents_full'::regclass AND a.attname='search_vector'""",
}
CLASSIFY_FIELDS = (
    "sampled",
    "compressed",
    "uncompressed",
    "pglz",
    "lz4",
    "stored_bytes_min",
    "stored_bytes_max",
    "stored_bytes_avg",
    "lexemes_avg",
)
EXTRA_ERRORS = (
    "p3_tool_mismatch",
    "component_recomposition_mismatch",
    "invalid_variant",
    "classification_invalid",
    "invalid_summary",
)


def verify_sources():
    if base.digest(Path(p2.__file__).read_bytes()) != P2_SHA:
        raise base.Refused("p3_tool_mismatch")
    p2.verify_sources()


def components(terms, parameters, original_score):
    # Reuse the actual builder, rather than a separately maintained H1 formula.
    copied = dict(parameters)
    if not terms:
        raise base.Refused("component_recomposition_mismatch")
    try:
        built = TunedSearch.score_expression(terms, copied)
    except (KeyError, TypeError, IndexError):
        raise base.Refused("component_recomposition_mismatch") from None
    if built != original_score or copied != parameters:
        raise base.Refused("component_recomposition_mismatch")
    parts = built.split("\n")
    if len(parts) != 3 or not all(p.lstrip().startswith("+ ") for p in parts[1:]):
        raise base.Refused("component_recomposition_mismatch")
    return (parts[0], *(p.strip()[2:] for p in parts[1:]))


def diagnostic_sql(original, score, terms, parameters, variant):
    # P2 independently checks the entire final SELECT/WHERE/ORDER/LIMIT template.
    p2.derived_sql(original, score, "top50")
    a, b, c = components(terms, parameters, score)
    if variant in ("top50", "observe"):
        return original
    if variant == "classify":
        # Fixed 0.1% block sample, fixed seed, hard row cap; never full population.
        # TABLESAMPLE requires the physical partition, not its partitioned parent.
        sample = WHERE.replace(
            "rag_full.documents d",
            "rag_full.documents_full d TABLESAMPLE SYSTEM (0.1) REPEATABLE (2703)",
        )
        return (
            """SELECT count(*) AS sampled,
            count(*) FILTER (WHERE compression IS NOT NULL) AS compressed,
            count(*) FILTER (WHERE compression IS NULL) AS uncompressed,
            count(*) FILTER (WHERE compression='pglz') AS pglz,
            count(*) FILTER (WHERE compression='lz4') AS lz4,
            min(stored_bytes) AS stored_bytes_min, max(stored_bytes) AS stored_bytes_max,
            avg(stored_bytes)::float8 AS stored_bytes_avg, avg(lexemes)::float8 AS lexemes_avg
            FROM (SELECT pg_column_size(d.search_vector) AS stored_bytes,
                  pg_column_compression(d.search_vector) AS compression,
                  length(d.search_vector) AS lexemes """
            + sample
            + " LIMIT 512) sampled_vectors"
        )
    expressions = {
        "zero": "0::float8",
        "idf": a,
        "terms": b,
        "rank": c,
        "idf-terms": f"({a}+{b})",
        "idf-rank": f"({a}+{c})",
        "terms-rank": f"({b}+{c})",
        "full": score,
        "touch": "length(d.search_vector)::float8",
    }
    if variant not in expressions:
        raise base.Refused("invalid_variant")
    return f"SELECT count(*) AS matched, sum(({expressions[variant]})) AS sink " + WHERE


class ComponentConnection(base.ExplainConnection):
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
            self.guard.stage = "component_setup"
            # Reuse P1/P2 controls in observe-only mode: no work_mem or I/O SET.
            self.guard.metadata.update(self.wire.configure_experiment(self.guard))
            self.guard.metadata.update(
                h1_sql_template=sql,
                measured_sql_template=measured,
                h1_sql_sha256=base.digest(sql.encode()),
                sql_sha256=base.digest(measured.encode()),
                parameters_sha256=p1.fingerprint(parameters),
                parameter_types={k: type(v).__name__ for k, v in parameters.items()},
                lexeme_count=len(caller.f_locals["terms"]),
            )
            if self.guard.variant == "observe":
                raise base.PlanCaptured(None)
            classify = self.guard.variant == "classify"
            self.wire.statement_ms = 2000 if classify else self.guard.measurement_ms
            emitted = text(measured if classify else p1.EXPLAIN + measured)
            emitted = emitted.bindparams(
                *(v for k, v in statement._bindparams.items() if k in emitted._bindparams)
            )
            self.guard.stage = "classification" if classify else "ranking"
            try:
                result = self.wire.execute(emitted, parameters)
                payload = dict(result.mappings().one()) if classify else result.scalar_one()
            finally:
                self.guard.metadata["ranking_statement_timeout_ms"] = self.wire.last_timeout_ms
            self.guard.stage = "result_received"
            raise base.PlanCaptured(payload)
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and sql == "SET LOCAL statement_timeout='30s'"
        ):
            return None
        return super().execute(statement, parameters)


class ComponentGuard(p2.ExperimentGuard):
    @contextmanager
    def _connect(self, engine):
        self.budget.check()
        with engine.connect() as raw:
            raw = raw.execution_options(postgresql_readonly=True)
            transaction = raw.begin()
            state = {"target": engine is self.target, "rollback": "pending"}
            self.metadata["transactions"].append(state)
            try:
                wire = p2.ExperimentWire(raw, self.budget, 2000, self.lock_ms)
                state.update(wire.initialize())
                connection = ComponentConnection(wire, self, target=engine is self.target)
                check_reader_role(connection)
                yield connection
            finally:
                transaction.rollback()
                state["rollback"] = "done"
        self.budget.check()


def collect_case(
    source, target, query, *, variant, mode="off", statement_ms=60000, lock_ms=200, seconds=90
):
    if variant not in VARIANTS:
        raise base.Refused("invalid_variant")
    p2.validate("costs", "top50", mode, "observe", statement_ms, lock_ms, seconds)
    guard = ComponentGuard(
        source,
        target,
        Budget(seconds),
        axis="costs",
        variant=variant,
        mode=mode,
        io_policy="observe",
        statement_ms=statement_ms,
        lock_ms=lock_ms,
    )
    engine = TunedSearch(base.ExplainStore(guard), statistics=True, prefilter=None)
    guard.engine_recipe = engine
    started, payload = time.monotonic(), None
    status, code = "error", "ranking_not_captured"
    try:
        with guard.budget.monitor(), guard.budget.phase("p3_collection"):
            try:
                engine.lexical(query, limit=50, questionnaire_id=None, unit_type=None, split=None)
            except base.PlanCaptured as captured:
                payload = captured.plan
                status, code = ("observed" if variant == "observe" else "ok"), "none"
    except Exception as error:
        status, code = p1.error_status(error)
        if isinstance(error, base.Refused) and error.args[0] in EXTRA_ERRORS:
            code = error.args[0]
    return payload, {
        "status": status,
        "code": code,
        "stage": guard.stage,
        "elapsed_seconds": time.monotonic() - started,
        **guard.metadata,
    }


def observe(engine, name):
    """One fixed lightweight query per fresh read-only transaction; no retry."""
    if name not in OBSERVATIONS:
        raise base.Refused("sql_not_allowlisted")
    state = {
        "status": "unavailable",
        "rollback": "pending",
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    budget = Budget(5)
    try:
        with budget.monitor(), budget.phase("p3_observation"), engine.connect() as raw:
            raw = raw.execution_options(postgresql_readonly=True)
            transaction = raw.begin()
            try:
                wire = p1.AnalyzeWire(raw, budget, 2000, 200)
                state["limits"] = wire.initialize()
                guard = SimpleNamespace(halted=False, allowed=base.preparation_allowlist())
                check_reader_role(base.ExplainConnection(wire, guard, target=True))
                result = wire.execute(text(OBSERVATIONS[name])).mappings().one_or_none()
                state.update(
                    status="ok" if result is not None else "unavailable",
                    values=dict(result) if result is not None else None,
                )
            finally:
                transaction.rollback()
                state["rollback"] = "done"
    except Exception as error:
        state["failure_status"], state["code"] = p1.error_status(error)
    state["completed_utc"] = datetime.now(timezone.utc).isoformat()
    return state


def safe_observation(name, observation):
    safe = {
        k: observation[k]
        for k in ("status", "rollback", "started_utc", "completed_utc")
        if k in observation
    }
    values = observation.get("values") or {}
    allowed = (
        COUNTERS
        if name == "counters"
        else ("toast_oid", "heap_bytes", "index_bytes", "toast_total_bytes", "avg_width")
    )
    safe["values"] = {k: v for k, v in values.items() if k in allowed and base.number(v)}
    if name == "storage":
        for k, choices in (("storage", ("p", "e", "m", "x")), ("compression", ("", "p", "l"))):
            if values.get(k) in choices:
                safe["values"][k] = values[k]
    return safe


def toast_delta(before, after):
    # Reset markers are private and compared without exporting database identity.
    if any(
        s["counters"].get("status") != "ok" or s["reset"].get("status") != "ok"
        for s in (before, after)
    ):
        return {"status": "unavailable"}
    if before["reset"].get("values") != after["reset"].get("values"):
        return {"status": "reset_detected"}
    a, b = before["counters"]["values"], after["counters"]["values"]
    if not all(base.number(a.get(k)) and base.number(b.get(k)) for k in COUNTERS):
        return {"status": "unavailable"}
    if any(b[k] < a[k] for k in COUNTERS):
        return {"status": "reset_detected"}
    return {
        "status": "global_window_not_backend_attributed",
        "blocks": {k: b[k] - a[k] for k in COUNTERS},
        "warning": "publication_may_lag_concurrent_activity_not_decompression_counts",
    }


def summarize(plan, variant, lexemes):
    summary = p2.summarize(plan)
    placements, aggregations, maximum_cases, rank_sink, touch_sink, sum_sink = (
        [],
        [],
        0,
        False,
        False,
        False,
    )

    def visit(node, path):
        nonlocal maximum_cases, rank_sink, touch_sink, sum_sink
        # Ignore literals: a tsquery string must not fake function/CASE evidence.
        output = [
            re.sub(r"'(?:''|[^'])*'", "''", s) for s in node.get("Output", []) if isinstance(s, str)
        ]
        cases = max((len(re.findall(r"\bCASE\b", s, re.I)) for s in output), default=0)
        rank = any("ts_rank_cd(" in s for s in output)
        touch = any(re.search(r"\blength\(", s) for s in output)
        sums = [
            s
            for s in output
            if re.search(r"\bsum\(", s)
            and base.number(node.get("Actual Loops"))
            and node["Actual Loops"] > 0
        ]
        maximum_cases = max(
            maximum_cases, max((len(re.findall(r"\bCASE\b", s, re.I)) for s in sums), default=0)
        )
        rank_sink |= any("ts_rank_cd(" in s for s in sums)
        touch_sink |= any(re.search(r"\blength\(", s) is not None for s in sums)
        sum_sink |= bool(sums)
        if cases or rank or touch or sums:
            placements.append(
                {
                    "path": path,
                    "case_occurrences_max": cases,
                    "rank_in_output": rank,
                    "touch_in_output": touch,
                    "sum_in_output": bool(sums),
                    "executed_node": base.number(node.get("Actual Loops"))
                    and node["Actual Loops"] > 0,
                }
            )
        if node.get("Node Type") == "Aggregate":
            aggregations.append(
                {"path": path, **{k: node[k] for k in ("Strategy", "Partial Mode") if k in node}}
            )
        for i, child in enumerate(node.get("Plans", [])):
            visit(child, f"{path}.{i}")

    visit(plan[0]["Plan"], "0")
    coverage_count = {
        "idf": 1,
        "terms": 1,
        "idf-terms": 2,
        "idf-rank": 1,
        "terms-rank": 1,
        "full": 2,
    }.get(variant, 0)
    required_rank = variant in ("rank", "idf-rank", "terms-rank", "full")
    consumed = (
        sum_sink
        and maximum_cases >= coverage_count * lexemes
        and (not required_rank or rank_sink)
        and (variant != "touch" or touch_sink)
    )
    if variant == "top50":
        consumed = None
    summary.update(
        expression_placements=placements,
        aggregation_shape=aggregations,
        aggregation_sha256=p1.fingerprint(aggregations),
        placement_sha256=p1.fingerprint(placements),
        consumption_evidence="original_top50"
        if consumed is None
        else "sum_argument_present"
        if consumed
        else "unverified_expression_removed_or_rewritten",
        consumption_limit="EXPLAIN_evidence_not_physical_call_count",
        parity="not_tested_aggregate_sum_is_not_score_parity",
    )
    return summary


def safe_classification(payload):
    if set(payload) != set(CLASSIFY_FIELDS) or not all(
        v is None or base.number(v) for v in payload.values()
    ):
        raise base.Refused("classification_invalid")
    if not 0 <= payload["sampled"] <= 512:
        raise base.Refused("classification_invalid")
    return {
        **payload,
        "externalized_count": None,
        "inline_compressed_count": None,
        "storage_location": "not_determined_by_accessible_SQL_functions",
        "sample_percent": 0.1,
        "seed": 2703,
        "row_cap": 512,
        "warning": "block_sample_biased_not_full_population_performance",
    }


def comparison(rows):
    results = []
    keys = (
        "h1_sql_sha256",
        "parameters_sha256",
        "generation_sha256",
        "settings_control_sha256",
        "tool_sha256",
        "limits_sha256",
    )
    for i, current in enumerate(rows):
        for j, prior in enumerate(rows[:i]):
            if current["query_id"] != prior["query_id"]:
                continue
            controlled = all(current.get(k) and current.get(k) == prior.get(k) for k in keys)
            controlled = bool(controlled and current["status"] == prior["status"] == "ok")
            fields = {
                "same_access_strategy": ("access_sha256",),
                "same_parallelism": ("workers_planned", "workers_launched"),
                "same_aggregation": ("aggregation_sha256",),
                "same_projection_placement": ("placement_sha256",),
                "same_cardinality_approx": ("candidate_rows_approx",),
            }
            flags = {
                label: all(
                    current.get(k) is not None and current.get(k) == prior.get(k) for k in names
                )
                if controlled
                else None
                for label, names in fields.items()
            }
            results.append(
                {
                    "rows": [j, i],
                    "controlled_conditions": controlled,
                    **flags,
                    "review_required": not controlled
                    or not all(v is True for v in flags.values())
                    or any(
                        r.get("consumption_evidence")
                        not in ("sum_argument_present", "original_top50")
                        for r in (current, prior)
                    ),
                    "interpretation": "observed_differences_not_exact_CPU_cost_no_score_parity",
                }
            )
    return {"rows": rows, "comparisons": results}


def safe_row(record):
    if (
        record.get("variant") not in VARIANTS
        or record.get("query_id") not in base.CASE_IDS
        or record.get("status") not in (*p1.STATUSES, "observed")
    ):
        raise base.Refused("invalid_summary")
    result = {k: record[k] for k in ("variant", "query_id", "status")}
    delta = record.get("toast_delta", {})
    for name, counter in (
        ("toast_hit_delta", "toast_blks_hit"),
        ("toast_read_delta", "toast_blks_read"),
        ("toast_index_hit_delta", "tidx_blks_hit"),
        ("toast_index_read_delta", "tidx_blks_read"),
    ):
        value = delta.get("blocks", {}).get(counter)
        result[name] = value if base.number(value) else None
    if record.get("consumption_evidence") in (
        "original_top50",
        "sum_argument_present",
        "unverified_expression_removed_or_rewritten",
    ):
        result["consumption_evidence"] = record["consumption_evidence"]
    for k in (*p1.TABLE_NUMBERS, "lexeme_count", "work_mem_effective_bytes"):
        result[k] = record.get(k) if base.number(record.get(k)) else None
    for k in (*p2.HASHES, "aggregation_sha256", "placement_sha256"):
        if isinstance(record.get(k), str) and re.fullmatch("[0-9a-f]{64}", record[k]):
            result[k] = record[k]
    codes = (*p2.ERRORS, *EXTRA_ERRORS)
    result["code"] = record.get("code") if record.get("code") in codes else "measurement_failed"
    return result


def table(rows):
    keys = (
        "query_id",
        "variant",
        "status",
        "execution_ms",
        "candidate_rows_approx",
        "workers_planned",
        "workers_launched",
        "shared_hit_blocks",
        "shared_read_blocks",
        "toast_hit_delta",
        "toast_read_delta",
        "consumption_evidence",
    )
    return (
        "\n".join(
            [
                "| " + " | ".join(keys) + " |",
                "| " + " | ".join("---" for _ in keys) + " |",
                *("| " + " | ".join(str(r.get(k, "n/a")) for k in keys) + " |" for r in rows),
            ]
        )
        + "\n"
    )


def run(args):
    verify_sources()
    queries = base.read_cases(args.queries)
    p2.validate(
        "costs",
        "top50",
        args.jit,
        "observe",
        args.statement_timeout_ms,
        args.lock_timeout_ms,
        args.case_deadline_seconds,
    )
    settings = load_settings(env_file=args.reader_env, environ={})
    limits = {
        "statement_ms": args.statement_timeout_ms,
        "lock_ms": args.lock_timeout_ms,
        "seconds": args.case_deadline_seconds,
    }
    record = {"variant": args.variant, "query_id": args.query, "status": "pending", "code": "none"}
    manifest = {
        "base_commit": base.BASE_COMMIT,
        "tool_sha256": base.digest(Path(__file__).read_bytes()),
        "p2_sha256": P2_SHA,
        "h1_sources_sha256": base.SOURCE_HASHES,
        "queries_sha256": base.QUERY_SHA256,
        "limits": limits,
        "metadata": {},
    }
    with p1.exclusive_output(args.output_dir):
        storage = p1.Storage(
            args.output_dir,
            maximum=args.max_output_mib * p1.MIB,
            minimum_free=args.min_free_mib * p1.MIB,
        )
        engines = []

        def save():
            storage.write("manifest.private.json", manifest)
            storage.write("summary.redacted.json", {"format": "p3-v1", "runs": [record]})
            storage.write("comparison.redacted.md", table([safe_row(record)]), as_text=True)

        save()
        try:
            storage.check_measurement()
            for url in (settings.require_source_url(), settings.require_rag_url()):
                engines.append(create_search_engine(url))
            record["status"] = "running"
            save()
            # Fresh observation transactions, closed before H1 opens its nested ones.
            before = {k: observe(engines[1], k) for k in ("reset", "counters")}
            manifest["before"] = before
            payload, meta = collect_case(
                *engines, queries[args.query], variant=args.variant, mode=args.jit, **limits
            )
            manifest["metadata"] = meta
            record.update({k: meta[k] for k in ("status", "code", "elapsed_seconds")})
            after = {k: observe(engines[1], k) for k in ("reset", "counters")}
            manifest["after"] = after
            record["toast_delta"] = toast_delta(before, after)
            record["observations"] = {
                "before": safe_observation("counters", before["counters"]),
                "after": safe_observation("counters", after["counters"]),
            }
            if args.variant == "observe":
                observed = observe(engines[1], "storage")
                manifest["storage"] = observed
                record["storage"] = safe_observation("storage", observed)
            if meta["status"] in ("ok", "observed"):
                record.update(
                    {
                        k: meta[k]
                        for k in (
                            "h1_sql_sha256",
                            "sql_sha256",
                            "parameters_sha256",
                            "settings_control_sha256",
                            "lexeme_count",
                        )
                    }
                )
                record.update(
                    generation_sha256=p1.fingerprint(meta["generation"]),
                    tool_sha256=manifest["tool_sha256"],
                    limits_sha256=p1.fingerprint(limits),
                    work_mem_effective_bytes=meta["controls_after"]["work_mem_bytes"],
                    effective_jit_off=meta["settings_effective"]["jit"] == "off",
                    diagnostic_derived=args.variant not in ("top50", "observe"),
                )
                if args.variant == "classify":
                    record["classification"] = safe_classification(payload)
                elif payload is not None:
                    safe = summarize(payload, args.variant, meta["lexeme_count"])
                    if args.jit == "off" and (
                        safe["jit"]["present"]
                        or any(
                            n["jit"]["present"] or any(w["jit"]["present"] for w in n["workers"])
                            for n in safe["nodes"]
                        )
                    ):
                        raise base.Refused("jit_off_plan_contains_jit")
                    storage.write("plan.private.json", payload, limit=p1.PLAN_LIMIT)
                    storage.write("plan.summary.redacted.json", safe, limit=p1.PLAN_LIMIT)
                    record.update({k: v for k, v in safe.items() if k != "nodes"})
                    record["review_required"] = safe["consumption_evidence"].startswith(
                        "unverified"
                    )
        except KeyboardInterrupt:
            record.update(status="error", code="interrupted")
        except Exception as error:
            status, code = p1.error_status(error)
            if isinstance(error, base.Refused) and error.args[0] in EXTRA_ERRORS:
                code = error.args[0]
            record.update(status=status, code=code)
        finally:
            for engine in engines:
                engine.dispose()
            save()
    return 0 if record["status"] in ("ok", "observed") else 1


def compare(args):
    rows = []
    for directory in args.compare:
        path = directory / "summary.redacted.json"
        if path.stat().st_size > p1.REPORT_LIMIT:
            raise base.Refused("invalid_summary")
        data = json.loads(path.read_bytes())
        if data.get("format") != "p3-v1" or len(data["runs"]) != 1:
            raise base.Refused("invalid_summary")
        rows.extend(safe_row(r) for r in data["runs"])
    with p1.exclusive_output(args.output_dir):
        storage = p1.Storage(
            args.output_dir,
            maximum=args.max_output_mib * p1.MIB,
            minimum_free=args.min_free_mib * p1.MIB,
        )
        storage.write("comparison.redacted.json", comparison(rows))
        storage.write("comparison.redacted.md", table(rows), as_text=True)
    return 0


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--variant", choices=VARIANTS)
    group.add_argument("--compare", nargs="+", type=Path)
    cli.add_argument("--execute", action="store_true")
    cli.add_argument("--query", choices=base.CASE_IDS)
    cli.add_argument("--jit", choices=("off", "current"), default="off")
    cli.add_argument("--reader-env", type=Path)
    cli.add_argument("--queries", type=Path)
    cli.add_argument("--output-dir", type=Path, required=True)
    for name, maximum, default in (
        ("statement-timeout-ms", 300000, 60000),
        ("case-deadline-seconds", 360, 90),
        ("lock-timeout-ms", 1000, 200),
        ("max-output-mib", 256, 64),
        ("min-free-mib", 1048576, 512),
    ):
        cli.add_argument("--" + name, type=base.bounded_integer(maximum), default=default)
    args = cli.parse_args(argv)
    if (
        args.max_output_mib < 32
        or args.min_free_mib < 64
        or args.case_deadline_seconds * 1000 < args.statement_timeout_ms
    ):
        cli.error("Invalid storage or deadline limits.")
    if args.variant and (
        not args.execute
        or any(getattr(args, k) is None for k in ("query", "reader_env", "queries"))
    ):
        cli.error("Requires --execute, --query, --reader-env and --queries.")
    if args.compare and len(args.compare) > 20:
        cli.error("At most 20 input collections.")
    os.umask(0o077)
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
