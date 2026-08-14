from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse


from app.api.deps import get_document_service
from app.schemas.common import PageOut
from app.schemas.document import ChunkItem, DocumentChunksOut, DocumentOut, JobOut
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


@router.get("/{document_id}/file")

async def document_file(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    download: bool = False,
) -> FileResponse:
    """원본 PDF 스트림 — download=False 시 inline 미리보기, True 시 강제 다운로드."""
    entity = await service.get_file(document_id)
    encoded = quote(f"{entity.title}.pdf")
    disposition = "attachment" if download else "inline"
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded}"}
    return FileResponse(
        entity.file_path,
        media_type="application/pdf",
        headers=headers,
    )



@router.get("/{document_id}/chunks", response_model=DocumentChunksOut)
async def get_document_chunks(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentChunksOut:
    """문서의 분할된 청크 목록 조회 (학습/검증용)."""
    entity, chunks = await service.get_chunks(document_id)
    items = [
        ChunkItem(
            seq=c.get("seq", i),
            page=c.get("page", 1),
            heading=c.get("heading", ""),
            text=c.get("text", ""),
            char_count=len(c.get("text", "")),
        )
        for i, c in enumerate(chunks)
    ]
    return DocumentChunksOut(
        document_id=entity.id or document_id,
        title=entity.title,
        total=len(items),
        chunks=items,
    )



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
