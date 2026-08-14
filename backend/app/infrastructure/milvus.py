"""Milvus 클라이언트 + 컬렉션 스키마 정의."""

import logging
from typing import Any

from pymilvus import DataType, MilvusClient

from app.core.config import Settings

logger = logging.getLogger(__name__)

COLLECTION_MANUAL_CHUNKS = "manual_chunks"


def create_milvus_client(settings: Settings) -> MilvusClient:
    """Milvus 클라이언트 생성 (pymilvus 2.5 스타일)."""
    return MilvusClient(uri=settings.milvus_uri)


def ensure_manual_chunks(client: MilvusClient, dim: int) -> None:
    """manual_chunks 컬렉션이 없으면 생성한다 (멱등)."""
    if client.has_collection(COLLECTION_MANUAL_CHUNKS):
        return
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=32)
    schema.add_field("seq", DataType.INT64)
    schema.add_field("page", DataType.INT64)
    schema.add_field("heading", DataType.VARCHAR, max_length=512)
    schema.add_field("text", DataType.VARCHAR, max_length=8192)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(COLLECTION_MANUAL_CHUNKS, schema=schema, index_params=index_params)
    logger.info("Milvus 컬렉션 생성", extra={"collection": COLLECTION_MANUAL_CHUNKS, "dim": dim})


def search_manual_chunks(
    client: MilvusClient,
    vector: list[float],
    *,
    top_k: int,
    filter_expr: str | None = None,
) -> list[dict[str, Any]]:
    """dense 검색 — COSINE distance → similarity(1-d) 로 변환해 반환."""
    results = client.search(
        collection_name=COLLECTION_MANUAL_CHUNKS,
        data=[vector],
        limit=top_k,
        filter=filter_expr or "",
        output_fields=["doc_id", "seq", "page", "heading", "text"],
        search_params={"metric_type": "COSINE", "params": {"ef": 64}},
    )
    hits: list[dict[str, Any]] = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        hits.append(
            {
                "doc_id": entity["doc_id"],
                "seq": entity["seq"],
                "page": entity["page"],
                "heading": entity["heading"],
                "text": entity["text"],
                "score": 1.0 - hit["distance"],
            }
        )
    return hits


def query_manual_chunks(client: MilvusClient, filter_expr: str) -> list[dict[str, Any]]:
    """expr 로 행 조회 (이웃 청크 확장용)."""
    return list(
        client.query(
            collection_name=COLLECTION_MANUAL_CHUNKS,
            filter=filter_expr,
            output_fields=["doc_id", "seq", "page", "heading", "text"],
        )
    )


def delete_manual_chunks_by_doc(client: MilvusClient, doc_id: str) -> None:
    """문서 삭제/재수집 전 청크 정리 (expr 삭제)."""
    client.delete(collection_name=COLLECTION_MANUAL_CHUNKS, filter=f'doc_id == "{doc_id}"')
