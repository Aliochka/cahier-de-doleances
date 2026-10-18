"""Trois modèles publics vérifiés, versions immuables et recettes officielles."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repository: str
    revision: str
    license: str
    parameters: int
    dimension: int
    max_tokens: int
    pooling: str
    document_prefix: str
    query_prefix: str
    weight_file: str

    def prepare(self, text: str, role: str):
        if role not in {"document", "query"}:
            raise ValueError("Rôle document ou query requis.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Texte non vide requis.")
        return (self.query_prefix if role == "query" else self.document_prefix) + text

    def to_dict(self):
        return asdict(self) | {
            "source": f"https://huggingface.co/{self.repository}/tree/{self.revision}"
        }


MODELS = {
    "e5-small": ModelSpec(
        "e5-small",
        "intfloat/multilingual-e5-small",
        "614241f622f53c4eeff9890bdc4f31cfecc418b3",
        "MIT",
        117653760,
        384,
        512,
        "mean",
        "passage: ",
        "query: ",
        "model.safetensors",
    ),
    "bge-m3": ModelSpec(
        "bge-m3",
        "BAAI/bge-m3",
        "5617a9f61b028005a4858fdac845db406aefb181",
        "MIT",
        568000000,
        1024,
        8192,
        "cls",
        "",
        "",
        "pytorch_model.bin",
    ),
    "qwen3-0.6b": ModelSpec(
        "qwen3-0.6b",
        "Qwen/Qwen3-Embedding-0.6B",
        "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        "Apache-2.0",
        595776512,
        1024,
        32768,
        "last",
        "",
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:",
        "model.safetensors",
    ),
}
