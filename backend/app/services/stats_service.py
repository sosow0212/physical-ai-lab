"""대시보드 통계 서비스 — 문서/도면/작업/그래프/채팅 요약."""

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.mongo.chat_repository import ChatMessageRepository, ChatSessionRepository
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.repositories.neo4j.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


class StatsService:
    def __init__(self, db: AsyncIOMotorDatabase, graph_repo: GraphRepository) -> None:
        self._documents = DocumentRepository(db)
        self._drawings = DrawingRepository(db)
        self._jobs = IngestionJobRepository(db)
        self._sessions = ChatSessionRepository(db)
        self._messages = ChatMessageRepository(db)
        self._graph = graph_repo

    async def collect(self) -> dict[str, Any]:
        """대시보드용 요약 지표 수집."""
        docs = await self._documents.find_all({}, limit=1000)
        drawings = await self._drawings.find_all({}, limit=1000)
        recent_jobs = await self._jobs.find_all({}, limit=10, sort=[("created_at", -1)])
        sessions = await self._sessions.count({})
        recent_questions = await self._messages.find_all(
            {"role": "user"}, limit=5, sort=[("created_at", -1)]
        )

        graph: dict[str, int] = {"nodes": 0, "links": 0}
        try:
            overview = await self._graph.overview()
            graph = {"nodes": len(overview["nodes"]), "links": len(overview["links"])}
        except Exception as exc:
            logger.warning("그래프 통계 수집 실패", extra={"error": str(exc)[:150]})

        return {
            "documents": {
                "total": len(docs),
                "done": sum(1 for d in docs if d.status.value == "DONE"),
                "failed": sum(1 for d in docs if d.status.value == "FAILED"),
                "chunks": sum(d.chunk_count or 0 for d in docs),
            },
            "drawings": {
                "total": len(drawings),
                "done": sum(1 for d in drawings if d.status.value == "DONE"),
            },
            "jobs": {
                "active": sum(1 for j in recent_jobs if j.status.value in {"PENDING", "RUNNING"}),
                "dead": sum(1 for j in recent_jobs if j.status.value == "DEAD"),
                "recent": [
                    {
                        "id": j.id,
                        "type": j.type.value,
                        "action": j.action.value,
                        "status": j.status.value,
                        "created_at": j.created_at,
                    }
                    for j in recent_jobs[:6]
                ],
            },
            "graph": graph,
            "chat": {
                "sessions": sessions,
                "recent_questions": [
                    {"id": m.id, "content": m.content, "created_at": m.created_at}
                    for m in recent_questions
                ],
            },
        }
