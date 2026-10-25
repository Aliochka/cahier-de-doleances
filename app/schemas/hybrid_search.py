"""Contrat public hybride ; aucune trace de classement ni donnée privée."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.forms import PublicId


class HybridQuestion(BaseModel):
    id: PublicId
    prompt: str
    url: str


class HybridForm(BaseModel):
    id: PublicId
    name: str
    url: str


class HybridText(BaseModel):
    unit_type: Literal["open_answer", "other_text"]
    unit_index: int = Field(ge=0)
    text: str


class HybridAnswer(BaseModel):
    answer_id: PublicId
    contribution_id: PublicId
    rank: int = Field(ge=1, description="Position stable de carte dans cette sélection.")
    texts: list[HybridText]
    is_truncated: bool
    question: HybridQuestion
    form: HybridForm
    url: str


class SearchWindow(BaseModel):
    document_limit: int = Field(
        ge=1, description="Sortie documentaire de la recette, provisoirement 50."
    )
    retrieval_depth: int = Field(
        ge=1, description="Profondeur par branche, distincte de page_size."
    )
    answer_count: int = Field(
        ge=0, description="Cartes de l'instantané, jamais un total du corpus."
    )
    exhaustive: Literal[False] = False


class HybridWarning(BaseModel):
    code: Literal["source_unavailable"] = "source_unavailable"
    count: int = Field(ge=1)
    message: str = (
        "Certaines réponses ne sont plus accessibles et ont été retirées de cette sélection."
    )


class HybridSearchPage(BaseModel):
    q: str
    state: Literal["idle", "results", "empty", "sources_unavailable"]
    mode: Literal["hybrid", "lexical"] = "hybrid"
    recipe_version: str
    items: list[HybridAnswer]
    page_size: int = Field(ge=1, le=20)
    has_next: bool
    next_cursor: str | None
    previous_cursor: str | None
    first_cursor: str | None
    expires_at: str | None
    window: SearchWindow
    warnings: list[HybridWarning]


class HybridErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool


class HybridErrorEnvelope(BaseModel):
    error: HybridErrorDetail
    request_id: str
