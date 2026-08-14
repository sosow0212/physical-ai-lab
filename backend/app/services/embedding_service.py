"""임베딩 서비스 — Ollama bge-m3 호출 + Redis 캐시(NaN 방지: 실패 시 예외 전파)."""

import hashlib
import json
import logging
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7일


async def embed_texts(
    texts: list[str], *, redis_client: Redis, settings: Settings
) -> list[list[float]]:
    """텍스트 목록 → 벡터 목록. 캐시 조회 후 미스만 배치 호출."""
    if not texts:
        return []
    keys = [_cache_key(settings.embedding_model, t) for t in texts]
    cached = await redis_client.mget(keys)

    result: list[list[float] | None] = [json.loads(c) if c else None for c in cached]
    missing = [i for i, vec in enumerate(result) if vec is None]

    for start in range(0, len(missing), settings.embedding_batch_size):
        batch_idx = missing[start : start + settings.embedding_batch_size]
        vectors = await _call_ollama([texts[i] for i in batch_idx], settings)
        pipe = redis_client.pipeline()
        for idx, vec in zip(batch_idx, vectors, strict=True):
            result[idx] = vec
            pipe.setex(keys[idx], CACHE_TTL_SECONDS, json.dumps(vec))
        await pipe.execute()
        logger.info(
            "임베딩 배치 완료",
            extra={
                "count": len(batch_idx),
                "model": settings.embedding_model,
                "cache_hit": len(texts) - len(missing),
            },
        )
    return [vec for vec in result if vec is not None]  # 타입 좁히기 (미스는 모두 채워짐)


def _cache_key(model: str, text: str) -> str:
    return f"emb:{model}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


async def _call_ollama(inputs: list[str], settings: Settings) -> list[list[float]]:
    payload: dict[str, Any] = {"model": settings.embedding_model, "input": inputs}
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{settings.embedding_base_url}/api/embed", json=payload)
        resp.raise_for_status()
        vectors = resp.json()["embeddings"]
        if len(vectors) != len(inputs) or len(vectors[0]) != settings.embedding_dim:
            raise ExternalServiceError(
                f"임베딩 결과 형식 오류 (dim={len(vectors[0])}, 기대={settings.embedding_dim})"
            )
        return vectors
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"임베딩 서비스 호출 실패: {exc}") from exc
