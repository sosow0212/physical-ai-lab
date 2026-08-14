"""지식그래프 API — overview/impact/reseed."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_graph_repository
from app.core.config import get_settings
from app.repositories.neo4j.graph_repository import GraphRepository

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/overview")
async def graph_overview(
    repo: Annotated[GraphRepository, Depends(get_graph_repository)],
) -> dict:
    """전체 노드/엣지 (프론트 force-graph 렌더용)."""
    return await repo.overview()


@router.get("/impact")
async def graph_impact(
    repo: Annotated[GraphRepository, Depends(get_graph_repository)],
    equipment: str = Query(..., description="설비/센서 코드 (예: TCU-100, TS-02)"),
    depth: int = Query(3, ge=1, le=4),
) -> dict:
    """특정 설비의 하류 영향범위."""
    return await repo.impact(equipment, max_depth=depth)


@router.post("/reseed")
async def graph_reseed(
    repo: Annotated[GraphRepository, Depends(get_graph_repository)],
) -> dict:
    """샘플 그래프 재적재 (개발 환경 전용)."""
    if not get_settings().is_dev:
        raise HTTPException(status_code=403, detail="운영 환경에서는 사용할 수 없습니다")
    return await repo.reseed()
