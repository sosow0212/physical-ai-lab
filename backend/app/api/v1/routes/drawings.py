from typing import Annotated
from urllib.parse import quote

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
    drawing_id: str,
    service: Annotated[DrawingService, Depends(get_drawing_service)],
    download: bool = False,
) -> FileResponse:
    """원본 이미지 스트림 — download=False 시 inline 미리보기, True 시 강제 다운로드."""
    entity = await service.get_drawing(drawing_id)
    ext = entity.mime.split("/")[-1] if "/" in entity.mime else "png"
    encoded = quote(f"{entity.drawing_no}.{ext}")
    disposition = "attachment" if download else "inline"
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded}"}
    return FileResponse(
        entity.file_path,
        media_type=entity.mime,
        headers=headers,
    )
