"""매뉴얼 문서 도메인."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class DocumentStatus(StrEnum):
    """문서 수집 상태 — 업로드 후 파이프라인을 거치며 진행된다."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class DocumentEntity:
    """매뉴얼 PDF 1건 (MongoDB documents 컬렉션 대응)."""

    title: str
    file_path: str
    mime: str
    size_bytes: int
    status: DocumentStatus = DocumentStatus.PENDING
    error: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    tags: list[str] = field(default_factory=list)
    equipment_refs: list[str] = field(default_factory=list)
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_doc(self) -> dict:
        """MongoDB 저장용 dict (id → _id 변환 포함)."""
        doc = {
            "title": self.title,
            "doc_type": "manual",
            "file_path": self.file_path,
            "mime": self.mime,
            "size_bytes": self.size_bytes,
            "status": self.status.value,
            "error": self.error,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "tags": self.tags,
            "equipment_refs": self.equipment_refs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.id is not None:
            doc["_id"] = _to_object_id(self.id)
        return doc

    @classmethod
    def from_doc(cls, doc: dict) -> "DocumentEntity":
        """MongoDB document → 엔티티 복원."""
        entity = cls(
            title=doc["title"],
            file_path=doc["file_path"],
            mime=doc["mime"],
            size_bytes=doc["size_bytes"],
            status=DocumentStatus(doc.get("status", DocumentStatus.PENDING.value)),
            error=doc.get("error"),
            page_count=doc.get("page_count"),
            chunk_count=doc.get("chunk_count"),
            tags=list(doc.get("tags", [])),
            equipment_refs=list(doc.get("equipment_refs", [])),
            created_at=doc.get("created_at", datetime.now(UTC)),
            updated_at=doc.get("updated_at", datetime.now(UTC)),
        )
        entity.id = str(doc["_id"])
        return entity


def _to_object_id(id_str: str):
    from bson import ObjectId

    return ObjectId(id_str)
