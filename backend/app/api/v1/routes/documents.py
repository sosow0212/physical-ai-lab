"""매뉴얼 문서 API — 업로드/목록/상세/삭제/재수집."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.deps import get_document_service
from app.schemas.common import PageOut
from app.schemas.document import DocumentOut, JobOut
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202)
async def upload_documents(
    files: list[UploadFile],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> dict:
    """PDF 업로드 → 비동기 수집 시작 (202 Accepted)."""
    entities = await service.upload(files)
    return {"documents": [DocumentOut.from_entity(e) for e in entities]}


@router.get("")
async def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageOut:
    items, total = await service.list_documents(status=status, q=q, page=page, page_size=page_size)
    return PageOut(
        items=[DocumentOut.from_entity(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> dict:
    entity, jobs = await service.get_document(document_id)
    return {
        "document": DocumentOut.from_entity(entity),
        "recent_jobs": [JobOut.from_entity(j) for j in jobs],
    }


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> None:
    await service.delete_document(document_id)


@router.post("/{document_id}/reingest", status_code=202)
async def reingest_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentOut:
    entity = await service.reingest(document_id)
    return DocumentOut.from_entity(entity)
