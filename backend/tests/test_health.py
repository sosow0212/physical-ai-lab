"""헬스 API 테스트 — lifespan 없이(의존성 미연결 상태)에서도 안전한지 확인."""

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_liveness_ok() -> None:
    resp = _client().get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_reports_components_even_without_lifespan() -> None:
    """lifespan 미실행(단위 테스트 환경)이면 컴포넌트가 skipped/degraded 여도 형태는 유지."""
    body = _client().get("/api/v1/health").json()

    assert body["status"] in {"ok", "degraded"}
    assert set(body["components"]) == {"mongo", "redis", "embedding"}
    assert body["llm"]["model"]
    assert body["llm"]["api_key_configured"] is True  # .env의 키 로드 확인


def test_app_error_format() -> None:
    """AppError → 표준 에러 봉투 변환 확인 (핸들러 직접 호출)."""
    import asyncio

    from app.core.errors import NotFoundError, app_error_handler

    async def run() -> tuple:
        from fastapi import Request

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        response = await app_error_handler(request, NotFoundError("문서 없음"))
        return response.status_code, response.body

    status, body = asyncio.run(run())
    import json

    payload = json.loads(body)
    assert status == 404
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "문서 없음"
