"""Adaptateur Transformers chargé explicitement, pooling officiel et réseau interdit."""

import gc
import os
import time

from cahier_rag.embeddings.core import EmbeddingError
from cahier_rag.embeddings.snapshots import verify_snapshot


class TransformersBackend:
    def __init__(self, spec, root, *, device="cpu", precision="float32", threads=4):
        if device not in {"cpu", "cuda"} or precision not in {"float32", "bfloat16", "float16"}:
            raise EmbeddingError("Périphérique ou précision invalide.")
        if device == "cpu" and precision != "float32":
            raise EmbeddingError("Cette expérience CPU requiert float32.")
        if type(threads) is not int or not 1 <= threads <= 16:
            raise EmbeddingError("Nombre de threads entre 1 et 16 requis.")
        self.spec, self.root, self.device, self.precision, self.threads = (
            spec,
            root,
            device,
            precision,
            threads,
        )
        self.dimension, self.max_tokens = spec.dimension, spec.max_tokens
        self.model = None
        self.tokenizer = None
        self.torch = None

    def load_tokenizer(self):
        if self.tokenizer is not None:
            return
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        from transformers import AutoConfig, AutoTokenizer

        started = time.perf_counter()
        self.folder, self.snapshot_hash = verify_snapshot(self.spec, self.root)
        self.integrity_seconds = time.perf_counter() - started
        self.config = AutoConfig.from_pretrained(
            self.folder, local_files_only=True, trust_remote_code=False
        )
        if self.config.hidden_size != self.dimension:
            raise EmbeddingError("Dimension du modèle différente du registre.")
        self.max_tokens = min(self.max_tokens, self.config.max_position_embeddings)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.folder, local_files_only=True, trust_remote_code=False
        )
        self.tokenizer.padding_side = "left" if self.spec.pooling == "last" else "right"

    def token_lengths(self, texts, role):
        self.load_tokenizer()
        return [
            len(
                self.tokenizer(
                    self.spec.prepare(text, role),
                    truncation=False,
                    add_special_tokens=True,
                    return_attention_mask=False,
                )["input_ids"]
            )
            for text in texts
        ]

    def load(self):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        self.load_tokenizer()
        import torch
        from transformers import AutoModel

        self.torch = torch
        torch.set_num_threads(self.threads)
        torch.manual_seed(42)
        if self.device == "cuda":
            if not torch.cuda.is_available():
                raise EmbeddingError("CUDA indisponible ; aucun repli CPU implicite.")
            if self.precision == "bfloat16" and not torch.cuda.is_bf16_supported():
                raise EmbeddingError("bfloat16 non pris en charge par ce GPU.")
            torch.backends.cuda.matmul.allow_tf32 = False
        try:
            self.model = AutoModel.from_pretrained(
                self.folder,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=self.spec.weight_file.endswith(".safetensors"),
                weights_only=True,
                dtype=getattr(torch, self.precision),
                attn_implementation="sdpa",
            )
            self.model.to(self.device).eval()
            if self.device == "cuda":
                torch.cuda.synchronize()
        except (RuntimeError, MemoryError):
            self.close()
            raise EmbeddingError(
                "Chargement CPU/GPU impossible ; vérifier les ressources et le pilote."
            ) from None

    def encode(self, texts, role):
        if self.model is None:
            raise EmbeddingError("Modèle non chargé.")
        inputs = self.tokenizer(
            [self.spec.prepare(text, role) for text in texts],
            padding=True,
            truncation=False,
            return_tensors="pt",
        )
        if inputs["input_ids"].shape[1] > self.max_tokens:
            raise EmbeddingError("Fenêtre dépassée ; aucune troncature.")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        torch = self.torch
        with torch.inference_mode():
            hidden = self.model(**inputs).last_hidden_state
            mask = inputs["attention_mask"]
            if self.spec.pooling == "cls":
                pooled = hidden[:, 0]
            elif self.spec.pooling == "last":
                pooled = hidden[:, -1]
            else:
                pooled = (hidden.float() * mask.unsqueeze(-1)).sum(1) / mask.sum(1).unsqueeze(-1)
            return pooled.float().cpu().tolist()

    def close(self):
        self.model = None
        gc.collect()
        if self.torch is not None and self.device == "cuda" and self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
