"""대시보드 통계 API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_stats_service
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats(
    service: Annotated[StatsService, Depends(get_stats_service)],
) -> dict:
    """대시보드 요약 지표."""
    return await service.collect()
