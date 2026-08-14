"""설계도면 API — 등록/목록/수정/리비전/삭제/원본 스트림."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_drawing_service
from app.schemas.drawing import DrawingOut, DrawingUpdateIn
from app.services.drawing_service import DrawingService

router = APIRouter(prefix="/drawings", tags=["drawings"])


@router.post("", status_code=202)
async def create_drawing(
    file: UploadFile,
    service: Annotated[DrawingService, Depends(get_drawing_service)],
    title: str = Form(...),
    drawing_no: str = Form(...),
    equipment: str | None = Form(None),
    line: str | None = Form(None),
    description: str | None = Form(None),
) -> DrawingOut:
    entity = await service.create(file, title, drawing_no, equipment, line, description)
    return DrawingOut.from_entity(entity)


@router.get("")
async def list_drawings(
    service: Annotated[DrawingService, Depends(get_drawing_service)], q: str | None = None
) -> list[DrawingOut]:
    return [DrawingOut.from_entity(d) for d in await service.list_drawings(q=q)]


@router.get("/{drawing_id}")
async def get_drawing(
    drawing_id: str, service: Annotated[DrawingService, Depends(get_drawing_service)]
) -> DrawingOut:
    return DrawingOut.from_entity(await service.get_drawing(drawing_id))


@router.patch("/{drawing_id}")
async def update_drawing(
    drawing_id: str,
    body: DrawingUpdateIn,
    service: Annotated[DrawingService, Depends(get_drawing_service)],
) -> DrawingOut:
    entity = await service.update(
        drawing_id,
        title=body.title,
        equipment=body.equipment,
        line=body.line,
        description=body.description,
    )
    return DrawingOut.from_entity(entity)


@router.post("/{drawing_id}/revisions", status_code=202)
async def add_revision(
    drawing_id: str,
    file: UploadFile,
    service: Annotated[DrawingService, Depends(get_drawing_service)],
) -> DrawingOut:
    entity = await service.add_revision(drawing_id, file)
    return DrawingOut.from_entity(entity)


@router.delete("/{drawing_id}", status_code=204)
async def delete_drawing(
    drawing_id: str, service: Annotated[DrawingService, Depends(get_drawing_service)]
) -> None:
    await service.delete(drawing_id)


@router.get("/{drawing_id}/file")
async def drawing_file(
    drawing_id: str, service: Annotated[DrawingService, Depends(get_drawing_service)]
) -> FileResponse:
    """원본 이미지 스트림 (썸네일/뷰어용)."""
    entity = await service.get_drawing(drawing_id)
    return FileResponse(
        entity.file_path, media_type=entity.mime, filename=f"{entity.drawing_no}.png"
    )
