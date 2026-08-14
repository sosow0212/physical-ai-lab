"""v1 API 라우터 조립 — 기능 추가 시 여기서 include."""

from fastapi import APIRouter

from app.api.v1.routes import chat, documents, drawings, graph, health, pipeline

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(drawings.router)
api_router.include_router(pipeline.router)
api_router.include_router(chat.router)
api_router.include_router(graph.router)
