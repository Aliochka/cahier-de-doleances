"""Stockage dédié : lots et checkpoints atomiques, verrous de progression."""

import hashlib
import struct

from sqlalchemy import text

from cahier_rag.contracts import canonical_json
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.sources.gdn import Cursor
from cahier_rag.storage import document_record, restore_document

SPACES = frozenset({"pilot100k", "full"})


def vector_hash(vector):
    return hashlib.sha256(struct.pack("<1024f", *vector)).hexdigest()


def decode_vector_binary(value):
    """pgvector send : dimension/reserved uint16, puis float32 réseau.

    Le transport binaire préserve notamment le bit de signe des zéros, que
    json.loads("[-0]") transforme en entier zéro positif.
    """
    raw = bytes(value)
    if len(raw) != 4100 or struct.unpack("!HH", raw[:4]) != (1024, 0):
        raise ValueError("Protocole vector(1024) incompatible.")
    return struct.unpack("!1024f", raw[4:])


def vector_literal(value):
    """Arrondir UNE fois en float32 avant transport décimal PostgreSQL.

    Les coordonnées restent une chaîne JSON, pour préserver aussi -0.0 dans
    le transit JSONB. Le SHA porte sur ces mêmes octets float32.
    """
    quantized = struct.unpack("<1024f", struct.pack("<1024f", *value))
    return "[" + ",".join(repr(x) for x in quantized) + "]"


def chain(previous, documents):
    for doc in documents:
        previous = hashlib.sha256(
            (previous + doc.document_id + doc.content_hash).encode()
        ).hexdigest()
    return previous


def require_space(space):
    if space not in SPACES:
        raise ValueError("Espace RAG-026 inconnu.")
    return space


class FullStore:
    def __init__(self, guard, space):
        self.guard, self.space = guard, require_space(space)

    def state(self, connection=None, *, lock=False):
        if connection is None:
            with self.guard.transaction() as (c, _):
                return self.state(c)
        row = (
            connection.execute(
                text(
                    "SELECT * FROM rag_full.spaces WHERE space_id=:space"
                    + (" FOR UPDATE" if lock else "")
                ),
                {"space": self.space},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ValueError("Espace non initialisé.")
        if fingerprint(row["manifest"]) != row["recipe_hash"]:
            raise ValueError("Manifeste modifié.")
        return dict(row)

    def initialize(self, manifest, expected):
        with self.guard.transaction() as (c, identity):
            if manifest["audit_source"] != identity.to_dict():
                raise ValueError("Source différente de l'audit.")
            c.execute(
                text("""INSERT INTO rag_full.spaces(space_id,manifest,recipe_hash,expected_units)
                VALUES (:space,CAST(:manifest AS jsonb),:hash,:expected) ON CONFLICT DO NOTHING"""),
                dict(
                    space=self.space,
                    manifest=canonical_json(manifest),
                    hash=fingerprint(manifest),
                    expected=expected,
                ),
            )
            state = self.state(c)
            if state["recipe_hash"] != fingerprint(manifest) or state["expected_units"] != expected:
                raise ValueError("Reprise incompatible : paramètres/versions différents.")
        return state

    def commit_documents(self, batch, before):
        documents = batch.documents
        if (
            before["extraction_complete"]
            or before["documents"] + len(documents) > before["expected_units"]
        ):
            raise ValueError("Extraction close ou plafond dépassé.")
        records = [
            document_record(d) | {"ordinal": before["documents"] + i + 1}
            for i, d in enumerate(documents)
        ]
        after_hash = chain(before["chain_hash"], documents)
        cursor = batch.next_cursor.to_dict() if batch.next_cursor else None
        with self.guard.transaction() as (c, _):
            c.execute(text("SET LOCAL statement_timeout='60s'"))
            actual = self.state(c, lock=True)
            if (actual["documents"], actual["cursor"]) != (before["documents"], before["cursor"]):
                raise ValueError("Progression concurrente détectée.")
            if records:
                c.execute(
                    text("""INSERT INTO rag_full.documents
                    (space_id,document_id,ordinal,answer_id,contribution_id,questionnaire_id,
                     unit_type,content_hash,record,search_vector,historical_split)
                    SELECT :space,r->>'document_id',(r->>'ordinal')::bigint,
                    (r->>'answer_id')::bigint,(r->>'contribution_id')::bigint,
                    (r->>'questionnaire_id')::bigint,r->>'unit_type',r->>'content_hash',
                    r-'ordinal',setweight(to_tsvector('pg_catalog.french',r->>'text'),'A'),
                    m.split FROM jsonb_array_elements(CAST(:records AS jsonb)) r
                    LEFT JOIN rag.lexical_members m ON m.document_id=r->>'document_id'
                    AND m.sample_hash='d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc'
                    ON CONFLICT DO NOTHING"""),
                    dict(space=self.space, records=canonical_json(records)),
                )
                valid = c.execute(
                    text("""SELECT count(*) FROM rag_full.documents d
                    JOIN jsonb_array_elements(CAST(:records AS jsonb)) r
                    ON d.document_id=r->>'document_id' AND d.space_id=:space
                    WHERE d.content_hash=r->>'content_hash' AND d.ordinal=(r->>'ordinal')::bigint"""),
                    dict(space=self.space, records=canonical_json(records)),
                ).scalar_one()
                if valid != len(records):
                    raise ValueError("Identité/empreinte documentaire en conflit.")
            c.execute(
                text("""UPDATE rag_full.spaces SET documents=:n,cursor=CAST(:cursor AS jsonb),
                          chain_hash=:hash,updated_at=now() WHERE space_id=:space"""),
                dict(
                    n=before["documents"] + len(documents),
                    cursor=canonical_json(cursor),
                    hash=after_hash,
                    space=self.space,
                ),
            )
        return len(documents)

    def finish_extraction(self):
        with self.guard.transaction() as (c, _):
            state = self.state(c, lock=True)
            if state["documents"] != state["expected_units"]:
                raise ValueError("Inventaire et extraction ne concordent pas.")
            c.execute(
                text("UPDATE rag_full.spaces SET extraction_complete=true WHERE space_id=:space"),
                {"space": self.space},
            )

    def documents(self, after=0, limit=100):
        with self.guard.transaction() as (c, _):
            rows = (
                c.execute(
                    text(
                        "SELECT ordinal,record FROM rag_full.documents "
                        "WHERE space_id=:space AND ordinal>:after ORDER BY ordinal LIMIT :n"
                    ),
                    dict(space=self.space, after=after, n=limit),
                )
                .mappings()
                .all()
            )
        return [(r["ordinal"], restore_document(r["record"])) for r in rows]

    def commit_vectors(self, before, last_ordinal, rows):
        if (
            before["vectors_complete"]
            or not before["extraction_complete"]
            or last_ordinal > before["documents"]
            or last_ordinal <= before["vector_cursor"]
            or not rows
        ):
            raise ValueError("Progression vectorielle invalide.")
        for row in rows:
            if row["vector_hash"] != vector_hash(row["embedding"]):
                raise ValueError("Empreinte vectorielle incohérente.")
        stored_rows = [r | {"embedding": vector_literal(r["embedding"])} for r in rows]
        with self.guard.transaction() as (c, _):
            c.execute(text("SET LOCAL statement_timeout='60s'"))
            actual = self.state(c, lock=True)
            if actual["vector_cursor"] != before["vector_cursor"]:
                raise ValueError("Progression vectorielle concurrente.")
            c.execute(
                text("""INSERT INTO rag_full.segments
                (space_id,document_id,segment_index,representation_id,start_offset,end_offset,
                 tokens,content_hash,vector_hash,embedding)
                SELECT :space,r->>'document_id',(r->>'segment_index')::int,r->>'representation_id',
                (r->>'start')::int,(r->>'end')::int,(r->>'tokens')::int,r->>'content_hash',
                r->>'vector_hash',CAST(r->>'embedding' AS public.vector)
                FROM jsonb_array_elements(CAST(:rows AS jsonb)) r"""),
                dict(space=self.space, rows=canonical_json(stored_rows)),
            )
            c.execute(
                text("""UPDATE rag_full.spaces SET vector_cursor=:cursor,segments=segments+:n,
                updated_at=now(),vectors_complete=(:cursor=documents) WHERE space_id=:space"""),
                dict(space=self.space, cursor=last_ordinal, n=len(rows)),
            )

    def verify(self):
        # Streaming, pas de collection des millions d'identifiants.
        state = self.state()
        previous, count, after = "", 0, 0
        while docs := self.documents(after, 1000):
            previous = chain(previous, [d for _, d in docs])
            count += len(docs)
            after = docs[-1][0]
            if count % 100000 == 0:
                print(
                    canonical_json(
                        dict(phase="verify_documents", units=count, total=state["expected_units"])
                    ),
                    flush=True,
                )
        if previous != state["chain_hash"] or count != state["expected_units"]:
            raise ValueError("Intégrité documentaire invalide.")
        with self.guard.transaction() as (c, _):
            actual = self.state(c, lock=True)
            if not actual["extraction_complete"] or not actual["vectors_complete"]:
                raise ValueError("Index incomplet.")
            invalid = c.execute(
                text("""SELECT count(*) FROM rag_full.documents d
                WHERE d.space_id=:space AND NOT EXISTS(SELECT 1 FROM rag_full.segments s
                WHERE s.space_id=d.space_id AND s.document_id=d.document_id)"""),
                {"space": self.space},
            ).scalar_one()
            if invalid:
                raise ValueError("Documents sans vecteur.")
            # Vérifier les vecteurs et les offsets sans charger l'index entier.
            result = c.execution_options(stream_results=True).execute(
                text("""
                SELECT s.space_id,s.document_id,s.segment_index,s.representation_id,
                s.start_offset,s.end_offset,s.tokens,s.content_hash,s.vector_hash,
                public.vector_send(s.embedding) AS embedding_binary,
                d.record,char_length(d.record->>'text') AS length
                FROM rag_full.segments s JOIN rag_full.documents d USING(space_id,document_id)
                WHERE s.space_id=:space ORDER BY d.ordinal,s.segment_index"""),
                {"space": self.space},
            )
            n = 0
            last = None
            try:
                for row in result.mappings():
                    if last is None or last["document_id"] != row["document_id"]:
                        if last is not None and last["end_offset"] != last["length"]:
                            raise ValueError("Dernier segment incomplet.")
                        if row["segment_index"] != 0 or row["start_offset"] != 0:
                            raise ValueError("Premier segment manquant.")
                    elif (
                        row["segment_index"] != last["segment_index"] + 1
                        or not last["start_offset"] < row["start_offset"] <= last["end_offset"]
                        or row["end_offset"] <= last["end_offset"]
                    ):
                        raise ValueError("Progression des segments incohérente.")
                    last = row
                    values = decode_vector_binary(row["embedding_binary"])
                    if row["end_offset"] > row["length"]:
                        raise ValueError("Positions dépassant le texte source.")
                    if vector_hash(values) != row["vector_hash"]:
                        raise ValueError(
                            f"Empreinte vectorielle altérée : {row['document_id']} segment {row['segment_index']}."
                        )
                    from cahier_rag.fullcorpus.pipeline import prepare_metadata

                    doc = restore_document(row["record"])
                    item = prepare_metadata(
                        doc,
                        state["recipe_hash"],
                        row["start_offset"],
                        row["end_offset"],
                        row["segment_index"],
                        row["tokens"],
                    )
                    if (
                        item["representation_id"] != row["representation_id"]
                        or item["content_hash"] != row["content_hash"]
                    ):
                        raise ValueError("Provenance de segment altérée.")
                    n += 1
                    if n % 100000 == 0:
                        print(
                            canonical_json(
                                dict(phase="verify_segments", segments=n, total=state["segments"])
                            ),
                            flush=True,
                        )
            finally:
                result.close()
            if last is not None and last["end_offset"] != last["length"]:
                raise ValueError("Dernier segment incomplet.")
            if n != actual["segments"]:
                raise ValueError("Nombre de segments incohérent.")
            c.execution_options(stream_results=False).execute(
                text("UPDATE rag_full.spaces SET verified=true WHERE space_id=:space"),
                {"space": self.space},
            )
        return dict(documents=count, segments=n, chain_hash=previous, verified=True)

    def cursor(self, state):
        return Cursor.from_dict(state["cursor"]) if state["cursor"] else None
