"""Contrôle le vrai 14B et les ressources, sans charger les poids sur GPU."""

import bootstrap  # noqa: F401  # isort: skip
import importlib.metadata
import json
import subprocess
import sys

import torch
from cahier_rag.judges.models import MODELS, verify

from qcommon import HERE, ROOT, preserve, save

preserve()
spec = MODELS["qwen3-14b"]
folder, digest = verify(spec, ROOT / "rag/models/judges")
gpu = subprocess.run(
    [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu",
        "--format=csv,noheader",
    ],
    capture_output=True,
    text=True,
)
processes = subprocess.run(
    ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
    capture_output=True,
    text=True,
)
result = dict(
    model=spec.to_dict(),
    folder=str(folder.relative_to(ROOT)),
    snapshot_hash=digest,
    python=sys.version,
    interpreter=sys.executable,
    libraries={
        p: importlib.metadata.version(p)
        for p in ["torch", "transformers", "bitsandbytes", "accelerate", "psutil"]
    },
    cuda_available=torch.cuda.is_available(),
    cuda_runtime=torch.version.cuda,
    gpu=gpu.stdout.strip(),
    compute_processes=processes.stdout.strip(),
    original_python_symlink_target="/tmp/rag010-python/cpython-3.11-linux-x86_64-gnu/bin/python3.11",
    environment_modified=False,
    new_packages_installed=False,
)
if result["cuda_available"]:
    result["cuda_capability"] = torch.cuda.get_device_capability()
save(HERE / "data/environment.json", result)
print(json.dumps(result, ensure_ascii=False, indent=2))
assert result["cuda_available"], "CUDA required; no CPU or smaller model fallback"
assert not processes.stdout.strip(), (
    "GPU has running compute processes; no heavy inference allowed yet"
)
