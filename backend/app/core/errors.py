"""도메인 예외 정의 + 공통 에러 응답 변환.

Spring의 @ControllerAdvice 대응물.
service 계층은 이 파일의 예외만 던지고, HTTP 상태 코드는 여기서만 다룬다.
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """애플리케이션 예외의 기반 클래스.

    code: 머신이 읽는 에러 코드 (프론트 분기용)
    status: HTTP 상태 코드
    """

    code = "INTERNAL_ERROR"
    status = 500

    def __init__(self, message: str = "", details: Any = None) -> None:
        super().__init__(message or self.__class__.code)
        self.message = message or self.__class__.code
        self.details = details


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status = 404


class ConflictError(AppError):
    code = "CONFLICT"
    status = 409


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status = 422


class IngestionFailedError(AppError):
    code = "INGESTION_FAILED"
    status = 500


class ExternalServiceError(AppError):
    """LLM/임베딩/저장소 등 외부 의존성 장애."""

    code = "EXTERNAL_SERVICE_ERROR"
    status = 502


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """AppError → {"error": {code, message, details?}} 표준 에러 응답."""
    request.state.log_context = {"error_code": exc.code}
    body: dict[str, Any] = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        body["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status, content=body)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상 못한 예외 — 상세는 로그로만, 응답은 일반화된 메시지로."""
    request.state.log_context = {"error_code": "INTERNAL_ERROR"}
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."}},
    )
