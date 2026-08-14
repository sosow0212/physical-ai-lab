"""Kafka(Redpanda) 연결 — api는 producer, worker는 consumer를 쓴다."""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import Settings

logger = logging.getLogger(__name__)

TOPIC_INGEST_JOBS = "ingest.jobs"
TOPIC_INGEST_DLQ = "ingest.jobs.dlq"


async def create_producer(settings: Settings) -> AIOKafkaProducer:
    """JSON 직렬화 producer 생성 + 시작 (lifespan/worker에서 관리)."""
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        acks="all",
    )
    await producer.start()
    return producer


async def stop_producer(producer: AIOKafkaProducer) -> None:
    await producer.stop()


def ingest_event(payload: dict[str, Any]) -> dict[str, Any]:
    """수집 작업 이벤트 봉투 — WORKPLAN §4.6 규격."""
    return {
        "event_id": uuid.uuid4().hex,
        "type": "ingest.document.upsert"
        if payload.get("action") == "upsert"
        else "ingest.document.delete",
        "occurred_at": datetime.now(UTC).isoformat(),
        "version": 1,
        "payload": payload,
    }


async def publish(producer: AIOKafkaProducer, topic: str, event: dict[str, Any]) -> None:
    """이벤트 발행 (동일 key로 파티셔닝되면 document_id 순서 보장)."""
    key = str(event["payload"].get("document_id", event["event_id"]))
    await producer.send_and_wait(topic, event, key=key.encode("utf-8"))
    logger.info(
        "이벤트 발행", extra={"topic": topic, "event_id": event["event_id"], "type": event["type"]}
    )
