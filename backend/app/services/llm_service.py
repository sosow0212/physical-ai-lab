"""LLM 서비스 — OpenAI 호환 API(GLM Coding Plan 기본) 스트리밍 어댑터.

provider 교체는 .env 의 LLM_* 값만 바꾸면 된다 (ollama/openai 모두 동일 인터페이스).
학습 목적으로 SDK 대신 httpx로 SSE 스트리밍을 직접 파싱한다.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)


async def stream_chat(messages: list[dict[str, str]], *, settings: Settings) -> AsyncIterator[str]:
    """채팅 스트리밍 — content 델타만 yield (reasoning_content는 UI에서 제외)."""
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": True,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }
    # GLM 추론 모델: thinking 토글 (RAG처럼 근거가 주어진 답변엔 disabled가 효과적)
    if settings.llm_provider == "glm":
        payload["thinking"] = {"type": settings.llm_thinking}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    url = f"{settings.llm_base_url}/chat/completions"
    try:
        async with (
            httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http,
            http.stream("POST", url, json=payload, headers=headers) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                delta = _parse_sse_line(line)
                if delta:
                    yield delta
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"LLM 호출 실패: {exc}") from exc


def _parse_sse_line(line: str) -> str | None:
    """data: {...} 한 줄 → content 델타 추출 ([DONE]은 무시)."""
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if data == "[DONE]":
        return None
    try:
        choice = json.loads(data)["choices"][0]
    except (json.JSONDecodeError, KeyError, IndexError):
        return None
    return choice.get("delta", {}).get("content") or None
