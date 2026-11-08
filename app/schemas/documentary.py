"""Public/documentary presentation contracts, independent of questionnaire models."""

from typing import Literal

from pydantic import BaseModel, Field


class DocumentaryWarning(BaseModel):
    code: str
    message: str


class DocumentarySource(BaseModel):
    label: str
    url: str


class DocumentaryMetadata(BaseModel):
    document_id: str
    release_id: str
    title: str
    source_title: str
    place: str | None = None
    orders: list[str]
    reference: str
    sources: list[DocumentarySource]
    warnings: list[DocumentaryWarning]
    url: str


class HistoricalSearchResult(DocumentaryMetadata):
    kind: Literal["historical_document"] = "historical_document"
    corpus_id: Literal["cahiers-1789-ap-stanford"] = "cahiers-1789-ap-stanford"
    rank: int = Field(ge=1)
    excerpt: str
    unit_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    match_origin: Literal["text", "metadata"] = "text"


class DocumentaryCatalogue(BaseModel):
    items: list[DocumentaryMetadata]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)
    has_next: bool
    preview: bool = False


class DocumentaryBlock(BaseModel):
    text: str
    anchor: str | None = None


class DocumentaryUnit(BaseModel):
    unit_id: str
    start_offset: int
    end_offset: int
    text_sha256: str


class DocumentaryFragment(DocumentaryBlock):
    selected: bool = False


class DocumentaryParagraph(BaseModel):
    kind: Literal["paragraph", "heading"]
    start_offset: int
    end_offset: int
    fragments: list[DocumentaryFragment]


class DocumentaryReading(DocumentaryMetadata):
    blocks: list[DocumentaryBlock]
    paragraphs: list[DocumentaryParagraph]
    selected_unit: DocumentaryUnit | None
    previous: str | None
    next: str | None
    preview: bool = False
    text_sha256: str


class CorpusOption(BaseModel):
    id: Literal["2019", "1789"]
    label: str
    available: bool
    published: bool
    preview: bool = False
