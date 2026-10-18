"""Deux campagnes explicites ; le catalogue et les bilans ne créent aucune session."""

import fcntl
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cahier_rag.annotation.session import Session
from cahier_rag.evaluation.files import load_json
from cahier_rag.evaluation.sampling import digest


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    label: str
    pool: Path
    manifest: Path
    folder: Path
    seed: int

    @property
    def session_path(self):
        return self.folder / "session.json"

    @contextmanager
    def writer_lock(self):
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.folder / "session.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield


class Catalogue:
    def __init__(self, root, queries, sample, *, expected_count=400):
        self.root, self.queries, self.sample = Path(root), queries, sample
        self.expected_count = expected_count
        local = self.root / "evaluation/local"
        self.campaigns = {
            "rag010": Campaign(
                "rag010",
                "Campagne initiale",
                local / "rag009/annotations/pool.json",
                local / "rag009/annotations/manifest.json",
                local / "rag010",
                20261020,
            ),
            "rag014": Campaign(
                "rag014",
                "Campagne complémentaire",
                local / "rag014/candidates-final/pool.json",
                local / "rag014/candidates-final/manifest.json",
                local / "rag015/campaigns/rag014",
                20261021,
            ),
        }

    def get(self, campaign_id):
        if campaign_id not in self.campaigns:
            raise ValueError("Campagne inconnue.")
        return self.campaigns[campaign_id]

    def load_pool(self, campaign_id):
        spec = self.get(campaign_id)
        pool, manifest = load_json(spec.pool), load_json(spec.manifest)
        if (
            digest(pool) != manifest["pool_hash"]
            or len(pool) != self.expected_count
            or manifest["candidate_count"] != len(pool)
            or manifest["split"] != "development"
            or manifest["sample_hash"] != self.sample["selected_hash"]
        ):
            raise ValueError("Pool ou manifeste de campagne incompatible.")
        if "queries_hash" in manifest:
            if manifest["queries_hash"] != digest(self.queries):
                raise ValueError("Requêtes de campagne modifiées.")
        else:
            # RAG-014 relie les requêtes via son expérience, sans modifier le pool gelé.
            experiment = self.root / "evaluation/local/rag014/development-replay"
            report, runs = (
                load_json(experiment / "report.json"),
                load_json(experiment / "runs.json"),
            )
            if (
                report["queries_hash"]
                != digest([q for q in self.queries if q["split"] == "development"])
                or report["sample_hash"] != self.sample["selected_hash"]
                or report["split"] != "development"
                or digest(runs) != manifest["runs_hash"]
                or report["runs_hash"] != manifest["runs_hash"]
            ):
                raise ValueError("Expérience source de campagne incompatible.")
        docs = {d["document_id"]: d for d in self.sample["documents"]}
        queries = {q["query_id"]: q for q in self.queries}
        pairs = set()
        for row in pool:
            pair = row["query_id"], row["document_id"]
            if (
                pair in pairs
                or pair[0] not in queries
                or pair[1] not in docs
                or queries[pair[0]]["split"] != "development"
                or docs[pair[1]]["split"] != "development"
                or any(
                    row[key] != docs[pair[1]][key]
                    for key in ("content_hash", "corpus_id", "contribution_id")
                )
            ):
                raise ValueError("Candidat de campagne dupliqué ou incompatible.")
            pairs.add(pair)
        return pool

    def session(self, campaign_id, *, evaluator, seed=None, read_only=False, allow_create=False):
        spec = self.get(campaign_id)
        return Session(
            self.load_pool(campaign_id),
            self.queries,
            self.sample,
            spec.session_path,
            evaluator=evaluator,
            seed=spec.seed if seed is None else seed,
            expected_count=self.expected_count,
            campaign_id=None if campaign_id == "rag010" else campaign_id,
            read_only=read_only,
            allow_create=allow_create,
        )

    def snapshot(self, campaign_id):
        spec = self.get(campaign_id)
        if not spec.session_path.exists():
            return None
        identity = load_json(spec.session_path)["identity"]
        return self.session(
            campaign_id, evaluator=identity["evaluator"], seed=identity["seed"], read_only=True
        )

    def create(self, campaign_id, *, evaluator, seed=None):
        spec = self.get(campaign_id)
        self.load_pool(campaign_id)
        with spec.writer_lock():
            if spec.session_path.exists():
                raise ValueError("Session existante préservée ; utiliser open pour reprendre.")
            return self.session(campaign_id, evaluator=evaluator, seed=seed, allow_create=True)

    def status(self, campaign_id):
        pool = self.load_pool(campaign_id)
        session = self.snapshot(campaign_id)
        judged = session.export() if session else []
        pairs = {(r["query_id"], r["document_id"]) for r in judged}
        return {
            "campaign_id": campaign_id,
            "label": self.get(campaign_id).label,
            "started": session is not None,
            "total": len(pool),
            "judged": len(judged),
            "remaining": len(pool) - len(judged),
            "grades": dict(sorted(Counter(r["grade"] for r in judged).items())),
            "pool_hash": digest(pool),
            "queries_hash": digest(self.queries),
            "session_hash": digest(session.state) if session else None,
            "pending_pairs": [
                {"query_id": r["query_id"], "document_id": r["document_id"]}
                for r in pool
                if (r["query_id"], r["document_id"]) not in pairs
            ],
        }
