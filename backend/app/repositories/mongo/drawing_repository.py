"""설계도면 저장소."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.drawing import DrawingEntity
from app.repositories.mongo.base import MongoRepository


class DrawingRepository(MongoRepository[DrawingEntity]):
    collection_name = "drawings"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    def _to_entity(self, doc: dict) -> DrawingEntity:
        return DrawingEntity.from_doc(doc)
