"""수집 워커 진입점 — Kafka consumer 루프 + 재시도/DLQ.

설계(WORDPLAN §4.6):
  - ingest.jobs 소비 → manual/drawing 파이프라인 라우팅
  - 처리 실패 시 로컬 재시도 3회 (백오프 5s/15s/45s)
  - 소진 시 ingest.jobs.dlq 발행 + 작업 DEAD 표시
"""

import asyncio
import json
import logging
import signal
from typing import Any, Protocol

from aiokafka import AIOKafkaConsumer
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.kafka import TOPIC_INGEST_DLQ, TOPIC_INGEST_JOBS, create_producer, publish
from app.infrastructure.milvus import (
    create_milvus_client,
    ensure_drawing_cards,
    ensure_manual_chunks,
)
from app.infrastructure.mongo import create_mongo_client
from app.infrastructure.neo4j import create_neo4j_driver
from app.infrastructure.redis import create_redis
from worker.pipelines.drawing_pipeline import DrawingPipeline
from worker.pipelines.manual_pipeline import ManualPipeline

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [5, 15, 45]


class Pipeline(Protocol):
    """워커가 사용하는 파이프라인 공통 인터페이스."""

    async def upsert(self, document_id: str, job_id: str) -> None: ...
    async def delete(self, document_id: str, job_id: str) -> None: ...
    async def fail(self, job_id: str, document_id: str, error: str, *, dead: bool) -> None: ...


async def main() -> None:
    settings = get_settings()
    setup_logging(settings)

    mongo_client = create_mongo_client(settings)
    db = mongo_client.get_default_database()
    redis: Redis = create_redis(settings)
    milvus: MilvusClient = create_milvus_client(settings)
    ensure_manual_chunks(milvus, settings.embedding_dim)
    ensure_drawing_cards(milvus, settings.embedding_dim)
    neo4j_driver = create_neo4j_driver(settings)

    pipelines: dict[str, Pipeline] = {
        "manual": ManualPipeline(db, milvus, redis, settings, neo4j_driver=neo4j_driver),
        "drawing": DrawingPipeline(db, milvus, redis, settings),
    }

    consumer = AIOKafkaConsumer(
        TOPIC_INGEST_JOBS,
        bootstrap_servers=settings.kafka_bootstrap,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    producer = await create_producer(settings)
    await consumer.start()
    logger.info("워커 시작", extra={"topic": TOPIC_INGEST_JOBS, "group": settings.kafka_group_id})

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=5)
            if not batch:
                continue
            for _topic, records in batch.items():
                for record in records:
                    await handle_with_retry(record.value, pipelines, producer)
                    await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        await neo4j_driver.close()
        await redis.aclose()
        milvus.close()
        mongo_client.close()
        logger.info("워커 종료")


NON_RETRYABLE_EXCEPTIONS = (
    ValueError,
    FileNotFoundError,
    KeyError,
    TypeError,
)


def is_non_retryable(exc: Exception) -> bool:
    """재시도해도 성공할 수 없는 영구적 오류 판별."""
    if isinstance(exc, NON_RETRYABLE_EXCEPTIONS):
        return True
    exc_name = type(exc).__name__
    return "FileDataError" in exc_name or "PdfError" in exc_name


async def handle_with_retry(
    event: dict[str, Any], pipelines: dict[str, Pipeline], producer: Any
) -> None:
    """doc_type 으로 파이프라인 선택 → 실행/재시도 → 치명적 오류 즉시 실패 or 소진 시 DLQ."""
    payload = event["payload"]
    job_id, document_id = payload["job_id"], payload["document_id"]
    pipeline = pipelines.get(payload.get("doc_type", ""))
    if pipeline is None:
        logger.warning("알 수 없는 작업 타입 — 스킵", extra={"doc_type": payload.get("doc_type")})
        return

    last_error_msg = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if payload["action"] == "delete":
                await pipeline.delete(document_id, job_id)
            else:
                await pipeline.upsert(document_id, job_id)
            return
        except Exception as exc:
            last_error_msg = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "작업 실패",
                extra={"job_id": job_id, "attempt": attempt, "error": last_error_msg[:300]},
            )

            # 영구적 오류(텍스트 미추출, 파일 없음, 잘못된 형식 등)는 즉시 종료
            if is_non_retryable(exc):
                error_text = f"수집 실패: {exc}"
                await pipeline.fail(job_id, document_id, error_text, dead=True)
                await publish(
                    producer,
                    TOPIC_INGEST_DLQ,
                    {**event, "type": "ingest.document.dead", "error": error_text},
                )
                logger.error(
                    "치명적 수집 오류 → 즉시 DLQ", extra={"job_id": job_id, "error": error_text}
                )
                return

            # 일시적 오류인 경우 중간 상태 기록
            if attempt < MAX_ATTEMPTS:
                await pipeline.fail(
                    job_id,
                    document_id,
                    f"수집 재시도 중 ({attempt}/{MAX_ATTEMPTS}): {last_error_msg[:200]}",
                    dead=False,
                )
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    error_text = f"{MAX_ATTEMPTS}회 재시도 실패: {last_error_msg}"
    await pipeline.fail(job_id, document_id, error_text, dead=True)
    await publish(
        producer, TOPIC_INGEST_DLQ, {**event, "type": "ingest.document.dead", "error": error_text}
    )
    logger.error(
        "작업 DEAD → DLQ", extra={"job_id": job_id, "document_id": document_id, "error": error_text}
    )


if __name__ == "__main__":
    asyncio.run(main())
