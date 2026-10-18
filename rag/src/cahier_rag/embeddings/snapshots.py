"""Téléchargement explicite des poids publics ; l'inférence reste hors ligne."""

import hashlib
import os
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.files import load_json
from cahier_rag.evaluation.sampling import digest

FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
    "vocab.json",
    "vocab.txt",
    "merges.txt",
    "modules.json",
    "1_Pooling/config.json",
    "sentence_bert_config.json",
    "README.md",
    "LICENSE",
)


def sha256_file(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify_snapshot(spec, root):
    folder = Path(root) / spec.key / spec.revision
    manifest = load_json(folder / "snapshot-manifest.json")
    expected = manifest.pop("manifest_hash")
    if digest(manifest) != expected or manifest["model"] != spec.to_dict():
        raise ValueError("Snapshot de modèle incompatible.")
    if spec.weight_file not in manifest["files"] or "config.json" not in manifest["files"]:
        raise ValueError("Snapshot incomplet.")
    for name, checksum in manifest["files"].items():
        if name not in (*FILES, spec.weight_file) or sha256_file(folder / name) != checksum:
            raise ValueError("Fichier de modèle manquant ou modifié.")
    return folder, expected


def download(spec, root):
    # Seule opération réseau du moteur : aucun document ni requête n'est transmis.
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from huggingface_hub import snapshot_download

    folder = Path(root) / spec.key / spec.revision
    if (folder / "snapshot-manifest.json").exists():
        verify_snapshot(spec, root)
        return folder
    snapshot_download(
        spec.repository,
        revision=spec.revision,
        local_dir=folder,
        allow_patterns=[*FILES, spec.weight_file],
        max_workers=2,
    )
    manifest = {
        "version": 1,
        "model": spec.to_dict(),
        "files": {
            name: sha256_file(folder / name)
            for name in (*FILES, spec.weight_file)
            if (folder / name).is_file()
        },
    }
    if spec.weight_file not in manifest["files"]:
        raise ValueError("Poids de modèle absents.")
    manifest["manifest_hash"] = digest(manifest)
    with (folder / "snapshot-manifest.json").open("x") as stream:
        stream.write(canonical_json(manifest) + "\n")
    return folder
