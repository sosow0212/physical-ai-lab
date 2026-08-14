# api / worker 공용 이미지 (Phase 2+ 파이프라인 의존성은 여기에 추가)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 의존성 캐싱: lock 파일만 먼저 복사해 설치
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 소스 복사 (개발 중엔 compose volume 마운트가 우선)
COPY . .

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
