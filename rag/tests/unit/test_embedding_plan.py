"""Plans d'entrées communes et réutilisation de C, sur représentations synthétiques."""

import json
from types import SimpleNamespace

import pytest

from cahier_rag.embeddings.benchmark import run_encoding, stability
from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingError
from cahier_rag.embeddings.planning import create_plan, inputs_for_plan, validate_plan
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.representations.artifacts import generate
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from tests.unit.test_representations import corpus  # noqa: F401


class CountBackend:
    def __init__(self, spec):
        self.spec = spec
        self.max_tokens = 80 if spec.key == "e5-small" else 1000
        self.snapshot_hash = "snapshot-" + spec.key
        self.tokenizer = SimpleNamespace(model_max_length=self.max_tokens)

    def load_tokenizer(self):
        pass

    def token_lengths(self, texts, role):
        return [len(self.spec.prepare(t, role).split()) for t in texts]


def test_common_inputs_plan_aliases_and_integrity(request, tmp_path):
    docs, _, repo = request.getfixturevalue("corpus")
    ids = [d.document_id for d in docs[:4]]
    dirs = {}
    for strategy in Strategy:
        dirs[strategy.value] = tmp_path / strategy
        generate(repo, PreparationConfig(strategy), ids, dirs[strategy.value], selection={})
    backends = {key: CountBackend(spec) for key, spec in MODELS.items()}
    path = tmp_path / "plan.json"
    plan = create_plan(
        repo.scope,
        {key: dirs[key] for key in ("A", "B", "D")},
        backends,
        path,
        c_directory=dirs["C"],
    )
    validate_plan(plan)
    assert json.loads(path.read_text()) == plan
    for strategy in ("A", "B", "D"):
        selected = inputs_for_plan(plan, strategy, repo.scope)
        assert [i.input_id for i in selected] == plan["strategies"][strategy]["common_input_ids"]
        assert len(selected) < 4
        assert all(
            n <= 80
            for n in backends["e5-small"].token_lengths([i.text for i in selected], "document")
        )
    assert plan["C_reuse"]["recomputed_vectors"] == 0
    assert len(plan["C_reuse"]["aliases"]) == plan["strategies"]["B"]["common_representations"]
    assert plan["strategies"]["A"]["tokenization"]["e5-small"]["statistics"]["overflow_count"] == 1
    with pytest.raises(FileExistsError):
        create_plan(repo.scope, {key: dirs[key] for key in ("A", "B", "D")}, backends, path)
    plan["sample_hash"] = "modified"
    with pytest.raises(EmbeddingError):
        validate_plan(plan)


def test_binary_artifact_order_hashes_and_stability(tmp_path):
    from tests.unit.test_embeddings import Fake, inputs

    fake = Fake()
    fake.device = "cpu"
    engine = EmbeddingEngine(fake).load()
    result, reference = run_encoding(
        engine, inputs(), role="document", batch_size=2, output=tmp_path, prefix="example"
    )
    assert (tmp_path / "example.f32").stat().st_size == 3 * 3 * 4
    metadata = json.loads((tmp_path / "example.json").read_text())
    assert [r["input_id"] for r in metadata["rows"]] == [i.input_id for i in inputs()]
    assert result["output_hash"] == metadata["vectors_sha256"]
    assert stability(reference, reference, 0.001)["passed"]
    with pytest.raises(EmbeddingError):
        stability(reference, [tuple(-v for v in r) for r in reference], 0.001)


def test_benchmark_manifest_with_simulated_cpu_backend(tmp_path, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace

    import cahier_rag.embeddings.benchmark as module
    from cahier_rag.evaluation.sampling import digest

    class Memory:
        baseline = 100
        peak = 120

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Backend:
        spec = replace(MODELS["e5-small"], dimension=3)
        snapshot_hash = "synthetic-snapshot"
        dimension = 3
        max_tokens = 512
        device = "cpu"
        precision = "float32"
        threads = 4
        integrity_seconds = 0
        tokenizer = SimpleNamespace(model_max_length=512)
        torch = SimpleNamespace(version=SimpleNamespace(cuda=None))
        closed = False

        def load(self):
            pass

        def token_lengths(self, texts, role):
            return [len(t.split()) for t in texts]

        def encode(self, texts, role):
            return [[float(len(t)), 2.0, 3.0] for t in texts]

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "MemorySampler", Memory)
    monkeypatch.setattr(module.importlib.metadata, "version", lambda _: "synthetic-test")
    backend = Backend()
    plan = {
        "version": 1,
        "models": {
            "e5-small": {"spec": backend.spec.to_dict(), "snapshot_hash": backend.snapshot_hash}
        },
        "strategies": {},
    }
    plan["plan_hash"] = digest(plan)
    result = module.benchmark(backend, plan, None, tmp_path / "run", cpu_queries_only=True)
    assert backend.closed
    expected = result.pop("manifest_hash")
    assert digest(result) == expected
    assert result["documents"] == {} and result["queries"]["count"] == 8
    assert result["queries"]["stability"]["passed"]
    assert result["query_vectors"]["rows"] == 8
    assert result["tokenizer"]["query_prefix"] == "query: "
    assert result["ram"]["rss_peak_sampled_bytes"] == 120
    assert (tmp_path / "run/queries.f32").stat().st_size == 8 * 3 * 4


def test_inspection_detects_binary_corruption(tmp_path, monkeypatch):
    # Réutiliser le parcours complet simulé, puis altérer une seule valeur stockée.
    from dataclasses import replace
    from types import SimpleNamespace

    import cahier_rag.embeddings.benchmark as module
    from cahier_rag.evaluation.sampling import digest

    class Memory:
        baseline = 100
        peak = 120

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Backend:
        spec = replace(MODELS["e5-small"], dimension=3)
        snapshot_hash = "synthetic"
        dimension = 3
        max_tokens = 512
        device = "cpu"
        precision = "float32"
        threads = 4
        integrity_seconds = 0
        tokenizer = SimpleNamespace(model_max_length=512)
        torch = SimpleNamespace(version=SimpleNamespace(cuda=None))

        def load(self):
            pass

        def token_lengths(self, texts, role):
            return [len(t.split()) for t in texts]

        def encode(self, texts, role):
            return [[3.0, 4.0, 0.0] for _ in texts]

        def close(self):
            pass

    monkeypatch.setattr(module, "MemorySampler", Memory)
    monkeypatch.setattr(module.importlib.metadata, "version", lambda _: "synthetic-test")
    backend = Backend()
    plan = {
        "version": 1,
        "models": {
            "e5-small": {"spec": backend.spec.to_dict(), "snapshot_hash": backend.snapshot_hash}
        },
        "strategies": {},
    }
    plan["plan_hash"] = digest(plan)
    module.benchmark(backend, plan, None, tmp_path / "run", cpu_queries_only=True)
    _, integrity = module.inspect_benchmark(tmp_path / "run")
    assert integrity == {"matrices_checked": 1, "vectors_checked": 8, "valid": True}
    with (tmp_path / "run/queries.f32").open("r+b") as stream:
        stream.write(b"xxxx")
    with pytest.raises(EmbeddingError):
        module.inspect_benchmark(tmp_path / "run")
