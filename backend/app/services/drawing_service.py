"""설계도면 유스케이스 — 등록/수정/리비전/삭제 (메타데이터 변경 시 재수집)."""

import logging

from aiokafka import AIOKafkaProducer
from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.domain.drawing import DrawingEntity, DrawingStatus
from app.domain.ingestion_job import JobAction, JobType
from app.infrastructure.storage import FileStorage
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.services.ingest_events import dispatch_ingest_job

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class DrawingService:
    def __init__(
        self,
        drawing_repo: DrawingRepository,
        job_repo: IngestionJobRepository,
        producer: AIOKafkaProducer,
        storage: FileStorage,
        settings: Settings,
    ) -> None:
        self._drawings = drawing_repo
        self._jobs = job_repo
        self._producer = producer
        self._storage = storage
        self._settings = settings

    async def create(
        self,
        file: UploadFile,
        title: str,
        drawing_no: str,
        equipment: str | None,
        line: str | None,
        description: str | None,
    ) -> DrawingEntity:
        """도면 등록 → 파일 저장 + PENDING + 수집 이벤트."""
        self._validate(file)
        content = await file.read()
        path = self._storage.save(file.filename or "drawing.png", content)
        entity = await self._drawings.insert(
            DrawingEntity(
                title=title,
                drawing_no=drawing_no,
                file_path=path,
                mime=file.content_type or "image/png",
                equipment=(equipment or None) or None,
                line=(line or None) or None,
                description=(description or None) or None,
            )
        )
        await self._dispatch(entity.id, JobAction.UPSERT)
        logger.info("도면 등록", extra={"drawing_id": entity.id, "drawing_no": drawing_no})
        return entity

    async def list_drawings(self, *, q: str | None = None) -> list[DrawingEntity]:
        filter_ = {"title": {"$regex": q, "$options": "i"}} if q else {}
        return await self._drawings.find_all(filter_, limit=100, sort=[("created_at", -1)])

    async def get_drawing(self, drawing_id: str) -> DrawingEntity:
        return await self._drawings.find_by_id_or_fail(drawing_id)

    async def update(
        self, drawing_id: str, *, title=None, equipment=None, line=None, description=None
    ) -> DrawingEntity:
        """메타데이터 수정 — 검색에 쓰이는 텍스트가 바뀌면 자동 재수집."""
        entity = await self._drawings.find_by_id_or_fail(drawing_id)
        changes = {
            k: v
            for k, v in {
                "title": title,
                "equipment": equipment,
                "line": line,
                "description": description,
            }.items()
            if v is not None
        }
        if not changes:
            return entity
        entity = await self._drawings.update_by_id(
            drawing_id,
            {**changes, "status": DrawingStatus.PENDING.value, "error": None},
        )
        await self._dispatch(drawing_id, JobAction.UPSERT)
        return entity

    async def add_revision(self, drawing_id: str, file: UploadFile) -> DrawingEntity:
        """신규 리비전 파일 교체 — revision +1 후 재수집."""
        self._validate(file)
        entity = await self._drawings.find_by_id_or_fail(drawing_id)
        content = await file.read()
        self._storage.delete(entity.file_path)
        path = self._storage.save(file.filename or "drawing.png", content)
        entity = await self._drawings.update_by_id(
            drawing_id,
            {
                "file_path": path,
                "mime": file.content_type or "image/png",
                "revision": entity.revision + 1,
                "status": DrawingStatus.PENDING.value,
                "error": None,
            },
        )
        await self._dispatch(drawing_id, JobAction.UPSERT)
        return entity

    async def delete(self, drawing_id: str) -> None:
        """파일 + Mongo 즉시 삭제 → Milvus 카드는 이벤트로 비동기 정리."""
        entity = await self._drawings.find_by_id_or_fail(drawing_id)
        self._storage.delete(entity.file_path)
        await self._drawings.delete_by_id(drawing_id)
        await self._dispatch(drawing_id, JobAction.DELETE)

    async def _dispatch(self, drawing_id: str, action: JobAction) -> None:
        await dispatch_ingest_job(self._jobs, self._producer, drawing_id, JobType.DRAWING, action)

    @staticmethod
    def _validate(file: UploadFile) -> None:
        if (file.content_type or "") not in ALLOWED_IMAGE_MIME:
            raise ValidationAppError(f"PNG/JPG 이미지만 등록할 수 있습니다: {file.filename}")
        if (file.size or 0) > MAX_IMAGE_BYTES:
            raise ValidationAppError(f"파일이 너무 큽니다 (최대 20MB): {file.filename}")
