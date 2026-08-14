"""헬스체크 API — 프로세스 생존 + 주요 설정 로드 여부 확인."""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness. 인프라별 상세 체크는 Phase 1 lifespan에서 확장한다."""
    s = get_settings()
    return {
        "status": "ok",
        "app_env": s.app_env,
        "llm": {
            "provider": s.llm_provider,
            "model": s.llm_model,
            "api_key_configured": bool(s.llm_api_key),
        },
        "embedding": {"provider": s.embedding_provider, "model": s.embedding_model, "dim": s.embedding_dim},
    }
