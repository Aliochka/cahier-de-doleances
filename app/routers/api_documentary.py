"""Version-pinned documentary catalogue/reading with fail-closed publication policy."""

from cahier_rag.search.service.control import SearchBusy
from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.documentary import CorpusOption, DocumentaryCatalogue, DocumentaryReading

router = APIRouter(prefix="/api/v1", tags=["Documentary"])
HEADERS = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}


def repository(request):
    common = getattr(getattr(request.app.state, "hybrid_search", None), "common", None)
    if common is None or not common.repository.ready:
        raise HTTPException(404, "Corpus indisponible")
    return common.repository


async def read_safely(common, fn):
    try:
        return await common.read(fn)
    except SearchBusy:
        raise HTTPException(
            503, "Lecture documentaire occupée", headers={"Retry-After": "1"}
        ) from None
    except SQLAlchemyError:
        raise HTTPException(503, "Lecture documentaire indisponible") from None


@router.get("/corpora", response_model=list[CorpusOption], operation_id="list_search_corpora")
async def corpora(request: Request, response: Response):
    response.headers.update(HEADERS)
    common = getattr(getattr(request.app.state, "hybrid_search", None), "common", None)
    preview = common.repository.preview(request) if common else False
    available = (
        await read_safely(common, lambda: common.repository.available(preview=preview))
        if common
        else False
    )
    return [
        dict(id="2019", label="Grand Débat national — 2019", available=True, published=True),
        dict(
            id="1789",
            label="Cahiers de doléances — 1789",
            available=available,
            published=available and not preview,
            preview=preview and available,
        ),
    ]


@router.get(
    "/documentary/1789",
    response_model=DocumentaryCatalogue,
    operation_id="list_historical_documents",
)
async def catalogue(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=50),
):
    response.headers.update(HEADERS)
    repo = repository(request)
    common = request.app.state.hybrid_search.common
    return await read_safely(
        common, lambda: repo.catalogue(page, page_size, preview=repo.preview(request))
    )


@router.get(
    "/documentary/1789/{release}/documents/{document_id}",
    response_model=DocumentaryReading,
    operation_id="read_historical_document",
)
async def read_document(
    request: Request,
    response: Response,
    release: str,
    document_id: str,
    unit: str | None = Query(None, max_length=256),
):
    response.headers.update(HEADERS)
    repo = repository(request)
    common = request.app.state.hybrid_search.common
    return await read_safely(
        common, lambda: repo.read(release, document_id, unit, preview=repo.preview(request))
    )
