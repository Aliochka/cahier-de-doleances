"""Inventaire agrégé READ ONLY ; aucune réponse citoyenne dans les sorties."""

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from cahier_rag.contracts import CONTRACT_VERSION
from cahier_rag.db import source_connection
from cahier_rag.safety import inspect_database
from cahier_rag.vector.preparation import atomic_json

# Python str.strip() accepte plus de blancs que btrim(text) ou POSIX space.
WHITESPACE = "".join(chr(i) for i in range(0x110000) if chr(i).isspace())

# Les erreurs restent des obstacles explicites : aucun JSON invalide n'est ignoré.
VALID_JSON = """WITH j AS MATERIALIZED (
 SELECT a.id, a.value_json FROM public.answers a JOIN public.questions q ON q.id=a.question_id
 WHERE q.type IN ('single_choice','multi_choice') AND a.value_json IS NOT NULL)
 SELECT count(*) FILTER(WHERE NOT pg_input_is_valid(value_json,'jsonb')) AS invalid_json,
 count(*) FILTER(WHERE CASE WHEN pg_input_is_valid(value_json,'jsonb') THEN
 jsonb_typeof(value_json::jsonb) <> 'object' ELSE false END) AS invalid_object
 FROM j"""
OTHER_SHAPE = """WITH j AS MATERIALIZED (
 SELECT a.value_json::jsonb AS v FROM public.answers a
 JOIN public.questions q ON q.id=a.question_id
 WHERE q.type IN ('single_choice','multi_choice') AND a.value_json IS NOT NULL)
 SELECT count(*) FILTER(WHERE v ? 'other_text' AND jsonb_typeof(v->'other_text') <> 'array')
 AS invalid_array FROM j"""
OTHER_ITEMS = """WITH j AS MATERIALIZED (
 SELECT a.value_json::jsonb AS v FROM public.answers a
 JOIN public.questions q ON q.id=a.question_id
 WHERE q.type IN ('single_choice','multi_choice') AND a.value_json IS NOT NULL)
 SELECT count(*) AS invalid_item FROM j CROSS JOIN LATERAL
 jsonb_array_elements(coalesce(v->'other_text','[]'::jsonb)) e
 WHERE jsonb_typeof(e) <> 'string'"""

# Conforme au lecteur : type text -> answers.text ; choix -> other_text, indice original.
UNIT_CTE = """WITH textual AS (
 SELECT a.id AS answer_id,a.contribution_id,a.question_id,q.form_id,
 'open_answer'::text AS kind,0::bigint AS unit_index,a.text AS body
 FROM public.answers a JOIN public.questions q ON q.id=a.question_id WHERE q.type='text'
 UNION ALL
 SELECT a.id,a.contribution_id,a.question_id,q.form_id,'other_text',e.ordinality-1,e.body
 FROM public.answers a JOIN public.questions q ON q.id=a.question_id
 CROSS JOIN LATERAL jsonb_array_elements_text(
 coalesce(a.value_json::jsonb->'other_text','[]'::jsonb)) WITH ORDINALITY e(body,ordinality)
 WHERE q.type IN ('single_choice','multi_choice')),
 usable AS (SELECT * FROM textual WHERE body IS NOT NULL AND btrim(body,:whitespace)<>'')
"""


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def resource_estimate(units, segments_per_unit, bytes_per_unit, free_bytes):
    if units < 1 or segments_per_unit < 1 or bytes_per_unit <= 0:
        raise ValueError("Estimation positive requise.")
    segments = int(units * segments_per_unit + 0.999999)
    raw = segments * 1024 * 4
    # Enveloppe prudente avant pilote, à remplacer par tailles mesurées.
    persistent = int(units * bytes_per_unit + raw * 4)
    temporary = persistent  # WAL, construction ANN, tri et marge de reprise.
    reserve = 100 * 1024**3
    required = persistent + temporary + reserve
    return dict(
        units=units,
        estimated_segments=segments,
        float32_bytes=raw,
        float16_bytes=segments * 1024 * 2,
        estimated_persistent_bytes=persistent,
        temporary_bytes=temporary,
        reserve_bytes=reserve,
        required_free_bytes=required,
        free_bytes=free_bytes,
        sufficient=free_bytes >= required,
        assumptions="documents measured on pilot; vectors/table/HNSW envelope 4x raw",
    )


def audit(source, target, output: Path):
    if output.exists():
        raise ValueError("Inventaire existant : choisir un nouveau chemin.")
    result = {
        "version": 1,
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timings": {},
    }

    def run(connection, name, sql, params=None):
        start = time.perf_counter()
        rows = [dict(r) for r in connection.execute(text(sql), params or {}).mappings()]
        result[name] = rows
        result["timings"][name] = time.perf_counter() - start
        print(json.dumps({"audit": name, "seconds": result["timings"][name]}), flush=True)
        return rows

    with source_connection(source) as c:
        c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        c.execute(text("SET LOCAL statement_timeout='240s'"))
        c.execute(text("SET LOCAL lock_timeout='2s'"))
        c.execute(text("SET LOCAL work_mem='64MB'"))
        result["source"] = inspect_database(c, source=True).to_dict()
        run(
            c,
            "source_meta",
            "SELECT version(), pg_database_size(current_database()) AS bytes, "
            "(SELECT count(*) FROM public.contributions) AS contributions, "
            "(SELECT count(*) FROM public.answers) AS answers, "
            "(SELECT min(id)::text FROM public.answers) AS min_answer_id, "
            "(SELECT max(id)::text FROM public.answers) AS max_answer_id",
        )
        run(
            c,
            "indexes",
            "SELECT tablename,indexname,indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename IN ('answers','contributions','questions','forms')",
        )
        checks = run(c, "json_validation", VALID_JSON)[0]
        if any(checks.values()):
            raise ValueError("JSON source incompatible avec GdnReader ; inventaire arrêté.")
        if run(c, "other_shape", OTHER_SHAPE)[0]["invalid_array"]:
            raise ValueError("other_text non tableau ; inventaire arrêté.")
        if run(c, "other_items", OTHER_ITEMS)[0]["invalid_item"]:
            raise ValueError("other_text non textuel ; inventaire arrêté.")
        run(
            c,
            "integrity",
            "SELECT count(*) FILTER(WHERE q.id IS NULL OR c.id IS NULL "
            "OR f.id IS NULL OR q.form_id<>c.form_id) AS broken "
            "FROM public.answers a LEFT JOIN public.questions q ON q.id=a.question_id "
            "LEFT JOIN public.contributions c ON c.id=a.contribution_id "
            "LEFT JOIN public.forms f ON f.id=q.form_id",
        )
        if result["integrity"][0]["broken"]:
            raise ValueError("Relations sources incohérentes.")
        run(
            c,
            "per_question",
            UNIT_CTE
            + """
 SELECT t.form_id::text,t.question_id::text,t.kind,count(*) AS units,
 sum(char_length(body))::bigint AS characters,sum(octet_length(body))::bigint AS bytes,
 min(char_length(body)) AS min_length,max(char_length(body)) AS max_length,
 count(*) FILTER(WHERE char_length(body)<60) AS short,
 count(*) FILTER(WHERE char_length(body)>2000) AS long,
 count(*) FILTER(WHERE char_length(body)>4000) AS over4000
 FROM usable t GROUP BY t.form_id,t.question_id,t.kind ORDER BY t.form_id,t.question_id,t.kind
 """,
            {"whitespace": WHITESPACE},
        )
        run(
            c,
            "excluded",
            UNIT_CTE
            + """SELECT kind,count(*) AS excluded
 FROM textual WHERE body IS NULL OR btrim(body,:whitespace)='' GROUP BY kind""",
            {"whitespace": WHITESPACE},
        )
        run(
            c,
            "duplicates",
            UNIT_CTE
            + """SELECT count(*) AS distinct_md5,
 sum(n)::bigint AS units,sum(n-1)::bigint AS repeated_occurrences,
 count(*) FILTER(WHERE parents>1) AS groups_across_contributions,
 max(n) AS max_occurrences FROM (
 SELECT md5(body),count(*) AS n,count(DISTINCT contribution_id) AS parents
 FROM usable GROUP BY md5(body)) d""",
            {"whitespace": WHITESPACE},
        )
        run(
            c,
            "parents",
            UNIT_CTE
            + """SELECT count(*) AS parents,
 count(*) FILTER(WHERE n>1) AS multiple_units FROM
 (SELECT contribution_id,count(*) AS n FROM usable GROUP BY contribution_id) x""",
            {"whitespace": WHITESPACE},
        )
    with source_connection(target) as c:
        result["target"] = inspect_database(c).to_dict()
        run(
            c,
            "target_meta",
            "SELECT version(), pg_database_size(current_database()) AS bytes, "
            "(SELECT extversion FROM pg_extension WHERE extname='vector') AS pgvector",
        )
        run(
            c,
            "settings",
            "SELECT name,setting,unit FROM pg_settings WHERE name IN "
            "('shared_buffers','work_mem','maintenance_work_mem','max_parallel_maintenance_workers')",
        )
    result["units"] = sum(r["units"] for r in result["per_question"])
    # Reproductible hors horodatages et chronométrages ; comptes + identité + règles.
    result["selection"] = dict(
        source=result["source"],
        source_meta=result["source_meta"],
        contract_version=CONTRACT_VERSION,
        reader="GdnReader-v1",
        filter="all forms; text/other_text; Python str.strip nonempty",
        counts=result["per_question"],
        excluded=result["excluded"],
    )
    result["selection_hash"] = fingerprint(result["selection"])
    result["filesystem"] = dict(zip(("total", "used", "free"), shutil.disk_usage(output.parent)))
    atomic_json(output, result)
    return result
