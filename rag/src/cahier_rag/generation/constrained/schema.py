"""Schéma v1 adapté aux références, sous-ensemble du contrat RAG-022 non affaibli."""

from copy import deepcopy

SCHEMA_VERSION = "rag-response-schema-v4-native-token-filter"
DECODER_CONFIG = {
    "max_consecutive_whitespaces": 12,
    "force_json_field_order": False,
    "max_json_array_length": 20,
}
POST_VALIDATION = [
    "unique references",
    "non-whitespace strings",
    "quotes reference belongs to block",
    "literal quote is exact source substring",
    "no unstructured quotes/bracketed references",
    "semantic support is NOT checked by decoder or deterministic validator",
]


def response_schema(item):
    refs = [s["reference"] for s in item.document["sources"]]
    if len(refs) != len(set(refs)) or any(not isinstance(r, str) or not r for r in refs):
        raise ValueError("Références documentaires invalides.")
    reference = (
        {"type": "string", "enum": refs} if refs else {"type": "string", "enum": ["__NO_SOURCE__"]}
    )
    # Sans source, seul un bloc limitation sans citation peut être généré.
    quote = {
        "type": "object",
        "properties": {
            "reference": reference,
            "text": {
                "type": "string",
                "minLength": 1,
                "maxLength": max([len(s["answer"]) for s in item.document["sources"]], default=1),
            },
        },
        "required": ["reference", "text"],
        "additionalProperties": False,
    }
    props = {
        "kind": {"type": "string", "enum": ["synthesis", "reported_opinion", "reported_claim"]},
        "text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 600,
        },
        "references": {
            "type": "array",
            "items": reference,
            "minItems": 1,
            "maxItems": min(3, len(refs)),
            "uniqueItems": True,
        },
        "quotes": {"type": "array", "items": quote, "minItems": 0, "maxItems": 8},
    }
    normal = {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }
    limitation = deepcopy(normal)
    limitation["properties"]["kind"] = {"type": "string", "enum": ["limitation"]}
    limitation["properties"]["references"]["minItems"] = 0
    if not refs:
        limitation["properties"]["quotes"]["maxItems"] = 0
        block = limitation
    else:
        # Base required/properties explicites pour le merge oneOf du parseur LMFE.
        block = {"type": "object", "properties": {}, "required": [], "oneOf": [normal, limitation]}
    return {
        "type": "object",
        "properties": {
            "blocks": {"type": "array", "items": block, "minItems": 1, "maxItems": 4},
            "limits": {
                "type": "array",
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
                "minItems": 0,
                "maxItems": 3,
            },
            "insufficient_sources": {"type": "boolean"},
        },
        "required": ["blocks", "limits", "insufficient_sources"],
        "additionalProperties": False,
    }


def parser_for(item):
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig

    config = CharacterLevelParserConfig(**DECODER_CONFIG)
    extra = "".join(chr(n) for n in range(160, 384)) + "…–—‘’“”€"
    extra += getattr(item, "query", "")
    for source in item.document["sources"]:
        extra += "".join(source.get(k, "") for k in ("answer", "question", "questionnaire"))
    config.alphabet = "".join(sorted(c for c in set(config.alphabet + extra) if ord(c) >= 32))
    return JsonSchemaParser(response_schema(item), config=config)


def accepts(text, item):
    """Diagnostic caractère par caractère, sans tokenizer ni poids de modèle."""
    parser = parser_for(item)
    for c in text:
        if c not in parser.get_allowed_characters():
            return False
        parser = parser.add_character(c)
    return parser.can_end()
