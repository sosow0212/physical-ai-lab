"""애플리케이션 설정 — 모든 환경 변수는 이 모듈에서만 읽는다 (12-Factor).

.env 는 docker compose가 컨테이너에 주입하고, pydantic-settings가 이를 파싱한다.
AI 관련 값(LLM_PROVIDER/MODEL/...)도 전부 여기서 관리한다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """전역 설정. 필드명 = 환경 변수명 (대소문자 무관)."""

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            "../.env",
        ),  # 백엔드 디렉터리 기준 → 프로젝트 루트 .env (나중 파일이 우선)
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 앱 ──
    app_env: str = "dev"  # dev | prod
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ── 데이터스토어 ──
    mongo_uri: str = "mongodb://mongo:27017/pal"
    redis_url: str = "redis://redis:6379/0"
    milvus_uri: str = "http://milvus:19530"
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "palpass123"

    # ── Kafka(Redpanda) ──
    kafka_bootstrap: str = "redpanda:29092"
    kafka_group_id: str = "pal-worker"

    # ── LLM (채팅) — provider 공통 OpenAI 호환 인터페이스 ──
    llm_provider: str = "glm"  # glm | openai | ollama
    llm_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    llm_api_key: str = ""
    llm_model: str = "glm-4.6"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120
    # glm 추론 모델의 thinking 토글 — RAG 답변은 근거가 이미 주어져 disabled 기본
    llm_thinking: str = "disabled"  # enabled | disabled

    # ── 임베딩 — 채팅과 별도 provider 가능 ──
    embedding_provider: str = "ollama"  # ollama(로컬) | openai(호환 API)
    embedding_base_url: str = "http://ollama:11434"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    embedding_batch_size: int = 32

    # ── 검색 / 청킹 ──
    retrieval_top_k: int = 8
    chunk_max_chars: int = 900
    chunk_overlap_chars: int = 150

    # ── 스토리지 ──
    upload_dir: str = "/data/uploads"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴 (FastAPI Depends 주입용으로도 사용)."""
    return Settings()
