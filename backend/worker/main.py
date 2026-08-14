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
from typing import Any

from aiokafka import AIOKafkaConsumer
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.kafka import TOPIC_INGEST_DLQ, TOPIC_INGEST_JOBS, create_producer, publish
from app.infrastructure.milvus import create_milvus_client, ensure_manual_chunks
from app.infrastructure.mongo import create_mongo_client
from app.infrastructure.redis import create_redis
from worker.pipelines.manual_pipeline import ManualPipeline

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [5, 15, 45]


async def process_event(event: dict[str, Any], pipeline: ManualPipeline) -> None:
    """이벤트 라우팅 — 현재는 manual 타입만 존재 (drawing은 Phase 5)."""
    payload = event["payload"]
    if payload["doc_type"] != "manual":
        logger.warning("알 수 없는 작업 타입 — 스킵", extra={"doc_type": payload["doc_type"]})
        return
    if payload["action"] == "delete":
        await pipeline.delete(payload["document_id"], payload["job_id"])
    else:
        await pipeline.upsert(payload["document_id"], payload["job_id"])


async def main() -> None:
    settings = get_settings()
    setup_logging(settings)

    mongo_client = create_mongo_client(settings)
    db = mongo_client.get_default_database()
    redis: Redis = create_redis(settings)
    milvus: MilvusClient = create_milvus_client(settings)
    ensure_manual_chunks(milvus, settings.embedding_dim)
    pipeline = ManualPipeline(db, milvus, redis, settings)

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
                    await handle_with_retry(record.value, pipeline, producer)
                    await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        await redis.aclose()
        milvus.close()
        mongo_client.close()
        logger.info("워커 종료")


async def handle_with_retry(event: dict[str, Any], pipeline: ManualPipeline, producer: Any) -> None:
    """재시도 정책 적용 처리 — 소진 시 DLQ 발행."""
    payload = event["payload"]
    job_id, document_id = payload["job_id"], payload["document_id"]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await process_event(event, pipeline)
            return
        except Exception as exc:
            logger.warning(
                "작업 실패 (재시도 예정)",
                extra={"job_id": job_id, "attempt": attempt, "error": str(exc)[:200]},
            )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    error_text = f"{MAX_ATTEMPTS}회 재시도 소진"
    await pipeline.fail(job_id, document_id, error_text, dead=True)
    await publish(producer, TOPIC_INGEST_DLQ, {**event, "type": "ingest.document.dead"})
    logger.error("작업 DEAD → DLQ", extra={"job_id": job_id, "document_id": document_id})


if __name__ == "__main__":
    asyncio.run(main())
