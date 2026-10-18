"""Persistance pgvector explicite, sans numpy, torch ni adaptateur global psycopg."""

import hashlib
import json
import math
import struct

from sqlalchemy import text

from cahier_rag.contracts import canonical_json
from cahier_rag.db import source_connection
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.lexical import SearchResult
from cahier_rag.storage import restore_document
from cahier_rag.vector.preparation import representation_identity


def float32_vector(values):
    if len(values) != 1024 or not all(math.isfinite(x) for x in values):
        raise ValueError("Vecteur BGE-M3 invalide : 1024 valeurs finies requises.")
    try:
        binary = struct.pack("<1024f", *values)
    except (OverflowError, struct.error):
        raise ValueError("Vecteur hors domaine float32.") from None
    vector = struct.unpack("<1024f", binary)
    if abs(math.sqrt(math.fsum(x * x for x in vector)) - 1) > 1e-4:
        raise ValueError("Vecteur non normalisé L2.")
    return canonical_json(list(vector)), hashlib.sha256(binary).hexdigest()


def recipe(prepared, *, precision="bfloat16"):
    if precision not in {"float32", "bfloat16"}:
        raise ValueError("Précision non validée pour cet espace.")
    return {
        "version": 1,
        "prepared": prepared,
        "model": MODELS["bge-m3"].to_dict(),
        "dimension": 1024,
        "storage": "float32",
        "normalization": "L2",
        "precision": precision,
        "pooling": "cls",
        "aggregation": "max-cosine",
        "query_prefix": "",
        "document_prefix": "",
    }


class VectorStore:
    def __init__(self, guard, scope, configuration):
        self.guard, self.scope, self.configuration = guard, scope, configuration
        if (
            configuration != recipe(configuration["prepared"], precision=configuration["precision"])
            or configuration["prepared"]["sample_hash"] != scope.sample_hash
            or configuration["prepared"]["units"] != len(scope.documents)
        ):
            raise ValueError("Recette vectorielle ou corpus incompatible.")
        self.space_id = digest(configuration)

    @staticmethod
    def timeouts(connection):
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        connection.execute(text("SET LOCAL lock_timeout='3s'"))

    def _locked(self, connection):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": self.space_id}
        )
        row = (
            connection.execute(
                text("SELECT * FROM rag.vector_spaces WHERE space_id=:id FOR UPDATE"),
                {"id": self.space_id},
            )
            .mappings()
            .one()
        )
        self._compatible(row)
        return row

    def _compatible(self, row):
        if row["manifest"] != self.configuration or row["sample_hash"] != self.scope.sample_hash:
            raise ValueError("Espace vectoriel incompatible.")

    def initialize(self):
        with self.guard.transaction() as (connection, _):
            self.timeouts(connection)
            connection.execute(
                text("""
                INSERT INTO rag.vector_spaces(space_id,sample_hash,manifest,expected_units,expected_segments)
                VALUES(:id,:sample,CAST(:manifest AS jsonb),:units,:segments)
                ON CONFLICT(space_id) DO NOTHING
            """),
                {
                    "id": self.space_id,
                    "sample": self.scope.sample_hash,
                    "manifest": canonical_json(self.configuration),
                    "units": len(self.scope.documents),
                    "segments": self.configuration["prepared"]["segments"],
                },
            )
            self._locked(connection)
        return self.status()

    def status(self):
        with source_connection(self.guard.target) as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM rag.vector_spaces WHERE space_id=:id"),
                    {"id": self.space_id},
                )
                .mappings()
                .one()
            )
            self._compatible(row)
            return dict(row)

    def commit(self, unit_offset, groups, vectors):
        """CAS sur le checkpoint : concurrence refusée, retry identique idempotent."""
        items = [item for group in groups for item in group]
        if len(items) != len(vectors) or not groups:
            raise ValueError("Lot de vecteurs incompatible.")
        wanted = sorted(self.scope.documents)[unit_offset : unit_offset + len(groups)]
        if wanted != [group[0]["document_id"] for group in groups]:
            raise ValueError("Ordre des unités incompatible avec le checkpoint.")
        records = []
        for item, vector in zip(items, vectors):
            expected = self.scope.documents.get(item["document_id"])
            check = dict(item)
            claimed = check.pop("content_hash")
            if (
                not expected
                or item["source_hash"] != expected["content_hash"]
                or item["split"] != expected["split"]
                or digest(check) != claimed
                or item["representation_id"] != representation_identity(item)
                or item["configuration"] != self.configuration["prepared"]["configuration"]
            ):
                raise ValueError("Unité modifiée ou extérieure au corpus.")
            literal, checksum = float32_vector(vector)
            records.append(
                {
                    "space": self.space_id,
                    "id": item["representation_id"],
                    "document": item["document_id"],
                    "source": item["source_hash"],
                    "content": item["content_hash"],
                    "split": item["split"],
                    "index": item["segment_index"],
                    "start": item["start"],
                    "end": item["end"],
                    "payload": canonical_json(item),
                    "vector": literal,
                    "hash": checksum,
                }
            )
        with self.guard.transaction() as (connection, _):
            self.timeouts(connection)
            state = self._locked(connection)
            retry = state["completed_units"] >= unit_offset + len(groups)
            if state["completed_units"] != unit_offset and not retry:
                raise ValueError("Checkpoint concurrent ou position de reprise incompatible.")
            for record in records:
                old = (
                    connection.execute(
                        text("""
                    SELECT content_hash,vector_hash FROM rag.vector_representations
                    WHERE space_id=:space AND representation_id=:id
                """),
                        record,
                    )
                    .mappings()
                    .one_or_none()
                )
                if old:
                    if (
                        old["content_hash"] != record["content"]
                        or old["vector_hash"] != record["hash"]
                    ):
                        raise ValueError("Conflit d'empreinte vectorielle ; aucun écrasement.")
                    continue
                if retry:
                    raise ValueError("Checkpoint corrompu : représentation manquante.")
                # Vérification du contenu stocké dans la même transaction que les vecteurs.
                source = (
                    connection.execute(
                        text("SELECT * FROM rag.text_units WHERE document_id=:document"), record
                    )
                    .mappings()
                    .one()
                )
                if restore_document(source).content_hash != record["source"]:
                    raise ValueError("Document original modifié depuis la préparation.")
                connection.execute(
                    text("""
                    INSERT INTO rag.vector_representations
                    (space_id,representation_id,document_id,source_hash,content_hash,split,
                     segment_index,start_offset,end_offset,payload,embedding,vector_hash)
                    VALUES(:space,:id,:document,:source,:content,:split,:index,:start,:end,
                           CAST(:payload AS jsonb),CAST(:vector AS public.vector(1024)),:hash)
                """),
                    record,
                )
            if not retry:
                connection.execute(
                    text("""
                    UPDATE rag.vector_spaces SET completed_units=completed_units+:units,
                    completed_segments=completed_segments+:segments, updated_at=now() WHERE space_id=:id
                """),
                    {"units": len(groups), "segments": len(items), "id": self.space_id},
                )

    def verify(self, *, require_complete=False):
        """Validation indépendante du modèle, mémoire bornée à une unité/vecteur."""
        state = self.status()
        expected_ids = sorted(self.scope.documents)[: state["completed_units"]]
        found, count, aggregate = {}, 0, hashlib.sha256()
        previous_id, previous_end, previous_start, previous_length = None, 0, -1, 0
        with source_connection(self.guard.target) as connection:
            self.timeouts(connection)
            statement = text("""
                SELECT r.*,r.embedding::text AS vector_text,u.content_hash AS actual_hash,
                       to_jsonb(u) AS original_record
                FROM rag.vector_representations r JOIN rag.text_units u USING(document_id)
                WHERE r.space_id=:id ORDER BY r.document_id,r.segment_index
            """)
            with connection.execution_options(stream_results=True, yield_per=1).execute(
                statement, {"id": self.space_id}
            ) as rows:
                for row in rows.mappings():
                    payload = row["payload"]
                    check = dict(payload)
                    claimed = check.pop("content_hash")
                    _, checksum = float32_vector(json.loads(row["vector_text"]))
                    did = row["document_id"]
                    expected = self.scope.documents.get(did)
                    original = restore_document(row["original_record"])
                    if did != previous_id:
                        if previous_id is not None and previous_end != previous_length:
                            raise ValueError("Fin de réponse absente de la segmentation.")
                        previous_end, previous_start = 0, -1
                    start, end = row["start_offset"], row["end_offset"]
                    if (
                        not 0 <= start < end <= len(original.text)
                        or start > previous_end
                        or start <= previous_start
                    ):
                        raise ValueError("Positions de segmentation invalides ou lacunaires.")
                    previous_id, previous_start, previous_end, previous_length = (
                        did,
                        start,
                        end,
                        len(original.text),
                    )
                    if (
                        not expected
                        or row["actual_hash"] != expected["content_hash"]
                        or row["source_hash"] != original.content_hash
                        or row["split"] != expected["split"]
                        or digest(check) != claimed
                        or claimed != row["content_hash"]
                        or checksum != row["vector_hash"]
                        or row["segment_index"] != found.get(did, 0)
                        or payload["document_id"] != did
                        or payload["source_hash"] != original.content_hash
                        or payload["representation_id"] != row["representation_id"]
                        or payload["representation_id"] != representation_identity(payload)
                        or payload["split"] != row["split"]
                        or payload["start"] != row["start_offset"]
                        or payload["end"] != row["end_offset"]
                        or payload["text"]
                        != "Question :\n"
                        + original.question_text
                        + "\n\nRéponse :\n"
                        + original.text[row["start_offset"] : row["end_offset"]]
                    ):
                        raise ValueError("Intégrité vectorielle invalide.")
                    found[did] = found.get(did, 0) + 1
                    count += 1
                    aggregate.update((row["representation_id"] + checksum).encode())
        if previous_id is not None and previous_end != previous_length:
            raise ValueError("Dernier segment incomplet.")
        if sorted(found) != expected_ids or count != state["completed_segments"]:
            raise ValueError("Index et checkpoint incohérents.")
        complete = len(found) == state["expected_units"] and count == state["expected_segments"]
        if require_complete and (not complete or state["state"] != "complete"):
            raise ValueError("Index incomplet ; recherche refusée.")
        return {
            "space_id": self.space_id,
            "units": len(found),
            "segments": count,
            "complete": complete,
            "vectors_hash": aggregate.hexdigest(),
        }

    def finish(self):
        report = self.verify()
        if not report["complete"]:
            raise ValueError("Index incomplet.")
        with self.guard.transaction() as (connection, _):
            self.timeouts(connection)
            self._locked(connection)
            connection.execute(
                text(
                    "UPDATE rag.vector_spaces SET state='complete',updated_at=now() WHERE space_id=:id"
                ),
                {"id": self.space_id},
            )
        return report

    def search(
        self, vector, *, limit=10, split="development", questionnaire_id=None, unit_type=None
    ):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or split not in {"development", "evaluation"}
        ):
            raise ValueError("Limite ou partition invalide.")
        if unit_type not in {None, "open_answer", "other_text"}:
            raise ValueError("Type documentaire invalide.")
        if questionnaire_id is not None and (
            type(questionnaire_id) is not int or questionnaire_id < 1
        ):
            raise ValueError("Identifiant questionnaire invalide.")
        # Vérification complète au chargement du moteur ; contrôle d'état à chaque requête.
        state = self.status()
        if state["state"] != "complete":
            raise ValueError("Index incomplet ; recherche refusée.")
        literal, _ = float32_vector(vector)
        with source_connection(self.guard.target) as connection:
            self.timeouts(connection)
            counts = (
                connection.execute(
                    text("""
                    SELECT count(*) AS segments,count(DISTINCT document_id) AS units
                    FROM rag.vector_representations WHERE space_id=:id
                """),
                    {"id": self.space_id},
                )
                .mappings()
                .one()
            )
            if (
                counts["segments"] != state["expected_segments"]
                or counts["units"] != state["expected_units"]
            ):
                raise ValueError("Index incomplet ; recherche refusée.")
            rows = (
                connection.execute(
                    text("""
                WITH scores AS (
                    SELECT r.document_id,min(r.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector(1024))) AS distance
                    FROM rag.vector_representations r JOIN rag.text_units u USING(document_id)
                    WHERE r.space_id=:id AND r.split=:split
                      AND (:form IS NULL OR u.questionnaire_id=:form)
                      AND (:kind IS NULL OR u.unit_type=:kind)
                    GROUP BY r.document_id
                ) SELECT u.*,1-s.distance AS score FROM scores s
                  JOIN rag.text_units u USING(document_id)
                  ORDER BY s.distance,s.document_id COLLATE "C" LIMIT :limit
            """),
                    {
                        "id": self.space_id,
                        "vector": literal,
                        "split": split,
                        "form": questionnaire_id,
                        "kind": unit_type,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )
        results = []
        for row in rows:
            unit = restore_document(row)
            if (
                unit.document_id not in self.scope.documents
                or unit.content_hash != self.scope.documents[unit.document_id]["content_hash"]
            ):
                raise ValueError("Résultat extérieur ou modifié.")
            results.append(SearchResult(unit, float(row["score"])))
        return results
