"""수집 작업 저장소."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.ingestion_job import IngestionJob
from app.repositories.mongo.base import MongoRepository


class IngestionJobRepository(MongoRepository[IngestionJob]):
    collection_name = "ingestion_jobs"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    def _to_entity(self, doc: dict) -> IngestionJob:
        return IngestionJob.from_doc(doc)
