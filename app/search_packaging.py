"""Offline CPU/recipe packaging check; no database or model loading."""

import json
from importlib.metadata import distributions


def check_runtime():
    import numpy
    import tokenizers
    import torch
    import transformers
    from cahier_rag.search.service.core import H1LexicalSearch, SearchRecipe
    from cahier_rag.tuning.lexical import TunedSearch
    from transformers import AutoModel, AutoTokenizer

    if not callable(AutoModel.from_pretrained) or not callable(AutoTokenizer.from_pretrained):
        raise RuntimeError("Transformers model/tokenizer loader unavailable")
    if torch.version.cuda is not None:
        raise RuntimeError("CPU-only PyTorch required")
    names = {d.metadata["Name"].lower().replace("_", "-") for d in distributions()}
    if any(n.startswith("nvidia-") or n == "triton" for n in names):
        raise RuntimeError("GPU dependencies are forbidden in the CPU image")
    recipe = SearchRecipe()
    if recipe.version != "h1-public-v2-ts-rank":
        raise RuntimeError("Unexpected public search recipe")
    sql = H1LexicalSearch.score_expression([dict(query="'test'", idf=1.0, total=1.0)], {})
    if "ts_rank(" not in sql or "ts_rank_cd(" in sql:
        raise RuntimeError("Unexpected lexical scoring function")
    if H1LexicalSearch.lexical is not TunedSearch.lexical:
        raise RuntimeError("Unexpected lexical retrieval implementation")
    # Exercise the native CPU runtime without loading or fetching any model.
    if torch.ones(2, device="cpu").sum().item() != 2:
        raise RuntimeError("CPU tensor operation failed")
    return dict(
        status="ok",
        torch=torch.__version__,
        transformers=transformers.__version__,
        tokenizers=tokenizers.__version__,
        numpy=numpy.__version__,
        cpu=True,
        recipe=recipe.version,
        recipe_fingerprint=recipe.fingerprint,
        model_loaded=False,
    )


if __name__ == "__main__":
    print(json.dumps(check_runtime()))
