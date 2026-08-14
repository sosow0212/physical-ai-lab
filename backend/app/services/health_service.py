"""헬스 서비스 — 컴포넌트별 상태를 수집해 종합 판정한다.

각 체크는 독립적으로 실패해도 전체를 죽이지 않는다 (부분 장애 가시성).
liveness 관점에서 HTTP 200을 유지하고, 상태 값으로 degraded 를 알린다.
"""

import logging
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CHECK_TIMEOUT = 3.0


async def check_mongo(client: AsyncIOMotorClient | None) -> dict[str, Any]:
    if client is None:
        return {"status": "skipped"}
    try:
        await client.admin.command("ping")  # 타임아웃은 클라이언트 생성 시 지정됨
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("mongo 헬스체크 실패: %s", exc)
        return {"status": "down", "detail": str(exc)[:200]}


async def check_redis(client: Redis | None) -> dict[str, Any]:
    if client is None:
        return {"status": "skipped"}
    try:
        if await client.ping():
            return {"status": "ok"}
        return {"status": "down"}
    except Exception as exc:
        logger.warning("redis 헬스체크 실패: %s", exc)
        return {"status": "down", "detail": str(exc)[:200]}


async def check_embedding_service() -> dict[str, Any]:
    """Ollama(로컬 임베딩 서비스) 가용성 — /api/tags 로 모델 목록 확인."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT) as http:
            resp = await http.get(f"{settings.embedding_base_url}/api/tags")
        models = [m["name"] for m in resp.json().get("models", [])]
        has_model = any(settings.embedding_model in name for name in models)
        return {
            "status": "ok" if has_model else "degraded",
            "model": settings.embedding_model,
            "model_loaded": has_model,
        }
    except Exception as exc:
        logger.warning("embedding 헬스체크 실패: %s", exc)
        return {"status": "down", "detail": str(exc)[:200]}


async def collect_health(
    mongo_client: AsyncIOMotorClient | None,
    redis_client: Redis | None,
) -> dict[str, Any]:
    """전체 컴포넌트 상태 수집. (Neo4j/Milvus/Kafka 체크는 각 Phase에서 추가)"""
    settings = get_settings()
    components = {
        "mongo": await check_mongo(mongo_client),
        "redis": await check_redis(redis_client),
        "embedding": await check_embedding_service(),
    }
    all_ok = all(c.get("status") == "ok" for c in components.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "app_env": settings.app_env,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key_configured": bool(settings.llm_api_key),
        },
        "components": components,
    }
