"""Filtrage LMFE au décodage ; chargeur et prompt RAG-022 inchangés."""

import importlib.metadata
import time

from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.backend import LocalGenerator
from cahier_rag.generation.constrained.schema import (
    DECODER_CONFIG,
    SCHEMA_VERSION,
    parser_for,
    response_schema,
)

VERSION = "generation-fr-v3-constrained"


def safe_token_ids(tokens):
    """Sous-ensemble sans échappements ni guillemets typographiques en sortie.

    Les textes sources ne sont pas transformés ; le validateur original reste requis.
    """
    return {i for i, text, _ in tokens if not any(c in text for c in "\\«»“”")}


class ConstrainedGenerator(LocalGenerator):
    def __init__(self, root, config):
        super().__init__(root, config)
        self.tokenizer_data = None
        self.tokenizer_preparation_seconds = 0.0
        self.last_metrics = {}
        self.safe_tokens = None

    def recipe(self):
        original = super().recipe()
        return original | {
            "version": VERSION,
            "prompt_version": original["version"],
            "prompt_changed": False,
            "decoder": {
                "engine": "lm-format-enforcer",
                "version": importlib.metadata.version("lm-format-enforcer"),
                "interegular_version": importlib.metadata.version("interegular"),
                "schema_version": SCHEMA_VERSION,
                "config": DECODER_CONFIG,
                "per_query_reference_enum": True,
                "alphabet_policy": "LMFE ASCII + Latin U+00A0..017F + punctuation + input characters; C0 controls excluded",
                "mechanism": "Transformers prefix_allowed_tokens_fn",
                "output_token_filter": "no backslash or typographic quotation characters v1",
            },
        }

    def generate(self, inputs):
        self.last_metrics = {}
        if self.model is None or len(inputs) != 1:
            raise ValueError("Modèle chargé et batch=1 requis.")
        item = inputs[0]
        n = self.token_counts(inputs)[0]
        if (
            n > self.config.max_input_tokens
            or n + self.config.max_new_tokens > self.spec.context_tokens
        ):
            raise ValueError("Contexte hors fenêtre, aucune troncature.")
        from lmformatenforcer.integrations.transformers import (
            build_token_enforcer_tokenizer_data,
            build_transformers_prefix_allowed_tokens_fn,
        )

        tokenizer_setup_seconds = 0.0
        if self.tokenizer_data is None:
            before = time.perf_counter()
            self.tokenizer_data = build_token_enforcer_tokenizer_data(self.tokenizer)
            self.safe_tokens = safe_token_ids(self.tokenizer_data.regular_tokens)
            self.safe_tokens.add(self.tokenizer.eos_token_id)
            self.tokenizer_preparation_seconds = time.perf_counter() - before
            tokenizer_setup_seconds = self.tokenizer_preparation_seconds
        before = time.perf_counter()
        prefix = build_transformers_prefix_allowed_tokens_fn(self.tokenizer_data, parser_for(item))
        grammar_seconds = time.perf_counter() - before
        callback_seconds = 0.0
        calls = 0

        def allowed(batch_id, sent):
            nonlocal callback_seconds, calls
            start = time.perf_counter()
            try:
                return [i for i in prefix(batch_id, sent) if i in self.safe_tokens]
            finally:
                callback_seconds += time.perf_counter() - start
                calls += 1

        encoded = self.tokenizer(
            [self.rendered(item)],
            padding=True,
            truncation=False,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
        prefill_started = None
        prefill_seconds = None

        def pre_hook(module, args, kwargs):
            nonlocal prefill_started
            if prefill_started is None:
                self.torch.cuda.synchronize()
                prefill_started = time.perf_counter()

        def post_hook(module, args, output):
            nonlocal prefill_seconds
            if prefill_seconds is None:
                self.torch.cuda.synchronize()
                prefill_seconds = time.perf_counter() - prefill_started

        a = self.model.register_forward_pre_hook(pre_hook, with_kwargs=True)
        b = self.model.register_forward_hook(post_hook)
        self.torch.cuda.synchronize()
        before = time.perf_counter()
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
                    prefix_allowed_tokens_fn=allowed,
                )
            self.torch.cuda.synchronize()
            generation_seconds = time.perf_counter() - before
            generated = output[:, encoded["input_ids"].shape[1] :]
            self.last_output_tokens = int((generated != self.tokenizer.eos_token_id).sum().item())
            result = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
        finally:
            a.remove()
            b.remove()
        self.last_metrics = {
            "schema_hash": digest(response_schema(item)),
            "grammar_seconds": grammar_seconds,
            "tokenizer_preparation_seconds": tokenizer_setup_seconds,
            "prefill_seconds": prefill_seconds,
            "generate_seconds": generation_seconds,
            "decode_and_loop_seconds": generation_seconds - (prefill_seconds or 0),
            "callback_wall_seconds": callback_seconds,
            "callback_calls": calls,
            "timing_note": "callback wall time may include CUDA synchronization; prefill is first forward, decode includes filtering and loop",
        }
        return result
