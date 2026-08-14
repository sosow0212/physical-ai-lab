"""채팅 도메인."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatSource:
    """어시스턴트 답변에 인용된 출처(매뉴얼 청크 또는 도면)."""

    type: str  # manual | drawing
    doc_id: str
    title: str
    page: int | None = None
    score: float | None = None


@dataclass
class ChatSession:
    """대화 세션 (chat_sessions 컬렉션)."""

    title: str = "새 대화"
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_doc(self) -> dict:
        doc = {"title": self.title, "created_at": self.created_at, "updated_at": self.updated_at}
        if self.id is not None:
            from bson import ObjectId

            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_doc(cls, doc: dict) -> "ChatSession":
        session = cls(
            title=doc.get("title", "새 대화"),
            created_at=doc.get("created_at", datetime.now(UTC)),
            updated_at=doc.get("updated_at", datetime.now(UTC)),
        )
        session.id = str(doc["_id"])
        return session


@dataclass
class ChatMessage:
    """대화 메시지 1건 (chat_messages 컬렉션)."""

    session_id: str
    role: MessageRole
    content: str
    sources: list[ChatSource] = field(default_factory=list)
    impact: dict[str, Any] | None = None  # 영향범위 분석 결과 (Phase 4)
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_doc(self) -> dict:
        doc = {
            "session_id": _to_oid(self.session_id),
            "role": self.role.value,
            "content": self.content,
            "sources": [vars(s) for s in self.sources],
            "impact": self.impact,
            "created_at": self.created_at,
        }
        if self.id is not None:
            from bson import ObjectId

            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_doc(cls, doc: dict) -> "ChatMessage":
        message = cls(
            session_id=str(doc["session_id"]),
            role=MessageRole(doc["role"]),
            content=doc["content"],
            sources=[ChatSource(**s) for s in doc.get("sources", [])],
            impact=doc.get("impact"),
            created_at=doc.get("created_at", datetime.now(UTC)),
        )
        message.id = str(doc["_id"])
        return message


def _to_oid(id_str: str):
    from bson import ObjectId

    return ObjectId(id_str)
