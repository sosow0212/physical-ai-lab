"""PAL API 애플리케이션 엔트리포인트 (앱 팩토리 패턴)."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.lifespan import lifespan
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """모든 요청에 요청 ID를 부여하고 접근 로그를 남긴다 (Filter/Interceptor 대응)."""

    async def dispatch(self, request: Request, call_next):
        import uuid

        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response


def create_app() -> FastAPI:
    """FastAPI 인스턴스를 조립한다. (Spring의 @SpringBootApplication 역할)"""
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(
        title="Physical AI Lab API",
        version="0.1.0",
        description="공정 매뉴얼·설계도면 기반 RAG 챗봇 (학습용)",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if settings.is_dev else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 예외 핸들러 등록 (@ControllerAdvice)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(api_router, prefix="/api/v1")

    # 도커 헬스체크용 루트 별칭 (정식 엔드포인트는 /api/v1/health/live)
    from app.api.v1.routes.health import liveness

    app.add_api_route("/health", liveness, methods=["GET"], include_in_schema=False)

    return app


app = create_app()
