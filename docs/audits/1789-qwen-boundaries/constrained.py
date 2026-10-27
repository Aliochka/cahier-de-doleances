"""Décodage LMFE existant, schéma restreint aux seuls IDs visibles; aucune vérité injectée."""

from cahier_rag.generation.constrained.backend import safe_token_ids
from cahier_rag.judges.backend import TransformersJudge


def schema(window):
    ids = [b["id"] for b in window["blocks"] if b["tag"] != "pb"]
    ref = {"type": "string", "enum": ids}
    nullable = {"anyOf": [ref, {"type": "null"}]}
    annex = {
        "type": "object",
        "properties": {
            "start_id": ref,
            "end_id": ref,
            "relation": {"type": "string", "enum": ["included", "excluded", "uncertain"]},
        },
        "required": ["start_id", "end_id", "relation"],
        "additionalProperties": False,
    }
    props = {
        "decision": {"type": "string", "enum": ["propose", "abstain", "not_found"]},
        "start_id": nullable,
        "end_id": nullable,
        "signatures": {"type": "array", "items": ref, "maxItems": 8},
        "annexes": {"type": "array", "items": annex, "maxItems": 3},
        "other_documents": {"type": "array", "items": ref, "maxItems": 5},
        "uncertain": {"type": "boolean"},
        "reason": {"type": "string", "minLength": 1, "maxLength": 240},
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


class BoundaryJudge(TransformersJudge):
    def generate(self, inputs):
        if len(inputs) != 1:
            raise ValueError("one window at a time")
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
        from lmformatenforcer.integrations.transformers import (
            build_token_enforcer_tokenizer_data,
            build_transformers_prefix_allowed_tokens_fn,
        )

        item = inputs[0]
        n = self.token_counts(inputs)[0]
        if (
            n > self.config.max_input_tokens
            or n + self.config.max_new_tokens > self.spec.context_tokens
        ):
            raise ValueError("context overflow; no truncation")
        if not hasattr(self, "tokenizer_data"):
            self.tokenizer_data = build_token_enforcer_tokenizer_data(self.tokenizer)
            self.safe_tokens = safe_token_ids(self.tokenizer_data.regular_tokens)
            self.safe_tokens.add(self.tokenizer.eos_token_id)
        config = CharacterLevelParserConfig(
            max_consecutive_whitespaces=6, force_json_field_order=True, max_json_array_length=8
        )
        extra = "".join(chr(i) for i in range(160, 384)) + "…–—‘’€"
        config.alphabet = "".join(sorted(c for c in set(config.alphabet + extra) if ord(c) >= 32))
        parser = JsonSchemaParser(schema(item.window), config=config)
        callback = build_transformers_prefix_allowed_tokens_fn(self.tokenizer_data, parser)

        def allowed(batch, sent):
            return [i for i in callback(batch, sent) if i in self.safe_tokens]

        encoded = self.tokenizer(
            [self.rendered(item)],
            padding=True,
            truncation=False,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
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
        generated = output[:, encoded["input_ids"].shape[1] :]
        self.last_output_tokens = int((generated != self.tokenizer.eos_token_id).sum().item())
        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)
