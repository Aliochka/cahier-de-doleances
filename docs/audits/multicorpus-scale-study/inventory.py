"""Inventaire local borné, strictement READ ONLY, sans configuration privée."""

import datetime
import platform
import time

from common import CACHE, HERE, PRIOR, ROOT, connect, read, sha, write


def main():
    import psutil

    result = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "connection": {
            "transport": "unix",
            "host": "/var/run/postgresql",
            "port": 5432,
            "role": "ro",
            "read_only": True,
            "remote_dsn_used": False,
        },
        "resources": {
            "available_ram": psutil.virtual_memory().available,
            "free_disk": psutil.disk_usage(ROOT).free,
            "cpu_percent_1s": psutil.cpu_percent(interval=1),
            "platform": platform.platform(),
        },
        "queries": [],
    }
    with connect(timeout_ms=15000) as c:
        with c.cursor() as q:
            q.execute("SELECT version()")
            result["postgresql"] = q.fetchone()[0]
            q.execute(
                "SELECT space_id,documents,segments,verified,vectors_complete,recipe_hash,chain_hash,manifest FROM rag_full.spaces ORDER BY space_id"
            )
            names = [x.name for x in q.description]
            result["spaces"] = [dict(zip(names, r)) for r in q.fetchall()]
            q.execute(
                "SELECT state,count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY state"
            )
            result["activity"] = dict(q.fetchall())
            q.execute("SELECT extname,extversion FROM pg_extension WHERE extname='vector'")
            result["pgvector"] = dict(q.fetchall())
    full = next(s for s in result["spaces"] if s["space_id"] == "full")
    prior_model = read(PRIOR / "data/encoding.json")["model"]
    assert (
        full["verified"] and full["vectors_complete"] and full["manifest"]["model"] == prior_model
    )
    assert full["manifest"]["normalize"] is True
    assert full["manifest"]["tokens"] == {
        "budget": 1024,
        "overlap": 128,
        "strategy": "B",
        "version": 1,
        "offsets": "unicode-codepoints",
    }
    for database, name, sql in (
        ("cahier_doleances_local", "answers", "SELECT count(*) FROM public.answers"),
        ("cahier_doleances_local", "contributions", "SELECT count(*) FROM public.contributions"),
        (
            "cahier_rag",
            "full_documents",
            "SELECT count(*),min(ordinal),max(ordinal) FROM rag_full.documents WHERE space_id='full'",
        ),
    ):
        started = time.perf_counter()
        try:
            with connect(database, timeout_ms=15000) as c:
                with c.cursor() as q:
                    q.execute(sql)
                    count = q.fetchone()
            result["queries"].append(
                dict(
                    database=database,
                    name=name,
                    result=list(count),
                    seconds=time.perf_counter() - started,
                    status="measured",
                )
            )
        except Exception as error:
            result["queries"].append(
                dict(
                    database=database,
                    name=name,
                    status=type(error).__name__,
                    seconds=time.perf_counter() - started,
                )
            )
    result["prior_local_sample"] = {
        "units": read(ROOT / "rag/evaluation/local/rag013/bge-B/manifest.json")["units"],
        "segments": read(ROOT / "rag/evaluation/local/rag013/bge-B/manifest.json")["segments"],
        "scope": read(ROOT / "rag/evaluation/local/rag007/corpus.json")["scope"],
        "path": "rag/evaluation/local/rag013/bge-B/encoded",
        "manifest_sha256": sha(ROOT / "rag/evaluation/local/rag013/bge-B/manifest.json"),
    }
    result["selected_maximum"] = 1000000
    result["resource_assumptions"] = {
        "raw_vectors_bytes_1m_approx": 4109000000,
        "working_ram_budget_bytes": 12 * 1024**3,
        "cache_path": str(CACHE),
        "sequential_bounded_queries": True,
        "other_running_db_queries_observed": 0,
        "new_embeddings": 0,
    }
    write(HERE / "data/inventory.json", result)
    print(
        {
            "full_units": full["documents"],
            "compatible_segments": full["segments"],
            "source_counts": result["queries"],
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
