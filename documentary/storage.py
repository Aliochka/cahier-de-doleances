"""Atomic offline import, replay, and read-only comparison with original artifacts."""

from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .artifacts import CORPUS, GENERATION, canonical
from .editorial import replay

JSON_FIELDS = {
    "metadata",
    "source_manifest",
    "source_inventory",
    "counts",
    "source_metadata",
    "provenance",
    "order_locator",
    "boundary_status",
    "warnings",
    "value",
    "evidence",
}
TABLES = {"corpus", "release", "document", "search_unit", "editorial_decision"}
SCOPE = {"corpus": CORPUS, "release": GENERATION}
WHERE = "corpus_id=:corpus AND release_id=:release"


def insert(c, table, records):
    if table not in TABLES:
        raise ValueError("Unknown maintenance table")
    records = list(records)
    if not records:
        return
    columns = list(records[0])
    values = [f"CAST(:{k} AS jsonb)" if k in JSON_FIELDS else f":{k}" for k in columns]
    sql = text(f"INSERT INTO documentary.{table} ({','.join(columns)}) VALUES ({','.join(values)})")
    for start in range(0, len(records), 250):
        batch = [
            {k: canonical(v) if k in JSON_FIELDS else v for k, v in r.items()}
            for r in records[start : start + 250]
        ]
        c.execute(sql, batch)


def migrate(destination):
    with destination.transaction() as c:
        c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
        c.execute(text("CREATE SCHEMA IF NOT EXISTS documentary"))
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        config.attributes.update(connection=c, documentary_guarded=True)
        command.upgrade(config, "head")


def compare_rows(c, table, expected, key):
    expected = {r[key]: r for r in expected}
    result = c.execute(text(f"SELECT * FROM documentary.{table} WHERE {WHERE}"), SCOPE)
    seen = set()
    for row in result.mappings():
        identity = row[key]
        if identity not in expected or identity in seen:
            raise ValueError(f"Unexpected/duplicate {table} identifier")
        if any(row[k] != value for k, value in expected[identity].items()):
            raise ValueError(f"Stored {table} differs from source/projection: {identity}")
        if table == "document" and (
            row["metadata_vector"] is not None or row["filter_metadata"] != {}
        ):
            raise ValueError("Unexpected phase-2 document representations")
        if table == "search_unit" and any(
            row[k] is not None for k in ("search_vector", "embedding", "embedding_hash")
        ):
            raise ValueError("Unexpected phase-2 unit representations")
        seen.add(identity)
    if seen != set(expected):
        raise ValueError(f"Missing {table} records")


def check_events(c, bundle, *, extending=False):
    events = {e["decision_id"]: e for e in bundle["decisions"]}
    found = set()
    for row in c.execute(
        text("SELECT * FROM documentary.editorial_decision WHERE corpus_id=:corpus"), SCOPE
    ).mappings():
        event = events.get(row["decision_id"])
        if event is None:
            raise ValueError("Existing editorial event cannot disappear on reimport")
        for key, value in event.items():
            if key == "decided_at":
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if row[key] != value:
                raise ValueError("Existing editorial decision is immutable")
        found.add(row["decision_id"])
    if not extending and found != set(events):
        raise ValueError("Missing editorial events")
    return found


def release_expected(artifacts, bundle, projection):
    return dict(
        corpus_id=CORPUS,
        release_id=GENERATION,
        source_generation=GENERATION,
        source_manifest=artifacts.manifest,
        source_manifest_hash=artifacts.manifest_hash,
        source_inventory={
            "inventory": artifacts.inventory,
            "metadata_without_text": {
                k: v for k, v in artifacts.metadata.items() if k not in artifacts.documents
            },
        },
        editorial_revision=bundle["revision_id"],
        editorial_hash=projection["hash"],
        counts=artifacts.counts(),
    )


def verify(c, artifacts, bundle):
    projection = replay(artifacts, bundle)
    release = (
        c.execute(text(f"SELECT * FROM documentary.release WHERE {WHERE}"), SCOPE).mappings().one()
    )
    if any(release[k] != v for k, v in release_expected(artifacts, bundle, projection).items()):
        raise ValueError("Release source/editorial manifest differs")
    if (
        release["state"] != "verified"
        or release["validated_at"] is None
        or any(
            release[k]
            for k in ("representations_ready", "statistics_ready", "publication_authorized")
        )
        or any(
            release[k] != {} for k in ("lexical_recipe", "embedding_recipe", "lexical_statistics")
        )
    ):
        raise ValueError("Phase 1 must remain verified, without search readiness or publication")
    if (
        c.execute(
            text("SELECT active_release_id FROM documentary.corpus WHERE corpus_id=:corpus"), SCOPE
        ).scalar_one()
        is not None
    ):
        raise ValueError("Phase 1 must not activate a public release")
    compare_rows(c, "document", artifacts.document_rows(projection), "document_id")
    compare_rows(c, "search_unit", artifacts.unit_rows(projection), "unit_id")
    check_events(c, bundle)
    if c.execute(
        text(f"SELECT count(*) FROM documentary.lexical_term_statistics WHERE {WHERE}"), SCOPE
    ).scalar_one():
        raise ValueError("No lexical statistics in phase 1")
    # Independent PostgreSQL Unicode slicing, in addition to Python source verification.
    for row in c.execute(
        text("""SELECT u.unit_id, substring(d.full_text FROM u.start_offset+1
            FOR u.end_offset-u.start_offset) AS passage
        FROM documentary.search_unit u JOIN documentary.document d USING(corpus_id,release_id,document_id)
        WHERE u.corpus_id=:corpus AND u.release_id=:release"""),
        SCOPE,
    ).mappings():
        if row["passage"] != artifacts.units[row["unit_id"]]["text"]:
            raise ValueError("PostgreSQL Unicode slice differs from original passage")
    return dict(
        **artifacts.counts(),
        state="verified",
        search_ready=False,
        publication_authorized=False,
        active_release=None,
        editorial_revision=bundle["revision_id"],
        editorial_hash=projection["hash"],
        excluded_units=sum(not enabled for enabled in projection["units"].values()),
        permitted_units=sum(projection["units"].values()),
        candidate_permitted_units=sum(
            projection["units"][u["id"]]
            and artifacts.documents[u["document_id"]]["document_kind"] == "cahier_autonome_probable"
            for u in artifacts.units.values()
        ),
        public_documents=0,
        representations=0,
        source_manifest_hash=artifacts.manifest_hash,
    )


def import_collection(destination, artifacts, bundle):
    projection = replay(artifacts, bundle)  # Refuse invalid decisions before any write.
    with destination.transaction() as c:
        c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
        existing = (
            c.execute(text(f"SELECT * FROM documentary.release WHERE {WHERE}"), SCOPE)
            .mappings()
            .one_or_none()
        )
        expected = release_expected(artifacts, bundle, projection)
        if existing:
            # Never overwrite a damaged import. Editorial changes use a separate, explicit command.
            return dict(verify(c, artifacts, bundle), imported=False)
        corpus = (
            c.execute(text("SELECT * FROM documentary.corpus WHERE corpus_id=:corpus"), SCOPE)
            .mappings()
            .one_or_none()
        )
        if corpus is None:
            insert(
                c,
                "corpus",
                [dict(corpus_id=CORPUS, slug="cahiers-1789", label="Cahiers de doléances de 1789")],
            )
        elif corpus["active_release_id"] is not None:
            raise ValueError("Phase-1 importer cannot change an activated corpus")
        known = check_events(c, bundle, extending=True)
        insert(
            c,
            "editorial_decision",
            [e for e in bundle["decisions"] if e["decision_id"] not in known],
        )
        insert(c, "release", [expected])
        insert(c, "document", artifacts.document_rows(projection))
        insert(c, "search_unit", artifacts.unit_rows(projection))
        c.execute(
            text(
                f"UPDATE documentary.release SET state='verified', validated_at=now() WHERE {WHERE}"
            ),
            SCOPE,
        )
        report = verify(c, artifacts, bundle)
        return dict(report, imported=True)


def apply_editorial(destination, artifacts, previous, replacement):
    projection = replay(artifacts, replacement)
    if previous["revision_id"] == replacement["revision_id"]:
        raise ValueError("A changed editorial bundle needs a new revision")
    if replacement["decisions"][: len(previous["decisions"])] != previous["decisions"]:
        raise ValueError("Editorial history is append-only")
    with destination.transaction() as c:
        c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
        verify(c, artifacts, previous)
        known = check_events(c, replacement, extending=True)
        insert(
            c,
            "editorial_decision",
            [e for e in replacement["decisions"] if e["decision_id"] not in known],
        )
        # Recompute projections from the entire log, without changing source columns.
        for key, row in projection["documents"].items():
            c.execute(
                text(f"""UPDATE documentary.document SET display_title=:display_title,
                warnings=CAST(:warnings AS jsonb) WHERE {WHERE} AND document_id=:id"""),
                dict(
                    SCOPE,
                    id=key,
                    display_title=row["display_title"],
                    warnings=canonical(row["warnings"]),
                ),
            )
        c.execute(text(f"UPDATE documentary.search_unit SET searchable=true WHERE {WHERE}"), SCOPE)
        disabled = [key for key, enabled in projection["units"].items() if not enabled]
        if disabled:
            c.execute(
                text(
                    f"UPDATE documentary.search_unit SET searchable=false WHERE {WHERE} AND unit_id=ANY(:ids)"
                ),
                dict(SCOPE, ids=disabled),
            )
        c.execute(
            text(f"""UPDATE documentary.release SET editorial_revision=:revision,
            editorial_hash=:hash WHERE {WHERE}"""),
            dict(SCOPE, revision=replacement["revision_id"], hash=projection["hash"]),
        )
        return verify(c, artifacts, replacement)
