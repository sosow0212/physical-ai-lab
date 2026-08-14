"""설계도면 도메인 — 매뉴얼과 라이프사이클이 달라 별도 애그리게잇으로 분리했다."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class DrawingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class DrawingEntity:
    """설계도면 1건 (MongoDB drawings 컬렉션 대응)."""

    title: str
    drawing_no: str
    file_path: str
    mime: str
    equipment: str | None = None
    line: str | None = None
    description: str | None = None
    revision: int = 1
    status: DrawingStatus = DrawingStatus.PENDING
    error: str | None = None
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_doc(self) -> dict:
        doc = {
            "title": self.title,
            "drawing_no": self.drawing_no,
            "file_path": self.file_path,
            "mime": self.mime,
            "equipment": self.equipment,
            "line": self.line,
            "description": self.description,
            "revision": self.revision,
            "status": self.status.value,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.id is not None:
            from bson import ObjectId

            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_doc(cls, doc: dict) -> "DrawingEntity":
        entity = cls(
            title=doc["title"],
            drawing_no=doc["drawing_no"],
            file_path=doc["file_path"],
            mime=doc["mime"],
            equipment=doc.get("equipment"),
            line=doc.get("line"),
            description=doc.get("description"),
            revision=doc.get("revision", 1),
            status=DrawingStatus(doc.get("status", DrawingStatus.PENDING.value)),
            error=doc.get("error"),
            created_at=doc.get("created_at", datetime.now(UTC)),
            updated_at=doc.get("updated_at", datetime.now(UTC)),
        )
        entity.id = str(doc["_id"])
        return entity
