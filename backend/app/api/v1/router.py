"""v1 API 라우터 조립 — 기능 추가 시 여기서 include."""
from fastapi import APIRouter

from app.api.v1.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
