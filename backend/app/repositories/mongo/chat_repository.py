"""채팅 세션/메시지 저장소."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.chat import ChatMessage, ChatSession
from app.repositories.mongo.base import MongoRepository


class ChatSessionRepository(MongoRepository[ChatSession]):
    collection_name = "chat_sessions"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    def _to_entity(self, doc: dict) -> ChatSession:
        return ChatSession.from_doc(doc)


class ChatMessageRepository(MongoRepository[ChatMessage]):
    collection_name = "chat_messages"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    def _to_entity(self, doc: dict) -> ChatMessage:
        return ChatMessage.from_doc(doc)

    async def find_by_session(self, session_id: str, *, limit: int = 100) -> list[ChatMessage]:
        """세션의 메시지를 시간순으로 조회."""
        return await self.find_all(
            {"session_id": _to_oid(session_id)},
            limit=limit,
            sort=[("created_at", 1)],
        )

    async def delete_by_session(self, session_id: str) -> int:
        """세션 삭제 시 소속 메시지 일괄 삭제. 삭제 건수 반환."""
        result = await self._collection.delete_many({"session_id": _to_oid(session_id)})
        return result.deleted_count


def _to_oid(session_id: str):
    from bson import ObjectId

    return ObjectId(session_id)
