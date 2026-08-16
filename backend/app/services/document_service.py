"""매뉴얼 문서 유스케이스 — 업로드/조회/삭제/재수집 (이벤트 발행 포함)."""

import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from fastapi import UploadFile
from pymilvus import MilvusClient

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.domain.document import DocumentEntity, DocumentStatus
from app.domain.ingestion_job import IngestionJob, JobAction, JobType
from app.infrastructure.kafka import TOPIC_INGEST_JOBS, ingest_event, publish
from app.infrastructure.milvus import query_manual_chunks
from app.infrastructure.storage import FileStorage
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository

logger = logging.getLogger(__name__)

ALLOWED_MIME = {"application/pdf", "application/x-pdf", "application/octet-stream"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        job_repo: IngestionJobRepository,
        producer: AIOKafkaProducer,
        storage: FileStorage,
        settings: Settings,
        milvus: MilvusClient | None = None,
    ) -> None:
        self._documents = document_repo
        self._jobs = job_repo
        self._producer = producer
        self._storage = storage
        self._settings = settings
        self._milvus = milvus

    async def upload(self, files: list[UploadFile]) -> list[DocumentEntity]:
        """다중 PDF 업로드 → 즉시 유효성 검증 + 파일 저장 + PENDING 문서/작업 생성 + Kafka 발행."""
        entities: list[DocumentEntity] = []
        for upload in files:
            content = await upload.read()
            self._validate(upload, content)
            path = self._storage.save(upload.filename or "file.pdf", content)
            entity = await self._documents.insert(
                DocumentEntity(
                    title=self._title_from(upload.filename or "제목없음"),
                    file_path=path,
                    mime=upload.content_type or "application/pdf",
                    size_bytes=len(content),
                )
            )
            await self._dispatch(entity.id, JobType.MANUAL, JobAction.UPSERT)
            entities.append(entity)
            logger.info("문서 업로드", extra={"document_id": entity.id, "title": entity.title})
        return entities

    async def list_documents(
        self, *, status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[DocumentEntity], int]:
        filter_: dict[str, Any] = {}
        if status:
            filter_["status"] = status
        if q:
            filter_["title"] = {"$regex": q, "$options": "i"}
        skip = (page - 1) * page_size
        items = await self._documents.find_all(
            filter_, skip=skip, limit=page_size, sort=[("created_at", -1)]
        )
        total = await self._documents.count(filter_)
        return items, total

    async def get_document(self, document_id: str) -> tuple[DocumentEntity, list[IngestionJob]]:
        """상세 + 최근 작업 이력."""
        entity = await self._documents.find_by_id_or_fail(document_id)
        jobs = await self._jobs.find_all(
            {"document_id": _oid(document_id)}, limit=5, sort=[("created_at", -1)]
        )
        return entity, jobs

    async def get_file(self, document_id: str) -> DocumentEntity:
        """원본 파일 조회용 (뷰어)."""
        return await self._documents.find_by_id_or_fail(document_id)

    async def get_chunks(self, document_id: str) -> tuple[DocumentEntity, list[dict[str, Any]]]:
        """문서 청크 목록 조회 (Milvus 적재 데이터)."""
        entity = await self._documents.find_by_id_or_fail(document_id)
        if self._milvus is None:
            return entity, []
        try:
            chunks = query_manual_chunks(self._milvus, f'doc_id == "{document_id}"')
            chunks.sort(key=lambda c: c.get("seq", 0))
            return entity, chunks
        except Exception as exc:
            logger.warning(
                "Milvus 청크 조회 실패", extra={"document_id": document_id, "error": str(exc)}
            )
            return entity, []

    async def delete_document(self, document_id: str) -> None:
        """원본 파일 + Mongo 문서 즉시 삭제 → Milvus 청크는 이벤트로 비동기 정리."""
        entity = await self._documents.find_by_id_or_fail(document_id)
        self._storage.delete(entity.file_path)
        await self._documents.delete_by_id(document_id)
        await self._dispatch(document_id, JobType.MANUAL, JobAction.DELETE)

    async def reingest(self, document_id: str) -> DocumentEntity:
        """재수집 — 상태 초기화 후 이벤트 재발행."""
        entity = await self._documents.find_by_id_or_fail(document_id)
        entity = await self._documents.update_by_id(
            document_id,
            {"status": DocumentStatus.PENDING.value, "error": None},
        )
        await self._dispatch(document_id, JobType.MANUAL, JobAction.UPSERT)
        return entity

    # ── 내부 ──

    async def _dispatch(self, document_id: str, type_: JobType, action: JobAction) -> None:
        """작업 레코드 생성 + Kafka 이벤트 발행."""
        job = await self._jobs.insert(
            IngestionJob(document_id=document_id, type=type_, action=action)
        )
        await publish(
            self._producer,
            TOPIC_INGEST_JOBS,
            ingest_event(
                {
                    "job_id": job.id,
                    "document_id": document_id,
                    "doc_type": type_.value,
                    "action": action.value,
                }
            ),
        )

    @staticmethod
    def _validate(upload: UploadFile, content: bytes) -> None:
        filename = upload.filename or "file.pdf"
        # 1. 파일명/확장자 검증
        if not filename.lower().endswith(".pdf"):
            raise ValidationAppError(f"PDF 파일(.pdf)만 업로드할 수 있습니다: {filename}")

        # 2. 파일 크기 검증 (0바이트 및 초과)
        if len(content) == 0:
            raise ValidationAppError(f"빈 파일(0 byte)은 업로드할 수 없습니다: {filename}")
        if len(content) > MAX_UPLOAD_BYTES:
            size_mb = len(content) / (1024 * 1024)
            raise ValidationAppError(
                f"파일이 너무 큽니다 (최대 50MB, 현재 {size_mb:.1f}MB): {filename}"
            )

        # 3. PDF 매직 바이트 (%PDF) 검증
        if not content.startswith(b"%PDF"):
            raise ValidationAppError(f"유효한 PDF 파일 형식이 아닙니다 (헤더 불일치): {filename}")

        # 4. PyMuPDF 열람 및 무결성 검증
        try:
            import pymupdf

            doc = pymupdf.open(stream=content, filetype="pdf")
            if doc.is_encrypted:
                doc.close()
                raise ValidationAppError(f"암호로 보호된 PDF는 업로드할 수 없습니다: {filename}")
            if doc.page_count <= 0:
                doc.close()
                raise ValidationAppError(f"페이지가 없는 빈 PDF 파일입니다: {filename}")
            doc.close()
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(
                f"손상되었거나 열 수 없는 PDF 파일입니다: {filename} ({exc})"
            ) from exc

    @staticmethod
    def _title_from(filename: str) -> str:
        """파일명 → 제목 (확장자 제거, 밑줄→공백)."""
        stem = filename.rsplit(".", 1)[0]
        return stem.replace("_", " ").strip()


def _oid(id_str: str):
    from bson import ObjectId

    return ObjectId(id_str)
