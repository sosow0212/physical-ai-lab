"""도면 수집 파이프라인 — 메타데이터 텍스트 임베딩 → drawing_cards 적재."""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.domain.drawing import DrawingStatus
from app.domain.ingestion_job import JobStatus
from app.infrastructure.milvus import delete_drawing_cards
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.services.embedding_service import embed_texts

logger = logging.getLogger(__name__)


class DrawingPipeline:
    def __init__(
        self, db: AsyncIOMotorDatabase, milvus: MilvusClient, redis: Redis, settings: Settings
    ) -> None:
        self._drawings = DrawingRepository(db)
        self._jobs = IngestionJobRepository(db)
        self._milvus = milvus
        self._redis = redis
        self._settings = settings

    async def upsert(self, drawing_id: str, job_id: str) -> None:
        await self._jobs.update_by_id(job_id, {"status": JobStatus.RUNNING.value})
        drawing = await self._drawings.find_by_id_or_fail(drawing_id)
        await self._drawings.update_by_id(drawing_id, {"status": DrawingStatus.PROCESSING.value})

        # 검색용 텍스트 = 제목 + 도면번호 + 설비/라인 + 설명
        text = " | ".join(
            str(part)
            for part in [
                drawing.title,
                drawing.drawing_no,
                f"설비 {drawing.equipment}" if drawing.equipment else None,
                f"라인 {drawing.line}" if drawing.line else None,
                drawing.description,
            ]
            if part
        )
        vector = (await embed_texts([text], redis_client=self._redis, settings=self._settings))[0]

        delete_drawing_cards(self._milvus, drawing_id)
        self._milvus.insert(
            collection_name="drawing_cards",
            data=[
                {
                    "drawing_id": drawing_id,
                    "title": drawing.title[:256],
                    "description": (drawing.description or "")[:2048],
                    "equipment": (drawing.equipment or "")[:64],
                    "revision": drawing.revision,
                    "embedding": vector,
                }
            ],
        )
        await self._drawings.update_by_id(
            drawing_id, {"status": DrawingStatus.DONE.value, "error": None}
        )
        await self._jobs.update_by_id(job_id, {"status": JobStatus.DONE.value})
        logger.info("도면 수집 완료", extra={"drawing_id": drawing_id, "rev": drawing.revision})

    async def delete(self, drawing_id: str, job_id: str) -> None:
        await self._jobs.update_by_id(job_id, {"status": JobStatus.RUNNING.value})
        delete_drawing_cards(self._milvus, drawing_id)
        await self._jobs.update_by_id(job_id, {"status": JobStatus.DONE.value})
        logger.info("도면 삭제 완료", extra={"drawing_id": drawing_id})

    async def fail(self, job_id: str, drawing_id: str, error: str, *, dead: bool) -> None:
        await self._jobs.update_by_id(
            job_id,
            {
                "status": (JobStatus.DEAD if dead else JobStatus.FAILED).value,
                "last_error": error[:500],
            },
        )
        try:
            await self._drawings.update_by_id(
                drawing_id, {"status": DrawingStatus.FAILED.value, "error": error[:500]}
            )
        except Exception:
            logger.warning("실패 상태 반영 불가 (도면 없음)", extra={"drawing_id": drawing_id})
