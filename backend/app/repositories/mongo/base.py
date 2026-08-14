"""MongoRepository 제네릭 베이스 — dict CRUD를 담당하고, 엔티티 매핑은 하위 클래스에 위임한다.

Spring Data MongoDB의 MongoRepository 인터페이스와 대응되는 구조:
  - save / findById / findAll(필터+페이징) / deleteById / count
엔티티 ↔ document 변환(_to_entity)만 각 저장소가 구현하면 공통 쿼리를 재사용할 수 있다.
"""

from abc import ABC, abstractmethod
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.errors import NotFoundError


class MongoRepository[T](ABC):
    """컬렉션 단위 저장소 기반 클래스 (PEP 695 제네릭)."""

    #: 하위 클래스가 지정하는 Mongo 컬렉션명
    collection_name: str

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection: AsyncIOMotorCollection = db[self.collection_name]

    @abstractmethod
    def _to_entity(self, doc: dict) -> T:
        """MongoDB document → 도메인 엔티티 변환."""

    async def insert(self, entity: T) -> T:
        """엔티티 저장 후 id가 채워진 엔티티를 반환한다."""
        doc = self._to_doc(entity)
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._to_entity(doc)

    async def find_by_id(self, entity_id: str) -> T | None:
        doc = await self._collection.find_one({"_id": _to_object_id(entity_id)})
        return self._to_entity(doc) if doc else None

    async def find_by_id_or_fail(self, entity_id: str) -> T:
        entity = await self.find_by_id(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.collection_name} id={entity_id} 를 찾을 수 없습니다.")
        return entity

    async def find_all(
        self,
        filter_: dict[str, Any] | None = None,
        *,
        skip: int = 0,
        limit: int = 50,
        sort: list[tuple[str, int]] | None = None,
    ) -> list[T]:
        """필터 + 페이징 목록 조회. sort 예: [("created_at", -1)]."""
        cursor = self._collection.find(filter_ or {}).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return [self._to_entity(doc) async for doc in cursor]

    async def count(self, filter_: dict[str, Any] | None = None) -> int:
        return await self._collection.count_documents(filter_ or {})

    async def update_by_id(self, entity_id: str, update: dict[str, Any]) -> T:
        """부분 업데이트($set) 후 갱신된 엔티티 반환. updated_at은 자동 갱신."""
        from datetime import UTC, datetime

        update = {**update, "updated_at": datetime.now(UTC)}
        doc = await self._collection.find_one_and_update(
            {"_id": _to_object_id(entity_id)},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise NotFoundError(f"{self.collection_name} id={entity_id} 를 찾을 수 없습니다.")
        return self._to_entity(doc)

    async def delete_by_id(self, entity_id: str) -> bool:
        """삭제 성공 시 True. 존재하지 않으면 NotFoundError."""
        result = await self._collection.delete_one({"_id": _to_object_id(entity_id)})
        if result.deleted_count == 0:
            raise NotFoundError(f"{self.collection_name} id={entity_id} 를 찾을 수 없습니다.")
        return True

    @staticmethod
    def _to_doc(entity: T) -> dict:
        """엔티티 → MongoDB document 변환 (기본: 엔티티의 to_doc 사용)."""
        to_doc = getattr(entity, "to_doc", None)
        if to_doc is None:
            raise TypeError(f"{type(entity).__name__} 에 to_doc() 가 없습니다.")
        return to_doc()


def _to_object_id(entity_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        return ObjectId(entity_id)
    except InvalidId as exc:
        raise NotFoundError(f"잘못된 id 형식: {entity_id}") from exc
