"""Local corpus selection and versioned per-document rebuilds; no public application."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from articles import Journal, canonical
from reviewlib import Conflict, sha


def discover():
    from production import current_directory

    return current_directory()


def overrides(directory, private_root):
    log = Journal(Path(private_root) / "rebuilds.jsonl")
    if not log.journal.exists():
        return []
    latest = {}
    for event in log.history():
        if event["corpus_directory"] == str(Path(directory).resolve()):
            latest[event["document_id"]] = event
    result = []
    root = Path(private_root).resolve()
    for event in latest.values():
        path = (root / event["artifact"]).resolve()
        if root not in path.parents or sha(path.read_bytes()) != event["artifact_sha256"]:
            raise ValueError("Rebuild artifact integrity error")
        result.append(json.loads(path.read_text()))
    return result


def rebuild(store, engine, key, expected_event):
    from production import extract_one

    if not (engine.directory / "complete.json").exists():
        raise Conflict("Activez le corpus global avant une reconstruction documentaire.")
    from boundary_rules import effective

    record = effective(store.by_id[key], store.automatic_corrections.get(key))
    state = store.state(record)
    if state["status"] != "human_validated" or state["stale"]:
        raise Conflict("Validez d’abord les frontières du document dans le mode Cahiers.")
    if (state["event"] or {}).get("id") != expected_event:
        raise Conflict("La décision du cahier a changé. Rechargez le dossier.")
    article_history = [e for e in engine.log.history() if e["document_id"] == key]
    if article_history:
        if key in engine.parents and engine.parent_version(engine.parents[key])["compatible"]:
            return dict(
                document_id=key,
                retained=True,
                message="Les frontières et les décisions d’articles existantes sont déjà compatibles ; elles sont conservées.",
            )
        raise Conflict(
            "Ce document contient des décisions humaines sur les articles. Le changement de parent nécessite une réconciliation explicite ; aucune validation n’a été écrasée. Restaurez le périmètre précédent ou conservez le dossier bloqué pour réconciliation."
        )
    entry, parent, units, raw = extract_one(store, record, state)
    if parent is None:
        raise Conflict(
            "La notice ne permet pas une reconstruction sûre : " + entry["extraction_state"]
        )
    engine.check(parent, [engine.record_from_unit(parent, u) for u in units])
    root = engine.override_directory
    root.mkdir(parents=True, exist_ok=True)
    payload = dict(parent=parent, units=units, inventory=entry, automatic_proposals=raw)
    artifact = canonical(payload) + "\n"
    name = sha(artifact) + ".json"
    path = root / name
    if not path.exists():
        temp = root / (name + ".tmp")
        temp.write_text(artifact)
        os.replace(temp, path)
    log = Journal(root / "rebuilds.jsonl")
    with log.locked_journal() as f:
        history = log.history()
        event = dict(
            id=str(uuid.uuid4()),
            action="explicit_document_rebuild",
            actor_type="system_extraction_after_user_request",
            date=datetime.now(timezone.utc).isoformat(),
            corpus_directory=str(engine.directory.resolve()),
            document_id=key,
            parent_event_id=expected_event,
            parent_extent_id=parent["extent_id"],
            artifact=name,
            artifact_sha256=sha(path.read_bytes()),
            previous_hash=history[-1]["event_hash"] if history else None,
        )
        event["event_hash"] = sha(canonical(event))
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    engine.refresh()
    return dict(
        document_id=key,
        articles=sum(u["type"] == "article" for u in units),
        message="Document reconstruit depuis les frontières humaines ; version précédente conservée.",
    )
