"""Paramètres immuables d'une extraction limitée et versions explicites."""

import hashlib
from dataclasses import asdict, dataclass, fields

from cahier_rag.contracts import CONTRACT_VERSION, UnitType, canonical_json, validate_id

READER_VERSION = "gdn-v1"
PIPELINE_VERSION = 1
MAX_DOCUMENT_LIMIT = 10_000
MAX_SOURCE_ROWS = 100_000


class ExtractionError(ValueError):
    """Erreur métier ne contenant aucune donnée documentaire ni URL."""


@dataclass(frozen=True)
class ExtractionSpec:
    limit: int
    corpus_id: str = "gdn-2019"
    batch_size: int = 500
    max_source_rows: int = MAX_SOURCE_ROWS
    questionnaire_id: int | None = None
    contribution_id: int | None = None
    unit_type: UnitType | None = None
    contract_version: int = CONTRACT_VERSION
    reader_version: str = READER_VERSION
    pipeline_version: int = PIPELINE_VERSION

    def __post_init__(self) -> None:
        if type(self.limit) is not int or not 1 <= self.limit <= MAX_DOCUMENT_LIMIT:
            raise ExtractionError(
                f"La limite explicite doit être comprise entre 1 et {MAX_DOCUMENT_LIMIT} documents."
            )
        if type(self.batch_size) is not int or not 1 <= self.batch_size <= 5000:
            raise ExtractionError("La taille des lots doit être comprise entre 1 et 5000 lignes.")
        if (
            type(self.max_source_rows) is not int
            or not 1 <= self.max_source_rows <= MAX_SOURCE_ROWS
        ):
            raise ExtractionError(
                f"Le plafond de lignes sources doit être compris entre 1 et {MAX_SOURCE_ROWS}."
            )
        if not isinstance(self.corpus_id, str) or not self.corpus_id.strip():
            raise ExtractionError("Un identifiant de corpus est requis.")
        for name in ("questionnaire_id", "contribution_id"):
            value = getattr(self, name)
            if value is not None:
                validate_id(value, name)
        if self.unit_type is not None and not isinstance(self.unit_type, UnitType):
            raise ExtractionError("Type d'unité invalide.")

    def ensure_current(self) -> None:
        if (self.contract_version, self.reader_version, self.pipeline_version) != (
            CONTRACT_VERSION,
            READER_VERSION,
            PIPELINE_VERSION,
        ):
            raise ExtractionError(
                "Versions de contrat, lecteur ou pipeline incompatibles avec la reprise."
            )

    def to_dict(self) -> dict:
        value = asdict(self)
        for name in ("questionnaire_id", "contribution_id"):
            value[name] = str(value[name]) if value[name] is not None else None
        value["unit_type"] = self.unit_type.value if self.unit_type is not None else None
        return value

    @classmethod
    def from_dict(cls, value: dict) -> "ExtractionSpec":
        if set(value) != {field.name for field in fields(cls)}:
            raise ExtractionError("Paramètres de manifeste non pris en charge.")
        decoded = dict(value)
        for name in ("questionnaire_id", "contribution_id"):
            raw = value[name]
            if raw is not None:
                if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
                    raise ExtractionError("Identifiant de filtre invalide dans le manifeste.")
                decoded[name] = int(raw)
        decoded["unit_type"] = (
            UnitType(value["unit_type"]) if value["unit_type"] is not None else None
        )
        return cls(**decoded)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode()).hexdigest()
