"""Three private, non-executing H1 lexical plans. Never initializes an encoder.

Only the ranking execute call inside the pinned TunedSearch.lexical can become
EXPLAIN. Every other application statement must match a small metadata/preparation
allowlist. Unknown SQL fails closed. No documentary SELECT is ever forwarded.
"""

import argparse
import ast
import hashlib
import inspect
import json
import math
import os
import re
import sys
import textwrap
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

from cahier_rag.config import load_settings
from cahier_rag.safety import inspect_database
from cahier_rag.search.preparation import normalize
from cahier_rag.search.service.control import Budget, SearchTimeout
from cahier_rag.search.service.reader import (
    ReadGuard,
    ReadStore,
    check_reader_role,
    create_search_engine,
)
from cahier_rag.tuning.lexical import TunedSearch
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.elements import TextClause

BASE_COMMIT = "0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73"
QUERY_SHA256 = "f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e"
CASE_IDS = ("fiscalite-05", "democratie-02", "fiscalite-01")
EXPLAIN = "EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON) "
SOURCE_HASHES = {
    "tuning/lexical.py": "d443c1f3b5ec1388d9ac0f56306086f029db9aee80804c82c239e288658b2d6b",
    "search/preparation.py": "1c6cc9f096141ef19166b025870de2e1da04b2b4e466c86d32588aa3215ec55c",
    "search/flexible.py": "caf45208b995ffdc567f99f87bbb12f18a114e89ba5abdbcfed77f2a81ee7e09",
    "fullcorpus/search.py": "5b675c3990c63f8d3e9fb4229900c5a29417a77a274d0eebbed9c5dbe5339d59",
    "fullcorpus/store.py": "7c0fe3f013b22b6f04829aeed5026bc09afd9297c07d307e9a2e8be115003102",
    "search/service/reader.py": "54f9709e9572937d6ef2f65b824f54b66266e0d3577fcdb4268cb885aabb66b9",
    "safety.py": "bbc6edc2eb833b312bb8e57ddb2542a730621e2adc1f6bbc5dc9d8e902b543a6",
}
PLANNER_SETTINGS = (
    "work_mem",
    "shared_buffers",
    "effective_cache_size",
    "jit",
    "jit_above_cost",
    "jit_inline_above_cost",
    "jit_optimize_above_cost",
    "random_page_cost",
    "seq_page_cost",
    "default_statistics_target",
    "max_parallel_workers_per_gather",
    "plan_cache_mode",
    "enable_partition_pruning",
    "enable_bitmapscan",
    "enable_seqscan",
    "enable_indexscan",
    "search_path",
    "row_security",
    "server_version_num",
)


class Refused(Exception):
    """A fixed code, never a database message or user-provided string."""


class PlanCaptured(Exception):
    def __init__(self, plan):
        self.plan = plan
        super().__init__("plan_captured")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_sources():
    root = Path(inspect.getfile(TunedSearch)).resolve().parents[1]
    for relative, expected in SOURCE_HASHES.items():
        if digest((root / relative).read_bytes()) != expected:
            raise Refused("h1_source_mismatch")
    if version("SQLAlchemy") != "2.0.43" or version("psycopg2-binary") != "2.9.10":
        raise Refused("driver_version_mismatch")


def literal_statements(function):
    """Extract only fixed text(...) calls from already fingerprinted functions."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return {
        node.args[0].value.strip()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "text"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


def sql_key(sql):
    # inspect.getsource dedenting changes indentation inside SQL literals in
    # Python. Ignore SQL whitespace, but preserve quoted SQL values verbatim.
    return re.sub(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\s+",
        lambda match: " " if match[0].isspace() else match[0],
        sql,
    ).strip()


def preparation_allowlist():
    allowed = set()
    for function in (normalize, inspect_database, check_reader_role, ReadGuard.transaction):
        allowed.update(literal_statements(function))
    # FullStore.state concatenates an optional FOR UPDATE; only the read form.
    allowed.add("SELECT * FROM rag_full.spaces WHERE space_id=:space")
    allowed.update(literal_statements(TunedSearch._terms))
    # The stored-DF SQL is assigned to sql before execute(text(sql), params).
    tree = ast.parse(textwrap.dedent(inspect.getsource(TunedSearch._terms)))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and any(isinstance(t, ast.Name) and t.id == "sql" for t in node.targets)
        ):
            allowed.add(node.value.value.strip())
    return {sql_key(sql) for sql in allowed}


class Wire:
    """Bound every database round trip, including preparation and EXPLAIN."""

    def __init__(self, raw, budget, statement_ms, lock_ms):
        self.raw, self.budget = raw, budget
        self.statement_ms, self.lock_ms = statement_ms, lock_ms

    def execute(self, statement, parameters=None):
        self.budget.check()
        remaining = min(self.statement_ms, max(1, int(self.budget.remaining() * 1000)))
        with self.budget.connection(self.raw.connection.driver_connection):
            self.raw.execute(
                text("SELECT set_config('statement_timeout', :value, true)"),
                {"value": str(remaining)},
            )
            result = self.raw.execute(statement, parameters if parameters is not None else {})
        self.budget.check()
        return result

    def initialize(self):
        # First statement after BEGIN, before any metadata/preparation query.
        self.budget.check()
        with self.budget.connection(self.raw.connection.driver_connection):
            self.raw.execute(text("SET TRANSACTION READ ONLY"))
        self.execute(
            text("SELECT set_config('lock_timeout', :value, true)"),
            {"value": str(self.lock_ms)},
        )
        row = (
            self.execute(
                text("""SELECT
            current_setting('transaction_read_only') AS read_only,
            current_setting('statement_timeout') AS statement_timeout,
            current_setting('lock_timeout') AS lock_timeout""")
            )
            .mappings()
            .one()
        )
        if row["read_only"] != "on":
            raise Refused("transaction_not_read_only")
        if (
            not 0 < timeout_ms(row["statement_timeout"]) <= self.statement_ms
            or not 0 < timeout_ms(row["lock_timeout"]) <= self.lock_ms
        ):
            raise Refused("transaction_timeout_not_bounded")
        return dict(row)


def timeout_ms(value):
    match = re.fullmatch(r"(\d+)(ms|s|min)", value)
    if not match:
        raise Refused("unexpected_timeout_format")
    return int(match[1]) * {"ms": 1, "s": 1000, "min": 60000}[match[2]]


class ExplainConnection:
    def __init__(self, wire, guard, *, target):
        self.wire, self.guard, self.target = wire, guard, target

    def execute(self, statement, parameters=None):
        if self.guard.halted or not isinstance(statement, TextClause):
            raise Refused("unexpected_statement")
        sql = statement.text
        caller = sys._getframe(1)
        ranking_call = (
            caller.f_code is TunedSearch.lexical.__code__
            and caller.f_locals.get("sql") == sql
            and caller.f_locals.get("params") is parameters
        )
        if ranking_call:
            if (
                not self.target
                or self.guard.captures
                or parameters["space"] != "full"
                or parameters["limit"] != 50
                or any(parameters[k] is not None for k in ("form", "kind", "split"))
                or self.guard.engine_recipe.statistics is not True
                or self.guard.engine_recipe.prefilter is not None
            ):
                raise Refused("unexpected_ranking")
            self.guard.halted = True  # Also prevents hydration or a second ranking.
            self.guard.captures += 1
            self.guard.metadata["ranking_sql_sha256"] = digest(sql.encode())
            self.guard.metadata["parameter_types"] = {
                k: type(v).__name__ for k, v in parameters.items()
            }
            # Preserve the original TextClause bind definitions and Python values.
            explained = text(EXPLAIN + sql).bindparams(*statement._bindparams.values())
            plan = self.wire.execute(explained, parameters).scalar_one()
            raise PlanCaptured(plan)
        if (
            caller.f_code is TunedSearch.lexical.__code__
            and sql == "SET LOCAL statement_timeout='30s'"
        ):
            # Never let the historical timeout relax the diagnostic ceiling.
            return None
        if sql_key(sql) not in self.guard.allowed:
            raise Refused("sql_not_allowlisted")
        return self.wire.execute(statement, parameters)


class ExplainGuard(ReadGuard):
    def __init__(self, source, target, budget, *, statement_ms, lock_ms):
        super().__init__(source, target, budget)
        self.statement_ms, self.lock_ms = statement_ms, lock_ms
        self.allowed = preparation_allowlist()
        self.halted, self.captures = False, 0
        self.metadata = {"transactions": []}
        self.engine_recipe = None

    @contextmanager
    def _connect(self, engine):
        self.budget.check()
        with engine.connect() as raw:
            raw = raw.execution_options(postgresql_readonly=True)
            transaction = raw.begin()
            try:
                wire = Wire(raw, self.budget, self.statement_ms, self.lock_ms)
                state = wire.initialize()
                self.metadata["transactions"].append(
                    {
                        "target": engine is self.target,
                        **state,
                        "end": "rollback",
                    }
                )
                connection = ExplainConnection(wire, self, target=engine is self.target)
                check_reader_role(connection)
                if engine is self.target and "session_settings" not in self.metadata:
                    self.metadata["session_settings"] = dict(
                        wire.execute(
                            text("SELECT name, setting FROM pg_settings WHERE name=ANY(:names)"),
                            {"names": list(PLANNER_SETTINGS)},
                        ).all()
                    )
                yield connection
            finally:
                transaction.rollback()
        self.budget.check()


class ExplainStore(ReadStore):
    def state(self, connection=None):
        state = super().state(connection)
        generation = {k: state[k] for k in ("documents", "chain_hash", "recipe_hash")}
        old = self.guard.metadata.setdefault("generation", generation)
        if old != generation:
            raise Refused("corpus_generation_changed")
        return state


def collect_case(source, target, query, *, statement_ms=2000, lock_ms=200, seconds=10):
    budget = Budget(seconds)
    guard = ExplainGuard(source, target, budget, statement_ms=statement_ms, lock_ms=lock_ms)
    engine = TunedSearch(ExplainStore(guard), statistics=True, prefilter=None)
    guard.engine_recipe = engine
    with budget.monitor(), budget.phase("explain_collection"):
        try:
            engine.lexical(query, limit=50, questionnaire_id=None, unit_type=None, split=None)
        except PlanCaptured as captured:
            return captured.plan, guard.metadata
    raise Refused("ranking_not_captured")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def safe_name(value):
    return isinstance(value, str) and re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,127}", value)


def summarize(plan):
    """Positive projection only: never serialize expressions, filters or values."""
    root = plan[0] if isinstance(plan, list) and len(plan) == 1 else None
    if not isinstance(root, dict) or not isinstance(root.get("Plan"), dict):
        raise Refused("unexpected_plan_format")
    nodes = []

    def visit(node, path):
        item = {"path": path}
        node_type = node.get("Node Type", "")
        if isinstance(node_type, str) and re.fullmatch(r"[A-Za-z ]{1,48}", node_type):
            item["node_type"] = node_type
        for key in ("Startup Cost", "Total Cost", "Plan Rows", "Plan Width", "Workers Planned"):
            if number(node.get(key)):
                item[key] = node[key]
        for key in ("Parallel Aware", "Async Capable"):
            if type(node.get(key)) is bool:
                item[key] = node[key]
        for key in ("Schema", "Relation Name", "Index Name", "Scan Direction"):
            if safe_name(node.get(key)):
                item[key] = node[key]
        if "Sort Key" in node:
            item["sort_keys"] = [
                "document_id_collate_C"
                if 'COLLATE "C"' in key and "document_id" in key
                else "weighted_score"
                if "ts_rank_cd" in key or key in ("score", "score DESC")
                else "expression_redacted"
                for key in node["Sort Key"]
                if isinstance(key, str)
            ]
        nodes.append(item)
        for i, child in enumerate(node.get("Plans", [])):
            visit(child, f"{path}.{i}")

    visit(root["Plan"], "0")
    jit = root.get("JIT", {})
    return {
        "nodes": nodes,
        "jit": {
            "present": "JIT" in root,
            "functions": jit.get("Functions") if number(jit.get("Functions")) else None,
            "options": {
                k: v
                for k, v in jit.get("Options", {}).items()
                if k in ("Inlining", "Optimization", "Expressions", "Deforming") and type(v) is bool
            },
        },
        "scope": "estimates_only_no_execution_or_actual_timings",
    }


def private_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with open(
        path, "x", encoding="utf-8", opener=lambda name, flags: os.open(name, flags, 0o600)
    ) as f:
        f.write(payload)


def read_cases(path):
    raw = path.read_bytes()
    if digest(raw) != QUERY_SHA256:
        raise Refused("query_file_mismatch")
    rows = json.loads(raw)["queries"]
    cases = {r["query_id"]: r["text"] for r in rows if r["query_id"] in CASE_IDS}
    if set(cases) != set(CASE_IDS) or len(rows) != 32:
        raise Refused("query_cases_mismatch")
    return cases


def run(args):
    verify_sources()
    cases = read_cases(args.queries)
    settings = load_settings(env_file=args.reader_env, environ={})
    # Validate both URLs before creating any output or connecting.
    source_url, target_url = settings.require_source_url(), settings.require_rag_url()
    args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    manifest = {
        "base_commit": BASE_COMMIT,
        "source_sha256": SOURCE_HASHES,
        "diagnostic_sha256": digest(Path(__file__).read_bytes()),
        "queries_sha256": QUERY_SHA256,
        "driver_versions": {k: version(k) for k in ("SQLAlchemy", "psycopg2-binary")},
        "limits": {
            "statement_ms": args.statement_timeout_ms,
            "lock_ms": args.lock_timeout_ms,
            "case_seconds": args.case_deadline_seconds,
        },
        "explain_options": EXPLAIN.strip(),
        "cases": [],
    }
    summary = {"cases": []}
    source = target = None
    try:
        source = create_search_engine(source_url)
        target = create_search_engine(target_url)
        previous_generation = None
        for query_id in args.query_ids:
            try:
                plan, metadata = collect_case(
                    source,
                    target,
                    cases[query_id],
                    statement_ms=args.statement_timeout_ms,
                    lock_ms=args.lock_timeout_ms,
                    seconds=args.case_deadline_seconds,
                )
                if (
                    previous_generation is not None
                    and metadata["generation"] != previous_generation
                ):
                    raise Refused("corpus_generation_changed")
                previous_generation = metadata["generation"]
                safe = summarize(plan)
                private_json(args.output_dir / f"{query_id}.plan.json", plan)
                manifest["cases"].append({"query_id": query_id, "status": "ok", **metadata})
                summary["cases"].append({"query_id": query_id, "status": "ok", **safe})
            except Exception as error:
                code = error.args[0] if isinstance(error, Refused) else "collection_failed"
                if isinstance(error, SearchTimeout):
                    code = "case_deadline_exceeded"
                if isinstance(error, DBAPIError):
                    code = {"57014": "statement_cancelled", "55P03": "lock_timeout"}.get(
                        getattr(error.orig, "pgcode", None), "database_error"
                    )
                failure = {"query_id": query_id, "status": "error", "code": code}
                manifest["cases"].append(failure)
                summary["cases"].append(failure)
                break  # No automatic retry or further SQL after an error.
    finally:
        for engine in (source, target):
            if engine is not None:
                engine.dispose()
        private_json(args.output_dir / "manifest.private.json", manifest)
        private_json(args.output_dir / "summary.redacted.json", summary)
    return (
        0
        if len(summary["cases"]) == 3 and all(c["status"] == "ok" for c in summary["cases"])
        else 1
    )


def bounded_integer(maximum):
    def parse(value):
        try:
            result = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError("Entier requis.") from None
        if not 1 <= result <= maximum:
            raise argparse.ArgumentTypeError(f"Valeur requise entre 1 et {maximum}.")
        return result

    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader-env", required=True, type=Path)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--query-ids", nargs=3, choices=CASE_IDS, default=list(CASE_IDS))
    parser.add_argument("--statement-timeout-ms", type=bounded_integer(2000), default=2000)
    parser.add_argument("--lock-timeout-ms", type=bounded_integer(200), default=200)
    parser.add_argument("--case-deadline-seconds", type=bounded_integer(10), default=10)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if tuple(args.query_ids) != CASE_IDS:
        parser.error("Les trois cas sont requis dans l'ordre prévu.")
    os.umask(0o077)
    try:
        result = run(args)
    except Refused as error:
        print(json.dumps({"status": "error", "code": error.args[0]}))
        return 1
    except FileExistsError:
        print('{"status":"error","code":"output_already_exists"}')
        return 1
    except Exception:
        print('{"status":"error","code":"diagnostic_refused_or_failed"}')
        return 1
    print(
        json.dumps(
            {
                "status": "ok" if result == 0 else "error",
                "code": "collection_complete" if result == 0 else "collection_incomplete",
            }
        )
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
