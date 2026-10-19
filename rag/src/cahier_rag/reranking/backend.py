"""Cross-encoder BGE et logits yes/no Qwen ; aucune génération ou API distante."""

import gc
import importlib.metadata
import os
import time

from cahier_rag.reranking.contracts import validate_scores
from cahier_rag.reranking.registry import verify

INSTRUCTION = "Given a web search query, retrieve relevant passages that answer the query"
PREFIX = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


class TransformersReranker:
    def __init__(self, spec, root, *, device="cuda", budget=1024):
        if (
            device not in {"cuda", "cpu"}
            or type(budget) is not int
            or not 64 <= budget <= spec.context_tokens
        ):
            raise ValueError("Appareil ou budget de reranking invalide.")
        self.spec, self.root, self.device, self.budget = spec, root, device, budget
        self.precision = "bfloat16" if device == "cuda" else "float32"
        self.tokenizer, self.model, self.torch = None, None, None
        self.load_seconds = 0.0

    def load_tokenizer(self):
        if self.tokenizer is not None:
            return
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        from transformers import AutoTokenizer

        self.folder, self.snapshot_hash = verify(self.spec, self.root)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.folder, local_files_only=True, trust_remote_code=False, use_fast=True
        )
        if self.spec.architecture == "causal_yes_no":
            self.tokenizer.padding_side = "left"
            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            self.prefix_ids = self.tokenizer.encode(PREFIX, add_special_tokens=False)
            self.suffix_ids = self.tokenizer.encode(SUFFIX, add_special_tokens=False)
            self.yes_id = self.tokenizer.convert_tokens_to_ids("yes")
            self.no_id = self.tokenizer.convert_tokens_to_ids("no")
            if self.tokenizer.encode("yes", add_special_tokens=False) != [
                self.yes_id
            ] or self.tokenizer.encode("no", add_special_tokens=False) != [self.no_id]:
                raise ValueError("Tokens yes/no incompatibles.")

    def encode_pair(self, query, document):
        self.load_tokenizer()
        if self.spec.architecture == "sequence_classification":
            return self.tokenizer(query, document, truncation=False, add_special_tokens=True)
        value = f"<Instruct>: {INSTRUCTION}\n<Query>: {query}\n<Document>: {document}"
        ids = (
            self.prefix_ids
            + self.tokenizer.encode(value, add_special_tokens=False, truncation=False)
            + self.suffix_ids
        )
        return {"input_ids": ids, "attention_mask": [1] * len(ids)}

    def token_count(self, query, document):
        return len(self.encode_pair(query, document)["input_ids"])

    def recipe(self):
        self.load_tokenizer()
        return {
            "version": 1,
            "model": self.spec.to_dict(),
            "snapshot_hash": self.snapshot_hash,
            "device": self.device,
            "precision": self.precision,
            "budget": self.budget,
            "attention": "sdpa",
            "truncation": False,
            "libraries": {
                n: importlib.metadata.version(n) for n in ("torch", "transformers", "numpy")
            },
            "seed": 42,
            "threads": 4,
            "score": "single classification logit"
            if self.spec.architecture == "sequence_classification"
            else "yes_logit - no_logit",
            "instruction": None
            if self.spec.architecture == "sequence_classification"
            else INSTRUCTION,
            "prefix": None if self.spec.architecture == "sequence_classification" else PREFIX,
            "suffix": None if self.spec.architecture == "sequence_classification" else SUFFIX,
        }

    def load(self):
        if self.model is not None:
            return
        self.load_tokenizer()
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification

        self.torch = torch
        torch.set_num_threads(4)
        torch.manual_seed(42)
        torch.backends.cuda.matmul.allow_tf32 = False
        if self.device == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA indisponible ; aucun repli CPU implicite.")
            torch.cuda.reset_peak_memory_stats()
        cls = (
            AutoModelForSequenceClassification
            if self.spec.architecture == "sequence_classification"
            else AutoModelForCausalLM
        )
        started = time.perf_counter()
        try:
            self.model = (
                cls.from_pretrained(
                    self.folder,
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                    dtype=torch.bfloat16 if self.device == "cuda" else torch.float32,
                    attn_implementation="sdpa",
                )
                .to(self.device)
                .eval()
            )
            self.synchronize()
            self.load_seconds = time.perf_counter() - started
        except (RuntimeError, MemoryError):
            self.close()
            raise ValueError(
                "Chargement du reranker impossible ; ressources locales à vérifier."
            ) from None

    def synchronize(self):
        if self.device == "cuda" and self.torch is not None:
            self.torch.cuda.synchronize()

    def score(self, pairs):
        if self.model is None:
            raise ValueError("Charger explicitement le modèle.")
        if not pairs or len(pairs) > 4:
            raise ValueError("Lot de 1 à 4 segments requis.")
        encoded = [self.encode_pair(p.query, p.document) for p in pairs]
        if any(len(v["input_ids"]) > self.budget for v in encoded):
            raise ValueError("Couple hors budget ; aucune troncature.")
        padded = self.tokenizer.pad(encoded, padding=True, return_tensors="pt").to(self.device)
        try:
            with self.torch.inference_mode():
                if self.spec.architecture == "sequence_classification":
                    scores = self.model(**padded, return_dict=True).logits.reshape(-1).float()
                else:
                    logits = (
                        self.model(**padded, logits_to_keep=1, use_cache=False, return_dict=True)
                        .logits[:, -1, :]
                        .float()
                    )
                    scores = logits[:, self.yes_id] - logits[:, self.no_id]
            return validate_scores(scores.cpu().tolist(), len(pairs))
        except (RuntimeError, MemoryError):
            raise ValueError(
                "Inférence reranker interrompue ; reprendre les lots non validés."
            ) from None

    def close(self):
        self.model = None
        gc.collect()
        if self.torch is not None and self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
