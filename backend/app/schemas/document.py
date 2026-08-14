"""매뉴얼 문서 DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.document import DocumentEntity
from app.domain.ingestion_job import IngestionJob


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    mime: str
    size_bytes: int
    page_count: int | None = None
    chunk_count: int | None = None
    tags: list[str] = []
    equipment_refs: list[str] = []
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, entity: DocumentEntity) -> "DocumentOut":
        return cls(
            id=entity.id or "",
            title=entity.title,
            status=entity.status.value,
            mime=entity.mime,
            size_bytes=entity.size_bytes,
            page_count=entity.page_count,
            chunk_count=entity.chunk_count,
            tags=entity.tags,
            equipment_refs=entity.equipment_refs,
            error=entity.error,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    type: str
    action: str
    status: str
    attempts: int
    last_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_entity(cls, job: IngestionJob) -> "JobOut":
        return cls(
            id=job.id or "",
            document_id=job.document_id,
            type=job.type.value,
            action=job.action.value,
            status=job.status.value,
            attempts=job.attempts,
            last_error=job.last_error,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
        )


class ChunkItem(BaseModel):
    seq: int
    page: int
    heading: str
    text: str
    char_count: int


class DocumentChunksOut(BaseModel):
    document_id: str
    title: str
    total: int
    chunks: list[ChunkItem]

