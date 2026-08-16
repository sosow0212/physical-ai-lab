"""의존성 주입 프로바이더 — Spring의 @Autowired/생성자 주입에 대응.

요청마다 app.state 의 클라이언트에서 저장소를 만들어 service 로 전달한다.
저장소 생성은 가볍다(컬렉션 래퍼) — 싱글턴 캐시 대신 명시적 팩토리가 FastAPI 표준 스타일.
"""

from fastapi import Request

from app.core.config import Settings, get_settings
from app.infrastructure.storage import FileStorage
from app.repositories.mongo.chat_repository import ChatMessageRepository, ChatSessionRepository
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.repositories.neo4j.graph_repository import GraphRepository
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.drawing_service import DrawingService
from app.services.stats_service import StatsService


def get_mongo_db(request: Request):
    """lifespan이 만들어 둔 Mongo DB 핸들 반환."""
    return request.app.state.mongo_db


def get_settings_dep() -> Settings:
    return get_settings()


# ── 저장소 프로바이더 ──
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


# ── 서비스 프로바이더 ──
def get_document_service(request: Request) -> DocumentService:
    return DocumentService(
        document_repo=get_document_repository(request),
        job_repo=get_ingestion_job_repository(request),
        producer=request.app.state.kafka_producer,
        storage=FileStorage(get_settings()),
        settings=get_settings(),
        milvus=getattr(request.app.state, "milvus", None),
    )


def get_chat_service(request: Request) -> ChatService:
    return ChatService(
        db=request.app.state.mongo_db,
        milvus=request.app.state.milvus,
        redis=request.app.state.redis,
        neo4j_driver=request.app.state.neo4j,
        settings=get_settings(),
    )


def get_graph_repository(request: Request) -> GraphRepository:
    return GraphRepository(request.app.state.neo4j)


def get_drawing_service(request: Request) -> DrawingService:
    return DrawingService(
        drawing_repo=get_drawing_repository(request),
        job_repo=get_ingestion_job_repository(request),
        producer=request.app.state.kafka_producer,
        storage=FileStorage(get_settings()),
        settings=get_settings(),
    )


def get_stats_service(request: Request) -> StatsService:
    return StatsService(
        db=request.app.state.mongo_db,
        graph_repo=GraphRepository(request.app.state.neo4j),
    )


def get_telemetry_generator(request: Request):
    return request.app.state.telemetry_generator


def get_anomaly_detector(request: Request):
    return request.app.state.anomaly_detector
