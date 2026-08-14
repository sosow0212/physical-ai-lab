"""의존성 주입 프로바이더 — Spring의 @Autowired/생성자 주입에 대응.

요청마다 app.state 의 클라이언트에서 저장소를 만들어 service 로 전달한다.
저장소 생성은 가볍다(컬렉션 래퍼) — 싱글턴 캐시 대신 명시적 팩토리가 FastAPI 표준 스타일.
"""

from fastapi import Request

from app.core.config import Settings, get_settings
from app.repositories.mongo.chat_repository import ChatMessageRepository, ChatSessionRepository
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository


def get_mongo_db(request: Request):
    """lifespan이 만들어 둔 Mongo DB 핸들 반환."""
    return request.app.state.mongo_db


def get_settings_dep() -> Settings:
    return get_settings()


# ── 저장소 프로바이더 (Annotated 로 간단히 주입) ──
def get_document_repository(request: Request) -> DocumentRepository:
    return DocumentRepository(request.app.state.mongo_db)


def get_drawing_repository(request: Request) -> DrawingRepository:
    return DrawingRepository(request.app.state.mongo_db)


def get_chat_session_repository(request: Request) -> ChatSessionRepository:
    return ChatSessionRepository(request.app.state.mongo_db)


def get_chat_message_repository(request: Request) -> ChatMessageRepository:
    return ChatMessageRepository(request.app.state.mongo_db)


def get_ingestion_job_repository(request: Request) -> IngestionJobRepository:
    return IngestionJobRepository(request.app.state.mongo_db)
