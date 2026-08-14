"""앱 라이프사이클 관리 — 시작/종료 시 인프라 연결을 열고 닫는다.

Spring의 @PostConstruct/@PreDestroy + 커너네이너 초기화 대응물.
클라이언트는 app.state 에 보관하고, api/deps.py 에서 요청별로 꺼내 주입한다.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.infrastructure.kafka import create_producer, stop_producer
from app.infrastructure.milvus import (
    create_milvus_client,
    ensure_drawing_cards,
    ensure_manual_chunks,
)
from app.infrastructure.mongo import create_mongo_client
from app.infrastructure.neo4j import create_neo4j_driver
from app.infrastructure.redis import create_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan 컨텍스트 — yield 기준으로 시작/종료 로직이 나뉜다."""
    settings = get_settings()

    mongo_client = create_mongo_client(settings)
    redis_client = create_redis(settings)
    kafka_producer = await create_producer(settings)
    milvus_client = create_milvus_client(settings)
    ensure_manual_chunks(milvus_client, settings.embedding_dim)
    ensure_drawing_cards(milvus_client, settings.embedding_dim)
    neo4j_driver = create_neo4j_driver(settings)
    await neo4j_driver.verify_connectivity()

    app.state.mongo_client = mongo_client
    app.state.mongo_db = mongo_client.get_default_database()
    app.state.redis = redis_client
    app.state.kafka_producer = kafka_producer
    app.state.milvus = milvus_client
    app.state.neo4j = neo4j_driver

    logger.info("인프라 연결 완료", extra={"component": "lifespan"})

    yield

    await stop_producer(kafka_producer)
    await neo4j_driver.close()
    await redis_client.aclose()
    milvus_client.close()
    mongo_client.close()
    logger.info("인프라 연결 종료", extra={"component": "lifespan"})
