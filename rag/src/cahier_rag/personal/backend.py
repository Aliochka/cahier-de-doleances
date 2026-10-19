"""Même chargeur NF4 ; contraintes JSON sans fermeture forcée à 600 caractères."""

import importlib.metadata
import time

from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.backend import LocalGenerator
from cahier_rag.personal.contracts import ANALYSIS_SYSTEM, SYSTEM, VERSION, Config, schema


class Generator(LocalGenerator):
    def __init__(self, root, *, token_filter=False):
        super().__init__(root, Config())
        if token_filter:
            raise ValueError("Filtre de tokens LMFE non utilisé par cette recette XGrammar.")
        self.token_filter = token_filter
        self.data = None

    def recipe(self):
        return super().recipe() | {
            "version": VERSION,
            "prompt_hash": digest(SYSTEM),
            "analysis_prompt_hash": digest(ANALYSIS_SYSTEM),
            "schema": "personal-json-v2-sentence-end",
            "token_filter": self.token_filter,
            "decoder": "xgrammar-" + importlib.metadata.version("xgrammar"),
            "sentence_end_validation": True,
            "repetition_penalty": 1.05,
        }

    def generate_one(self, item):
        self.load()
        rendered = self.rendered(item)
        tokens = self.token_counts([item])[0]
        if (
            tokens > self.config.max_input_tokens
            or tokens + self.config.max_new_tokens > self.spec.context_tokens
        ):
            raise ValueError("input_window_exceeded_no_truncation")
        import xgrammar as xgr
        from xgrammar.contrib.hf import LogitsProcessor

        if self.data is None:
            self.data = xgr.GrammarCompiler(
                xgr.TokenizerInfo.from_huggingface(
                    self.tokenizer, vocab_size=self.model.config.vocab_size
                )
            )
        before = time.perf_counter()
        compiled = self.data.compile_json_schema(schema(item))
        grammar_seconds = time.perf_counter() - before
        processor = LogitsProcessor(compiled)
        encoded = self.tokenizer(
            rendered, add_special_tokens=False, truncation=False, return_tensors="pt"
        ).to("cuda")
        self.torch.cuda.synchronize()
        started = time.perf_counter()
        with self.torch.inference_mode():
            result = self.model.generate(
                **encoded,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                num_beams=1,
                use_cache=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                logits_processor=[processor],
                repetition_penalty=1.05,
            )
        self.torch.cuda.synchronize()
        output = result[:, encoded["input_ids"].shape[1] :]
        count = int((output != self.tokenizer.eos_token_id).sum().item())
        return {
            "raw_output": self.tokenizer.batch_decode(output, skip_special_tokens=True)[0],
            "input_tokens": tokens,
            "output_tokens": count,
            "seconds": time.perf_counter() - started,
            "token_limit_reached": count >= self.config.max_new_tokens,
            "peak_vram_bytes": self.torch.cuda.max_memory_allocated(),
            "load_seconds": self.load_seconds,
            "grammar_seconds": grammar_seconds,
        }
