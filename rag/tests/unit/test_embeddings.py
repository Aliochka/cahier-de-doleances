"""Contrats d'embedding simulés, sans bibliothèques lourdes ni réseau."""

import json
import math
from array import array
from dataclasses import replace
from pathlib import Path

import pytest

from cahier_rag.embeddings.core import (
    EmbeddingEngine,
    EmbeddingError,
    EmbeddingInput,
    InputTooLong,
    validate_vectors,
)
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.snapshots import sha256_file, verify_snapshot
from cahier_rag.evaluation.sampling import digest


class Fake:
    dimension = 3
    max_tokens = 5

    def __init__(self):
        self.loaded = False
        self.calls = []

    def load(self):
        self.loaded = True

    def close(self):
        self.loaded = False

    def token_lengths(self, texts, role):
        return [len(text.split()) for text in texts]

    def encode(self, texts, role):
        self.calls.append((texts, role))
        return [[3.0, 4.0, float(len(text))] for text in texts]


def inputs():
    return [
        EmbeddingInput(f"input:{i}", text, digest(text), str(2**63 - 1 - i))
        for i, text in enumerate(("oui", "non merci", "proposition précise"))
    ]


def test_interchangeable_loading_order_batches_normalization_and_binary():
    fake = Fake()
    engine = EmbeddingEngine(fake)
    with pytest.raises(EmbeddingError):
        list(engine.encode_documents(inputs()))
    engine.load()
    batches = list(engine.encode_documents(inputs(), batch_size=2))
    assert [i for b in batches for i in b.identifiers] == [i.input_id for i in inputs()]
    assert fake.calls == [(["oui", "non merci"], "document"), (["proposition précise"], "document")]
    assert all(
        abs(math.sqrt(sum(x * x for x in row)) - 1) < 1e-8 for b in batches for row in b.vectors
    )
    values = array("f")
    values.frombytes(batches[0].binary())
    assert len(values) == 6
    assert (
        batches[0].output_hash
        == list(engine.encode_documents(inputs(), batch_size=2))[0].output_hash
    )
    assert batches[0].input_hashes == tuple(i.fingerprint() for i in inputs()[:2])
    assert batches[0].token_lengths == (1, 2)
    list(engine.encode_queries(inputs()[:1]))
    assert fake.calls[-1][1] == "query"
    engine.close()
    assert not fake.loaded


def test_overflow_rejected_before_any_encoding():
    fake = Fake()
    engine = EmbeddingEngine(fake).load()
    too_long = EmbeddingInput("BIGINT:9223372036854775807", "un deux trois quatre cinq six", "hash")
    with pytest.raises(InputTooLong) as error:
        list(engine.encode_documents([inputs()[0], too_long], batch_size=1))
    assert fake.calls == []
    assert error.value.items == ((too_long.input_id, 6),)
    assert "un deux" not in str(error.value)


@pytest.mark.parametrize(
    "vectors", [[[0, 0, 0]], [[float("nan"), 1, 1]], [[float("inf"), 1, 1]], [[1, 2]], []]
)
def test_invalid_vectors(vectors):
    with pytest.raises(EmbeddingError):
        validate_vectors(vectors, expected_rows=1, dimension=3, normalize=True)


def test_without_normalization_and_duplicate_ids():
    result = validate_vectors([[3, 4, 0]], expected_rows=1, dimension=3, normalize=False)
    assert result == ((3, 4, 0),)
    engine = EmbeddingEngine(Fake(), normalize=False).load()
    with pytest.raises(EmbeddingError):
        list(engine.encode_documents([inputs()[0]] * 2))
    for size in (0, 65, True):
        with pytest.raises(EmbeddingError):
            list(engine.encode_documents(inputs(), batch_size=size))
    assert replace(inputs()[0], text="autre").fingerprint() != inputs()[0].fingerprint()


@pytest.mark.parametrize("error", [RuntimeError("secret GPU driver"), MemoryError("secret RAM")])
def test_device_errors_are_explicit_and_private(error):
    fake = Fake()

    def fail(*args):
        raise error

    fake.encode = fail
    with pytest.raises(EmbeddingError, match="CPU/GPU") as caught:
        list(EmbeddingEngine(fake).load().encode_documents(inputs()))
    assert "secret" not in str(caught.value)


def test_model_instructions_dimensions_and_versions():
    assert MODELS["e5-small"].prepare("question française", "query") == "query: question française"
    assert MODELS["e5-small"].prepare("réponse", "document") == "passage: réponse"
    assert MODELS["bge-m3"].prepare("réponse", "document") == "réponse"
    assert MODELS["qwen3-0.6b"].prepare("question", "query").startswith("Instruct: ")
    assert MODELS["qwen3-0.6b"].prepare("réponse", "document") == "réponse"
    assert MODELS["qwen3-0.6b"].max_tokens == 32768
    assert MODELS["e5-small"].dimension == 384
    assert MODELS["bge-m3"].pooling == "cls"
    assert MODELS["qwen3-0.6b"].pooling == "last"
    for spec in MODELS.values():
        assert len(spec.revision) == 40
        with pytest.raises(ValueError):
            spec.prepare("", "query")
        with pytest.raises(ValueError):
            spec.prepare("bonjour", "invalid")


def test_snapshot_checksums_and_revision(tmp_path):
    spec = MODELS["e5-small"]
    folder = tmp_path / spec.key / spec.revision
    folder.mkdir(parents=True)
    (folder / spec.weight_file).write_bytes(b"synthetic weights only")
    (folder / "config.json").write_text("{}")
    manifest = {
        "version": 1,
        "model": spec.to_dict(),
        "files": {name: sha256_file(folder / name) for name in (spec.weight_file, "config.json")},
    }
    manifest["manifest_hash"] = digest(manifest)
    (folder / "snapshot-manifest.json").write_text(json.dumps(manifest))
    assert verify_snapshot(spec, tmp_path) == (folder, manifest["manifest_hash"])
    (folder / spec.weight_file).write_bytes(b"modified")
    with pytest.raises(ValueError):
        verify_snapshot(spec, tmp_path)


def test_backend_construction_does_not_import_torch():
    from cahier_rag.embeddings.transformers_backend import TransformersBackend

    backend = TransformersBackend(MODELS["e5-small"], Path("missing"))
    assert backend.torch is None and backend.model is None
    with pytest.raises(EmbeddingError):
        TransformersBackend(MODELS["e5-small"], Path("missing"), device="cpu", precision="float16")
    with pytest.raises(EmbeddingError):
        TransformersBackend(MODELS["e5-small"], Path("missing"), device="mystery")


def test_imports_without_heavy_dependencies_or_network(tmp_path):
    import subprocess
    import sys

    script = """
import importlib.abc
import sys,socket
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','numpy','huggingface_hub','psutil','app'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0,Block())
def forbidden(*args,**kwargs):raise AssertionError('network forbidden')
socket.socket.connect=forbidden
import cahier_rag.embeddings.core
import cahier_rag.embeddings.registry
import cahier_rag.embeddings.snapshots
import cahier_rag.embeddings.transformers_backend
import cahier_rag.embeddings.data
import cahier_rag.embeddings.planning
import cahier_rag.embeddings.benchmark
import cahier_rag.embeddings.cli
from cahier_rag.embeddings.cli import main
assert main(['list'])==0
import cahier_rag.search.lexical
import cahier_rag.annotation.session
import cahier_rag.annotation.documents
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_gpu_unavailable_never_falls_back_to_cpu(monkeypatch):
    import sys
    from types import SimpleNamespace

    from cahier_rag.embeddings.transformers_backend import TransformersBackend

    fake_torch = SimpleNamespace(
        set_num_threads=lambda _: None,
        manual_seed=lambda _: None,
        cuda=SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoModel=object()))
    backend = TransformersBackend(MODELS["e5-small"], "unused", device="cuda", precision="bfloat16")
    monkeypatch.setattr(backend, "load_tokenizer", lambda: None)
    with pytest.raises(EmbeddingError, match="CUDA indisponible"):
        backend.load()
    assert backend.device == "cuda" and backend.model is None


@pytest.mark.parametrize("key", list(MODELS))
def test_pooling_recipes_with_cpu_tensors_when_extra_installed(key):
    torch = pytest.importorskip("torch")
    from types import SimpleNamespace

    from cahier_rag.embeddings.transformers_backend import TransformersBackend

    backend = TransformersBackend(MODELS[key], "unused")
    backend.torch = torch
    if backend.spec.pooling == "last":
        mask = torch.tensor([[0, 1, 1]])
        hidden = torch.tensor([[[99.0, 99.0], [1.0, 2.0], [3.0, 4.0]]])
        expected = [[3.0, 4.0]]
    else:
        mask = torch.tensor([[1, 1, 0]])
        hidden = torch.tensor([[[1.0, 2.0], [3.0, 4.0], [99.0, 99.0]]])
        expected = [[1.0, 2.0]] if backend.spec.pooling == "cls" else [[2.0, 3.0]]

    class Tokenizer:
        def __call__(self, texts, **kwargs):
            assert kwargs["truncation"] is False
            assert texts == [backend.spec.prepare("bonjour", "query")]
            return {"input_ids": torch.tensor([[1, 2, 3]]), "attention_mask": mask}

    backend.tokenizer = Tokenizer()
    backend.model = lambda **kwargs: SimpleNamespace(last_hidden_state=hidden)
    assert backend.encode(["bonjour"], "query") == expected
