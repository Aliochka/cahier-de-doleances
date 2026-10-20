"""Adaptation technique du keyset RAG-004, même projection et transformation."""

from sqlalchemy import text

from cahier_rag.db import source_connection
from cahier_rag.sources.gdn import ANSWER_SELECT, GdnReader


class FullReader(GdnReader):
    def __init__(self, engine, *, pilot=False, batch_size=1000):
        super().__init__(engine, batch_size=batch_size)
        self.pilot = pilot

    def _read_rows(self, after):
        # L'audit préalable valide la structure JSON. Ce prédicat saute les choix
        # sans texte libre, sans toucher à la transformation row_to_documents.
        conditions = [
            "(q.type='text' OR (q.type IN ('single_choice','multi_choice') "
            "AND a.value_json IS NOT NULL "
            "AND jsonb_array_length(coalesce(a.value_json::jsonb->'other_text',"
            "'[]'::jsonb))>0))"
        ]
        params = {"limit": self.batch_size}
        if after:
            conditions.append("a.id > :after" if after.unit_index is None else "a.id >= :after")
            params["after"] = after.answer_id
        if self.pilot:
            # Stable sur le serveur figé ; tous les ID d'une contribution suivent
            # le même tirage. Le pilote n'est pas un nouvel ensemble d'évaluation.
            conditions.append("mod(hashtextextended(a.contribution_id::text,26),50)=0")
        with source_connection(self.engine) as connection:
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            connection.execute(text("SET LOCAL lock_timeout='2s'"))
            return (
                connection.execute(
                    text(
                        ANSWER_SELECT
                        + " WHERE "
                        + " AND ".join(conditions)
                        + " ORDER BY a.id LIMIT :limit"
                    ),
                    params,
                )
                .mappings()
                .all()
            )
