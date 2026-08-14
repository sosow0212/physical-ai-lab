"""수집 파이프라인 작업 API — 목록/상태 조회."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_ingestion_job_repository
from app.repositories.mongo.ingestion_job_repository import IngestionJobRepository
from app.schemas.common import PageOut
from app.schemas.document import JobOut

router = APIRouter(prefix="/pipeline/jobs", tags=["pipeline"])


@router.get("")
async def list_jobs(
    repo: Annotated[IngestionJobRepository, Depends(get_ingestion_job_repository)],
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageOut:
    filter_ = {"status": status} if status else {}
    items = await repo.find_all(
        filter_, skip=(page - 1) * page_size, limit=page_size, sort=[("created_at", -1)]
    )
    total = await repo.count(filter_)
    return PageOut(
        items=[JobOut.from_entity(j) for j in items], total=total, page=page, page_size=page_size
    )
