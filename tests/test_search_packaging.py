"""Final CPU packaging gates; no database, network or model snapshot required."""

from types import SimpleNamespace

import pytest

from app import search_packaging


@pytest.fixture
def torch():
    return pytest.importorskip("torch")


def test_cpu_runtime_and_current_recipe(torch):
    if torch.version.cuda is not None:
        pytest.skip("Requires the dedicated CPU environment")
    result = search_packaging.check_runtime()
    assert result["cpu"] and not result["model_loaded"]
    assert result["recipe"] == "h1-public-v2-ts-rank"


def test_rejects_cuda_build(torch, monkeypatch):
    monkeypatch.setattr(torch.version, "cuda", "12.8")
    with pytest.raises(RuntimeError, match="CPU-only"):
        search_packaging.check_runtime()


def test_rejects_gpu_transitive_dependency(torch, monkeypatch):
    monkeypatch.setattr(torch.version, "cuda", None)
    monkeypatch.setattr(
        search_packaging,
        "distributions",
        lambda: [SimpleNamespace(metadata={"Name": "nvidia-cublas-cu12"})],
    )
    with pytest.raises(RuntimeError, match="GPU dependencies"):
        search_packaging.check_runtime()


def test_rejects_old_h1_recipe(torch, monkeypatch):
    from cahier_rag.search.service import core

    monkeypatch.setattr(torch.version, "cuda", None)
    monkeypatch.setattr(search_packaging, "distributions", lambda: [])
    monkeypatch.setattr(core, "SearchRecipe", lambda: SimpleNamespace(version="h1-public-v1"))
    with pytest.raises(RuntimeError, match="Unexpected public search recipe"):
        search_packaging.check_runtime()
