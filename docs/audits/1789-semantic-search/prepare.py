"""Copie bornée des artefacts locaux, contrôlés sans ouvrir une base."""

import collections
import sys

from common import HERE, ROOT, read, rows, sha, text_sha, write, write_rows

sys.path.insert(0, str(ROOT / "rag/src"))
from cahier_rag.embeddings.registry import MODELS  # noqa: E402
from cahier_rag.embeddings.snapshots import verify_snapshot  # noqa: E402
from cahier_rag.evaluation.sampling import digest  # noqa: E402
from cahier_rag.vector.cache import cached, inputs_for  # noqa: E402


def main():
    import numpy as np

    frozen = read(HERE / "preregistration.json")
    assert frozen["queries_sha256"] == sha(HERE / "queries.json")
    assert frozen["protocol_sha256"] == sha(HERE / "protocol.json")
    baseline = read(HERE / "prior-audits-sha256.json")
    assert all(sha(ROOT / p) == h for p, h in baseline.items())
    source = HERE.parent / "1789-extraction-pilot/data"
    parents = {p["id"]: p for p in rows(source / "documents.jsonl")}
    historical = []
    for u in rows(source / "units.jsonl"):
        if u["status"] != "A":
            continue
        parent = parents[u["document_id"]]
        assert text_sha(u["text"]) == u["text_sha256"]
        assert u["text"] == "".join(
            parent["full_text"][a - parent["source_text_start"] : b - parent["source_text_start"]]
            for a, b in u["text_spans"]
        )
        section = next((s for s in parent["sections"] if s["id"] == u["section_id"]), None)
        # Reuse the pilot's sourced display title, not a new historical attribution.
        title = parent["title_display"]
        section_text = "\n".join(section["title_exact"]) if section else ""
        prefix = f"Cahier :\n{title}\n"
        if section_text:
            prefix += f"Section :\n{section_text}\n"
        prefix += "\nArticle :\n"
        historical.append(
            dict(
                id=u["id"],
                corpus=u["corpus_id"],
                parent_id=u["document_id"],
                document_key=u["document_key"],
                title=title,
                text=u["text"],
                status="A",
                validation=u["validation"],
                section=section_text,
                context_prefix=prefix,
                metadata=u["metadata"],
                order=u["order"],
                label=u["label_exact"],
                historical_number=u["historical_number"],
                references={
                    k: u[k]
                    for k in (
                        "volume",
                        "pages",
                        "scan_url",
                        "source_url",
                        "source_revision",
                        "source_sha256",
                        "text_spans",
                        "parent_start",
                        "parent_end",
                        "xml_blocks",
                        "anchor",
                        "section_id",
                    )
                },
                source_text_sha256=u["text_sha256"],
            )
        )
    assert len(historical) == 269
    for i, d in enumerate(historical, 1):
        d["short_id"] = f"h{i:03d}"

    local = ROOT / "rag/evaluation/local"
    frame_path = local / "rag007/corpus.json"
    frame = read(frame_path)
    indexed = {d["document_id"]: d for d in frame["documents"]}
    config = read(HERE / "protocol.json")["contemporary_selection"]
    chosen, seen_parents = [], set()
    for form in sorted({d["questionnaire_id"] for d in indexed.values()}):
        candidates = sorted(
            (d for d in indexed.values() if d["questionnaire_id"] == form),
            key=lambda d: text_sha(config["seed"] + ":" + d["document_id"]),
        )
        count = 0
        for d in candidates:
            if d["contribution_id"] in seen_parents:
                continue
            chosen.append(d)
            seen_parents.add(d["contribution_id"])
            count += 1
            if count == config["per_questionnaire"]:
                break
        assert count == config["per_questionnaire"]
    selected = {d["document_id"] for d in chosen}
    prepared_dir = local / "rag013/bge-B"
    manifest = read(prepared_dir / "manifest.json")
    assert manifest["data_hash"] == sha(prepared_dir / "representations.jsonl")
    mc = dict(manifest)
    assert mc.pop("manifest_hash") == digest(mc)
    assert manifest["model"] == MODELS["bge-m3"].to_dict()
    _, snapshot_hash = verify_snapshot(MODELS["bge-m3"], ROOT / "rag/models")
    assert snapshot_hash == manifest["snapshot_hash"]
    parameters = read(prepared_dir / "encoded/parameters.json")
    assert parameters["configuration"]["prepared"] == manifest
    groups = []
    for r in rows(prepared_dir / "representations.jsonl"):
        c = dict(r)
        assert c.pop("content_hash") == digest(c)
        assert r["source_hash"] == indexed[r["document_id"]]["content_hash"]
        if not groups or groups[-1][0]["document_id"] != r["document_id"]:
            groups.append([])
        assert r["segment_index"] == len(groups[-1])
        groups[-1].append(r)
    assert len(groups) == manifest["units"]
    used_paths = [
        frame_path,
        prepared_dir / "manifest.json",
        prepared_dir / "representations.jsonl",
        prepared_dir / "encoded/parameters.json",
    ]
    vectors, segment_refs, modern = [], [], []
    for offset in range(0, len(groups), 25):
        batch = groups[offset : offset + 25]
        if not any(g[0]["document_id"] in selected for g in batch):
            continue
        vec = cached(prepared_dir, offset, inputs_for(batch), parameters["configuration"])
        assert vec is not None
        used_paths.extend(
            prepared_dir / "encoded" / f"{offset:05d}{suffix}" for suffix in (".json", ".f32")
        )
        vi = 0
        for group in batch:
            if group[0]["document_id"] in selected:
                did = group[0]["document_id"]
                full = [None] * max(r["end"] for r in group)
                question = None
                for j, r in enumerate(group):
                    q, answer = r["text"].removeprefix("Question :\n").split("\n\nRéponse :\n", 1)
                    assert len(answer) == r["end"] - r["start"]
                    if question is None:
                        question = q
                    assert question == q
                    for k, char in enumerate(answer, r["start"]):
                        assert full[k] is None or full[k] == char
                        full[k] = char
                    segment_refs.append(
                        dict(
                            unit_id=did,
                            segment_index=j,
                            start=r["start"],
                            end=r["end"],
                            tokens=r["tokens"],
                            text=r["text"],
                            representation_id=r["representation_id"],
                            source_hash=r["source_hash"],
                            precision=parameters["configuration"]["precision"],
                        )
                    )
                    vectors.append(vec[vi + j])
                assert None not in full
                answer = "".join(full)
                assert text_sha(answer) == indexed[did]["text_hash"]
                first = group[0]
                modern.append(
                    dict(
                        id=did,
                        corpus="gdn-2019",
                        parent_id=first["contribution_id"],
                        document_key=did,
                        title=f"Grand Débat · questionnaire {first['questionnaire_id']}",
                        text=answer,
                        question=question,
                        context_prefix=f"Question :\n{question}\n\nRéponse :\n",
                        status="local_2019",
                        source_text_sha256=text_sha(answer),
                        references={
                            "questionnaire_id": first["questionnaire_id"],
                            "answer_id": did.split(":")[-2],
                            "source_hash": first["source_hash"],
                            "local_source": "rag007 corpus / rag013 representations",
                            "context_path": f"/forms/{first['questionnaire_id']}/contributions/{first['contribution_id']}#answer-{did.split(':')[-2]}",
                        },
                    )
                )
            vi += len(group)
    modern.sort(key=lambda d: d["id"])
    assert len(modern) == len(selected) == 240
    for i, d in enumerate(modern, 1):
        d["short_id"] = f"m{i:03d}"
    write_rows(HERE / "data/corpus.jsonl", historical + modern)
    write_rows(HERE / "data/contemporary-segments.jsonl", segment_refs)
    (HERE / "vectors").mkdir(exist_ok=True)
    np.save(
        HERE / "vectors/contemporary.npy", np.asarray(vectors, dtype=np.float32), allow_pickle=False
    )
    write(
        HERE / "data/preparation.json",
        dict(
            historical=len(historical),
            contemporary=len(modern),
            contemporary_segments=len(vectors),
            contemporary_by_form=dict(
                collections.Counter(d["references"]["questionnaire_id"] for d in modern)
            ),
            selection=config,
            prior_scope=frame["scope"],
            prior_method=frame["method"],
            contemporary_reused_precision=parameters["configuration"]["precision"],
            snapshot_hash=snapshot_hash,
            source_fingerprints={str(p.relative_to(ROOT)): sha(p) for p in used_paths},
            corpus_sha256=sha(HERE / "data/corpus.jsonl"),
        ),
    )
    print(
        f"Prepared {len(historical)} historical + {len(modern)} contemporary; {len(vectors)} reused vectors"
    )


if __name__ == "__main__":
    main()
