"""Un précontrôle incomplet ou incohérent interdit l'inférence."""

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.campaign import execute, preflight
from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.protocols import V2, resolve
from tests.unit.test_judges import Fake, data, lightweight, small_plan  # noqa: F401


def test_both_preflights_required_and_overflow_refused(request, tmp_path):
    directory, manifest, _ = request.getfixturevalue("small_plan")
    request.getfixturevalue("lightweight")
    manifest["prompt_version"] = V2
    manifest["prompt_hash"] = digest(resolve(V2))
    manifest.pop("manifest_hash")
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    config = InferenceConfig()
    backend = Fake()
    backend.prompt_version = V2
    cache = Cache(tmp_path / "cache.db")
    try:
        preflight(directory, backend, config)
        with pytest.raises(FileNotFoundError):
            execute(directory, backend, config, cache, limit=8)
        second = Fake()
        second.prompt_version = V2
        second.spec = MODELS["qwen3-14b"]
        second.token_counts = lambda inputs: [100000] * len(inputs)
        failed = preflight(directory, second, config)
        assert not failed["success"] and failed["exceeded"] == 8 and second.calls == 0
        with pytest.raises(ValueError, match="Précontrôle"):
            execute(directory, backend, config, cache, limit=8)
        second.token_counts = lambda inputs: [100] * len(inputs)
        preflight(directory, second, config)
        result = execute(directory, backend, config, cache, limit=8)
        assert result["complete"] and result["counts"]["valid"] == 8
        backend.snapshot_hash = "changed"
        with pytest.raises(ValueError, match="Recette"):
            execute(directory, backend, config, cache, limit=8)
    finally:
        cache.close()
