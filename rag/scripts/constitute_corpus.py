"""Opération locale RAG-007 : plan borné, extraction reprenable, sélection et audit.

Exécuter depuis rag/ ; aucun texte source n'est écrit dans les sorties.
Les requêtes doivent être bornées via PGOPTIONS (statement_timeout et lock_timeout).
"""

import argparse
import random
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.db import source_connection
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, write_json
from cahier_rag.evaluation.sampling import describe, digest, select_described_sample
from cahier_rag.extraction import ExtractionSpec
from cahier_rag.pipeline import run_extraction

SEED = 20261018
SPLIT_SEED = 1729
FORMS = (4, 5, 7, 10)


def save(path, value):
    """Remplacement atomique des seuls états opérationnels locaux, jamais des jugements."""
    temporary = path.with_suffix(".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        from cahier_rag.contracts import canonical_json

        stream.write(canonical_json(value) + "\n")
    temporary.replace(path)


def plan(store, directory):
    if (directory / "plan.json").exists():
        raise ValueError("Un plan existe déjà ; réutiliser ses étapes.")
    if shutil.disk_usage(directory).free < 1024**3:
        raise ValueError("Au moins 1 Gio libre requis.")
    rng = random.Random(SEED)
    windows = []
    contributions = []
    started = time.monotonic()
    with source_connection(store.guard.source) as connection:
        timeout = connection.execute(text("SHOW statement_timeout")).scalar_one()
        if timeout not in {"5s", "5000ms"}:
            raise ValueError("Cette opération requiert statement_timeout=5000 via PGOPTIONS.")
        bounds = (
            connection.execute(
                text("""
            SELECT form_id, min(id) AS lo, max(id) AS hi FROM public.contributions
            WHERE form_id IN (4,5,7,10) GROUP BY form_id ORDER BY form_id
        """)
            )
            .mappings()
            .all()
        )
    for bound in bounds:
        form, lo, hi = bound["form_id"], bound["lo"], bound["hi"]
        chosen = set()
        for zone in range(40):
            lower = lo + (hi - lo + 1) * zone // 40
            upper = lo + (hi - lo + 1) * (zone + 1) // 40
            anchor = lower + rng.randrange(max(1, (upper - lower) * 3 // 4))
            before = time.monotonic()
            with source_connection(store.guard.source) as connection:
                ids = (
                    connection.execute(
                        text("""
                    SELECT id FROM public.contributions
                    WHERE form_id=:form AND id>=:anchor AND id<:upper
                    ORDER BY id LIMIT 40
                """),
                        dict(form=form, anchor=anchor, upper=upper),
                    )
                    .scalars()
                    .all()
                )
            windows.append(
                dict(
                    form=form,
                    zone=zone,
                    lower=str(lower),
                    upper=str(upper),
                    anchor=str(anchor),
                    count=len(ids),
                    seconds=round(time.monotonic() - before, 6),
                )
            )
            chosen.update(ids)
        # Shuffle before chunks: each extraction contains contributions from several zones.
        ids = sorted(chosen)
        rng.shuffle(ids)
        for offset in range(0, len(ids), 500):
            contributions.append(
                dict(form=form, ids=[str(i) for i in sorted(ids[offset : offset + 500])])
            )
    if len(contributions) > 20:
        raise ValueError("Le plan dépasse vingt extractions.")
    value = dict(
        operation_version=1,
        seed=SEED,
        split_seed=SPLIT_SEED,
        corpus_version="gdn-2019-audit-2026-10-16",
        source_identity=store.guard.source_identity().to_dict(),
        windows=windows,
        chunks=contributions,
        seconds=time.monotonic() - started,
    )
    value["plan_hash"] = digest(value)
    write_json(directory / "plan.json", value)
    print(
        "Plan",
        len(contributions),
        "extractions ; contributions",
        sum(len(c["ids"]) for c in contributions),
    )


def load_plan(directory):
    planned = load_json(directory / "plan.json")
    expected = dict(planned)
    saved_hash = expected.pop("plan_hash")
    if digest(expected) != saved_hash:
        raise ValueError("Plan modifié : empreinte incohérente.")
    return planned


def extract(store, directory):
    planned = load_plan(directory)
    if store.guard.source_identity().to_dict() != planned["source_identity"]:
        raise ValueError("Identité source différente du plan.")
    path = directory / "progress.json"
    progress = (
        load_json(path) if path.exists() else {"plan_hash": planned["plan_hash"], "chunks": {}}
    )
    if progress["plan_hash"] != planned["plan_hash"]:
        raise ValueError("Plan incompatible avec la reprise.")
    from uuid import UUID

    for index, chunk in enumerate(planned["chunks"]):
        spec = ExtractionSpec(
            limit=10000,
            batch_size=100,
            questionnaire_id=chunk["form"],
            contribution_ids=tuple(map(int, chunk["ids"])),
            max_source_rows=100000,
        )
        key = str(index)
        if key not in progress["chunks"]:
            state = store.create_extraction(spec)
            progress["chunks"][key] = {"id": str(state.extraction_id), "batches": []}
            save(path, progress)
        record = progress["chunks"][key]
        state = store.get_state(UUID(record["id"]))
        while state.status != "completed":
            before = time.monotonic()
            state = run_extraction(store, state.extraction_id, expected_spec=spec, max_batches=1)
            elapsed = time.monotonic() - before
            record["batches"].append(
                dict(
                    seconds=elapsed,
                    documents=state.document_count,
                    rows=state.source_row_count,
                    revision=state.revision,
                )
            )
            record["state"] = state.to_dict()
            save(path, progress)
            print(
                "Lot",
                index,
                "documents",
                state.document_count,
                "lignes",
                state.source_row_count,
                "secondes",
                round(elapsed, 3),
                flush=True,
            )


def frame_data(store, directory):
    from uuid import UUID

    planned = load_plan(directory)
    progress = load_json(directory / "progress.json")
    states = [
        store.get_state(UUID(record["id"]))
        for _, record in sorted(progress["chunks"].items(), key=lambda p: int(p[0]))
    ]
    if len(states) != len(planned["chunks"]) or any(s.status != "completed" for s in states):
        raise ValueError("Extractions incomplètes.")
    if progress["plan_hash"] != planned["plan_hash"]:
        raise ValueError("Progression incompatible avec le plan.")
    for state, chunk in zip(states, planned["chunks"]):
        expected = ExtractionSpec(
            limit=10000,
            batch_size=100,
            questionnaire_id=chunk["form"],
            contribution_ids=tuple(map(int, chunk["ids"])),
            max_source_rows=100000,
        )
        store.validate_resume(state, store.guard.source_identity(), expected)
    rows = {}
    for state in states:
        for document in store.iter_documents(state.extraction_id):
            item = describe(document)
            if item["document_id"] in rows and rows[item["document_id"]] != item:
                raise ValueError("Conflit documentaire.")
            rows[item["document_id"]] = item
            if len(rows) > 100000:
                raise ValueError("Cadre trop grand.")
    frame = dict(
        corpus_version=planned["corpus_version"],
        plan_hash=planned["plan_hash"],
        extractions=[s.to_dict() for s in states],
    )
    return list(rows.values()), frame


def selections(rows, frame):
    options = dict(seed=SEED, split_seed=SPLIT_SEED, frame=frame)
    random_sample = select_described_sample(rows, size=10000, method="random", **options)
    random_ids = {d["document_id"] for d in random_sample["documents"]}
    # Default quotas are stable above 800 units; union size grows one at a time.
    lo, hi = 10000, 20000
    while lo < hi:
        mid = (lo + hi) // 2
        candidate = select_described_sample(
            rows, size=mid, method="stratified", **(options | {"seed": SEED + 1})
        )
        union = random_ids | {d["document_id"] for d in candidate["documents"]}
        if len(union) < 20000:
            lo = mid + 1
        else:
            hi = mid
    stratified = select_described_sample(
        rows, size=lo, method="stratified", **(options | {"seed": SEED + 1})
    )
    union = {d["document_id"]: d for d in random_sample["documents"] + stratified["documents"]}
    if len(union) != 20000 or stratified["shortfalls"] or stratified["size_shortfall"]:
        raise ValueError("Vingt mille unités et tous les quotas sont requis.")
    final = dict(random_sample)
    final.update(
        method="union",
        requested_size=20000,
        documents=sorted(union.values(), key=lambda d: d["document_id"]),
        selections={
            "random": random_sample["selected_hash"],
            "stratified": stratified["selected_hash"],
        },
    )
    final["selected_hash"] = digest(final["documents"])
    final["scope"] = "Union expérimentale enrichie, non représentative du corpus national."
    final["statistics"] = statistics(final["documents"])
    final["quotas"] = stratified["quotas"]
    final["shortfalls"] = {}
    return random_sample, stratified, final


def statistics(rows, *, with_types=True):
    lengths = sorted(r["length"] for r in rows)
    texts = Counter(r["text_hash"] for r in rows)
    parents = Counter(
        (r["corpus_id"], r["contribution_id"]) for r in rows if r["unit_type"] == "open_answer"
    )
    result = dict(
        count=len(rows),
        forms=dict(Counter(r["questionnaire_id"] for r in rows)),
        types=dict(Counter(r["unit_type"] for r in rows)),
        splits=dict(Counter(r["split"] for r in rows)) if rows and "split" in rows[0] else {},
        length=dict(
            min=lengths[0],
            max=lengths[-1],
            mean=sum(lengths) / len(lengths),
            **{f"p{p}": lengths[(len(lengths) - 1) * p // 100] for p in (50, 90, 95, 99)},
        ),
        at_most_20=sum(n <= 20 for n in lengths),
        less_than_60=sum(n < 60 for n in lengths),
        over_2000=sum(n > 2000 for n in lengths),
        duplicate_excess=sum(n - 1 for n in texts.values()),
        duplicate_text_groups=sum(n > 1 for n in texts.values()),
        multiple_open_contributions=sum(n > 1 for n in parents.values()),
    )

    by_text = defaultdict(set)
    for row in rows:
        by_text[row["text_hash"]].add((row["corpus_id"], row["contribution_id"]))
    cross = {key for key, parents in by_text.items() if len(parents) > 1}
    result["cross_contribution_duplicate_groups"] = len(cross)
    result["cross_contribution_duplicate_occurrences"] = sum(
        row["text_hash"] in cross for row in rows
    )
    result["contributions_with_open_answers"] = len(
        {
            (row["corpus_id"], row["contribution_id"])
            for row in rows
            if row["unit_type"] == "open_answer"
        }
    )
    if with_types:
        result["by_type"] = {
            kind: statistics([r for r in rows if r["unit_type"] == kind], with_types=False)
            for kind in sorted({r["unit_type"] for r in rows})
        }
    return result


def select(store, directory):
    rows, frame = frame_data(store, directory)
    samples = selections(rows, frame)
    for name, value in zip(("random", "stratified", "corpus"), samples):
        write_json(directory / (name + ".json"), value)
    write_json(
        directory / "statistics.json",
        dict(
            frame=statistics(rows),
            **{
                name: statistics(value["documents"])
                for name, value in zip(("random", "stratified", "corpus"), samples)
            },
        ),
    )
    print("Corpus final :", len(samples[2]["documents"]), "unités distinctes", flush=True)


def verify(store, directory):
    rows, frame = frame_data(store, directory)
    reproduced = selections(rows, frame)
    saved = [
        load_sample(directory / (name + ".json")) for name in ("random", "stratified", "corpus")
    ]
    for actual, expected in zip(saved, reproduced):
        if (
            actual["selected_hash"] != expected["selected_hash"]
            or actual["frame_hash"] != expected["frame_hash"]
        ):
            raise ValueError("Sélection non reproductible.")
    for key in ("contribution_id", "text_hash"):
        split_by_key = defaultdict(set)
        for row in saved[2]["documents"]:
            identity = (row["corpus_id"], row[key]) if key == "contribution_id" else row[key]
            split_by_key[identity].add(row["split"])
        if any(len(partitions) > 1 for partitions in split_by_key.values()):
            raise ValueError("Fuite de partition.")
    print("Vérification complète : références, empreintes, répétition et partitions conformes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["plan", "extract", "select", "verify"])
    parser.add_argument("--directory", type=Path, default=Path("evaluation/local/rag007"))
    parser.add_argument("--env-file")
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    with open_store(load_settings(env_file=args.env_file)) as store:
        # Check actual session settings on every stage, including a later resume.
        with source_connection(store.guard.source) as connection:
            if (
                connection.execute(text("SHOW statement_timeout")).scalar_one() != "5s"
                or connection.execute(text("SHOW lock_timeout")).scalar_one() != "2s"
            ):
                raise ValueError("Délais de cinq et deux secondes requis pour toute étape.")
        if args.stage == "extract" and shutil.disk_usage(args.directory).free < 1024**3:
            raise ValueError("Au moins 1 Gio libre requis avant écriture.")
        {"plan": plan, "extract": extract, "select": select, "verify": verify}[args.stage](
            store, args.directory
        )


if __name__ == "__main__":
    try:
        main()
    except (SQLAlchemyError, ValueError, KeyError, OSError):
        print(
            "Opération refusée : contrôler bases, délais, paramètres et état local ; reprendre avec extract.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    except KeyboardInterrupt:
        print("Interruption : reprendre avec extract depuis le dernier commit.", file=sys.stderr)
        raise SystemExit(130) from None
