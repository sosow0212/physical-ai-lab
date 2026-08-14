"""헬스 API 스파이 테스트 — Phase 1부터 services 단위 테스트를 확장한다."""
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm"]["model"]
