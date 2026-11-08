"""Read policy and version-pinned documentary consultation; default denies publication."""

import hashlib
import hmac
import ipaddress
from contextlib import contextmanager
from urllib.parse import quote, urlsplit

from cahier_rag.embeddings.registry import MODELS
from cahier_rag.safety import inspect_database
from fastapi import HTTPException
from sqlalchemy import text

from app.config import settings
from documentary.representations import ELIGIBLE
from documentary.representations import gate as laboratory_gate
from documentary.storage import SCOPE, WHERE

PUBLIC_ELIGIBLE = ELIGIBLE + " AND d.readable AND d.searchable"


def document_url(document_id, release_id, unit_id=None):
    url = f"/parcourir/1789/{quote(release_id, safe='')}/documents/{quote(document_id, safe='')}"
    if unit_id:
        url += "?unit=" + quote(unit_id, safe="") + "#passage-" + quote(unit_id, safe="")
    return url


def reference_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(x for x in value if isinstance(x, str))
    return ""


class ReaderDestination:
    def __init__(self, engine, expected):
        self.engine, self.expected = engine, expected

    @contextmanager
    def transaction(self, *, readonly=False):
        if not readonly:
            raise ValueError("Documentary application reader cannot write")
        with self.engine.connect() as c, c.begin():
            c.execute(text("SET TRANSACTION READ ONLY"))
            if inspect_database(c).to_dict() != self.expected:
                raise ValueError("Documentary reader target mismatch")
            yield c


class DocumentaryRepository:
    def __init__(self, engine, config):
        self.destination = ReaderDestination(engine, config["expected_target"])
        self.config = config
        self.ready = False
        self.query_snapshot = None

    def preview(self, request):
        if not self.config.get("local_preview") or settings.ENV != "dev":
            return False
        peer = (
            request.scope.get("cahier.transport_client")
            or (request.client.host, request.client.port)
            if request.client
            else None
        )
        host = urlsplit("http://" + request.headers.get("host", "")).hostname
        token = request.headers.get("x-documentary-preview", "")
        expected = self.config.get("preview_token", "")
        try:
            local_peer = peer is not None and ipaddress.ip_address(peer[0]).is_loopback
        except ValueError:
            return False
        return bool(
            local_peer
            and host in {"127.0.0.1", "localhost", "::1"}
            and len(expected) >= 32
            and token.isascii()
            and hmac.compare_digest(token, expected)
            and not any(
                h in request.headers for h in ("forwarded", "x-forwarded-host", "x-forwarded-for")
            )
        )

    def read_gate(self, c, *, preview):
        release = (
            c.execute(text(f"SELECT * FROM documentary.release WHERE {WHERE}"), SCOPE)
            .mappings()
            .one_or_none()
        )
        if release is None:
            raise HTTPException(404, "Corpus indisponible")
        if any(release[k] != self.config[k] for k in ("source_manifest_hash", "editorial_hash")):
            raise HTTPException(503, "Collection documentaire incompatible")
        active = c.execute(
            text("SELECT active_release_id FROM documentary.corpus WHERE corpus_id=:corpus"), SCOPE
        ).scalar_one()
        if preview:
            if release["state"] not in {"verified", "ready"}:
                raise HTTPException(503, "Collection non vérifiée")
        elif (
            not release["publication_authorized"]
            or active != SCOPE["release"]
            or release["state"] != "ready"
        ):
            raise HTTPException(404, "Corpus non publié")
        return release

    def check_representations(self, release):
        recipe = release["embedding_recipe"]
        if (
            recipe.get("version") != "historical-bge-1"
            or recipe.get("model") != MODELS["bge-m3"].to_dict()
            or recipe.get("input") != "exact technical passage only"
            or recipe.get("precision") not in {"float32", "bfloat16"}
            or self.query_snapshot is not None
            and recipe.get("snapshot_hash") != self.query_snapshot
        ):
            raise HTTPException(503, "Recette documentaire incompatible avec le modèle commun")

    def search_gate(self, c, *, preview):
        if preview:
            self.read_gate(c, preview=True)
            release = laboratory_gate(c)
        else:
            release = self.read_gate(c, preview=False)
            if not release["representations_ready"] or not release["statistics_ready"]:
                raise HTTPException(503, "Représentations indisponibles")
            n = c.execute(
                text(
                    f"SELECT count(*) FROM documentary.search_unit u JOIN documentary.document d USING(corpus_id,release_id,document_id) WHERE {PUBLIC_ELIGIBLE}"
                ),
                SCOPE,
            ).scalar_one()
            if n != release["lexical_statistics"]["units"]:
                raise HTTPException(503, "Statistiques du périmètre public incompatibles")
        self.check_representations(release)
        return release

    def available(self, *, preview):
        if not self.ready:
            return False
        try:
            with self.destination.transaction(readonly=True) as c:
                self.read_gate(c, preview=preview)
            return True
        except HTTPException as e:
            if e.status_code == 404:
                return False
            raise

    def start(self):
        if self.config.get("local_preview"):
            from documentary.local_application import LOCAL_IDENTITY

            if settings.ENV != "dev" or self.config["expected_target"] != LOCAL_IDENTITY:
                raise ValueError(
                    "Unpublished preview is restricted to the explicitly identified local dev database"
                )
            url = self.destination.engine.url
            if url.host not in {None, "127.0.0.1", "::1"} or (
                url.host is None and url.query.get("host") != "/var/run/postgresql"
            ):
                raise ValueError("Unpublished preview requires a local PostgreSQL transport")
        with self.destination.transaction(readonly=True) as c:
            # Access metadata only. No migration/import or implicit public activation.
            if (
                c.execute(text("SELECT version_num FROM documentary.alembic_version")).scalar_one()
                != "doc_0001"
            ):
                raise ValueError("Documentary migration revision incompatible")
        self.ready = True

    def predicate(self, preview, *, catalogue=True):
        return (
            "d.candidate"
            if preview
            else (
                "d.candidate AND d.readable AND d.catalogue_visible"
                if catalogue
                else "d.candidate AND d.readable"
            )
        )

    def metadata(self, row):
        m = row["source_metadata"]["metadata"]
        original = m.get("original_metadata") or {}
        origin = m.get("origin") or {}

        def safe_url(url):
            return url if isinstance(url, str) and url.startswith("https://") else None

        return dict(
            document_id=row["document_id"],
            release_id=row["release_id"],
            title=row["display_title"],
            source_title=row["source_title"],
            place=origin.get("label"),
            orders=m.get("historical_orders", [])
            if m.get("historical_orders_status") == "explicit_in_metadata_title"
            else [],
            reference=reference_text(original.get("bibliographic_citation")),
            sources=[
                dict(label=label, url=url)
                for label, url in [
                    ("Notice Persée", safe_url(original.get("document_url"))),
                    ("Transcription Stanford", safe_url(row["provenance"].get("scan_url"))),
                ]
                if url
            ],
            warnings=[dict(code=k, message=v["message"]) for k, v in row["warnings"].items()],
            url=document_url(row["document_id"], row["release_id"]),
            edition_order=row["edition_order"],
        )

    def catalogue(self, page, size, *, preview):
        with self.destination.transaction(readonly=True) as c:
            c.execute(text("SET LOCAL statement_timeout='2s'"))
            self.read_gate(c, preview=preview)
            pred = self.predicate(preview)
            total = c.execute(
                text(f"SELECT count(*) FROM documentary.document d WHERE {WHERE} AND {pred}"), SCOPE
            ).scalar_one()
            rows = (
                c.execute(
                    text(f"""SELECT d.* FROM documentary.document d WHERE {WHERE} AND {pred}
                ORDER BY edition_order LIMIT :size OFFSET :offset"""),
                    dict(SCOPE, size=size, offset=(page - 1) * size),
                )
                .mappings()
                .all()
            )
            return dict(
                items=[self.metadata(r) for r in rows],
                page=page,
                page_size=size,
                total=total,
                has_next=page * size < total,
                preview=preview,
            )

    def read(self, release, document_id, unit, *, preview):
        # Never remap an old release/anchor to a different canonical text.
        if release != SCOPE["release"]:
            raise HTTPException(404, "Version documentaire indisponible")
        with self.destination.transaction(readonly=True) as c:
            c.execute(text("SET LOCAL statement_timeout='2s'"))
            self.read_gate(c, preview=preview)
            pred = self.predicate(preview, catalogue=False)
            catalogue_pred = self.predicate(preview)
            row = (
                c.execute(
                    text(
                        f"SELECT d.* FROM documentary.document d WHERE {WHERE} AND {pred} AND document_id=:id"
                    ),
                    dict(SCOPE, id=document_id),
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise HTTPException(404, "Cahier indisponible")
            witness = None
            if unit:
                witness = (
                    c.execute(
                        text(f"""SELECT unit_id,start_offset,end_offset,text_sha256 FROM documentary.search_unit
                    WHERE {WHERE} AND document_id=:id AND unit_id=:unit"""),
                        dict(SCOPE, id=document_id, unit=unit),
                    )
                    .mappings()
                    .one_or_none()
                )
                if witness is None:
                    raise HTTPException(404, "Passage absent de cette version du cahier")
            prev = c.execute(
                text(
                    f"SELECT document_id FROM documentary.document d WHERE {WHERE} AND {catalogue_pred} AND edition_order<:ord ORDER BY edition_order DESC LIMIT 1"
                ),
                dict(SCOPE, ord=row["edition_order"]),
            ).scalar_one_or_none()
            nxt = c.execute(
                text(
                    f"SELECT document_id FROM documentary.document d WHERE {WHERE} AND {catalogue_pred} AND edition_order>:ord ORDER BY edition_order LIMIT 1"
                ),
                dict(SCOPE, ord=row["edition_order"]),
            ).scalar_one_or_none()
            full = row["full_text"]
            if hashlib.sha256(full.encode()).hexdigest() != row["text_sha256"]:
                raise HTTPException(503, "Empreinte documentaire incompatible")
            if witness:
                a, z = witness["start_offset"], witness["end_offset"]
                value = full[a:z]
                if hashlib.sha256(value.encode()).hexdigest() != witness["text_sha256"]:
                    raise HTTPException(503, "Empreinte du passage incompatible")
                blocks = [
                    dict(text=full[:a], anchor=None),
                    dict(text=value, anchor="passage-" + unit),
                    dict(text=full[z:], anchor=None),
                ]
            else:
                blocks = [dict(text=full, anchor=None)]
            return dict(
                **self.metadata(row),
                blocks=blocks,
                selected_unit=dict(witness) if witness else None,
                previous=document_url(prev, release) if prev else None,
                next=document_url(nxt, release) if nxt else None,
                preview=preview,
                text_sha256=row["text_sha256"],
            )
