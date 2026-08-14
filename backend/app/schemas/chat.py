"""채팅 도메인 DTO."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.domain.chat import ChatMessage, ChatSession


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, s: ChatSession) -> "SessionOut":
        return cls(id=s.id or "", title=s.title, created_at=s.created_at, updated_at=s.updated_at)


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = []
    impact: dict[str, Any] | None = None
    created_at: datetime

    @classmethod
    def from_entity(cls, m: ChatMessage) -> "MessageOut":
        return cls(
            id=m.id or "",
            role=m.role.value,
            content=m.content,
            sources=[vars(s) for s in m.sources],
            impact=m.impact,
            created_at=m.created_at,
        )


class AskIn(BaseModel):
    """채팅 질의 요청."""

    question: str
