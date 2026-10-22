"""Opt-in, bounded execution of the exact H1 lexical ranking, never hydration.

The non-executing explain_h1_lexical tool is imported unchanged. Its independent
CLI, SQL policy and limits are not changed or monkeypatched by this tool.
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.config import load_settings
from cahier_rag.fullcorpus.search import FILTERS
from cahier_rag.search.service.control import Budget, SearchTimeout
from cahier_rag.search.service.reader import check_reader_role, create_search_engine
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

if __package__:
    from . import explain_h1_lexical as base
else:
    import explain_h1_lexical as base

EXPLAIN = "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON) "
BASE_TOOL_SHA = "8e7e00ca1a1cafb1e63b7bfd61069a8e585ffe28b3eec702ae117d6c3c401511"
MIB = 1024 * 1024
PLAN_LIMIT = 4 * MIB
REPORT_LIMIT = 8 * MIB
RESERVE = 24 * MIB  # Kept available for statuses, summaries and atomic replacement.
INITIAL = (
    ("fiscalite-05-current", "fiscalite-05", "current"),
    ("democratie-02-current", "democratie-02", "current"),
    ("democratie-02-off", "democratie-02", "off"),
    ("fiscalite-01-current", "fiscalite-01", "current"),
    ("fiscalite-01-off", "fiscalite-01", "off"),
)
GROUPS = {"initial": INITIAL, "democratie-pair": INITIAL[1:3], "fiscalite-pair": INITIAL[3:5]}
CASES = {case[0]: case for case in INITIAL}
SETTINGS = tuple(
    dict.fromkeys(
        (
            *base.PLANNER_SETTINGS,
            "track_io_timing",
            "temp_file_limit",
            "parallel_leader_participation",
            "max_parallel_workers",
            "max_worker_processes",
            "default_text_search_config",
        )
    )
)
SETTING_SQL = """SELECT name, setting FROM pg_settings
    WHERE name=ANY(:names) OR category LIKE 'Query Tuning/%' ORDER BY name"""
NUMERIC_FIELDS = (
    "Startup Cost",
    "Total Cost",
    "Plan Rows",
    "Plan Width",
    "Actual Startup Time",
    "Actual Total Time",
    "Actual Rows",
    "Actual Loops",
    "Rows Removed by Filter",
    "Rows Removed by Index Recheck",
    "Workers Planned",
    "Workers Launched",
    "Worker Number",
    "Shared Hit Blocks",
    "Shared Read Blocks",
    "Shared Dirtied Blocks",
    "Shared Written Blocks",
    "Local Hit Blocks",
    "Local Read Blocks",
    "Local Dirtied Blocks",
    "Local Written Blocks",
    "Temp Read Blocks",
    "Temp Written Blocks",
    "I/O Read Time",
    "I/O Write Time",
    "Shared I/O Read Time",
    "Shared I/O Write Time",
    "Local I/O Read Time",
    "Local I/O Write Time",
    "Temp I/O Read Time",
    "Temp I/O Write Time",
    "Sort Space Used",
    "Exact Heap Blocks",
    "Lossy Heap Blocks",
    "Peak Memory Usage",
    "Disk Usage",
    "HashAgg Batches",
)
STRUCTURAL_FIELDS = (
    "Node Type",
    "Parent Relationship",
    "Parallel Aware",
    "Async Capable",
    "Join Type",
    "Schema",
    "Relation Name",
    "Index Name",
    "Scan Direction",
    "Workers Planned",
    "Output",
    "Filter",
    "Index Cond",
    "Recheck Cond",
    "Sort Key",
    "Group Key",
    "Hash Cond",
    "Merge Cond",
    "Join Filter",
    "Strategy",
    "Partial Mode",
)
TABLE_NUMBERS = (
    "planning_ms",
    "execution_ms",
    "elapsed_seconds",
    "jit_total_ms",
    "jit_generation_ms",
    "jit_inlining_ms",
    "jit_optimization_ms",
    "jit_emission_ms",
    "shared_hit_blocks",
    "shared_read_blocks",
    "temp_read_blocks",
    "temp_written_blocks",
    "candidate_rows_approx",
    "workers_planned",
    "workers_launched",
)
HASH_FIELDS = (
    "structure_sha256",
    "estimates_sha256",
    "sql_sha256",
    "parameters_sha256",
    "generation_sha256",
    "settings_other_sha256",
    "limits_sha256",
    "sources_sha256",
    "tool_sha256",
)
STATUSES = ("pending", "running", "ok", "timeout", "error", "skipped")
ERROR_CODES = (
    "none",
    "statement_timeout",
    "case_timeout",
    "lock_timeout",
    "database_error",
    "measurement_failed",
    "sql_not_allowlisted",
    "unexpected_statement",
    "unexpected_ranking",
    "transaction_not_read_only",
    "transaction_timeout_not_bounded",
    "unexpected_timeout_format",
    "corpus_generation_changed",
    "jit_current_not_on",
    "jit_setting_mismatch",
    "settings_changed_beyond_jit",
    "ranking_not_captured",
    "unexpected_plan_format",
    "plan_missing_actual_statistics",
    "jit_off_plan_contains_jit",
    "plan_too_large",
    "storage_limit",
    "low_disk_space",
    "not_run_after_error",
    "reader_refused",
    "interrupted",
    "output_limit",
)


def fingerprint(value):
    return base.digest(json.dumps(value, sort_keys=True, allow_nan=False).encode())


def verify_sources():
    if base.digest(Path(base.__file__).read_bytes()) != BASE_TOOL_SHA:
        raise base.Refused("base_explain_tool_mismatch")
    base.verify_sources()


class AnalyzeWire(base.Wire):
    def execute(self, statement, parameters=None):
        self.budget.check()
        remaining = min(self.statement_ms, max(1, int(self.budget.remaining() * 1000)))
        with self.budget.connection(self.raw.connection.driver_connection):
            self.raw.execute(
                text("SELECT set_config('statement_timeout', :value, true)"),
                {"value": str(remaining)},
            )
            self.last_timeout_ms = remaining
            result = self.raw.execute(statement, parameters if parameters is not None else {})
        self.budget.check()
        return result

    def configure_measurement(self, mode, statement_ms):
        before = dict(self.execute(text(SETTING_SQL), {"names": list(SETTINGS)}).all())
        if mode == "current" and before.get("jit") != "on":
            raise base.Refused("jit_current_not_on")
        if mode == "off":
            self.execute(text("SELECT set_config('jit', 'off', true)"))
        after = dict(self.execute(text(SETTING_SQL), {"names": list(SETTINGS)}).all())
        if after.get("jit") != ("on" if mode == "current" else "off"):
            raise base.Refused("jit_setting_mismatch")

        def other(settings):
            return {k: v for k, v in settings.items() if k != "jit"}

        if other(before) != other(after):
            raise base.Refused("settings_changed_beyond_jit")
        self.statement_ms = statement_ms
        # This read sets and then verifies the actual measurement timeout, not
        # the 2-second preparation ceiling. No historic 30s timeout is forwarded.
        effective = (
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
        if effective["read_only"] != "on":
            raise base.Refused("transaction_not_read_only")
        if (
            not 0 < base.timeout_ms(effective["statement_timeout"]) <= statement_ms
            or not 0 < base.timeout_ms(effective["lock_timeout"]) <= self.lock_ms
        ):
            raise base.Refused("transaction_timeout_not_bounded")
        if effective["jit"] != after["jit"]:
            raise base.Refused("jit_setting_mismatch")
        return {
            "settings_before": before,
            "settings_effective": after,
            "effective_limits": dict(effective),
            "settings_other_sha256": fingerprint(other(after)),
        }


class AnalyzeConnection(base.ExplainConnection):
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
            # Defense in depth: only the exact final template from pinned H1.
            expected = f"""SELECT d.document_id,{caller.f_locals["score"]} AS score FROM rag_full.documents d
                WHERE {FILTERS} AND d.search_vector @@ CAST(:query AS tsquery)
                ORDER BY score DESC,d.document_id COLLATE "C" LIMIT :limit"""
            if sql != expected:
                raise base.Refused("unexpected_ranking")
            self.guard.halted = True
            self.guard.captures += 1
            self.guard.stage = "ranking_setup"
            self.guard.metadata.update(
                self.wire.configure_measurement(
                    self.guard.mode,
                    self.guard.measurement_ms,
                )
            )
            self.guard.metadata.update(
                {
                    "sql_sha256": base.digest(sql.encode()),
                    "parameters_sha256": fingerprint(parameters),
                    "parameter_types": {k: type(v).__name__ for k, v in parameters.items()},
                }
            )
            explained = text(EXPLAIN + sql).bindparams(*statement._bindparams.values())
            self.guard.stage = "ranking"
            self.wire.last_timeout_ms = None
            try:
                plan = self.wire.execute(explained, parameters).scalar_one()
            finally:
                if self.wire.last_timeout_ms is not None:
                    self.guard.metadata["ranking_statement_timeout_ms"] = self.wire.last_timeout_ms
            self.guard.stage = "plan_received"
            raise base.PlanCaptured(plan)
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and sql == "SET LOCAL statement_timeout='30s'"
        ):
            return None
        # All other statements still pass the unchanged non-executing allowlist.
        return super().execute(statement, parameters)


class AnalyzeGuard(base.ExplainGuard):
    def __init__(self, source, target, budget, *, mode, statement_ms, lock_ms):
        super().__init__(source, target, budget, statement_ms=2000, lock_ms=lock_ms)
        self.mode, self.measurement_ms = mode, statement_ms
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
                wire = AnalyzeWire(raw, self.budget, 2000, self.lock_ms)
                state.update(wire.initialize())
                connection = AnalyzeConnection(wire, self, target=engine is self.target)
                check_reader_role(connection)
                yield connection
            finally:
                transaction.rollback()
                state["rollback"] = "done"
        self.budget.check()


def error_status(error):
    if isinstance(error, SearchTimeout):
        return "timeout", "case_timeout"
    if isinstance(error, DBAPIError):
        code = getattr(error.orig, "pgcode", None)
        if code == "57014":
            return "timeout", "statement_timeout"
        return "error", "lock_timeout" if code == "55P03" else "database_error"
    if isinstance(error, base.Refused) and error.args[0] in ERROR_CODES:
        return "error", error.args[0]
    return "error", "measurement_failed"


def collect_case(source, target, query, *, mode, statement_ms=60000, lock_ms=200, seconds=90):
    if (
        mode not in ("current", "off")
        or not 1 <= statement_ms <= 300000
        or not 1 <= lock_ms <= 1000
        or not 1 <= seconds <= 360
        or seconds * 1000 < statement_ms
    ):
        raise base.Refused("invalid_measurement_limits")
    budget = Budget(seconds)
    guard = AnalyzeGuard(
        source, target, budget, mode=mode, statement_ms=statement_ms, lock_ms=lock_ms
    )
    engine = TunedSearch(base.ExplainStore(guard), statistics=True, prefilter=None)
    guard.engine_recipe = engine
    started = time.monotonic()
    plan = None
    status, code = "error", "ranking_not_captured"
    try:
        with budget.monitor(), budget.phase("analyze_collection"):
            try:
                engine.lexical(query, limit=50, questionnaire_id=None, unit_type=None, split=None)
            except base.PlanCaptured as captured:
                plan = captured.plan
                status, code = "ok", "none"
    except Exception as error:
        status, code = error_status(error)
    return plan, {
        "status": status,
        "code": code,
        "stage": guard.stage,
        "elapsed_seconds": time.monotonic() - started,
        **guard.metadata,
    }


def jit_summary(jit):
    result = {"present": isinstance(jit, dict) and bool(jit)}
    if not isinstance(jit, dict):
        return result
    if base.number(jit.get("Functions")):
        result["Functions"] = jit["Functions"]
    result["Options"] = {
        k: v
        for k, v in jit.get("Options", {}).items()
        if k in ("Inlining", "Optimization", "Expressions", "Deforming") and type(v) is bool
    }
    result["Timing"] = {
        k: v
        for k, v in jit.get("Timing", {}).items()
        if k in ("Generation", "Deform", "Inlining", "Optimization", "Emission", "Total")
        and base.number(v)
    }
    return result


def metrics(obj):
    result = {k: obj[k] for k in NUMERIC_FIELDS if base.number(obj.get(k))}
    if obj.get("Sort Method") in ("top-N heapsort", "quicksort", "external merge", "external sort"):
        result["Sort Method"] = obj["Sort Method"]
    if obj.get("Sort Space Type") in ("Memory", "Disk"):
        result["Sort Space Type"] = obj["Sort Space Type"]
    return result


def summarize(plan):
    skeleton = base.summarize(plan)
    root = plan[0]
    if not all(base.number(root.get(k)) for k in ("Planning Time", "Execution Time")):
        raise base.Refused("plan_missing_actual_statistics")
    nodes, structural, estimates = [], [], []

    def visit(node, path):
        item = {"path": path, **metrics(node)}
        # Reuse only the positive structural projection from the original tool.
        safe = skeleton["nodes"][len(nodes)]
        item.update(safe)
        item["jit"] = jit_summary(node.get("JIT"))
        item["workers"] = [
            {**metrics(worker), "jit": jit_summary(worker.get("JIT"))}
            for worker in node.get("Workers", [])
        ]
        nodes.append(item)
        structural.append({k: node[k] for k in STRUCTURAL_FIELDS if k in node} | {"path": path})
        estimates.append(
            {
                k: node[k]
                for k in ("Startup Cost", "Total Cost", "Plan Rows", "Plan Width")
                if k in node
            }
            | {"path": path}
        )
        for i, child in enumerate(node.get("Plans", [])):
            visit(child, f"{path}.{i}")

    visit(root["Plan"], "0")
    scan_nodes = [
        n
        for n in nodes
        if n.get("Relation Name") == "documents_full" and "Actual Rows" in n and "Actual Loops" in n
    ]
    # Per-loop figures may be rounded by PostgreSQL: explicitly approximate.
    candidates = (
        scan_nodes[0]["Actual Rows"] * scan_nodes[0]["Actual Loops"]
        if len(scan_nodes) == 1
        else None
    )
    jit = jit_summary(root.get("JIT"))
    top = root["Plan"]
    result = {
        "planning_ms": root["Planning Time"],
        "execution_ms": root["Execution Time"],
        "jit": jit,
        "jit_total_ms": jit.get("Timing", {}).get("Total"),
        "nodes": nodes,
        "planning_buffers": metrics(root.get("Planning", {})),
        "structure_sha256": fingerprint(structural),
        "estimates_sha256": fingerprint(estimates),
        "candidate_rows_approx": candidates,
        "workers_planned": max(
            (n["Workers Planned"] for n in nodes if "Workers Planned" in n), default=None
        ),
        "workers_launched": max(
            (n["Workers Launched"] for n in nodes if "Workers Launched" in n), default=None
        ),
        "timing_scope": "inclusive_per_loop_ms_workers_overlap_do_not_sum_nodes",
        "buffer_scope": "root_totals_not_sum_of_nodes_not_physical_ssd_reads",
    }
    for name in ("Generation", "Inlining", "Optimization", "Emission"):
        result[f"jit_{name.lower()}_ms"] = jit.get("Timing", {}).get(name)
    for output, key in (
        ("shared_hit_blocks", "Shared Hit Blocks"),
        ("shared_read_blocks", "Shared Read Blocks"),
        ("temp_read_blocks", "Temp Read Blocks"),
        ("temp_written_blocks", "Temp Written Blocks"),
    ):
        result[output] = top.get(key) if base.number(top.get(key)) else None
    return result


def schedule(case, repeats, alternate):
    selected = GROUPS.get(case, (CASES[case],) if case in CASES else ())
    if not selected or (alternate and case not in GROUPS):
        raise base.Refused("invalid_schedule")
    result = []
    for repetition in range(1, repeats + 1):
        order = list(selected)
        if alternate and repetition % 2 == 0:
            for query_id in ("democratie-02", "fiscalite-01"):
                indices = [i for i, entry in enumerate(order) if entry[1] == query_id]
                if len(indices) == 2:
                    a, b = indices
                    order[a], order[b] = order[b], order[a]
        for name, query_id, mode in order:
            result.append(
                {
                    "run_id": f"r{repetition:02d}-{name}",
                    "case": name,
                    "query_id": query_id,
                    "jit_mode": mode,
                    "repetition": repetition,
                    "status": "pending",
                    "code": "none",
                }
            )
    return result


class Storage:
    """Bound diagnostic output independently of PostgreSQL temporary files."""

    def __init__(self, directory, *, maximum=64 * MIB, minimum_free=512 * MIB):
        self.directory, self.maximum, self.minimum_free = directory, maximum, minimum_free
        self.sizes = {}

    def check_measurement(self):
        if sum(self.sizes.values()) + 2 * PLAN_LIMIT + RESERVE > self.maximum:
            raise base.Refused("storage_limit")
        if shutil.disk_usage(self.directory).free < self.minimum_free + 2 * PLAN_LIMIT + RESERVE:
            raise base.Refused("low_disk_space")

    def write(self, name, value, *, limit=REPORT_LIMIT, as_text=False):
        serialized = (
            value if as_text else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
        )
        payload = (serialized + "\n").encode()
        if len(payload) > limit:
            raise base.Refused("plan_too_large" if limit == PLAN_LIMIT else "output_limit")
        # Peak usage includes old and replacement files until atomic rename.
        if sum(self.sizes.values()) + len(payload) > self.maximum:
            raise base.Refused("storage_limit")
        if shutil.disk_usage(self.directory).free < self.minimum_free + len(payload):
            raise base.Refused("low_disk_space")
        temporary = self.directory / (name + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / name)
            self.sizes[name] = len(payload)
        finally:
            if temporary.exists():
                temporary.unlink()


@contextmanager
def exclusive_output(path):
    # A common parent shared by all prescribed Docker commands serializes clients.
    fd = os.open(path.parent / ".h1-analyze.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise base.Refused("another_collection_running") from None
        path.mkdir(mode=0o700, exist_ok=False)
        yield
    finally:
        os.close(fd)


def table_row(record):
    # Also used to sanitize externally supplied summaries during offline comparison.
    if record.get("case") not in CASES or record.get("status") not in STATUSES:
        raise base.Refused("invalid_summary")
    repetition = record.get("repetition")
    if type(repetition) is not int or not 1 <= repetition <= 20:
        raise base.Refused("invalid_summary")
    case = CASES[record["case"]]
    row = {
        "case": case[0],
        "query_id": case[1],
        "jit_mode": case[2],
        "repetition": repetition,
        "status": record["status"],
        "code": record.get("code") if record.get("code") in ERROR_CODES else "measurement_failed",
    }
    for key in TABLE_NUMBERS:
        row[key] = record.get(key) if base.number(record.get(key)) else None
    for key in HASH_FIELDS:
        value = record.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            row[key] = value
    return row


def comparisons(rows):
    results = []
    for i, row in enumerate(rows):
        for j in range(i):
            other = rows[j]
            if (
                row["query_id"] != other["query_id"]
                or row["jit_mode"] == other["jit_mode"]
                or row["repetition"] != other["repetition"]
            ):
                continue
            keys = (
                "sql_sha256",
                "parameters_sha256",
                "generation_sha256",
                "settings_other_sha256",
                "limits_sha256",
                "sources_sha256",
                "tool_sha256",
            )
            comparable = row["status"] == other["status"] == "ok" and all(
                row.get(k) is not None and row.get(k) == other.get(k) for k in keys
            )
            results.append(
                {
                    "rows": [j, i],
                    "comparable": comparable,
                    "structure_equal": row.get("structure_sha256") == other.get("structure_sha256")
                    if comparable
                    else None,
                    "estimates_equal": row.get("estimates_sha256") == other.get("estimates_sha256")
                    if comparable
                    else None,
                }
            )
    return results


def markdown_table(rows):
    columns = (
        "case",
        "repetition",
        "status",
        "code",
        "planning_ms",
        "execution_ms",
        "jit_total_ms",
        "jit_generation_ms",
        "jit_inlining_ms",
        "jit_optimization_ms",
        "jit_emission_ms",
        "candidate_rows_approx",
        "workers_planned",
        "workers_launched",
        "shared_hit_blocks",
        "shared_read_blocks",
        "temp_read_blocks",
        "temp_written_blocks",
    )
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend(
        "| "
        + " | ".join(str(row.get(k)) if row.get(k) is not None else "n/a" for k in columns)
        + " |"
        for row in rows
    )
    return "\n".join(lines) + "\n"


def save_reports(storage, records, manifest):
    rows = [table_row(record) for record in records]
    comparison = {
        "rows": rows,
        "comparisons": comparisons(rows),
        "table_markdown": markdown_table(rows),
    }
    manifest["outcomes"] = rows
    storage.write("manifest.private.json", manifest)
    storage.write("summary.redacted.json", {"format": 1, "runs": records})
    storage.write("comparison.redacted.json", comparison)
    storage.write("comparison.redacted.md", comparison["table_markdown"], as_text=True)


def run(args):
    verify_sources()
    cases = base.read_cases(args.queries)
    settings = load_settings(env_file=args.reader_env, environ={})
    source_url, target_url = settings.require_source_url(), settings.require_rag_url()
    records = schedule(args.case, args.repeats, args.alternate_jit_order)
    limits = {
        "statement_ms": args.statement_timeout_ms,
        "lock_ms": args.lock_timeout_ms,
        "case_seconds": args.case_deadline_seconds,
    }
    manifest = {
        "base_commit": base.BASE_COMMIT,
        "sources_sha256": base.SOURCE_HASHES,
        "tool_sha256": base.digest(Path(__file__).read_bytes()),
        "base_tool_sha256": BASE_TOOL_SHA,
        "queries_sha256": base.QUERY_SHA256,
        "explain": EXPLAIN.strip(),
        "limits": limits,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }
    with exclusive_output(args.output_dir):
        storage = Storage(
            args.output_dir, maximum=args.max_output_mib * MIB, minimum_free=args.min_free_mib * MIB
        )
        save_reports(storage, records, manifest)
        source = target = None
        stop = False
        generation = None
        try:
            source = create_search_engine(source_url)
            target = create_search_engine(target_url)
            for record in records:
                if stop:
                    record.update(status="skipped", code="not_run_after_error")
                    continue
                try:
                    storage.check_measurement()
                    record.update(status="running")
                    save_reports(storage, records, manifest)
                    plan, metadata = collect_case(
                        source,
                        target,
                        cases[record["query_id"]],
                        mode=record["jit_mode"],
                        **{
                            "statement_ms": limits["statement_ms"],
                            "lock_ms": limits["lock_ms"],
                            "seconds": limits["case_seconds"],
                        },
                    )
                    record.update({k: metadata[k] for k in ("status", "code", "elapsed_seconds")})
                    if metadata.get("stage") in (
                        "preparation",
                        "ranking_setup",
                        "ranking",
                        "plan_received",
                    ):
                        record["stage"] = metadata["stage"]
                    if "ranking_statement_timeout_ms" in metadata:
                        record["ranking_statement_timeout_ms"] = metadata[
                            "ranking_statement_timeout_ms"
                        ]
                    if "settings_effective" in metadata:
                        effective = metadata["settings_effective"]
                        record["effective_jit"] = effective["jit"]
                        record["io_timing_enabled"] = effective.get("track_io_timing") == "on"
                    attempt = {"run_id": record["run_id"], **metadata}
                    attempt["collection_status"] = attempt.pop("status")
                    attempt["collection_code"] = attempt.pop("code")
                    manifest["runs"].append(attempt)
                    if metadata["status"] == "ok":
                        current_generation = fingerprint(metadata["generation"])
                        if generation is not None and generation != current_generation:
                            raise base.Refused("corpus_generation_changed")
                        generation = current_generation
                        safe = summarize(plan)
                        if record["jit_mode"] == "off" and (
                            safe["jit"]["present"]
                            or any(
                                n["jit"]["present"]
                                or any(w["jit"]["present"] for w in n["workers"])
                                for n in safe["nodes"]
                            )
                        ):
                            raise base.Refused("jit_off_plan_contains_jit")
                        storage.write(
                            record["run_id"] + ".plan.private.json", plan, limit=PLAN_LIMIT
                        )
                        storage.write(
                            record["run_id"] + ".summary.redacted.json", safe, limit=PLAN_LIMIT
                        )
                        record.update({k: v for k, v in safe.items() if k != "nodes"})
                        record.update(
                            {
                                k: metadata[k]
                                for k in (
                                    "sql_sha256",
                                    "parameters_sha256",
                                    "settings_other_sha256",
                                )
                            }
                        )
                        record.update(
                            generation_sha256=generation,
                            limits_sha256=fingerprint(limits),
                            sources_sha256=fingerprint(base.SOURCE_HASHES),
                            tool_sha256=manifest["tool_sha256"],
                        )
                except KeyboardInterrupt:
                    record.update(status="error", code="interrupted")
                    stop = True
                except Exception as error:
                    status, code = error_status(error)
                    record.update(status=status, code=code)
                    stop = True
                # A timeout is recorded once, with no automatic retry. The
                # explicitly scheduled next case may proceed; other errors stop.
                stop = stop or record["status"] == "error"
                save_reports(storage, records, manifest)
        finally:
            for engine in (source, target):
                if engine is not None:
                    engine.dispose()
            for record in records:
                if record["status"] in ("running", "pending"):
                    record.update(status="skipped", code="not_run_after_error")
            save_reports(storage, records, manifest)
    return 0 if all(r["status"] == "ok" for r in records) else 1


def compare(args):
    # This branch never loads credentials or opens a database connection.
    rows = []
    for directory in args.compare:
        path = directory / "summary.redacted.json"
        if path.stat().st_size > REPORT_LIMIT:
            raise base.Refused("invalid_summary")
        data = json.loads(path.read_bytes())
        if data.get("format") != 1 or len(data["runs"]) > 100:
            raise base.Refused("invalid_summary")
        rows.extend(table_row(record) for record in data["runs"])
    with exclusive_output(args.output_dir):
        storage = Storage(
            args.output_dir, maximum=args.max_output_mib * MIB, minimum_free=args.min_free_mib * MIB
        )
        storage.write(
            "comparison.redacted.json",
            {
                "rows": rows,
                "comparisons": comparisons(rows),
                "table_markdown": markdown_table(rows),
            },
        )
        storage.write("comparison.redacted.md", markdown_table(rows), as_text=True)
    return 0


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--case", choices=(*CASES, *GROUPS))
    mode.add_argument("--compare", type=Path, nargs="+")
    result.add_argument(
        "--execute", action="store_true", help="Explicitly authorize real SQL execution"
    )
    result.add_argument("--reader-env", type=Path)
    result.add_argument("--queries", type=Path)
    result.add_argument("--output-dir", required=True, type=Path)
    result.add_argument("--statement-timeout-ms", type=base.bounded_integer(300000), default=60000)
    result.add_argument("--case-deadline-seconds", type=base.bounded_integer(360), default=90)
    result.add_argument("--lock-timeout-ms", type=base.bounded_integer(1000), default=200)
    result.add_argument("--repeats", type=base.bounded_integer(20), default=1)
    result.add_argument("--alternate-jit-order", action="store_true")
    result.add_argument("--max-output-mib", type=base.bounded_integer(256), default=64)
    result.add_argument("--min-free-mib", type=base.bounded_integer(1048576), default=512)
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.case and (not args.execute or args.reader_env is None or args.queries is None):
        cli.error("Measurement requires --execute, --reader-env and --queries.")
    if args.max_output_mib < 32 or args.min_free_mib < 64:
        cli.error("Storage requires --max-output-mib >=32 and --min-free-mib >=64.")
    if args.compare and len(args.compare) > 20:
        cli.error("At most 20 input collections.")
    if args.case_deadline_seconds * 1000 < args.statement_timeout_ms:
        cli.error("Case deadline must be at least the statement timeout.")
    if args.alternate_jit_order and args.case not in GROUPS:
        cli.error("Alternation requires a group of JIT cases.")
    os.umask(0o077)
    try:
        result = compare(args) if args.compare else run(args)
        print(json.dumps({"status": "ok" if result == 0 else "incomplete"}))
        return result
    except base.Refused as error:
        # All refusal codes are internal constants, never database messages.
        print(json.dumps({"status": "error", "code": error.args[0]}))
    except FileExistsError:
        print('{"status":"error","code":"output_already_exists"}')
    except Exception:
        print('{"status":"error","code":"diagnostic_failed"}')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
