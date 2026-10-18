"""Transformers local NF4, GPU explicite ; aucun téléchargement ni serveur."""

import gc
import os
import time

from cahier_rag.judges.models import verify


class TransformersJudge:
    def __init__(self, spec, root, config, *, prompt_version="relevance-fr-v1"):
        self.prompt_version = prompt_version
        self.spec, self.root, self.config = spec, root, config
        self.model, self.tokenizer, self.torch = None, None, None
        self.load_seconds = 0

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
            self.folder, local_files_only=True, trust_remote_code=False
        )
        self.tokenizer.padding_side = "left"
        self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

    def load(self):
        if self.model is not None:
            return
        self.load_tokenizer()
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise ValueError("CUDA indisponible ; aucun repli implicite.")
        self.torch = torch
        torch.set_num_threads(4)
        torch.manual_seed(self.config.seed)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.folder,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                dtype=torch.bfloat16,
                device_map={"": 0},
                quantization_config=BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                ),
                attn_implementation="sdpa",
            )
            self.model.eval()
            torch.cuda.synchronize()
            self.load_seconds = time.perf_counter() - started
        except (RuntimeError, MemoryError):
            self.close()
            raise ValueError(
                "Chargement GPU impossible ; vérifier les ressources locales."
            ) from None

    def rendered(self, item):
        return self.tokenizer.apply_chat_template(
            item.messages(self.prompt_version),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def token_counts(self, inputs):
        self.load_tokenizer()
        return [
            len(
                self.tokenizer(self.rendered(i), add_special_tokens=False, truncation=False)[
                    "input_ids"
                ]
            )
            for i in inputs
        ]

    def generate(self, inputs):
        if self.model is None:
            raise ValueError("Charger explicitement le juge.")
        counts = self.token_counts(inputs)
        if any(
            n > self.config.max_input_tokens
            or n + self.config.max_new_tokens > self.spec.context_tokens
            for n in counts
        ):
            raise ValueError("Contexte trop long ; aucune troncature.")
        encoded = self.tokenizer(
            [self.rendered(i) for i in inputs],
            padding=True,
            truncation=False,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
        try:
            with self.torch.inference_mode():
                output = self.model.generate(
                    **encoded,
                    max_new_tokens=self.config.max_new_tokens,
                    do_sample=False,
                    num_beams=1,
                    temperature=None,
                    top_p=None,
                    top_k=None,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    use_cache=True,
                )
            self.last_output_tokens = int(
                (output[:, encoded["input_ids"].shape[1] :] != self.tokenizer.eos_token_id)
                .sum()
                .item()
            )
            return self.tokenizer.batch_decode(
                output[:, encoded["input_ids"].shape[1] :], skip_special_tokens=True
            )
        except (RuntimeError, MemoryError):
            raise ValueError(
                "Génération GPU interrompue ; lot non validé, reprise possible."
            ) from None

    def close(self):
        self.model = None
        gc.collect()
        if self.torch is not None and self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
