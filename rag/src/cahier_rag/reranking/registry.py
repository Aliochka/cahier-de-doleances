"""Checkpoints officiels et recettes fixes, sans sélection à partir des jugements."""

from dataclasses import asdict, dataclass

from cahier_rag.judges.models import download as download_snapshot
from cahier_rag.judges.models import verify as verify_snapshot


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repository: str
    revision: str
    parameters: int
    hidden_size: int
    context_tokens: int
    architecture: str
    files: tuple
    license: str = "Apache-2.0"

    def to_dict(self):
        return asdict(self) | {"files": list(self.files)}


MODELS = {
    "R1": ModelSpec(
        "bge-reranker-v2-m3",
        "BAAI/bge-reranker-v2-m3",
        "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        567755777,
        1024,
        8192,
        "sequence_classification",
        (
            "README.md",
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "sentencepiece.bpe.model",
        ),
    ),
    "R2": ModelSpec(
        "qwen3-reranker-4b",
        "Qwen/Qwen3-Reranker-4B",
        "22e683669bc0f0bd69640a1354a6d0aebcfeede5",
        4021784576,
        2560,
        32768,
        "causal_yes_no",
        (
            "README.md",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
            "generation_config.json",
            "model.safetensors.index.json",
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
        ),
    ),
}


def download(spec, root):
    # Utilitaires SHA-256 existants seulement ; aucun référentiel de jugements lu.
    return download_snapshot(spec, root)


def verify(spec, root):
    return verify_snapshot(spec, root)
