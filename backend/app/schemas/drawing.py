"""설계도면 DTO."""

from datetime import datetime

from pydantic import BaseModel

from app.domain.drawing import DrawingEntity


class DrawingCreateIn(BaseModel):
    """도면 등록 메타데이터 (multipart 폼 필드)."""

    title: str
    drawing_no: str
    equipment: str | None = None
    line: str | None = None
    description: str | None = None


class DrawingUpdateIn(BaseModel):
    """도면 메타데이터 수정 — 텍스트 필드 변경 시 자동 재수집."""

    title: str | None = None
    equipment: str | None = None
    line: str | None = None
    description: str | None = None


class DrawingOut(BaseModel):
    id: str
    title: str
    drawing_no: str
    equipment: str | None
    line: str | None
    description: str | None
    revision: int
    status: str
    mime: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, d: DrawingEntity) -> "DrawingOut":
        return cls(
            id=d.id or "",
            title=d.title,
            drawing_no=d.drawing_no,
            equipment=d.equipment,
            line=d.line,
            description=d.description,
            revision=d.revision,
            status=d.status.value,
            mime=d.mime,
            error=d.error,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
