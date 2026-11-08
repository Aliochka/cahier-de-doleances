"""Controlled additive import into the precisely authorized local cahier_rag."""

import argparse
import json
import subprocess
from pathlib import Path

from sqlalchemy import text

from .artifacts import DECISIONS, Artifacts, canonical
from .editorial import load_decisions
from .local_application import LOCAL_IDENTITY, LocalApplicationDestination, digest
from .representations import gate, prepare_lexical, verify_representations
from .safety import Destination
from .storage import SCOPE, WHERE, import_collection, migrate, verify

TARGET = "postgresql+psycopg2:///cahier_rag?host=/var/run/postgresql"


def backup(directory, source):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = LocalApplicationDestination(TARGET)
    try:
        with target.transaction(readonly=True) as c:
            state = dict(
                c.execute(text("SELECT * FROM rag_full.spaces WHERE space_id='full'"))
                .mappings()
                .one()
            )
            stats = dict(
                c.execute(text("SELECT * FROM rag_tuning.statistics WHERE space_id='full'"))
                .mappings()
                .one()
            )
            indexes = [
                dict(r)
                for r in c.execute(
                    text("""SELECT n.nspname,c.relname,c.relfilenode,i.indisvalid,pg_get_indexdef(c.oid) AS definition
                FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname IN ('rag_full','rag_tuning') ORDER BY n.nspname,c.relname""")
                ).mappings()
            ]
            existed = c.execute(
                text("SELECT to_regnamespace('documentary') IS NOT NULL")
            ).scalar_one()
        (directory / "gdn-state.json").write_text(
            json.dumps(dict(state=state, statistics=stats, indexes=indexes), default=str, indent=2)
            + "\n"
        )
        common = [
            "/usr/lib/postgresql/17/bin/pg_dump",
            "-h",
            "/var/run/postgresql",
            "-d",
            "cahier_rag",
            "-Fc",
            "--no-owner",
        ]
        subprocess.run(
            common + ["--schema-only", "-f", str(directory / "search-schema.dump")],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            common
            + [
                "--data-only",
                "-t",
                "rag_full.spaces",
                "-t",
                "rag_tuning.statistics",
                "-t",
                "rag_tuning.term_statistics",
                "-t",
                "public.rag_alembic_version",
                "-f",
                str(directory / "gdn-control-data.dump"),
            ],
            check=True,
            capture_output=True,
        )
        source_url = source.engine.url
        subprocess.run(
            [
                "/usr/lib/postgresql/17/bin/pg_dump",
                "-h",
                source_url.query["host"],
                "-p",
                source_url.query["port"],
                "-U",
                source_url.username,
                "-d",
                source_url.database,
                "-Fc",
                "-n",
                "documentary",
                "--no-owner",
                "-f",
                str(directory / "documentary-source.dump"),
            ],
            check=True,
            capture_output=True,
        )
        if existed:
            subprocess.run(
                common + ["-n", "documentary", "-f", str(directory / "documentary-before.dump")],
                check=True,
                capture_output=True,
            )
        files = {p.name: digest(p) for p in directory.iterdir() if p.is_file()}
        manifest = dict(
            target=LOCAL_IDENTITY,
            documentary_previously_present=existed,
            files=files,
            scope="Additive documentary only; GDN bulk untouched, schema/control-data saved, full documentary source saved",
        )
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return directory / "manifest.json"
    finally:
        target.close()


def transfer(source, target, *, reuse_lexical=False):
    # Verify every immutable text/slice/vector and recipe BEFORE touching the target.
    original = verify_representations(source)
    artifacts, bundle = Artifacts(), load_decisions(DECISIONS)
    migrate(target)
    with target.transaction(readonly=True) as c:
        existing = c.execute(
            text(f"SELECT count(*) FROM documentary.release WHERE {WHERE}"), SCOPE
        ).scalar_one()
    if not existing:
        import_collection(target, artifacts, bundle)
    with source.transaction(readonly=True) as src, target.transaction() as dst:
        dst.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
        verify(dst, artifacts, bundle, phase1=False)
        release = gate(src)
        for table, key, fields, casts in [
            (
                "document",
                "document_id",
                ["metadata_vector", "filter_metadata"],
                {"metadata_vector": "tsvector", "filter_metadata": "jsonb"},
            ),
            (
                "search_unit",
                "unit_id",
                ["search_vector", "embedding", "embedding_hash"],
                {"search_vector": "tsvector", "embedding": "public.vector"},
            ),
        ]:
            columns = ",".join(
                f"{field}::text AS {field}" if field in casts else field for field in fields
            )
            rows = (
                src.execute(
                    text(
                        f"SELECT {key},text_sha256,{columns} FROM documentary.{table} WHERE {WHERE}"
                    ),
                    SCOPE,
                )
                .mappings()
                .all()
            )
            assignments = ",".join(
                f"{field}=CAST(:{field} AS {casts[field]})"
                if field in casts
                else f"{field}=:{field}"
                for field in fields
            )
            sql = text(
                f"UPDATE documentary.{table} SET {assignments} WHERE {WHERE} AND {key}=:id AND text_sha256=:hash"
            )
            for offset in range(0, len(rows), 250):
                batch = [
                    dict(
                        SCOPE,
                        id=r[key],
                        hash=r["text_sha256"],
                        **{field: r[field] for field in fields},
                    )
                    for r in rows[offset : offset + 250]
                ]
                updated = dst.execute(sql, batch)
                if updated.rowcount != len(batch):
                    raise ValueError("Representation/source fingerprint mismatch")
        rows = src.execute(
            text(
                f"SELECT term,document_frequency FROM documentary.lexical_term_statistics WHERE {WHERE}"
            ),
            SCOPE,
        ).all()
        dst.execute(text(f"DELETE FROM documentary.lexical_term_statistics WHERE {WHERE}"), SCOPE)
        for offset in range(0, len(rows), 1000):
            dst.execute(
                text(
                    "INSERT INTO documentary.lexical_term_statistics VALUES (:corpus,:release,:term,:df)"
                ),
                [dict(SCOPE, term=t, df=df) for t, df in rows[offset : offset + 1000]],
            )
        dst.execute(
            text(f"""UPDATE documentary.release SET lexical_recipe=CAST(:lex AS jsonb),
            embedding_recipe=CAST(:emb AS jsonb),lexical_statistics=CAST(:stats AS jsonb),
            statistics_ready=:statistics_ready,representations_ready=true WHERE {WHERE}"""),
            dict(
                SCOPE,
                lex=canonical(release["lexical_recipe"]),
                emb=canonical(release["embedding_recipe"]),
                stats=canonical(release["lexical_statistics"]),
                statistics_ready=reuse_lexical,
            ),
        )
        for table in ["document", "search_unit", "lexical_term_statistics"]:
            dst.execute(text(f"ANALYZE documentary.{table}"))
        dst.execute(text("GRANT USAGE ON SCHEMA documentary TO cahier_search_reader"))
        dst.execute(
            text(
                "GRANT SELECT ON documentary.corpus,documentary.release,documentary.document,documentary.search_unit,documentary.lexical_term_statistics,documentary.alembic_version TO cahier_search_reader"
            )
        )
    with target.transaction() as c:
        c.execute(text("REVOKE ALL ON documentary.editorial_decision FROM cahier_search_reader"))
    # Text search case folding depends on the database locale, not only french.
    # Rebuild this small corpus on the target; existing GDN statistics are untouched.
    if not reuse_lexical:
        prepare_lexical(target)
    with target.transaction() as c:
        locale = dict(
            c.execute(
                text("SELECT datcollate,datctype FROM pg_database WHERE datname=current_database()")
            )
            .mappings()
            .one()
        )
        c.execute(
            text(
                f"UPDATE documentary.release SET lexical_statistics=lexical_statistics || CAST(:locale AS jsonb) WHERE {WHERE}"
            ),
            dict(SCOPE, locale=canonical({"database_locale": locale})),
        )
    try:
        result = verify_representations(target)
        if (
            result["source_integrity"] != original["source_integrity"]
            or result["vectors"] != original["vectors"]
        ):
            raise ValueError("Integrated documentary differs from verified source")
    except Exception:
        # In particular, copied lexical derivatives can disagree with target
        # locale rules. A failed verification must not leave promotable flags.
        with target.transaction() as c:
            c.execute(
                text(
                    f"UPDATE documentary.release SET statistics_ready=false,representations_ready=false WHERE {WHERE}"
                ),
                SCOPE,
            )
        raise
    result["source_statistics"] = original["statistics"]
    # verify_representations recomputes expected tsvectors/DF on the destination.
    # A non-compatible transfer fails explicitly; no ready/public release results.
    result["lexical_rebuilt_on_target"] = not reuse_lexical
    return result


def verify_gdn(target, manifest):
    expected = json.loads((Path(manifest).parent / "gdn-state.json").read_text())
    with target.transaction(readonly=True) as c:
        state = dict(
            c.execute(text("SELECT * FROM rag_full.spaces WHERE space_id='full'")).mappings().one()
        )
        stats = dict(
            c.execute(text("SELECT * FROM rag_tuning.statistics WHERE space_id='full'"))
            .mappings()
            .one()
        )
        indexes = [
            dict(r)
            for r in c.execute(
                text("""SELECT n.nspname,c.relname,c.relfilenode,i.indisvalid,pg_get_indexdef(c.oid) AS definition
            FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('rag_full','rag_tuning') ORDER BY n.nspname,c.relname""")
            ).mappings()
        ]
    if (
        json.loads(json.dumps(dict(state=state, statistics=stats, indexes=indexes), default=str))
        != expected
    ):
        raise ValueError("GDN state/statistics/index identity changed")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["backup", "import", "verify"])
    p.add_argument("--source-url", required=True)
    p.add_argument("--source-data-directory", required=True)
    p.add_argument("--source-system-id", required=True)
    p.add_argument("--backup-directory", type=Path)
    p.add_argument("--backup-manifest", type=Path)
    args = p.parse_args()
    source = Destination(args.source_url, args.source_data_directory, args.source_system_id)
    target = None
    try:
        if args.action == "backup":
            if args.backup_directory is None:
                p.error("--backup-directory required")
            result = {"backup_manifest": str(backup(args.backup_directory, source))}
        else:
            if args.backup_manifest is None:
                p.error("--backup-manifest required")
            target = LocalApplicationDestination(
                TARGET, backup=args.backup_manifest, writable=args.action == "import"
            )
            verify_gdn(target, args.backup_manifest)
            result = (
                transfer(source, target)
                if args.action == "import"
                else verify_representations(target)
            )
            result["gdn_unchanged"] = verify_gdn(target, args.backup_manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        source.close()
        if target:
            target.close()


if __name__ == "__main__":
    main()
