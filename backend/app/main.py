"""PAL API 애플리케이션 엔트리포인트 (앱 팩토리 패턴)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routes.health import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    """FastAPI 인스턴스를 조립한다. (Spring의 @SpringBootApplication 역할)"""
    settings = get_settings()

    app = FastAPI(
        title="Physical AI Lab API",
        version="0.1.0",
        description="공정 매뉴얼·설계도면 기반 RAG 챗봇 (학습용)",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if settings.is_dev else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    # 도커 헬스체크용 루트 별칭 (정식 엔드포인트는 /api/v1/health)
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)

    return app


app = create_app()
