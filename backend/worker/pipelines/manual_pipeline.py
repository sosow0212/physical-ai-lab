"""매뉴얼 수집 파이프라인 — 파싱 → 청킹 → 임베딩 → Milvus 적재 → 상태 확정."""

import logging
import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from neo4j import AsyncDriver
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.domain.document import DocumentStatus
from app.domain.ingestion_job import JobStatus
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.repositories.neo4j.graph_repository import GraphRepository
from app.services.embedding_service import embed_texts
from worker.parser.pdf_parser import parse_pdf
from worker.pipelines.chunker import chunk_document

logger = logging.getLogger(__name__)

EQUIPMENT_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9-])[A-Z]{2,4}-\d{2,3}\b"
)  # IH-250 (PAL-OM-001 같은 문서번호 제외)


class ManualPipeline:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        milvus: MilvusClient,
        redis: Redis,
        settings: Settings,
        neo4j_driver: AsyncDriver | None = None,
    ) -> None:
        self._documents = DocumentRepository(db)
        self._jobs = IngestionJobRepository(db)
        self._milvus = milvus
        self._redis = redis
        self._settings = settings
        self._graph = GraphRepository(neo4j_driver) if neo4j_driver else None

    async def upsert(self, document_id: str, job_id: str) -> None:
        """문서 수집 전체 흐름. 실패 시 예외를 던져 재시도/DLQ 대상이 된다."""
        await self._mark(job_id, JobStatus.RUNNING, document_status=DocumentStatus.PROCESSING)

        document = await self._documents.find_by_id_or_fail(document_id)

        # 1) 파싱 + 청킹
        parsed = await parse_pdf(document.file_path)
        chunks = await chunk_document(parsed, self._settings)
        if not chunks:
            raise ValueError("추출된 텍스트가 없습니다 (스캔본/이미지 전용 PDF로 추정)")

        # 2) 임베딩 (Redis 캐시 활용)
        vectors = await embed_texts(
            [c.text for c in chunks], redis_client=self._redis, settings=self._settings
        )

        # 3) Milvus 적재 (재수집 대비 기존 청크 삭제 후 삽입)
        rows: list[dict[str, Any]] = [
            {
                "doc_id": document_id,
                "seq": c.seq,
                "page": c.page,
                "heading": c.heading[:512],
                "text": c.text[:8000],
                "embedding": v,
            }
            for c, v in zip(chunks, vectors, strict=True)
        ]
        self._milvus.delete(collection_name="manual_chunks", filter=f'doc_id == "{document_id}"')
        self._milvus.insert(collection_name="manual_chunks", data=rows)

        # 4) 문서 메타 확정 (설비 코드 자동 태깅)
        full_text = "\n".join(s.text for s in parsed.sections)
        equipment_refs = sorted(set(EQUIPMENT_CODE_RE.findall(full_text)))
        await self._documents.update_by_id(
            document_id,
            {
                "status": DocumentStatus.DONE.value,
                "error": None,
                "page_count": parsed.page_count,
                "chunk_count": len(chunks),
                "equipment_refs": equipment_refs,
            },
        )
        # 지식그래프 출처 연결 (Document -[:DESCRIBES]-> Equipment)
        if self._graph is not None:
            try:
                await self._graph.describe_equipment(document_id, document.title, equipment_refs)
            except Exception as exc:
                logger.warning("DESCRIBES 엣지 실패(무시)", extra={"error": str(exc)[:150]})
        await self._jobs.update_by_id(job_id, {"status": JobStatus.DONE.value})
        logger.info(
            "수집 완료",
            extra={"document_id": document_id, "chunks": len(chunks), "pages": parsed.page_count},
        )

    async def delete(self, document_id: str, job_id: str) -> None:
        """Milvus 청크 정리 (Mongo 문서/파일은 api에서 이미 삭제됨)."""
        await self._mark(job_id, JobStatus.RUNNING)
        self._milvus.delete(collection_name="manual_chunks", filter=f'doc_id == "{document_id}"')
        await self._jobs.update_by_id(job_id, {"status": JobStatus.DONE.value})
        logger.info("문서 삭제 완료", extra={"document_id": document_id})

    async def fail(self, job_id: str, document_id: str, error: str, *, dead: bool) -> None:
        """재시도 소진(DEAD) 또는 재시도 예약(FAILED) 상태 기록."""
        await self._jobs.update_by_id(
            job_id,
            {
                "status": (JobStatus.DEAD if dead else JobStatus.FAILED).value,
                "last_error": error[:500],
            },
        )
        try:
            await self._documents.update_by_id(
                document_id, {"status": DocumentStatus.FAILED.value, "error": error[:500]}
            )
        except Exception:  # 문서가 이미 삭제된 경우 등 — 작업 기록만 유지
            logger.warning("실패 상태 반영 불가 (문서 없음)", extra={"document_id": document_id})

    async def _mark(
        self, job_id: str, job_status: JobStatus, *, document_status: DocumentStatus | None = None
    ) -> None:
        await self._jobs.update_by_id(job_id, {"status": job_status.value})
        if document_status is not None:
            await self._documents.update_by_id(
                (await self._jobs.find_by_id_or_fail(job_id)).document_id,
                {"status": document_status.value},
            )
