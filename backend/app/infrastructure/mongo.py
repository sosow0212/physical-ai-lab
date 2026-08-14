"""MongoDB(Motor async) 클라이언트 팩토리."""

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import Settings


def create_mongo_client(settings: Settings) -> AsyncIOMotorClient:
    """설정 기반 Motor 클라이언트 생성. DB명은 URI(/pal)에서 가져온다."""
    return AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
