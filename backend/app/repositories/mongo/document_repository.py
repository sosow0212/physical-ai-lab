"""매뉴얼 문서 저장소."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.document import DocumentEntity
from app.repositories.mongo.base import MongoRepository


class DocumentRepository(MongoRepository[DocumentEntity]):
    collection_name = "documents"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    def _to_entity(self, doc: dict) -> DocumentEntity:
        return DocumentEntity.from_doc(doc)
