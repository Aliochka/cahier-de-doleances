"""Bounded read-only local check; never generates statistics or loads BGE-M3."""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    from app.db import DB_URL
    from app.routers import api_forms, api_questions

    url = make_url(DB_URL)
    if url.database != "cahier_doleances_local" or url.host not in (
        None,
        "127.0.0.1",
        "localhost",
        "::1",
    ):
        raise SystemExit("Recette limitée au corpus applicatif local Hal9000.")
    engine = create_engine(
        DB_URL,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )
    api_forms.SessionLocal = api_questions.SessionLocal = sessionmaker(engine)
    app = FastAPI()
    app.include_router(api_forms.router)
    app.include_router(api_questions.router)
    statements, observations = [], []

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
        assert not re.search(
            r"\b(?:FROM|JOIN)\s+(?:public\.)?(?:answers|answer_options)\b", statement, re.I
        )

    try:
        with TestClient(app) as client:
            forms = client.get("/api/v1/forms").json()
            assert len(forms) == 7
            total = 0
            generations = set()
            for form in forms:
                identifier = form["id"]
                statements.clear()
                start = time.monotonic()
                response = client.get(f"/api/v1/forms/{identifier}")
                seconds = time.monotonic() - start
                assert response.status_code == 200
                body = response.json()
                assert body["statistics_availability"]["status"] == "available"
                generations.add(body["statistics_availability"]["generation_id"])
                assert len(body["questions"]) == body["questions_count"]
                assert len(statements) == 3
                assert all(
                    isinstance(q["id"], str) and q["answers_count"] is not None
                    for q in body["questions"]
                )
                ordering = [
                    (q["position"] if q["position"] is not None else 999999, int(q["id"]))
                    for q in body["questions"]
                ]
                assert ordering == sorted(ordering)
                total += len(body["questions"])
                observations.append(
                    {
                        "form_id": identifier,
                        "seconds": seconds,
                        "bytes": len(response.content),
                        "selects": len(statements),
                        "questions": len(body["questions"]),
                    }
                )
                stats = client.get(f"/api/v1/forms/{identifier}/stats")
                assert stats.status_code == 200
                by_id = {
                    item["question"]["id"]: item["stats"] for item in stats.json()["questions"]
                }
                for question in body["questions"]:
                    if question["type"] in ("single_choice", "multi_choice"):
                        assert question["statistics"] == by_id[question["id"]]
            assert total == 120 and len(generations) == 1
            for qid in ("2", "4", "159"):
                start = time.monotonic()
                response = client.get(f"/api/v1/questions/{qid}/stats")
                assert response.status_code == 200
                observations.append(
                    {
                        "question_id": qid,
                        "seconds": time.monotonic() - start,
                        "bytes": len(response.content),
                    }
                )
            print(
                json.dumps(
                    {
                        "forms": len(forms),
                        "questions": total,
                        "generation": next(iter(generations)),
                        "aggregations_on_sources": 0,
                        "requests": observations,
                    },
                    indent=2,
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
