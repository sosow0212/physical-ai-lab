"""수집 작업 발행 헬퍼 — document/drawing 서비스가 공유한다."""

from aiokafka import AIOKafkaProducer

from app.domain.ingestion_job import IngestionJob, JobAction, JobType
from app.infrastructure.kafka import TOPIC_INGEST_JOBS, ingest_event, publish
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository


async def dispatch_ingest_job(
    job_repo: IngestionJobRepository,
    producer: AIOKafkaProducer,
    document_id: str,
    type_: JobType,
    action: JobAction,
) -> IngestionJob:
    """작업 레코드 생성 + Kafka 이벤트 발행."""
    job = await job_repo.insert(IngestionJob(document_id=document_id, type=type_, action=action))
    payload = {
        "job_id": job.id,
        "document_id": document_id,
        "doc_type": type_.value,
        "action": action.value,
    }
    await publish(producer, TOPIC_INGEST_JOBS, ingest_event(payload))
    return job
