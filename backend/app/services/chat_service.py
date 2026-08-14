"""채팅 서비스 — RAG 오케스트레이션 + SSE 이벤트 스트림 생성.

SSE 이벤트 규격 (WORKPLAN §4.8): sources → (graph) → token... → done / error
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from neo4j import AsyncDriver
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.domain.chat import ChatMessage, ChatSession, ChatSource, MessageRole
from app.repositories.mongo.chat_repository import ChatMessageRepository, ChatSessionRepository
from app.services.impact_service import ImpactService
from app.services.llm_service import stream_chat
from app.services.retriever_service import RetrieverService

logger = logging.getLogger(__name__)

HISTORY_TURNS = 6  # 프롬프트에 포함할 최근 턴 수

SYSTEM_PROMPT = """너는 스마트공장 파일럿 라인(LINE-1, 사출성형)의 공정 엔지니어링 어시스턴트다.

규칙:
- 반드시 [참고자료]와 [영향분석]에 근거하여 답한다. 근거가 없으면 솔직히 없다고 말한다.
- 답변 구조: ① 요약 ② 근거(문서명/페이지 인용) ③ 필요 시 조치 절차(번호 단계) ④ 주의사항.
- 안전 관련(비상정지, 과열, 화재) 항목은 최우선으로 강조한다.
- 영향범위 질문에는 상류/하류 설비를 구분해 정리하고 근거 관계를 밝힌다.
- 매뉴얼에 없는 일반 지식으로 답하지 않는다."""


class ChatService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        milvus: MilvusClient,
        redis: Redis,
        neo4j_driver: AsyncDriver,
        settings: Settings,
    ) -> None:
        self._sessions = ChatSessionRepository(db)
        self._messages = ChatMessageRepository(db)
        self._settings = settings
        self._retriever = RetrieverService(milvus, redis, _document_repo(db), settings)
        self._impact = ImpactService(_graph_repo(neo4j_driver))

    # ── 세션 관리 ──
    async def create_session(self) -> ChatSession:
        return await self._sessions.insert(ChatSession())

    async def list_sessions(self) -> list[ChatSession]:
        return await self._sessions.find_all({}, limit=50, sort=[("updated_at", -1)])

    async def delete_session(self, session_id: str) -> None:
        await self._sessions.find_by_id_or_fail(session_id)
        await self._messages.delete_by_session(session_id)
        await self._sessions.delete_by_id(session_id)

    async def get_messages(self, session_id: str) -> list[ChatMessage]:
        await self._sessions.find_by_id_or_fail(session_id)
        return await self._messages.find_by_session(session_id, limit=200)

    # ── 질의 응답 ──
    async def ask_stream(self, session_id: str, question: str) -> AsyncIterator[dict[str, Any]]:
        """RAG 질의 → SSE 이벤트 dict yield ({event, data})."""
        started = time.monotonic()
        await self._sessions.find_by_id_or_fail(session_id)
        question = question.strip()
        if not question:
            return

        # 1) 검색 → 출처 이벤트
        retrieval = await self._retriever.retrieve(question)
        yield {"event": "sources", "data": {"sources": retrieval.sources}}

        # 2) 영향범위 분석 (설비/키워드 감지 시) → graph 이벤트
        impact = None
        try:
            impact = await self._impact.analyze(question)
        except Exception as exc:  # 그래프 장애가 채팅을 막지 않도록 격리
            logger.warning("영향분석 실패(무시)", extra={"error": str(exc)[:150]})
        if impact:
            yield {
                "event": "graph",
                "data": {
                    "root": impact["root"],
                    "nodes": [i["impacted"] for i in impact["items"]],
                    "items": impact["items"],
                },
            }

        # 3) 프롬프트 조립 + 사용자 메시지 저장
        history = await self._recent_history(session_id)
        user_message = await self._messages.insert(
            ChatMessage(session_id=session_id, role=MessageRole.USER, content=question)
        )
        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {
                "role": "user",
                "content": self._user_prompt(
                    question, retrieval.context_block, impact and self._impact.to_context(impact)
                ),
            },
        ]

        # 4) LLM 스트리밍 → token 이벤트
        answer_parts: list[str] = []
        try:
            async for delta in stream_chat(llm_messages, settings=self._settings):
                answer_parts.append(delta)
                yield {"event": "token", "data": {"delta": delta}}
        except Exception as exc:
            logger.error(
                "LLM 스트리밍 실패", extra={"session_id": session_id, "error": str(exc)[:200]}
            )
            yield {"event": "error", "data": {"code": "LLM_ERROR", "message": str(exc)[:200]}}
            return

        # 5) 어시스턴트 메시지 저장 + 세션 갱신 + done 이벤트
        sources = [ChatSource(**s) for s in retrieval.sources]
        impact_payload = None
        if impact:
            impact_payload = {
                "root": impact["root"],
                "nodes": [i["impacted"] for i in impact["items"]],
            }
        assistant = await self._messages.insert(
            ChatMessage(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="".join(answer_parts),
                sources=sources,
                impact=impact_payload,
            )
        )
        title = question[:24] + ("…" if len(question) > 24 else "")
        await self._sessions.update_by_id(session_id, {"title": title})
        yield {
            "event": "done",
            "data": {
                "message_id": assistant.id,
                "user_message_id": user_message.id,
                "latency_ms": int((time.monotonic() - started) * 1000),
            },
        }

    # ── 내부 ──
    async def _recent_history(self, session_id: str) -> list[dict[str, str]]:
        messages = await self._messages.find_by_session(session_id, limit=HISTORY_TURNS)
        return [{"role": m.role.value, "content": m.content} for m in messages]

    @staticmethod
    def _user_prompt(question: str, context_block: str, impact_block: str | None = None) -> str:
        context = context_block or "(참고자료 없음 — 근거가 없다고 답할 것)"
        impact = f"[영향분석]\n{impact_block}" if impact_block else "[영향분석]\n(해당 없음)"
        return f"""{impact}

[참고자료]
{context}

[질문]
{question}"""


def _document_repo(db: AsyncIOMotorDatabase):
    from app.repositories.mongo.document_repository import DocumentRepository

    return DocumentRepository(db)


def _graph_repo(driver: AsyncDriver):
    from app.repositories.neo4j.graph_repository import GraphRepository

    return GraphRepository(driver)
