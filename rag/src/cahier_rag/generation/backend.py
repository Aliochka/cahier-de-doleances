"""Réutilisation du chargeur local NF4, nouveau prompt et métriques de génération."""

import importlib.metadata

from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.contracts import SYSTEM, VERSION
from cahier_rag.judges.backend import TransformersJudge
from cahier_rag.judges.models import MODELS


class LocalGenerator(TransformersJudge):
    def __init__(self, root, config):
        super().__init__(MODELS["qwen3-14b"], root, config, prompt_version=VERSION)

    def recipe(self):
        self.load_tokenizer()
        return {
            "version": VERSION,
            "prompt_hash": digest(SYSTEM),
            "model": self.spec.to_dict(),
            "snapshot_hash": self.snapshot_hash,
            "inference": self.config.to_dict(),
            "libraries": {
                p: importlib.metadata.version(p)
                for p in ("torch", "transformers", "bitsandbytes", "accelerate")
            },
            "chat_template_hash": digest(self.tokenizer.chat_template),
            "thinking": False,
        }

    def prompt(self, item):
        self.load_tokenizer()
        return self.rendered(item)
