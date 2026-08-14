"""지식그래프 API — overview/impact/reseed + 노드·엣지 CRUD."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_graph_repository
from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.repositories.neo4j.graph_repository import (
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    GraphRepository,
)

router = APIRouter(prefix="/graph", tags=["graph"])


class NodeIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(description=f"{'/'.join(sorted(ALLOWED_LABELS))} 중 하나")
    name: str = Field(min_length=1, max_length=128)
    props: dict[str, str] = Field(default_factory=dict)


class EdgeIn(BaseModel):
    source: str
    target: str
    type: str = Field(description=f"{'/'.join(sorted(ALLOWED_REL_TYPES))} 중 하나")
    props: dict[str, str] = Field(default_factory=dict)


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


# ── CRUD (사용자 편집) ──


@router.post("/nodes")
async def upsert_node(
    body: NodeIn, repo: Annotated[GraphRepository, Depends(get_graph_repository)]
) -> dict:
    try:
        return await repo.upsert_node(body.id, body.label, body.name, body.props)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node(
    node_id: str, repo: Annotated[GraphRepository, Depends(get_graph_repository)]
) -> None:
    await repo.delete_node(node_id)


@router.post("/edges")
async def upsert_edge(
    body: EdgeIn, repo: Annotated[GraphRepository, Depends(get_graph_repository)]
) -> dict:
    try:
        return await repo.upsert_edge(body.source, body.target, body.type, body.props)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.delete("/edges", status_code=204)
async def delete_edge(
    repo: Annotated[GraphRepository, Depends(get_graph_repository)],
    source: str = Query(...),
    target: str = Query(...),
    type: str = Query(...),
) -> None:
    try:
        await repo.delete_edge(source, target, type)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
