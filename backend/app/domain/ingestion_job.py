"""수집(ingestion) 작업 도메인 — api가 발행하고 worker가 소비하는 작업 단위."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class JobType(StrEnum):
    MANUAL = "manual"
    DRAWING = "drawing"


class JobAction(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"  # 재시도 여지 있음
    DEAD = "DEAD"  # 재시도 소진 (DLQ行)


@dataclass
class IngestionJob:
    """ingestion_jobs 컬렉션 1건 — Kafka 이벤트의 지속 상태 추적용."""

    document_id: str
    type: JobType
    action: JobAction
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_doc(self) -> dict:
        doc = {
            "document_id": _to_oid(self.document_id),
            "type": self.type.value,
            "action": self.action.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "created_at": self.created_at,
        }
        if self.id is not None:
            from bson import ObjectId

            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_doc(cls, doc: dict) -> "IngestionJob":
        job = cls(
            document_id=str(doc["document_id"]),
            type=JobType(doc["type"]),
            action=JobAction(doc["action"]),
            status=JobStatus(doc.get("status", JobStatus.PENDING.value)),
            attempts=doc.get("attempts", 0),
            last_error=doc.get("last_error"),
            started_at=doc.get("started_at"),
            finished_at=doc.get("finished_at"),
            created_at=doc.get("created_at", datetime.now(UTC)),
        )
        job.id = str(doc["_id"])
        return job


def _to_oid(id_str: str):
    from bson import ObjectId

    return ObjectId(id_str)
