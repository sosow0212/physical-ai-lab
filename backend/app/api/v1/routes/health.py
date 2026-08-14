"""헬스체크 API — liveness + 컴포넌트 상태."""

from typing import Any

from fastapi import APIRouter, Request

from app.services.health_service import collect_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """컴포넌트 상태 포함 헬스. 일부 다운이어도 200 (degraded 표시).

    liveness만 빠르게 확인하고 싶으면 GET /health/live 를 사용한다.
    """
    mongo_client = getattr(request.app.state, "mongo_client", None)
    redis_client = getattr(request.app.state, "redis", None)
    return await collect_health(mongo_client, redis_client)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """프로세스 생존만 확인 (의존성 체크 없음 — 도커 healthcheck용)."""
    return {"status": "ok"}
