"""Préparation déterministe : consignes facultatives, phrases obligatoires, SQL lié."""

import re
import unicodedata
from dataclasses import asdict, dataclass

from sqlalchemy import text

GENERIC_WORDS = tuple(
    sorted(
        {
            "quel",
            "quelle",
            "quels",
            "quelles",
            "comment",
            "pourquoi",
            "retrouver",
            "retrouve",
            "retrouvez",
            "contribution",
            "contributions",
            "citoyen",
            "citoyens",
            "citoyenne",
            "citoyennes",
            "reponse",
            "reponses",
            "evoque",
            "evoquent",
            "mentionne",
            "mentionnent",
            "mentionnant",
            "parle",
            "parlent",
            "proposent",
            "exprimes",
            "exprimees",
        }
    )
)
TOKEN = re.compile(r"""(-?)(?:"([^"]*)"|([^\W_]+(?:['’][^\W_]+)*))""", re.UNICODE)


@dataclass(frozen=True)
class Preparation:
    remove_generic: bool = True
    version: int = 1
    max_terms: int = 32

    def __post_init__(self):
        if type(self.remove_generic) is not bool or self.version != 1 or self.max_terms != 32:
            raise ValueError("Configuration de préparation non supportée.")

    def to_dict(self):
        return asdict(self) | {"generic_words": list(GENERIC_WORDS)}


def folded(word):
    return "".join(
        c for c in unicodedata.normalize("NFD", word.casefold()) if not unicodedata.combining(c)
    )


def tokenize(query, config=Preparation()):
    if not isinstance(query, str) or len(query) > 1000:
        raise ValueError("Requête limitée à 1000 caractères.")
    query = unicodedata.normalize("NFC", query).replace("«", '"').replace("»", '"')
    if query.count('"') % 2:
        raise ValueError("Guillemets non équilibrés.")
    terms, phrases, excluded = [], [], []
    for match in TOKEN.finditer(query):
        negative = bool(match[1]) and (match.start() == 0 or query[match.start() - 1].isspace())
        phrase = match[2]
        value = phrase if phrase is not None else match[3]
        if negative:
            excluded.append(value)
        elif phrase is not None:
            phrases.append(value)
        elif value.upper() != "OR" and not (
            config.remove_generic and folded(value) in GENERIC_WORDS
        ):
            terms.append(value)
    if len(phrases) > 8 or len(excluded) > 8:
        raise ValueError("Au plus huit expressions ou exclusions.")
    return {"terms": terms, "phrases": phrases, "excluded": excluded}


def normalize(connection, tokens, config=Preparation()):
    """PostgreSQL produit les lexèmes et leur échappement ; jamais du SQL interpolé."""
    positive = " ".join(tokens["terms"] + tokens["phrases"])
    lexemes = connection.execute(
        text("SELECT tsvector_to_array(to_tsvector('pg_catalog.french',:value))"),
        {"value": positive},
    ).scalar_one()
    if len(lexemes) > config.max_terms:
        raise ValueError("Au plus 32 lexèmes significatifs.")
    if not lexemes:
        return {"query": "", "terms": []}
    quoted = (
        connection.execute(
            text("SELECT quote_literal(t) FROM unnest(CAST(:terms AS text[])) AS t"),
            {"terms": lexemes},
        )
        .scalars()
        .all()
    )
    parts = []
    if tokens["terms"]:
        parts.append("(" + " | ".join(quoted) + ")")
    for phrase in tokens["phrases"]:
        expr = connection.execute(
            text("SELECT phraseto_tsquery('pg_catalog.french',:value)::text"), {"value": phrase}
        ).scalar_one()
        if not expr:
            # A quoted phrase made entirely of stopwords cannot be verified by this index.
            return {"query": "", "terms": []}
        parts.append("(" + expr + ")")
    for value in tokens["excluded"]:
        expr = connection.execute(
            text("SELECT phraseto_tsquery('pg_catalog.french',:value)::text"), {"value": value}
        ).scalar_one()
        if expr:
            parts.append("!(" + expr + ")")
    return {"query": " & ".join(parts), "terms": lexemes}
