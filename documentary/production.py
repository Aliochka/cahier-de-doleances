"""Opt-in documentary maintenance for the physically inventoried Gavroche cluster.

Default is read-only. Import requires --execute-import and a full backup proof,
or the specifically approved Nov 2 cold backup plus fresh checks and rollback
assets preserved before deployment. No publication command.
The original local/laboratory destination guards are unchanged.
"""

import argparse
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cahier_rag.safety import inspect_database
from dotenv import dotenv_values
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from .backup_exception import check_cold_exception
from .local_application import LocalApplicationDestination, digest
from .safety import UnsafeDestination

IDENTITY = dict(
    cluster_id="7695026423032606758",
    database_oid=634726,
    database_name="cahier_search",
    schema_revision=None,
)
APPLICATION_IDENTITY = dict(
    cluster_id=IDENTITY["cluster_id"],
    database_oid=16384,
    database_name="cahier_doleances",
    schema_revision="forms_statistics_v1",
)
OWNER = "cahier_documentary_owner"
LOGIN = "cahier_search_maintenance"
MIGRATION_SHA256 = "f6b998e25971c754021a2948a845bdc52820b95ed10faf31eacae4db0debc7ba"
ARCHIVE_SHA256 = "a9196d21f3abe5c8198cf4f13c05826e6ab21f37ec109b09571523c36c3e3275"


def gdn_snapshot(target):
    with target.transaction(readonly=True) as c:
        return {
            "state": dict(
                c.execute(text("SELECT * FROM rag_full.spaces WHERE space_id='full'"))
                .mappings()
                .one()
            ),
            "statistics": dict(
                c.execute(text("SELECT * FROM rag_tuning.statistics WHERE space_id='full'"))
                .mappings()
                .one()
            ),
            "indexes": [
                dict(r)
                for r in c.execute(
                    text("""SELECT n.nspname,c.relname,c.relfilenode,i.indisvalid,pg_get_indexdef(c.oid) AS definition
            FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('rag_full','rag_tuning') ORDER BY n.nspname,c.relname""")
                ).mappings()
            ],
        }


def check_backup_proof(proof, *, now=None):
    """Validate a human attestation, NOT a substitute for actually restoring backups.

    Full archives stay on the backup disk; this small evidence file is brought to
    the operator workstation. Remote archive checksums/restoration are a runbook
    prerequisite; this client cannot independently attest those remote files.
    """
    now = now or datetime.now(timezone.utc)
    try:
        if "exception" in proof:
            if not (
                proof["target"] == IDENTITY
                and proof["application"] == APPLICATION_IDENTITY
                and proof["operator"].strip()
            ):
                raise ValueError()
            check_cold_exception(proof, now=now)
            return
        completed = datetime.fromisoformat(proof["restore_completed_at"])
        backup_completed = datetime.fromisoformat(proof["backup_completed_at"])
        if not (
            proof["target"] == IDENTITY
            and proof["application"] == APPLICATION_IDENTITY
            and proof["operator"].strip()
            and proof["restore_verified"] is True
            and completed.tzinfo is not None
            and backup_completed.tzinfo is not None
            and now - timedelta(hours=24) <= backup_completed <= completed <= now
            and proof["restored_application_revision"] == "forms_statistics_v1"
            and proof["restored_rag_revision"] == "rag_0007"
        ):
            raise ValueError()
        expected = {"application", "search", "globals", "configuration"}
        if set(proof["backups"]) != expected:
            raise ValueError()
        for kind, item in proof["backups"].items():
            database_backup = kind in {"application", "search"}
            physical = database_backup and item["kind"] == "physical-cluster"
            if physical and not (
                item.get("integrity_file") == "backup_manifest"
                and set(item.get("covers", [])) == {"cahier_doleances", "cahier_search"}
            ):
                raise ValueError()
            if not (
                (physical or item["kind"] == ("pg_dump-full" if database_backup else kind))
                and item["bytes"] > 0
                and re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                and item["sha256"] != "0" * 64
                and Path(item["path"]).is_relative_to("/backups/postgresql")
                and ".." not in Path(item["path"]).parts
            ):
                raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise UnsafeDestination(
            "Fresh FULL backup proof or complete approved Nov 2 exception required"
        ) from None


class ProductionDestination:
    def __init__(self, url, *, writable=False, backup_proof=None):
        parsed = make_url(url)
        if (
            parsed.drivername != "postgresql+psycopg2"
            or parsed.username != LOGIN
            or parsed.database != IDENTITY["database_name"]
            or (parsed.host, parsed.port) != ("127.0.0.1", 55495)
            or parsed.query
        ):
            raise UnsafeDestination(
                "Explicit Gavroche maintenance URL via the pinned SSH tunnel required"
            )
        self.writable = writable
        self.backup_proof = backup_proof
        if writable:
            check_backup_proof(backup_proof)
        self.migration = (Path(__file__).parent / "migrations/versions/doc_0001.sql").read_text()
        if hashlib.sha256(self.migration.encode()).hexdigest() != MIGRATION_SHA256:
            raise UnsafeDestination("Documentary migration differs from the reviewed doc_0001")
        self.engine = create_engine(
            parsed,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 3,
                "options": "-c statement_timeout=120000 -c lock_timeout=2000"
                + " -c default_transaction_read_only="
                + ("off" if writable else "on"),
            },
        )
        event.listen(self.engine, "before_cursor_execute", self._restrict)

    def _restrict(self, connection, cursor, statement, parameters, context, executemany):
        sql = statement.strip()
        if re.match(r"^(SELECT|SHOW|SET)\b", sql, re.I):
            return
        if connection.info.get("documentary_write"):
            if sql == self.migration.strip():
                return
            if re.match(
                r"^(INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE|ANALYZE) documentary\.", sql, re.I
            ):
                return
            if sql in {
                "GRANT USAGE ON SCHEMA documentary TO cahier_search_reader",
                "GRANT SELECT ON documentary.corpus,documentary.release,documentary.document,documentary.search_unit,documentary.lexical_term_statistics,documentary.alembic_version TO cahier_search_reader",
                "REVOKE ALL ON documentary.editorial_decision FROM cahier_search_reader",
            }:
                return
        raise UnsafeDestination("Production maintenance permits documentary mutations only")

    def _unpublished(self, c):
        if c.execute(text("SELECT to_regclass('documentary.release') IS NOT NULL")).scalar_one():
            if c.execute(
                text("""SELECT EXISTS(SELECT 1 FROM documentary.release
                WHERE publication_authorized OR state='ready')
                OR EXISTS(SELECT 1 FROM documentary.corpus WHERE active_release_id IS NOT NULL)
                OR EXISTS(SELECT 1 FROM documentary.document
                WHERE readable OR searchable OR catalogue_visible)""")
            ).scalar_one():
                raise UnsafeDestination("Technical deployment cannot activate or publish documents")

    @contextmanager
    def transaction(self, *, readonly=False):
        if not readonly and not self.writable:
            raise UnsafeDestination("Production is read-only without explicit import authorization")
        with self.engine.connect() as c, c.begin():
            c.info["documentary_write"] = False
            if readonly:
                c.execute(text("SET TRANSACTION READ ONLY"))
            if inspect_database(c).to_dict() != IDENTITY:
                raise UnsafeDestination("Physical Gavroche database identity mismatch")
            row = c.execute(
                text("""SELECT current_user,session_user,current_setting('server_version_num')::int,
                (SELECT extversion FROM pg_extension WHERE extname='vector'),
                (SELECT version_num FROM public.rag_alembic_version)""")
            ).one()
            if (
                row[:2] != (LOGIN, LOGIN)
                or not 170000 <= row[2] < 180000
                or row[3:] != ("0.8.7", "rag_0007")
            ):
                raise UnsafeDestination(
                    "Gavroche role, PostgreSQL, vector or RAG revision mismatch"
                )
            if not readonly:
                check_backup_proof(self.backup_proof)
                if not c.execute(
                    text("SELECT EXISTS(SELECT FROM pg_roles WHERE rolname=:owner)"),
                    {"owner": OWNER},
                ).scalar_one():
                    raise UnsafeDestination(
                        "Provision the dedicated documentary owner after approval"
                    )
                c.execute(text("SET LOCAL ROLE " + OWNER))
                schema_owner = c.execute(
                    text(
                        "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='documentary'"
                    )
                ).scalar_one_or_none()
                if schema_owner != OWNER:
                    raise UnsafeDestination("Pre-provisioned documentary schema owner mismatch")
                self._unpublished(c)
                c.info["documentary_write"] = True
            try:
                yield c
                if not readonly:
                    self._unpublished(c)
            finally:
                c.info["documentary_write"] = False

    def close(self):
        self.engine.dispose()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["inspect", "import"])
    p.add_argument("--maintenance-env", type=Path, required=True)
    p.add_argument("--backup-proof", type=Path)
    p.add_argument("--execute-import", action="store_true")
    p.add_argument(
        "--source-archive",
        type=Path,
        help="Restore the approved archive into a NEW local private cluster, then transfer; never restore an archive directly over production",
    )
    p.add_argument(
        "--rebuild-lexical",
        action="store_true",
        help="Rebuild only 1789 lexical derivatives if destination verification requires it",
    )
    args = p.parse_args()
    if args.action == "import" and (not args.execute_import or args.backup_proof is None):
        p.error("Import requires --execute-import and --backup-proof after operator approval")
    target = source = None
    try:
        url = dotenv_values(args.maintenance_env, interpolate=False).get(
            "DOCUMENTARY_PRODUCTION_URL"
        )
        if not url:
            raise UnsafeDestination("Explicit DOCUMENTARY_PRODUCTION_URL file required")
        proof = json.loads(args.backup_proof.read_text()) if args.backup_proof else None
        target = ProductionDestination(url, writable=args.action == "import", backup_proof=proof)
        with target.transaction(readonly=True) as c:
            result = dict(
                identity=inspect_database(c).to_dict(), rag_revision="rag_0007", writable=False
            )
        if args.action == "import":
            from .integrate_local import TARGET, transfer

            before = gdn_snapshot(target)
            if args.source_archive:
                from .restore_check import check

                if digest(args.source_archive) != ARCHIVE_SHA256:
                    raise UnsafeDestination("Source archive differs from the reviewed 1789 release")
                restored = check(
                    args.source_archive,
                    verified_callback=lambda src: transfer(
                        src, target, reuse_lexical=not args.rebuild_lexical
                    ),
                )
                result = restored["verified_action"]
            else:
                source = LocalApplicationDestination(TARGET)
                # The source verifies its own precise physical identity on every transaction.
                result = transfer(source, target, reuse_lexical=not args.rebuild_lexical)
            if gdn_snapshot(target) != before:
                raise UnsafeDestination("GDN state, lexical statistics or index identity changed")
            result["gdn_unchanged"] = True
        print(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        # Never display a driver exception, SQL parameters or a credential URL.
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": str(exc)
                    if isinstance(exc, UnsafeDestination)
                    else type(exc).__name__,
                }
            )
        )
        raise SystemExit(1) from None
    finally:
        if source:
            source.close()
        if target:
            target.close()


if __name__ == "__main__":
    main()
