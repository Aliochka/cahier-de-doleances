"""Checkpoints officiels immuables ; téléchargement distinct de toute inférence."""

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.files import load_json
from cahier_rag.evaluation.sampling import digest


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repository: str
    revision: str
    parameters_billions: float
    shards: int
    license: str = "Apache-2.0"
    context_tokens: int = 32768

    def to_dict(self):
        return asdict(self)

    @property
    def files(self):
        return (
            "config.json",
            "generation_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "model.safetensors.index.json",
            "LICENSE",
            "README.md",
            *(f"model-{i:05d}-of-{self.shards:05d}.safetensors" for i in range(1, self.shards + 1)),
        )


MODELS = {
    "qwen3-8b": ModelSpec(
        "qwen3-8b", "Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218", 8.2, 5
    ),
    "qwen3-14b": ModelSpec(
        "qwen3-14b", "Qwen/Qwen3-14B", "40c069824f4251a91eefaf281ebe4c544efd3e18", 14.8, 8
    ),
}


def verify(spec, root):
    folder = Path(root) / spec.key / spec.revision
    manifest = load_json(folder / "snapshot-manifest.json")
    body = dict(manifest)
    expected = body.pop("manifest_hash")
    if (
        digest(body) != expected
        or body["model"] != spec.to_dict()
        or set(body["files"]) != set(spec.files)
    ):
        raise ValueError("Snapshot de juge incompatible ou incomplet.")
    for name, checksum in body["files"].items():
        if sha256_file(folder / name) != checksum:
            raise ValueError("Poids ou tokenizer du juge modifié.")
    return folder, expected


def download(spec, root):
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import snapshot_download

    folder = Path(root) / spec.key / spec.revision
    if (folder / "snapshot-manifest.json").exists():
        return verify(spec, root)[0]
    snapshot_download(
        spec.repository,
        revision=spec.revision,
        local_dir=folder,
        allow_patterns=list(spec.files),
        max_workers=4,
        token=False,
    )
    manifest = {
        "version": 1,
        "model": spec.to_dict(),
        "files": {name: sha256_file(folder / name) for name in spec.files},
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(folder / "snapshot-manifest.json", manifest)
    return folder
